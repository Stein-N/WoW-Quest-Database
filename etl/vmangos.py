"""Reads the VMangos world database snapshot (SQLite release `db_latest`)."""

import re
import sqlite3
from collections import defaultdict

from constants import VMANGOS_LOCALE_INDEX

# Highest content patch to read (10 = 1.12).
MAX_PATCH = 10


class VMangos:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.quests = self._latest("quest_template")
        self.items = self._latest("item_template")
        self.creatures = self._latest("creature_template")
        self.objects = {r["entry"]: r for r in self.db.execute("SELECT entry, name FROM gameobject_template")}
        self.quest_locales = self._by_entry("locales_quest")
        self.item_locales = self._by_entry("locales_item")
        self.creature_locales = self._by_entry("locales_creature")
        self.object_locales = self._by_entry("locales_gameobject")
        self.areas = {r["entry"]: dict(r) for r in self.db.execute("SELECT * FROM area_template")}
        self.area_locales = {r["Entry"]: r for r in self.db.execute("SELECT * FROM locales_area")}
        self.factions = self._max_build("faction", "id")
        self.faction_locales = self._by_entry("locales_faction")
        self.faction_templates = {
            r["id"]: r["faction_id"] for r in self._max_build("faction_template", "id").values()
        }
        self.spells = self._max_build("spell_template", "entry")
        self.creature_loot = self._loot("creature_loot_template")

    def _latest(self, table):
        """Newest row per entry that exists at MAX_PATCH."""
        rows = {}
        for r in self.db.execute(
            f"SELECT * FROM {table} WHERE patch <= ? ORDER BY entry, patch", (MAX_PATCH,)
        ):
            rows[r["entry"]] = r
        return rows

    def _max_build(self, table, key):
        rows = {}
        for r in self.db.execute(f"SELECT * FROM {table} ORDER BY {key}, build"):
            rows[r[key]] = r
        return rows

    def _by_entry(self, table):
        return {r["entry"]: r for r in self.db.execute(f"SELECT * FROM {table}")}

    def _loot(self, table):
        """loot entry -> [(item, chance%, mincount, maxcount)], direct items only.

        Grouped entries with chance 0 share what the explicit chances in their group leave.
        Reference entries (negative mincountOrRef) point at shared world-drop tables and are
        skipped; they would attach hundreds of generic drops to every creature.
        """
        raw = defaultdict(list)
        for r in self.db.execute(
            f"SELECT * FROM {table} WHERE mincountOrRef > 0 AND patch_min <= ? AND patch_max >= ?",
            (MAX_PATCH, MAX_PATCH),
        ):
            raw[r["entry"]].append(r)
        loot = {}
        for entry, rows in raw.items():
            groups = defaultdict(list)
            for r in rows:
                groups[r["groupid"]].append(r)
            out = []
            for groupid, members in groups.items():
                explicit = sum(abs(m["ChanceOrQuestChance"]) for m in members)
                zero = [m for m in members if m["ChanceOrQuestChance"] == 0]
                share = max(0.0, 100.0 - explicit) / len(zero) if groupid and zero else 0.0
                for m in members:
                    chance = abs(m["ChanceOrQuestChance"]) or share
                    if chance > 0:
                        out.append((m["item"], round(chance, 2), m["mincountOrRef"], m["maxcount"]))
            loot[entry] = out
        return loot

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def localized(row, column_fmt, locale):
        """Value of e.g. `Title_loc{n}` for a site locale, or None."""
        index = VMANGOS_LOCALE_INDEX.get(locale)
        if row is None or index is None:
            return None
        key = column_fmt.format(n=index)
        try:
            value = row[key]
        except (IndexError, KeyError):
            return None
        return value or None

    def faction_for_template(self, template_id):
        faction_id = self.faction_templates.get(template_id)
        return faction_id if faction_id in self.factions else None

    def spell_text(self, spell_id):
        """(name, description) with $sN placeholders resolved where possible."""
        row = self.spells.get(spell_id)
        if row is None:
            return None, None
        desc = row["description"] or ""

        def effect(n):
            base = row[f"effectBasePoints{n}"] + 1
            sides = row[f"effectDieSides{n}"]
            low, high = base, base + max(sides - 1, 0)
            return str(abs(low)) if low == high else f"{abs(low)} to {abs(high)}"

        def sub(m):
            spell_ref, letter, n = m.group(1), m.group(2), m.group(3)
            if spell_ref:  # $12345s1 refers to another spell; leave readable
                return "X"
            if letter == "s" and n in ("1", "2", "3"):
                return effect(int(n))
            return "X"

        desc = re.sub(r"\$(\d+)?([a-zA-Z])(\d)?", sub, desc)
        return row["name"], desc or None
