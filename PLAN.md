# WoW Quest Database – Projektplan (Entwurf)

> Status: **Entwurf zur Abstimmung** · Stand: 2026-10-01

Ziel: Eine Webseite, die alle Quests (plus zugehörige NPCs, Objekte und Items) für
**WoW Classic (Era)** und **WoW Forever** durchsuchbar und verlinkt darstellt –
inklusive Karten mit Questgebern, Abgabe-NPCs und Questzielen.

---

## 1. Datenquellen – was steckt wo drin?

### 1.1 QuestieDB (`github.com/Questie/QuestieDB`)

Analysiert am aktuellen Stand des Repos (geklont, ~84 MB Rohdaten).

| Aspekt | Inhalt |
| --- | --- |
| Format | Lua-Tabellen (`data/<Flavor>/<flavor>{Quest,Npc,Object,Item}DB.lua`), positionsbasiert; Feldbedeutung in `src/meta/*Meta.lua` |
| Flavors | Classic, TBC, Wotlk, Cata, MoP, **Forever** (eigene, unabhängige Daten) |
| Quests (36 Felder) | Name, Start/Ende (NPC/Objekt/Item), Level, Rassen/Klassen-Bitmasken, Zieltext, Objectives (Kill/Objekt/Item/Ruf/Kill-Credit/Spell), Vorquests, Folgequest, Breadcrumbs, Zone, Skill/Ruf-Anforderungen, Ruf-Belohnung, Flags … |
| NPCs (15 Felder) | Name, Level, HP, Rang, **Spawns (Zone → Koordinaten in %)**, Wegpunkte, Fraktion, Questbeziehungen, Untertitel, NPC-Flags |
| Objekte (7 Felder) | Name, Spawns, Zone, Questbeziehungen, Wegpunkte |
| Items (16 Felder) | Name, Drop-Quellen (NPC/Objekt/Item), Händler, Quest-Bezug, Itemlevel, Klasse … |
| Korrekturen | `src/corrections/<Flavor>/` – von der Questie-Community gepflegte Fixes, müssen beim Export angewendet werden |
| Lokalisierung | `l10n/` – 9 Sprachen (u. a. **deDE**) für Namen/Texte |
| Support-Daten | `support/` – Zonen-Mapping (AreaId ↔ UiMapId), Quest-XP, Droptabellen, Fraktions-Templates, Dungeons |
| Forever | `data/Forever`, `support/Forever`, `l10n/Forever`; Koordinaten bereits auf Forever-Karten umgerechnet (`conversion.json`) |

**Stärken:** kuratierte Questgeber/-abgaben, Spawn-Koordinaten direkt als Karten-%, Forever-Daten, deutsche Übersetzungen.
**Lücken:** keine vollständigen Questtexte (nur Zieltext), keine Belohnungen außer Ruf, keine Item-Stats, keine Lootchancen pro NPC.

### 1.2 VMangos Core (`github.com/vmangos/core`)

- Die **Weltdatenbank** liegt nicht als Datei im Repo, sondern als Release
  `db_latest` (aktuell „Development Database Snapshot 2026-09-28“) – **es gibt sie
  sogar direkt als SQLite** (`db-sqlite-*.zip`, ~42 MB) neben dem MySQL-Dump.
- Relevante Tabellen (MaNGOS-Schema): `quest_template`, `creature_template`,
  `creature`, `gameobject_template`, `gameobject`, `item_template`,
  `creature_loot_template`, `gameobject_loot_template`, `npc_vendor`,
  `creature_questrelation` / `creature_involvedrelation` (bzw. `*_questrelation`),
  `locales_*` usw.
- Besonderheit: Datensätze haben **Patch-Spalten** (1.2 – 1.12) → Inhalte pro Patch darstellbar.
- Koordinaten sind **Weltkoordinaten** (x/y/z + map-ID), keine Karten-%.

**Stärken:** vollständige Questtexte (Beschreibung, Fortschritts- und Abschlusstext),
Belohnungen (Items, Auswahl-Items, Gold, XP), Item-Stats, Loot-Tabellen mit Chancen,
Händlerlisten, Patch-Historie.
**Lücken:** nur Vanilla 1.12 – **keine Forever-Daten**.

### 1.3 Konsequenz für die Zusammenführung

