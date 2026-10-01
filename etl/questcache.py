"""Reads quest texts from WoW client cache files (Cache/WDB/<locale>/questcache.wdb).

The client stores the server's quest query responses there for every quest the player has
seen. That is the only source for texts of quests that neither QuestieDB nor VMangos have,
e.g. the new WoW Forever quests.

    python3 etl/questcache.py <questcache.wdb> [...]     # print what is found

Record layout (Classic Era 1.15 / Forever 1.60 clients, verified against known quest names):
    ... fixed fields ...
    objectives, each: u32 id | u8 type | 4 bytes | i32 objectId (+9) | i32 amount (+13) | ...
                      | i32 visualEffectCount n (+33) | 4 bytes | n x i32 effects (+41)
                      | u8 descLen | 1 byte bit flags | desc (descLen bytes)
    12 bytes bit-packed string lengths (MSB first): title 9, logDescription 12,
        questDescription 12, areaDescription 9, portraitGiverText 10, portraitGiverName 8,
        portraitTurnInText 10, portraitTurnInName 8, questCompletionLog 11, (+ flags)
    the strings, in that order, ending the record

The string header is found by scanning; only the position where a chain of objective
records ends exactly at it (and the title looks like a title) is accepted.
"""

import re
import struct
import sys
from pathlib import Path

STRING_FIELDS = [
    ("title", 9), ("logDescription", 12), ("questDescription", 12), ("areaDescription", 9),
    ("portraitGiverText", 10), ("portraitGiverName", 8), ("portraitTurnInText", 10),
    ("portraitTurnInName", 8), ("completionLog", 11),
]
HEADER_LEN = 12
OBJ_FIXED = 43          # objective record size without visual effects and description
OBJ_AMOUNT = 13         # offset of the amount inside an objective record
OBJ_EFFECTS = 33        # offset of the visual effect count
OBJ_DESC_LEN = 41       # offset of the description length byte (without visual effects)
MAX_OBJECTIVES = 12


def read_wdb(path):
    """-> (magic, build, locale, {record id: bytes})"""
    data = Path(path).read_bytes()
    if len(data) < 24:
        raise ValueError(f"{path}: not a WDB file")
    magic = data[:4]
    build = struct.unpack_from("<I", data, 4)[0]
    locale = data[8:12][::-1].decode("ascii", "replace")
    records, pos = {}, 24
    while pos + 8 <= len(data):
        rid, length = struct.unpack_from("<II", data, pos)
        if length == 0 or pos + 8 + length > len(data):
            break
        records[rid] = data[pos + 8:pos + 8 + length]
        pos += 8 + length
    return magic, build, locale, records


def _lengths(rec, pos):
    value = int.from_bytes(rec[pos:pos + HEADER_LEN], "big")
    shift, out = HEADER_LEN * 8, []
    for _, width in STRING_FIELDS:
        shift -= width
        out.append((value >> shift) & ((1 << width) - 1))
    return out


def _objective_chain(rec, header):
    """Objective amounts if a chain of objective records ends exactly at `header`, else None."""
    best = None
    # walk candidate starts backwards; the longest consistent chain wins
    for start in range(header - OBJ_FIXED, max(-1, header - MAX_OBJECTIVES * (OBJ_FIXED + 255)), -1):
        pos, amounts, ids = start, [], []
        while pos + OBJ_FIXED <= header:
            # objective ids are large database ids, the type a small enum value
            if struct.unpack_from("<I", rec, pos)[0] < 1000 or rec[pos + 4] > 30:
                break
            effects = struct.unpack_from("<i", rec, pos + OBJ_EFFECTS)[0]
            if not 0 <= effects <= 8 or pos + OBJ_FIXED + 4 * effects > header:
                break
            desc_len = rec[pos + OBJ_DESC_LEN + 4 * effects]
            desc_start = pos + OBJ_FIXED + 4 * effects
            end = desc_start + desc_len
            if end > header:
                break
            try:
                rec[desc_start:end].decode("utf-8")
            except UnicodeDecodeError:
                break
            ids.append(struct.unpack_from("<I", rec, pos)[0])
            amounts.append(struct.unpack_from("<i", rec, pos + OBJ_AMOUNT)[0])
            pos = end
        if pos == header and amounts and all(0 < b - a < 64 for a, b in zip(ids, ids[1:])):
            if all(0 < a < 10000 for a in amounts) and (best is None or len(amounts) > len(best)):
                best = amounts
    return best


