"""Localized deterministic finish passes for Visitor Forge 2D.

These passes sit between structural rendering and the final gameplay critic.
They let recipes paint wear, scratches and grain accents inside authored masks
instead of applying the same global texture to the entire asset.
"""
from __future__ import annotations

import math
import random
from copy import deepcopy

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import scene_composer_v3, smooth_geometry

_ALLOWED_STYLES = {"wood_wear", "edge_wear", "scratches"}
_MAX_REGIONS = 32
_MAX_STAMPS = 120


def _num(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def validate_regions(regions: object) -> None:
    if regions is None:
        return
    if not isinstance(regions, list) or len(regions) > _MAX_REGIONS:
        raise ValueError(f"finishRegions must be a list with at most {_MAX_REGIONS} entries")
    for index, region in enumerate(regions):
        label = f"finishRegions[{index}]"
        if not isinstance(region, dict):
            raise ValueError(f"{label} must be an object")
        if region.get("style") not in _ALLOWED_STYLES:
            raise ValueError(f"{label}.style must be one of {sorted(_ALLOWED_STYLES)}")
        mask = region.get("mask")
        if not isinstance(mask, dict):
            raise ValueError(f"{label}.mask must be a shape object")
        stamps = region.get("stamps", 24)
        if type(stamps) is not int or not 0 <= stamps <= _MAX_STAMPS:
            raise ValueError(f"{label}.stamps must be 0..{_MAX_STAMPS}")
        opacity = _num(region.get("opacity", 0.12), label + ".opacity")
        if not 0 <= opacity <= 0.5:
            raise ValueError(f"{label}.opacity must be 0..0.5")
        angle = _num(region.get("angleDeg", 0), label + ".angleDeg")
        if abs(angle) > 3600:
            raise ValueError(f"{label}.angleDeg is outside safe limits")


def _expanded_mask_node(mask: dict) -> dict:
    if mask.get("primitive") != "smooth_polygon":
        return deepcopy(mask)
    node = deepcopy(mask)
    node["points"] = smooth_geometry.sample_closed_catmull_rom(
        node.get("points"), node.pop("samplesPerSegment", 6), node.pop("tension", 0.5)
    )
    node["primitive"] = "polygon"
    return node


def _mask(size: tuple[int, int], spec: dict, label: str) -> Image.Image:
    identity = {"translate": [0.0, 0.0], "scale": [1.0, 1.0], "rotateDeg": 0.0}
    return scene_composer_v3._shape_mask(size, _expanded_mask_node(spec), identity, label)


def _oriented_line(draw: ImageDraw.ImageDraw, cx: float, cy: float, angle: float,
                   half_len: float, width: int, fill) -> None:
    c, s = math.cos(angle), math.sin(angle)
    draw.line((cx-c*half_len, cy-s*half_len, cx+c*half_len, cy+s*half_len),
              fill=fill, width=max(1, width))


def _wood_wear(size, mask, rng, stamps: int, opacity: float, angle_deg: float) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    angle = math.radians(angle_deg)
    for _ in range(stamps):
        x = rng.randrange(size[0]); y = rng.randrange(size[1])
        length = rng.uniform(5, 18); width = rng.choice((1, 1, 2))
        light = rng.random() > 0.44
        alpha = round(255 * opacity * rng.uniform(0.25, 0.9))
        fill = (246, 205, 153, alpha) if light else (67, 37, 24, alpha)
        _oriented_line(d, x, y, angle + rng.uniform(-0.13, 0.13), length/2, width, fill)
    layer = layer.filter(ImageFilter.GaussianBlur(0.35))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def _scratches(size, mask, rng, stamps: int, opacity: float, angle_deg: float) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    angle = math.radians(angle_deg)
    for _ in range(stamps):
        x = rng.randrange(size[0]); y = rng.randrange(size[1])
        length = rng.uniform(3, 13)
        alpha = round(255 * opacity * rng.uniform(0.3, 1.0))
        fill = (238, 220, 192, alpha) if rng.random() > 0.58 else (49, 36, 31, alpha)
        _oriented_line(d, x, y, angle + rng.uniform(-0.32, 0.32), length/2, 1, fill)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def _edge_wear(size, mask, rng, stamps: int, opacity: float) -> Image.Image:
    inner = mask.filter(ImageFilter.MinFilter(5))
    edge = ImageChops.subtract(mask, inner)
    layer = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    for _ in range(stamps):
        x = rng.randrange(size[0]); y = rng.randrange(size[1])
        r = rng.randint(1, 4)
        alpha = round(255 * opacity * rng.uniform(0.25, 0.9))
        fill = (250, 222, 184, alpha) if rng.random() > 0.45 else (55, 34, 24, alpha)
        d.ellipse((x-r, y-r, x+r, y+r), fill=fill)
    layer = layer.filter(ImageFilter.GaussianBlur(0.55))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), edge))
    return layer


def apply_regions(frame: Image.Image, regions: object, seed: int) -> Image.Image:
    validate_regions(regions)
    if not regions:
        return frame
    image = frame.convert("RGBA")
    for index, region in enumerate(regions):
        mask = _mask(image.size, region["mask"], f"finishRegions[{index}].mask")
        rng = random.Random((seed + 1) * 104729 + index * 8191)
        stamps = region.get("stamps", 24)
        opacity = _num(region.get("opacity", 0.12), f"finishRegions[{index}].opacity")
        angle = _num(region.get("angleDeg", 0), f"finishRegions[{index}].angleDeg")
        style = region["style"]
        if style == "wood_wear":
            layer = _wood_wear(image.size, mask, rng, stamps, opacity, angle)
        elif style == "scratches":
            layer = _scratches(image.size, mask, rng, stamps, opacity, angle)
        else:
            layer = _edge_wear(image.size, mask, rng, stamps, opacity)
        image = Image.alpha_composite(image, layer)
    return image
