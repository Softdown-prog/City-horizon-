#!/usr/bin/env python3
"""Build clown_01 SOUTH 8-frame in-place/treadmill walk.

Appearance is transferred from the approved-art candidate S/idle. Locomotion is
read from treadmill_landmarks.py, which mirrors the already approved CH Actor
8-frame pose cycle. Ground anchor/root translation stay fixed for every frame.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from build_clown_master import ART_ROOT, LAYER_RECIPES, MASK_RECIPES, OUTLINE_RGBA
from character_draw_cli import load_json, render
from treadmill_landmarks import ANCHOR, FRAME, build as build_landmarks

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYER_ANCHORS = {
    "skin": ["head", "neck", "hand_L", "hand_R"],
    "hair": ["head", "head_top", "neck"],
    "face": ["head", "head_top", "neck"],
    "upper_clothing": ["neck", "chest", "pelvis", "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "hand_L", "hand_R"],
    "lower_clothing": ["pelvis", "hip_L", "hip_R", "knee_L", "knee_R", "ankle_L", "ankle_R"],
    "footwear": ["ankle_L", "ankle_R", "foot_L", "foot_R"],
    "accessories_front": ["head", "neck", "chest", "pelvis", "shoulder_L", "shoulder_R", "hand_L", "hand_R", "hip_L", "hip_R", "foot_L", "foot_R"],
}
MASK_ANCHORS = {
    "appearance": ["head", "head_top", "neck", "hand_L", "hand_R"],
    "clothing": ["neck", "chest", "pelvis", "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "hand_L", "hand_R", "hip_L", "hip_R", "knee_L", "knee_R", "ankle_L", "ankle_R", "foot_L", "foot_R"],
    "held_object": ["hand_L", "hand_R"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted_inverse(x: float, y: float, names: list[str], source: dict, target: dict) -> tuple[float, float]:
    candidates = []
    for name in names:
        sp = source.get(name)
        tp = target.get(name)
        if not isinstance(sp, list) or not isinstance(tp, list):
            continue
        dx, dy = x - tp[0], y - tp[1]
        candidates.append((dx * dx + dy * dy, sp, tp))
    candidates.sort(key=lambda item: item[0])
    candidates = candidates[:4]
    if not candidates:
        return x, y
    total = 0.0
    ox = oy = 0.0
    for d2, sp, tp in candidates:
        weight = 1.0 / (d2 + 3.0)
        total += weight
        ox += (sp[0] - tp[0]) * weight
        oy += (sp[1] - tp[1]) * weight
    return x + ox / total, y + oy / total


def transfer(source_image: Image.Image, source_frame: dict, target_frame: dict, anchors: list[str]) -> Image.Image:
    src = source_image.convert("RGBA")
    out = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    src_px = src.load()
    out_px = out.load()
    source_points = source_frame.get("points", {})
    target_points = target_frame.get("points", {})
    for y in range(FRAME[1]):
        for x in range(FRAME[0]):
            sx, sy = weighted_inverse(x + .5, y + .5, anchors, source_points, target_points)
            ix, iy = int(round(sx - .5)), int(round(sy - .5))
            if 0 <= ix < FRAME[0] and 0 <= iy < FRAME[1]:
                out_px[x, y] = src_px[ix, iy]
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
    source_frame = landmarks["frames"]["S:idle"]
    master_layers = {name: render(load_json(ART_ROOT / filename), args.seed) for name, filename in LAYER_RECIPES}
    master_masks = {name: render(load_json(ART_ROOT / filename), args.seed) for name, filename in MASK_RECIPES}

    transparent_frames: list[Image.Image] = []
    review_frames: list[Image.Image] = []
    frame_reports = []

    for index in range(8):
        key = f"S:walk_{index:02d}"
        target_frame = landmarks["frames"][key]
        layers = []
        for name, image in master_layers.items():
            layers.append(transfer(image, source_frame, target_frame, LAYER_ANCHORS.get(name, LAYER_ANCHORS["accessories_front"])))
        outline = make_outline(layers)
        composite = Image.new("RGBA", FRAME, (0,0,0,0))
        for image in layers:
            composite.alpha_composite(image)
        composite.alpha_composite(outline)
        path = frames_dir / f"s_walk_{index:02d}.png"
        composite.save(path, optimize=False, compress_level=9)
        transparent_frames.append(composite)
        review_frames.append(checker_frame(composite))

        mask_hashes = {}
        for bank, source_mask in master_masks.items():
            warped = transfer(source_mask, source_frame, target_frame, MASK_ANCHORS[bank])
            mask_path = masks_dir / f"s_walk_{index:02d}_{bank}.png"
            warped.save(mask_path, optimize=False, compress_level=9)
            mask_hashes[bank] = sha256(mask_path)

        frame_reports.append({
            "frame": key,
            "rootTranslationPx": target_frame["rootTranslationPx"],
            "groundAnchor": target_frame["anchors"]["ground"],
            "pngSha256": sha256(path),
            "masks": mask_hashes,
        })

    gif_path = out_dir / "clown_01_s_walk_treadmill.gif"
    review_frames[0].save(gif_path, save_all=True, append_images=review_frames[1:], duration=args.duration_ms, loop=0, disposal=2)

    landmarks_path = out_dir / "landmarks.json"
    landmarks_path.write_text(json.dumps(landmarks, indent=2) + "\n", encoding="utf-8")

    invariant_ok = all(item["rootTranslationPx"] == [0,0] and item["groundAnchor"] == list(ANCHOR) for item in frame_reports)
    report = {
        "contract": "CH_CLOWN_TREADMILL_WALK_V0",
        "status": "candidate_for_visual_review" if invariant_ok else "invalid",
        "characterId": "clown_01",
        "direction": "S",
        "frames": 8,
        "durationMs": args.duration_ms,
        "motionSource": "approved_ch_actor_8_frame_cycle",
        "motionMode": "treadmill_in_place",
        "worldTranslationDuringSpriteCycle": False,
        "groundAnchor": list(ANCHOR),
        "anchorInvariantPassed": invariant_ok,
        "gif": {"path": str(gif_path), "sha256": sha256(gif_path)},
        "landmarks": {"path": str(landmarks_path), "sha256": sha256(landmarks_path)},
        "frameReports": frame_reports,
    }
    report_path = out_dir / "treadmill_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if invariant_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
