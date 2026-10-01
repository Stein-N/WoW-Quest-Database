"""Downloads the VMangos world DB snapshot (release `db_latest`, SQLite variant).

    python3 etl/fetch_vmangos.py vendor/vmangos
"""

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "https://api.github.com/repos/vmangos/core/releases/tags/db_latest"


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "vendor/vmangos")
    with urllib.request.urlopen(RELEASE) as r:
        release = json.load(r)
    asset = next(a for a in release["assets"] if "sqlite" in a["name"])
    print(f"downloading {asset['name']} ({asset['size'] // 1_000_000} MB) …", file=sys.stderr)
    with urllib.request.urlopen(asset["browser_download_url"]) as r:
        data = r.read()
    target.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(target)
    # e.g. "db-sqlite-4641790 (2026-09-28)", shown on the site as the data version
    version = f"{asset['name'].removesuffix('.zip')} ({release['published_at'][:10]})"
    (target / "VERSION").write_text(version + "\n")
    print(version, file=sys.stderr)


if __name__ == "__main__":
    main()
