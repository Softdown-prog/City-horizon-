"""Prepare and validate the reusable four-state City Horizon button atlas.

The input is a single presentation sheet.  The script removes only an
edge-connected near-black matte, keeps the full fixed canvas, and rejects
missing sprite cells.  Runtime reads the adjacent JSON manifest rather than
guessing crop coordinates from image content.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from prepare_ui_overlay_asset import remove_exterior_black_matte


CANVAS = (1448, 1086)
FAMILIES = {
    "blue_wide": ((20, 90), 354, (354, 140)),
    "blue_wide_patterned": ((20, 236), 354, (354, 140)),
    "green_wide": ((20, 383), 354, (354, 142)),
    "red_wide": ((20, 535), 354, (354, 142)),
    "blue_compact": ((35, 688), 350, (330, 114)),
    "blue_circle": ((92, 810), 346, (224, 228)),
}


def validate_cells(image: Image.Image) -> None:
    alpha = image.getchannel("A")
    for name, (origin, step_x, size) in FAMILIES.items():
        for column, state in enumerate(("normal", "hover", "pressed", "disabled")):
            left = origin[0] + step_x * column
            top = origin[1]
            right = left + size[0]
            bottom = top + size[1]
            if right > image.width or bottom > image.height:
                raise ValueError(f"{name}/{state} is outside the fixed atlas canvas")
            if alpha.crop((left, top, right, bottom)).getbbox() is None:
                raise ValueError(f"{name}/{state} has no visible pixels")


def manifest() -> dict[str, object]:
    return {
        "schema": "city_horizon.ui_button_states.v1",
        "image": "button_states_v1.png",
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "columns": ["normal", "hover", "pressed", "disabled"],
        "families": {
            name: {"origin": list(origin), "stepX": step_x, "cell": list(size)}
            for name, (origin, step_x, size) in FAMILIES.items()
        },
        "rules": {
            "active": "uses pressed column",
            "disabled": "always uses disabled column",
            "background": "RGBA transparency; no matte",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--manifest", type=Path, help="defaults beside destination")
    args = parser.parse_args()

    with Image.open(args.source) as source:
        if source.size != CANVAS:
            parser.error(f"source is {source.width}x{source.height}; expected {CANVAS[0]}x{CANVAS[1]}")
        prepared = remove_exterior_black_matte(source)
    try:
        validate_cells(prepared)
    except ValueError as error:
        parser.error(str(error))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(args.destination, "PNG", optimize=True)
    manifest_path = args.manifest or args.destination.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest(), indent=2) + "\n", encoding="utf-8")
    print(f"prepared {args.destination}: canvas={CANVAS[0]}x{CANVAS[1]}, 24 four-state button cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
