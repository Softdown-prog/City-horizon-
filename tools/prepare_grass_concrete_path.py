"""Create a CH_MASK_V1 concrete-path terrain pilot from the canonical grass tile.

No cement is painted or generated here.  The approved seamless concrete sidewalk
is resampled as material; CH_MASK_V1 owns the grass tile alpha and output audit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.asset_masks.apply_mask_variant import process_mask_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path, help="Runtime root, e.g. build/Debug")
    args = parser.parse_args()
    root = args.asset_root
    grass_path = root / "assets" / "terrain" / "grass_isometric_01.png"
    concrete_path = root / "assets" / "sidewalks" / "concrete_01" / "sidewalk_concrete_15_seamless.png"
    if not grass_path.is_file() or not concrete_path.is_file():
        raise FileNotFoundError("Canonical grass or approved concrete sidewalk asset is missing")

    work = root / "assets" / "definitions" / "masks" / "grass_concrete_path"
    output = root / "assets" / "terrain" / "paths"
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    grass = Image.open(grass_path).convert("RGBA")
    # The source is a 2:1 seamless concrete surface.  Preserve its art while
    # normalizing its material canvas to the grass source's texture domain.
    material = Image.open(concrete_path).convert("RGBA").resize(grass.size, Image.Resampling.LANCZOS)
    material_pixels = material.load()
    for y in range(material.height):
        for x in range(material.width):
            red, green, blue, alpha = material_pixels[x, y]
            # CH_MASK_V1 texture sampling uses RGB; never allow transparent
            # source padding to inject black into the concrete path.
            if alpha == 0:
                material_pixels[x, y] = (184, 184, 178, 255)
    base_name = "grass_isometric_01_base.png"
    material_name = "concrete_sidewalk_material.png"
    mask_name = "grass_surface_semantic_mask.png"
    grass.save(work / base_name, format="PNG")
    material.save(work / material_name, format="PNG")

    mask = Image.new("L", grass.size, 0)
    alpha = grass.getchannel("A")
    mask.paste(1, mask=alpha.point(lambda value: 255 if value > 0 else 0))
    mask.save(work / mask_name, format="PNG")

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "grass_to_concrete_path_01",
        "base": base_name,
        "semanticMask": mask_name,
        "regions": {"ground_surface": 1},
        "variants": [{
            "id": "concrete_path",
            "region_recipes": {
                "ground_surface": {
                    "mode": "texture",
                    "texture": material_name,
                    "textureSpace": "tile",
                    "scale": 1.0,
                    "offset": [0.0, 0.0],
                    "preserveShading": False,
                }
            }
        }]
    }
    manifest_path = work / "grass_to_concrete_path_01.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    pngs, sidecars = process_mask_manifest(str(manifest_path), str(output))
    print(json.dumps({"contract": "CH_MASK_V1", "asset": pngs[0], "sidecar": sidecars[0]}, indent=2))


if __name__ == "__main__":
    main()
