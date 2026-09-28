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
        surf = Image.merge("RGBA", (ImageChops.multiply(r, hgrad), ImageChops.multiply(g, hgrad), ImageChops.multiply(bc, hgrad), alpha))
    if highlight:
        hx, hy, radius_factor, strength = highlight
        glow = Image.new("L", (w, h), 0)
        cx, cy = round(hx * w), round(hy * h)
        radius = round(radius_factor * max(w, h))
        ImageDraw.Draw(glow).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=round(strength * 255))
        glow = glow.filter(ImageFilter.GaussianBlur(max(1.0, radius * .4)))
        r, g, bc, alpha = surf.split()
        surf = Image.merge("RGBA", (ImageChops.add(r, glow), ImageChops.add(g, glow), ImageChops.add(bc, glow), alpha))
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
    back = Image.new("L", (W, H)); core = Image.new("L", (W, H)); mid = Image.new("L", (W, H)); front = Image.new("L", (W, H))
    for tier in tiers:
        y = float(tier["y"]); span = float(tier["span"]); thick = float(tier["thickness"]); skew = float(tier.get("skew", 0))
        _irregular_blob(core, rng, cx + skew, y + thick * .55, max(4.5, span * .12), thick * .60, 16, 255, .12)
        for side in (-1, 1):
            asym = 1 + rng.uniform(-.08, .08)
            for off, factor in ((-3.5, .96), (1.0, .82)):
                _conifer_branch(back, rng, (cx + skew, y + off), (cx + skew + side * span * factor * asym, y + thick * (.16 if off < 0 else .32)), max(4.4, thick * .29), thick * (.02 if off < 0 else .10), side, max(5, int(span / 12)), tuft_strength=.92)
            for off, factor in ((0, .98), (4.0, .88)):
                _conifer_branch(mid, rng, (cx + skew, y + off), (cx + skew + side * span * factor * asym, y + thick * (.52 if off == 0 else .66)), max(5.2, thick * .34), thick * (.18 if off == 0 else .24), side, max(6, int(span / 10)), tuft_strength=1.02)
            _conifer_branch(front, rng, (cx + skew, y + 3), (cx + skew + side * span * .76 * asym, y + thick * .90), max(4.7, thick * .31), thick * .31, side, max(5, int(span / 11)), tuft_strength=.98)
    core = core.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(.08 * WORK_SCALE))
    back = back.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    mid = mid.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.05 * WORK_SCALE))
    front = front.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    return back, core, mid, front


def _leaf_cluster(mask, rng, cx, cy, rx, ry, lobes=11, jitter=.24, satellites=3):
    """Paint one foliage cluster as a main leaf mass plus smaller satellites."""
    _irregular_blob(mask, rng, cx, cy, rx, ry, lobes, 255, jitter)
    for _ in range(satellites):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(.24, .62)
        sx = cx + math.cos(angle) * rx * distance
        sy = cy + math.sin(angle) * ry * distance
        _irregular_blob(mask, rng, sx, sy, rx * rng.uniform(.24, .42), ry * rng.uniform(.24, .44), max(7, lobes - 3), 255, jitter + .04)


def _broadleaf_branch_group(mask, rng, root, tip, width, cluster_scale, density, view_phase, layer_bias=0.0):
    """Build a deciduous branch carrying multiple discrete foliage clusters."""
    rx, ry = root
    tx, ty = tip
    lateral = math.sin(view_phase + rng.uniform(-.35, .35)) * cluster_scale * .22
    ctrl = ((_lerp(rx, tx, .52) + lateral), _lerp(ry, ty, .48) - cluster_scale * .10 + layer_bias)
    _tapered_stroke(mask, root, ctrl, tip, width, max(.8, width * .24), 34, 255)
    for j in range(1, density + 1):
        t = j / (density + 1)
        cx, cy = _quad(root, ctrl, tip, t)
        side = -1 if j % 2 else 1
        tangent_x = _lerp(rx, tx, t)
        spread = cluster_scale * (1.0 - .18 * t)
        cx += side * spread * rng.uniform(.20, .48) + (cx - tangent_x) * .15
        cy += rng.uniform(-spread * .12, spread * .20)
        _leaf_cluster(mask, rng, cx, cy, spread * rng.uniform(.50, .72), spread * rng.uniform(.32, .52), rng.randint(9, 13), .22, rng.randint(2, 4))
    _leaf_cluster(mask, rng, tx, ty, cluster_scale * rng.uniform(.62, .82), cluster_scale * rng.uniform(.42, .60), rng.randint(10, 14), .24, 4)


