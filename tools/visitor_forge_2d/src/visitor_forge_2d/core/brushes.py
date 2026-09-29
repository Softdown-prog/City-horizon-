"""Reusable deterministic raster brushes for Visitor Forge 2D.

These are intentionally small composable drawing primitives, not full asset
renderers. Species renderers combine them into crowns, branches and finish
passes while keeping the CH 2D pipeline deterministic and reviewable.
"""
from __future__ import annotations

import math
import random
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

WORK_SCALE = 4


def _hex(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def leaf_cluster_round(
    mask: Image.Image,
    rng: random.Random,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    lobes: int = 14,
    jitter: float = 0.18,
    fill: int = 255,
) -> None:
    """Rounded irregular foliage mass for dense broadleaf families."""
    points = []
    for i in range(max(8, lobes)):
        angle = math.tau * i / max(8, lobes)
        radial = 1.0 + rng.uniform(-jitter, jitter)
        points.append((
            round((cx + math.cos(angle) * rx * radial) * WORK_SCALE),
            round((cy + math.sin(angle) * ry * radial) * WORK_SCALE),
        ))
    ImageDraw.Draw(mask).polygon(points, fill=fill)


def leaf_cluster_broadleaf(
    mask: Image.Image,
    rng: random.Random,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    satellites: int = 4,
    fill: int = 255,
) -> None:
    """Medium-scale foliage group with attached submasses.

    The main lobe provides macro readability; satellites break the contour and
    keep the group from looking like one procedural polygon.
    """
    leaf_cluster_round(mask, rng, cx, cy, rx, ry, lobes=13, jitter=.23, fill=fill)
    for _ in range(max(0, satellites)):
        angle = rng.uniform(0.0, math.tau)
        distance = rng.uniform(.34, .70)
        sx = cx + math.cos(angle) * rx * distance
        sy = cy + math.sin(angle) * ry * distance
        leaf_cluster_round(
            mask, rng, sx, sy,
            rx * rng.uniform(.22, .40),
            ry * rng.uniform(.22, .42),
            lobes=rng.randint(8, 11), jitter=.27, fill=fill,
        )


def maple_leaf_points(
    x: float,
    y: float,
    size: float,
    angle: float,
    *,
    work_scale: int = WORK_SCALE,
) -> list[tuple[float, float]]:
    """Return a compact ten-point stylized maple leaf silhouette."""
    radii = (1.00, .46, .83, .41, .72, .35, .72, .41, .83, .46)
    points: list[tuple[float, float]] = []
    for index, radius in enumerate(radii):
        theta = angle - math.pi / 2 + index * math.tau / len(radii)
        points.append((
            (x + math.cos(theta) * size * radius) * work_scale,
            (y + math.sin(theta) * size * radius * .86) * work_scale,
        ))
    return points


def leaf_cluster_maple(
    layer: Image.Image,
    rng: random.Random,
    mask: Image.Image,
    center: tuple[float, float],
    radius: tuple[float, float],
    palette: Iterable[str],
    *,
    count: int | None = None,
    highlight_color: str | None = None,
    shadow_color: str | None = None,
) -> None:
    """Paint many small maple leaves constrained to an authored group mask."""
    cx, cy = center
    rx, ry = radius
    colors = tuple(palette)
    if not colors:
        raise ValueError("maple brush needs at least one palette color")
    pixels = mask.load()
    draw = ImageDraw.Draw(layer, "RGBA")
    target = count if count is not None else max(30, round((rx * ry) / 5.7))

    for _ in range(target):
        x = cx + rng.uniform(-.94, .94) * rx
        y = cy + rng.uniform(-.92, .92) * ry
        ix, iy = round(x * WORK_SCALE), round(y * WORK_SCALE)
        if not (0 <= ix < mask.width and 0 <= iy < mask.height):
            continue
        if pixels[ix, iy] < 210:
            continue

        roll = rng.random()
        if highlight_color and y < cy and roll < .16:
            color = highlight_color
        elif shadow_color and y > cy + ry * .15 and roll < .24:
            color = shadow_color
        else:
            color = colors[rng.randrange(len(colors))]

        size = rng.uniform(2.7, 5.1)
        points = maple_leaf_points(x, y, size, rng.uniform(-.58, .58))
        draw.polygon(points, fill=(*_hex(color), rng.randint(178, 242)))


def branch_tapered(
    mask: Image.Image,
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    w0: float,
    w1: float,
    *,
    samples: int = 48,
    fill: int = 255,
) -> None:
    """Quadratic-bezier branch brush with continuous taper."""
    draw = ImageDraw.Draw(mask)
    for i in range(samples + 1):
        t = i / samples
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        width = (w0 + (w1 - w0) * t) * WORK_SCALE
        r = max(1.0, width * .5)
        x *= WORK_SCALE
        y *= WORK_SCALE
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def interior_occlusion_patch(
    mask: Image.Image,
    rng: random.Random,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    strength: int = 150,
) -> None:
    """Soft organic shadow patch used between overlapping foliage groups."""
    leaf_cluster_round(mask, rng, cx, cy, rx, ry, lobes=11, jitter=.22, fill=strength)
    blurred = mask.filter(ImageFilter.GaussianBlur(.35 * WORK_SCALE))
    mask.paste(blurred)


def edge_breakup_stamp(
    mask: Image.Image,
    rng: random.Random,
    cx: float,
    cy: float,
    radius: float,
    *,
    count: int = 8,
    fill: int = 255,
) -> None:
    """Add small contour protrusions around a silhouette edge."""
    draw = ImageDraw.Draw(mask)
    for _ in range(max(1, count)):
        angle = rng.uniform(0.0, math.tau)
        distance = rng.uniform(radius * .56, radius * .98)
        x = (cx + math.cos(angle) * distance) * WORK_SCALE
        y = (cy + math.sin(angle) * distance) * WORK_SCALE
        r = rng.uniform(radius * .08, radius * .18) * WORK_SCALE
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def silhouette_gap_cutter(
    mask: Image.Image,
    rng: random.Random,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    count: int = 3,
) -> None:
    """Cut small negative-space bites to avoid perfectly solid crown edges."""
    draw = ImageDraw.Draw(mask)
    for _ in range(max(0, count)):
        angle = rng.uniform(0.0, math.tau)
        x = (cx + math.cos(angle) * rx * rng.uniform(.72, 1.02)) * WORK_SCALE
        y = (cy + math.sin(angle) * ry * rng.uniform(.72, 1.02)) * WORK_SCALE
        crx = rng.uniform(rx * .08, rx * .17) * WORK_SCALE
        cry = rng.uniform(ry * .08, ry * .18) * WORK_SCALE
        draw.ellipse((x - crx, y - cry, x + crx, y + cry), fill=0)
