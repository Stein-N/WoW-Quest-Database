"""Extracts the world map images from a local WoW installation into web/static/maps/<flavor>/.

    python3 etl/maps.py --product wow_classic_era  --flavor classic
    python3 etl/maps.py --product wow_classic_beta --flavor forever

Reads the game's CASC storage directly, as wow.export does, so no manual export is needed.
The client tables give everything:

  UiMapXMapArt / UiMapArtTile          base map tiles of every UiMap (the unexplored look)
  WorldMapOverlay / WorldMapOverlayTile  the detail textures the game reveals on exploration

For each map two images are written, cropped to the frame QuestieDB's percent coordinates
refer to: <uiMapId>.webp with every overlay applied (no fog of war) and <uiMapId>-fog.webp
with the base art only. index.json lists the available maps.
"""

import argparse
import io
import json
from pathlib import Path

from PIL import Image

from casc import LocalCasc
from db2 import read_wdc5

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WOW = Path.home() / "Games/battlenet/drive_c/Program Files (x86)/World of Warcraft"

# FileDataIDs of the client tables (stable across builds).
WORLD_MAP_OVERLAY = 1134579       # ID, UiMapArtID, TextureWidth, TextureHeight, OffsetX, OffsetY, ...
UI_MAP_ART = 1957202              # HighlightFileDataID, HighlightAtlasID, UiMapArtStyleID
UI_MAP_ART_STYLE_LAYER = 1957208  # ..., LayerWidth, LayerHeight, TileWidth, TileHeight; rel: style
UI_MAP_ART_TILE = 1957210         # RowIndex, ColIndex, LayerIndex, FileDataID; rel: UiMapArtID
WORLD_MAP_OVERLAY_TILE = 1957212  # RowIndex, ColIndex, LayerIndex, FileDataID; rel: overlay
UI_MAP_X_MAP_ART = 1957217        # PhaseID, UiMapArtID; rel: UiMapID

# Output frame shared by all maps (QuestieDB coordinates are percent of the visible area).
OUT_W, OUT_H = 1002, 668


class MapArt:
    def __init__(self, casc):
        self.casc = casc
        self._textures = {}
        self.art_for_map = {}
        for r in sorted(read_wdc5(casc.read_fdid(UI_MAP_X_MAP_ART)), key=lambda r: r["fields"][0]):
            self.art_for_map.setdefault(r["relation"], r["fields"][1])  # phase 0 first
        self.tiles_for_art = self._tiles(UI_MAP_ART_TILE)
        self.arts = {r["id"]: r["fields"] for r in read_wdc5(casc.read_fdid(UI_MAP_ART))}
        self.styles = {r["relation"]: r["fields"] for r in read_wdc5(casc.read_fdid(UI_MAP_ART_STYLE_LAYER))}
        overlay_tiles = self._tiles(WORLD_MAP_OVERLAY_TILE)
        self.overlays_for_art = {}
        for r in read_wdc5(casc.read_fdid(WORLD_MAP_OVERLAY)):
            f = r["fields"]
            overlay = {"w": f[2], "h": f[3], "x": f[4], "y": f[5], "tiles": overlay_tiles.get(r["id"], [])}
            self.overlays_for_art.setdefault(f[1], []).append(overlay)

    def _tiles(self, fdid):
        out = {}
        for r in read_wdc5(self.casc.read_fdid(fdid)):
            row, col, layer, file_id = r["fields"]
            if layer == 0:
                out.setdefault(r["relation"], []).append((row, col, file_id))
        return out

    def texture(self, fdid):
        if fdid not in self._textures:
            self._textures[fdid] = Image.open(io.BytesIO(self.casc.read_fdid(fdid))).convert("RGBA")
        return self._textures[fdid]

    def layer_size(self, art_id):
        style = self.styles.get(self.arts.get(art_id, [0, 0, 0])[2])
        return (style[1], style[2]) if style else (OUT_W, OUT_H)

    def render(self, ui_map):
        """-> (explored, unexplored) images in the output frame."""
        art_id = self.art_for_map[ui_map]
        tiles = self.tiles_for_art.get(art_id)
        if not tiles:
            raise KeyError("no tiles")
        layer_w, layer_h = self.layer_size(art_id)
        tw, th = self.texture(tiles[0][2]).size
        base = Image.new("RGBA", (layer_w, layer_h))
        for row, col, fdid in tiles:
            base.paste(self.texture(fdid), (col * tw, row * th))
        explored = base.copy()
        for o in self.overlays_for_art.get(art_id, []):
            if not o["tiles"]:
                continue
            ow, oh = self.texture(o["tiles"][0][2]).size
            layer = Image.new("RGBA", (o["w"], o["h"]))
            for row, col, fdid in o["tiles"]:
                layer.paste(self.texture(fdid), (col * ow, row * oh))
            explored.alpha_composite(layer, (o["x"], o["y"]))
        return tuple(self._frame(img) for img in (explored, base))

    @staticmethod
    def _frame(img):
        img = img.convert("RGB")
        return img if img.size == (OUT_W, OUT_H) else img.resize((OUT_W, OUT_H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wow-dir", type=Path, default=DEFAULT_WOW)
    ap.add_argument("--product", required=True, help="e.g. wow_classic_era, wow_classic_beta")
    ap.add_argument("--flavor", required=True, help="site flavor the art belongs to")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "static" / "maps")
    args = ap.parse_args()

    casc = LocalCasc(args.wow_dir, args.product)
    print(f"{args.product} {casc.version} -> {args.flavor}")
    art = MapArt(casc)
    out = args.out / args.flavor
    out.mkdir(parents=True, exist_ok=True)

    written, failed = [], []
    for ui_map in sorted(art.art_for_map):
        try:
            explored, unexplored = art.render(ui_map)
        except KeyError as e:
            failed.append((ui_map, str(e)))
            continue
        explored.save(out / f"{ui_map}.webp", "WEBP", quality=82, method=6)
        unexplored.save(out / f"{ui_map}-fog.webp", "WEBP", quality=82, method=6)
        written.append(ui_map)

    index = {"source": f"{args.product} {casc.version}", "maps": written}
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"wrote {len(written)} maps to {out}")
    for ui_map, reason in failed:
        print(f"  skipped {ui_map}: {reason}")


if __name__ == "__main__":
    main()
