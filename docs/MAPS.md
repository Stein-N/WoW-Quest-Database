# Kartenbilder

```sh
make maps
# oder mit anderem Pfad / Produkt:
make maps WOW_DIR="/pfad/zu/World of Warcraft" PRODUCT=wow_classic_era
```

`etl/maps.py` liest die Kartengrafiken direkt aus dem CASC-Speicher der lokalen
WoW-Installation. Das ist dieselbe Datenquelle, die auch wow.export öffnet. wow.export selbst
ist eine reine GUI-App ohne Kommandozeile. Deshalb gibt es hier einen kleinen eigenen
Reader (`etl/casc.py`, `etl/db2.py`). Das Skript arbeitet so:

1. Es liest die Client-Tabellen `UiMapXMapArt` und `UiMapArtTile`, also welche Kacheln zu
   welcher UiMap gehören.
2. Es lädt die BLP-Kacheln und setzt sie zusammen. Pillow dekodiert BLP.
3. Es schneidet auf den sichtbaren Kartenbereich zu (1002×668, aus `UiMapArtStyleLayer`).
4. Es schreibt `web/static/maps/<uiMapId>.webp` und eine `index.json`.

Die Bilder sind Blizzard-Artwork und stehen deshalb in `.gitignore`.

## Aktueller Stand

- Quelle: `wow_classic_beta` 1.60.1, das ist der **Forever-Client**. Er enthält 60 Karten:
  alle Zonen, die Hauptstädte, die Kontinente, die Schlachtfelder und die neuen Forever-Zonen.
- Die Beschriftungen sind **deutsch**, weil der Client mit deutschen Texten installiert ist.
  Für englische Karten müsste man im Battle.net-Launcher die Textsprache auf Englisch stellen
  und danach `make maps` erneut ausführen.
- **Classic Era** nutzt dieselben Bilder. Bei vier Zonen weicht die Forever-Karte von Era ab
  (Mulgore, Östliche Pestländer, Rotkammgebirge, Sturmwind). Für diese rechnet die Seite die
  Classic-Koordinaten mit den Koeffizienten aus QuestieDBs `conversion.json` um
  (`index.json` → `transforms.classic`). Ist ein Era-Client installiert, erzeugt
  `PRODUCT=wow_classic_era` stattdessen exakte Era-Karten. Pro Flavor getrennte Bildsätze
  sind dann noch nicht vorgesehen.
- Dungeons haben im Client keine Kartengrafik. Spawns in Instanzen erscheinen deshalb am
  Instanzeingang auf der Außenkarte.

## Hosting

Der GitHub-Pages-Workflow baut ohne Karten, weil die Bilder nicht im Repository liegen. Für
den eigenen Server reicht `make maps build`. Danach `web/build/` hochladen.
