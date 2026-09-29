#!/usr/bin/env python3
"""Build clown_01 in S/E/N/W with 8 in-place walk frames per direction.

Each direction owns an independently authored idle master. The current approved
motion policy is reused unchanged: V4 leg polish, V3 rigid-shoe polish, fixed
48x64 frame and [24,60] ground anchor. World translation remains runtime-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

import build_clown_treadmill as body
import build_clown_treadmill_v3 as foot
from clown_directional_art import build_direction
from character_draw_cli import load_json
from treadmill_landmarks import ANCHOR, FRAME, build as build_landmarks

REPO_ROOT = Path(__file__).resolve().parents[2]
RIG_PATH = Path(__file__).resolve().parent / "art" / "clown_01" / "directional_authoring_landmarks.json"
DIRECTIONS = ("S", "E", "N", "W")
FRAMES = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def composite_layers(layers: dict[str, Image.Image]) -> Image.Image:
    ordered = [layers[name] for name in body.LAYER_BONES if name in layers]
    # Preserve any semantic layer not listed in LAYER_BONES as well.
    for name, image in layers.items():
        if name not in body.LAYER_BONES:
            ordered.append(image)
    outline = body.make_outline(ordered)
    out = Image.new("RGBA", FRAME, (0,0,0,0))
    for image in ordered:
        out.alpha_composite(image)
    out.alpha_composite(outline)
    return out


def checker(image: Image.Image, scale: int = 4) -> Image.Image:
    bg = Image.new("RGBA", FRAME, (45,58,65,255))
    draw = ImageDraw.Draw(bg)
    cell = 4
    for y in range(0, FRAME[1], cell):
        for x in range(0, FRAME[0], cell):
            if ((x // cell) + (y // cell)) & 1:
                draw.rectangle((x,y,min(x+cell-1,47),min(y+cell-1,63)), fill=(57,73,80,255))
    bg.alpha_composite(image)
    return bg.resize((FRAME[0]*scale, FRAME[1]*scale), Image.Resampling.NEAREST)


def save_gif(frames: list[Image.Image], path: Path, duration: int) -> dict:
    pal = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=duration,
                loop=0, disposal=2)
    return foot.validate_gif(path, len(frames))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("out/ch_character_studio/clown_01/four_directions"))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--duration-ms", type=int, default=138)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rig = load_json(RIG_PATH)
    if rig.get("contract") != "CH_CHARACTER_DIRECTIONAL_ART_LANDMARKS_V1":
        raise ValueError("directional rig must use CH_CHARACTER_DIRECTIONAL_ART_LANDMARKS_V1")
    landmarks = build_landmarks()

    sheet = Image.new("RGBA", (FRAME[0] * FRAMES, FRAME[1] * len(DIRECTIONS)), (0,0,0,0))
    idle_strip = Image.new("RGBA", (FRAME[0] * len(DIRECTIONS), FRAME[1]), (0,0,0,0))
    review_by_tick: list[list[Image.Image]] = [[] for _ in range(FRAMES)]
    report_dirs: dict[str, dict] = {}

    for row, direction in enumerate(DIRECTIONS):
        direction_dir = out_dir / direction.lower()
        frames_dir = direction_dir / "frames"
        masks_dir = direction_dir / "masks"
        direction_dir.mkdir(parents=True, exist_ok=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)

        master_layers, master_masks = build_direction(direction, args.seed)
        source_points = rig["directions"][direction]
        actor_idle = landmarks["frames"][f"{direction}:idle"]["points"]

        idle = composite_layers(master_layers)
        idle_path = direction_dir / f"clown_01_{direction.lower()}_idle.png"
        idle.save(idle_path, optimize=False, compress_level=9)
        idle_strip.alpha_composite(idle, (row * FRAME[0], 0))

        for bank, mask in master_masks.items():
            mask.save(masks_dir / f"{direction.lower()}_idle_{bank}.png", optimize=False, compress_level=9)

        direction_reviews: list[Image.Image] = []
        frame_reports = []
        for index in range(FRAMES):
            key = f"{direction}:walk_{index:02d}"
            actor_target = landmarks["frames"][key]
            target_points = body.retarget_points(source_points, actor_idle, actor_target["points"])

            posed_layers: dict[str, Image.Image] = {}
            for name, source in master_layers.items():
                bones = body.LAYER_BONES.get(name, [("torso", "neck", "pelvis")])
                posed_layers[name] = foot.transfer_segmented_v3(
                    source, source_points, target_points, bones, mask_mode=False
                )
            composite = composite_layers(posed_layers)
            frame_path = frames_dir / f"{direction.lower()}_walk_{index:02d}.png"
            composite.save(frame_path, optimize=False, compress_level=9)
            sheet.alpha_composite(composite, (index * FRAME[0], row * FRAME[1]))

            review = checker(composite, 4)
            direction_reviews.append(review)
            review_by_tick[index].append(review)

            mask_hashes = {}
            for bank, source_mask in master_masks.items():
                bones = body.MASK_BONES[bank]
                posed_mask = foot.transfer_segmented_v3(
                    source_mask, source_points, target_points, bones, mask_mode=True
                )
                mask_path = masks_dir / f"{direction.lower()}_walk_{index:02d}_{bank}.png"
                posed_mask.save(mask_path, optimize=False, compress_level=9)
                mask_hashes[bank] = sha256(mask_path)

            frame_reports.append({
                "frame": key,
                "groundAnchor": actor_target["anchors"]["ground"],
                "rootTranslationPx": actor_target["rootTranslationPx"],
                "pngSha256": sha256(frame_path),
                "masks": mask_hashes,
            })

        gif_path = direction_dir / f"clown_01_{direction.lower()}_walk.gif"
        gif_validation = save_gif(direction_reviews, gif_path, args.duration_ms)
        invariant_ok = all(
            fr["groundAnchor"] == list(ANCHOR) and fr["rootTranslationPx"] == [0,0]
            for fr in frame_reports
        )
        report_dirs[direction] = {
            "idle": {"path": str(idle_path), "sha256": sha256(idle_path)},
            "walkGif": {"path": str(gif_path), "sha256": sha256(gif_path),
                        "validation": gif_validation},
            "anchorInvariantPassed": invariant_ok,
            "frames": frame_reports,
        }

    sheet_path = out_dir / "clown_01_walk_4dir_sheet.png"
    sheet.save(sheet_path, optimize=False, compress_level=9)
    idle_path = out_dir / "clown_01_idle_4dir_strip.png"
    idle_strip.save(idle_path, optimize=False, compress_level=9)

    # One review GIF shows the same animation tick in all four directions.
    board_frames: list[Image.Image] = []
    for tick in range(FRAMES):
        board = Image.new("RGBA", (FRAME[0]*4*2, FRAME[1]*4*2), (35,45,52,255))
        # 2x2 board: S/E on top, N/W below. Each review cell is 192x256.
        positions = ((0,0),(192,0),(0,256),(192,256))
        for cell, pos in zip(review_by_tick[tick], positions):
            board.alpha_composite(cell, pos)
        board_frames.append(board)
    board_gif = out_dir / "clown_01_walk_4dir_review.gif"
    board_validation = save_gif(board_frames, board_gif, args.duration_ms)

    all_invariants = all(data["anchorInvariantPassed"] for data in report_dirs.values())
    report = {
        "contract": "CH_CLOWN_4DIR_WALK_V1",
        "status": "candidate_for_visual_review" if all_invariants else "invalid",
        "characterId": "clown_01",
        "directions": list(DIRECTIONS),
        "framesPerDirection": FRAMES,
        "totalWalkFrames": FRAMES * len(DIRECTIONS),
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "motionMode": "treadmill_in_place",
        "motionProfile": landmarks.get("walkPolish"),
        "shoePolish": {
            "rotationDamping": foot.SHOE_ROTATION_DAMPING,
            "rotationLimitDeg": foot.SHOE_ROTATION_LIMIT_DEG,
            "scale": foot.SHOE_SCALE,
            "pivot": "ankle"
        },
        "artPolicy": {
            "south": "reviewed_south_master_preserved",
            "eastWest": "independent_profile_art",
            "north": "independent_back_art_no_front_face",
            "crossDirectionRasterWarp": False
        },
        "anchorInvariantPassed": all_invariants,
        "sheet": {"path": str(sheet_path), "sha256": sha256(sheet_path),
                  "layout": "8_columns_x_4_rows", "rows": list(DIRECTIONS)},
        "idleStrip": {"path": str(idle_path), "sha256": sha256(idle_path),
                      "order": list(DIRECTIONS)},
        "reviewGif": {"path": str(board_gif), "sha256": sha256(board_gif),
                      "validation": board_validation},
        "directionsData": report_dirs,
    }
    report_path = out_dir / "four_direction_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all_invariants else 2


if __name__ == "__main__":
    raise SystemExit(main())
