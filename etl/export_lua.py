"""Exports the merged site data (QuestieDB + VMangos) as Lua tables, e.g. for an addon.

    python3 etl/export_lua.py --flavor forever --type quest --fields name,level,rewards
    python3 etl/export_lua.py --flavor classic --type npc --zone 12 --locale deDE -o npcs.lua
    python3 etl/export_lua.py --flavor forever --type questline --style return

Reads web/static/data (run `make data` first). Output, by default in the same shape as
QuestRewards.lua:

    local _, addon = ...

    addon.questData = {
        [2] = { name = "Sharptalon's Claw", level = 30, ... },
    }

Options:
  --type      quest | npc | object | item | questline
  --fields    comma-separated top-level fields to keep (default: all)
  --exclude   comma-separated fields to drop (e.g. spawns,sources)
  --ids       comma-separated IDs, or a range like 100-200
  --zone      only entities whose zone (or questline zone) is this area ID
  --locale    merge translated texts (deDE, frFR, ...) over the English ones
  --refs      id (default): references to other entities become plain IDs;
              full: keep {t, id, name, ...} tables
  --style     addon (default): `local _, addon = ...` + addon.<var> = {...}
              return: `return {...}` for dofile/require
  --var       table name for --style addon (default: <type>Data)
  -o/--out    output file (default: stdout)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "static" / "data"
TYPES = ("quest", "npc", "object", "item", "questline")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LUA_KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if",
    "in", "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
}


# ---------------------------------------------------------------------------- loading

def load_records(flavor, kind):
    base = DATA / flavor
    if not base.exists():
        sys.exit(f"{base} not found — run `make data` first")
    if kind == "questline":
        return {line["id"]: line for line in json.loads((base / "questlines.json").read_text())}
    records = {}
    for shard in (base / kind).glob("*.json"):
        records.update({int(k): v for k, v in json.loads(shard.read_text()).items()})
    return records


def load_l10n(flavor, kind, locale):
    out = {}
    for shard in (DATA / flavor / "l10n" / locale / kind).glob("*.json"):
        out.update({int(k): v for k, v in json.loads(shard.read_text()).items()})
    return out


def localize_refs(value, names, zone_names):
    """Replaces English names inside entity and zone references with the translated ones."""
    if isinstance(value, dict):
        if "t" in value and "id" in value and "name" in value:
            value = {**value, "name": names.get(value["t"], {}).get(str(value["id"]), value["name"])}
        elif "zone" in value and "name" in value and str(value["zone"]) in zone_names:
            value = {**value, "name": zone_names[str(value["zone"])]}
        return {k: localize_refs(v, names, zone_names) for k, v in value.items()}
    if isinstance(value, list):
        return [localize_refs(v, names, zone_names) for v in value]
    return value


def compact_refs(value):
    """{t, id, name, ...} -> id, keeping extra facts such as chance or count."""
    if isinstance(value, dict):
        if "t" in value and "id" in value:
            extra = {k: v for k, v in value.items() if k not in ("t", "id", "name", "q", "lvl", "missing")}
            if not extra:
                return value["id"]
            return {"id": value["id"], **{k: compact_refs(v) for k, v in extra.items()}}
        return {k: compact_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [compact_refs(v) for v in value]
    return value


def parse_ids(spec):
    ids = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part[1:]:
            lo, hi = part.split("-", 1)
            ids.update(range(int(lo), int(hi) + 1))
        elif part:
            ids.add(int(part))
    return ids


def zone_of(record):
    zone = record.get("zone")
    if isinstance(zone, dict):
        return zone.get("zone") or zone.get("sort")
    return zone


# ---------------------------------------------------------------------------- Lua output

def lua_string(s):
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    out = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", lambda m: f"\\{ord(m.group()):03d}", out)
    return f'"{out}"'


def lua_key(key):
    if isinstance(key, int) or (isinstance(key, str) and re.fullmatch(r"-?\d+", key)):
        return f"[{int(key)}]"
    if IDENT.match(key) and key not in LUA_KEYWORDS:
        return key
    return f"[{lua_string(key)}]"


def lua_value(value):
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, list):
        return "{" + ", ".join(lua_value(v) for v in value) + "}"
    if isinstance(value, dict):
        items = [(k, v) for k, v in value.items() if v is not None]
        return "{ " + ", ".join(f"{lua_key(k)} = {lua_value(v)}" for k, v in items) + " }" if items else "{}"
    raise TypeError(f"cannot convert {type(value).__name__}")


def render(records, args, meta):
    header = [
        f"-- {Path(args.out).name if args.out else args.var + '.lua'}",
        "--",
        f"-- {args.type} data for {meta['flavors'][args.flavor]['label']}, exported from the WoW Quest Database.",
        f"-- Sources: QuestieDB {meta.get('questie')}, VMangos {meta.get('vmangos')} (built {meta.get('built')}).",
        f"-- Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by: "
        f"etl/export_lua.py {' '.join(sys.argv[1:])}",
        f"-- {len(records)} entries.",
        "",
    ]
    body = [f"    [{entity_id}] = {lua_value(rec)}," for entity_id, rec in sorted(records.items())]
    if args.style == "return":
        return "\n".join(header + ["return {"] + body + ["}", ""])
    return "\n".join(header + ["local _, addon = ...", "", f"addon.{args.var} = {{"] + body + ["}", ""])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flavor", required=True, choices=["classic", "forever"])
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--fields")
    ap.add_argument("--exclude")
    ap.add_argument("--ids")
    ap.add_argument("--zone", type=int)
    ap.add_argument("--locale")
    ap.add_argument("--refs", choices=["id", "full"], default="id")
    ap.add_argument("--style", choices=["addon", "return"], default="addon")
    ap.add_argument("--var")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    args.var = args.var or f"{args.type}Data"
    if not IDENT.match(args.var):
        sys.exit(f"--var must be a Lua identifier: {args.var}")

    meta = json.loads((DATA / "meta.json").read_text())
    records = load_records(args.flavor, args.type)

    if args.ids:
        wanted = parse_ids(args.ids)
        records = {i: r for i, r in records.items() if i in wanted}
    if args.zone is not None:
        records = {i: r for i, r in records.items() if zone_of(r) == args.zone}

    if args.locale and args.locale != "enUS":
        if args.locale not in meta["locales"]:
            sys.exit(f"unknown locale {args.locale}; available: {', '.join(meta['locales'])}")
        names = json.loads((DATA / args.flavor / "l10n" / args.locale / "search.json").read_text())
        zone_names = json.loads((DATA / args.flavor / "l10n" / args.locale / "zones.json").read_text())
        translated = load_l10n(args.flavor, args.type, args.locale) if args.type != "questline" else {}
        records = {i: localize_refs({**r, **translated.get(i, {})}, names, zone_names) for i, r in records.items()}

    keep = set(args.fields.split(",")) if args.fields else None
    drop = set(args.exclude.split(",")) if args.exclude else set()
    out = {}
    for entity_id, rec in records.items():
        rec = {k: v for k, v in rec.items() if (keep is None or k in keep) and k not in drop and k != "id"}
        out[entity_id] = compact_refs(rec) if args.refs == "id" else rec

    text = render(out, args, meta)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(out)} entries to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