def _crown_masks_broadleaf(recipe, rng, W, H, view="south"):
    """Build a deciduous crown from branch groups carrying discrete leaf clusters."""
    tiers = recipe["tiers"]
    cx = float(recipe.get("crownCx", 96))
    phase = VIEW_PHASE.get(view, 0.0)
    cfg = recipe.get("broadleafStructure", {})
    branch_density = max(3, int(cfg.get("clustersPerBranch", 5)))
    branch_groups = max(2, int(cfg.get("branchGroupsPerTier", 3)))
    cluster_factor = float(cfg.get("clusterScale", .22))
    back = Image.new("L", (W, H)); core = Image.new("L", (W, H)); mid = Image.new("L", (W, H)); front = Image.new("L", (W, H))

    for tier_index, tier in enumerate(tiers):
        y = float(tier["y"]); span = float(tier["span"]); thick = float(tier["thickness"]); skew = float(tier.get("skew", 0)); tcx = cx + skew
        # Dense core prevents accidental holes but no longer defines the visible silhouette.
        _leaf_cluster(core, rng, tcx, y + thick * .20, span * .30, thick * .38, 13, .16, 3)
        for group in range(branch_groups):
            z = (group - (branch_groups - 1) / 2) / max(1, branch_groups - 1)
            angle_phase = phase + tier_index * .63 + group * (math.tau / branch_groups)
            side = -1 if math.cos(angle_phase) < 0 else 1
            depth = math.sin(angle_phase)
            visible_span = span * (.66 + .22 * abs(math.cos(angle_phase)))
            tip_x = tcx + side * visible_span * rng.uniform(.74, 1.02)
            tip_y = y + thick * (.20 + .34 * ((depth + 1) * .5)) + rng.uniform(-2.0, 2.0)
            root = (tcx + rng.uniform(-span * .08, span * .08), y + thick * .18)
            scale = max(6.0, min(span, thick) * cluster_factor * rng.uniform(.86, 1.18))
            target = back if depth < -.22 else front if depth > .28 else mid
            _broadleaf_branch_group(target, rng, root, (tip_x, tip_y), max(2.2, thick * .085), scale, branch_density, phase, layer_bias=depth * 2.0)
        # Small independent clusters bridge tiers without flattening them into one blob.
        for _ in range(3):
            ox = rng.uniform(-span * .44, span * .44)
            oy = rng.uniform(-thick * .10, thick * .42)
            target = front if oy > thick * .18 else mid
            _leaf_cluster(target, rng, tcx + ox, y + oy, span * rng.uniform(.09, .15), thick * rng.uniform(.13, .21), rng.randint(9, 12), .23, 2)

    core = core.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.05 * WORK_SCALE))
    back = back.filter(ImageFilter.GaussianBlur(.025 * WORK_SCALE))
    mid = mid.filter(ImageFilter.GaussianBlur(.020 * WORK_SCALE))
    front = front.filter(ImageFilter.GaussianBlur(.018 * WORK_SCALE))
    return back, core, mid, front