def _looks_like_title(text):
    return (
        0 < len(text) <= 120
        and "\n" not in text
        and not text[0].islower()
        and not text.startswith(" ")
        and all(ord(c) >= 32 for c in text)
    )


def parse_quest(rec):
    """-> dict with title, objectives, details, ... or None if the record can't be read."""
    found = []
    for pos in range(0, len(rec) - HEADER_LEN):
        lengths = _lengths(rec, pos)
        total = sum(lengths)
        if lengths[0] == 0 or total > len(rec) - pos - HEADER_LEN:
            continue
        strings, offset = {}, len(rec) - total
        try:
            for (name, _), n in zip(STRING_FIELDS, lengths):
                strings[name] = rec[offset:offset + n].decode("utf-8")
                offset += n
        except UnicodeDecodeError:
            continue
        if not _looks_like_title(strings["title"]) or not strings["logDescription"]:
            continue
        # objectives sit between the fixed part and the header; quests without
        # objectives (talk-to quests) have none, so accept that too
        amounts = _objective_chain(rec, pos)
        found.append((amounts is not None, pos, strings, amounts or []))
    if not found:
        return None
    # prefer a header confirmed by an objective chain, then the last plausible one
    found.sort(key=lambda f: (f[0], f[1]))
    confirmed, _, strings, amounts = found[-1]
    return {"strings": strings, "amounts": amounts, "confirmed": confirmed}


_PLACEHOLDER = re.compile(r"\$(\d+)o[a-z]")


def fill_amounts(text, amounts):
    """$1oa -> amount of objective 1 (client placeholder for objective quantities)."""
    def sub(m):
        i = int(m.group(1)) - 1
        return str(amounts[i]) if 0 <= i < len(amounts) else m.group(0)
    return _PLACEHOLDER.sub(sub, text)


def _normalize(text):
    """Line breaks as $B, like VMangos texts (the site renders $B as a line break)."""
    return text.replace("\r\n", "$B").replace("\n", "$B")


def quest_texts(path):
    """-> (locale, build, {quest id: {name, objectivesText, details, endText}})"""
    magic, build, locale, records = read_wdb(path)
    if magic != b"TSQW":
        raise ValueError(f"{path}: not a quest cache (magic {magic!r})")
    out = {}
    for quest_id, rec in records.items():
        parsed = parse_quest(rec)
        if not parsed:
            continue
        s, amounts = parsed["strings"], parsed["amounts"]
        entry = {
            "name": s["title"],
            "objectivesText": [_normalize(fill_amounts(s["logDescription"], amounts))],
            "details": _normalize(fill_amounts(s["questDescription"], amounts)) if s["questDescription"] else None,
            "endText": _normalize(s["completionLog"]) or None,
            "_confirmed": parsed["confirmed"],
        }
        out[quest_id] = {k: v for k, v in entry.items() if v is not None}
    return locale, build, out


def main():
    for path in sys.argv[1:]:
        locale, build, quests = quest_texts(path)
        print(f"== {path}: {locale}, build {build}, {len(quests)} quests")
        for qid, e in sorted(quests.items()):
            flag = "" if e["_confirmed"] else "  (unconfirmed)"
            print(f"  {qid}: {e['name']}{flag}\n      {e['objectivesText'][0][:90]}")


if __name__ == "__main__":
    main()
