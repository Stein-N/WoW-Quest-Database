"""Minimal reader for a local WoW CASC installation (read-only, unencrypted files only).

Reads files by path from the installed game data, the same storage wow.export opens:

    casc = LocalCasc("~/Games/.../World of Warcraft", product="wow_classic_beta")
    data = casc.read_path("interface/worldmap/elwynn/elwynn1.blp")

Paths are resolved through the root file's Jenkins name hashes, so no listfile is needed.
"""

import struct
import zlib
from pathlib import Path


# ---------------------------------------------------------------------------- name hashing

def _rot(x, k):
    return ((x << k) | (x >> (32 - k))) & 0xFFFFFFFF


def hashlittle2(data, pc=0, pb=0):
    """Bob Jenkins' lookup3 hashlittle2 -> (pc, pb)."""
    length = len(data)
    a = b = c = (0xDEADBEEF + length + pc) & 0xFFFFFFFF
    c = (c + pb) & 0xFFFFFFFF
    i = 0
    while length > 12:
        a = (a + struct.unpack_from("<I", data, i)[0]) & 0xFFFFFFFF
        b = (b + struct.unpack_from("<I", data, i + 4)[0]) & 0xFFFFFFFF
        c = (c + struct.unpack_from("<I", data, i + 8)[0]) & 0xFFFFFFFF
        a = (a - c) & 0xFFFFFFFF; a ^= _rot(c, 4); c = (c + b) & 0xFFFFFFFF
        b = (b - a) & 0xFFFFFFFF; b ^= _rot(a, 6); a = (a + c) & 0xFFFFFFFF
        c = (c - b) & 0xFFFFFFFF; c ^= _rot(b, 8); b = (b + a) & 0xFFFFFFFF
        a = (a - c) & 0xFFFFFFFF; a ^= _rot(c, 16); c = (c + b) & 0xFFFFFFFF
        b = (b - a) & 0xFFFFFFFF; b ^= _rot(a, 19); a = (a + c) & 0xFFFFFFFF
        c = (c - b) & 0xFFFFFFFF; c ^= _rot(b, 4); b = (b + a) & 0xFFFFFFFF
        length -= 12
        i += 12
    if length == 0:
        return c, b
    tail = data[i:] + b"\0" * (12 - length)
    a = (a + struct.unpack_from("<I", tail, 0)[0]) & 0xFFFFFFFF
    b = (b + struct.unpack_from("<I", tail, 4)[0]) & 0xFFFFFFFF
    c = (c + struct.unpack_from("<I", tail, 8)[0]) & 0xFFFFFFFF
    c ^= b; c = (c - _rot(b, 14)) & 0xFFFFFFFF
    a ^= c; a = (a - _rot(c, 11)) & 0xFFFFFFFF
    b ^= a; b = (b - _rot(a, 25)) & 0xFFFFFFFF
    c ^= b; c = (c - _rot(b, 16)) & 0xFFFFFFFF
    a ^= c; a = (a - _rot(c, 4)) & 0xFFFFFFFF
    b ^= a; b = (b - _rot(a, 14)) & 0xFFFFFFFF
    c ^= b; c = (c - _rot(b, 24)) & 0xFFFFFFFF
    return c, b


def name_hash(path):
    norm = path.replace("/", "\\").upper().encode("ascii")
    pc, pb = hashlittle2(norm)
    return (pc << 32) | pb


# ---------------------------------------------------------------------------- BLTE

class EncryptedError(Exception):
    pass


def blte_decode(data):
    if data[:4] != b"BLTE":
        raise ValueError("not a BLTE stream")
    header_size = struct.unpack_from(">I", data, 4)[0]
    chunks = []
    if header_size == 0:
        chunks.append(data[8:])
    else:
        count = int.from_bytes(data[9:12], "big")
        pos, offset = 12, header_size
        for _ in range(count):
            comp_size, _decomp = struct.unpack_from(">II", data, pos)
            chunks.append(data[offset:offset + comp_size])
            offset += comp_size
            pos += 24
    out = bytearray()
    for chunk in chunks:
        mode = chunk[:1]
        if mode == b"N":
            out += chunk[1:]
        elif mode == b"Z":
            out += zlib.decompress(chunk[1:])
        elif mode == b"F":
            out += blte_decode(chunk[1:])
        elif mode == b"E":
            raise EncryptedError("encrypted BLTE chunk")
        else:
            raise ValueError(f"unknown BLTE chunk mode {mode!r}")
    return bytes(out)


# ---------------------------------------------------------------------------- storage

