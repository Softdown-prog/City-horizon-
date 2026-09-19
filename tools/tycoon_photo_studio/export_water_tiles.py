"""Export Blender-baked water surfaces into canonical 128x64 terrain tiles."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

SIZE = (128, 64)
DIRECTIONS = ("south", "east", "west", "north")
OFFSETS = ((0, 0), (1, 0), (0, 1), (1, 1))

def diamond_mask():
    mask = Image.new("L", SIZE, 0)
    pixels = mask.load()
    for y in range(SIZE[1]):
        for x in range(SIZE[0]):
            if abs(x - 63.5) / 63.5 + abs(y - 31.5) / 31.5 <= 1.0:
                pixels[x, y] = 255
    return mask

MASK = diamond_mask()

def normalize(source):
    image = Image.open(source).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty Blender colour pass: {source}")
    crop = image.crop(bbox).resize(SIZE, Image.Resampling.LANCZOS)
    crop.putalpha(ImageChops.multiply(crop.getchannel("A"), MASK))
    return crop

def manifest(asset_id, variant, files):
    return {
        "contractVersion": "CH_TERRAIN_CONTRACT_V0", "status": "PILOT",
        "assetId": asset_id, "terrainType": "water", "variant": variant,
        "activeVariantSlot": 2, "worldSamplingSupported": True,
        "geometry": {"projection": "isometric_2_to_1", "logicalTileWidth": 128,
          "logicalTileHeight": 64, "ratio": 2, "canvasWidth": 128, "canvasHeight": 64,
          "marginHorizontalPx": 0, "alphaMask": "abs(x - 64) / 64 + abs(y - 32) / 32 <= 1.0"},
        "source": {"pipeline": "Blender 4.2.3 -> CH_TYCOON_STUDIO_V1 -> PNG",
          "surface": "subdivided zero-thickness plane", "sideWalls": False},
        "parameters": {"causticsIntensity": 0.35, "waveScale": 0.35, "glitterCount": 3,
          "noiseFactor": 0.18, "ripplesFactor": 0.65},
        "variants": files}

def write_family(source_dir, output_dir, stem, variant):
    records = []
    for direction, offset in zip(DIRECTIONS, OFFSETS, strict=True):
        image = normalize(source_dir / f"{stem}_{direction}_color_source.png")
        name = f"{variant}_{offset[0]}{offset[1]}.png"
        image.save(output_dir / name, optimize=True)
        records.append({"file": name, "offset": list(offset), "rotationSource": direction})
    return records

def review(output_dir):
    board = Image.new("RGBA", (640, 208), (30, 43, 50, 255))
    draw = ImageDraw.Draw(board)
    for row, variant in enumerate(("water_deep", "water_shallow")):
        for col, offset in enumerate(OFFSETS):
            image = Image.open(output_dir / f"{variant}_{offset[0]}{offset[1]}.png").convert("RGBA")
            board.alpha_composite(image, (col * 160 + 16, row * 104 + 8))
            draw.text((col * 160 + 16, row * 104 + 76), f"{variant} {offset[0]}{offset[1]}", fill=(226, 235, 240, 255))
    board.save(output_dir / "water_surface_3d_review.png", optimize=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep-source", type=Path, required=True)
    parser.add_argument("--shallow-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    deep = write_family(args.deep_source, args.output, "water_surface_deep_01", "water_deep")
    shallow = write_family(args.shallow_source, args.output, "water_surface_shallow_01", "water_shallow")
    (args.output / "ch_terrain_water_water_deep_manifest.json").write_text(json.dumps(manifest("ch_terrain_water_water_deep", "water_deep", deep), indent=2) + "\n", encoding="utf-8")
    (args.output / "ch_terrain_water_water_shallow_manifest.json").write_text(json.dumps(manifest("ch_terrain_water_water_shallow", "water_shallow", shallow), indent=2) + "\n", encoding="utf-8")
    review(args.output)
    print("waterTileExport: PASS")

if __name__ == "__main__":
    main()
