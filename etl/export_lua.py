"""Exports the merged site data (QuestieDB + VMangos) as Lua tables, e.g. for an addon.

The website's Export page does the same in the browser (web/src/lib/lua-export.ts); keep
both producing identical output.

    python3 etl/export_lua.py --flavor forever --type quest -o export/
    python3 etl/export_lua.py --flavor classic --type npc --zone 12 --locale deDE -o export/
    python3 etl/export_lua.py --flavor forever --type questline --style return

Reads web/static/data (run `make data` first). Texts (names, quest texts, descriptions) always
go to their own file, linked by the entity ID:

    questData.lua                          questTexts.deDE.lua
    local _, addon = ...                   local _, addon = ...
    addon.questData = {                    addon.questTexts = addon.questTexts or {}
        [2] = { level = 30, ... },         addon.questTexts["deDE"] = {
    }                                          [2] = { name = "Klaue von Scharfkralle", ... },
                                           }

Options:
  --type      quest | npc | object | item | questline
  --fields    comma-separated top-level fields to keep (default: all)
  --exclude   comma-separated fields to drop (e.g. spawns,sources)
  --ids       comma-separated IDs, or a range like 100-200
  --zone      only entities whose zone (or questline zone) is this area ID
  --locale    language of the texts and names (default enUS; deDE, frFR, ...),
              or "all" for one texts file per language
  --refs      id (default): references to other entities become plain IDs;
              full: keep {t, id, name, ...} tables
  --style     addon (default): `local _, addon = ...` + addon.<var> = {...}
              return: `return {...}` for dofile/require
  --var       data table name (default: <type>Data)
  --text-var  texts table name (default: <type>Texts)
  -o/--out-dir  directory for <var>.lua and <text-var>.<locale>.lua (default: .)
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
# Texts are always written to their own file (<name>Texts.<locale>.lua), keyed by entity ID.
TEXT_FIELDS = {
    "quest": ("name", "objectivesText", "details", "progress", "completion", "endText"),
    "npc": ("name", "subName"),
    "object": ("name",),
    "item": ("name", "description"),
}
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
    """{t, id, name, ...} -> id, keeping extra facts such as chance or count.

    Zone references become their area ID and faction/skill references lose their name, so the
    data file carries no display text at all.
    """
    if isinstance(value, dict):
        keys = set(value)
        if keys in ({"zone", "name"}, {"sort", "name"}):
            return value.get("zone", value.get("sort"))
        if "id" in keys and "name" in keys and "t" not in keys and keys <= {"id", "name", "value"}:
            return {k: v for k, v in value.items() if k != "name"} if "value" in keys else value["id"]
        if "t" in value and "id" in value:
            extra = {k: v for k, v in value.items() if k not in ("t", "id", "name", "q", "lvl", "missing")}
            if not extra:
                return value["id"]
            return {"id": value["id"], **{k: compact_refs(v) for k, v in extra.items()}}
        return {k: compact_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [compact_refs(v) for v in value]
    return value


def quest_rewards_format(rewards, refs):
    """rewards.items groups -> the QuestRewards.lua shape, merged into rewards:

        type = "all",    items = {...}                  every item is rewarded
        type = "single", items = {...}, fixed = {...}   choose one of items, plus all fixed ones

    With ID references, item lists are plain IDs and amounts above one go to counts[itemId].
    """
    groups = rewards.get("items")
    if not groups:
        return rewards
    fixed = next((g["items"] for g in groups if g["kind"] == "fixed"), [])
    choice = next((g["items"] for g in groups if g["kind"] == "choice"), [])
    out = {"type": "single", "items": choice, "fixed": fixed} if choice else {"type": "all", "items": fixed}
    if not out.get("fixed"):
        out.pop("fixed", None)
    if refs == "id":
        # sorted by item ID, matching the browser export (JS orders integer keys numerically)
        counts = {str(r["id"]): r["count"] for r in sorted(choice + fixed, key=lambda r: r["id"])
                  if (r.get("count") or 1) > 1}
        out["items"] = [r["id"] for r in out["items"]]
        if "fixed" in out:
            out["fixed"] = [r["id"] for r in out["fixed"]]
        if counts:
            out["counts"] = counts
    return {**out, **{k: v for k, v in rewards.items() if k != "items"}}


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


def export_text(value):
    """The player's name placeholder $N becomes ${playerName} in exported texts."""
    if isinstance(value, list):
        return [export_text(v) for v in value]
    return re.sub(r"\$[Nn]", "${playerName}", value) if isinstance(value, str) else value


def text_var_for(var):
    return var[:-4] + "Texts" if var.endswith("Data") else var + "Texts"


def header(file_name, description, count, meta):
    return [
        f"-- {file_name}",
        "--",
        f"-- {description}",
        f"-- Sources: QuestieDB {meta.get('questie')}, VMangos {meta.get('vmangos')} (built {meta.get('built')}).",
        f"-- Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by: "
        f"etl/export_lua.py {' '.join(sys.argv[1:])}",
        f"-- {count} entries.",
        "",
    ]


