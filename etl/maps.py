"""Extracts the world map images from a local WoW installation into web/static/maps/.

    python3 etl/maps.py [--wow-dir DIR] [--product wow_classic_beta]

Reads the game's CASC storage directly, as wow.export does, so no manual export is needed:
the UiMapXMapArt / UiMapArtTile client tables give the tile textures (BLP) of every map,
which are stitched and cropped to the map frame QuestieDB's percent coordinates refer to.

Writes <uiMapId>.webp plus index.json, which lists the available maps and, for flavors whose
coordinates use a different map frame than the extracted art, the linear transforms from
QuestieDB's Forever conversion (Era coordinates -> Forever art).
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
UI_MAP_ART = 1957202          # fields: HighlightFileDataID, HighlightAtlasID, UiMapArtStyleID
UI_MAP_ART_STYLE_LAYER = 1957208  # fields: ..., LayerWidth, LayerHeight, TileWidth, TileHeight; rel: style
UI_MAP_ART_TILE = 1957210     # fields: RowIndex, ColIndex, LayerIndex, FileDataID; rel: UiMapArtID
UI_MAP_X_MAP_ART = 1957217    # fields: PhaseID, UiMapArtID; rel: UiMapID

# Output frame shared by all maps (QuestieDB coordinates are percent of the visible area).
OUT_W, OUT_H = 1002, 668

# Which product the art comes from, keyed by site flavor that matches it 1:1.
ART_FLAVOR = {"wow_classic_beta": "forever", "wow_classic_era": "classic"}


def load_tables(casc):
    xmap = read_wdc5(casc.read_fdid(UI_MAP_X_MAP_ART))
    tiles = read_wdc5(casc.read_fdid(UI_MAP_ART_TILE))
    arts = {r["id"]: r for r in read_wdc5(casc.read_fdid(UI_MAP_ART))}
    styles = {r["relation"]: r for r in read_wdc5(casc.read_fdid(UI_MAP_ART_STYLE_LAYER))}
    art_for_map = {}
    for r in sorted(xmap, key=lambda r: r["fields"][0]):  # phase 0 first
        art_for_map.setdefault(r["relation"], r["fields"][1])
    tiles_for_art = {}
    for r in tiles:
        row, col, layer, fdid = r["fields"]
        if layer == 0:
            tiles_for_art.setdefault(r["relation"], []).append((row, col, fdid))
    return art_for_map, tiles_for_art, arts, styles


def stitch(casc, tiles, layer_w, layer_h):
    images = {}
    for row, col, fdid in tiles:
        images[(row, col)] = Image.open(io.BytesIO(casc.read_fdid(fdid))).convert("RGB")
    tw, th = next(iter(images.values())).size
    rows = max(r for r, _ in images) + 1
    cols = max(c for _, c in images) + 1
    canvas = Image.new("RGB", (cols * tw, rows * th))
    for (row, col), img in images.items():
        canvas.paste(img, (col * tw, row * th))
    canvas = canvas.crop((0, 0, min(layer_w, canvas.width), min(layer_h, canvas.height)))
    if canvas.size != (OUT_W, OUT_H):
        canvas = canvas.resize((OUT_W, OUT_H), Image.LANCZOS)
    return canvas


def era_to_forever_transforms():
    path = ROOT / "vendor" / "QuestieDB" / "data" / "Forever" / "conversion.json"
    data = json.loads(path.read_text())
    out = {}
    for t in data["geometry"]["transforms"]:
        if t["changed"]:
            k = t["coefficients"]
            out[str(t["ui_map_id"])] = [k["scale_x"], k["offset_x"], k["scale_y"], k["offset_y"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wow-dir", type=Path, default=DEFAULT_WOW)
    ap.add_argument("--product", default="wow_classic_beta")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "static" / "maps")
    args = ap.parse_args()

    casc = LocalCasc(args.wow_dir, args.product)
    print(f"{args.product} {casc.version}")
    art_for_map, tiles_for_art, arts, styles = load_tables(casc)
    args.out.mkdir(parents=True, exist_ok=True)

    written, failed = [], []
    for ui_map, art_id in sorted(art_for_map.items()):
        tiles = tiles_for_art.get(art_id)
        if not tiles:
            failed.append((ui_map, "no tiles"))
            continue
        style_id = arts.get(art_id, {}).get("fields", [0, 0, 0])[2]
        style = styles.get(style_id)
        layer_w, layer_h = (style["fields"][1], style["fields"][2]) if style else (OUT_W, OUT_H)
        try:
            image = stitch(casc, tiles, layer_w, layer_h)
        except KeyError as e:
            failed.append((ui_map, str(e)))
            continue
        image.save(args.out / f"{ui_map}.webp", "WEBP", quality=82, method=6)
        written.append(ui_map)

    art_flavor = ART_FLAVOR.get(args.product)
    index = {
        "source": f"{args.product} {casc.version}",
        "maps": written,
        # Coordinates of these flavors must be transformed before drawing on this art:
        # [scaleX, offsetX, scaleY, offsetY] per uiMapId.
        "transforms": {"classic": era_to_forever_transforms()} if art_flavor == "forever" else {},
    }
    (args.out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"wrote {len(written)} maps to {args.out}")
    for ui_map, reason in failed:
        print(f"  skipped {ui_map}: {reason}")


if __name__ == "__main__":
    main()
