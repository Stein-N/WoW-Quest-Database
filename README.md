# WoW Quest Database

Statische Webseite mit allen Quests, NPCs, Objekten und Items für **WoW Classic Era** und
**WoW Forever**. Die Daten stammen aus [QuestieDB](https://github.com/Questie/QuestieDB)
(kuratierte Questdaten, Spawns, Übersetzungen) und der Welt-Datenbank von
[VMangos](https://github.com/vmangos/core) (Questtexte, Belohnungen, Item-Werte, Loot).

## Schnellstart

Voraussetzungen: Python ≥ 3.12 (mit Pillow nur für Karten), Node.js ≥ 22, git.

```sh
git submodule update --init
make data      # QuestieDB exportieren, VMangos-Snapshot laden, web/static/data erzeugen
make dev       # Entwicklungsserver auf http://localhost:5173
make build     # statische Seite in web/build/
make maps      # Kartenbilder neu aus den lokalen WoW-Clients ziehen, siehe docs/MAPS.md
make update    # neueste QuestieDB- und VMangos-Daten holen und neu bauen
```

## Daten als Lua exportieren

`etl/export_lua.py` schreibt die zusammengeführten Daten (QuestieDB + VMangos) als Lua-Tabellen,
standardmäßig im Addon-Format wie `QuestRewards.lua`. Voraussetzung ist `make data`. Dieselbe
Funktion gibt es auf der Webseite unter **Export**: Optionen wählen, *Generate Lua*, herunterladen
oder kopieren. Die Logik steckt in `web/src/lib/lua-export.ts` und erzeugt dieselbe Ausgabe wie das
Skript.

**Texte stehen immer in einer eigenen Datei**, verknüpft über die ID. Pro Export entstehen deshalb
zwei Dateien:

```lua
-- questData.lua                          -- questTexts.deDE.lua
local _, addon = ...                      local _, addon = ...
addon.questData = {                       addon.questTexts = addon.questTexts or {}
    [33] = { level = 2, zone = 9,         addon.questTexts["deDE"] = {
             rewards = { ... } },             [33] = { name = "Wölfe an der Grenze",
}                                                      objectivesText = {...}, details = "...", ... },
                                          }
```

| Typ | Textfelder (→ `<typ>Texts.<sprache>.lua`) |
| --- | --- |
| Quest | `name`, `objectivesText`, `details`, `progress`, `completion`, `endText` |
| NPC | `name`, `subName` |
| Objekt | `name` |
| Item | `name`, `description` |

Mehrere Sprachen lassen sich nebeneinander laden (`addon.questTexts.enUS`, `addon.questTexts.deDE`, …).
Im Standardmodus (`--refs id`) enthält die Datendatei keine Anzeigetexte: Verweise auf Quests, NPCs,
Items, Zonen und Fraktionen sind reine IDs.

```sh
# alle Forever-Quests (questData.lua + questTexts.enUS.lua) nach export/
python3 etl/export_lua.py --flavor forever --type quest -o export/
# deutsche Texte zusätzlich
python3 etl/export_lua.py --flavor forever --type quest --fields name,objectivesText,details --locale deDE -o export/
# NPCs einer Zone (Elwynn = 12) ohne Quellenangaben
python3 etl/export_lua.py --flavor classic --type npc --zone 12 --exclude sources -o export/
# Questreihen als `return {...}` für dofile/require
python3 etl/export_lua.py --flavor classic --type questline --style return -o export/
# über make
make lua ARGS="--flavor forever --type item --ids 100-200 -o export/"
```

| Option | Bedeutung |
| --- | --- |
| `--type` | `quest`, `npc`, `object`, `item`, `questline` |
| `--fields` / `--exclude` | Felder behalten bzw. weglassen (kommagetrennt) |
| `--ids` | IDs oder Bereiche, z. B. `2,33,100-200` |
| `--zone` | nur Einträge dieser Zone (Area-ID) |
| `--locale` | Sprache der Texte (Standard `enUS`; `deDE`, `frFR`, …) |
| `--refs` | `id` (Standard): Verweise als reine IDs; `full`: mit Typ und Name |
| `--style` | `addon` (Standard) oder `return` |
| `--var` / `--text-var` | Tabellennamen (Standard `<type>Data` / `<type>Texts`) |
| `-o` / `--out-dir` | Zielordner (Standard: aktueller Ordner) |

Die Feldnamen entsprechen den JSON-Daten der Webseite (siehe `web/src/lib/types.ts`).

## Aufbau

```
etl/questie_export.lua   QuestieDB (inkl. Corrections) → build/questie/<flavor>/*.json
etl/fetch_vmangos.py     lädt den VMangos-Snapshot (Release db_latest, SQLite)
etl/build.py             führt beide Quellen zusammen → web/static/data/
etl/maps.py              liest Weltkarten aus den WoW-Clients (CASC) → web/static/maps/<flavor>/
etl/casc.py, etl/db2.py   minimaler CASC- und DB2-Reader (wie wow.export, ohne GUI)
web/                     SvelteKit-App (statisch, Hash-Routing, Leaflet-Karten)
vendor/QuestieDB         Git-Submodule
QuestRewards.lua         Item-Belohnungen für Forever (aus VMangos extrahiert)
```

**Regeln beim Zusammenführen:** QuestieDB hat Vorrang bei allem, was es selbst enthält.
VMangos ergänzt nur fehlende Felder. Item-Belohnungen für Forever-Quests kommen aus
`QuestRewards.lua`, für Classic direkt aus VMangos (inkl. Anzahl).

**Datenformat für die Webseite:** Pro Flavor und Entitätstyp gibt es Shards zu je 100 IDs
(`data/classic/quest/0.json` enthält die Quests 0–99). Übersetzungen liegen unter
`data/<flavor>/l10n/<locale>/`. Indexdateien (`quests.json`, `search.json`, `zones.json`)
versorgen Liste, Suche und Zonenseiten.

## Hosting

`web/build/` ist eine rein statische Seite und braucht keine Server-Konfiguration. Die URLs
nutzen Hash-Routing (`/#/classic/quest/2`). Den Inhalt von `web/build/` in ein beliebiges
Webroot kopieren (nginx, Apache, Caddy …).

## Lizenz

GPL-3.0 (siehe `LICENSE`). QuestieDB steht unter GPL-3.0, VMangos unter GPL-2.0.
Die Kartenbilder in `web/static/maps/` sind Eigentum von Blizzard Entertainment (Repository privat).
