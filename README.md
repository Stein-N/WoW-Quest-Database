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

**Item-Belohnungen** haben dieselbe Form wie in `QuestRewards.lua`, direkt unter `rewards`:

```lua
rewards = { type = "all",    items = {4536}, ... }                         -- alle Items
rewards = { type = "single", items = {2954, 2953, 1282}, fixed = {7344} }  -- eins wählen + feste Items
rewards = { type = "all", items = {1017, 2701}, counts = { [1017] = 4 } }   -- Mengen > 1 in counts
```

Mit `--locale all` (Webseite: *All languages*) entstehen die Datendatei und eine Textdatei je
Sprache. Die Webseite bietet die Dateien zusätzlich als ZIP an. Mehrere Sprachen lassen sich nebeneinander laden (`addon.questTexts.enUS`, `addon.questTexts.deDE`, …).
Im Standardmodus (`--refs id`) enthält die Datendatei keine Anzeigetexte: Verweise auf Quests, NPCs,
Items, Zonen und Fraktionen sind reine IDs.

```sh
# alle Forever-Quests (questData.lua + questTexts.enUS.lua) nach export/
python3 etl/export_lua.py --flavor forever --type quest -o export/
# deutsche Texte zusätzlich
python3 etl/export_lua.py --flavor forever --type quest --fields name,objectivesText,details --locale deDE -o export/
# Texte in allen 10 Sprachen auf einmal (questData.lua + questTexts.<sprache>.lua je Sprache)
python3 etl/export_lua.py --flavor forever --type quest --locale all -o export/
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
| `--locale` | Sprache der Texte (Standard `enUS`; `deDE`, `frFR`, …) oder `all` für eine Textdatei pro Sprache |
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
etl/questcache.py        Parser für questcache.wdb (Questtexte aus dem Client-Cache)
web/                     SvelteKit-App (statisch, Hash-Routing, Leaflet-Karten)
vendor/QuestieDB         Git-Submodule
QuestRewards.lua         Item-Belohnungen für Forever (aus VMangos extrahiert)
```

