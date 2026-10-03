"""Downloads AzerothCore's locale tables and converts them to vendor/azerothcore/locales.json.gz.

    python3 etl/fetch_azerothcore.py vendor/azerothcore

AzerothCore emulates Wrath of the Lich King (3.3.5a), so its texts are the state after TBC/WotLK
and can differ from Classic. etl/build.py uses them only as the last fallback for translations
QuestieDB, VMangos, the client cache and Wowhead do not have, and marks them on the site.

The commit is pinned so builds are reproducible; update COMMIT to take newer translations.
"""

import gzip
import json
import sys
import urllib.request
from pathlib import Path

COMMIT = "4d9d1d4b5723e819c5c390f6ca1177283dbfb8e3"  # 2026-06-02, last change of data/sql/base/db_world
BASE = f"https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/{COMMIT}/data/sql/base/db_world"

# table -> (kind, {column index after (id, locale): our field}).
# quest_template_locale columns: Title, Details, Objectives, EndText (area text), CompletedText
# (the "Return to ..." log text, which VMangos calls EndText), ObjectiveText1-4, VerifiedBuild
TABLES = {
    "quest_template_locale": ("quest", {0: "name", 1: "details", 2: "objectivesText", 4: "endText"}),
    "quest_request_items_locale": ("quest", {0: "progress"}),
    "quest_offer_reward_locale": ("quest", {0: "completion"}),
    "creature_template_locale": ("npc", {0: "name", 1: "subName"}),
    "gameobject_template_locale": ("object", {0: "name"}),
    "item_template_locale": ("item", {0: "name", 1: "description"}),
}

ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a"}


def rows(sql):
    """Value tuples of the INSERT statements in a mysqldump file."""
    i, n = 0, len(sql)
    while True:
        i = sql.find("INSERT INTO", i)
        if i < 0:
            return
        i = sql.find("VALUES", i) + 6
        while i < n:
            while sql[i] in " \n\r\t,":
                i += 1
            if sql[i] == ";":
                break
            assert sql[i] == "(", sql[i - 20:i + 20]
            i += 1
            row = []
            while True:
                while sql[i] == " ":
                    i += 1
                if sql[i] == "'":
                    i += 1
                    buf = []
                    while True:
                        c = sql[i]
                        if c == "\\":
                            buf.append(ESCAPES.get(sql[i + 1], sql[i + 1]))
                            i += 2
                        elif c == "'":
                            if sql[i + 1] == "'":
                                buf.append("'")
                                i += 2
                            else:
                                i += 1
                                break
                        else:
                            j = i
                            while sql[j] not in "\\'":
                                j += 1
                            buf.append(sql[i:j])
                            i = j
                    row.append("".join(buf))
                else:
                    j = i
                    while sql[j] not in ",)":
                        j += 1
                    token = sql[i:j].strip()
                    row.append(None if token == "NULL" else int(token) if token.lstrip("-").isdigit() else token)
                    i = j
                if sql[i] == ",":
                    i += 1
                    continue
                i += 1  # ")"
                break
            yield row


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "vendor/azerothcore")
    target.mkdir(parents=True, exist_ok=True)
    out = {}  # kind -> locale -> id -> {field: text}
    for table, (kind, columns) in TABLES.items():
        print(f"downloading {table} …", file=sys.stderr)
        with urllib.request.urlopen(f"{BASE}/{table}.sql") as r:
            sql = r.read().decode("utf-8")
        count = 0
        for row in rows(sql):
            entity_id, values = row[0], row[2:]
            locale = row[1][:2].lower() + row[1][2:].upper()  # a few rows say e.g. "eseS"
            fields = {f: values[c] for c, f in columns.items() if c < len(values) and values[c]}
            if fields:
                out.setdefault(kind, {}).setdefault(locale, {}).setdefault(str(entity_id), {}).update(fields)
                count += 1
        print(f"  {count} rows", file=sys.stderr)
    with gzip.open(target / "locales.json.gz", "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    (target / "VERSION").write_text(f"{COMMIT[:7]}\n")
    print(f"AzerothCore {COMMIT[:7]}", file=sys.stderr)


if __name__ == "__main__":
    main()
