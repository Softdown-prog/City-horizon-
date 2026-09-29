"""Species renderer for the City Horizon Red Mapple family.

The generic broadleaf painter is intentionally simple.  This opt-in renderer
keeps the same CH_2D_ORGANIC_SCENERY_V1 recipe contract, but builds the crown
from authored branch endpoints and many small maple-shaped leaves so visible
wood, negative space and foliage hierarchy survive gameplay 1x.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import organic_scenery as organic

CONTRACT = organic.CONTRACT
CAMERA_CONTRACT = organic.CAMERA_CONTRACT
ROTATION_CONTRACT = organic.ROTATION_CONTRACT
WORK_SCALE = organic.WORK_SCALE
VALID_VIEWS = organic.VALID_VIEWS
DEFAULT_YAWS = organic.DEFAULT_YAWS
VIEW_PHASE = organic.VIEW_PHASE


def _draw_maple_leaf(draw, x, y, size, angle, color, opacity):
    """Draw one compact five-lobed maple silhouette at supersampled scale."""
    # Alternating long and short radii make a readable maple/star leaf after
    # the 4x -> 1x alpha-safe downsample without adding a dark outline.
    radii = (1.00, .47, .84, .42, .73, .36, .73, .42, .84, .47)
    points = []
    for index, radius in enumerate(radii):
        theta = angle - math.pi / 2 + index * math.tau / len(radii)
        stretch_y = .86
        points.append(((x + math.cos(theta) * size * radius) * WORK_SCALE,
                       (y + math.sin(theta) * size * radius * stretch_y) * WORK_SCALE))
    draw.polygon(points, fill=(*organic._hex(color), opacity))


def _paint_leaf_group(work, rng, palette, center, radius, *, light_bias=0.0):
    """Paint one shaded leaf cloud with many small defined maple leaves."""
    cx, cy = center
    rx, ry = radius
    W, H = work.size
    mask = organic._cloud_mask((W, H), rng, cx, cy, rx, ry, scallops=12)

    # Dark underpainting gives the crown depth while preserving gaps between
    # neighbouring groups and between branch-borne volumes.
    top = organic._mix_color(palette["mid_top"], palette["front_top"], .44 + light_bias)
    bottom = organic._mix_color(palette["mid_bottom"], palette["back_bottom"], .34)
    organic._composite(work, mask, top, bottom, right_shade=.08)

    shade = Image.new("L", (W, H))
    organic._irregular_blob(shade, rng, cx + rx * .24, cy + ry * .28,
                            rx * .66, ry * .43, 11, 92, .20)
    shade = ImageChops.multiply(shade, mask)
    organic._composite(work, shade, palette["occlusion"], palette["back_bottom"])

    leaves = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(leaves, "RGBA")
    pixels = mask.load()
    colors = (palette["mid_top"], palette["front_top"], palette["front_bottom"],
              palette["highlight"], palette["leaf_shadow_top"])
    count = max(34, round((rx * ry) / 5.6))
    for _ in range(count):
        x = cx + rng.uniform(-.93, .93) * rx
        y = cy + rng.uniform(-.91, .91) * ry
        ix, iy = round(x * WORK_SCALE), round(y * WORK_SCALE)
        if not (0 <= ix < W and 0 <= iy < H) or pixels[ix, iy] < 210:
            continue
        lit = x < cx + rx * .18 and y < cy + ry * .12
        roll = rng.random()
        if lit and roll < .22:
            color = colors[3]
        elif lit and roll < .72:
            color = colors[1]
        elif y > cy + ry * .18 and roll < .44:
            color = colors[4]
        else:
            color = colors[0] if roll < .62 else colors[2]
        _draw_maple_leaf(draw, x, y, rng.uniform(3.0, 5.5),
                         rng.uniform(-.55, .55), color, rng.randint(175, 238))
    leaves.putalpha(ImageChops.multiply(leaves.getchannel("A"), mask))
    work.alpha_composite(leaves)


def _group_positions(recipe, rng, view):
    cfg = recipe["mapleStyle"]
    cx, cy = map(float, cfg.get("center", [128, 126]))
    phase = VIEW_PHASE[view]
    branches = recipe.get("trunkBranches", [])[1:]
    if not branches:
        raise ValueError("red_mapple renderer requires authored trunkBranches")

    groups = []
    for index, branch in enumerate(branches):
        p0 = tuple(map(float, branch["p0"]))
        p1 = tuple(map(float, branch.get("p1", branch["p0"])))
        p2 = tuple(map(float, branch["p2"]))
        for step, along in enumerate((.58, .82, 1.03)):
            x, y = organic._quad(p0, p1, p2, along)
            x += math.sin(phase + index * 1.37 + step * .7) * 2.6 + rng.uniform(-2.4, 2.4)
            y += math.cos(phase + index * .91 + step * .6) * 1.5 + rng.uniform(-2.0, 2.0)
            size = rng.uniform(.86, 1.13)
            # Upper twigs carry smaller groups; lower limbs carry broader ones.
            height_factor = max(.72, min(1.12, (y - 58) / 120))
            groups.append((y, x, 13.5 * size * height_factor,
                           10.4 * size * height_factor))

    # Interior connectors prevent a skeletal centre without turning the crown
    # into one opaque generic blob.
    interior = ((cx - 19, cy - 34, 17, 12), (cx + 5, cy - 39, 17, 12),
                (cx + 23, cy - 20, 18, 13), (cx - 27, cy - 8, 18, 13),
                (cx + 2, cy - 5, 19, 14), (cx - 9, cy + 17, 18, 13))
    for x, y, rx, ry in interior:
        groups.append((y + math.sin(phase) * 1.2, x + math.cos(phase) * 1.8,
                       rx * rng.uniform(.92, 1.08), ry * rng.uniform(.92, 1.08)))
    groups.sort()
    return groups


def render(recipe, view="south"):
    if recipe.get("contract") != CONTRACT:
        raise ValueError(f"recipe must declare {CONTRACT}")
    camera = recipe.get("camera", {})
    if camera.get("contract") != CAMERA_CONTRACT or camera.get("tile") != [128, 64]:
        raise ValueError("Red Mapple scenery requires CH_CAMERA_V1 on the 128x64 grid")
    if view not in VALID_VIEWS:
        raise ValueError(f"view must be one of {VALID_VIEWS}")

    canvas = recipe.get("canvas", [256, 320])
    anchor = recipe.get("anchor", [128, 308])
    seed = int(recipe.get("seed", 1))
    phase_seed = int(round(VIEW_PHASE[view] * 1000))
    rng = random.Random(seed ^ (0x5A17 + phase_seed))
    W, H = canvas[0] * WORK_SCALE, canvas[1] * WORK_SCALE
    palette = recipe["palette"]
    work = Image.new("RGBA", (W, H))

    shadow = Image.new("L", (W, H))
    sw = int(recipe.get("shadowWidth", 92))
    ImageDraw.Draw(shadow).ellipse(
        ((anchor[0] - sw // 2) * WORK_SCALE, (anchor[1] - 8) * WORK_SCALE,
         (anchor[0] + sw // 2) * WORK_SCALE, (anchor[1] + 4) * WORK_SCALE), fill=126)
    shadow = shadow.filter(ImageFilter.GaussianBlur(2.3 * WORK_SCALE))
    sh = Image.new("RGBA", (W, H), (*organic._hex(palette["ground_shadow"]), 0))
    sh.putalpha(shadow)
    work.alpha_composite(sh)

    organic._draw_trunk_and_bark(work, recipe, palette, W, H)

    groups = _group_positions(recipe, rng, view)
    for index, (y, x, rx, ry) in enumerate(groups):
        # Upper-left groups receive slightly more warmth in camera space.
        light_bias = .08 if x < canvas[0] * .50 and y < canvas[1] * .43 else 0.0
        _paint_leaf_group(work, rng, palette, (x, y), (rx, ry), light_bias=light_bias)

    frame = organic._alpha_safe_resize(work, tuple(canvas))
    frame = organic._final_raster_pass(frame, rng, palette, recipe)
    bounds = frame.getchannel("A").getbbox()
    return frame, {
        "contract": CONTRACT,
        "id": recipe["id"],
        "canvas": canvas,
        "anchor": anchor,
        "bounds": list(bounds),
        "seed": seed,
        "crownStyle": "broadleaf",
        "sceneryType": "red_mapple",
        "authoringMode": "procedural_maple_leaf_groups",
        "view": view,
        "yawDeg": int(recipe.get("rotation", {}).get("yawDeg", {}).get(view, DEFAULT_YAWS[view])),
        "camera": camera,
        "runtimePromotion": False,
        "artApproved": False,
    }


def export(recipe_path: Path, output_dir: Path):
    raw = recipe_path.read_bytes()
    recipe = json.loads(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = recipe["id"]
    rotation = recipe.get("rotation", {})
    views = rotation.get("views", ["south"])
    if not views or any(view not in VALID_VIEWS for view in views):
        raise ValueError(f"rotation views must be a non-empty subset of {VALID_VIEWS}")

    slots = {}
    first_meta = None
    for view in views:
        frame, meta = render(recipe, view)
        first_meta = first_meta or meta
        source = output_dir / f"{stem}_{view}_source.png"
        final = output_dir / f"{stem}_{view}.png"
        frame.save(source)
        final.write_bytes(source.read_bytes())
        organic.review_board(frame).save(output_dir / f"{stem}_{view}_review.png")
        organic.isometric_board(frame, meta["anchor"],
                                f"CH_CAMERA_V1 / {view} / yaw {meta['yawDeg']} / 128x64").save(
                                    output_dir / f"{stem}_{view}_isometric_review.png")
        slots[view] = {
            "path": str(final), "source": str(source), "yawDeg": meta["yawDeg"],
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(), "finish": None,
        }

    canonical_view = "south" if "south" in slots else views[0]
    canonical = output_dir / f"{stem}.png"
    canonical.write_bytes(Path(slots[canonical_view]["path"]).read_bytes())
    with Image.open(canonical) as image:
        final_frame = image.convert("RGBA")
    review = output_dir / f"{stem}_review.png"
    iso = output_dir / f"{stem}_isometric_review.png"
    organic.review_board(final_frame).save(review)
    organic.isometric_board(final_frame, first_meta["anchor"]).save(iso)

    manifest = {
        "contract": ROTATION_CONTRACT,
        "id": stem,
        "mode": rotation.get("mode", "procedural_quarter_turns"),
        "lightingSpace": rotation.get("lightingSpace", "screen_camera_relative"),
        "generatedViews": True,
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
