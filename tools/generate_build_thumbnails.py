"""Generate fixed-canvas build-catalog thumbnails from canonical world art.

The game keeps these PNGs separate from the large transparent world sprites:
they are UI presentation assets, never placement or render geometry.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS = ROOT / "assets" / "definitions"
OUTPUT = ROOT / "assets" / "ui" / "thumbnails" / "buildings"
CANVAS = (192, 128)
PADDING = 8


def source_sprite(definition: dict) -> Path | None:
    sprite = definition.get("texture")
    if not sprite and definition.get("levels"):
        sprite = definition["levels"][0].get("sprite")
    if not sprite:
        return None
    return ROOT / sprite


def build_thumbnail(definition_path: Path) -> bool:
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    # Catalog entries are only created for player-buildable objects.  Keep a
    # thumbnail for decor too because it uses the same card presentation.
    if not definition.get("playerBuildable", True):
        return False
    source = source_sprite(definition)
    if source is None or not source.is_file():
        print(f"skip {definition_path.name}: source sprite missing")
        return False

    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        print(f"skip {definition_path.name}: transparent source")
        return False
    image = image.crop(bounds)
    scale = min((CANVAS[0] - PADDING * 2) / image.width, (CANVAS[1] - PADDING * 2) / image.height)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    thumbnail = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    thumbnail.alpha_composite(resized, ((CANVAS[0] - resized.width) // 2, (CANVAS[1] - resized.height) // 2))
    thumbnail.save(OUTPUT / f"{definition['id']}.png", "PNG", optimize=True)
    return True


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    created = sum(build_thumbnail(path) for path in sorted(DEFINITIONS.glob("*.json")))
    print(f"generated {created} catalog thumbnails in {OUTPUT}")


if __name__ == "__main__":
    main()
