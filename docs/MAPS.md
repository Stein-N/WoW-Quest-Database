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

## Dungeons und Raids

Die Classic-Clients enthalten die Kartengrafiken der Instanzen, verknüpfen sie aber nicht in
ihren UiMap-Tabellen. Die Zuordnung (uiMapId → Ebenen → Kacheln) kommt deshalb aus den
Retail-Tabellen von wago.tools (zwischengespeichert in `build/wago/`). Die Kacheln selbst
stammen aus dem lokalen Client. Eine Ebene wird nur geschrieben, wenn der Client alle ihre
Kacheln hat.

Ausgewählt werden die Instanzen aus `web/static/data/<flavor>/zones.json`, in denen es NPCs
oder Objekte gibt. Deshalb vorher `make data` ausführen. Ergebnis: 31 Instanzen bei Classic
(die alte Scholomance-Karte fehlt im Classic-Era-Client) und 32 bei Forever.

Die Instanzkarten sind reine Bilder. QuestieDB hat in Instanzen keine Koordinaten (`-1, -1`).
Sie stehen in `index.json` unter `instances` und nicht unter `maps`. Die Webseite zeigt
Instanz-Spawns nur dann am Eingang auf der Außenkarte, wenn die Instanz nicht unter `maps` steht.

Ausgabe in `web/static/maps/<flavor>/`:

- `<uiMapId>.webp`: komplett erkundet, ohne Nebel (Standard auf der Seite)
- `<uiMapId>-fog.webp`: unerkundet, nur die Basiskarte (Umschalter „Fog of war“ unter der Karte)
- `<uiMapId>.webp` je Instanzebene (ohne `-fog`-Variante)
- `index.json`: Liste der vorhandenen Karten (`maps`), Instanzen mit ihren Ebenen
  (`instances`: `{"<uiMapId der Instanz>": [{"uiMapId", "name"}, …]}`) und Client-Version

Die Bilder sind im Repository eingecheckt. Das Repository ist privat, denn es handelt sich
um Blizzard-Artwork. Nach einem erneuten `make maps` die geänderten Dateien committen.

## Hinweise

- Die Beschriftungen kommen aus der Textsprache des Clients. Die eingecheckten Karten sind
  **englisch** (enUS). Vor `make maps` im Battle.net-Launcher die Textsprache auf Englisch
  lassen, sonst werden die Karten in einer anderen Sprache beschriftet.
- Spawns in Instanzen erscheinen auf der Webseite weiterhin am Instanzeingang auf der Außenkarte.
