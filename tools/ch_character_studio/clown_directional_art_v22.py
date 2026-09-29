#!/usr/bin/env python3
"""Directional clown art V2.2.

Refines V2.1 by opening the E/W forehead/face silhouette and using a BOX
supersample resolve for new directional art, avoiding LANCZOS ringing/bright
color fringes at transparent edges. SOUTH remains byte-for-byte on its reviewed
master path.
"""
from __future__ import annotations

from collections import defaultdict
from PIL import Image, ImageDraw

import clown_directional_art_v2 as v2
import clown_directional_art_v21 as v21

FRAME = v2.FRAME
SS = v2.SS
LAYERS = v2.LAYERS
MASK_BANKS = v2.MASK_BANKS
CHANNEL = v2.CHANNEL


def _open_profile_face(primitives: list[dict], direction: str) -> list[dict]:
    """Remove the center hair cap that covered too much of the 3/4 face."""
    out = []
    for item in primitives:
        if item["layer"] == "hair" and item["kind"] == "ellipse":
            x0,y0,x1,y1 = item["geometry"]
            # Center cap after E/W mirroring: about 10px wide starting at y=8.
            if y0 == 8 and y1 == 18 and (x1 - x0) >= 9:
                continue
        out.append(item)
    return out


def _clean_downsample(image: Image.Image) -> Image.Image:
    """4x area resolve without LANCZOS ringing around transparent pixels."""
    return image.convert("RGBA").resize(FRAME, Image.Resampling.BOX)


def _render_clean(primitives: list[dict]):
    by_layer = defaultdict(list)
    for item in primitives:
        by_layer[item["layer"]].append(item)

    layers = {}
    for name in LAYERS:
        canvas = Image.new("RGBA", (FRAME[0]*SS, FRAME[1]*SS), (0,0,0,0))
        draw = ImageDraw.Draw(canvas)
        for item in by_layer.get(name, []):
            v2._draw_one(draw, item, scale=SS)
        layers[name] = _clean_downsample(canvas)

    masks = {bank: Image.new("RGBA", FRAME, (0,0,0,0)) for bank in MASK_BANKS}
    for bank in MASK_BANKS:
        draw = ImageDraw.Draw(masks[bank])
        for item in primitives:
            if item.get("bank") == bank and item.get("channel") in CHANNEL:
                v2._draw_one(draw, item, scale=1, mask=True)
    return layers, masks


def build_direction(direction: str, seed: int = 1337):
    direction = direction.upper()
    if direction == "S":
        return v2.south_master(seed)
    if direction in {"E", "W"}:
        primitives = v21._refine(v2._three_quarter(direction), direction)
        primitives = _open_profile_face(primitives, direction)
        return _render_clean(primitives)
    if direction == "N":
        primitives = v21._refine(v2._rear_three_quarter(), "N")
        return _render_clean(primitives)
    raise ValueError(direction)
