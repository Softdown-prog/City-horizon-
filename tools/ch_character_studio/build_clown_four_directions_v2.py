#!/usr/bin/env python3
"""Build clown_01 S/E/N/W V2 using isometric 3/4 directional masters.

Preserves the approved treadmill motion, V4 leg polish, V3 rigid shoes, 48x64
frame, [24,60] ground anchor and runtime-only world translation. Only directional
appearance/authoring rigs differ from V1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image

import build_clown_four_directions as common
import build_clown_treadmill as body
import build_clown_treadmill_v3 as foot
from clown_directional_art_v2 import build_direction
from character_draw_cli import load_json
from treadmill_landmarks import ANCHOR, FRAME, build as build_landmarks

REPO_ROOT = Path(__file__).resolve().parents[2]
RIG_PATH = Path(__file__).resolve().parent / "art" / "clown_01" / "directional_authoring_landmarks_v2.json"
DIRECTIONS = ("S", "E", "N", "W")
FRAMES = 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("out/ch_character_studio/clown_01/four_directions_v2"))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--duration-ms", type=int, default=138)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    rig = load_json(RIG_PATH)
    if rig.get("contract") != "CH_CHARACTER_DIRECTIONAL_ART_LANDMARKS_V2":
        raise ValueError("directional rig must use CH_CHARACTER_DIRECTIONAL_ART_LANDMARKS_V2")
    landmarks = build_landmarks()

    sheet = Image.new("RGBA", (FRAME[0] * FRAMES, FRAME[1] * 4), (0,0,0,0))
    idle_strip = Image.new("RGBA", (FRAME[0] * 4, FRAME[1]), (0,0,0,0))
    review_by_tick = [[] for _ in range(FRAMES)]
    report_dirs = {}

    for row, direction in enumerate(DIRECTIONS):
        direction_dir = out_dir / direction.lower()
        frames_dir = direction_dir / "frames"
        masks_dir = direction_dir / "masks"
        frames_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)

        master_layers, master_masks = build_direction(direction, args.seed)
        source_points = rig["directions"][direction]
        actor_idle = landmarks["frames"][f"{direction}:idle"]["points"]

        idle = common.composite_layers(master_layers)
        idle_file = direction_dir / f"clown_01_{direction.lower()}_idle_v2.png"
        idle.save(idle_file, optimize=False, compress_level=9)
        idle_strip.alpha_composite(idle, (row * FRAME[0], 0))
        for bank, mask in master_masks.items():
            mask.save(masks_dir / f"{direction.lower()}_idle_{bank}.png", optimize=False, compress_level=9)

        reviews = []
        frame_reports = []
        for index in range(FRAMES):
            key = f"{direction}:walk_{index:02d}"
            actor_target = landmarks["frames"][key]
            target_points = body.retarget_points(source_points, actor_idle, actor_target["points"])

            posed_layers = {}
            for name, source in master_layers.items():
                bones = body.LAYER_BONES.get(name, [("torso", "neck", "pelvis")])
                posed_layers[name] = foot.transfer_segmented_v3(
                    source, source_points, target_points, bones, mask_mode=False
                )
            composite = common.composite_layers(posed_layers)
            frame_file = frames_dir / f"{direction.lower()}_walk_{index:02d}.png"
            composite.save(frame_file, optimize=False, compress_level=9)
            sheet.alpha_composite(composite, (index * FRAME[0], row * FRAME[1]))

            review = common.checker(composite, 4)
            reviews.append(review)
            review_by_tick[index].append(review)

            mask_hashes = {}
            for bank, source_mask in master_masks.items():
                bones = body.MASK_BONES[bank]
                posed_mask = foot.transfer_segmented_v3(
                    source_mask, source_points, target_points, bones, mask_mode=True
                )
                mask_file = masks_dir / f"{direction.lower()}_walk_{index:02d}_{bank}.png"
                posed_mask.save(mask_file, optimize=False, compress_level=9)
                mask_hashes[bank] = common.sha256(mask_file)

            frame_reports.append({
                "frame": key,
                "groundAnchor": actor_target["anchors"]["ground"],
                "rootTranslationPx": actor_target["rootTranslationPx"],
                "pngSha256": common.sha256(frame_file),
                "masks": mask_hashes,
            })

        gif_file = direction_dir / f"clown_01_{direction.lower()}_walk_v2.gif"
        validation = common.save_gif(reviews, gif_file, args.duration_ms)
        invariant_ok = all(
            fr["groundAnchor"] == list(ANCHOR) and fr["rootTranslationPx"] == [0,0]
            for fr in frame_reports
        )
        report_dirs[direction] = {
            "idle": {"path": str(idle_file), "sha256": common.sha256(idle_file)},
            "walkGif": {"path": str(gif_file), "sha256": common.sha256(gif_file),
                        "validation": validation},
            "anchorInvariantPassed": invariant_ok,
            "frames": frame_reports,
        }

    sheet_file = out_dir / "clown_01_walk_4dir_v2_sheet.png"
    sheet.save(sheet_file, optimize=False, compress_level=9)
    idle_file = out_dir / "clown_01_idle_4dir_v2_strip.png"
    idle_strip.save(idle_file, optimize=False, compress_level=9)

    board_frames = []
    for tick in range(FRAMES):
        board = Image.new("RGBA", (384,512), (35,45,52,255))
        for cell, pos in zip(review_by_tick[tick], ((0,0),(192,0),(0,256),(192,256))):
            board.alpha_composite(cell, pos)
        board_frames.append(board)
    board_gif = out_dir / "clown_01_walk_4dir_v2_review.gif"
    board_validation = common.save_gif(board_frames, board_gif, args.duration_ms)

    all_invariants = all(v["anchorInvariantPassed"] for v in report_dirs.values())
    report = {
        "contract": "CH_CLOWN_4DIR_WALK_V2",
        "status": "candidate_for_visual_review" if all_invariants else "invalid",
        "characterId": "clown_01",
        "directions": list(DIRECTIONS),
        "framesPerDirection": FRAMES,
        "totalWalkFrames": 32,
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "motionMode": "treadmill_in_place",
        "motionProfile": landmarks.get("walkPolish"),
        "directionalArt": "isometric_three_quarter_v2",
        "cameraIntent": "CH_ACTOR_CAMERA_V1_45deg_30deg",
        "artPolicy": {
            "south": "reviewed_master_preserved",
            "eastWest": "independent_three_quarter_masters_not_flat_profiles",
            "north": "independent_rear_three_quarter_master_no_front_face",
            "crossDirectionRasterWarp": false
        },
        "anchorInvariantPassed": all_invariants,
        "sheet": {"path": str(sheet_file), "sha256": common.sha256(sheet_file),
                  "layout": "8_columns_x_4_rows", "rows": list(DIRECTIONS)},
        "idleStrip": {"path": str(idle_file), "sha256": common.sha256(idle_file),
                      "order": list(DIRECTIONS)},
        "reviewGif": {"path": str(board_gif), "sha256": common.sha256(board_gif),
                      "validation": board_validation},
        "directionsData": report_dirs,
    }
    (out_dir / "four_direction_v2_report.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all_invariants else 2


if __name__ == "__main__":
    raise SystemExit(main())
