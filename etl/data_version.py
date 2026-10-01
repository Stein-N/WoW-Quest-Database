"""Writes data-version.json: which QuestieDB commit and VMangos snapshot the site is built from.

    python3 etl/data_version.py [data-version.json]

Used by the daily release workflow: a change of this file (or of the code) since the last
release is what triggers a new release.
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = "https://api.github.com/repos/vmangos/core/releases/tags/db_latest"


def questie():
    out = subprocess.check_output(
        ["git", "-C", str(ROOT / "vendor" / "QuestieDB"), "log", "-1", "--format=%H%n%cs%n%s"], text=True
    ).splitlines()
    return {"commit": out[0], "date": out[1], "subject": out[2]}


def vmangos():
    with urllib.request.urlopen(RELEASE) as r:
        release = json.load(r)
    asset = next(a for a in release["assets"] if "sqlite" in a["name"])
    return {"snapshot": asset["name"].removesuffix(".zip"), "published": release["published_at"][:10]}


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data-version.json"
    data = {"questie": questie(), "vmangos": vmangos()}
    target.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data))


if __name__ == "__main__":
    main()
