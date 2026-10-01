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
