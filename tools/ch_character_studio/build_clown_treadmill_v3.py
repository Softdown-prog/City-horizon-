#!/usr/bin/env python3
"""Build clown_01 SOUTH walk with V3 foot-specific polish.

Reuses the approved 8-frame treadmill locomotion and segmented body skinning from
build_clown_treadmill.py, but constrains clown shoes to remain rigid/readable:
constant scale, damped rotation, fixed angular limit, and ankle-pivot anchoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image

import build_clown_treadmill as base
from build_clown_master import ART_ROOT, LAYER_RECIPES, MASK_RECIPES
from character_draw_cli import load_json, render
from treadmill_landmarks import ANCHOR, FRAME, build as build_landmarks

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORING_LANDMARKS = ART_ROOT / "authoring_landmarks.json"

SHOE_ROTATION_DAMPING = 0.28
SHOE_ROTATION_LIMIT_DEG = 16.0
SHOE_SCALE = 1.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shoe_inverse(source_a: list[float], source_b: list[float], target_a: list[float], target_b: list[float]):
    """Inverse affine for a rigid shoe anchored at the ankle.

    source_a/target_a are the ankle pivots. The ankle->toe direction only informs
    a heavily damped rotation; shoe scale never changes.
    """
    sax, say = map(float, source_a)
    sbx, sby = map(float, source_b)
    tax, tay = map(float, target_a)
    tbx, tby = map(float, target_b)

    source_angle = math.atan2(sby - say, sbx - sax)
    target_angle = math.atan2(tby - tay, tbx - tax)
    delta = target_angle - source_angle
    while delta > math.pi:
        delta -= 2 * math.pi
    while delta < -math.pi:
        delta += 2 * math.pi

    limit = math.radians(SHOE_ROTATION_LIMIT_DEG)
    angle = max(-limit, min(limit, delta * SHOE_ROTATION_DAMPING))
    c, s = math.cos(angle), math.sin(angle)

    # Forward transform: p' = R * (p-sourcePivot) + targetPivot.
    # PIL requires target->source inverse coefficients.
    i00, i01 = c, s
    i10, i11 = -s, c
    off_x = sax - (i00 * tax + i01 * tay)
    off_y = say - (i10 * tax + i11 * tay)
    return (i00, i01, off_x, i10, i11, off_y)


def transfer_segmented_v3(source_image: Image.Image, source_points: dict, target_points: dict,
                          bones: list[tuple[str, str, str]], *, mask_mode: bool = False) -> Image.Image:
    pieces = base.split_by_bones(source_image, bones, source_points)
    transformed = []
    resample = Image.Resampling.NEAREST if mask_mode else Image.Resampling.BICUBIC

    for bone_id, start_name, end_name in bones:
        if bone_id.startswith("foot_"):
            coeffs = shoe_inverse(
                source_points[start_name], source_points[end_name],
                target_points[start_name], target_points[end_name],
            )
        else:
            coeffs = base.similarity_inverse(
                source_points[start_name], source_points[end_name],
                target_points[start_name], target_points[end_name],
            )
        warped = pieces[bone_id].transform(FRAME, Image.Transform.AFFINE, coeffs, resample=resample)
        midpoint_y = (target_points[start_name][1] + target_points[end_name][1]) * 0.5
        transformed.append((midpoint_y, bone_id, warped))

    transformed.sort(key=lambda item: item[0])
    out = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    for _, _, warped in transformed:
        out.alpha_composite(warped)
    return out


def validate_gif(path: Path, expected_frames: int = 8) -> dict:
    with Image.open(path) as gif:
        count = getattr(gif, "n_frames", 1)
        if count != expected_frames:
            raise ValueError(f"GIF frame count {count}, expected {expected_frames}")
        for index in range(count):
            gif.seek(index)
            gif.convert("RGBA").load()
        return {"frames": count, "size": list(gif.size), "durationMs": gif.info.get("duration")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("out/ch_character_studio/clown_01/south_walk_v3"))
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

    review_frames = []
    frame_reports = []
    strip = Image.new("RGBA", (FRAME[0] * 8, FRAME[1]), (0, 0, 0, 0))

    for index in range(8):
        key = f"S:walk_{index:02d}"
        actor_target = landmarks["frames"][key]
        target_points = base.retarget_points(source_points, actor_idle, actor_target["points"])

        layers = []
        for name, image in master_layers.items():
            bones = base.LAYER_BONES.get(name, [("torso", "neck", "pelvis")])
            layers.append(transfer_segmented_v3(image, source_points, target_points, bones, mask_mode=False))

        outline = base.make_outline(layers)
        composite = Image.new("RGBA", FRAME, (0, 0, 0, 0))
        for image in layers:
            composite.alpha_composite(image)
        composite.alpha_composite(outline)

        frame_path = frames_dir / f"s_walk_{index:02d}.png"
        composite.save(frame_path, optimize=False, compress_level=9)
        strip.alpha_composite(composite, (index * FRAME[0], 0))
        review_frames.append(base.checker_frame(composite))

        mask_hashes = {}
        for bank, source_mask in master_masks.items():
            bones = base.MASK_BONES[bank]
            warped = transfer_segmented_v3(source_mask, source_points, target_points, bones, mask_mode=True)
            mask_path = masks_dir / f"s_walk_{index:02d}_{bank}.png"
            warped.save(mask_path, optimize=False, compress_level=9)
            mask_hashes[bank] = sha256(mask_path)

        frame_reports.append({
            "frame": key,
            "rootTranslationPx": actor_target["rootTranslationPx"],
            "groundAnchor": actor_target["anchors"]["ground"],
            "pngSha256": sha256(frame_path),
            "masks": mask_hashes,
        })

    gif_path = out_dir / "clown_01_s_walk_foot_polish_v3.gif"
    review_frames[0].save(gif_path, save_all=True, append_images=review_frames[1:],
                          duration=args.duration_ms, loop=0, disposal=2)
    gif_validation = validate_gif(gif_path, 8)

    strip_path = out_dir / "clown_01_s_walk_foot_polish_v3_strip.png"
    strip.save(strip_path, optimize=False, compress_level=9)

    landmarks_path = out_dir / "landmarks.json"
    landmarks_path.write_text(json.dumps(landmarks, indent=2) + "\n", encoding="utf-8")

    invariant_ok = all(item["rootTranslationPx"] == [0, 0] and item["groundAnchor"] == list(ANCHOR)
                       for item in frame_reports)
    report = {
        "contract": "CH_CLOWN_TREADMILL_WALK_V3",
        "status": "candidate_for_visual_review" if invariant_ok else "invalid",
        "characterId": "clown_01",
        "direction": "S",
        "frames": 8,
        "durationMs": args.duration_ms,
        "motionMode": "treadmill_in_place",
        "motionSource": "approved_ch_actor_8_frame_cycle",
        "walkPolish": landmarks.get("walkPolish"),
        "shoePolish": {
            "scale": SHOE_SCALE,
            "rotationDamping": SHOE_ROTATION_DAMPING,
            "rotationLimitDeg": SHOE_ROTATION_LIMIT_DEG,
            "pivot": "ankle",
            "maskUsesSameTransform": True,
        },
        "groundAnchor": list(ANCHOR),
        "anchorInvariantPassed": invariant_ok,
        "gifValidation": gif_validation,
        "gif": {"path": str(gif_path), "sha256": sha256(gif_path)},
        "strip": {"path": str(strip_path), "sha256": sha256(strip_path)},
        "landmarks": {"path": str(landmarks_path), "sha256": sha256(landmarks_path)},
        "frameReports": frame_reports,
    }
    (out_dir / "treadmill_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if invariant_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
