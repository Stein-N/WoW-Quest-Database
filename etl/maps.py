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

Dungeons and raids: the Classic clients ship the instance map textures but do not link them
in their UiMap tables. The links (uiMapId -> floors -> tiles) come from the retail tables on
wago.tools instead; a floor is written only when the local client has all of its tiles. These
are plain images (QuestieDB has no coordinates inside instances), listed separately under
"instances" in index.json: {"<uiMapId of the instance>": [{"uiMapId": .., "name": ..}, ...]}.
"""

import argparse
import csv
import io
import json
import urllib.request
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

# Retail client tables (CSV) that link instance maps to their floors and tiles.
WAGO_CSV = "https://wago.tools/db2/{}/csv"
WAGO_CACHE = ROOT / "build" / "wago"

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


def wago_table(name):
    path = WAGO_CACHE / f"{name}.csv"
    if not path.exists():
        WAGO_CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(WAGO_CSV.format(name), headers={"User-Agent": "WoW-Quest-Database"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path.write_bytes(resp.read())
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: int(v) if v.lstrip("-").isdigit() else v for k, v in r.items()} for r in csv.DictReader(f)]


class InstanceArt(MapArt):
    """Instance (dungeon/raid) maps: retail table links, textures from the local client."""

    def __init__(self, casc):
        self.casc = casc
        self._textures = {}
        self.art_for_map = {}
        for r in sorted(wago_table("UiMapXMapArt"), key=lambda r: r["PhaseID"]):
            self.art_for_map.setdefault(r["UiMapID"], r["UiMapArtID"])
        self.tiles_for_art = {}
        for r in wago_table("UiMapArtTile"):
            if r["LayerIndex"] == 0:
                self.tiles_for_art.setdefault(r["UiMapArtID"], []).append(
                    (r["RowIndex"], r["ColIndex"], r["FileDataID"]))
        self.arts = {r["ID"]: [0, 0, r["UiMapArtStyleID"]] for r in wago_table("UiMapArt")}
        self.styles = {r["UiMapArtStyleID"]: [0, r["LayerWidth"], r["LayerHeight"]]
                       for r in wago_table("UiMapArtStyleLayer") if r["LayerIndex"] == 0}
        self.overlays_for_art = {}
        self.names = {r["ID"]: r["Name_lang"] for r in wago_table("UiMap")}
        self.floors = {}  # uiMapId -> [(floor index, uiMapId, floor name)] of its group
        groups = {}
        for r in wago_table("UiMapGroupMember"):
            groups.setdefault(r["UiMapGroupID"], []).append((r["FloorIndex"], r["UiMapID"], r["Name_lang"]))
        for members in groups.values():
            for _, ui_map, _ in members:
                self.floors[ui_map] = sorted(members)

    def available(self, ui_map):
        """True when the local client has every tile of the map."""
        tiles = self.tiles_for_art.get(self.art_for_map.get(ui_map), [])
        try:
            return bool(tiles) and all(self.texture(fdid) for _, _, fdid in tiles)
        except Exception:
            return False


def instance_maps(flavor):
    """uiMapIds of the instances the site has NPCs or objects in (build.py output).

    QuestieDB's dungeon list also holds the later expansions' instances; the spawns limit it
    to the ones that exist in the flavor."""
    data = ROOT / "web" / "static" / "data" / flavor
    if not (data / "zones.json").exists():
        print(f"  {data / 'zones.json'} missing (make data first), no instance maps")
        return []
    zones = json.loads((data / "zones.json").read_text())["zones"]
    spawned = set()
    for shard in [*(data / "npc").glob("*.json"), *(data / "object").glob("*.json")]:
        for entity in json.loads(shard.read_text()).values():
            if isinstance(entity, dict):
                spawned.update((entity.get("spawns") or {}).keys())
    return sorted({z["uiMapId"] for area, z in zones.items()
                   if z.get("instance") and z.get("uiMapId") and area in spawned})


def write_instances(casc, flavor, out, outdoor):
    art = InstanceArt(casc)
    instances, missing = {}, []
    for ui_map in instance_maps(flavor):
        if ui_map in outdoor:  # battlegrounds have world map art of their own
            continue
        floors = art.floors.get(ui_map) or [(0, ui_map, art.names.get(ui_map, ""))]
        written = []
        for _, floor_map, name in floors:
            if not art.available(floor_map):
                continue
            explored, _ = art.render(floor_map)
            explored.save(out / f"{floor_map}.webp", "WEBP", quality=82, method=6)
            written.append({"uiMapId": floor_map, "name": name or art.names.get(floor_map, "")})
        if written:
            instances[str(ui_map)] = written
        else:
            missing.append(ui_map)
    floors = sum(len(f) for f in instances.values())
    print(f"wrote {len(instances)} instance maps ({floors} floors) to {out}")
    for ui_map in missing:
        print(f"  no instance art for {ui_map} {art.names.get(ui_map, '')}")
    return instances


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

    index = {"source": f"{args.product} {casc.version}", "maps": written,
             "instances": write_instances(casc, args.flavor, out, set(written))}
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"wrote {len(written)} maps to {out}")
    for ui_map, reason in failed:
        print(f"  skipped {ui_map}: {reason}")


if __name__ == "__main__":
    main()