def render_data(records, args, meta, file_name, texts_file):
    flavor = meta["flavors"][args.flavor]["label"]
    lines = header(file_name, f"{args.type} data for {flavor}, exported from the WoW Quest Database.",
                   len(records), meta)
    if texts_file:
        lines[3:3] = [f"-- Texts (names, descriptions, ...) are in {texts_file}, keyed by the same IDs."]
    body = [f"    [{entity_id}] = {lua_value(rec)}," for entity_id, rec in sorted(records.items())]
    if args.style == "return":
        return "\n".join(lines + ["return {"] + body + ["}", ""])
    return "\n".join(lines + ["local _, addon = ...", "", f"addon.{args.var} = {{"] + body + ["}", ""])


def render_texts(texts, args, meta, file_name, locale):
    flavor = meta["flavors"][args.flavor]["label"]
    lines = header(file_name, f"{args.type} texts ({locale}) for {flavor}, keyed by {args.type} ID.",
                   len(texts), meta)
    body = [f"    [{entity_id}] = {lua_value(rec)}," for entity_id, rec in sorted(texts.items())]
    if args.style == "return":
        return "\n".join(lines + ["return {"] + body + ["}", ""])
    table = f"addon.{args.text_var}"
    return "\n".join(lines + ["local _, addon = ...", "", f"{table} = {table} or {{}}",
                              f"{table}[{lua_string(locale)}] = {{"] + body + ["}", ""])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flavor", required=True, choices=["classic", "forever"])
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--fields")
    ap.add_argument("--exclude")
    ap.add_argument("--ids")
    ap.add_argument("--zone", type=int)
    ap.add_argument("--locale", default="enUS")
    ap.add_argument("--refs", choices=["id", "full"], default="id")
    ap.add_argument("--style", choices=["addon", "return"], default="addon")
    ap.add_argument("--var")
    ap.add_argument("--text-var")
    ap.add_argument("-o", "--out-dir", default=".")
    args = ap.parse_args()
    args.var = args.var or f"{args.type}Data"
    args.text_var = args.text_var or text_var_for(args.var)
    for name in (args.var, args.text_var):
        if not IDENT.match(name) or name in LUA_KEYWORDS:
            sys.exit(f"table names must be Lua identifiers: {name}")

    meta = json.loads((DATA / "meta.json").read_text())
    records = load_records(args.flavor, args.type)

    if args.ids:
        wanted = parse_ids(args.ids)
        records = {i: r for i, r in records.items() if i in wanted}
    if args.zone is not None:
        records = {i: r for i, r in records.items() if zone_of(r) == args.zone}

    all_locales = ["enUS"] + meta["locales"]
    if args.locale != "all" and args.locale not in all_locales:
        sys.exit(f"unknown locale {args.locale}; available: all, {', '.join(all_locales)}")
    # "all": one data file (English references) plus a texts file for every language
    locales = all_locales if args.locale == "all" else [args.locale]

    keep = set(args.fields.split(",")) if args.fields else None
    drop = set(args.exclude.split(",")) if args.exclude else set()
    text_fields = TEXT_FIELDS.get(args.type, ())

    def localized(locale):
        if locale == "enUS":
            return records
        names = json.loads((DATA / args.flavor / "l10n" / locale / "search.json").read_text())
        zone_names = json.loads((DATA / args.flavor / "l10n" / locale / "zones.json").read_text())
        translated = load_l10n(args.flavor, args.type, locale) if args.type != "questline" else {}
        return {i: localize_refs({**r, **translated.get(i, {})}, names, zone_names) for i, r in records.items()}

    def split(recs):
        data, texts = {}, {}
        for entity_id, rec in recs.items():
            rec = {k: v for k, v in rec.items() if (keep is None or k in keep) and k not in drop and k not in ("id", "azerothcore")}
            text = {k: export_text(rec.pop(k)) for k in text_fields if k in rec}
            if args.type == "quest" and rec.get("rewards"):
                rec["rewards"] = quest_rewards_format(rec["rewards"], args.refs)
            data[entity_id] = compact_refs(rec) if args.refs == "id" else rec
            if text:
                texts[entity_id] = text
        return data, texts

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_file = f"{args.var}.lua"
    for n, locale in enumerate(locales):
        data, texts = split(localized(locale))
        texts_file = f"{args.text_var}.{locale}.lua" if texts else None
        if n == 0 and (any(data.values()) or not texts):
            reference = f"{args.text_var}.<locale>.lua (one file per language)" if len(locales) > 1 else texts_file
            (out_dir / data_file).write_text(
                render_data(data, args, meta, data_file, reference if texts else None), encoding="utf-8")
            print(f"wrote {len(data)} entries to {out_dir / data_file}", file=sys.stderr)
        if texts:
            (out_dir / texts_file).write_text(render_texts(texts, args, meta, texts_file, locale), encoding="utf-8")
            print(f"wrote {len(texts)} entries to {out_dir / texts_file}", file=sys.stderr)
        elif n == 0:
            break  # no text fields selected: nothing per language


if __name__ == "__main__":
    main()
