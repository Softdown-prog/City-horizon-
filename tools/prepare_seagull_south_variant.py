"""Build the masked, mirrored South-bound seagull animation (CH_MASK_V1)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

# Allow direct execution from the repository root on Windows and CI.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.asset_masks.apply_mask_variant import process_mask_manifest


def semantic_mask(source: Image.Image) -> Image.Image:
    """Classify opaque bird pixels without ever assigning a mask over alpha 0."""
    rgba = source.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    source_pixels = rgba.load()
    mask_pixels = mask.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = source_pixels[x, y]
            if alpha == 0:
                continue
            # Preserve the warm beak/feet separately from the feather plumage.
            mask_pixels[x, y] = 2 if red >= 105 and green >= 75 and blue <= 105 else 1
    return mask


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    args = parser.parse_args()

    north_frames = args.asset_root / "assets" / "ambient" / "seagull_north" / "frames"
    mask_root = args.asset_root / "assets" / "definitions" / "masks" / "seagull_south"
    south_frames = args.asset_root / "assets" / "ambient" / "seagull_south" / "frames"
    mask_root.mkdir(parents=True, exist_ok=True)
    south_frames.mkdir(parents=True, exist_ok=True)

    output_frames: list[str] = []
    for frame_index in range(8):
        north_path = north_frames / f"flight_north_{frame_index:02d}.png"
        if not north_path.is_file():
            raise FileNotFoundError(f"Missing canonical North frame: {north_path}")

        asset_id = f"seagull_south_frame_{frame_index:02d}"
        base_name = f"{asset_id}_base.png"
        mask_name = f"{asset_id}_semantic_mask.png"
        manifest_name = f"{asset_id}_mask.json"
        base_path = mask_root / base_name
        mask_path = mask_root / mask_name
        manifest_path = mask_root / manifest_name

        mirrored = Image.open(north_path).convert("RGBA").transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        mirrored.save(base_path, format="PNG")
        semantic_mask(mirrored).save(mask_path, format="PNG")
        manifest = {
            "contract": "CH_MASK_V1",
            "assetId": asset_id,
            "base": base_name,
            "semanticMask": mask_name,
            "regions": {"plumage": 1, "beak_feet": 2},
            "variants": [{
                "id": "ocean_blue",
                "region_recipes": {
                    "plumage": {"mode": "recolor", "targetRGB": [76, 165, 210], "preserveShading": True},
                    "beak_feet": {"mode": "recolor", "targetRGB": [238, 176, 56], "preserveShading": True},
                },
            }],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        pngs, _ = process_mask_manifest(str(manifest_path), str(south_frames))
        if len(pngs) != 1:
            raise RuntimeError(f"Unexpected mask output count for frame {frame_index}: {len(pngs)}")
        output_frames.append("assets/ambient/seagull_south/frames/" + Path(pngs[0]).name)

    animation_manifest = {
        "id": "seagull_south",
        "clips": [{
            "id": "fly_south_calm",
            "state": "fly",
            "direction": "south",
            "fps": 3.5,
            "loop": True,
            "frames": output_frames,
        }],
    }
    animation_path = args.asset_root / "assets" / "definitions" / "animations" / "seagull_south.json"
    animation_path.parent.mkdir(parents=True, exist_ok=True)
    animation_path.write_text(json.dumps(animation_manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"contract": "CH_MASK_V1", "frames": len(output_frames), "manifest": str(animation_path)}))


if __name__ == "__main__":
    main()
