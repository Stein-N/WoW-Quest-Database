"""Minimal WDC5 (DB2) reader: yields inline fields, the record ID and the relation column.

Only what the UiMap tables need: scalar fields (no arrays/strings), non-inline IDs and one
non-inline relation. Encrypted sections are skipped.
"""

import struct


def read_wdc5(data):
    """-> list of dicts {"id": int, "fields": [int, ...], "relation": int | None}"""
    if data[:4] != b"WDC5":
        raise ValueError(f"unsupported DB2 format {data[:4]!r}")
    pos = 4 + 4 + 128  # magic, version, schema string
    (record_count, field_count, record_size, string_table_size, _table_hash, _layout_hash,
     _min_id, _max_id, _locale, flags, id_index, _total_field_count, _bitpacked_offset,
     _lookup_columns, storage_info_size, common_size, pallet_size, section_count) = struct.unpack_from(
        "<9IHH7I", data, pos)
    pos += struct.calcsize("<9IHH7I")

    sections = []
    for _ in range(section_count):
        sections.append(struct.unpack_from("<QIIIIIIII", data, pos))
        pos += 40
    pos += field_count * 4  # field structure (size/offset); storage info carries the same

    storage = []
    for _ in range(storage_info_size // 24):
        storage.append(struct.unpack_from("<HHIIIII", data, pos))
        pos += 24

    pallet_start = pos
    pos += pallet_size
    common_start = pos
    pos += common_size

    # Per-field offsets into the pallet / common data blocks, plus common-data lookups.
    pallet_offsets, common_maps = [], []
    p_off = c_off = 0
    for (_off_bits, _size_bits, additional, ctype, _v1, _v2, _v3) in storage:
        pallet_offsets.append(pallet_start + p_off)
        cmap = {}
        if ctype == 2:
            for i in range(additional // 8):
                rid, value = struct.unpack_from("<II", data, common_start + c_off + i * 8)
                cmap[rid] = value
            c_off += additional
        elif ctype in (3, 4):
            p_off += additional
        common_maps.append(cmap)

    if flags & 0x1:
        raise ValueError("offset-map DB2 files are not supported")

    rows = []
    for (tact_key, file_offset, count, strings_size, _records_end, id_list_size,
         relationship_size, offset_map_count, copy_count) in sections:
        if count == 0:
            continue
        p = file_offset
        records = data[p:p + count * record_size]
        p += count * record_size + strings_size
        ids = list(struct.unpack_from(f"<{id_list_size // 4}I", data, p)) if id_list_size else None
        p += id_list_size
        copies = [struct.unpack_from("<II", data, p + i * 8) for i in range(copy_count)]
        p += copy_count * 8
        p += offset_map_count * 6
        relations = {}
        if relationship_size:
            n = struct.unpack_from("<I", data, p)[0]
            for i in range(n):
                foreign, index = struct.unpack_from("<II", data, p + 12 + i * 8)
                relations[index] = foreign
        if tact_key and not any(records):
            continue  # encrypted section without key
        for i in range(count):
            rec = int.from_bytes(records[i * record_size:(i + 1) * record_size], "little")
            fields = []
            for f, (off_bits, size_bits, _add, ctype, v1, v2, v3) in enumerate(storage):
                if ctype == 0:
                    value = (rec >> off_bits) & ((1 << size_bits) - 1)
                elif ctype in (1, 5):
                    value = (rec >> v1) & ((1 << v2) - 1)
                    if ctype == 5 and value >> (v2 - 1):
                        value -= 1 << v2
                elif ctype == 2:
                    value = None  # resolved below once the ID is known
                elif ctype in (3, 4):
                    index = (rec >> v1) & ((1 << v2) - 1)
                    width = 4 * (v3 if ctype == 4 else 1)
                    value = struct.unpack_from("<I", data, pallet_offsets[f] + index * width)[0]
                else:
                    raise ValueError(f"unknown compression {ctype}")
                fields.append(value)
            rid = ids[i] if ids else fields[id_index]
            for f, (_o, _s, _a, ctype, v1, _v2, _v3) in enumerate(storage):
                if ctype == 2:
                    fields[f] = common_maps[f].get(rid, v1)
            rows.append({"id": rid, "fields": fields, "relation": relations.get(i)})
        by_id = {r["id"]: r for r in rows}
        for new_id, old_id in copies:
            if old_id in by_id:
                rows.append({**by_id[old_id], "id": new_id})
    return rows
