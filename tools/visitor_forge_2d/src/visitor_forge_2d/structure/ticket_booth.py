from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from visitor_forge_2d.core.composer import LayerComposer
from visitor_forge_2d.core.exporter import alpha_safe_resize
from visitor_forge_2d.core.model import CanvasSpec, CharacterDefinition, LayerSpec, PoseSpec, Vec2

WORKING_SIZE = (1024, 1024)
OUTPUT_SIZE = (256, 256)
ASSET_ID = "park_ticket_booth_01"
CONTRACT = "CH_LAYERED_STRUCTURE_2D_V1"


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _face_point(face: tuple[tuple[float, float], ...], u: float, v: float) -> tuple[float, float]:
    top = _lerp(face[0], face[1], u)
    bottom = _lerp(face[3], face[2], u)
    return _lerp(top, bottom, v)


def _face_quad(
    face: tuple[tuple[float, float], ...], u0: float, u1: float, v0: float, v1: float
) -> list[tuple[float, float]]:
    return [
        _face_point(face, u0, v0),
        _face_point(face, u1, v0),
        _face_point(face, u1, v1),
        _face_point(face, u0, v1),
    ]


def _arch_polygon(
    face: tuple[tuple[float, float], ...],
    center_u: float,
    half_u: float,
    top_v: float,
    spring_v: float,
    bottom_v: float,
    segments: int = 18,
) -> list[tuple[float, float]]:
    points = [_face_point(face, center_u - half_u, bottom_v), _face_point(face, center_u - half_u, spring_v)]
    for i in range(segments + 1):
        theta = math.pi - math.pi * i / segments
        u = center_u + math.cos(theta) * half_u
        v = spring_v - math.sin(theta) * (spring_v - top_v)
        points.append(_face_point(face, u, v))
    points.extend([_face_point(face, center_u + half_u, spring_v), _face_point(face, center_u + half_u, bottom_v)])
    return points


def _star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return points


def _polygon_pattern(
    base: Image.Image,
    polygon: list[tuple[float, float]],
    lines: list[tuple[tuple[float, float], tuple[float, float], tuple[int, int, int, int], int]],
) -> None:
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for start, end, color, width in lines:
        draw.line([start, end], fill=color, width=width)
    base.alpha_composite(Image.composite(overlay, Image.new("RGBA", base.size), mask))


