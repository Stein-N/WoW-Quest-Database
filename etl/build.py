"""Merges the QuestieDB export and the VMangos world DB into static JSON for the website.

    python3 etl/build.py [--out web/static/data] [--flavors classic,forever]

Expects `build/questie/<flavor>/` from questie_export.lua (see Makefile) and the VMangos
SQLite snapshot in vendor/vmangos/sqlite-dump/mangos.sqlite.

QuestieDB is authoritative for everything it carries (names, quest givers, objectives, chains,
spawns). VMangos fills in what QuestieDB lacks: quest texts, rewards, item stats, loot.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import constants as C
from vmangos import VMangos

ROOT = Path(__file__).resolve().parent.parent
BUCKET = 100
MAX_ITEM_SOURCES = 25  # droppers embedded per item objective (map + list)
MAX_LOOT = 150


def bucket_of(entity_id):
    return int(entity_id) // BUCKET


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))


def write_shards(base, records):
    shards = defaultdict(dict)
    for entity_id, record in records.items():
        shards[bucket_of(entity_id)][entity_id] = record
    for b, shard in shards.items():
        write_json(base / f"{b}.json", shard)


def prettify_symbol(symbol):
    words = symbol.split("_")
    small = {"OF", "THE", "AND"}
    return " ".join(
        w.capitalize() if i == 0 or w not in small else w.lower() for i, w in enumerate(words)
    )


def load_quest_rewards_lua(path):
    """Parses the hand-extracted QuestRewards.lua (Forever item rewards)."""
    rewards = {}
    pattern = re.compile(
        r"\[(\d+)\]\s*=\s*\{\s*type\s*=\s*\"(\w+)\",\s*items\s*=\s*\{([\d,\s]*)\}"
        r"(?:,\s*fixed\s*=\s*\{([\d,\s]*)\})?"
    )
    for m in pattern.finditer(path.read_text(encoding="utf-8")):
        ids = [int(x) for x in m.group(3).replace(" ", "").split(",") if x]
        fixed = [int(x) for x in (m.group(4) or "").replace(" ", "").split(",") if x]
        rewards[int(m.group(1))] = {"type": m.group(2), "items": ids, "fixed": fixed}
    return rewards


class Flavor:
    def __init__(self, site_id, vm, quest_rewards_lua):
        self.site_id = site_id
        self.vm = vm
        src = ROOT / "build" / "questie" / site_id
        load = lambda name: json.loads((src / name).read_text(encoding="utf-8"))
        self.quests = {int(k): v for k, v in load("Quest.json").items()}
        self.npcs = {int(k): v for k, v in load("Npc.json").items()}
        self.objects = {int(k): v for k, v in load("Object.json").items()}
        self.items = {int(k): v for k, v in load("Item.json").items()}
        self.l10n = load("l10n.json")
        self.support = load("support.json")
        self.questie_meta = load("meta.json")
        self.quest_rewards_lua = quest_rewards_lua if site_id == "forever" else None
        self.quest_xp = self.support["questXP"]
        self.item_drop_chances = self.support["itemDrops"]
        self.warnings = []

        self._apply_corrections()
        self.cache_texts = self._load_cache_texts()
        self._build_reverse_indexes()
        self.zones = self._build_zones()

    # ------------------------------------------------------------------ corrections

    def _apply_corrections(self):
        """etl/corrections/<flavor>.json: project-side quest fixes on top of QuestieDB.

        Uses QuestieDB's field names; keys starting with "_" are documentation only.
        """
        path = ROOT / "etl" / "corrections" / f"{self.site_id}.json"
        self.area_ui_map_overrides = {}
        if not path.exists():
            return
        corrections = json.loads(path.read_text(encoding="utf-8"))
        self.area_ui_map_overrides = {
            int(k): v for k, v in corrections.get("areaUiMaps", {}).items() if not k.startswith("_")
        }
        applied = 0
        for group in corrections.get("groups", []):
            for quest_id, fields in group["quests"].items():
                quest = self.quests.get(int(quest_id))
                if quest is None:
                    print(f"  correction for unknown quest {quest_id} ({group['name']})", file=sys.stderr)
                    continue
                for field, value in fields.items():
                    if not field.startswith("_"):
                        quest[field] = value
                applied += 1
        print(f"  applied {applied} quest corrections from {path.name}", file=sys.stderr)

    def _load_cache_texts(self):
        """etl/corrections/questcache/<flavor>/<locale>.json -> {locale: {quest id: texts}}.

        Quest texts read from WoW client caches (etl/import_questcache.py); they only fill
        gaps that QuestieDB and VMangos leave.
        """
        out = {}
        for path in sorted((ROOT / "etl" / "corrections" / "questcache" / self.site_id).glob("*.json")):
            quests = json.loads(path.read_text(encoding="utf-8"))["quests"]
            out[path.stem] = {int(k): v for k, v in quests.items()}
        if out:
            print("  client cache texts: " + ", ".join(f"{loc} {len(q)}" for loc, q in out.items()),
                  file=sys.stderr)
        return out

    # ------------------------------------------------------------------ uiMap of a quest zone

    CONTINENT_UI_MAPS = {946, 947, 1414, 1415}

    def area_ui_map(self, area_id):
        """UiMapId for a quest's zone (AreaTable id), or None.

        1. QuestieDB's area -> uiMap table   2. own override (corrections "areaUiMaps")
        3. parent zone (QuestieDB sub-zone table, VMangos area_template.zone_id)
        4. where the zone's quest givers stand, if one non-continent map clearly dominates
        """
        if not hasattr(self, "_area_ui_maps"):
            self._area_ui_maps = {}
        if area_id in self._area_ui_maps:
            return self._area_ui_maps[area_id]
        self._area_ui_maps[area_id] = None  # guards against parent cycles
        result = None
        zone = self.zones.get(area_id) or {}
        if zone.get("uiMapId"):
            result = zone["uiMapId"]
        elif area_id in self.area_ui_map_overrides:
            result = self.area_ui_map_overrides[area_id]
        else:
            vm_area = self.vm.areas.get(area_id) or {}
            for parent in (zone.get("parent"), vm_area.get("zone_id")):
                if parent and parent != area_id:
                    result = self.area_ui_map(parent)
                    if result:
                        break
            if not result:
                result = self._ui_map_from_givers(area_id)
        self._area_ui_maps[area_id] = result
        return result

    def _ui_map_from_givers(self, area_id):
        votes = defaultdict(int)
        for q in self.quests.values():
            if q.get("zoneOrSort") != area_id:
                continue
            starters = q.get("startedBy") or []
            for kind, ids in zip(("npc", "object"), starters[:2]):
                source = self.npcs if kind == "npc" else self.objects
                for entity_id in ids or []:
                    for spawn_area in (source.get(entity_id) or {}).get("spawns") or {}:
                        ui_map = (self.zones.get(int(spawn_area)) or {}).get("uiMapId")
                        if ui_map and ui_map not in self.CONTINENT_UI_MAPS:
                            votes[ui_map] += 1
        total = sum(votes.values())
        if total < 2:
            return None
        best = max(votes, key=votes.get)
        return best if votes[best] * 3 >= total * 2 else None

    # ------------------------------------------------------------------ indexes

    def _build_reverse_indexes(self):
        self.npc_objective_of = defaultdict(set)
        self.object_objective_of = defaultdict(set)
        self.item_objective_of = defaultdict(set)
        self.item_reward_of = defaultdict(set)
        self.item_starts = {}
        for qid, q in self.quests.items():
            obj = q.get("objectives") or []
            for i, target in enumerate(obj[:3]):
                for entry in target or []:
                    if entry and entry[0]:
                        [self.npc_objective_of, self.object_objective_of, self.item_objective_of][i][entry[0]].add(qid)
            if len(obj) > 4 and obj[4]:
                for entry in obj[4]:
                    for npc_id in (entry[0] or []) if entry else []:
                        self.npc_objective_of[npc_id].add(qid)
            starters = q.get("startedBy") or []
            if len(starters) > 2:
                for item_id in starters[2] or []:
                    self.item_starts[item_id] = qid
        for qid in self.quests:
            for reward in self._quest_rewards(qid):
                for entry in reward["items"]:
                    self.item_reward_of[entry["id"]].add(qid)
        # NPC loot from VMangos, keyed by creature entry (loot tables are keyed by loot_id).
        self.npc_loot = {}
        self.item_dropped_by = defaultdict(list)
        for npc_id in self.npcs:
            creature = self.vm.creatures.get(npc_id)
            if creature is None or not creature["loot_id"]:
                continue
            loot = self.vm.creature_loot.get(creature["loot_id"])
            if loot:
                self.npc_loot[npc_id] = loot
                for item_id, chance, _lo, _hi in loot:
                    self.item_dropped_by[item_id].append((npc_id, chance))
        self.npc_sells = defaultdict(list)
        for item_id, item in self.items.items():
            for npc_id in item.get("vendors") or []:
                self.npc_sells[npc_id].append(item_id)

    def _build_zones(self):
        sup = self.support
        area_to_ui = {**sup["areaIdToUiMapId"], **sup["areaIdToUiMapIdOverride"]}
        parent = {**sup["subZoneToParentZone"], **sup["subZoneToParentZoneOverride"]}
        dungeons = sup["dungeons"]
        zones = {}
        ids = set(area_to_ui) | set(sup["zoneSymbols"]) | set(dungeons)
        for npc in list(self.npcs.values()) + list(self.objects.values()):
            ids.update((npc.get("spawns") or {}).keys())
        for q in self.quests.values():
            if q.get("zoneOrSort", 0) > 0:
                ids.add(str(q["zoneOrSort"]))
        for key in ids:
            area_id = int(key)
            if area_id <= 0:
                continue
            area = self.vm.areas.get(area_id)
            if key in dungeons:
                name = dungeons[key][0]
            elif area:
                name = area["name"]
            elif key in sup["zoneSymbols"]:
                name = prettify_symbol(sup["zoneSymbols"][key])
            else:
                name = f"Zone {area_id}"
            zone = {"name": name}
            if area_to_ui.get(key):
                zone["uiMapId"] = area_to_ui[key]
            if parent.get(key):
                zone["parent"] = parent[key]
            if key in dungeons:
                d = dungeons[key]
                zone["instance"] = True
                zone["parent"] = d[2]
                if len(d) > 3 and d[3]:
                    zone["entrances"] = [{"zone": e[0], "x": e[1], "y": e[2]} for e in d[3]]
            zones[area_id] = zone
        return zones

    # ------------------------------------------------------------------ names & refs

    def name(self, kind, entity_id):
        source = {"npc": self.npcs, "object": self.objects, "item": self.items, "quest": self.quests}[kind]
        entity = source.get(entity_id)
        if entity and entity.get("name"):
            return entity["name"]
        vm_source = {"npc": self.vm.creatures, "object": self.vm.objects, "item": self.vm.items,
                     "quest": self.vm.quests}[kind]
        row = vm_source.get(entity_id)
        if row is not None:
            return row["Title"] if kind == "quest" else row["name"]
        return None

    def ref(self, kind, entity_id, **extra):
        source = {"npc": self.npcs, "object": self.objects, "item": self.items, "quest": self.quests}[kind]
        r = {"t": kind, "id": entity_id, "name": self.name(kind, entity_id) or f"#{entity_id}"}
        if entity_id not in source:
            r["missing"] = True  # referenced, but not part of this flavor's data: no page to link
        if kind == "item":
            vm_item = self.vm.items.get(entity_id)
            if vm_item is not None:
                r["q"] = vm_item["quality"]
        if kind == "quest":
            q = self.quests.get(entity_id)
            if q:
                r["lvl"] = q.get("questLevel")
        r.update({k: v for k, v in extra.items() if v is not None})
        return r

    def zone_ref(self, zone_or_sort):
        if not zone_or_sort:
            return None
        if zone_or_sort < 0:
            return {"sort": zone_or_sort, "name": C.QUEST_SORTS.get(zone_or_sort, f"Category {zone_or_sort}")}
        zone = self.zones.get(zone_or_sort)
        return {"zone": zone_or_sort, "name": zone["name"] if zone else f"Zone {zone_or_sort}"}

    def faction_ref(self, faction_id, value=None):
        row = self.vm.factions.get(faction_id)
        r = {"id": faction_id, "name": row["name"] if row else f"Faction {faction_id}"}
        if value is not None:
            r["value"] = value
        return r

    def spawn_data(self, kind, entity_id):
        entity = (self.npcs if kind == "npc" else self.objects).get(entity_id) or {}
        out = {}
        if entity.get("spawns"):
            out["spawns"] = entity["spawns"]
        if entity.get("waypoints"):
            out["waypoints"] = entity["waypoints"]
        return out

    # ------------------------------------------------------------------ quests

    def _quest_rewards(self, qid):
        """[{'kind': 'fixed'|'choice', 'items': [ref...]}]"""
        vmq = self.vm.quests.get(qid)
        counts = {}
        fixed, choice = [], []
        if vmq is not None:
            for n in range(1, 5):
                if vmq[f"RewItemId{n}"]:
                    fixed.append(vmq[f"RewItemId{n}"])
                    counts[vmq[f"RewItemId{n}"]] = vmq[f"RewItemCount{n}"]
            for n in range(1, 7):
                if vmq[f"RewChoiceItemId{n}"]:
                    choice.append(vmq[f"RewChoiceItemId{n}"])
                    counts[vmq[f"RewChoiceItemId{n}"]] = vmq[f"RewChoiceItemCount{n}"]
        if self.quest_rewards_lua is not None:
            entry = self.quest_rewards_lua.get(qid)
            if entry is None:
                fixed, choice = [], []
            elif entry["type"] == "single":
                choice, fixed = entry["items"], entry["fixed"]
            else:
                fixed, choice = entry["items"], []
        out = []
        for kind, ids in (("fixed", fixed), ("choice", choice)):
            if ids:
                out.append({"kind": kind, "items": [
                    self.ref("item", i, count=counts.get(i) if counts.get(i, 1) > 1 else None) for i in ids
                ]})
        return out

    def _objective_entries(self, qid, q, vmq, spawns):
        objectives = []
        obj = q.get("objectives") or []

        def vm_count(id_key, count_key, target_id, max_n=4):
            if vmq is None:
                return None
            for n in range(1, max_n + 1):
                if abs(vmq[f"{id_key}{n}"] or 0) == target_id:
                    return vmq[f"{count_key}{n}"] or None
            return None

        def add_spawns(kind, entity_id):
            key = f"{kind}:{entity_id}"
            if key not in spawns:
                data = self.spawn_data(kind, entity_id)
                if data:
                    spawns[key] = data

        kinds = ["npc", "object", "item"]
        for i, kind in enumerate(kinds):
            for entry in (obj[i] if len(obj) > i and obj[i] else []):
                if not entry or not entry[0]:
                    continue
                target = entry[0]
                text = entry[1] if len(entry) > 1 else None
                if kind == "item":
                    count = vm_count("ReqItemId", "ReqItemCount", target)
                else:
                    count = vm_count("ReqCreatureOrGOId", "ReqCreatureOrGOCount", target)
                o = {"kind": {"npc": "kill", "object": "object", "item": "item"}[kind],
                     "target": self.ref(kind, target)}
                if text:
                    o["text"] = text
                if count:
                    o["count"] = count
                if kind == "item":
                    o["sources"] = self._item_sources(target, spawns)
                else:
                    add_spawns(kind, target)
                objectives.append(o)
        if len(obj) > 3 and obj[3]:
            rep = obj[3]
            objectives.append({"kind": "reputation", "faction": self.faction_ref(rep[0], rep[1])})
        if len(obj) > 4 and obj[4]:
            for entry in obj[4]:
                if not entry:
                    continue
                npc_ids = entry[0] or []
                base = entry[1] if len(entry) > 1 else None
                o = {"kind": "killcredit", "targets": [self.ref("npc", n) for n in npc_ids]}
                if base:
                    o["target"] = self.ref("npc", base)
                    o["count"] = vm_count("ReqCreatureOrGOId", "ReqCreatureOrGOCount", base)
                if len(entry) > 2 and entry[2]:
                    o["text"] = entry[2]
                for n in npc_ids:
                    add_spawns("npc", n)
                objectives.append(o)
        if len(obj) > 5 and obj[5]:
            for entry in obj[5]:
                if entry:
                    name, _ = self.vm.spell_text(entry[0])
                    objectives.append({"kind": "spell", "spell": {"id": entry[0], "name": name},
                                       "text": entry[1] if len(entry) > 1 else None})
        trigger = q.get("triggerEnd")
        if trigger:
            key = f"trigger:{qid}"
            if isinstance(trigger[1], dict):
                spawns[key] = {"spawns": trigger[1]}
            objectives.append({"kind": "event", "text": trigger[0], "spawnKey": key})
        for i, extra in enumerate(q.get("extraObjectives") or []):
            if not extra:
                continue
            o = {"kind": "extra", "text": extra[2] if len(extra) > 2 else None}
            if extra[0]:
                key = f"extra:{qid}:{i}"
                spawns[key] = {"spawns": extra[0]}
                o["spawnKey"] = key
            if len(extra) > 4 and extra[4]:
                o["targets"] = []
                for t in extra[4]:
                    kind = {"monster": "npc", "object": "object", "item": "item"}.get(t[0])
                    if kind:
                        o["targets"].append(self.ref(kind, t[1]))
                        if kind != "item":
                            add_spawns(kind, t[1])
            objectives.append(o)
        return objectives

    def _item_sources(self, item_id, spawns):
        item = self.items.get(item_id) or {}
        chances = self.item_drop_chances.get(str(item_id)) or {}
        vm_chances = {npc: ch for npc, ch in self.item_dropped_by.get(item_id, [])}
        sources = []
        for npc_id in item.get("npcDrops") or []:
            chance = chances.get(str(npc_id)) or vm_chances.get(npc_id)
            sources.append(self.ref("npc", npc_id, chance=chance))
        sources.sort(key=lambda r: -(r.get("chance") or 0))
        for obj_id in item.get("objectDrops") or []:
            sources.append(self.ref("object", obj_id))
        for src_item in item.get("itemDrops") or []:
            sources.append(self.ref("item", src_item))
        for npc_id in item.get("vendors") or []:
            sources.append(self.ref("npc", npc_id, vendor=True))
        sources = sources[:MAX_ITEM_SOURCES]
        for s in sources:
            if s["t"] in ("npc", "object"):
                key = f"{s['t']}:{s['id']}"
                if key not in spawns:
                    data = self.spawn_data(s["t"], s["id"])
                    if data:
                        spawns[key] = data
        return sources

    def build_quest(self, qid):
        q = self.quests[qid]
        vmq = self.vm.quests.get(qid)
        spawns = {}

        def givers(field):
            data = q.get(field) or []
            out = []
            for i, kind in enumerate(["npc", "object", "item"]):
                for entity_id in (data[i] if len(data) > i and data[i] else []):
                    out.append(self.ref(kind, entity_id))
                    if kind != "item":
                        key = f"{kind}:{entity_id}"
                        d = self.spawn_data(kind, entity_id)
                        if d:
                            spawns[key] = d
            return out

        races = q.get("requiredRaces") or 0
        r = {
            "id": qid,
            "name": q.get("name"),
            "level": q.get("questLevel"),
            "reqLevel": q.get("requiredLevel"),
            "side": side_of(races),
            "races": C.bitmask_names(races, C.RACES) if races and not is_full_side(races) else None,
            "classes": C.bitmask_names(q.get("requiredClasses") or 0, C.CLASSES) or None,
            "zone": self.zone_ref(q.get("zoneOrSort")),
            "uiMapId": self.area_ui_map(q["zoneOrSort"]) if (q.get("zoneOrSort") or 0) > 0 else None,
            "objectivesText": q.get("objectivesText"),
            "starters": givers("startedBy"),
            "enders": givers("finishedBy"),
        }
        if q.get("requiredMaxLevel"):
            r["maxLevel"] = q["requiredMaxLevel"]
        if vmq is not None:
            r["details"] = vmq["Details"] or None
            r["progress"] = vmq["RequestItemsText"] or None
            r["completion"] = vmq["OfferRewardText"] or None
            r["endText"] = vmq["EndText"] or None
            if vmq["Type"]:
                r["type"] = C.QUEST_TYPES.get(vmq["Type"], f"Type {vmq['Type']}")
            if vmq["SuggestedPlayers"]:
                r["suggestedPlayers"] = vmq["SuggestedPlayers"]
            if vmq["LimitTime"]:
                r["timeLimit"] = vmq["LimitTime"]
        cached = self.cache_texts.get("enUS", {}).get(qid)
        if cached:
            used = False
            for field in ("name", "objectivesText", "details", "endText"):
                if not r.get(field) and cached.get(field):
                    r[field] = cached[field]
                    used = True
            if used:
                r["_fromCache"] = True
        if (q.get("specialFlags") or 0) & 1:
            r["repeatable"] = True
        r["objectives"] = self._objective_entries(qid, q, vmq, spawns)
        if q.get("sourceItemId"):
            r["providedItem"] = self.ref("item", q["sourceItemId"])
        if q.get("requiredSourceItems"):
            r["requiredItems"] = [self.ref("item", i) for i in q["requiredSourceItems"]]

        # chain & requirements
        chain = {}
        for field, key in (("preQuestSingle", "preSingle"), ("preQuestGroup", "preGroup"),
                           ("childQuests", "children"), ("inGroupWith", "groupWith"),
                           ("exclusiveTo", "exclusive"), ("breadcrumbs", "breadcrumbs")):
            if q.get(field):
                chain[key] = [self.ref("quest", i) for i in q[field] if i]
        for field, key in (("nextQuestInChain", "next"), ("parentQuest", "parent"),
                           ("breadcrumbForQuestId", "breadcrumbFor")):
            if q.get(field):
                chain[key] = self.ref("quest", q[field])
        prev = self._previous_in_chain(qid)
        if prev:
            chain["prev"] = [self.ref("quest", i) for i in prev]
        if chain:
            r["chain"] = chain
        req = {}
        if q.get("requiredSkill"):
            skill, value = q["requiredSkill"][0], q["requiredSkill"][1] if len(q["requiredSkill"]) > 1 else None
            req["skill"] = {"id": skill, "name": C.SKILLS.get(skill, f"Skill {skill}"), "value": value}
        if q.get("requiredMinRep"):
            req["minRep"] = self.faction_ref(*q["requiredMinRep"][:2])
        if q.get("requiredMaxRep"):
            req["maxRep"] = self.faction_ref(*q["requiredMaxRep"][:2])
        if q.get("requiredSpell"):
            name, _ = self.vm.spell_text(abs(q["requiredSpell"]))
            req["spell"] = {"id": abs(q["requiredSpell"]), "name": name, "lacking": q["requiredSpell"] < 0}
        if req:
            r["requirements"] = req

        # rewards
        rewards = {}
        items = self._quest_rewards(qid)
        if items:
            rewards["items"] = items
        xp = self.quest_xp.get(str(qid))
        if xp:
            rewards["xp"] = xp[1]
        elif vmq is not None and vmq["RewXP"]:
            rewards["xp"] = vmq["RewXP"]
        if vmq is not None:
            money = vmq["RewOrReqMoney"]
            if money > 0:
                rewards["money"] = money
            elif money < 0:
                r.setdefault("requirements", {})["money"] = -money
            if vmq["RewMoneyMaxLevel"]:
                rewards["moneyMaxLevel"] = vmq["RewMoneyMaxLevel"]
            spell_id = vmq["RewSpellCast"] or vmq["RewSpell"]
            if spell_id:
                name, desc = self.vm.spell_text(spell_id)
                rewards["spell"] = {"id": spell_id, "name": name, "description": desc}
        if q.get("reputationReward"):
            rewards["reputation"] = [self.faction_ref(f, v) for f, v in q["reputationReward"]]
        if rewards:
            r["rewards"] = rewards
        if spawns:
            r["spawns"] = spawns
        line = self.questline_of.get(qid)
        if line is not None:
            r["questline"] = {"id": line["id"], "size": len(line["quests"])}
        r["sources"] = ["questie"] + (["vmangos"] if vmq is not None else []) + (["cache"] if r.pop("_fromCache", False) else [])
        return {k: v for k, v in r.items() if v is not None}

    def _previous_in_chain(self, qid):
        if not hasattr(self, "_prev_index"):
            self._prev_index = defaultdict(list)
            for other_id, other in self.quests.items():
                if other.get("nextQuestInChain"):
                    self._prev_index[other["nextQuestInChain"]].append(other_id)
        return self._prev_index.get(qid)

    # ------------------------------------------------------------------ npcs / objects

    def build_npc(self, npc_id):
        n = self.npcs[npc_id]
        vmc = self.vm.creatures.get(npc_id)
        faction = self.vm.faction_for_template(n.get("factionID")) if n.get("factionID") else None
        r = {
            "id": npc_id,
            "name": n.get("name"),
            "subName": n.get("subName"),
            "minLevel": n.get("minLevel"),
            "maxLevel": n.get("maxLevel"),
            "minHealth": n.get("minLevelHealth"),
            "maxHealth": n.get("maxLevelHealth"),
            "rank": C.CREATURE_RANKS.get(n.get("rank") or 0),
            "react": n.get("friendlyToFaction"),
            "faction": self.faction_ref(faction) if faction else None,
            "roles": C.bitmask_names(n.get("npcFlags") or 0, C.NPC_FLAGS) or None,
            "zone": self.zone_ref(n.get("zoneID")),
            **self.spawn_data("npc", npc_id),
            "starts": [self.ref("quest", i) for i in n.get("questStarts") or []] or None,
            "ends": [self.ref("quest", i) for i in n.get("questEnds") or []] or None,
            "objectiveOf": [self.ref("quest", i) for i in sorted(self.npc_objective_of.get(npc_id, []))] or None,
            "sells": [self.ref("item", i) for i in sorted(self.npc_sells.get(npc_id, []))] or None,
        }
        loot = self.npc_loot.get(npc_id)
        if loot:
            loot = sorted(loot, key=lambda e: -e[1])[:MAX_LOOT]
            r["loot"] = [self.ref("item", i, chance=ch, min=lo if lo > 1 else None,
                                  max=hi if hi > 1 else None) for i, ch, lo, hi in loot]
        if vmc is not None:
            r["sources"] = ["questie", "vmangos"]
        else:
            r["sources"] = ["questie"]
        return {k: v for k, v in r.items() if v is not None}

    def build_object(self, obj_id):
        o = self.objects[obj_id]
        contains = self._object_contains.get(obj_id, [])
        r = {
            "id": obj_id,
            "name": o.get("name"),
            "zone": self.zone_ref(o.get("zoneID")),
            **self.spawn_data("object", obj_id),
            "starts": [self.ref("quest", i) for i in o.get("questStarts") or []] or None,
            "ends": [self.ref("quest", i) for i in o.get("questEnds") or []] or None,
            "objectiveOf": [self.ref("quest", i) for i in sorted(self.object_objective_of.get(obj_id, []))] or None,
            "contains": [self.ref("item", i) for i in sorted(contains)] or None,
        }
        return {k: v for k, v in r.items() if v is not None}

    # ------------------------------------------------------------------ items

    def build_item(self, item_id):
        it = self.items[item_id]
        vmi = self.vm.items.get(item_id)
        r = {"id": item_id, "name": it.get("name")}
        if vmi is not None:
            class_name, subclasses = C.ITEM_CLASSES.get(vmi["class"], (None, {}))
            r.update({
                "quality": vmi["quality"],
                "itemLevel": vmi["item_level"] or None,
                "reqLevel": vmi["required_level"] or None,
                "class": class_name,
                "subClass": subclasses.get(vmi["subclass"]),
                "slot": C.INVENTORY_TYPES.get(vmi["inventory_type"]),
                "bonding": C.BONDING.get(vmi["bonding"]),
                "unique": vmi["max_count"] == 1 or None,
                "stack": vmi["stackable"] if vmi["stackable"] > 1 else None,
                "slots": vmi["container_slots"] or None,
                "armor": vmi["armor"] or None,
                "block": vmi["block"] or None,
                "durability": vmi["max_durability"] or None,
                "sellPrice": vmi["sell_price"] or None,
                "buyPrice": vmi["buy_price"] or None,
                "description": vmi["description"] or None,
                "classes": C.bitmask_names(vmi["allowable_class"], C.CLASSES)
                if 0 < vmi["allowable_class"] and (vmi["allowable_class"] & 0x5DF) != 0x5DF else None,
                "races": C.bitmask_names(vmi["allowable_race"], C.RACES)
                if 0 < vmi["allowable_race"] and not is_full_side(vmi["allowable_race"]) and vmi["allowable_race"] & 0xFF != 0xFF else None,
            })
            if vmi["required_skill"]:
                r["reqSkill"] = {"id": vmi["required_skill"],
                                 "name": C.SKILLS.get(vmi["required_skill"], f"Skill {vmi['required_skill']}"),
                                 "value": vmi["required_skill_rank"]}
            if vmi["required_reputation_faction"]:
                r["reqRep"] = self.faction_ref(vmi["required_reputation_faction"], vmi["required_reputation_rank"])
            stats = []
            for n in range(1, 11):
                if vmi[f"stat_value{n}"]:
                    stats.append({"stat": C.STAT_TYPES.get(vmi[f"stat_type{n}"], f"Stat {vmi[f'stat_type{n}']}"),
                                  "value": vmi[f"stat_value{n}"]})
            if stats:
                r["stats"] = stats
            damage = []
            for n in range(1, 6):
                if vmi[f"dmg_max{n}"]:
                    damage.append({"min": vmi[f"dmg_min{n}"], "max": vmi[f"dmg_max{n}"],
                                   "school": C.DAMAGE_SCHOOLS.get(vmi[f"dmg_type{n}"], "")})
            if damage:
                r["damage"] = damage
                r["speed"] = round(vmi["delay"] / 1000, 2) if vmi["delay"] else None
            res = {s: vmi[f"{s}_res"] for s in ("holy", "fire", "nature", "frost", "shadow", "arcane") if vmi[f"{s}_res"]}
            if res:
                r["resistances"] = res
            spells = []
            for n in range(1, 6):
                spell_id = vmi[f"spellid_{n}"]
                if spell_id:
                    name, desc = self.vm.spell_text(spell_id)
                    spells.append({"id": spell_id, "trigger": C.SPELL_TRIGGERS.get(vmi[f"spelltrigger_{n}"], "Use"),
                                   "name": name, "description": desc})
            if spells:
                r["spells"] = spells
        else:
            r["quality"] = None
        start = it.get("startQuest") or self.item_starts.get(item_id)
        if start:
            r["startsQuest"] = self.ref("quest", start)
        drops = []
        chances = self.item_drop_chances.get(str(item_id)) or {}
        vm_chances = dict(self.item_dropped_by.get(item_id, []))
        for npc_id in it.get("npcDrops") or []:
            drops.append(self.ref("npc", npc_id, chance=chances.get(str(npc_id)) or vm_chances.get(npc_id)))
        seen = {d["id"] for d in drops}
        for npc_id, chance in sorted(self.item_dropped_by.get(item_id, []), key=lambda e: -e[1]):
            if npc_id not in seen and len(drops) < MAX_LOOT:
                drops.append(self.ref("npc", npc_id, chance=chance))
        drops.sort(key=lambda d: -(d.get("chance") or 0))
        r.update({
            "droppedBy": drops or None,
            "objectDrops": [self.ref("object", i) for i in it.get("objectDrops") or []] or None,
            "containedIn": [self.ref("item", i) for i in it.get("itemDrops") or []] or None,
            "vendors": [self.ref("npc", i) for i in it.get("vendors") or []] or None,
            "rewardFrom": [self.ref("quest", i) for i in sorted(self.item_reward_of.get(item_id, []))] or None,
            "objectiveOf": [self.ref("quest", i) for i in sorted(self.item_objective_of.get(item_id, []))] or None,
            "sources": ["questie"] + (["vmangos"] if vmi is not None else []),
        })
        return {k: v for k, v in r.items() if v is not None}

    # ------------------------------------------------------------------ output

    def build(self, out):
        self._object_contains = defaultdict(list)
        for item_id, item in self.items.items():
            for obj_id in item.get("objectDrops") or []:
                self._object_contains[obj_id].append(item_id)

        base = out / self.site_id
        if base.exists():
            shutil.rmtree(base)
        self.build_questlines()
        records = {
            "quest": {i: self.build_quest(i) for i in self.quests},
            "npc": {i: self.build_npc(i) for i in self.npcs},
            "object": {i: self.build_object(i) for i in self.objects},
            "item": {i: self.build_item(i) for i in self.items},
        }
        for kind, recs in records.items():
            write_shards(base / kind, recs)

        quest_index = []
        for qid, rec in sorted(records["quest"].items()):
            zone = rec.get("zone") or {}
            flags = (1 if rec.get("repeatable") else 0) | (2 if rec.get("type") in ("Dungeon", "Raid") else 0) \
                | (4 if rec.get("type") == "Group" else 0) | (8 if rec.get("type") == "PvP" else 0)
            quest_index.append([qid, rec["name"], rec.get("level"), rec.get("reqLevel"), rec["side"],
                                zone.get("zone") or zone.get("sort") or 0,
                                self.quests[qid].get("requiredClasses") or 0, flags])
        write_json(base / "quests.json", quest_index)
        write_json(base / "search.json", {
            "npc": [[i, r["name"], r.get("subName") or "", r.get("minLevel"), r.get("maxLevel"), r.get("react") or ""]
                    for i, r in sorted(records["npc"].items())],
            "object": [[i, r["name"]] for i, r in sorted(records["object"].items())],
            "item": [[i, r["name"], r.get("quality")] for i, r in sorted(records["item"].items())],
        })
        self.build_zone_givers(base, records["quest"])
        write_json(base / "questlines.json", self.questlines)
        sorts = {str(k): v for k, v in C.QUEST_SORTS.items()}
        write_json(base / "zones.json", {"zones": {str(k): v for k, v in self.zones.items()}, "sorts": sorts})

        self.build_l10n(base, records)
        self.uimap_report = self._uimap_report(records["quest"])
        return {kind: len(recs) for kind, recs in records.items()}

    def _uimap_report(self, quests):
        """uiMapId per quest that has a zone (None = unresolved), for the release report."""
        report, zones = {}, {}
        for qid, rec in sorted(quests.items()):
            zone = (rec.get("zone") or {}).get("zone")
            if zone:
                report[str(qid)] = [zone, rec.get("uiMapId")]
                zones[str(zone)] = rec["zone"]["name"]
        return {"quests": report, "zones": zones}

    def build_questlines(self):
        """Groups quests connected by prerequisites, follow-ups and breadcrumbs.

        Each questline is a connected component of that graph (at least two quests) with its
        directed edges [from, to, kind]: "pre" (from must be done first) or "breadcrumb"
        (from leads to to). Exclusive alternatives are kept as "exclusive" pairs.
        """
        edges = {}
        neighbours = defaultdict(set)

        def link(a, b, kind):
            if a == b or a not in self.quests or b not in self.quests:
                return
            if (a, b) not in edges or kind == "pre":
                edges[(a, b)] = kind
            neighbours[a].add(b)
            neighbours[b].add(a)

        for qid, q in self.quests.items():
            for pre in (q.get("preQuestSingle") or []) + (q.get("preQuestGroup") or []):
                link(pre, qid, "pre")
            if q.get("nextQuestInChain"):
                link(qid, q["nextQuestInChain"], "pre")
            for crumb in q.get("breadcrumbs") or []:
                link(crumb, qid, "breadcrumb")
            if q.get("breadcrumbForQuestId"):
                link(qid, q["breadcrumbForQuestId"], "breadcrumb")

        self.questlines, self.questline_of = [], {}
        seen = set()
        for start in sorted(neighbours):
            if start in seen:
                continue
            component, stack = [], [start]
            seen.add(start)
            while stack:
                node = stack.pop()
                component.append(node)
                for other in neighbours[node]:
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
            members = set(component)
            line_edges = sorted([a, b, k] for (a, b), k in edges.items() if a in members)
            has_incoming = {b for _a, b, _k in line_edges}
            roots = sorted((q for q in members if q not in has_incoming),
                           key=lambda q: (self.quests[q].get("questLevel") or 0, q))
            zones = defaultdict(int)
            for q in members:
                if self.quests[q].get("zoneOrSort"):
                    zones[self.quests[q]["zoneOrSort"]] += 1
            levels = [self.quests[q].get("questLevel") for q in members if self.quests[q].get("questLevel")]
            sides = {side_of(self.quests[q].get("requiredRaces") or 0) for q in members}
            exclusive = sorted({tuple(sorted((q, x))) for q in members
                                for x in self.quests[q].get("exclusiveTo") or [] if x in members})
            line = {
                "id": min(members),
                "root": roots[0] if roots else min(members),
                "zone": max(zones, key=zones.get) if zones else 0,
                "levels": [min(levels), max(levels)] if levels else None,
                "side": sides.pop() if len(sides) == 1 else "B",
                "quests": sorted(members),
                "edges": line_edges,
            }
            if exclusive:
                line["exclusive"] = [list(p) for p in exclusive]
            self.questlines.append(line)
            for q in members:
                self.questline_of[q] = line

    def build_zone_givers(self, base, quests):
        """zone/<areaId>.json: quest givers standing in that zone, for the zone map."""
        givers = defaultdict(dict)  # area -> "kind:id" -> entry
        for qid, quest in quests.items():
            for ref in quest["starters"]:
                if ref["t"] == "item":
                    continue
                key = f"{ref['t']}:{ref['id']}"
                spawn = (quest.get("spawns") or {}).get(key, {}).get("spawns") or {}
                for area, points in spawn.items():
                    entry = givers[area].setdefault(key, {**ref, "spawns": {area: points}, "quests": []})
                    entry["quests"].append(qid)
        for area, entries in givers.items():
            write_json(base / "zone" / f"{area}.json", {"givers": list(entries.values())})

    # ------------------------------------------------------------------ localization

    def localized_name(self, kind, entity_id, locale):
        type_name = {"npc": "Npc", "object": "Object", "item": "Item", "quest": "Quest"}[kind]
        entry = self.l10n.get(type_name, {}).get(str(entity_id))
        if entry and entry.get("name", {}).get(locale):
            return entry["name"][locale]
        vm_locale = {"npc": self.vm.creature_locales, "object": self.vm.object_locales,
                     "item": self.vm.item_locales, "quest": self.vm.quest_locales}[kind].get(entity_id)
        column = "Title_loc{n}" if kind == "quest" else "name_loc{n}"
        name = self.vm.localized(vm_locale, column, locale)
        if not name and kind == "quest":
            name = self.cache_texts.get(locale, {}).get(entity_id, {}).get("name")
        return name

    def build_l10n(self, base, records):
        for locale in C.LOCALES:
            names_cache = {}

            def name_of(kind, entity_id):
                key = (kind, entity_id)
                if key not in names_cache:
                    names_cache[key] = self.localized_name(kind, entity_id, locale)
                return names_cache[key]

            for kind, recs in records.items():
                out = {}
                for entity_id, rec in recs.items():
                    entry = {}
                    own = name_of(kind, entity_id)
                    if own:
                        entry["name"] = own
                    if kind == "quest":
                        qe = self.l10n.get("Quest", {}).get(str(entity_id), {})
                        if qe.get("objectivesText", {}).get(locale):
                            entry["objectivesText"] = qe["objectivesText"][locale]
                        vml = self.vm.quest_locales.get(entity_id)
                        for field, column in (("details", "Details_loc{n}"), ("progress", "RequestItemsText_loc{n}"),
                                              ("completion", "OfferRewardText_loc{n}"), ("endText", "EndText_loc{n}")):
                            v = self.vm.localized(vml, column, locale)
                            if v:
                                entry[field] = v
                        if "objectivesText" not in entry:
                            v = self.vm.localized(vml, "Objectives_loc{n}", locale)
                            if v:
                                entry["objectivesText"] = [v]
                        cached = self.cache_texts.get(locale, {}).get(entity_id, {})
                        for field in ("objectivesText", "details", "endText"):
                            if field not in entry and cached.get(field):
                                entry[field] = cached[field]
                    elif kind == "npc":
                        ne = self.l10n.get("Npc", {}).get(str(entity_id), {})
                        sub = ne.get("subName", {}).get(locale) or self.vm.localized(
                            self.vm.creature_locales.get(entity_id), "subname_loc{n}", locale)
                        if sub:
                            entry["subName"] = sub
                    elif kind == "item":
                        desc = self.vm.localized(self.vm.item_locales.get(entity_id), "description_loc{n}", locale)
                        if desc:
                            entry["description"] = desc
                    if entry:
                        out[entity_id] = entry
                write_shards(base / "l10n" / locale / kind, out)

            search = {kind: {str(i): name_of(kind, i) for i in recs if name_of(kind, i)}
                      for kind, recs in records.items()}
            write_json(base / "l10n" / locale / "search.json", search)
            zone_names = {}
            for area_id in self.zones:
                v = self.vm.localized(self.vm.area_locales.get(area_id), "NameLoc{n}", locale)
                if v:
                    zone_names[str(area_id)] = v
            write_json(base / "l10n" / locale / "zones.json", zone_names)


def side_of(races):
    if not races:
        return "B"
    a, h = races & C.ALLIANCE_RACES, races & C.HORDE_RACES
    if a and not h:
        return "A"
    if h and not a:
        return "H"
    return "B"


def is_full_side(races):
    """True if the mask is exactly one or both complete Vanilla faction race sets."""
    vanilla_a, vanilla_h = 1 | 4 | 8 | 64, 2 | 16 | 32 | 128
    a, h = races & C.ALLIANCE_RACES, races & C.HORDE_RACES
    return (a == 0 or a & vanilla_a == vanilla_a) and (h == 0 or h & vanilla_h == vanilla_h)


def git_rev(path):
    try:
        return subprocess.check_output(["git", "-C", str(path), "log", "-1", "--format=%h %cs"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("QUESTIE_REV") or None  # e.g. Docker builds without .git


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "web" / "static" / "data"))
    ap.add_argument("--flavors", default=",".join(C.FLAVORS))
    ap.add_argument("--vmangos", default=str(ROOT / "vendor" / "vmangos" / "sqlite-dump" / "mangos.sqlite"))
    ap.add_argument("--rewards", default=str(ROOT / "QuestRewards.lua"))
    args = ap.parse_args()
    out = Path(args.out)

    print("loading VMangos …", file=sys.stderr)
    vm = VMangos(args.vmangos)
    rewards_path = Path(args.rewards)
    quest_rewards = load_quest_rewards_lua(rewards_path) if rewards_path.exists() else None

    meta = {
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "questie": git_rev(ROOT / "vendor" / "QuestieDB"),
        "vmangos": (ROOT / "vendor" / "vmangos" / "VERSION").read_text().strip()
        if (ROOT / "vendor" / "vmangos" / "VERSION").exists() else None,
        "locales": C.LOCALES,
        "flavors": {},
    }
    # keep entries of flavors not rebuilt this time (e.g. --flavors forever)
    previous = out / "meta.json"
    if previous.exists():
        meta["flavors"] = json.loads(previous.read_text()).get("flavors", {})
    report_path = out / "uimap-report.json"
    uimap_report = json.loads(report_path.read_text()) if report_path.exists() else {}
    for site_id in args.flavors.split(","):
        print(f"building {site_id} …", file=sys.stderr)
        flavor = Flavor(site_id, vm, quest_rewards)
        counts = flavor.build(out)
        meta["flavors"][site_id] = {"label": C.FLAVORS[site_id]["label"], "counts": counts}
        uimap_report[site_id] = flavor.uimap_report
        print(f"  {counts}", file=sys.stderr)
    write_json(out / "meta.json", meta)
    # uiMapId coverage per quest; the release workflow compares it with the previous release
    write_json(out / "uimap-report.json", uimap_report)


if __name__ == "__main__":
    main()
