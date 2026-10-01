"""Maintains CHANGELOG.json, the patch notes shown on the website's start page.

    python3 etl/changelog.py backfill            # (re)build entries for all release tags
    python3 etl/changelog.py add 0.1.2           # entry for a new version: commits since the
                                                 # last tag up to HEAD, data from data-version.json

Each entry: version, date, data version (QuestieDB commit, VMangos snapshot) and the commit
subjects of the release. The release workflow runs `add` before building the image, so every
image already contains its own notes.
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.json"
# bookkeeping commits that are not changes of their own
SKIP_PREFIXES = ("Release v", "Initial commit")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def tags():
    out = git("tag", "-l", "v[0-9]*.[0-9]*.[0-9]*", "--sort=v:refname")
    return [t for t in out.splitlines() if t]


def subjects(since, until):
    rng = f"{since}..{until}" if since else until
    lines = git("log", "--reverse", "--format=%s", rng).splitlines()
    return [s for s in lines if s and not s.startswith(SKIP_PREFIXES)]


def data_version(ref):
    try:
        raw = git("show", f"{ref}:data-version.json")
    except subprocess.CalledProcessError:
        return None
    d = json.loads(raw)
    return {
        "questie": {k: d["questie"][k] for k in ("commit", "date", "subject")},
        "vmangos": {k: d["vmangos"][k] for k in ("snapshot", "published")},
    }


def entry(version, since, until, day):
    e = {"version": version, "date": day, "changes": subjects(since, until)}
    data = data_version(until)
    if data:
        e["data"] = data
    return e


def load():
    if CHANGELOG.exists():
        return json.loads(CHANGELOG.read_text(encoding="utf-8"))
    return {"_comment": "Patch notes shown on the website. Maintained by etl/changelog.py.", "versions": []}


def save(log):
    log["versions"].sort(key=lambda e: [int(x) for x in e["version"].split(".")], reverse=True)
    CHANGELOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert(log, e):
    log["versions"] = [v for v in log["versions"] if v["version"] != e["version"]] + [e]


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("backfill", "add"):
        sys.exit(__doc__)
    log = load()
    if sys.argv[1] == "backfill":
        previous = None
        for tag in tags():
            upsert(log, entry(tag[1:], previous, tag, git("log", "-1", "--format=%cs", tag)))
            previous = tag
    else:
        version = sys.argv[2].lstrip("v")
        existing = tags()
        last = existing[-1] if existing else None
        upsert(log, entry(version, last, "HEAD", date.today().isoformat()))
    save(log)
    for e in log["versions"]:
        print(f"{e['version']} ({e['date']}): {len(e['changes'])} changes")


if __name__ == "__main__":
    main()