def _build_layers() -> dict[str, Image.Image]:
    layers = {
        name: Image.new("RGBA", WORKING_SIZE, (0, 0, 0, 0))
        for name in ("walls", "stone", "openings", "roof", "trim", "flag")
    }

    # Canonical SOUTH 2:1 construction. Two visible faces meet at the near corner.
    n = (512.0, 388.0)
    e = (756.0, 510.0)
    s = (512.0, 632.0)
    w = (268.0, 510.0)
    gn = (512.0, 610.0)
    ge = (756.0, 732.0)
    gs = (512.0, 854.0)
    gw = (268.0, 732.0)

    left_face = (w, s, gs, gw)
    right_face = (s, e, ge, gs)

    walls = ImageDraw.Draw(layers["walls"])
    walls.polygon([w, s, gs, gw], fill=(223, 208, 176, 255), outline=(91, 75, 57, 235), width=5)
    walls.polygon([s, e, ge, gs], fill=(203, 188, 157, 255), outline=(83, 69, 54, 235), width=5)

    # Soft 2D contact shading gives volume without invoking a 3D light rig.
    for face, shade in ((left_face, (118, 93, 66, 30)), (right_face, (92, 72, 54, 42))):
        d = ImageDraw.Draw(layers["walls"])
        d.polygon(_face_quad(face, 0.0, 1.0, 0.00, 0.055), fill=shade)
        d.polygon(_face_quad(face, 0.0, 1.0, 0.91, 1.00), fill=(80, 62, 47, 30))

    # Chunky corner stones/quoins, deliberately readable after 4x downscale.
    stone = ImageDraw.Draw(layers["stone"])
    stone_light = (183, 151, 109, 255)
    stone_dark = (157, 126, 91, 255)
    for face, side in ((left_face, "left"), (right_face, "right")):
        for row in range(6):
            v0 = 0.08 + row * 0.145
            v1 = min(v0 + 0.095, 0.94)
            if side == "left":
                quad = _face_quad(face, 0.00, 0.095 if row % 2 == 0 else 0.075, v0, v1)
            else:
                quad = _face_quad(face, 0.905 if row % 2 == 0 else 0.925, 1.00, v0, v1)
            stone.polygon(quad, fill=stone_light if row % 2 == 0 else stone_dark, outline=(103, 80, 59, 220), width=3)

    # Ticket window on left face: blue inset, dark booth interior, wooden counter.
    openings = ImageDraw.Draw(layers["openings"])
    window_outer = _face_quad(left_face, 0.16, 0.63, 0.34, 0.73)
    openings.polygon(window_outer, fill=(79, 116, 129, 255), outline=(72, 58, 46, 235), width=5)
    window_inner = _face_quad(left_face, 0.205, 0.585, 0.385, 0.69)
    openings.polygon(window_inner, fill=(42, 49, 48, 255), outline=(38, 47, 48, 255), width=3)
    counter = _face_quad(left_face, 0.13, 0.66, 0.70, 0.775)
    openings.polygon(counter, fill=(151, 103, 63, 255), outline=(84, 59, 43, 255), width=4)
    # Small ticket/register plaque on counter.
    p = _face_point(left_face, 0.39, 0.685)
    openings.rounded_rectangle([p[0] - 18, p[1] - 13, p[0] + 26, p[1] + 8], radius=5,
                               fill=(223, 201, 157, 255), outline=(95, 72, 52, 230), width=3)

    # Red/cream striped awning, projected as one 2D canopy layer.
    inner0 = _face_point(left_face, 0.12, 0.29)
    inner1 = _face_point(left_face, 0.67, 0.29)
    outer0 = (inner0[0] - 34, inner0[1] + 42)
    outer1 = (inner1[0] - 34, inner1[1] + 42)
    awning_poly = [inner0, inner1, outer1, outer0]
    trim = ImageDraw.Draw(layers["trim"])
    trim.polygon(awning_poly, fill=(232, 220, 190, 255), outline=(103, 67, 52, 240), width=4)
    stripe_overlay = Image.new("RGBA", WORKING_SIZE, (0, 0, 0, 0))
    stripe_draw = ImageDraw.Draw(stripe_overlay)
    min_x = int(min(p[0] for p in awning_poly)) - 30
    max_x = int(max(p[0] for p in awning_poly)) + 30
    for x in range(min_x, max_x, 44):
        stripe_draw.polygon([(x, 300), (x + 24, 300), (x + 110, 800), (x + 78, 800)], fill=(178, 62, 51, 255))
    mask = Image.new("L", WORKING_SIZE, 0)
    ImageDraw.Draw(mask).polygon(awning_poly, fill=255)
    layers["trim"].alpha_composite(Image.composite(stripe_overlay, Image.new("RGBA", WORKING_SIZE), mask))
    trim = ImageDraw.Draw(layers["trim"])
    for i in range(5):
        t0 = i / 5
        t1 = (i + 1) / 5
        a = _lerp(outer0, outer1, t0)
        b = _lerp(outer0, outer1, t1)
        trim.ellipse([a[0] - 7, a[1] - 3, b[0] + 7, b[1] + 13], fill=(232, 220, 190, 255) if i % 2 == 0 else (178, 62, 51, 255))

    # Main passage: actual dark void in 2D, with thick cream stone arch surround.
    outer_arch = _arch_polygon(right_face, 0.47, 0.27, 0.19, 0.43, 0.96)
    inner_arch = _arch_polygon(right_face, 0.47, 0.205, 0.255, 0.445, 0.965)
    openings.polygon(outer_arch, fill=(239, 224, 194, 255), outline=(104, 82, 59, 240), width=5)
    openings.polygon(inner_arch, fill=(39, 43, 40, 255), outline=(76, 60, 47, 235), width=4)

    # Simple wedge lines make the stone arch read as masonry without tiny noise.
    arch_draw = ImageDraw.Draw(layers["openings"])
    for i in range(1, 6):
        theta = math.pi - math.pi * i / 6
        u0 = 0.47 + math.cos(theta) * 0.205
        v0 = 0.445 - math.sin(theta) * (0.445 - 0.255)
        u1 = 0.47 + math.cos(theta) * 0.27
        v1 = 0.43 - math.sin(theta) * (0.43 - 0.19)
        arch_draw.line([_face_point(right_face, u0, v0), _face_point(right_face, u1, v1)], fill=(155, 128, 91, 210), width=3)
    # Red keystone.
    k = _face_point(right_face, 0.47, 0.17)
    openings.polygon([(k[0] - 16, k[1] - 7), (k[0] + 13, k[1] - 21), (k[0] + 22, k[1] + 12), (k[0] - 10, k[1] + 28)],
                     fill=(170, 64, 49, 255), outline=(99, 58, 48, 230))

    # Blue/gold crest over the passage, still part of the little house only.
    crest_center = _face_point(right_face, 0.49, 0.055)
    crest = ImageDraw.Draw(layers["trim"])
    crest_poly = [
        (crest_center[0] - 82, crest_center[1] + 4),
        (crest_center[0] - 55, crest_center[1] - 34),
        (crest_center[0], crest_center[1] - 48),
        (crest_center[0] + 59, crest_center[1] - 18),
        (crest_center[0] + 82, crest_center[1] + 23),
        (crest_center[0] + 48, crest_center[1] + 44),
        (crest_center[0] - 52, crest_center[1] + 34),
    ]
    crest.polygon(crest_poly, fill=(58, 102, 132, 255), outline=(235, 216, 177, 255), width=12)
    crest.line(crest_poly + [crest_poly[0]], fill=(115, 86, 59, 255), width=3)
    crest.polygon(_star_points(crest_center[0], crest_center[1] - 1, 32, 14),
                  fill=(224, 166, 53, 255), outline=(119, 80, 42, 255))
    for dx, dy in ((-76, -16), (76, 5)):
        crest.ellipse([crest_center[0] + dx - 10, crest_center[1] + dy - 10,
                       crest_center[0] + dx + 10, crest_center[1] + dy + 10],
                      fill=(239, 224, 194, 255), outline=(119, 91, 64, 255), width=3)

    # Roof: two visible pyramid faces with coarse tile rhythm that survives 256px output.
    roof = ImageDraw.Draw(layers["roof"])
    rw = (236.0, 486.0)
    rs = (512.0, 624.0)
    re = (788.0, 486.0)
    apex = (512.0, 178.0)
    left_roof = [rw, rs, apex]
    right_roof = [rs, re, apex]
    roof.polygon(left_roof, fill=(166, 62, 48, 255), outline=(83, 53, 43, 255), width=6)
    roof.polygon(right_roof, fill=(145, 52, 43, 255), outline=(77, 49, 41, 255), width=6)

    roof_lines: list[tuple[tuple[float, float], tuple[float, float], tuple[int, int, int, int], int]] = []
    for row in range(1, 9):
        t = row / 9
        left = _lerp(apex, rw, t)
        right = _lerp(apex, rs, t)
        roof_lines.append((left, right, (103, 46, 39, 175), 3))
        segments = max(1, row)
        for col in range(1, segments + 1):
            p0 = _lerp(apex, rw, (row - 1) / 9)
            p1 = _lerp(left, right, col / (segments + 1))
            roof_lines.append((p0, p1, (214, 101, 69, 80), 2))
    _polygon_pattern(layers["roof"], left_roof, roof_lines)

    roof_lines = []
    for row in range(1, 9):
        t = row / 9
        left = _lerp(apex, rs, t)
        right = _lerp(apex, re, t)
        roof_lines.append((left, right, (91, 41, 36, 185), 3))
        segments = max(1, row)
        for col in range(1, segments + 1):
            roof_lines.append((_lerp(apex, re, (row - 1) / 9), _lerp(left, right, col / (segments + 1)), (196, 83, 62, 65), 2))
    _polygon_pattern(layers["roof"], right_roof, roof_lines)

    # Green eave/fascia from the approved concept.
    trim = ImageDraw.Draw(layers["trim"])
    trim.line([rw, rs], fill=(60, 101, 71, 255), width=18)
    trim.line([rs, re], fill=(48, 84, 62, 255), width=18)
    trim.line([rw, rs], fill=(116, 143, 96, 170), width=4)
    trim.line([rs, re], fill=(103, 127, 86, 140), width=4)

    # Small terracotta brackets below the eave; architectural, not adjacent decoration.
    for face in (left_face, right_face):
        for u in (0.18, 0.50, 0.82):
            q = _face_quad(face, u - 0.025, u + 0.025, 0.01, 0.10)
            trim.polygon(q, fill=(147, 70, 50, 255), outline=(90, 57, 45, 210), width=2)

    # Roof cap, pole and golden flag.
    flag = ImageDraw.Draw(layers["flag"])
    flag.polygon([(493, 179), (531, 179), (525, 205), (499, 205)], fill=(226, 211, 178, 255), outline=(111, 87, 62, 230), width=3)
    flag.line([(512, 180), (512, 82)], fill=(181, 132, 43, 255), width=8)
    flag.ellipse([503, 68, 521, 86], fill=(229, 178, 62, 255), outline=(127, 89, 40, 255), width=3)
    flag.polygon([(516, 91), (602, 105), (570, 129), (516, 119)], fill=(221, 165, 51, 255), outline=(126, 88, 39, 255))
    flag.line([(521, 100), (583, 112)], fill=(245, 205, 92, 180), width=4)

    return layers


