#!/usr/bin/env python3
"""Directional clown art V2 for the City Horizon 45/30 isometric camera.

SOUTH keeps the reviewed master. EAST/WEST are 3/4 views rather than flat side
profiles; NORTH is a 3/4 rear view rather than a flat back. Geometry and RGB mask
coverage are authored from the same primitives so recolor masks stay aligned.
"""
from __future__ import annotations

from collections import defaultdict
from PIL import Image, ImageDraw

from build_clown_master import ART_ROOT as SOUTH_ROOT, LAYER_RECIPES, MASK_RECIPES
from character_draw_cli import downsample_premultiplied, load_json, render

FRAME = (48, 64)
SS = 4
LAYERS = ("skin", "hair", "face", "upper_clothing", "lower_clothing", "footwear", "accessories_front")
MASK_BANKS = ("appearance", "clothing", "held_object")
CHANNEL = {"R": (255, 0, 0, 255), "G": (0, 255, 0, 255), "B": (0, 0, 255, 255)}


def _op(layer, kind, geometry, color, bank=None, channel=None, width=1):
    return {"layer": layer, "kind": kind, "geometry": geometry, "color": color,
            "bank": bank, "channel": channel, "width": width}


def _mirror(direction: str):
    east = direction == "E"
    def mx(x: int) -> int:
        return x if east else 47 - x
    def box(x0, y0, x1, y1):
        a, b = mx(x0), mx(x1)
        return [min(a, b), y0, max(a, b), y1]
    def pts(values):
        return [[mx(x), y] for x, y in values]
    return east, mx, box, pts


def _three_quarter(direction: str) -> list[dict]:
    if direction not in {"E", "W"}:
        raise ValueError(direction)
    east, mx, box, pts = _mirror(direction)
    near = "#f2d744" if east else "#2b71c9"
    far = "#2b71c9" if east else "#f2d744"
    near_mask = "B" if east else "G"
    far_mask = "G" if east else "B"
    p: list[dict] = []

    # Hair keeps almost the same total width as SOUTH; only depth/overlap changes.
    p += [
        _op("hair", "ellipse", box(12,10,20,19), "#bd2a26", "appearance", "G"),
        _op("hair", "ellipse", box(15,7,23,15), "#ea5144", "appearance", "G"),
        _op("hair", "ellipse", box(24,7,33,15), "#df4438", "appearance", "G"),
        _op("hair", "ellipse", box(28,10,36,19), "#c72f2a", "appearance", "G"),
        _op("hair", "ellipse", box(19,8,29,18), "#d43b2f", "appearance", "G"),
        _op("hair", "pixel", [mx(17),10], "#f07867", "appearance", "G"),
        _op("hair", "pixel", [mx(31),10], "#f07867", "appearance", "G"),
    ]

    # 3/4 head: still broad; far cheek/eye is visible but compressed.
    p += [
        _op("skin", "ellipse", box(17,11,31,23), "#f3ead7", "appearance", "R"),
        _op("skin", "polygon", pts([[19,18],[21,22],[27,24],[30,20],[29,23],[27,25],[21,24],[19,21]]), "#ddc7ac", "appearance", "R"),
        _op("skin", "ellipse", box(15,36,19,40), "#f3ead7", "appearance", "R"),
        _op("skin", "ellipse", box(30,35,34,40), "#f3ead7", "appearance", "R"),
        _op("face", "ellipse", box(20,14,22,16), "#403a36"),
        _op("face", "ellipse", box(26,14,28,16), "#2f2b29"),
        _op("face", "pixel", [mx(27),14], "#ffffff"),
        _op("face", "ellipse", box(24,17,29,21), "#df3b36", "appearance", "B"),
        _op("face", "pixel", [mx(28),18], "#ff8c7c", "appearance", "B"),
        _op("face", "line", pts([[21,22],[24,23],[27,23],[29,22]]), "#a7373d", "appearance", "B"),
    ]

    # Broad 3/4 torso: far arm behind, near shoulder/arm larger in front.
    p += [
        _op("upper_clothing", "polygon", pts([[15,28],[19,27],[19,37],[15,38],[13,32]]), far, "clothing", far_mask),
        _op("upper_clothing", "polygon", pts([[18,26],[21,24],[28,24],[32,27],[31,38],[17,38]]), "#d43b2f", "clothing", "R"),
        _op("upper_clothing", "polygon", pts([[18,27],[21,25],[20,37],[17,38]]), "#b52f28", "clothing", "R"),
        _op("upper_clothing", "polygon", pts([[29,27],[33,28],[36,32],[35,37],[31,38]]), near, "clothing", near_mask),
        _op("upper_clothing", "ellipse", box(18,24,31,29), "#f4f2e3"),
        _op("upper_clothing", "ellipse", box(20,24,25,28), "#ebe7d7"),
        _op("upper_clothing", "ellipse", box(26,24,32,28), "#fffdf3"),
        _op("upper_clothing", "line", pts([[21,26],[21,37]]), "#f2d744", "clothing", "B"),
        _op("upper_clothing", "line", pts([[28,26],[28,37]]), "#2b71c9", "clothing", "G"),
        _op("accessories_front", "ellipse", box(21,28,27,32), "#8b5cf6"),
        _op("accessories_front", "pixel", [mx(24),29], "#b9a0ff"),
        _op("accessories_front", "pixel", [mx(26),30], "#5e3dbd"),
    ]

    # Keep leg spacing close to SOUTH, with the far leg slightly tucked back.
    p += [
        _op("lower_clothing", "polygon", pts([[18,38],[24,38],[23,54],[18,54]]), far, "clothing", far_mask),
        _op("lower_clothing", "polygon", pts([[24,38],[31,38],[31,54],[25,54]]), near, "clothing", near_mask),
        _op("lower_clothing", "polygon", pts([[18,39],[21,39],[20,53],[18,54]]), "#225ca5" if far == "#2b71c9" else "#d4ae2e", "clothing", far_mask),
        _op("lower_clothing", "line", pts([[24,39],[24,52]]), "#8f3d32", "clothing", "R"),
        _op("footwear", "ellipse", box(15,52,25,58), "#26313a"),
        _op("footwear", "ellipse", box(24,52,34,58), "#26313a"),
        _op("footwear", "rect", box(17,53,23,55), "#394650"),
        _op("footwear", "rect", box(27,53,32,55), "#394650"),
    ]
    return p