| Datenbereich | Classic | Forever |
| --- | --- | --- |
| Quest-Grunddaten, Questgeber, Ziele, Ketten | QuestieDB | QuestieDB |
| Questtexte, Belohnungen | VMangos | VMangos *nur* wo ID identisch und Inhalt nicht von Forever überschrieben – sonst „nicht verfügbar“ |
| Karten-Spawns | QuestieDB (bereits %) | QuestieDB (Forever-konvertiert) |
| Item-Stats, Loot-Chancen, Händler | VMangos | VMangos mit Hinweis „Stand Classic“ (zu klären) |
| Deutsche Texte | QuestieDB `l10n` (+ VMangos `locales_*`, falls vorhanden) | QuestieDB `l10n/Forever` |

Join-Schlüssel sind die Blizzard-IDs (Quest-, Creature-, GameObject-, Item-ID); beide
Quellen nutzen dieselben IDs. Abweichungen (z. B. anderer Name, anderes Level) werden im
Import protokolliert; bei Konflikten gewinnt **QuestieDB** (Community-korrigiert),
VMangos ergänzt nur fehlende Felder.

---

## 2. Architektur

```
 ┌───────────────┐   ┌───────────────┐
 │  QuestieDB    │   │ VMangos       │
 │  (git clone)  │   │ db_latest     │
 └──────┬────────┘   └──────┬────────┘
        │ Lua-Exporter       │ SQLite lesen
        ▼                    ▼
 ┌──────────────────────────────────────┐
 │  ETL-Pipeline (Python)               │
 │  normalisieren · mergen · validieren │
 └──────────────────┬───────────────────┘
                    ▼
        site.db  (SQLite, read-only, pro Build neu)
                    ▼
 ┌──────────────────────────────────────┐
 │  Web-App (SvelteKit oder Astro)      │
 │  Listen, Detailseiten, Suche, Karten │
 └──────────────────────────────────────┘
```

### 2.1 Import / ETL

1. **QuestieDB-Export (Lua → JSON):** Ein kleines Lua-5.1-Skript lädt die Rohdaten
   **mit angewendeten Static Corrections** (QuestieDB bringt einen Lua-Interpreter und
   einen Emulator für den Source-Mode mit) und schreibt pro Flavor JSON.
   Vorteil gegenüber eigenem Lua-Parser: Korrekturen und Derived Passes werden exakt so
   angewendet wie im Addon.
2. **VMangos-Import:** SQLite-Snapshot herunterladen, relevante Tabellen per SQL abfragen.
   Patch-Spalten auswerten (Standard: letzter Patch 1.12).
3. **Merge & Validierung:** in ein eigenes, sauberes Schema (siehe 2.2); Konflikte und
   fehlende Referenzen als Bericht ausgeben.
4. **Versionierung:** Commit-Hash von QuestieDB und DB-Snapshot-Name von VMangos werden in
   der DB gespeichert und auf der Seite angezeigt („Datenstand“).

### 2.2 Ziel-Datenmodell (vereinfacht)

```
flavor(id, name)                       -- classic, forever
quest(flavor, id, name, level, req_level, races, classes, zone_id,
      objectives_text, description, progress_text, completion_text,
      money, xp, prev_quest, next_quest, flags, …)
quest_starter / quest_ender(flavor, quest_id, entity_type, entity_id)
quest_objective(flavor, quest_id, type, target_id, count, text)
quest_reward(flavor, quest_id, item_id, count, is_choice)
quest_reputation(flavor, quest_id, faction_id, value)
npc(flavor, id, name, subname, min_lvl, max_lvl, rank, faction, flags)
object(flavor, id, name, …)
item(flavor, id, name, quality, ilvl, req_level, class, subclass, stats_json …)
spawn(flavor, entity_type, entity_id, ui_map_id, x, y)   -- x/y in Prozent
waypoint(…)
loot(flavor, source_type, source_id, item_id, chance)
zone(flavor, area_id, ui_map_id, name, parent)
l10n(flavor, entity_type, entity_id, locale, field, text)
```

### 2.3 Web-Frontend

**Vorschlag:** SvelteKit (oder Astro) + SQLite (read-only), TypeScript.

- **Seiten:** Startseite mit Suche · Questliste (Filter: Flavor, Zone, Level, Fraktion,
  Klasse, Rasse, Questtyp) · Quest-Detail · NPC-Detail · Objekt-Detail · Item-Detail ·
  Zonen-Übersicht mit allen Quests der Zone.
- **Quest-Detail:** Texte, Ziele, Belohnungen, Questkette (Vor-/Folgequests als Graph),
  Questgeber/-abgabe mit Karte, Karte der Zielorte (Mob-Spawns, Objekte, Item-Drops).