**Eigene Korrekturen:** `etl/corrections/<flavor>.json` ergänzt oder überschreibt QuestieDB-Questfelder
(gleiche Feldnamen wie QuestieDB, z. B. `preQuestSingle`, `nextQuestInChain`, `exclusiveTo`). Jede Gruppe
nennt ihre Quelle. Aktuell: die Questreihe von Zephras Isle (Skyborne-Startgebiet in Forever) nach
[warcraft.wiki.gg](https://warcraft.wiki.gg/wiki/Zephras_Isle_storyline). Die Einträge lassen sich
1:1 an QuestieDB (`src/corrections/Forever/foreverQuestFixes.lua`) zurückmelden.

**Questtexte aus dem WoW-Client-Cache:** Für Quests ohne Texte in QuestieDB und VMangos (vor allem
neue Forever-Quests) liest `etl/import_questcache.py` die Datei `Cache/WDB/<sprache>/questcache.wdb`
eines WoW-Clients aus. Dort speichert der Client jede Quest, die man im Spiel gesehen hat: Titel, Ziel
(Mengen wie `$1oa` werden eingesetzt), Beschreibung, Abschlusstext. Die Texte landen in
`etl/corrections/questcache/<flavor>/<sprache>.json` (versioniert) und füllen beim Build nur Lücken;
englische Titel werden gegen QuestieDB geprüft.

```sh
make questcache                                    # lokaler Forever-Client
make questcache CACHE="/pfad/zu/Cache/WDB"         # z. B. Cache-Ordner eines anderen PCs
make questcache FLAVOR=classic CACHE="…/_classic_era_/Cache/WDB"
```

Danach `make site-data` (bzw. committen und den Release-Workflow abwarten).

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
Webroot kopieren (nginx, Apache, Caddy …), oder das Docker-Image verwenden.

### Docker (Homeserver)

Das `Dockerfile` baut alles im Container: QuestieDB-Export (Lua 5.1), Download des aktuellen
VMangos-Snapshots, Zusammenführen der Daten und die Webseite. Ausgeliefert wird nur die fertige
Seite über nginx (`docker/nginx.conf`, mit gzip und Caching). Es läuft auf x86-64 und ARM64.

```sh
git submodule update --init          # QuestieDB muss ausgecheckt sein
make docker                          # baut das Image "wow-quest-database"
docker run -d --name wow-quest-database -p 8080:80 --restart unless-stopped wow-quest-database
```

Oder mit Docker Compose (`docker-compose.yml`, Port 8080):

```sh
QUESTIE_REV="$(git -C vendor/QuestieDB log -1 --format='%h %cs')" docker compose up -d --build
```

`QUESTIE_REV` ist optional und wird nur als Datenstand auf der Startseite angezeigt.

**Daten aktualisieren:** `git submodule update --remote vendor/QuestieDB`, dann neu bauen.
Den VMangos-Snapshot cached Docker. Einen neueren Snapshot holt
`docker build --no-cache -t wow-quest-database .`.

### Tägliche Releases

Der Workflow `.github/workflows/daily-release.yml` läuft jeden Tag um 00:00 Uhr (Europe/Berlin):

1. zieht den aktuellen `master` von QuestieDB ins Submodule und schreibt den Datenstand
   (QuestieDB-Commit, VMangos-Snapshot) nach `data-version.json`; Änderungen werden nach `main` committet,
2. baut nur bei neuen Daten (anderer QuestieDB-Commit, VMangos-Snapshot oder geänderte eigene Korrekturen in
   `etl/corrections/`, z. B. importierte Cache-Texte) das Image für `linux/amd64` und
   `linux/arm64`, pusht es nach `ghcr.io/stein-n/wow-quest-database:<version>` und `:latest`,
3. veröffentlicht ein GitHub-Release `v<version>` mit Datenstand, Änderungen, einer fertigen
   `docker-compose.yml` (Image auf diese Version festgelegt, Port 8080) und den Images als Dateien
   (`wow-quest-database-<version>-<arch>.tar.gz`).

**Docker Hub (optional):** Unter *Settings → Secrets and variables → Actions* die Secrets
`DOCKERHUB_USERNAME` und `DOCKERHUB_TOKEN` (Access Token mit Read & Write) anlegen, optional die Variable
`DOCKERHUB_REPOSITORY` (Standard `<username>/wow-quest-database`). Das Repository vorher auf Docker Hub
**als privat anlegen**: Der Workflow pusht nur in ein bestehendes privates Repository, weil das Image
Blizzard-Kartenbilder enthält (ein fehlendes Repository würde Docker Hub sonst beim Push automatisch, oft
öffentlich, anlegen). Passt etwas nicht, wird Docker Hub mit einer Fehlermeldung im Actions-Log
übersprungen, GHCR und das Release laufen trotzdem.

Versionen beginnen bei `0.1.0`; jedes weitere Release erhöht die letzte Stelle (`0.1.1`, `0.1.2`, …).
Tage ohne neue Daten erzeugen kein Release; reine Code-Änderungen erscheinen mit dem nächsten Daten-Release. Manuell starten: *Actions → Daily data release → Run workflow*
(mit `force` auch ohne Änderung).

Auf dem Homeserver: `docker-compose.yml` aus dem Release herunterladen und `docker compose up -d`.
Für ein Update die Datei des neuen Releases nehmen und den Befehl wiederholen. Ohne Compose:

```sh
# einmalig: Token mit read:packages (das Repository ist privat)
echo <TOKEN> | docker login ghcr.io -u Stein-N --password-stdin
docker pull ghcr.io/stein-n/wow-quest-database:latest
docker rm -f wow-quest-database
docker run -d --name wow-quest-database -p 8080:80 --restart unless-stopped ghcr.io/stein-n/wow-quest-database:latest
```

Ohne Registry-Zugang die Image-Datei aus dem Release laden (`gunzip -c wow-quest-database-0.1.0-amd64.tar.gz | docker load`).
Sie trägt denselben Namen wie in der Registry, die `docker-compose.yml` des Releases nutzt sie dann direkt.

## Lizenz

GPL-3.0 (siehe `LICENSE`). QuestieDB steht unter GPL-3.0, VMangos unter GPL-2.0.
Die Kartenbilder in `web/static/maps/` sind Eigentum von Blizzard Entertainment (Repository privat).
