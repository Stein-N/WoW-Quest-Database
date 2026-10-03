# WoW Forever Quest Database

Statische Webseite mit allen Quests, NPCs, Objekten und Items für **WoW Forever**. Die Daten
stammen aus den Forever-Daten von [QuestieDB](https://github.com/Questie/QuestieDB) (kuratierte
Questdaten, Spawns, Übersetzungen), ergänzt um die Welt-Datenbank von
[VMangos](https://github.com/vmangos/core) (Questtexte, Belohnungen, Item-Werte, Loot, Händler),
den Client-Cache, Wowhead und AzerothCore (Übersetzungen). Bis Oktober 2026 deckte die Seite auch
Classic Era ab; Daten und Karten dafür wurden entfernt.

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

`etl/export_lua.py` schreibt die zusammengeführten Daten (QuestieDB + VMangos) als Lua-Tabellen
im Addon-Format. Voraussetzung ist `make data`. Dieselbe
Funktion gibt es auf der Webseite unter **Export**: Optionen wählen, *Generate Lua*, herunterladen
oder kopieren. Die Logik steckt in `web/src/lib/lua-export.ts` und erzeugt dieselbe Ausgabe wie das
Skript.

**Texte stehen immer in eigenen Dateien pro Sprache**, verknüpft über die ID. Englisch ist die
Basis und der Fallback: `enUS` legt die Tabelle an, jede andere Sprache ersetzt nur die Einträge, die
sie übersetzt (vollständig, nicht übersetzte Felder enthalten den englischen Text), und läuft nur im
Client dieser Sprache. Die `enUS`-Datei wird immer mit exportiert und muss zuerst geladen werden.

```lua
-- questData.lua                     -- questTexts.enUS.lua
local _, addon = ...                 local _, addon = ...
addon.questData = {                  local L = {
    [33] = { level = 2, zone = 9,        [33] = { name = "Wolves Across the Border", ... },
             rewards = { ... } },    }
}                                    addon.questTexts = setmetatable(L, { __index = function(_, key) return key end })

-- questTexts.deDE.lua
if GetLocale() ~= "deDE" then return end
local _, addon = ...
local L = addon.questTexts

L[33] = { name = "Wölfe an der Grenze", objectivesText = "...", details = "...", ... }
```

`objectivesText` ist ein Text mit `$B` als Zeilenumbruch, `$N` wird zu `${playerName}`.

| Typ | Textfelder (→ `<typ>Texts.<sprache>.lua`) |
| --- | --- |
| Quest | `name`, `objectivesText`, `details`, `progress`, `completion`, `endText` |
| NPC | `name`, `subName` |
| Objekt | `name` |
| Item | `name`, `description` |

**Item-Belohnungen** stehen direkt unter `rewards`, mit `type` für die Art der Belohnung:

```lua
rewards = { type = "all",    items = {4536}, ... }                         -- alle Items
rewards = { type = "single", items = {2954, 2953, 1282}, fixed = {7344} }  -- eins wählen + feste Items
rewards = { type = "all", items = {1017, 2701}, counts = { [1017] = 4 } }   -- Mengen > 1 in counts
```

Mit `--locale all` (Webseite: *All languages*) entstehen die Datendatei und eine Textdatei je
Sprache. Die Webseite bietet die Dateien zusätzlich als ZIP an. Die Datendatei enthält keine
Anzeigetexte: Verweise auf Quests, NPCs, Items, Zonen und Fraktionen sind reine IDs.

```sh
# alle Forever-Quests (questData.lua + questTexts.enUS.lua) nach export/
python3 etl/export_lua.py --type quest -o export/
# deutsche Texte zusätzlich
python3 etl/export_lua.py --type quest --fields name,objectivesText,details --locale deDE -o export/
# Texte in allen 10 Sprachen auf einmal (questData.lua + questTexts.<sprache>.lua je Sprache)
python3 etl/export_lua.py --type quest --locale all -o export/
# NPCs einer Zone (Elwynn = 12) ohne Quellenangaben
python3 etl/export_lua.py --type npc --zone 12 --exclude sources -o export/
# Questreihen
python3 etl/export_lua.py --type questline -o export/
# über make
make lua ARGS="--type item --ids 100-200 -o export/"
```

| Option | Bedeutung |
| --- | --- |
| `--type` | `quest`, `npc`, `object`, `item`, `questline` |
| `--fields` / `--exclude` | Felder behalten bzw. weglassen (kommagetrennt) |
| `--ids` | IDs oder Bereiche, z. B. `2,33,100-200` |
| `--zone` | nur Einträge dieser Zone (Area-ID) |
| `--locale` | Sprache der Texte (Standard `enUS`; `deDE`, `frFR`, …) oder `all` für eine Textdatei pro Sprache |
| `--var` / `--text-var` | Tabellennamen (Standard `<type>Data` / `<type>Texts`) |
| `-o` / `--out-dir` | Zielordner (Standard: aktueller Ordner) |

Die Feldnamen entsprechen den JSON-Daten der Webseite (siehe `web/src/lib/types.ts`).

**`zone` und `uiMapId` bei Quests:** `zone` ist die AreaTable-ID (wie in QuestieDB/VMangos, negativ für
Kategorien wie Klassen oder Berufe). `uiMapId` ist die Karte dieser Zone für die WoW-Karten-API
(`C_Map`), z. B. Nordhaintal (`zone = 9`) → Wald von Elwynn (`uiMapId = 1429`). Sie wird bestimmt aus
der QuestieDB-Zuordnung, sonst über die übergeordnete Zone (QuestieDB, VMangos), eigene Einträge in
`etl/corrections/<flavor>.json` (`areaUiMaps`) oder den Standort der Questgeber. Kategorien und Zonen
ohne eigene Karte (Blackrockberg, Forever-„Crafting“) haben keine `uiMapId`.

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
```

Danach `make site-data` (bzw. committen und den Release-Workflow abwarten).

**Regeln beim Zusammenführen:** QuestieDB hat Vorrang bei allem, was es selbst enthält.
VMangos ergänzt nur fehlende Felder; Item-Belohnungen (inkl. Anzahl) kommen aus VMangos.

**Datenformat für die Webseite:** Pro Entitätstyp gibt es Shards zu je 100 IDs
(`data/forever/quest/0.json` enthält die Quests 0–99). Übersetzungen liegen unter
`data/<flavor>/l10n/<locale>/`. Indexdateien (`quests.json`, `search.json`, `zones.json`)
versorgen Liste, Suche und Zonenseiten.

## Hosting

`web/build/` ist eine rein statische Seite und braucht keine Server-Konfiguration. Die URLs
nutzen Hash-Routing (`/#/quest/2`; alte Links wie `/#/forever/quest/2` oder `/#/classic/quest/2`
werden umgeleitet). Den Inhalt von `web/build/` in ein beliebiges
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
3. veröffentlicht ein GitHub-Release `v<version>` mit Datenstand, Änderungen, einem Bericht zu den
   `uiMapId`s (Abdeckung, seit dem letzten Release neu zugeordnete/geänderte Quests, verbleibende Lücken;
   Rohdaten als `uimap-report.json` angehängt), einer fertigen
   `docker-compose.yml` (Image auf diese Version festgelegt, Port 8080) und den Images als Dateien
   (`wow-quest-database-<version>-<arch>.tar.gz`).

