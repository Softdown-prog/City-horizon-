#!/usr/bin/env python3
"""Small visual refinement over Directional Art V2.

Keeps V2 body proportions and masks, but reduces E/W/N hair mass around the
face/neck so the 3/4 views read closer to the reviewed SOUTH silhouette.
"""
from __future__ import annotations

import copy
import clown_directional_art_v2 as base


def _transform_point(point, sx: float, sy: float, px: float, py: float, dx: float = 0.0, dy: float = 0.0):
    x, y = point
    return [int(round(px + (x - px) * sx + dx)), int(round(py + (y - py) * sy + dy))]


def _transform_item(item: dict, sx: float, sy: float, px: float, py: float,
                    dx: float = 0.0, dy: float = 0.0) -> dict:
    out = copy.deepcopy(item)
    kind = out["kind"]
    g = out["geometry"]
    if kind == "pixel":
        out["geometry"] = _transform_point(g, sx, sy, px, py, dx, dy)
    elif kind in {"rect", "ellipse"}:
        a = _transform_point([g[0], g[1]], sx, sy, px, py, dx, dy)
        b = _transform_point([g[2], g[3]], sx, sy, px, py, dx, dy)
        out["geometry"] = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
    elif kind in {"polygon", "line"}:
        out["geometry"] = [_transform_point(p, sx, sy, px, py, dx, dy) for p in g]
    return out


def _refine(primitives: list[dict], direction: str) -> list[dict]:
    result = []
    for item in primitives:
        layer = item["layer"]
        if layer == "hair":
            # Reduce the mushroom-like mass while keeping asymmetry and color masks.
            if direction in {"E", "W"}:
                result.append(_transform_item(item, 0.91, 0.90, 24.0, 14.5, 0.0, 0.3))
            else:
                result.append(_transform_item(item, 0.92, 0.89, 24.0, 14.3, 0.0, 0.2))
        elif layer == "skin" and direction in {"E", "W"}:
            # Slightly more vertical face/neck separation in 3/4 profile.
            result.append(_transform_item(item, 0.98, 1.00, 24.0, 18.0, 0.0, 0.3))
        elif layer == "face" and direction in {"E", "W"}:
            result.append(_transform_item(item, 1.00, 1.00, 24.0, 18.0, 0.0, 0.4))
        else:
            result.append(copy.deepcopy(item))
    return result


def build_direction(direction: str, seed: int = 1337):
    direction = direction.upper()
    if direction == "S":
        return base.south_master(seed)
    if direction == "N":
        return base._render_primitives(_refine(base._rear_three_quarter(), "N"))
    if direction in {"E", "W"}:
        return base._render_primitives(_refine(base._three_quarter(direction), direction))
    raise ValueError(direction)