def _scatter_texture(layer, rng, mask, color, count, alpha_range=(12, 36), size_range=(.45, 1.7), elongate=2.0):
    bbox = mask.getbbox()
    if not bbox:
        return
    draw = ImageDraw.Draw(layer, "RGBA"); pixels = mask.load(); col = _hex(color)
    coords = [(x, y) for y in range(bbox[1], bbox[3]) for x in range(bbox[0], bbox[2]) if pixels[x, y] > 120]
    if not coords:
        return
    for _ in range(count):
        x, y = rng.choice(coords); radius = rng.uniform(*size_range) * WORK_SCALE; alpha = rng.randint(*alpha_range)
        dx = rng.uniform(-.4, .2) * radius; dy = rng.uniform(-.2, .35) * radius
        draw.ellipse((x - radius * elongate + dx, y - radius * .38 + dy, x + radius * .35 + dx, y + radius * .38 + dy), fill=(*col, alpha))


def _final_raster_pass(frame, rng, palette, recipe):
    out = frame.convert("RGBA"); alpha = out.getchannel("A"); bbox = alpha.getbbox()
    if not bbox:
        return out
    pixels = alpha.load(); draw = ImageDraw.Draw(out, "RGBA"); dark = _hex(palette.get("occlusion", "#123B30")); light = _hex(palette["highlight"]); cfg = recipe.get("raster", {})
    grain = int(cfg.get("finalGrain", 620)); needles = int(cfg.get("finalNeedles", 300)); bx0, by0, bx1, by1 = bbox
    for _ in range(grain):
        x = rng.randint(bx0, bx1 - 1); y = rng.randint(by0, by1 - 1)
        if pixels[x, y] <= 170:
            continue
        col, a = (dark, rng.randint(12, 28)) if rng.random() < .58 else (light, rng.randint(9, 24))
        draw.point((x, y), fill=(*col, a))
    for _ in range(needles):
        x = rng.randint(bx0, bx1 - 1); y = rng.randint(by0, by1 - 1)
        if pixels[x, y] <= 190:
            continue
        length = rng.choice([2, 2, 3, 3, 4]); col = light if rng.random() < .58 else dark
        draw.line((x, y, x - length, y + rng.choice([0, 0, 1])), fill=(*col, rng.randint(18, 48)), width=1)
    return out.filter(ImageFilter.UnsharpMask(radius=.65, percent=115, threshold=3))