- **Suche:** SQLite-FTS5 serverseitig, oder bei statischer Variante Pagefind.
- **Sprachen:** Englisch + Deutsch (Daten aus `l10n`), UI-Texte i18n.
- **Flavor-Umschalter** global (Classic / Forever), URLs z. B. `/classic/quest/2`.
- **Deployment:** Entweder komplett statisch generiert (~2 × 30–50 k Seiten, gut cachebar)
  oder kleiner Node-Server mit SQLite. Entscheidung siehe offene Fragen.

### 2.4 Karten

- QuestieDB-Koordinaten sind **Prozentwerte (0–100) auf einer Zonenkarte (UiMapId)** –
  ideal für eine Darstellung mit **Leaflet** (`CRS.Simple`, Bild als Overlay, Marker in %).
- Marker-Typen: Questgeber (!), Abgabe (?), Mob-Spawns, Objekte, Trigger-Bereiche,
  Patrouillen-Wegpunkte als Linien. Cluster bei vielen Spawns.
- Dungeon-Quests: Verweis auf Eingang (`support/Zones/dungeons.lua`).
- **Kartenbilder:** Weder QuestieDB noch VMangos enthalten Kartengrafiken. Optionen:
  1. Aus einem eigenen WoW-Client extrahieren (BLP → PNG, z. B. mit wow.export / BLP-Tools).
     Rechtlich: Blizzard-Assets – üblich bei Fan-Datenbanken, aber Graubereich.
  2. Eigene, schematische Karten (Zonenumrisse) – rechtlich sauber, viel Aufwand.
  3. Zunächst ohne Hintergrundbild (nur Koordinatengitter + Marker) und Bilder später ergänzen.
- Forever: Die Koordinaten passen auf die Forever-Karten; falls sich Kartenbilder
  unterscheiden, braucht es einen eigenen Bildsatz.

---

## 3. Projektstruktur (Vorschlag)

```
/etl
  questie_export.lua      # Lua: QuestieDB inkl. Corrections → JSON
  import_questie.py
  import_vmangos.py
  merge.py
  build_db.py             # erzeugt data/site.db
/web                      # SvelteKit/Astro-App
/assets/maps              # Kartenbilder (nicht im Git, falls Blizzard-Assets)
/vendor                   # QuestieDB als Git-Submodule, VMangos-Snapshot per Download
Makefile / justfile       # `make data`, `make dev`, `make build`
```

---

## 4. Umsetzungsphasen

| Phase | Inhalt | Ergebnis |
| --- | --- | --- |
| **0 – Machbarkeit** | QuestieDB-Export nach JSON (Classic), VMangos-SQLite einlesen, ID-Abgleich messen (wie viele Quests matchen, wie viele Konflikte) | Kurzer Bericht, Bestätigung des Datenmodells |
| **1 – Datenpipeline** | Vollständiger ETL für Classic + Forever, `site.db`, Validierungsbericht | Reproduzierbarer `make data` |
| **2 – MVP-Webseite** | Questliste mit Filtern, Quest-/NPC-/Item-/Objekt-Detailseiten, Suche, Flavor-Umschalter | Lokal lauffähige Seite ohne Karten |
| **3 – Karten** | Leaflet-Integration, Marker, Kartenbilder (je nach Entscheidung) | Karten auf Quest-/NPC-Seiten und Zonenansicht |
| **4 – Ausbau** | Deutsch, Questketten-Graph, Loot-Tabellen, Patch-Ansicht (VMangos), Tooltips, Permalinks | Vollständige Seite |
| **5 – Betrieb** | Deployment, automatischer Daten-Refresh (z. B. wöchentlich per CI), Datenstand-Anzeige | Öffentliche Seite |

---

## 5. Risiken & rechtliche Punkte

- **Lizenz QuestieDB:** ~~Das Repo enthält keine Lizenzdatei~~ → geklärt: GPL-3.0 (siehe 7.).
- **Lizenz VMangos:** GPL-2.0 (Code); Datenbankinhalte stammen ursprünglich von Blizzard.
  Dieses Projekt ist GPL-3.0 – kompatibel für eigene Nutzung, Attribution auf der Seite.
- **Blizzard-Assets** (Kartenbilder, Icons): Graubereich, siehe 2.4. Icons ggf. ebenfalls
  aus dem Client oder weglassen.
- **Forever-Datenqualität:** Laut QuestieDB-Doku ist Forever nicht vollständig
  (Delta-Base liefert keine vollständigen Objectives/Restriktionen). Wir zeigen
  fehlende Daten transparent als „unbekannt“ an statt Classic-Werte unbemerkt zu übernehmen.
- **Formatänderungen:** QuestieDB entwickelt sich aktiv; der Lua-Exporter muss das
  Meta-Schema (`src/meta`) dynamisch lesen statt Feldindizes fest zu kodieren.

