#!/usr/bin/env python3
"""Build clown_01 SOUTH 8-frame in-place/treadmill walk.

The approved CH Actor locomotion remains authoritative. The painted clown master
uses its own calibrated authoring landmarks; approved actor joint DELTAS are
retargeted onto those painted landmarks. Art is then skinned by rigid articulated
segments instead of inverse-distance landmark warping, preventing rubbery pants,
shoes and sleeves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from build_clown_master import ART_ROOT, LAYER_RECIPES, MASK_RECIPES, OUTLINE_RGBA
from character_draw_cli import load_json, render
from treadmill_landmarks import ANCHOR, FRAME, build as build_landmarks

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORING_LANDMARKS = ART_ROOT / "authoring_landmarks.json"

# Each semantic layer is decomposed into rigid 2D bone segments. Pieces are
# assigned to the nearest source segment once, then transformed independently.
# This preserves painted volume while allowing knees/elbows to articulate.
LAYER_BONES = {
    "skin": [
        ("head", "head_top", "neck"),
        ("hand_L", "elbow_L", "hand_L"),
        ("hand_R", "elbow_R", "hand_R"),
    ],
    "hair": [("head", "head_top", "neck")],
    "face": [("head", "head_top", "neck")],
    "upper_clothing": [
        ("torso", "neck", "pelvis"),
        ("upper_arm_L", "shoulder_L", "elbow_L"),
        ("forearm_L", "elbow_L", "hand_L"),
        ("upper_arm_R", "shoulder_R", "elbow_R"),
        ("forearm_R", "elbow_R", "hand_R"),
    ],
    "lower_clothing": [
        ("thigh_L", "hip_L", "knee_L"),
        ("shin_L", "knee_L", "ankle_L"),
        ("thigh_R", "hip_R", "knee_R"),
        ("shin_R", "knee_R", "ankle_R"),
    ],
    "footwear": [
        ("foot_L", "ankle_L", "foot_L"),
        ("foot_R", "ankle_R", "foot_R"),
    ],
    "accessories_front": [("torso", "neck", "pelvis")],
}

MASK_BONES = {
    "appearance": [
        ("head", "head_top", "neck"),
        ("hand_L", "elbow_L", "hand_L"),
        ("hand_R", "elbow_R", "hand_R"),
    ],
    "clothing": [
        ("torso", "neck", "pelvis"),
        ("upper_arm_L", "shoulder_L", "elbow_L"),
        ("forearm_L", "elbow_L", "hand_L"),
        ("upper_arm_R", "shoulder_R", "elbow_R"),
        ("forearm_R", "elbow_R", "hand_R"),
        ("thigh_L", "hip_L", "knee_L"),
        ("shin_L", "knee_L", "ankle_L"),
        ("foot_L", "ankle_L", "foot_L"),
        ("thigh_R", "hip_R", "knee_R"),
        ("shin_R", "knee_R", "ankle_R"),
        ("foot_R", "ankle_R", "foot_R"),
    ],
    "held_object": [("hand_R", "elbow_R", "hand_R")],
}

# Projected 2D bone length can change sharply when a limb points toward camera.
# The joints keep the exact approved deltas; only visual segment stretching is
# damped so painted trousers/sleeves do not inflate or collapse between frames.
VISUAL_SCALE_DAMPING = 0.55
VISUAL_SCALE_MIN = 0.88
VISUAL_SCALE_MAX = 1.14


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_segment_distance(px: float, py: float, a: list[float], b: list[float]) -> float:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length2))
    qx, qy = ax + vx * t, ay + vy * t
    return math.hypot(px - qx, py - qy)


def split_by_bones(image: Image.Image, bones: list[tuple[str, str, str]], points: dict) -> dict[str, Image.Image]:
    source = image.convert("RGBA")
    source_px = source.load()
    pieces = {bone_id: Image.new("RGBA", FRAME, (0, 0, 0, 0)) for bone_id, _, _ in bones}
    piece_px = {bone_id: piece.load() for bone_id, piece in pieces.items()}

    for y in range(FRAME[1]):
        for x in range(FRAME[0]):
            rgba = source_px[x, y]
            if rgba[3] == 0:
                continue
            best_id = None
            best_distance = float("inf")
            cx, cy = x + 0.5, y + 0.5
            for bone_id, start_name, end_name in bones:
                start, end = points[start_name], points[end_name]
                distance = point_segment_distance(cx, cy, start, end)
                if distance < best_distance:
                    best_id, best_distance = bone_id, distance
            if best_id is not None:
                piece_px[best_id][x, y] = rgba
    return pieces


def retarget_points(authoring: dict, actor_idle: dict, actor_target: dict) -> dict[str, list[float]]:
    """Apply only approved actor motion DELTAS to the calibrated painted rig."""
    result: dict[str, list[float]] = {}
    for name, art_point in authoring.items():
        source = actor_idle.get(name)
        target = actor_target.get(name)
        if not isinstance(source, list) or not isinstance(target, list):
            result[name] = list(art_point)
            continue
        result[name] = [
            float(art_point[0]) + float(target[0]) - float(source[0]),
            float(art_point[1]) + float(target[1]) - float(source[1]),
        ]
    return result


def similarity_inverse(source_a: list[float], source_b: list[float], target_a: list[float], target_b: list[float]) -> tuple[float, float, float, float, float, float]:
    sax, say = map(float, source_a)
    sbx, sby = map(float, source_b)
    tax, tay = map(float, target_a)
    tbx, tby = map(float, target_b)

    svx, svy = sbx - sax, sby - say
    tvx, tvy = tbx - tax, tby - tay
    source_len = max(1e-6, math.hypot(svx, svy))
    target_len = max(1e-6, math.hypot(tvx, tvy))
    source_angle = math.atan2(svy, svx)
    target_angle = math.atan2(tvy, tvx)
    angle = target_angle - source_angle

    raw_scale = target_len / source_len
    scale = 1.0 + (raw_scale - 1.0) * VISUAL_SCALE_DAMPING
    scale = max(VISUAL_SCALE_MIN, min(VISUAL_SCALE_MAX, scale))
    c, s = math.cos(angle), math.sin(angle)
    m00, m01 = scale * c, -scale * s
    m10, m11 = scale * s, scale * c
    determinant = m00 * m11 - m01 * m10
    if abs(determinant) <= 1e-9:
        return (1.0, 0.0, sax - tax, 0.0, 1.0, say - tay)

    i00, i01 = m11 / determinant, -m01 / determinant
    i10, i11 = -m10 / determinant, m00 / determinant
    off_x = sax - (i00 * tax + i01 * tay)
    off_y = say - (i10 * tax + i11 * tay)
    return (i00, i01, off_x, i10, i11, off_y)


def transfer_segmented(source_image: Image.Image, source_points: dict, target_points: dict, bones: list[tuple[str, str, str]], *, mask_mode: bool = False) -> Image.Image:
    pieces = split_by_bones(source_image, bones, source_points)
    transformed = []
    resample = Image.Resampling.NEAREST if mask_mode else Image.Resampling.BICUBIC

    for bone_id, start_name, end_name in bones:
        coeffs = similarity_inverse(
            source_points[start_name], source_points[end_name],
            target_points[start_name], target_points[end_name],
        )
        warped = pieces[bone_id].transform(
            FRAME,
            Image.Transform.AFFINE,
            coeffs,
            resample=resample,
        )
        midpoint_y = (target_points[start_name][1] + target_points[end_name][1]) * 0.5
        transformed.append((midpoint_y, bone_id, warped))

    # Smaller screen Y is farther away. Draw back-to-front using projected Y.
    transformed.sort(key=lambda item: item[0])
    out = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    for _, _, warped in transformed:
        out.alpha_composite(warped)
    return out


def make_outline(images: list[Image.Image]) -> Image.Image:
    coverage = [False] * (FRAME[0] * FRAME[1])
    for image in images:
        alpha = image.getchannel("A")
        for i, value in enumerate(alpha.getdata()):
            if value >= 24:
                coverage[i] = True
    out = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    px = out.load()
    neighbors = ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1))
    for y in range(FRAME[1]):
        for x in range(FRAME[0]):
            i = y * FRAME[0] + x
            if coverage[i]:
                continue
            if any(0 <= x+dx < FRAME[0] and 0 <= y+dy < FRAME[1] and coverage[(y+dy)*FRAME[0] + x+dx] for dx,dy in neighbors):
                px[x, y] = OUTLINE_RGBA
    return out


def checker_frame(image: Image.Image, scale: int = 8) -> Image.Image:
    bg = Image.new("RGBA", FRAME, (45, 58, 65, 255))
    draw = ImageDraw.Draw(bg)
    cell = 4
    for y in range(0, FRAME[1], cell):
        for x in range(0, FRAME[0], cell):
            if ((x // cell) + (y // cell)) & 1:
                draw.rectangle((x, y, min(x+cell-1, FRAME[0]-1), min(y+cell-1, FRAME[1]-1)), fill=(57,73,80,255))
    bg.alpha_composite(image)
    return bg.resize((FRAME[0]*scale, FRAME[1]*scale), Image.Resampling.NEAREST).convert("P", palette=Image.Palette.ADAPTIVE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("out/ch_character_studio/clown_01/south_walk"))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--duration-ms", type=int, default=138)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else (REPO_ROOT / args.out_dir).resolve()
    frames_dir = out_dir / "frames"
    masks_dir = out_dir / "masks"
    frames_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    landmarks = build_landmarks()
    actor_idle = landmarks["frames"]["S:idle"]["points"]
    authoring_payload = load_json(AUTHORING_LANDMARKS)
    if authoring_payload.get("contract") != "CH_CHARACTER_ART_LANDMARKS_V0":
        raise ValueError("authoring_landmarks.json must use CH_CHARACTER_ART_LANDMARKS_V0")
    source_points = authoring_payload["points"]

    master_layers = {name: render(load_json(ART_ROOT / filename), args.seed) for name, filename in LAYER_RECIPES}
    master_masks = {name: render(load_json(ART_ROOT / filename), args.seed) for name, filename in MASK_RECIPES}

    review_frames: list[Image.Image] = []
    frame_reports = []
    strip = Image.new("RGBA", (FRAME[0] * 8, FRAME[1]), (0, 0, 0, 0))

    for index in range(8):
        key = f"S:walk_{index:02d}"
        actor_target_frame = landmarks["frames"][key]
        target_points = retarget_points(source_points, actor_idle, actor_target_frame["points"])

        layers = []
        for name, image in master_layers.items():
            bones = LAYER_BONES.get(name, [("torso", "neck", "pelvis")])
            layers.append(transfer_segmented(image, source_points, target_points, bones, mask_mode=False))

        outline = make_outline(layers)
        composite = Image.new("RGBA", FRAME, (0,0,0,0))
        for image in layers:
            composite.alpha_composite(image)
        composite.alpha_composite(outline)

        path = frames_dir / f"s_walk_{index:02d}.png"
        composite.save(path, optimize=False, compress_level=9)
        strip.alpha_composite(composite, (index * FRAME[0], 0))
        review_frames.append(checker_frame(composite))

        mask_hashes = {}
        for bank, source_mask in master_masks.items():
            bones = MASK_BONES[bank]
            warped = transfer_segmented(source_mask, source_points, target_points, bones, mask_mode=True)
            mask_path = masks_dir / f"s_walk_{index:02d}_{bank}.png"
            warped.save(mask_path, optimize=False, compress_level=9)
            mask_hashes[bank] = sha256(mask_path)

        frame_reports.append({
            "frame": key,
            "rootTranslationPx": actor_target_frame["rootTranslationPx"],
            "groundAnchor": actor_target_frame["anchors"]["ground"],
            "pngSha256": sha256(path),
            "masks": mask_hashes,
        })

    gif_path = out_dir / "clown_01_s_walk_treadmill.gif"
    review_frames[0].save(gif_path, save_all=True, append_images=review_frames[1:], duration=args.duration_ms, loop=0, disposal=2)
    strip_path = out_dir / "clown_01_s_walk_strip.png"
    strip.save(strip_path, optimize=False, compress_level=9)

    landmarks_path = out_dir / "landmarks.json"
    landmarks_path.write_text(json.dumps(landmarks, indent=2) + "\n", encoding="utf-8")

    invariant_ok = all(item["rootTranslationPx"] == [0,0] and item["groundAnchor"] == list(ANCHOR) for item in frame_reports)
    report = {
        "contract": "CH_CLOWN_TREADMILL_WALK_V1",
        "status": "candidate_for_visual_review" if invariant_ok else "invalid",
        "characterId": "clown_01",
        "direction": "S",
        "frames": 8,
        "durationMs": args.duration_ms,
        "motionSource": "approved_ch_actor_8_frame_cycle",
        "motionRetarget": "approved_joint_deltas_onto_calibrated_clown_authoring_landmarks",
        "artTransfer": "rigid_segmented_bone_skinning",
        "visualScaleDamping": VISUAL_SCALE_DAMPING,
        "visualScaleClamp": [VISUAL_SCALE_MIN, VISUAL_SCALE_MAX],
        "motionMode": "treadmill_in_place",
        "worldTranslationDuringSpriteCycle": False,
        "groundAnchor": list(ANCHOR),
        "anchorInvariantPassed": invariant_ok,
        "gif": {"path": str(gif_path), "sha256": sha256(gif_path)},
        "strip": {"path": str(strip_path), "sha256": sha256(strip_path)},
        "landmarks": {"path": str(landmarks_path), "sha256": sha256(landmarks_path)},
        "authoringLandmarks": str(AUTHORING_LANDMARKS.relative_to(REPO_ROOT)),
        "frameReports": frame_reports,
    }
    report_path = out_dir / "treadmill_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if invariant_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