def _rear_three_quarter() -> list[dict]:
    p: list[dict] = []
    # Rear 3/4 head: broad hair silhouette, slightly offset crown and visible neck.
    p += [
        _op("hair", "ellipse", [12,10,21,19], "#bd2a26", "appearance", "G"),
        _op("hair", "ellipse", [16,7,24,15], "#ea5144", "appearance", "G"),
        _op("hair", "ellipse", [24,7,33,15], "#df4438", "appearance", "G"),
        _op("hair", "ellipse", [28,10,36,19], "#c72f2a", "appearance", "G"),
        _op("hair", "ellipse", [19,8,30,19], "#d43b2f", "appearance", "G"),
        _op("hair", "pixel", [17,10], "#f07867", "appearance", "G"),
        _op("hair", "pixel", [31,10], "#f07867", "appearance", "G"),
        _op("skin", "polygon", [[21,21],[27,21],[28,25],[21,25]], "#ddc7ac", "appearance", "R"),
        _op("skin", "ellipse", [15,36,19,40], "#f3ead7", "appearance", "R"),
        _op("skin", "ellipse", [30,35,34,40], "#f3ead7", "appearance", "R"),
    ]

    # Rear body has the same shoulder/torso mass as SOUTH, with depth asymmetry.
    p += [
        _op("upper_clothing", "polygon", [[15,28],[19,27],[19,37],[15,38],[13,32]], "#2b71c9", "clothing", "G"),
        _op("upper_clothing", "polygon", [[18,26],[21,24],[28,24],[32,27],[31,38],[17,38]], "#d43b2f", "clothing", "R"),
        _op("upper_clothing", "polygon", [[29,27],[33,28],[36,32],[35,37],[31,38]], "#f2d744", "clothing", "B"),
        _op("upper_clothing", "ellipse", [18,24,31,29], "#f4f2e3"),
        _op("upper_clothing", "line", [[24,29],[24,38]], "#9f2b27", "clothing", "R"),
        _op("upper_clothing", "pixel", [23,34], "#ed5a4c", "clothing", "R"),
    ]

    p += [
        _op("lower_clothing", "polygon", [[18,38],[24,38],[23,54],[18,54]], "#2b71c9", "clothing", "G"),
        _op("lower_clothing", "polygon", [[24,38],[31,38],[31,54],[25,54]], "#f2d744", "clothing", "B"),
        _op("lower_clothing", "line", [[24,39],[24,52]], "#8f3d32", "clothing", "R"),
        _op("footwear", "ellipse", [15,52,25,58], "#26313a"),
        _op("footwear", "ellipse", [24,52,34,58], "#26313a"),
        _op("footwear", "rect", [17,53,23,55], "#394650"),
        _op("footwear", "rect", [27,53,32,55], "#394650"),
    ]
    return p


def _draw_one(draw: ImageDraw.ImageDraw, item: dict, *, scale: int, mask: bool = False):
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
        raise ValueError(kind)


def _render_primitives(primitives: list[dict]):
    by_layer = defaultdict(list)
    for item in primitives:
        by_layer[item["layer"]].append(item)
    layers = {}
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


def south_master(seed: int = 1337):
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


def build_direction(direction: str, seed: int = 1337):
    direction = direction.upper()
    if direction == "S":
        return south_master(seed)
    if direction == "N":
        return _render_primitives(_rear_three_quarter())
    if direction in {"E", "W"}:
        return _render_primitives(_three_quarter(direction))
    raise ValueError(direction)
