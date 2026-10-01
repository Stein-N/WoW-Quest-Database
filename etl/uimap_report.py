"""Markdown section for the release notes: uiMapId coverage and changes since the last release.

    python3 etl/uimap_report.py <new uimap-report.json> [<previous uimap-report.json>]

The reports are written by etl/build.py (data/uimap-report.json): per flavor the zone and
uiMapId of every quest that has a zone (uiMapId null = not resolvable yet).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

LABELS = {"classic": "Classic Era", "forever": "WoW Forever"}
MAX_IDS = 12  # quest ids listed per line before "…"


def load(path):
    if not path or not Path(path).exists():
        return None
    return json.loads(Path(path).read_text())


def ids(quest_ids):
    shown = ", ".join(sorted(quest_ids, key=int)[:MAX_IDS])
    return shown + (f", … (+{len(quest_ids) - MAX_IDS})" if len(quest_ids) > MAX_IDS else "")


def n_quests(q):
    return f"{len(q)} quest{'s' if len(q) != 1 else ''}"


def zone_label(zones, zone):
    return f"{zones.get(str(zone), f'Zone {zone}')} ({zone})"


def section(new, old):
    lines = ["## Map IDs (uiMapId)", ""]
    lines += ["| | Quests with a zone | with uiMapId | without |", "| --- | ---: | ---: | ---: |"]
    for flavor, data in new.items():
        quests = data["quests"]
        have = sum(1 for _, ui in quests.values() if ui)
        delta = ""
        if old and flavor in old:
            old_have = sum(1 for _, ui in old[flavor]["quests"].values() if ui)
            if have != old_have:
                delta = f" ({have - old_have:+d})"
        lines.append(f"| {LABELS.get(flavor, flavor)} | {len(quests)} | {have}{delta} | {len(quests) - have} |")
    lines.append("")

    for flavor, data in new.items():
        quests, zones = data["quests"], data["zones"]
        prev = (old or {}).get(flavor, {}).get("quests") if old else None
        label = LABELS.get(flavor, flavor)

        if prev is not None:
            gained, changed, lost = defaultdict(list), defaultdict(list), defaultdict(list)
            for qid, (zone, ui) in quests.items():
                before = prev.get(qid, [zone, None])[1]
                if ui and not before:
                    gained[(zone, ui)].append(qid)
                elif ui and before and ui != before:
                    changed[(zone, before, ui)].append(qid)
                elif before and not ui:
                    lost[(zone, before)].append(qid)
            if gained or changed or lost:
                lines.append(f"**{label}: changes since the last release**")
                lines.append("")
                for (zone, ui), q in sorted(gained.items(), key=lambda kv: -len(kv[1])):
                    lines.append(f"- new: {zone_label(zones, zone)} → {ui}: {n_quests(q)} ({ids(q)})")
                for (zone, a, b), q in sorted(changed.items(), key=lambda kv: -len(kv[1])):
                    lines.append(f"- changed: {zone_label(zones, zone)} {a} → {b}: {n_quests(q)} ({ids(q)})")
                for (zone, a), q in sorted(lost.items(), key=lambda kv: -len(kv[1])):
                    lines.append(f"- lost: {zone_label(zones, zone)} (was {a}): {n_quests(q)} ({ids(q)})")
                lines.append("")
            else:
                lines += [f"**{label}:** no uiMapId changes since the last release.", ""]

        missing = defaultdict(list)
        for qid, (zone, ui) in quests.items():
            if not ui:
                missing[zone].append(qid)
        if missing:
            lines.append(f"**{label}: still without uiMapId**")
            lines.append("")
            for zone, q in sorted(missing.items(), key=lambda kv: -len(kv[1])):
                lines.append(f"- {zone_label(zones, zone)}: {n_quests(q)}")
            lines.append("")

    if old is None:
        lines += ["_No report from the previous release to compare with._", ""]
    return "\n".join(lines)


def main():
    new = load(sys.argv[1])
    if new is None:
        sys.exit(f"{sys.argv[1]} not found")
    old = load(sys.argv[2]) if len(sys.argv) > 2 else None
    print(section(new, old))


if __name__ == "__main__":
    main()