class LocalCasc:
    def __init__(self, game_dir, product):
        self.root_dir = Path(game_dir).expanduser()
        self.data_dir = self.root_dir / "Data"
        self.build_key = self._build_key(product)
        self.build_config = self._read_config(self.build_key)
        self.index = self._load_indices()
        enc_ckey, enc_ekey = self.build_config["encoding"].split()[:2]
        self.encoding_data = self._read_ekey(bytes.fromhex(enc_ekey))
        root_ckey = bytes.fromhex(self.build_config["root"].split()[0])
        root_ekey = self._find_ekeys({root_ckey})[root_ckey]
        self.root_by_hash, self.root_by_fdid = self._parse_root(self._read_ekey(root_ekey))

    # -- configuration

    def _build_key(self, product):
        lines = (self.root_dir / ".build.info").read_text().splitlines()
        cols = [c.split("!")[0] for c in lines[0].split("|")]
        for line in lines[1:]:
            row = dict(zip(cols, line.split("|")))
            if row.get("Product") == product and row.get("Active") == "1":
                self.version = row.get("Version")
                return row["Build Key"]
        raise KeyError(f"product {product} not installed")

    def _read_config(self, key):
        text = (self.data_dir / "config" / key[:2] / key[2:4] / key).read_text()
        out = {}
        for line in text.splitlines():
            if " = " in line:
                k, v = line.split(" = ", 1)
                out[k.strip()] = v.strip()
        return out

    # -- local index (.idx, version 7)

    def _load_indices(self):
        newest = {}
        for f in (self.data_dir / "data").glob("*.idx"):
            bucket, version = int(f.name[:2], 16), int(f.name[2:10], 16)
            if bucket not in newest or version > newest[bucket][0]:
                newest[bucket] = (version, f)
        index = {}
        for _, f in newest.values():
            raw = f.read_bytes()
            header_hash_size = struct.unpack_from("<I", raw, 0)[0]
            pos = (8 + header_hash_size + 0x0F) & ~0x0F
            entries_size = struct.unpack_from("<I", raw, pos)[0]
            pos += 8
            for off in range(pos, pos + entries_size - 17, 18):
                key = raw[off:off + 9]
                packed = int.from_bytes(raw[off + 9:off + 14], "big")
                size = struct.unpack_from("<I", raw, off + 14)[0]
                index.setdefault(key, (packed >> 30, packed & 0x3FFFFFFF, size))
        return index

    def _read_ekey(self, ekey):
        loc = self.index.get(ekey[:9])
        if loc is None:
            raise KeyError(f"ekey {ekey.hex()} not in local storage")
        archive, offset, size = loc
        with open(self.data_dir / "data" / f"data.{archive:03d}", "rb") as f:
            f.seek(offset + 0x1E)
            return blte_decode(f.read(size - 0x1E))

    # -- encoding: CKey -> EKey

    def _find_ekeys(self, ckeys):
        data = self.encoding_data
        ckey_size, ekey_size = data[3], data[4]
        page_size = struct.unpack_from(">H", data, 5)[0] * 1024
        page_count = struct.unpack_from(">I", data, 9)[0]
        espec_size = struct.unpack_from(">I", data, 18)[0]
        pos = 22 + espec_size
        page_index = [data[pos + i * 32:pos + i * 32 + 16] for i in range(page_count)]
        pages_start = pos + page_count * 32
        wanted = sorted(ckeys)
        found = {}
        for ckey in wanted:
            # last page whose first key <= ckey
            lo, hi = 0, page_count - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if page_index[mid] <= ckey:
                    lo = mid
                else:
                    hi = mid - 1
            p = pages_start + lo * page_size
            end = p + page_size
            while p < end:
                key_count = data[p]
                if key_count == 0:
                    break
                entry_ckey = data[p + 6:p + 6 + ckey_size]
                if entry_ckey == ckey:
                    found[ckey] = data[p + 6 + ckey_size:p + 6 + ckey_size + ekey_size]
                    break
                p += 6 + ckey_size + ekey_size * key_count
        return found

    # -- root: FileDataID / name hash -> CKey

    @staticmethod
    def _parse_root(data):
        by_hash, by_fdid, ranks = {}, {}, {}
        if data[:4] != b"TSFM":
            raise ValueError("unsupported root format")
        header_size, version = struct.unpack_from("<II", data, 4)
        if header_size in (0x14, 0x18) and version in (1, 2):
            pos = header_size
        else:  # 8.2 format: magic, total, named
            pos, version = 12, 1
        while pos < len(data):
            count = struct.unpack_from("<I", data, pos)[0]
            if version == 2:
                locale, unk1, unk2 = struct.unpack_from("<III", data, pos + 4)
                content = unk1 | unk2 | (data[pos + 16] << 17)
                pos += 17
            else:
                content, locale = struct.unpack_from("<II", data, pos + 4)
                pos += 12
            deltas = struct.unpack_from(f"<{count}i", data, pos)
            pos += 4 * count
            ckeys_pos = pos
            pos += 16 * count
            has_names = not (content & 0x10000000)
            hashes = struct.unpack_from(f"<{count}Q", data, pos) if has_names else None
            if has_names:
                pos += 8 * count
            fdid = -1
            for i in range(count):
                fdid = fdid + 1 + deltas[i]
                ckey = data[ckeys_pos + i * 16:ckeys_pos + i * 16 + 16]
                # A file can have several variants (locale, platform, ...); keep them all
                # and read whichever is present locally.
                variants = by_fdid.setdefault(fdid, [])
                if ckey not in variants:
                    # enUS first, then locale-neutral, then the rest
                    rank = 0 if locale & 0x2 else 1 if locale == 0xFFFFFFFF else 2
                    variants.append(ckey)
                    ranks.setdefault(fdid, []).append(rank)
                if hashes:
                    by_hash[hashes[i]] = fdid
        for fdid, variants in by_fdid.items():
            order = sorted(range(len(variants)), key=lambda i: ranks[fdid][i])
            by_fdid[fdid] = [variants[i] for i in order]
        return by_hash, by_fdid

    # -- public

    def fdid_for_path(self, path):
        return self.root_by_hash.get(name_hash(path))

    def read_fdid(self, fdid):
        ckeys = self.root_by_fdid[fdid]
        ekeys = self._find_ekeys(set(ckeys))
        for ckey in ckeys:
            ekey = ekeys.get(ckey)
            if ekey is not None and ekey[:9] in self.index:
                return self._read_ekey(ekey)
        raise KeyError(f"fdid {fdid} is not in local storage")

    def read_path(self, path):
        fdid = self.fdid_for_path(path)
        if fdid is None:
            raise KeyError(path)
        return self.read_fdid(fdid)
