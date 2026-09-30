#!/usr/bin/env python3
"""Deterministic 48x64 drawing CLI for CH Character Studio."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAME = (48, 64)
CONTRACT = "CH_CHARACTER_DRAW_RECIPE_V0"
ART_LAYERS = {
    "silhouette", "skin", "hair", "face", "upper_clothing", "lower_clothing",
    "footwear", "accessories_back", "accessories_front", "paint_over", "outline"
}
MASK_BANKS = {"appearance", "clothing", "held_object"}
CHANNEL_RGB = {"R": (255, 0, 0, 255), "G": (0, 255, 0, 255), "B": (0, 0, 255, 255)}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_color(value: str) -> tuple[int, int, int, int]:
    raw = str(value).lstrip("#")
    if len(raw) not in {6, 8}:
        raise ValueError(f"invalid color: {value}")
    rgb = tuple(int(raw[i:i+2], 16) for i in (0, 2, 4))
    alpha = int(raw[6:8], 16) if len(raw) == 8 else 255
    return rgb + (alpha,)


def scale_box(box: list[int] | tuple[int, ...], scale: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = map(int, box)
    return (x0 * scale, y0 * scale, (x1 + 1) * scale - 1, (y1 + 1) * scale - 1)


def draw_op(draw: ImageDraw.ImageDraw, op: dict, mask_mode: bool = False, scale: int = 1) -> None:
    kind = op.get("type")
    color = CHANNEL_RGB.get(op.get("channel")) if mask_mode else parse_color(op.get("color", "#FFFFFF"))
    if mask_mode and color is None:
        raise ValueError("mask operation requires channel R/G/B")
    if kind == "pixel":
        x, y = int(op["x"]), int(op["y"])
        if scale == 1:
            draw.point((x, y), fill=color)
        else:
            draw.rectangle((x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1), fill=color)
    elif kind == "rect":
        draw.rectangle(scale_box(op["box"], scale), fill=color)
    elif kind == "ellipse":
        draw.ellipse(scale_box(op["box"], scale), fill=color)
    elif kind == "polygon":
        points = [(int(x) * scale, int(y) * scale) for x, y in op["points"]]
        draw.polygon(points, fill=color)
    elif kind == "line":
        points = [(int(x) * scale, int(y) * scale) for x, y in op["points"]]
        draw.line(points, fill=color, width=max(1, int(op.get("width", 1)) * scale), joint="curve")
    else:
        raise ValueError(f"unsupported primitive: {kind}")


def downsample_premultiplied(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize RGBA without straight-alpha color fringes around transparent edges."""
    rgba = image.convert("RGBA")
    r, g, b, a = rgba.split()
    premultiplied = Image.merge("RGBA", (
        ImageChops.multiply(r, a),
        ImageChops.multiply(g, a),
        ImageChops.multiply(b, a),
        a,
    )).resize(size, Image.Resampling.LANCZOS)

    pr, pg, pb, pa = premultiplied.split()
    pr_data = list(pr.getdata())
    pg_data = list(pg.getdata())
    pb_data = list(pb.getdata())
    a_data = list(pa.getdata())
    out = bytearray(len(a_data) * 4)
    for i, alpha in enumerate(a_data):
        p = i * 4
        if alpha <= 0:
            out[p:p+4] = bytes((0, 0, 0, 0))
            continue
        out[p] = min(255, round(pr_data[i] * 255 / alpha))
        out[p+1] = min(255, round(pg_data[i] * 255 / alpha))
        out[p+2] = min(255, round(pb_data[i] * 255 / alpha))
        out[p+3] = alpha
    return Image.frombytes("RGBA", size, bytes(out))


def validate_recipe(recipe: dict) -> None:
    if recipe.get("contract") != CONTRACT:
        raise ValueError(f"contract must be {CONTRACT}")
    if recipe.get("frameSize", list(FRAME)) != list(FRAME):
        raise ValueError("frameSize must be [48,64]")
    target = recipe.get("target") or {}
    kind = target.get("kind")
    if kind == "artLayer":
        if target.get("name") not in ART_LAYERS:
            raise ValueError(f"unknown art layer: {target.get('name')}")
    elif kind == "maskBank":
        if target.get("name") not in MASK_BANKS:
            raise ValueError(f"unknown mask bank: {target.get('name')}")
    else:
        raise ValueError("target.kind must be artLayer or maskBank")
    if not isinstance(recipe.get("operations"), list):
        raise ValueError("operations must be an array")
    supersample = recipe.get("supersample", 1)
    if not isinstance(supersample, int) or not 1 <= supersample <= 8:
        raise ValueError("supersample must be an integer from 1 to 8")
    if kind == "maskBank" and supersample != 1:
        raise ValueError("maskBank recipes must use supersample=1 to keep RGB channels exact")


def render(recipe: dict, seed: int) -> Image.Image:
    validate_recipe(recipe)
    rng = random.Random(seed)
    mask_mode = recipe["target"]["kind"] == "maskBank"
    supersample = 1 if mask_mode else int(recipe.get("supersample", 1))
    working_frame = (FRAME[0] * supersample, FRAME[1] * supersample)
    image = Image.new("RGBA", working_frame, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for raw in recipe["operations"]:
        op = dict(raw)
        jitter = int(op.pop("jitterPx", 0) or 0)
        if jitter:
            dx, dy = rng.randint(-jitter, jitter), rng.randint(-jitter, jitter)
            if "x" in op: op["x"] = int(op["x"]) + dx
            if "y" in op: op["y"] = int(op["y"]) + dy
            if "box" in op:
                x0, y0, x1, y1 = map(int, op["box"])
                op["box"] = [x0 + dx, y0 + dy, x1 + dx, y1 + dy]
            if "points" in op:
                op["points"] = [[int(x) + dx, int(y) + dy] for x, y in op["points"]]
        draw_op(draw, op, mask_mode=mask_mode, scale=supersample)
    if supersample > 1:
        image = downsample_premultiplied(image, FRAME)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    try:
        recipe_path = args.recipe if args.recipe.is_absolute() else (REPO_ROOT / args.recipe).resolve()
        out_path = args.out if args.out.is_absolute() else (REPO_ROOT / args.out).resolve()
        recipe = load_json(recipe_path)
        image = render(recipe, args.seed)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path, optimize=False, compress_level=9)
        digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
        payload = {
            "contract": "CH_CHARACTER_DRAW_REPORT_V0",
            "status": "ok",
            "seed": args.seed,
            "target": recipe["target"],
            "frameSize": list(FRAME),
            "supersample": int(recipe.get("supersample", 1)),
            "alphaDownsample": "premultiplied_lanczos" if int(recipe.get("supersample", 1)) > 1 else "none",
            "output": str(out_path),
            "sha256": digest
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.stdout.write(json.dumps({"contract":"CH_CHARACTER_DRAW_REPORT_V0","status":"error","message":str(exc)}, indent=2) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
