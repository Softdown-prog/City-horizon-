"""Prepare supplied City Horizon UI reference art for the SDL runtime.

The loading image is a full-screen composition, while the existing RGBA atlas
contains independent category buttons. This tool copies only those authored
regions into canonical UI assets; it does not invent labels or redraw art.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ATLAS_BUTTONS = {
    "category_buildings.png": (700, 792, 951, 894),
    "category_roads.png": (958, 792, 1210, 894),
    "category_agriculture.png": (1217, 792, 1491, 894),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("loading_source", type=Path, help="supplied 1280x906 loading composition")
    parser.add_argument("--atlas", type=Path, default=Path("assets/ui/loading/loading_ui_sheet.png"))
    parser.add_argument("--assets", type=Path, default=Path("assets/ui"))
    args = parser.parse_args()

    with Image.open(args.loading_source) as source:
        if source.size != (1280, 906):
            parser.error(f"loading source is {source.width}x{source.height}; expected 1280x906")
        loading = source.convert("RGBA")
    loading_dir = args.assets / "loading"
    chrome_dir = args.assets / "chrome"
    loading_dir.mkdir(parents=True, exist_ok=True)
    chrome_dir.mkdir(parents=True, exist_ok=True)
    loading.save(loading_dir / "city_horizon_loading.png", "PNG", optimize=True)

    with Image.open(args.atlas) as atlas_source:
        atlas = atlas_source.convert("RGBA")
        if atlas.size != (1491, 1055):
            parser.error(f"UI atlas is {atlas.width}x{atlas.height}; expected 1491x1055")
        for name, bounds in ATLAS_BUTTONS.items():
            atlas.crop(bounds).save(chrome_dir / name, "PNG", optimize=True)
    print("prepared loading composition and 3 canonical category buttons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
