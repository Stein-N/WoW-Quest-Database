"""Imports quest texts from WoW client caches into etl/corrections/questcache/<flavor>/<locale>.json.

    python3 etl/import_questcache.py --flavor forever <questcache.wdb or Cache/WDB dir> [...]

Accepts questcache.wdb files or directories containing them (e.g. a client's Cache/WDB folder
with one subfolder per language). Entries are merged into the existing files: quests already
there are replaced only by data from the same or a newer client build. etl/build.py uses these
texts only where QuestieDB and VMangos have none.

English titles are cross-checked against the quest names known from QuestieDB; a mismatch
means the record was not read correctly and the quest is skipped.
"""

import argparse
import json
import sys
from pathlib import Path

from questcache import quest_texts

ROOT = Path(__file__).resolve().parent.parent
FLAVOR_DATA = {"classic": "classic", "forever": "forever"}


def known_names(flavor):
    path = ROOT / "build" / "questie" / flavor / "Quest.json"
    if not path.exists():
        return {}
    return {int(k): v.get("name") for k, v in json.loads(path.read_text()).items()}


def cache_files(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(p.rglob("questcache.wdb"))
        else:
            yield p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flavor", required=True, choices=sorted(FLAVOR_DATA))
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    names = known_names(args.flavor)
    out_dir = ROOT / "etl" / "corrections" / "questcache" / args.flavor
    out_dir.mkdir(parents=True, exist_ok=True)
    totals = {}

    for path in cache_files(args.paths):
        locale, build, quests = quest_texts(path)
        if not quests:
            print(f"{path}: {locale}, build {build}: no quests", file=sys.stderr)
            continue
        target = out_dir / f"{locale}.json"
        store = json.loads(target.read_text()) if target.exists() else {
            "_comment": "Quest texts read from WoW client caches (etl/import_questcache.py). "
                        "Used by etl/build.py only where QuestieDB and VMangos have no text.",
            "quests": {},
        }
        added = updated = skipped = 0
        for quest_id, entry in sorted(quests.items()):
            if not entry.pop("_confirmed"):
                skipped += 1
                print(f"  skip {quest_id}: record layout not confirmed", file=sys.stderr)
                continue
            if locale == "enUS" and names.get(quest_id) and names[quest_id] != entry["name"]:
                skipped += 1
                print(f"  skip {quest_id}: title {entry['name']!r} != known name {names[quest_id]!r}",
                      file=sys.stderr)
                continue
            if names and quest_id not in names:
                print(f"  note {quest_id}: not in {args.flavor} quest data (kept anyway)", file=sys.stderr)
            existing = store["quests"].get(str(quest_id))
            if existing and existing.get("build", 0) > build:
                continue
            store["quests"][str(quest_id)] = {**entry, "build": build}
            if existing:
                updated += 1
            else:
                added += 1
        store["quests"] = dict(sorted(store["quests"].items(), key=lambda kv: int(kv[0])))
        target.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        totals[locale] = len(store["quests"])
        print(f"{path}: {locale}, build {build}: {added} added, {updated} updated, {skipped} skipped "
              f"-> {target.relative_to(ROOT)}", file=sys.stderr)

    for locale, n in sorted(totals.items()):
        print(f"{args.flavor}/{locale}: {n} quests in cache corrections")


if __name__ == "__main__":
    main()
