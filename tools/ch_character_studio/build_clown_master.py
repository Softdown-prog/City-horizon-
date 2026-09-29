#!/usr/bin/env python3
"""Build the approved-art candidate for clown_01 SOUTH/idle.

This builder deliberately owns appearance only. It does not touch CH Actor motion,
landmarks, runtime camera, ground anchor, or held-object sockets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from character_draw_cli import load_json, render

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAME = (48, 64)
ART_ROOT = Path(__file__).resolve().parent / "art" / "clown_01" / "south_idle"
ART_SUPERSAMPLE = 4
OUTLINE_ALPHA_THRESHOLD = 48
LAYER_RECIPES = [
    ("skin", "skin.recipe.json"),
    ("hair", "hair.recipe.json"),
    ("face", "face.recipe.json"),
    ("upper_clothing", "upper_clothing.recipe.json"),
    ("lower_clothing", "lower_clothing.recipe.json"),
    ("footwear", "footwear.recipe.json"),
    ("accessories_front", "accessories_front.recipe.json"),
]
MASK_RECIPES = [
    ("appearance", "appearance_mask.recipe.json"),
    ("clothing", "clothing_mask.recipe.json"),
    ("held_object", "held_object_mask.recipe.json"),
]
OUTLINE_RGBA = (31, 41, 55, 255)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alpha_union(images: list[Image.Image]) -> list[int]:
    coverage = [0] * (FRAME[0] * FRAME[1])
    for image in images:
        values = list(image.getchannel("A").getdata())
        for i, value in enumerate(values):
            if value >= OUTLINE_ALPHA_THRESHOLD:
                coverage[i] = 1
    return coverage


def make_outline(images: list[Image.Image]) -> Image.Image:
    w, h = FRAME
    coverage = alpha_union(images)
    outline = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    pixels = outline.load()
    neighbors = ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1))
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if coverage[i]:
                continue
            if any(0 <= x+dx < w and 0 <= y+dy < h and coverage[(y+dy)*w + (x+dx)] for dx,dy in neighbors):
                pixels[x, y] = OUTLINE_RGBA
    return outline


def checker_review(image: Image.Image, scale: int = 8) -> Image.Image:
    w, h = image.size
    bg = Image.new("RGBA", image.size, (45, 58, 65, 255))
    draw = ImageDraw.Draw(bg)
    cell = 4
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) & 1:
                draw.rectangle((x, y, min(x+cell-1, w-1), min(y+cell-1, h-1)), fill=(57, 73, 80, 255))
    bg.alpha_composite(image)
    return bg.resize((w * scale, h * scale), Image.Resampling.NEAREST)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("out/ch_character_studio/clown_01/south_idle"))
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else (REPO_ROOT / args.out_dir).resolve()
    layer_dir = out_dir / "layers"
    mask_dir = out_dir / "masks"
    layer_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    rendered_layers: list[Image.Image] = []
    outputs: dict[str, dict[str, str]] = {"layers": {}, "masks": {}}

    for name, filename in LAYER_RECIPES:
        recipe = load_json(ART_ROOT / filename)
        recipe["supersample"] = ART_SUPERSAMPLE
        image = render(recipe, args.seed)
        path = layer_dir / f"{name}.png"
        image.save(path, optimize=False, compress_level=9)
        rendered_layers.append(image)
        outputs["layers"][name] = sha256(path)

    outline = make_outline(rendered_layers)
    outline_path = layer_dir / "outline.png"
    outline.save(outline_path, optimize=False, compress_level=9)
    outputs["layers"]["outline"] = sha256(outline_path)

    composite = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    for image in rendered_layers:
        composite.alpha_composite(image)
    composite.alpha_composite(outline)
    composite_path = out_dir / "clown_01_s_idle.png"
    composite.save(composite_path, optimize=False, compress_level=9)

    for name, filename in MASK_RECIPES:
        recipe = load_json(ART_ROOT / filename)
        recipe["supersample"] = 1
        image = render(recipe, args.seed)
        path = mask_dir / f"{name}.png"
        image.save(path, optimize=False, compress_level=9)
        outputs["masks"][name] = sha256(path)

    review = checker_review(composite)
    review_path = out_dir / "clown_01_s_idle_review_8x.png"
    review.save(review_path, optimize=False, compress_level=9)

    report = {
        "contract": "CH_CHARACTER_MASTER_BUILD_V0",
        "status": "ok",
        "characterId": "clown_01",
        "direction": "S",
        "frame": "idle",
        "frameSize": list(FRAME),
        "groundAnchor": [24, 60],
        "seed": args.seed,
        "artSupersample": ART_SUPERSAMPLE,
        "maskSupersample": 1,
        "motionModified": False,
        "canonicalCameraModified": False,
        "composite": {"path": str(composite_path), "sha256": sha256(composite_path)},
        "review": {"path": str(review_path), "sha256": sha256(review_path)},
        **outputs,
    }
    report_path = out_dir / "master_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