---

## 6. Offene Fragen an dich

1. **Hosting / Zielgruppe:** Nur lokal/privat oder öffentlich im Internet?
   (Beeinflusst Lizenz- und Kartenbild-Frage stark.)
2. **Statisch oder Server?** Statische Seite (billig, z. B. GitHub Pages/Netlify) oder
   kleiner Server (flexiblere Suche/Filter)?
3. **Tech-Stack:** Einverstanden mit Python (ETL) + SvelteKit/Astro (Web)? Oder gibt es
   Präferenzen (z. B. React/Next.js, PHP, .NET)?
4. **Kartenbilder:** Hast du einen WoW-Classic-Client zum Extrahieren, oder sollen wir
   mit Option 3 (ohne Hintergrund) starten?
5. **Sprache:** Englisch + Deutsch zum Start, oder nur eine Sprache?
6. **Umfang:** Nur Classic Era + Forever, oder sollen später auch TBC/Wotlk/… möglich
   sein? (Das Datenmodell ist dafür schon vorbereitet, da QuestieDB sie mitliefert.)
7. **VMangos-Daten für Forever:** Sollen Questtexte/Belohnungen aus VMangos auch bei
   Forever-Quests angezeigt werden (mit Hinweis „Classic-Stand“), oder dort strikt nur
   QuestieDB-Daten?

   
## 7. Antworen zu 6.
1. Vorrangig soll die Webseite als private datenbank dienen
2. Falls möglich über Github pages, ansonsten werde ich die webseite auf meinem private server hosten
3. etl und SvelteKit hört sich gut an
4. ich habe wow.export installiert: /home/nico/Projekte/WoW-Export/
5. Die webseite selber sollte erstmal nur in Englisch verfügbar sein, Quest Daten sollten in allen möglichen Sprachen anzeigbar sein.
6. Vorerst nur Classic Era und Forever, da das die Daten sind die ich benötige
7. Die Daten von Qestie sollten vorrangig genutzt werden, da diese kuratert sind. Item Rewards habe ich bereits aus VMangos core extrahiert und zwischen fixed und single choice rewards unterschieden (QuestRewards.lua)
Zusatz: QuestieDB steht ebefalls unter GPL-3.0, da es auf OpenSource Daten basiert

---

## 8. Stand der Umsetzung (2026-10-01)

Entscheidungen aus 7. umgesetzt:

- **Statische Seite** mit SvelteKit (`adapter-static`) und **Hash-Routing**. Dieselbe Ausgabe läuft
  auf GitHub Pages und auf dem eigenen Server, ohne Rewrites. Hinweis: Pages ist immer öffentlich.
- UI auf Englisch, **Questdaten in 10 Sprachen** umschaltbar (enUS + 9 QuestieDB-Locales;
  Questtexte aus VMangos `locales_quest`, außer ptBR).
- Nur **Classic Era + Forever**. QuestieDB hat Vorrang. Forever-Item-Belohnungen kommen aus
  `QuestRewards.lua`.

| Phase | Status |
| --- | --- |
| 0 – Machbarkeit | ✅ Classic: 4.250 von 4.257 Quests in VMangos gefunden. Forever: 739 Quests ohne VMangos-Gegenstück |
| 1 – Datenpipeline | ✅ `make data`: Lua-Export inkl. Corrections → Merge → JSON-Shards (~35 s, ~210 MB) |
| 2 – MVP-Webseite | ✅ Questliste mit Filtern, Detailseiten für Quest/NPC/Objekt/Item, Zonen, Suche |
| 3 – Karten | ✅ Leaflet-Karten; eigene Kartensätze aus Era- (54) und Forever-Client (60), erkundet und mit Nebel (`make maps`, docs/MAPS.md) |
| 4 – Ausbau | ✅ Übersetzungen, Questketten, Loot (direkte Einträge), Item-Tooltips. Offen: Patch-Ansicht, Ketten-Graph, Icons |
| 5 – Betrieb | GitHub-Pages-Workflow entfernt (privates Repo). Offen: Deployment auf eigenen Server |

Bekannte Lücken:

- VMangos-Loot: Nur direkte Loot-Einträge, keine Referenz-Tabellen. Allgemeine Welt-Drops
  fehlen deshalb bei NPCs bewusst.
- Zauberbeschreibungen: Nur `$s1`–`$s3` werden aufgelöst, andere Platzhalter erscheinen als „X“.
- Forever-Quests ohne VMangos-Gegenstück haben keine Beschreibungs- und Abschlusstexte.