def _draw_trunk_and_bark(work, recipe, palette, W, H):
    anchor = recipe.get("anchor", [96, 239]); base_x, base_y = anchor
    trunk = Image.new("L", (W, H)); branches = recipe.get("trunkBranches")
    if branches:
        for branch in branches:
            p0 = tuple(branch["p0"]); p1 = tuple(branch.get("p1", p0)); p2 = tuple(branch["p2"])
            _tapered_stroke(trunk, p0, p1, p2, float(branch.get("w0", 8)), float(branch.get("w1", 4)), 44, 255)
    else:
        tw = float(recipe.get("trunkWidth", 20)); top_y = float(recipe.get("trunkTopY", 120)); cx = float(base_x)
        ImageDraw.Draw(trunk).polygon([((cx - tw * .45) * WORK_SCALE, top_y * WORK_SCALE), ((cx + tw * .45) * WORK_SCALE, (top_y + 2) * WORK_SCALE), ((cx + tw * .55) * WORK_SCALE, base_y * WORK_SCALE), ((cx - tw * .55) * WORK_SCALE, base_y * WORK_SCALE)], fill=255)
    _composite(work, trunk, palette["trunk_top"], palette["trunk_bottom"], right_shade=.22, highlight=(.41, .48, .28, .15))
    bark = Image.new("RGBA", (W, H)); draw = ImageDraw.Draw(bark, "RGBA"); color = _hex(palette.get("trunk_light", "#DCA066"))
    for offset in (-4, 0, 4):
        draw.line(((base_x + offset) * WORK_SCALE, (base_y - 70) * WORK_SCALE, (base_x + offset - 1) * WORK_SCALE, (base_y - 8) * WORK_SCALE), fill=(*color, 70), width=round(1.8 * WORK_SCALE))
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
    canvas = recipe.get("canvas", [192, 256]); anchor = recipe.get("anchor", [96, 239]); seed = int(recipe.get("seed", 1))
    # All views share the same random sequence; view changes projected branch geometry, not identity.
    rng = random.Random(seed); W, H = canvas[0] * WORK_SCALE, canvas[1] * WORK_SCALE; palette = recipe["palette"]; work = Image.new("RGBA", (W, H))
    shadow = Image.new("L", (W, H)); sw = recipe.get("shadowWidth", 94)
    ImageDraw.Draw(shadow).ellipse(((anchor[0] - sw // 2) * WORK_SCALE, (anchor[1] - 9) * WORK_SCALE, (anchor[0] + sw // 2) * WORK_SCALE, (anchor[1] + 5) * WORK_SCALE), fill=145)
    shadow = shadow.filter(ImageFilter.GaussianBlur(2.4 * WORK_SCALE)); sh = Image.new("RGBA", (W, H), (*_hex(palette["ground_shadow"]), 0)); sh.putalpha(shadow); work.alpha_composite(sh)
    _draw_trunk_and_bark(work, recipe, palette, W, H)
    crown_style = recipe.get("crownStyle", "conifer")
    if crown_style == "broadleaf":
        back, core, mid, front = _crown_masks_broadleaf(recipe, rng, W, H, view)
    elif crown_style == "conifer":
        back, core, mid, front = _crown_masks_conifer(recipe, rng, W, H)
    else:
        raise ValueError(f"Unknown crownStyle {crown_style!r}; choose 'conifer' or 'broadleaf'")
    _composite(work, back, palette["back_top"], palette["back_bottom"], right_shade=.25, highlight=(.32, .21, .42, .05))
    _composite(work, core, palette["mid_bottom"], palette["back_bottom"], right_shade=.22, highlight=(.31, .27, .50, .05))
    _composite(work, mid, palette["mid_top"], palette["mid_bottom"], right_shade=.19, highlight=(.29, .30, .50, .10))
    texture = Image.new("RGBA", (W, H)); _scatter_texture(texture, rng, mid, palette.get("occlusion", "#123B30"), int(recipe.get("raster", {}).get("shadowDabs", 300)), (10, 34), (.5, 1.8), 2.3); work.alpha_composite(texture)
    _composite(work, front, palette["front_top"], palette["front_bottom"], right_shade=.16, highlight=(.27, .36, .48, .14))
    highlights = Image.new("RGBA", (W, H)); _scatter_texture(highlights, rng, front, palette["highlight"], int(recipe.get("raster", {}).get("highlightDabs", 260)), (8, 30), (.45, 1.45), 2.4); work.alpha_composite(highlights)
    frame = _alpha_safe_resize(work, tuple(canvas)); frame = _final_raster_pass(frame, rng, palette, recipe); bounds = frame.getchannel("A").getbbox()
    return frame, {"contract": CONTRACT, "id": recipe["id"], "canvas": canvas, "anchor": anchor, "bounds": list(bounds), "seed": seed, "crownStyle": crown_style, "view": view, "yawDeg": int(recipe.get("rotation", {}).get("yawDeg", {}).get(view, DEFAULT_YAWS[view])), "camera": recipe["camera"], "raster": recipe.get("raster", {}), "runtimePromotion": False, "artApproved": False}


def review_board(frame):
    w, h = frame.size; board = Image.new("RGBA", (w * 3 + 48, h * 2 + 40), (76, 116, 48, 255)); board.alpha_composite(frame, (16, 20 + h // 2)); board.alpha_composite(frame.resize((w * 2, h * 2), Image.Resampling.NEAREST), (w + 32, 20)); draw = ImageDraw.Draw(board); draw.text((16, 4), "1x / gameplay", fill=(247, 244, 220, 255)); draw.text((w + 32, 4), "2x / inspection", fill=(247, 244, 220, 255)); return board


def isometric_board(frame, anchor, label="CH_CAMERA_V1 / 30deg / 45deg yaw / 128x64"):
    board = Image.new("RGBA", (768, 480), (46, 77, 55, 255)); draw = ImageDraw.Draw(board); gx, gy = 384, 314; hw, hh = 64, 32
    for x in range(-3, 4):
        for y in range(-3, 4):
            cx = gx + (x - y) * hw; cy = gy + (x + y) * hh; poly = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]; fill = (76, 119, 66, 255) if (x + y) % 2 == 0 else (71, 113, 64, 255); draw.polygon(poly, fill=fill, outline=(105, 148, 93, 205))
    draw.polygon([(gx, gy - hh), (gx + hw, gy), (gx, gy + hh), (gx - hw, gy)], fill=(82, 132, 72, 255), outline=(174, 207, 145, 255)); board.alpha_composite(frame, (round(gx - anchor[0]), round(gy - anchor[1]))); draw.ellipse((gx - 3, gy - 3, gx + 3, gy + 3), fill=(255, 224, 132, 255)); draw.text((18, 16), label, fill=(247, 244, 220, 255)); draw.text((18, 36), "CH_2D_ORGANIC_SCENERY_V1 / gameplay 1x", fill=(220, 232, 205, 255)); return board


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
    raw = recipe_path.read_bytes(); recipe = json.loads(raw); output_dir.mkdir(parents=True, exist_ok=True); stem = recipe["id"]
    rotation = recipe.get("rotation", {}); views = rotation.get("views", ["south"])
    if not views or any(view not in VALID_VIEWS for view in views):
        raise ValueError(f"rotation views must be a non-empty subset of {VALID_VIEWS}")
    mode = rotation.get("mode", "single")
    finish_recipe = _resolve_finish_recipe(recipe_path, recipe["finishRecipe"]) if recipe.get("finishRecipe") else None
    slots = {}; first_meta = None
    for view in views:
        frame, meta = render(recipe, view=view); first_meta = first_meta or meta
        source = output_dir / f"{stem}_{view}_source.png"; final = output_dir / f"{stem}_{view}.png"; frame.save(source)
        finish_result = None
        if finish_recipe:
            finish_result = _finish_one(source, final, finish_recipe, output_dir / f"{stem}_{view}_finish_review.png")
        else:
            final.write_bytes(source.read_bytes())
        with Image.open(final) as image:
            finished = image.convert("RGBA")
        review_board(finished).save(output_dir / f"{stem}_{view}_review.png")
        isometric_board(finished, meta["anchor"], f"CH_CAMERA_V1 / {view} / yaw {meta['yawDeg']} / 128x64").save(output_dir / f"{stem}_{view}_isometric_review.png")
        slots[view] = {"path": str(final), "source": str(source), "yawDeg": meta["yawDeg"], "sha256": hashlib.sha256(final.read_bytes()).hexdigest(), "finish": finish_result}
    canonical_view = "south" if "south" in slots else views[0]
    canonical = output_dir / f"{stem}.png"; canonical.write_bytes(Path(slots[canonical_view]["path"]).read_bytes())
    with Image.open(canonical) as image:
        final = image.convert("RGBA")
    review = output_dir / f"{stem}_review.png"; iso = output_dir / f"{stem}_isometric_review.png"; review_board(final).save(review); isometric_board(final, first_meta["anchor"]).save(iso)
    manifest = {"contract": ROTATION_CONTRACT, "id": stem, "mode": mode, "lightingSpace": rotation.get("lightingSpace", "screen_camera_relative"), "generatedViews": mode != "camera_invariant", "views": slots}
    manifest_path = output_dir / f"{stem}_rotation.json"; manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    meta = dict(first_meta); meta.update({"recipe": str(recipe_path), "recipeSha256": hashlib.sha256(raw).hexdigest(), "png": str(canonical), "review": str(review), "isometricReview": str(iso), "finishRecipe": str(finish_recipe) if finish_recipe else None, "rotationManifest": str(manifest_path), "views": slots})
    report = output_dir / f"{stem}.json"; report.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"png": str(canonical), "review": str(review), "isometricReview": str(iso), "metadata": str(report), "rotationManifest": str(manifest_path), "views": {view: slot["path"] for view, slot in slots.items()}}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--recipe", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args(); print(json.dumps(export(args.recipe, args.output), indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
