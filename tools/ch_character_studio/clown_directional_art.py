#!/usr/bin/env python3
"""Deterministic four-direction master art for clown_01.

SOUTH is the already reviewed recipe master. EAST/WEST/NORTH are independently
authored 48x64 views; they are not raster warps of SOUTH. Visual primitives and
RGB color-mask primitives share the same geometry so masks remain aligned.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

from build_clown_master import ART_ROOT as SOUTH_ROOT, LAYER_RECIPES, MASK_RECIPES
from character_draw_cli import downsample_premultiplied, load_json, render

FRAME = (48, 64)
SS = 4
LAYERS = ("skin", "hair", "face", "upper_clothing", "lower_clothing", "footwear", "accessories_front")
MASK_BANKS = ("appearance", "clothing", "held_object")
CHANNEL = {"R": (255, 0, 0, 255), "G": (0, 255, 0, 255), "B": (0, 0, 255, 255)}


def _op(layer: str, kind: str, geometry, color: str, bank: str | None = None,
        channel: str | None = None, width: int = 1) -> dict:
    return {"layer": layer, "kind": kind, "geometry": geometry, "color": color,
            "bank": bank, "channel": channel, "width": width}


def _profile(direction: str) -> list[dict]:
    """Independent E/W profile art. `near` means the side facing the viewer."""
    if direction not in {"E", "W"}:
        raise ValueError(direction)
    east = direction == "E"
    # Face points toward +screen X for E and -screen X for W. Pixel coordinates
    # mirror around the center between x=23 and x=24 in the 48px frame.
    def mx(x: int) -> int:
        return x if east else 47 - x
    def box(x0, y0, x1, y1):
        a, b = mx(x0), mx(x1)
        return [min(a, b), y0, max(a, b), y1]
    def pts(values):
        return [[mx(x), y] for x, y in values]

    near_color = "#f2d744" if east else "#2b71c9"
    far_color = "#2b71c9" if east else "#f2d744"
    near_mask = "B" if east else "G"
    far_mask = "G" if east else "B"

    p: list[dict] = []
    # Hair/back volume. Profile is intentionally asymmetric.
    p += [
        _op("hair", "ellipse", box(13, 10, 22, 19), "#c72f2a", "appearance", "G"),
        _op("hair", "ellipse", box(16, 7, 25, 15), "#ea5144", "appearance", "G"),
        _op("hair", "ellipse", box(24, 9, 33, 17), "#d43b2f", "appearance", "G"),
        _op("hair", "ellipse", box(27, 12, 35, 19), "#b92824", "appearance", "G"),
        _op("hair", "pixel", [mx(17), 10], "#f07867", "appearance", "G"),
    ]
    # Skin/profile head and hands.
    p += [
        _op("skin", "ellipse", box(18, 11, 30, 23), "#f3ead7", "appearance", "R"),
        _op("skin", "polygon", pts([[21,21],[23,24],[27,24],[29,21],[28,25],[22,25]]), "#ddc7ac", "appearance", "R"),
        _op("skin", "ellipse", box(17, 36, 20, 40), "#f3ead7", "appearance", "R"),
        _op("skin", "ellipse", box(29, 35, 33, 40), "#f3ead7", "appearance", "R"),
    ]
    # One readable eye + profile nose/mouth. No fake second frontal eye.
    p += [
        _op("face", "ellipse", box(24, 14, 26, 16), "#2f2b29"),
        _op("face", "pixel", [mx(25), 14], "#ffffff"),
        _op("face", "ellipse", box(27, 17, 31, 21), "#df3b36", "appearance", "B"),
        _op("face", "line", pts([[25,22],[27,23],[29,22]]), "#a7373d", "appearance", "B"),
        _op("face", "pixel", [mx(29), 18], "#ff8c7c", "appearance", "B"),
    ]
    # Far arm first, torso, near arm. Red torso is primary; blue/yellow are independent recolor groups.
    p += [
        _op("upper_clothing", "polygon", pts([[18,28],[21,28],[20,38],[17,38],[16,32]]), far_color, "clothing", far_mask),
        _op("upper_clothing", "polygon", pts([[19,26],[22,24],[28,25],[31,28],[30,38],[18,38]]), "#d43b2f", "clothing", "R"),
        _op("upper_clothing", "polygon", pts([[19,27],[21,26],[20,37],[18,38]]), "#b52f28", "clothing", "R"),
        _op("upper_clothing", "polygon", pts([[29,27],[32,28],[34,32],[33,37],[30,38]]), near_color, "clothing", near_mask),
        _op("upper_clothing", "ellipse", box(19,24,30,29), "#f4f2e3"),
        _op("upper_clothing", "line", pts([[23,26],[23,37]]), "#f2d744", "clothing", "B"),
        _op("upper_clothing", "line", pts([[27,26],[27,37]]), "#2b71c9", "clothing", "G"),
    ]
    # Bow remains fixed purple and reads in 3/4 profile.
    p += [
        _op("accessories_front", "ellipse", box(21,28,26,32), "#8b5cf6"),
        _op("accessories_front", "pixel", [mx(24), 29], "#b9a0ff"),
    ]
    # Legs overlap slightly in profile. Far leg sits one pixel higher.
    p += [
        _op("lower_clothing", "polygon", pts([[20,38],[24,38],[24,53],[20,53]]), far_color, "clothing", far_mask),
        _op("lower_clothing", "polygon", pts([[24,38],[29,38],[30,54],[24,54]]), near_color, "clothing", near_mask),
        _op("lower_clothing", "line", pts([[24,39],[24,52]]), "#8f3d32", "clothing", "R"),
        _op("footwear", "ellipse", box(17,52,26,58), "#26313a"),
        _op("footwear", "ellipse", box(23,52,34,58), "#26313a"),
        _op("footwear", "rect", box(19,53,24,55), "#394650"),
        _op("footwear", "rect", box(26,53,32,55), "#394650"),
    ]
    return p


def _north() -> list[dict]:
    p: list[dict] = []
    # Full back hair. There is deliberately no face/makeup layer from the front.
    p += [
        _op("hair", "ellipse", [13,10,22,19], "#c72f2a", "appearance", "G"),
        _op("hair", "ellipse", [26,10,35,19], "#c72f2a", "appearance", "G"),
        _op("hair", "ellipse", [16,7,24,15], "#ea5144", "appearance", "G"),
        _op("hair", "ellipse", [24,7,32,15], "#ea5144", "appearance", "G"),
        _op("hair", "ellipse", [19,9,29,21], "#d43b2f", "appearance", "G"),
        _op("hair", "pixel", [17,10], "#f07867", "appearance", "G"),
        _op("hair", "pixel", [31,10], "#f07867", "appearance", "G"),
    ]
    # Only neck/hands expose skin from behind.
    p += [
        _op("skin", "rect", [22,22,26,25], "#ddc7ac", "appearance", "R"),
        _op("skin", "ellipse", [15,36,18,40], "#f3ead7", "appearance", "R"),
        _op("skin", "ellipse", [30,36,33,40], "#f3ead7", "appearance", "R"),
    ]
    # Back of costume: no suspenders, no bow. Collar and center seam remain readable.
    p += [
        _op("upper_clothing", "polygon", [[18,26],[21,24],[27,24],[30,26],[31,38],[17,38]], "#d43b2f", "clothing", "R"),
        _op("upper_clothing", "polygon", [[16,27],[19,28],[18,37],[14,37],[13,31]], "#2b71c9", "clothing", "G"),
        _op("upper_clothing", "polygon", [[29,28],[32,27],[35,31],[34,37],[30,37]], "#f2d744", "clothing", "B"),
        _op("upper_clothing", "ellipse", [18,24,30,29], "#f4f2e3"),
        _op("upper_clothing", "line", [[24,28],[24,38]], "#9f2b27", "clothing", "R"),
        _op("upper_clothing", "pixel", [23,34], "#ed5a4c", "clothing", "R"),
    ]
    p += [
        _op("lower_clothing", "polygon", [[18,38],[24,38],[23,54],[18,54]], "#2b71c9", "clothing", "G"),
        _op("lower_clothing", "polygon", [[24,38],[30,38],[30,54],[25,54]], "#f2d744", "clothing", "B"),
        _op("lower_clothing", "line", [[24,39],[24,52]], "#8f3d32", "clothing", "R"),
        _op("footwear", "ellipse", [15,52,24,58], "#26313a"),
        _op("footwear", "ellipse", [24,52,33,58], "#26313a"),
        _op("footwear", "rect", [17,53,22,55], "#394650"),
        _op("footwear", "rect", [26,53,31,55], "#394650"),
    ]
    return p


def _draw_one(draw: ImageDraw.ImageDraw, item: dict, *, scale: int, mask: bool = False) -> None:
    kind, geometry = item["kind"], item["geometry"]
    fill = CHANNEL[item["channel"]] if mask else item["color"]
    def sp(p): return tuple(int(round(v * scale)) for v in p)
    if kind == "pixel":
        x, y = geometry
        draw.rectangle((x*scale, y*scale, (x+1)*scale-1, (y+1)*scale-1), fill=fill)
    elif kind == "rect":
        x0,y0,x1,y1 = geometry
        draw.rectangle((x0*scale,y0*scale,(x1+1)*scale-1,(y1+1)*scale-1), fill=fill)
    elif kind == "ellipse":
        x0,y0,x1,y1 = geometry
        draw.ellipse((x0*scale,y0*scale,(x1+1)*scale-1,(y1+1)*scale-1), fill=fill)
    elif kind == "polygon":
        draw.polygon([sp(p) for p in geometry], fill=fill)
    elif kind == "line":
        draw.line([sp(p) for p in geometry], fill=fill, width=max(1,item.get("width",1)*scale), joint="curve")
    else:
        raise ValueError(f"unsupported primitive: {kind}")


def _render_primitives(primitives: list[dict]) -> tuple[dict[str, Image.Image], dict[str, Image.Image]]:
    layers: dict[str, Image.Image] = {}
    by_layer = defaultdict(list)
    for item in primitives:
        by_layer[item["layer"]].append(item)
    for name in LAYERS:
        canvas = Image.new("RGBA", (FRAME[0]*SS, FRAME[1]*SS), (0,0,0,0))
        draw = ImageDraw.Draw(canvas)
        for item in by_layer.get(name, []):
            _draw_one(draw, item, scale=SS)
        layers[name] = downsample_premultiplied(canvas, FRAME)

    masks = {bank: Image.new("RGBA", FRAME, (0,0,0,0)) for bank in MASK_BANKS}
    for bank in MASK_BANKS:
        draw = ImageDraw.Draw(masks[bank])
        for item in primitives:
            if item.get("bank") == bank and item.get("channel") in CHANNEL:
                _draw_one(draw, item, scale=1, mask=True)
    return layers, masks


def south_master(seed: int = 1337) -> tuple[dict[str, Image.Image], dict[str, Image.Image]]:
    layers = {}
    for name, filename in LAYER_RECIPES:
        recipe = load_json(SOUTH_ROOT / filename)
        recipe["supersample"] = 4
        layers[name] = render(recipe, seed)
    masks = {}
    for name, filename in MASK_RECIPES:
        recipe = load_json(SOUTH_ROOT / filename)
        recipe["supersample"] = 1
        masks[name] = render(recipe, seed)
    return layers, masks


def build_direction(direction: str, seed: int = 1337) -> tuple[dict[str, Image.Image], dict[str, Image.Image]]:
    direction = direction.upper()
    if direction == "S":
        return south_master(seed)
    if direction == "N":
        return _render_primitives(_north())
    if direction in {"E", "W"}:
        return _render_primitives(_profile(direction))
    raise ValueError(f"unsupported direction: {direction}")
