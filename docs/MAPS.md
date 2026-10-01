# Kartenbilder

```sh
make maps                                     # beide Clients
make maps WOW_DIR="/pfad/zu/World of Warcraft"
```

`etl/maps.py` liest die Kartengrafiken direkt aus dem CASC-Speicher der lokalen
WoW-Installation. Das ist dieselbe Datenquelle, die auch wow.export öffnet. wow.export selbst
ist eine reine GUI-App ohne Kommandozeile. Deshalb gibt es hier einen kleinen eigenen
Reader (`etl/casc.py`, `etl/db2.py`).

| Flavor | Client | Karten |
| --- | --- | --- |
| `classic` | `wow_classic_era` (`_classic_era_`) | 54 |
| `forever` | `wow_classic_beta` (`_classic_beta_`) | 60 (inkl. neuer Forever-Zonen) |

So entsteht jede Karte:

1. `UiMapXMapArt` und `UiMapArtTile` liefern die Basiskacheln einer UiMap, also den
   **unerkundeten** Look.
2. `WorldMapOverlay` und `WorldMapOverlayTile` liefern die Detailtexturen, die das Spiel bei
   der Erkundung aufdeckt. Sie werden an ihrer Position über die Basis gelegt.
3. Das Ergebnis wird auf den sichtbaren Kartenbereich zugeschnitten (1002×668). Auf diesen
   Bereich beziehen sich die Prozent-Koordinaten von QuestieDB.

Ausgabe in `web/static/maps/<flavor>/`:

- `<uiMapId>.webp`: komplett erkundet, ohne Nebel (Standard auf der Seite)
- `<uiMapId>-fog.webp`: unerkundet, nur die Basiskarte (Umschalter „Fog of war“ unter der Karte)
- `index.json`: Liste der vorhandenen Karten und Client-Version

Die Bilder sind im Repository eingecheckt. Das Repository ist privat, denn es handelt sich
um Blizzard-Artwork. Nach einem erneuten `make maps` die geänderten Dateien committen.

## Hinweise

- Die Beschriftungen sind **deutsch**, weil beide Clients mit deutschen Texten installiert
  sind. Für englische Karten im Battle.net-Launcher die Textsprache auf Englisch stellen und
  `make maps` erneut ausführen.
- Dungeons haben im Client keine Kartengrafik. Spawns in Instanzen erscheinen deshalb am
  Instanzeingang auf der Außenkarte.
