"""Deterministic raster-painted organic scenery for City Horizon."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .exporter import alpha_safe_resize as _alpha_safe_resize
from .render_finish import finish_render

CONTRACT = "CH_2D_ORGANIC_SCENERY_V1"
CAMERA_CONTRACT = "CH_CAMERA_V1"
ROTATION_CONTRACT = "CH_2D_ROTATION_BUNDLE_V1"
WORK_SCALE = 4
VALID_VIEWS = ("south", "west", "north", "east")
DEFAULT_YAWS = {"south": 45, "west": 135, "north": 225, "east": 315}
VIEW_PHASE = {"south": 0.0, "west": math.pi / 2, "north": math.pi, "east": math.pi * 1.5}


def _hex(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _lerp(a, b, t):
    return a + (b - a) * t


def _quad(p0, p1, p2, t):
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def _paint(mask, top, bottom, right_shade=0.0, highlight=None):
    w, h = mask.size
    a, b = _hex(top), _hex(bottom)
    grad = Image.new("L", (1, h))
    grad.putdata([round(y / max(1, h - 1) * 255) for y in range(h)])
    grad = grad.resize((w, h))
    surf = Image.composite(Image.new("RGB", (w, h), b), Image.new("RGB", (w, h), a), grad).convert("RGBA")
    if right_shade > 0:
        hgrad = Image.new("L", (w, 1))
        hgrad.putdata([round(255 * (1.0 - right_shade * (x / max(1, w - 1)))) for x in range(w)])
        hgrad = hgrad.resize((w, h))
        r, g, bc, alpha = surf.split()
        surf = Image.merge("RGBA", (
            ImageChops.multiply(r, hgrad),
            ImageChops.multiply(g, hgrad),
            ImageChops.multiply(bc, hgrad),
            alpha,
        ))
    if highlight:
        hx, hy, radius_factor, strength = highlight
        glow = Image.new("L", (w, h), 0)
        cx, cy = round(hx * w), round(hy * h)
        radius = round(radius_factor * max(w, h))
        ImageDraw.Draw(glow).ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=round(strength * 255),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(max(1.0, radius * .4)))
        r, g, bc, alpha = surf.split()
        surf = Image.merge("RGBA", (
            ImageChops.add(r, glow),
            ImageChops.add(g, glow),
            ImageChops.add(bc, glow),
            alpha,
        ))
    surf.putalpha(mask)
    return surf


def _composite(work, mask, top, bottom, **kwargs):
    work.alpha_composite(_paint(mask, top, bottom, kwargs.get("right_shade", 0), kwargs.get("highlight")))


def _irregular_blob(mask, rng, cx, cy, rx, ry, lobes=18, fill=255, jitter=.18):
    points = []
    for i in range(lobes):
        angle = 2 * math.pi * i / lobes
        radius_jitter = 1 + rng.uniform(-jitter, jitter)
        points.append((
            round((cx + math.cos(angle) * rx * radius_jitter) * WORK_SCALE),
            round((cy + math.sin(angle) * ry * radius_jitter) * WORK_SCALE),
        ))
    ImageDraw.Draw(mask).polygon(points, fill=fill)


def _tapered_stroke(mask, p0, p1, p2, w0, w1, samples=42, fill=255):
    draw = ImageDraw.Draw(mask)
    for i in range(samples + 1):
        t = i / samples
        x, y = _quad(p0, p1, p2, t)
        width = _lerp(w0, w1, t) * WORK_SCALE
        radius = max(1, width * .5)
        x *= WORK_SCALE
        y *= WORK_SCALE
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _needle_tuft(mask, rng, cx, cy, scale, base_angle, fill=255, strokes=9):
    for k in range(strokes):
        offset = (k - (strokes - 1) / 2) / max(1, (strokes - 1) / 2)
        angle = base_angle + offset * rng.uniform(.20, .42) + rng.uniform(-.08, .08)
        length = scale * rng.uniform(.72, 1.18)
        width = max(.65, scale * rng.uniform(.10, .16))
        ex = cx + math.cos(angle) * length
        ey = cy + math.sin(angle) * length * .44 + abs(offset) * scale * .06
        _tapered_stroke(mask, (cx, cy), (_lerp(cx, ex, .52), _lerp(cy, ey, .52)), (ex, ey), width, .24, 15, fill)


def _conifer_branch(mask, rng, root, tip, width, droop, side, density=7, fill=255, tuft_strength=1.0):
    rx, ry = root
    tx, ty = tip
    ctrl = ((rx + tx) / 2, min(ry, ty) + droop)
    _tapered_stroke(mask, root, ctrl, tip, width, .45, 44, fill)
    base_angle = -.05 if side < 0 else math.pi + .05
    for j in range(1, density + 1):
        t = j / (density + 1)
        cx, cy = _quad(root, ctrl, tip, t)
        _irregular_blob(mask, rng, cx, cy, max(2.3, width * (.62 - .16 * t)), max(1.3, width * (.24 - .05 * t)), 10, fill, .12)
        _needle_tuft(mask, rng, cx, cy, max(4.4, width * (1.45 - .35 * t)) * tuft_strength, base_angle, fill, 7 if t > .45 else 9)


def _crown_masks_conifer(recipe, rng, W, H):
    tiers = recipe["tiers"]
    cx = recipe.get("crownCx", 96)
    back = Image.new("L", (W, H))
    core = Image.new("L", (W, H))
    mid = Image.new("L", (W, H))
    front = Image.new("L", (W, H))
    for tier in tiers:
        y = float(tier["y"])
        span = float(tier["span"])
        thick = float(tier["thickness"])
        skew = float(tier.get("skew", 0))
        _irregular_blob(core, rng, cx + skew, y + thick * .55, max(4.5, span * .12), thick * .60, 16, 255, .12)
        for side in (-1, 1):
            asym = 1 + rng.uniform(-.08, .08)
            for off, factor in ((-3.5, .96), (1.0, .82)):
                _conifer_branch(
                    back, rng, (cx + skew, y + off),
                    (cx + skew + side * span * factor * asym, y + thick * (.16 if off < 0 else .32)),
                    max(4.4, thick * .29), thick * (.02 if off < 0 else .10), side,
                    max(5, int(span / 12)), tuft_strength=.92,
                )
            for off, factor in ((0, .98), (4.0, .88)):
                _conifer_branch(
                    mid, rng, (cx + skew, y + off),
                    (cx + skew + side * span * factor * asym, y + thick * (.52 if off == 0 else .66)),
                    max(5.2, thick * .34), thick * (.18 if off == 0 else .24), side,
                    max(6, int(span / 10)), tuft_strength=1.02,
                )
            _conifer_branch(
                front, rng, (cx + skew, y + 3),
                (cx + skew + side * span * .76 * asym, y + thick * .90),
                max(4.7, thick * .31), thick * .31, side,
                max(5, int(span / 11)), tuft_strength=.98,
            )
    core = core.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(.08 * WORK_SCALE))
    back = back.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    mid = mid.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.05 * WORK_SCALE))
    front = front.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    return back, core, mid, front


def _leaf_cluster(mask, rng, cx, cy, rx, ry, lobes=11, jitter=.24, satellites=3, light_mask=None, dark_mask=None):
    """Paint one foliage cluster plus local highlight/shadow submasses.

    The broadleaf painter previously merged every cluster into one layer mask,
    which erased internal structure and produced flat foliage plates.  The
    optional accent masks preserve a readable hierarchy inside each cluster
    while keeping the silhouette deterministic and alpha-safe.
    """
    _irregular_blob(mask, rng, cx, cy, rx, ry, lobes, 255, jitter)

    if dark_mask is not None:
        _irregular_blob(
            dark_mask, rng,
            cx + rx * rng.uniform(.10, .26),
            cy + ry * rng.uniform(.12, .28),
            rx * rng.uniform(.34, .50),
            ry * rng.uniform(.24, .38),
            max(7, lobes - 3), 175, jitter + .03,
        )
    if light_mask is not None:
        _irregular_blob(
            light_mask, rng,
            cx - rx * rng.uniform(.08, .24),
            cy - ry * rng.uniform(.12, .30),
            rx * rng.uniform(.28, .46),
            ry * rng.uniform(.20, .34),
            max(7, lobes - 4), 155, jitter + .02,
        )

    for _ in range(satellites):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(.24, .62)
        sx = cx + math.cos(angle) * rx * distance
        sy = cy + math.sin(angle) * ry * distance
        srx = rx * rng.uniform(.24, .42)
        sry = ry * rng.uniform(.24, .44)
        _irregular_blob(mask, rng, sx, sy, srx, sry, max(7, lobes - 3), 255, jitter + .04)
        if light_mask is not None and sy < cy and rng.random() < .58:
            _irregular_blob(light_mask, rng, sx, sy, srx * .52, sry * .42, max(6, lobes - 5), 125, jitter + .04)
        if dark_mask is not None and sy >= cy and rng.random() < .62:
            _irregular_blob(dark_mask, rng, sx, sy, srx * .58, sry * .46, max(6, lobes - 5), 135, jitter + .04)


def _broadleaf_branch_group(mask, rng, root, tip, width, cluster_scale, density, view_phase, layer_bias=0.0, light_mask=None, dark_mask=None):
    """Lay discrete leaf clusters along an implied deciduous branch."""
    rx, ry = root
    tx, ty = tip
    lateral = math.sin(view_phase + rng.uniform(-.35, .35)) * cluster_scale * .22
    ctrl = (_lerp(rx, tx, .52) + lateral, _lerp(ry, ty, .48) - cluster_scale * .10 + layer_bias)

    for j in range(1, density + 1):
        t = j / (density + 1)
        cx, cy = _quad(root, ctrl, tip, t)
        side = -1 if j % 2 else 1
        tangent_x = _lerp(rx, tx, t)
        spread = cluster_scale * (1.0 - .14 * t)
        cx += side * spread * rng.uniform(.18, .44) + (cx - tangent_x) * .12
        cy += rng.uniform(-spread * .18, spread * .24)
        _leaf_cluster(
            mask, rng, cx, cy,
            spread * rng.uniform(.58, .82),
            spread * rng.uniform(.44, .68),
            rng.randint(9, 13), .24, rng.randint(3, 5),
            light_mask=light_mask, dark_mask=dark_mask,
        )
    _leaf_cluster(
        mask, rng, tx, ty,
        cluster_scale * rng.uniform(.74, .96),
        cluster_scale * rng.uniform(.58, .76),
        rng.randint(10, 14), .25, 5,
        light_mask=light_mask, dark_mask=dark_mask,
    )


def _crown_masks_broadleaf(recipe, rng, W, H, view="south"):
    """Build a rounded deciduous crown with preserved internal leaf groups."""
    tiers = recipe["tiers"]
    cx = float(recipe.get("crownCx", 96))
    phase = VIEW_PHASE.get(view, 0.0)
    cfg = recipe.get("broadleafStructure", {})
    branch_density = max(3, int(cfg.get("clustersPerBranch", 5)))
    branch_groups = max(2, int(cfg.get("branchGroupsPerTier", 3)))
    cluster_factor = float(cfg.get("clusterScale", .22))
    back = Image.new("L", (W, H))
    core = Image.new("L", (W, H))
    mid = Image.new("L", (W, H))
    front = Image.new("L", (W, H))
    cluster_light = Image.new("L", (W, H))
    cluster_dark = Image.new("L", (W, H))

    for tier_index, tier in enumerate(tiers):
        y = float(tier["y"])
        span = float(tier["span"])
        thick = float(tier["thickness"])
        skew = float(tier.get("skew", 0))
        tcx = cx + skew

        _leaf_cluster(core, rng, tcx, y + thick * .24, span * .22, thick * .31, 13, .17, 4)

        for group in range(branch_groups):
            angle_phase = phase + tier_index * .51 + group * (math.tau / branch_groups)
            side = -1 if math.cos(angle_phase) < 0 else 1
            depth = math.sin(angle_phase)
            lateral = math.cos(angle_phase)
            visible_span = span * (.48 + .30 * abs(lateral))
            tip_x = tcx + side * visible_span * rng.uniform(.76, 1.02)
            tip_y = y + thick * (.18 + .28 * ((depth + 1) * .5)) + rng.uniform(-2.2, 2.2)
            root = (tcx + rng.uniform(-span * .07, span * .07), y + thick * .28)
            scale = max(6.0, min(span, thick) * cluster_factor * rng.uniform(.88, 1.20))
            target = back if depth < -.24 else front if depth > .24 else mid
            _broadleaf_branch_group(
                target, rng, root, (tip_x, tip_y), max(1.4, thick * .045),
                scale, branch_density, phase, layer_bias=depth * 1.8,
                light_mask=cluster_light if depth >= -.12 else None,
                dark_mask=cluster_dark if depth >= -.35 else None,
            )

        bridge_count = max(4, branch_groups // 2)
        for _ in range(bridge_count):
            ox = rng.uniform(-span * .50, span * .50)
            oy = rng.uniform(-thick * .16, thick * .48)
            target = back if oy < 0 else front if oy > thick * .22 else mid
            _leaf_cluster(
                target, rng, tcx + ox, y + oy,
                span * rng.uniform(.09, .15),
                thick * rng.uniform(.12, .20),
                rng.randint(9, 13), .25, rng.randint(2, 4),
                light_mask=cluster_light if oy >= 0 else None,
                dark_mask=cluster_dark,
            )

    core = core.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.045 * WORK_SCALE))
    back = back.filter(ImageFilter.GaussianBlur(.020 * WORK_SCALE))
    mid = mid.filter(ImageFilter.GaussianBlur(.018 * WORK_SCALE))
    front = front.filter(ImageFilter.GaussianBlur(.016 * WORK_SCALE))
    cluster_light = cluster_light.filter(ImageFilter.GaussianBlur(.010 * WORK_SCALE))
    cluster_dark = cluster_dark.filter(ImageFilter.GaussianBlur(.012 * WORK_SCALE))
    return back, core, mid, front, cluster_dark, cluster_light


def _mix_color(a, b, amount):
    amount = max(0.0, min(1.0, amount))
    return "#" + "".join(f"{round(x * (1 - amount) + y * amount):02X}"
                         for x, y in zip(_hex(a), _hex(b)))


def _paint_broadleaf_volume(work, recipe, rng, palette, W, H, view):
    """Paint separate leaf mounds across one crown envelope, not tier shelves.

    This is opt-in: older broadleaf recipes keep their exact raster output.
    Rotations shift the mound positions in world space; light stays upper-left
    in the camera. Every mound has a local shadow and clipped sunlit cap.
    """
    cfg = recipe.get("broadleafStructure", {})
    center = cfg.get("center", [recipe.get("crownCx", 96), 119])
    radius = cfg.get("radius", [71, 76])
    cx, cy = map(float, center)
    rx, ry = map(float, radius)
    phase = VIEW_PHASE[view]
    base = Image.new("L", (W, H))
    _irregular_blob(base, rng, cx, cy, rx * .91, ry * .91, 31, 255, .10)
    _composite(work, base, palette["back_top"], palette["back_bottom"], right_shade=.12)

    # A staggered canopy makes occupancy predictable at 1x; jitter keeps it
    # organic. Overlapping mounds remain individually shaded after compositing.
    rows = (-.75, -.52, -.28, -.04, .20, .44, .68)
    masses = max(1, min(90, int(cfg.get("masses", 43))))
    placed = []
    for row in rows:
        half = math.sqrt(max(0.0, 1.0 - row * row))
        count = max(3, round(masses * (1.0 + .23 * half) / len(rows)))
        for index in range(count):
            x_norm = ((index + .5 + (.24 if row > 0 else -.18)) / count * 2 - 1) * half
            x_norm += rng.uniform(-.11, .11)
            y_norm = row + rng.uniform(-.095, .095)
            # The world-space phase moves identifiable groups between views.
            x_norm += .035 * math.sin(phase + index * .8)
            px = cx + rx * x_norm
            py = cy + ry * y_norm
            size = rng.uniform(.78, 1.16)
            placed.append((py, px, 10.5 * size, 9.1 * size, y_norm))
    placed.sort()

    for py, px, sx, sy, vertical in placed:
        leaf = Image.new("L", (W, H))
        _leaf_cluster(leaf, rng, px, py, sx, sy, 11, .20, 2)
        # Olive undersides anchor the canopy; warm patches occupy the lighted
        # tops, leaving gaps and darker interior between discrete masses.
        autumn = rng.uniform(.66, .97) if vertical < -.18 else (
            rng.uniform(.40, .78) if vertical < .30 else rng.uniform(.20, .52))
        upper = _mix_color(palette["mid_top"], palette["front_top"], autumn)
        lower = _mix_color(palette["mid_bottom"], palette["front_bottom"], autumn * .76)
        _composite(work, leaf, upper, lower, right_shade=.08)

        shade = Image.new("L", (W, H))
        _irregular_blob(shade, rng, px + sx * .30, py + sy * .39,
                        sx * .66, sy * .42, 9, 95, .19)
        shade = ImageChops.multiply(shade, leaf)
        _composite(work, shade, palette["occlusion"], palette["back_bottom"])

        if rng.random() < (.72 if vertical < .18 else .38):
            light = Image.new("L", (W, H))
            _irregular_blob(light, rng, px - sx * .24, py - sy * .39,
                            sx * .62, sy * .39, 9, 130, .17)
            light = ImageChops.multiply(light, leaf)
            _composite(work, light, palette["highlight"], upper)


def _paint_broadleaf_groups_legacy(work, recipe, rng, palette, W, H, view):
    """Paint a few overlapping foliage groups instead of isolated leaf balls.

    `domed` has a continuous dark interior and irregular lit crown lobes;
    `branching` follows the authored branches and preserves open sky gaps.
    Existing layouts never enter this opt-in painter.
    """
    cfg = recipe["broadleafStructure"]
    cx, cy = map(float, cfg["center"])
    rx, ry = map(float, cfg["radius"])
    profile = cfg.get("profile", "domed")
    if profile not in ("domed", "branching"):
        raise ValueError("crown_groups profile must be domed or branching")
    phase = VIEW_PHASE[view]

    if profile == "domed":
        interior = Image.new("L", (W, H))
        _irregular_blob(interior, rng, cx, cy, rx * .93, ry * .86, 29, 255, .13)
        _composite(work, interior, palette["back_top"], palette["back_bottom"], right_shade=.12)
        # Staggered lobes overlap the dark crown. They read as several large
        # organic volumes rather than a uniform grid of tiny circular leaves.
        rows = ((-.55, 3), (-.18, 4), (.19, 4), (.53, 3))
        groups = []
        for row_index, (height, count) in enumerate(rows):
            extent = math.sqrt(1.0 - height * height)
            for index in range(count):
                x = ((index + .5 + (.20 if row_index % 2 else -.12)) / count * 2 - 1) * extent
                x += rng.uniform(-.13, .13) + .045 * math.sin(phase + index)
                y = height + rng.uniform(-.12, .12)
                scale = rng.uniform(.84, 1.23)
                groups.append((cx + rx * x, cy + ry * y, rx * .34 * scale,
                               ry * .24 * scale, y))
    else:
        branches = recipe.get("trunkBranches", [])[1:]
        if not branches:
            raise ValueError("branching crown_groups needs authored trunkBranches")
        groups = []
        for branch in branches:
            tip_x, tip_y = map(float, branch["p2"])
            root_x, root_y = map(float, branch["p0"])
            dx, dy = tip_x - root_x, tip_y - root_y
            for along in (.70, .92, 1.10):
                x = root_x + dx * along + rng.uniform(-7, 7)
                y = root_y + dy * along + rng.uniform(-9, 9)
                x += 2.5 * math.sin(phase + along * 5)
                scale = rng.uniform(.82, 1.16)
                groups.append((x, y, rx * .25 * scale, ry * .17 * scale,
                               (y - cy) / ry))
        # A few interior leaf groups connect the fork visually without
        # painting an opaque ball across the negative spaces.
        for _ in range(3):
            groups.append((cx + rng.uniform(-rx * .35, rx * .35),
                           cy + rng.uniform(-ry * .18, ry * .34),
                           rx * .20, ry * .14, .25))

    density = max(.55, min(1.45, float(cfg.get("density", 1.0))))
    groups.sort(key=lambda group: group[1])
    for gx, gy, gw, gh, vertical in groups:
        gw *= math.sqrt(density)
        gh *= math.sqrt(density)
        # A lumpy underpainting remains visible at the lower/right edge.
        mask = Image.new("L", (W, H))
        _leaf_cluster(mask, rng, gx, gy, gw, gh, 21, .23, 3)
        warmth = (.61 if vertical < 0 else .40) + rng.uniform(-.14, .14)
        top = _mix_color(palette["mid_top"], palette["front_top"], warmth)
        bottom = _mix_color(palette["mid_bottom"], palette["front_bottom"], warmth * .72)
        _composite(work, mask, top, bottom, right_shade=.10)

        shade = Image.new("L", (W, H))
        _irregular_blob(shade, rng, gx + gw * .30, gy + gh * .38,
                        gw * .60, gh * .38, 13, 52, .25)
        shade = ImageChops.multiply(shade, mask)
        _composite(work, shade, palette["occlusion"], palette["back_bottom"])

        highlight = Image.new("L", (W, H))
        if rng.random() < .72:
            _irregular_blob(highlight, rng, gx - gw * .30, gy - gh * .35,
                            gw * .47, gh * .38, 15, 62 if vertical > .42 else 86, .26)
        highlight = ImageChops.multiply(highlight, mask)
        _composite(work, highlight, palette["highlight"], top)

        # Small, low-contrast leaf strokes live inside each mass. They give
        # the painterly surface texture without a repeated ring of bubbles.
        texture = Image.new("RGBA", (W, H))
        count = round((14 if profile == "domed" else 20) * density)
        _scatter_texture(texture, rng, mask, palette["highlight"], count,
                         (14, 36), (.7, 1.8), 1.5)
        work.alpha_composite(texture)


def _cloud_mask(size, rng, cx, cy, rx, ry, scallops=11):
    """A fused, softly scalloped leaf envelope; no polygon facets or rows."""
    mask = Image.new("L", size)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(((cx - rx * .84) * WORK_SCALE, (cy - ry * .85) * WORK_SCALE,
                  (cx + rx * .84) * WORK_SCALE, (cy + ry * .85) * WORK_SCALE), fill=255)
    for i in range(scallops):
        angle = math.tau * (i + rng.uniform(-.32, .32)) / scallops
        x = cx + math.cos(angle) * rx * rng.uniform(.64, .78)
        y = cy + math.sin(angle) * ry * rng.uniform(.67, .83)
        sx = rx * rng.uniform(.23, .37)
        sy = ry * rng.uniform(.20, .34)
        draw.ellipse(((x - sx) * WORK_SCALE, (y - sy) * WORK_SCALE,
                      (x + sx) * WORK_SCALE, (y + sy) * WORK_SCALE), fill=255)
    # Fuse the joins at working resolution, then restore a clean alpha edge.
    return mask.filter(ImageFilter.GaussianBlur(1.0 * WORK_SCALE)).point(
        lambda alpha: 255 if alpha > 92 else 0)


def _foliage_paint(work, mask, rng, palette, center, radius, *, open_crown=False):
    """Layer foliage strokes within a shared silhouette, not shaded balls."""
    cx, cy = center
    rx, ry = radius
    W, H = mask.size
    _composite(work, mask, palette["mid_top"], palette["mid_bottom"], right_shade=.13)
    # Large, transparent underpaint establishes volumes without drawing a
    # circular border around each patch. Top left receives the warmest light.
    shade = Image.new("L", (W, H))
    light = Image.new("L", (W, H))
    for i in range(16 if not open_crown else 5):
        x = cx + rng.uniform(-.80, .80) * rx
        y = cy + rng.uniform(-.68, .68) * ry
        sx = rx * rng.uniform(.17, .35)
        sy = ry * rng.uniform(.16, .31)
        target = light if x < cx + rx * .15 and y < cy + ry * .20 and i % 3 else shade
        _irregular_blob(target, rng, x, y, sx, sy, 13, rng.randint(75, 125), .23)
    _composite(work, ImageChops.multiply(shade, mask), palette["occlusion"], palette["mid_bottom"])
    _composite(work, ImageChops.multiply(light, mask), palette["front_top"], palette["mid_top"])

    # Irregular overlapping leaflets are painted with low contrast and no
    # per-leaf dark ring. Their scale is small enough to survive gameplay 1x.
    patches = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(patches, "RGBA")
    count = 560 if not open_crown else 100
    colors = [palette["mid_top"], palette["front_top"], palette["front_bottom"],
              palette["highlight"], palette["mid_bottom"]]
    alpha = mask.load()
    for _ in range(count):
        x = cx + rng.uniform(-.97, .97) * rx
        y = cy + rng.uniform(-.96, .96) * ry
        px, py = round(x * WORK_SCALE), round(y * WORK_SCALE)
        if not 0 <= px < W or not 0 <= py < H or alpha[px, py] < 200:
            continue
        sx = rng.uniform(3.5, 10.0) * (1.05 if not open_crown else .90)
        sy = sx * rng.uniform(.48, .86)
        choice = rng.randrange(len(colors))
        if choice == 3 and (y > cy or x > cx + rx * .35):
            choice = 0
        points = [((x + math.cos(a) * sx * rng.uniform(.72, 1.15)) * WORK_SCALE,
                   (y + math.sin(a) * sy * rng.uniform(.72, 1.15)) * WORK_SCALE)
                  for a in (0, .95, 2.2, 3.4, 4.7, 5.5)]
        draw.polygon(points, fill=(*_hex(colors[choice]), rng.randint(165, 235)))
    clipped = ImageChops.multiply(patches.getchannel("A"), mask)
    patches.putalpha(clipped)
    work.alpha_composite(patches)


def _paint_broadleaf_groups(work, recipe, rng, palette, W, H, view):
    """A dense domed canopy or separate branch borne leaf clouds."""
    cfg = recipe["broadleafStructure"]
    cx, cy = map(float, cfg["center"])
    rx, ry = map(float, cfg["radius"])
    profile = cfg.get("profile", "domed")
    if profile not in ("domed", "branching"):
        raise ValueError("crown_groups profile must be domed or branching")
    phase = VIEW_PHASE[view]
    density = max(.55, min(1.45, float(cfg.get("density", 1.0))))
    if profile == "domed":
        mask = _cloud_mask((W, H), rng, cx, cy, rx * math.sqrt(density),
                           ry * math.sqrt(density), scallops=24)
        _foliage_paint(work, mask, rng, palette, (cx, cy), (rx, ry))
        return

    branches = recipe.get("trunkBranches", [])[1:]
    if not branches:
        raise ValueError("branching crown_groups needs authored trunkBranches")
    interior = _cloud_mask((W, H), rng, cx, cy + ry * .02,
                           rx * .50 * math.sqrt(density), ry * .55 * math.sqrt(density),
                           scallops=13)
    _foliage_paint(work, interior, rng, palette, (cx, cy + ry * .02),
                   (rx * .50, ry * .55), open_crown=True)
    # Each branch ends in its own leaf volume. The open sky between volumes
    # and the tapered wood below them make the structure readable at 1x.
    groups = []
    for index, branch in enumerate(branches):
        root = tuple(map(float, branch["p0"]))
        control = tuple(map(float, branch["p1"]))
        tip = tuple(map(float, branch["p2"]))
        for step, along in enumerate((.62, 1.0)):
            x, y = _quad(root, control, tip, along)
            x += math.sin(phase + index * 1.9 + step) * 2.7 + rng.uniform(-4, 4)
            y += math.cos(phase + index * 1.1 + step) * 1.6 + rng.uniform(-4, 4)
            size = (.91 + rng.uniform(-.16, .16)) * math.sqrt(density)
            groups.append((x, y, (22 + (index % 3) * 2) * size,
                           (18 + (index % 2) * 2) * size))
    groups.sort(key=lambda group: group[1])
    for x, y, sx, sy in groups:
        mask = _cloud_mask((W, H), rng, x, y, sx, sy, scallops=10)
        _foliage_paint(work, mask, rng, palette, (x, y), (sx, sy), open_crown=True)


def _draw_leaflet(draw, x, y, length, width, angle, color, opacity):
    """A small tapered leaf at supersampled resolution."""
    dx, dy = math.cos(angle), math.sin(angle)
    nx, ny = -dy, dx
    points = [((x - dx * length * .5) * WORK_SCALE, (y - dy * length * .5) * WORK_SCALE),
              ((x - dx * length * .08 + nx * width) * WORK_SCALE,
               (y - dy * length * .08 + ny * width) * WORK_SCALE),
              ((x + dx * length * .43 + nx * width * .38) * WORK_SCALE,
               (y + dy * length * .43 + ny * width * .38) * WORK_SCALE),
              ((x + dx * length * .62) * WORK_SCALE, (y + dy * length * .62) * WORK_SCALE),
              ((x + dx * length * .27 - nx * width * .76) * WORK_SCALE,
               (y + dy * length * .27 - ny * width * .76) * WORK_SCALE)]
    draw.polygon(points, fill=(*_hex(color), opacity))


def _paint_species_foliage(work, mask, rng, palette, center, radius, species):
    """Species leaf detail on top of a readable shaded canopy volume."""
    cx, cy = center
    rx, ry = radius
    W, H = mask.size
    layer = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(layer, "RGBA")
    pixels = mask.load()
    if species == "oiti":
        # Wider, simple leaves overlap. Young yellow-green growth stays near
        # the upper lit edge; mature foliage holds the cool dark interior.
        for _ in range(340):
            x = cx + rng.uniform(-.99, .99) * rx
            y = cy + rng.uniform(-.98, .98) * ry
            ix, iy = round(x * WORK_SCALE), round(y * WORK_SCALE)
            if not 0 <= ix < W or not 0 <= iy < H or pixels[ix, iy] < 220:
                continue
            lit = x < cx + rx * .25 and y < cy + ry * .22
            roll = rng.random()
            color = (palette["highlight"] if lit and roll < .15 else
                     palette["front_top"] if lit and roll < .58 else
                     palette["mid_top"] if y < cy or roll < .45 else palette["front_bottom"])
            _draw_leaflet(draw, x, y, rng.uniform(4.7, 8.7), rng.uniform(1.7, 3.3),
                          rng.uniform(-.75, .55), color, rng.randint(100, 175))
    else:
        # Paired leaflets along fine curved sprays suggest the bipinnate leaf
        # without drawing subpixel botanical detail that disappears at 1x.
        for _ in range(13):
            x = cx + rng.uniform(-.65, .65) * rx
            y = cy + rng.uniform(-.62, .62) * ry
            theta = rng.uniform(-2.8, .2)
            length = rng.uniform(8.0, 14.0)
            dx, dy = math.cos(theta), math.sin(theta)
            endpoint = (x + dx * length, y + dy * length)
            twig = _hex(palette["mid_bottom"])
            draw.line(((x * WORK_SCALE, y * WORK_SCALE),
                       (endpoint[0] * WORK_SCALE, endpoint[1] * WORK_SCALE)),
                      fill=(*twig, 80), width=max(1, round(.55 * WORK_SCALE)))
            for pair in range(1, 6):
                t = pair / 6
                for side in (-1, 1):
                    leaf_x = x + dx * length * t + (-dy) * side * 1.9
                    leaf_y = y + dy * length * t + dx * side * 1.9
                    lit = leaf_x < cx + rx * .12 and leaf_y < cy + ry * .10
                    color = (palette["highlight"] if lit and rng.random() < .18 else
                             palette["front_top"] if lit else palette["mid_top"])
                    _draw_leaflet(draw, leaf_x, leaf_y, rng.uniform(2.8, 4.2),
                                  rng.uniform(.72, 1.15), theta + side * 1.15,
                                  color, rng.randint(90, 160))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    work.alpha_composite(layer)


def _paint_species_canopy(work, recipe, rng, palette, W, H, view):
    """Species-aware crowns; older painted_canopy recipes keep their raster."""
    cfg = recipe["broadleafStructure"]
    cx, cy = map(float, cfg["center"])
    rx, ry = map(float, cfg["radius"])
    species = cfg.get("species")
    if species not in ("oiti", "angico"):
        raise ValueError("species_canopy requires species oiti or angico")
    density = max(.55, min(1.45, float(cfg.get("density", 1.0))))
    phase = VIEW_PHASE[view]
    if species == "oiti":
        # Seed-dependent irregularity lets a forest contain related trees
        # without repeated cutout silhouettes. A small world-facing offset
        # lets the four camera turns reveal different sides of a dense crown.
        cx += rng.uniform(-3.5, 3.5) + math.cos(phase + .35) * 3.4
        cy += rng.uniform(-2.5, 2.5) + math.sin(phase + .35) * 2.0
        rx *= rng.uniform(.94, 1.04) * (1 + .027 * math.cos(phase + .8)) * math.sqrt(density)
        ry *= rng.uniform(.96, 1.05) * (1 + .023 * math.sin(phase + .4)) * math.sqrt(density)
        silhouette = _cloud_mask((W, H), rng, cx, cy, rx, ry, scallops=19)
        _foliage_paint(work, silhouette, rng, palette, (cx, cy), (rx, ry))
        _paint_species_foliage(work, silhouette, rng, palette, (cx, cy), (rx, ry), species)
        return

    if not recipe.get("trunkBranches", [])[1:]:
        raise ValueError("angico species_canopy needs authored trunkBranches")
    # Preserve the broad, irregular forked structure. Fine paired leaflets
    # are applied after it is readable in 1x, rather than replacing the crown
    # with a row of translucent, disconnected foliage balls.
    _paint_broadleaf_groups(work, recipe, rng, palette, W, H, view)
    detail_rng = random.Random(int(recipe["seed"]) ^ (0xA691C0 + round(phase * 100)))
    occupied = work.getchannel("A")
    for x, y, sx, sy in ((cx - rx * .43, cy - ry * .10, rx * .45, ry * .51),
                         (cx + rx * .03, cy - ry * .29, rx * .43, ry * .48),
                         (cx + rx * .43, cy - ry * .06, rx * .45, ry * .50)):
        _paint_species_foliage(work, occupied, detail_rng, palette,
                               (x, y), (sx, sy), species)


def _scatter_texture(layer, rng, mask, color, count, alpha_range=(12, 36), size_range=(.45, 1.7), elongate=2.0):
    bbox = mask.getbbox()
    if not bbox:
        return
    draw = ImageDraw.Draw(layer, "RGBA")
    pixels = mask.load()
    col = _hex(color)
    coords = [(x, y) for y in range(bbox[1], bbox[3]) for x in range(bbox[0], bbox[2]) if pixels[x, y] > 120]
    if not coords:
        return
    for _ in range(count):
        x, y = rng.choice(coords)
        radius = rng.uniform(*size_range) * WORK_SCALE
        alpha = rng.randint(*alpha_range)
        dx = rng.uniform(-.4, .2) * radius
        dy = rng.uniform(-.2, .35) * radius
        draw.ellipse(
            (x - radius * elongate + dx, y - radius * .38 + dy, x + radius * .35 + dx, y + radius * .38 + dy),
            fill=(*col, alpha),
        )


def _final_raster_pass(frame, rng, palette, recipe):
    out = frame.convert("RGBA")
    alpha = out.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return out
    pixels = alpha.load()
    draw = ImageDraw.Draw(out, "RGBA")
    dark = _hex(palette.get("occlusion", "#123B30"))
    light = _hex(palette["highlight"])
    cfg = recipe.get("raster", {})
    grain = int(cfg.get("finalGrain", 620))
    needles = int(cfg.get("finalNeedles", 300))
    bx0, by0, bx1, by1 = bbox
    for _ in range(grain):
        x = rng.randint(bx0, bx1 - 1)
        y = rng.randint(by0, by1 - 1)
        if pixels[x, y] <= 170:
            continue
        col, a = (dark, rng.randint(12, 28)) if rng.random() < .58 else (light, rng.randint(9, 24))
        draw.point((x, y), fill=(*col, a))
    for _ in range(needles):
        x = rng.randint(bx0, bx1 - 1)
        y = rng.randint(by0, by1 - 1)
        if pixels[x, y] <= 190:
            continue
        length = rng.choice([2, 2, 3, 3, 4])
        col = light if rng.random() < .58 else dark
        draw.line((x, y, x - length, y + rng.choice([0, 0, 1])), fill=(*col, rng.randint(18, 48)), width=1)
    return out.filter(ImageFilter.UnsharpMask(radius=.65, percent=115, threshold=3))


def _draw_trunk_and_bark(work, recipe, palette, W, H):
    anchor = recipe.get("anchor", [96, 239])
    base_x, base_y = anchor
    trunk = Image.new("L", (W, H))
    branches = recipe.get("trunkBranches")
    if branches:
        for branch in branches:
            p0 = tuple(branch["p0"])
            p1 = tuple(branch.get("p1", p0))
            p2 = tuple(branch["p2"])
            _tapered_stroke(trunk, p0, p1, p2, float(branch.get("w0", 8)), float(branch.get("w1", 4)), 44, 255)
    else:
        tw = float(recipe.get("trunkWidth", 20))
        top_y = float(recipe.get("trunkTopY", 120))
        cx = float(base_x)
        ImageDraw.Draw(trunk).polygon([
            ((cx - tw * .45) * WORK_SCALE, top_y * WORK_SCALE),
            ((cx + tw * .45) * WORK_SCALE, (top_y + 2) * WORK_SCALE),
            ((cx + tw * .55) * WORK_SCALE, base_y * WORK_SCALE),
            ((cx - tw * .55) * WORK_SCALE, base_y * WORK_SCALE),
        ], fill=255)
    _composite(work, trunk, palette["trunk_top"], palette["trunk_bottom"], right_shade=.22, highlight=(.41, .48, .28, .15))
    bark = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(bark, "RGBA")
    color = _hex(palette.get("trunk_light", "#DCA066"))
    for offset in (-4, 0, 4):
        draw.line(
            ((base_x + offset) * WORK_SCALE, (base_y - 70) * WORK_SCALE,
             (base_x + offset - 1) * WORK_SCALE, (base_y - 8) * WORK_SCALE),
            fill=(*color, 70), width=round(1.8 * WORK_SCALE),
        )
    work.alpha_composite(bark)


def render(recipe, view="south"):
    if recipe.get("contract") != CONTRACT:
        raise ValueError(f"recipe must declare {CONTRACT}")
    if recipe.get("camera", {}).get("contract") != CAMERA_CONTRACT:
        raise ValueError("organic gameplay scenery must declare CH_CAMERA_V1")
    if recipe["camera"].get("tile") != [128, 64]:
        raise ValueError("CH_CAMERA_V1 review requires 128x64 tile")
    if view not in VALID_VIEWS:
        raise ValueError(f"view must be one of {VALID_VIEWS}")

    canvas = recipe.get("canvas", [192, 256])
    anchor = recipe.get("anchor", [96, 239])
    seed = int(recipe.get("seed", 1))
    rng = random.Random(seed)
    W, H = canvas[0] * WORK_SCALE, canvas[1] * WORK_SCALE
    palette = recipe["palette"]
    work = Image.new("RGBA", (W, H))

    shadow = Image.new("L", (W, H))
    sw = recipe.get("shadowWidth", 94)
    ImageDraw.Draw(shadow).ellipse(
        ((anchor[0] - sw // 2) * WORK_SCALE, (anchor[1] - 9) * WORK_SCALE,
         (anchor[0] + sw // 2) * WORK_SCALE, (anchor[1] + 5) * WORK_SCALE),
        fill=145,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(2.4 * WORK_SCALE))
    sh = Image.new("RGBA", (W, H), (*_hex(palette["ground_shadow"]), 0))
    sh.putalpha(shadow)
    work.alpha_composite(sh)

    _draw_trunk_and_bark(work, recipe, palette, W, H)

    crown_style = recipe.get("crownStyle", "conifer")
    layout = recipe.get("broadleafStructure", {}).get("layout")
    if crown_style == "broadleaf" and layout in ("continuous", "crown_groups", "painted_canopy", "species_canopy"):
        painter = {"continuous": _paint_broadleaf_volume,
                   "crown_groups": _paint_broadleaf_groups_legacy,
                   "painted_canopy": _paint_broadleaf_groups,
                   "species_canopy": _paint_species_canopy}[layout]
        painter(work, recipe, rng, palette, W, H, view)
        frame = _alpha_safe_resize(work, tuple(canvas))
        frame = _final_raster_pass(frame, rng, palette, recipe)
        bounds = frame.getchannel("A").getbbox()
        return frame, {
            "contract": CONTRACT, "id": recipe["id"], "canvas": canvas,
            "anchor": anchor, "bounds": list(bounds), "seed": seed,
            "crownStyle": crown_style, "view": view,
            "yawDeg": int(recipe.get("rotation", {}).get("yawDeg", {}).get(view, DEFAULT_YAWS[view])),
            "camera": recipe["camera"], "raster": recipe.get("raster", {}),
            "runtimePromotion": False, "artApproved": False,
        }
    cluster_dark = cluster_light = None
    if crown_style == "broadleaf":
        back, core, mid, front, cluster_dark, cluster_light = _crown_masks_broadleaf(recipe, rng, W, H, view)
    elif crown_style == "conifer":
        back, core, mid, front = _crown_masks_conifer(recipe, rng, W, H)
    else:
        raise ValueError(f"Unknown crownStyle {crown_style!r}; choose 'conifer' or 'broadleaf'")

    _composite(work, back, palette["back_top"], palette["back_bottom"], right_shade=.25, highlight=(.32, .21, .42, .05))
    _composite(work, core, palette["mid_bottom"], palette["back_bottom"], right_shade=.22, highlight=(.31, .27, .50, .05))
    _composite(work, mid, palette["mid_top"], palette["mid_bottom"], right_shade=.19, highlight=(.29, .30, .50, .10))
    texture = Image.new("RGBA", (W, H))
    _scatter_texture(texture, rng, mid, palette.get("occlusion", "#123B30"), int(recipe.get("raster", {}).get("shadowDabs", 300)), (10, 34), (.5, 1.8), 2.3)
    work.alpha_composite(texture)
    _composite(work, front, palette["front_top"], palette["front_bottom"], right_shade=.16, highlight=(.27, .36, .48, .14))

    if cluster_dark is not None:
        _composite(
            work, cluster_dark,
            palette.get("leaf_shadow_top", palette.get("mid_bottom", palette["back_top"])),
            palette.get("leaf_shadow_bottom", palette.get("occlusion", palette["back_bottom"])),
            right_shade=.10,
        )
    if cluster_light is not None:
        _composite(
            work, cluster_light,
            palette.get("leaf_light_top", palette["highlight"]),
            palette.get("leaf_light_bottom", palette.get("front_top", palette["highlight"])),
            right_shade=.06,
            highlight=(.26, .30, .34, .08),
        )

    highlights = Image.new("RGBA", (W, H))
    _scatter_texture(highlights, rng, front, palette["highlight"], int(recipe.get("raster", {}).get("highlightDabs", 260)), (8, 30), (.45, 1.45), 2.4)
    work.alpha_composite(highlights)

    frame = _alpha_safe_resize(work, tuple(canvas))
    frame = _final_raster_pass(frame, rng, palette, recipe)
    bounds = frame.getchannel("A").getbbox()
    return frame, {
        "contract": CONTRACT,
        "id": recipe["id"],
        "canvas": canvas,
        "anchor": anchor,
        "bounds": list(bounds),
        "seed": seed,
        "crownStyle": crown_style,
        "view": view,
        "yawDeg": int(recipe.get("rotation", {}).get("yawDeg", {}).get(view, DEFAULT_YAWS[view])),
        "camera": recipe["camera"],
        "raster": recipe.get("raster", {}),
        "runtimePromotion": False,
        "artApproved": False,
    }


def review_board(frame):
    w, h = frame.size
    board = Image.new("RGBA", (w * 3 + 48, h * 2 + 40), (76, 116, 48, 255))
    board.alpha_composite(frame, (16, 20 + h // 2))
    board.alpha_composite(frame.resize((w * 2, h * 2), Image.Resampling.NEAREST), (w + 32, 20))
    draw = ImageDraw.Draw(board)
    draw.text((16, 4), "1x / gameplay", fill=(247, 244, 220, 255))
    draw.text((w + 32, 4), "2x / inspection", fill=(247, 244, 220, 255))
    return board


def isometric_board(frame, anchor, label="CH_CAMERA_V1 / 30deg / 45deg yaw / 128x64"):
    board = Image.new("RGBA", (768, 480), (46, 77, 55, 255))
    draw = ImageDraw.Draw(board)
    gx, gy = 384, 314
    hw, hh = 64, 32
    for x in range(-3, 4):
        for y in range(-3, 4):
            cx = gx + (x - y) * hw
            cy = gy + (x + y) * hh
            poly = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
            fill = (76, 119, 66, 255) if (x + y) % 2 == 0 else (71, 113, 64, 255)
            draw.polygon(poly, fill=fill, outline=(105, 148, 93, 205))
    draw.polygon([(gx, gy - hh), (gx + hw, gy), (gx, gy + hh), (gx - hw, gy)], fill=(82, 132, 72, 255), outline=(174, 207, 145, 255))
    board.alpha_composite(frame, (round(gx - anchor[0]), round(gy - anchor[1])))
    draw.ellipse((gx - 3, gy - 3, gx + 3, gy + 3), fill=(255, 224, 132, 255))
    draw.text((18, 16), label, fill=(247, 244, 220, 255))
    draw.text((18, 36), "CH_2D_ORGANIC_SCENERY_V1 / gameplay 1x", fill=(220, 232, 205, 255))
    return board


def _resolve_finish_recipe(recipe_path: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_file():
        return candidate
    for parent in [recipe_path.parent, *recipe_path.parents]:
        resolved = parent / candidate
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"finishRecipe not found: {value}")


def _finish_one(source: Path, destination: Path, finish_recipe: Path, comparison: Path | None = None):
    if source != destination:
        destination.write_bytes(source.read_bytes())
    temporary = destination.with_name(destination.stem + ".finished.tmp.png")
    result = finish_render(destination, temporary, finish_recipe, comparison)
    temporary.replace(destination)
    return result


def export(recipe_path, output_dir):
    raw = recipe_path.read_bytes()
    recipe = json.loads(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = recipe["id"]
    rotation = recipe.get("rotation", {})
    views = rotation.get("views", ["south"])
    if not views or any(view not in VALID_VIEWS for view in views):
        raise ValueError(f"rotation views must be a non-empty subset of {VALID_VIEWS}")
    mode = rotation.get("mode", "single")
    finish_recipe = _resolve_finish_recipe(recipe_path, recipe["finishRecipe"]) if recipe.get("finishRecipe") else None
    slots = {}
    first_meta = None
    for view in views:
        frame, meta = render(recipe, view=view)
        first_meta = first_meta or meta
        source = output_dir / f"{stem}_{view}_source.png"
        final = output_dir / f"{stem}_{view}.png"
        frame.save(source)
        finish_result = None
        if finish_recipe:
            finish_result = _finish_one(source, final, finish_recipe, output_dir / f"{stem}_{view}_finish_review.png")
        else:
            final.write_bytes(source.read_bytes())
        with Image.open(final) as image:
            finished = image.convert("RGBA")
        review_board(finished).save(output_dir / f"{stem}_{view}_review.png")
        isometric_board(finished, meta["anchor"], f"CH_CAMERA_V1 / {view} / yaw {meta['yawDeg']} / 128x64").save(output_dir / f"{stem}_{view}_isometric_review.png")
        slots[view] = {
            "path": str(final),
            "source": str(source),
            "yawDeg": meta["yawDeg"],
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "finish": finish_result,
        }
    canonical_view = "south" if "south" in slots else views[0]
    canonical = output_dir / f"{stem}.png"
    canonical.write_bytes(Path(slots[canonical_view]["path"]).read_bytes())
    with Image.open(canonical) as image:
        final = image.convert("RGBA")
    review = output_dir / f"{stem}_review.png"
    iso = output_dir / f"{stem}_isometric_review.png"
    review_board(final).save(review)
    isometric_board(final, first_meta["anchor"]).save(iso)
    manifest = {
        "contract": ROTATION_CONTRACT,
        "id": stem,
        "mode": mode,
        "lightingSpace": rotation.get("lightingSpace", "screen_camera_relative"),
        "generatedViews": mode != "camera_invariant",
        "views": slots,
    }
    manifest_path = output_dir / f"{stem}_rotation.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    meta = dict(first_meta)
    meta.update({
        "recipe": str(recipe_path),
        "recipeSha256": hashlib.sha256(raw).hexdigest(),
        "png": str(canonical),
        "review": str(review),
        "isometricReview": str(iso),
        "finishRecipe": str(finish_recipe) if finish_recipe else None,
        "rotationManifest": str(manifest_path),
        "views": slots,
    })
    report = output_dir / f"{stem}.json"
    report.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {
        "png": str(canonical),
        "review": str(review),
        "isometricReview": str(iso),
        "metadata": str(report),
        "rotationManifest": str(manifest_path),
        "views": {view: slot["path"] for view, slot in slots.items()},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.recipe, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
