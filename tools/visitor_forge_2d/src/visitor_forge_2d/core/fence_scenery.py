"""Deterministic reference-inspired modular park fence for City Horizon.

The generator draws original 2D geometry from recipe parameters. It does not
sample or trace source-image pixels. Runtime promotion remains a separate gate.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .exporter import alpha_safe_resize

CONTRACT = "CH_2D_FENCE_SCENERY_V1"
SCALE = 4
DIRECTIONS = {
    "east": (64.0, 32.0),
    "south": (-64.0, 32.0),
}


def _color(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"{label} must be #RRGGBB")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    except ValueError as exc:
        raise ValueError(f"{label} must be #RRGGBB") from exc


def _number(value: object, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return result


def validate_recipe(recipe: dict) -> dict:
    if not isinstance(recipe, dict) or recipe.get("contract") != CONTRACT:
        raise ValueError(f"Fence recipe must declare {CONTRACT}")
    if recipe.get("camera") != {
        "contract": "CH_CAMERA_V1",
        "tile": [128, 64],
        "yawDeg": 45,
        "elevationDeg": 30,
    }:
        raise ValueError("Fence scenery requires exact CH_CAMERA_V1")
    if recipe.get("canvas") != [192, 128] or recipe.get("anchor") != [96, 64]:
        raise ValueError("V1 fence modules require canvas [192,128] and anchor [96,64]")
    geom = recipe.get("geometry")
    palette = recipe.get("palette")
    if not isinstance(geom, dict) or not isinstance(palette, dict):
        raise ValueError("Fence recipe requires geometry and palette objects")
    checked = {
        "height": _number(geom.get("heightPx"), "heightPx", 16, 48),
        "base_width": _number(geom.get("stoneBaseWidthPx"), "stoneBaseWidthPx", 3, 14),
        "bar_spacing": _number(geom.get("barSpacingPx"), "barSpacingPx", 5, 20),
        "post_width": _number(geom.get("postWidthPx"), "postWidthPx", 2, 10),
        "rail_width": _number(geom.get("railWidthPx"), "railWidthPx", 1, 8),
    }
    for key in ("metal", "metalHighlight", "metalShadow", "stone", "stoneHighlight",
                "stoneShadow", "groundShadow"):
        checked[key] = _color(palette.get(key), f"palette.{key}")
    return checked


def _pt(point: tuple[float, float]) -> tuple[int, int]:
    return round(point[0] * SCALE), round(point[1] * SCALE)


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]],
          fill: tuple[int, int, int, int], width: float) -> None:
    draw.line([_pt(point) for point in points], fill=fill,
              width=max(1, round(width * SCALE)), joint="curve")


def _ellipse(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float],
             fill: tuple[int, int, int, int]) -> None:
    draw.ellipse(tuple(round(value * SCALE) for value in box), fill=fill)


def _draw_post(draw: ImageDraw.ImageDraw, point: tuple[float, float], cfg: dict) -> None:
    x, y = point
    height = cfg["height"]
    width = cfg["post_width"]
    _line(draw, [(x, y - 2), (x, y - height - 5)], cfg["metalShadow"], width + 2)
    _line(draw, [(x, y - 2), (x, y - height - 5)], cfg["metal"], width)
    _line(draw, [(x - 0.7, y - 3), (x - 0.7, y - height - 4)], cfg["metalHighlight"], 0.8)
    radius = max(2.0, width * 0.7)
    _ellipse(draw, (x - radius, y - height - 9, x + radius, y - height - 3), cfg["metalShadow"])
    _ellipse(draw, (x - radius + 1, y - height - 8, x + radius - 1, y - height - 4), cfg["metalHighlight"])


def _draw_regular_segment(draw: ImageDraw.ImageDraw, p0: tuple[float, float],
                          p1: tuple[float, float], cfg: dict) -> None:
    height = cfg["height"]
    base = cfg["base_width"]
    _line(draw, [(p0[0] + 3, p0[1] + 4), (p1[0] + 3, p1[1] + 4)],
          (*cfg["groundShadow"][:3], 70), base + 3)
    _line(draw, [p0, p1], cfg["stoneShadow"], base + 3)
    _line(draw, [p0, p1], cfg["stone"], base)
    _line(draw, [(p0[0], p0[1] - 2), (p1[0], p1[1] - 2)], cfg["stoneHighlight"], 2)
    top0, top1 = (p0[0], p0[1] - height), (p1[0], p1[1] - height)
    low0, low1 = (p0[0], p0[1] - height * 0.35), (p1[0], p1[1] - height * 0.35)
    for start, end in ((top0, top1), (low0, low1)):
        _line(draw, [start, end], cfg["metalShadow"], cfg["rail_width"] + 1.5)
        _line(draw, [start, end], cfg["metal"], cfg["rail_width"])
    count = max(3, int(math.dist(p0, p1) / cfg["bar_spacing"]))
    for index in range(1, count):
        t = index / count
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        _line(draw, [(x, y - 3), (x, y - height + 2)], cfg["metalShadow"], 2.6)
        _line(draw, [(x - 0.4, y - 3), (x - 0.4, y - height + 2)], cfg["metalHighlight"], 0.8)


def _draw_gate_segment(draw: ImageDraw.ImageDraw, p0: tuple[float, float],
                       p1: tuple[float, float], cfg: dict) -> None:
    """Draw a two-leaf gate and deliberately keep the ground opening clear."""
    height = cfg["height"]
    _line(draw, [(p0[0] + 2, p0[1] + 4), (p1[0] + 2, p1[1] + 4)],
          (*cfg["groundShadow"][:3], 70), 5)
    for start, end in ((0.0, 0.5), (0.5, 1.0)):
        q0 = (p0[0] + (p1[0] - p0[0]) * start, p0[1] + (p1[1] - p0[1]) * start)
        q1 = (p0[0] + (p1[0] - p0[0]) * end, p0[1] + (p1[1] - p0[1]) * end)
        for rise, width in ((height, 3.5), (5, 3.2)):
            a, b = (q0[0], q0[1] - rise), (q1[0], q1[1] - rise)
            _line(draw, [a, b], cfg["metalShadow"], width + 1.5)
            _line(draw, [a, b], cfg["metal"], width)
        for t in (start, end):
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            _line(draw, [(x, y - 4), (x, y - height - 1)], cfg["metalShadow"], 4.2)
            _line(draw, [(x, y - 4), (x, y - height - 1)], cfg["metal"], 2.4)
        count = max(2, int(math.dist(q0, q1) / max(5.0, cfg["bar_spacing"] - 1)))
        for index in range(1, count):
            t = start + (end - start) * index / count
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            _line(draw, [(x, y - 6), (x, y - height + 2)], cfg["metalShadow"], 2.5)
            _line(draw, [(x - 0.35, y - 6), (x - 0.35, y - height + 2)], cfg["metalHighlight"], 0.75)


def _module(recipe: dict, cfg: dict, direction: str, kind: str) -> Image.Image:
    canvas = tuple(recipe["canvas"])
    work = Image.new("RGBA", (canvas[0] * SCALE, canvas[1] * SCALE))
    draw = ImageDraw.Draw(work)
    p0 = tuple(recipe["anchor"])
    vector = DIRECTIONS[direction]
    p1 = (p0[0] + vector[0], p0[1] + vector[1])
    if kind == "segment":
        _draw_regular_segment(draw, p0, p1, cfg)
    elif kind == "gate":
        _draw_gate_segment(draw, p0, p1, cfg)
    elif kind == "post":
        _draw_post(draw, p0, cfg)
    else:
        raise ValueError(f"Unknown fence module kind {kind!r}")
    return alpha_safe_resize(work, canvas)


def _review(recipe: dict, cfg: dict) -> Image.Image:
    width, height = 900, 620
    work = Image.new("RGBA", (width * SCALE, height * SCALE), (218, 214, 194, 255))
    draw = ImageDraw.Draw(work)
    origin = (450.0, 110.0)

    def project(x: int, y: int) -> tuple[float, float]:
        return origin[0] + (x - y) * 64, origin[1] + (x + y) * 32

    for y in range(5):
        for x in range(7):
            points = [project(x, y), project(x + 1, y), project(x + 1, y + 1), project(x, y + 1)]
            fill = (107 + ((x + y) % 2) * 3, 139, 74, 255)
            draw.polygon([_pt(point) for point in points], fill=fill)
            draw.line([_pt(point) for point in points + [points[0]]], fill=(164, 174, 133, 150), width=SCALE)

    segments: list[tuple[tuple[int, int], tuple[int, int], bool]] = []
    for x in range(7):
        segments += [((x, 0), (x + 1, 0), False), ((x, 5), (x + 1, 5), x == 2)]
    for y in range(5):
        segments += [((0, y), (0, y + 1), False), ((7, y), (7, y + 1), False)]
    segments.sort(key=lambda item: (project(*item[0])[1] + project(*item[1])[1]) / 2)
    for start, end, gate in segments:
        if gate:
            _draw_gate_segment(draw, project(*start), project(*end), cfg)
        else:
            _draw_regular_segment(draw, project(*start), project(*end), cfg)
    vertices = {vertex for start, end, _ in segments for vertex in (start, end)}
    for vertex in sorted(vertices, key=lambda item: project(*item)[1]):
        _draw_post(draw, project(*vertex), cfg)
    return alpha_safe_resize(work, (width, height))


def export_fence_scenery(recipe_path: Path, output_dir: Path) -> dict:
    raw = recipe_path.read_bytes()
    recipe = json.loads(raw)
    cfg = validate_recipe(recipe)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for direction in DIRECTIONS:
        for kind in ("segment", "gate"):
            image = _module(recipe, cfg, direction, kind)
            path = output_dir / f"{recipe['id']}_{kind}_{direction}.png"
            image.save(path, format="PNG", optimize=False)
            outputs[f"{kind}_{direction}"] = str(path)
    post_image = _module(recipe, cfg, "east", "post")
    post_path = output_dir / f"{recipe['id']}_post.png"
    post_image.save(post_path, format="PNG", optimize=False)
    outputs["post"] = str(post_path)
    review = _review(recipe, cfg)
    review_path = output_dir / f"{recipe['id']}_enclosure_review.png"
    review.save(review_path, format="PNG", optimize=False)

    metadata = {
        "contract": CONTRACT,
        "id": recipe["id"],
        "camera": recipe["camera"],
        "canvas": recipe["canvas"],
        "anchor": recipe["anchor"],
        "segmentVectors": {name: list(vector) for name, vector in DIRECTIONS.items()},
        "composition": "segment sprites plus one post per occupied fence vertex",
        "gate": "two-leaf segment; no stone base across walkable opening",
        "recipeSha256": hashlib.sha256(raw).hexdigest(),
        "outputs": outputs,
        "review": str(review_path),
        "artApproved": False,
        "runtimePromotion": False,
    }
    metadata_path = output_dir / f"{recipe['id']}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {**metadata, "metadata": str(metadata_path)}