**Docker Hub (optional):** Unter *Settings → Secrets and variables → Actions* die Secrets
`DOCKERHUB_USERNAME` und `DOCKERHUB_TOKEN` (Access Token mit Read & Write) anlegen, optional die Variable
`DOCKERHUB_REPOSITORY` (Standard `<username>/wow-quest-database`). Das Repository vorher auf Docker Hub
**als privat anlegen**: Der Workflow pusht nur in ein bestehendes privates Repository, weil das Image
Blizzard-Kartenbilder enthält (ein fehlendes Repository würde Docker Hub sonst beim Push automatisch, oft
öffentlich, anlegen). Passt etwas nicht, wird Docker Hub mit einer Fehlermeldung im Actions-Log
übersprungen, GHCR und das Release laufen trotzdem.

**Patch Notes** (Startseite und Release-Notes, Quelle `CHANGELOG.json`):

- **Webseite und Daten in Textform:** Neue Funktionen und Datenquellen werden bei der Entwicklung als
  Text unter `"unreleased"` in `CHANGELOG.json` eingetragen (`"website"` bzw. `"data"`).
- **Datenänderungen automatisch:** Der Build schreibt einen Fingerabdruck der Daten (`build/data-digest.json`:
  Name und Inhalts-Hash jeder Quest, jedes NPCs, Objekts und Items, Textabdeckung je Sprache). Der Workflow
  vergleicht ihn mit dem des vorigen Releases (Release-Anhang `data-digest.json.gz`, für `v0.1.1` einmalig
  `etl/digests/v0.1.1.json.gz`) und beschreibt die Änderungen in Worten, z. B. „12 quests added: …,
  45 quests updated, Quest descriptions: German +10“.
- **Entwurf durch Claude (optional):** Ist das Secret `CLAUDE_CODE_OAUTH_TOKEN` gesetzt (`claude setup-token`,
  Claude-Pro-Abo genügt), schreibt Claude Code vor dem Release ergänzende Notes für alles, was noch nicht
  beschrieben ist. Claude bekommt nur Text (Commits mit Beschreibung, geänderte Dateien, Datenänderungen,
  vorhandene Notes; Anweisung in `etl/patch-notes-prompt.md`), hat keine Werkzeuge und antwortet mit JSON,
  das `etl/changelog.py merge-notes` prüft und unter `"unreleased"` ergänzt. Ohne Secret oder bei Fehlern
  läuft das Release mit den vorhandenen Notes weiter.
- Vor dem Image-Build ruft der Workflow `etl/changelog.py add <version>` auf: Die unveröffentlichten Notes, die
  Datenänderungen und die Commit-Titel (als „Technical changes“) werden zur neuen Version und committet, damit
  jedes Image seine eigenen Notes zeigt. `etl/changelog.py render <version>` liefert dieselben Notes als Markdown
  für das GitHub-Release.

Versionen beginnen bei `0.1.0`; jedes weitere Release erhöht die letzte Stelle (`0.1.1`, `0.1.2`, …).
Tage ohne neue Daten erzeugen kein Release; reine Code-Änderungen erscheinen mit dem nächsten Daten-Release. Manuell starten: *Actions → Daily data release → Run workflow*
(mit `force` auch ohne Änderung).

Die `docker-compose.yml` jedes Releases nutzt das Image aus dem Docker-Hub-Repository (falls Docker Hub
eingerichtet ist, sonst GHCR); die Image-Dateien am Release tragen denselben Namen. Sie enthält außerdem einen `x-casaos`-Block für **ZimaOS/CasaOS**
(Titel, Beschreibung, Web-UI-Port 8080 und das App-Icon). Das Icon (`docker/icon.png`, aus `logo.png`)
ist als Data-URL eingebettet, weil das Repository privat ist und es keine öffentliche Bild-URL gibt.
Alternativ liefert die Seite das Logo selbst unter `http://<server>:8080/logo.png` aus.

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