def _definition(parts_dir: Path) -> CharacterDefinition:
    layer_order = ("walls", "stone", "openings", "roof", "trim", "flag")
    specs = {
        name: LayerSpec(
            layer_id=name,
            source=f"{name}.png",
            position=Vec2(512.0, 512.0),
            pivot=Vec2(512.0, 512.0),
            z_index=index,
        )
        for index, name in enumerate(layer_order)
    }
    return CharacterDefinition(
        character_id=ASSET_ID,
        direction="south",
        canvas=CanvasSpec(WORKING_SIZE, OUTPUT_SIZE, Vec2(128.0, 218.0)),
        joints={},
        layers=specs,
        parts=(),
        palette={},
        forge_contract_version=CONTRACT,
    )


def build_ticket_booth_south(output_dir: str | Path) -> dict[str, object]:
    out = Path(output_dir)
    parts_dir = out / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    layers = _build_layers()
    for name, image in layers.items():
        image.save(parts_dir / f"{name}.png", "PNG")

    definition = _definition(parts_dir)
    pose = PoseSpec(pose_id="static", direction="south", frame_duration_ms=1000, joints={})
    composer = LayerComposer(parts_dir)
    working = composer.compose(definition, pose)
    sprite = alpha_safe_resize(working, OUTPUT_SIZE)

    sprite_path = out / f"{ASSET_ID}_south.png"
    sprite.save(sprite_path, "PNG")

    # Review-only dark board. Background never enters the runtime-facing RGBA PNG.
    review = Image.new("RGBA", (512, 512), (31, 35, 37, 255))
    enlarged = sprite.resize((384, 384), Image.Resampling.NEAREST)
    review.alpha_composite(enlarged, (64, 54))
    rdraw = ImageDraw.Draw(review)
    rdraw.text((18, 18), "Visitor Forge 2D / STRUCTURE SOUTH / review only", fill=(231, 230, 224, 255))
    rdraw.text((18, 482), "2:1 procedural layered sprite - transparent production frame", fill=(188, 191, 188, 255))
    review_path = out / f"{ASSET_ID}_south_review.png"
    review.save(review_path, "PNG")

    digest = hashlib.sha256(sprite_path.read_bytes()).hexdigest()
    manifest = {
        "contract": CONTRACT,
        "assetId": ASSET_ID,
        "assetType": "static_ticket_booth",
        "status": "south_visual_gate",
        "generator": "tools/visitor_forge_2d",
        "generatorModule": "visitor_forge_2d.structure.ticket_booth",
        "corePipeline": ["procedural_2d_layers", "LayerComposer", "premultiplied_alpha_downscale"],
        "projection": "isometric_2_to_1",
        "direction": "south",
        "workingCanvas": list(WORKING_SIZE),
        "outputCanvas": list(OUTPUT_SIZE),
        "anchor": [128, 218],
        "footprint": {"widthTiles": 2, "depthTiles": 2},
        "transparent": True,
        "groundIncluded": False,
        "excluded": ["ground", "plants", "fences", "queue_rails", "posts", "lanterns", "adjacent_decor"],
        "layers": list(layers),
        "runtimeApproved": False,
        "spriteSha256": digest,
    }
    manifest_path = out / f"{ASSET_ID}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"sprite": str(sprite_path), "review": str(review_path), "manifest": str(manifest_path), "sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the SOUTH ticket booth with the real Visitor Forge 2D core")
    parser.add_argument("--output", default="out/visitor_forge_2d/ticket_booth")
    args = parser.parse_args()
    result = build_ticket_booth_south(args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
