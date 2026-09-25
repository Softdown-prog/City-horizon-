"""Small, deterministic 2D shape recipes for props and editable sprite parts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .exporter import alpha_safe_resize


CONTRACT = "CH_2D_SHAPE_RECIPE_V1"
SCALE = 4


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _pair(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be [x, y]")
    return _number(value[0], label), _number(value[1], label)


def _color(value: object, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ValueError(f"{label} must be #RRGGBB")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError as exc:
        raise ValueError(f"{label} must be #RRGGBB") from exc


def _point(value: object, label: str) -> tuple[int, int]:
    x, y = _pair(value, label)
    return round(x * SCALE), round(y * SCALE)


def _box(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{label} must be [x0, y0, x1, y1]")
    x0, y0, x1, y1 = (_number(x, label) for x in value)
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"{label} requires x0<x1 and y0<y1")
    return round(x0 * SCALE), round(y0 * SCALE), round(x1 * SCALE), round(y1 * SCALE)


def _draw_shape(mask: Image.Image, shape: dict, label: str) -> None:
    if not isinstance(shape, dict):
        raise ValueError(f"{label} must be an object")
    draw = ImageDraw.Draw(mask)
    shape_type = shape.get("type")
    fill = 0 if shape.get("operation", "paint") == "erase" else 255
    if shape.get("operation", "paint") not in ("paint", "erase"):
        raise ValueError(f"{label}.operation must be paint or erase")
    if shape_type == "ellipse":
        draw.ellipse(_box(shape.get("box"), label + ".box"), fill=fill)
    elif shape_type == "rounded_rect":
        radius = _number(shape.get("radius", 0), label + ".radius")
        if radius < 0:
            raise ValueError(f"{label}.radius must be nonnegative")
        draw.rounded_rectangle(_box(shape.get("box"), label + ".box"),
                               radius=round(radius * SCALE), fill=fill)
    elif shape_type == "polygon":
        points = shape.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(f"{label}.points requires at least three points")
        draw.polygon([_point(p, label + ".points") for p in points], fill=fill)
    elif shape_type in ("line", "quadratic"):
        points = shape.get("points")
        needed = 2 if shape_type == "line" else 3
        if not isinstance(points, list) or len(points) != needed:
            raise ValueError(f"{label}.points requires {needed} points")
        coords = [_pair(p, label + ".points") for p in points]
        width = _number(shape.get("width"), label + ".width")
        if width <= 0:
            raise ValueError(f"{label}.width must be positive")
        if shape_type == "quadratic":
            a, b, c = coords
            coords = [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * b[0] + t ** 2 * c[0],
                       (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * b[1] + t ** 2 * c[1])
                      for t in (n / 32 for n in range(33))]
        draw.line([(round(x * SCALE), round(y * SCALE)) for x, y in coords],
                  fill=fill, width=max(1, round(width * SCALE)), joint="curve")
    else:
        raise ValueError(f"{label}.type must be ellipse, rounded_rect, polygon, line or quadratic")


def _surface(size: tuple[int, int], mask: Image.Image, fill: dict, label: str) -> Image.Image:
    if not isinstance(fill, dict):
        raise ValueError(f"{label}.fill must be an object")
    top = _color(fill.get("top"), label + ".fill.top")
    bottom = _color(fill.get("bottom", fill.get("top")), label + ".fill.bottom")
    opacity = _number(fill.get("opacity", 1), label + ".fill.opacity")
    if not 0 <= opacity <= 1:
        raise ValueError(f"{label}.fill.opacity must be between 0 and 1")
    gradient = Image.new("RGB", size)
    draw = ImageDraw.Draw(gradient)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        draw.line((0, y, size[0], y), fill=tuple(round(a * (1 - t) + b * t)
                                                 for a, b in zip(top, bottom)))
    alpha = mask.point(lambda value: round(value * opacity))
    gradient.putalpha(alpha)
    return gradient


def render_shape_recipe(recipe: dict) -> tuple[Image.Image, dict]:
    """Render at 4x and downsample with premultiplied alpha; no runtime promotion."""
    if not isinstance(recipe, dict) or recipe.get("contract") != CONTRACT:
        raise ValueError(f"Recipe must declare contract {CONTRACT}")
    asset_id = recipe.get("id")
    if not isinstance(asset_id, str) or not asset_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in asset_id):
        raise ValueError("id must use lowercase letters, digits, _ or -")
    canvas = recipe.get("canvas")
    if not isinstance(canvas, list) or len(canvas) != 2 or any(type(x) is not int or x <= 0 or x > 1024 for x in canvas):
        raise ValueError("canvas must be [width, height] with positive integers <= 1024")
    anchor = _pair(recipe.get("anchor"), "anchor")
    if not (0 <= anchor[0] <= canvas[0] and 0 <= anchor[1] <= canvas[1]):
        raise ValueError("anchor must lie within canvas")
    layers = recipe.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("layers must be a non-empty list")
    size = (canvas[0] * SCALE, canvas[1] * SCALE)
    work = Image.new("RGBA", size)
    for index, layer in enumerate(layers):
        label = f"layers[{index}]"
        if not isinstance(layer, dict) or not isinstance(layer.get("name"), str):
            raise ValueError(f"{label} must have a name")
        shapes = layer.get("shapes")
        if not isinstance(shapes, list) or not shapes:
            raise ValueError(f"{label}.shapes must be a non-empty list")
        mask = Image.new("L", size)
        for pos, shape in enumerate(shapes):
            _draw_shape(mask, shape, f"{label}.shapes[{pos}]")
        if mask.getbbox() is None:
            raise ValueError(f"{label} has no visible shapes")
        shadow = layer.get("shadow")
        if shadow is not None:
            if not isinstance(shadow, dict):
                raise ValueError(f"{label}.shadow must be an object")
            dx, dy = _pair(shadow.get("offset"), label + ".shadow.offset")
            blur = _number(shadow.get("blur", 0), label + ".shadow.blur")
            opacity = _number(shadow.get("opacity", 0.4), label + ".shadow.opacity")
            if not 0 <= blur <= 32 or not 0 <= opacity <= 1:
                raise ValueError(f"{label}.shadow.blur/opacity out of range")
            shifted = ImageChops.offset(mask, round(dx * SCALE), round(dy * SCALE))
            # ImageChops.offset wraps at the edge: clear the wrapped strip.
            if dx:
                region = (0, 0, min(size[0], abs(round(dx * SCALE))), size[1]) if dx > 0 else (max(0, size[0] + round(dx * SCALE)), 0, size[0], size[1])
                ImageDraw.Draw(shifted).rectangle(region, fill=0)
            if dy:
                region = (0, 0, size[0], min(size[1], abs(round(dy * SCALE)))) if dy > 0 else (0, max(0, size[1] + round(dy * SCALE)), size[0], size[1])
                ImageDraw.Draw(shifted).rectangle(region, fill=0)
            shifted = shifted.filter(ImageFilter.GaussianBlur(blur * SCALE))
            color = _color(shadow.get("color", "#1E2630"), label + ".shadow.color")
            shadow_image = Image.new("RGBA", size, (*color, 0))
            shadow_image.putalpha(shifted.point(lambda value: round(value * opacity)))
            work.alpha_composite(shadow_image)
        work.alpha_composite(_surface(size, mask, layer.get("fill"), label))
    frame = alpha_safe_resize(work, tuple(canvas))
    bounds = frame.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Recipe renders an empty image")
    return frame, {"contract": CONTRACT, "id": asset_id, "canvas": canvas,
                   "anchor": list(anchor), "bounds": list(bounds),
                   "layerNames": [layer["name"] for layer in layers],
                   "artApproved": False, "runtimePromotion": False}


def export_shape_recipe(recipe_path: Path, output_dir: Path) -> dict:
    raw = recipe_path.read_bytes()
    recipe = json.loads(raw)
    frame, metadata = render_shape_recipe(recipe)
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{metadata['id']}.png"
    report = output_dir / f"{metadata['id']}.json"
    review = output_dir / f"{metadata['id']}_review.png"
    frame.save(png, format="PNG", optimize=False)
    width, height = frame.size
    panel = Image.new("RGBA", (width * 3 + 48, height * 2 + 40), (76, 116, 48, 255))
    panel.alpha_composite(frame, (16, 20 + height // 2))
    enlarged = frame.resize((width * 2, height * 2), Image.Resampling.NEAREST)
    panel.alpha_composite(enlarged, (width + 32, 20))
    ImageDraw.Draw(panel).text((16, 4), "1x / gameplay", fill=(247, 244, 220, 255))
    ImageDraw.Draw(panel).text((width + 32, 4), "2x / inspection", fill=(247, 244, 220, 255))
    panel.save(review, format="PNG", optimize=False)
    metadata.update({"recipe": str(recipe_path), "recipeSha256": hashlib.sha256(raw).hexdigest(),
                     "png": str(png), "review": str(review)})
    report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {"png": str(png), "metadata": str(report), "review": str(review),
            "artApproved": False,
            "runtimePromotion": False}
