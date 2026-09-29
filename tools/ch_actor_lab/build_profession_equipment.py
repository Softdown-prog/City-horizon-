"""Build profession equipment overlays for the approved CH Actor.

The production pedestrian remains the exact approved 48x64 CH Actor.  This tool
only generates transparent, frame-aligned equipment layers.  The first profile
is the city cleaner broom.  It deliberately reuses the actor's camera, walk
phases and hand kinematics instead of authoring a second walk cycle.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from software_render import ANCHOR, DIRECTIONS, ELEVATION, FRAME, SCALE, YAW

DEFAULT_OUTPUT = Path("assets/characters/ch_actor_green_01/equipment/broom/frames")
DEFAULT_MANIFEST = Path("assets/characters/ch_actor_green_01/equipment/broom/manifest.json")
DEFAULT_REVIEW = Path("tools/ch_actor_lab/art/professions/cleaner_broom_review.png")


def project(point: tuple[float, float, float], direction: float) -> tuple[float, float]:
    x, y, z = point
    c, s = math.cos(direction), math.sin(direction)
    x, z = c * x + s * z, -s * x + c * z
    right = math.cos(YAW) * x - math.sin(YAW) * z
    up = math.cos(ELEVATION) * y - math.sin(ELEVATION) * (
        math.sin(YAW) * x + math.cos(YAW) * z)
    return ANCHOR[0] + SCALE * right, ANCHOR[1] - SCALE * up


def hand_contact(direction_key: str, direction: float, sine: float, idle: bool) -> tuple[float, float]:
    # Matches software_render.ActorPainter.arm().  SOUTH/NORTH use the +X hand;
    # EAST/WEST use the -X hand, mirroring the approved umbrella attachment rule.
    sign = 1 if direction_key.lower() in "sn" else -1
    phase = 0.0 if idle else (0.25 if sine > 0 else 0.75 if sine < 0 else 0.0)
    bob = 0.0 if idle else .004 * abs(math.sin(4 * math.pi * phase))
    opposite = -sign * sine
    hand = (sign * .19, .445 + bob, .115 * opposite + .01)
    return project(hand, direction)


def make_broom(direction_key: str, direction: float, sine: float, idle: bool) -> Image.Image:
    image = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    hand_x, hand_y = hand_contact(direction_key, direction, sine, idle)

    side = {"s": 7, "n": -7, "e": 8, "w": -8}[direction_key]
    brush_x = max(7.0, min(41.0, hand_x + side))
    brush_y = 58.0
    vx, vy = brush_x - hand_x, brush_y - hand_y
    length = max(1.0, math.hypot(vx, vy))
    shaft_start = (hand_x + vx / length * 1.5, hand_y + vy / length * 1.5)
    shaft_end = (brush_x, brush_y - 3.0)

    # Dark rim + warm wood highlight keeps the handle readable at 1x.
    draw.line((*map(round, shaft_start), *map(round, shaft_end)), fill=(57, 38, 26, 255), width=2)
    draw.line((round(shaft_start[0]), round(shaft_start[1]),
               round(shaft_end[0] - .5), round(shaft_end[1] - .5)),
              fill=(151, 102, 57, 255), width=1)

    ferrule_x, ferrule_y = shaft_end
    draw.line((round(ferrule_x - 1), round(ferrule_y),
               round(ferrule_x + 1), round(ferrule_y + 1)),
              fill=(88, 92, 91, 255), width=2)

    if direction_key in "sn":
        head = [(brush_x - 5, brush_y - 2), (brush_x + 4, brush_y),
                (brush_x + 4, brush_y + 2), (brush_x - 5, brush_y)]
    else:
        head = [(brush_x - 4, brush_y), (brush_x + 4, brush_y - 2),
                (brush_x + 5, brush_y), (brush_x - 3, brush_y + 2)]
    draw.polygon([(round(x), round(y)) for x, y in head], fill=(124, 72, 38, 255))

    bristle_y = min(FRAME[1] - 1, round(brush_y + 3))
    for offset in (-4, -2, 0, 2, 4):
        x = max(1.0, min(FRAME[0] - 2.0, brush_x + offset))
        lean = .8 if direction_key in "se" else -.8
        draw.line((round(x), round(brush_y), round(x + lean), bristle_y),
                  fill=(194, 157, 91, 255), width=1)
    return image


def build(output: Path, manifest_path: Path, review_path: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    direction_angles = {logical.lower(): angle for logical, _, angle in DIRECTIONS}
    manifest: dict[str, object] = {
        "contract": "CH_ACTOR_EQUIPMENT_V1",
        "actor": "ch_actor_green_01",
        "equipment": "broom",
        "frame": {"width": FRAME[0], "height": FRAME[1], "groundAnchor": list(ANCHOR)},
        "poses": {},
    }

    for key in "senw":
        angle = direction_angles[key]
        poses = {
            "idle": make_broom(key, angle, 0.0, True),
            "walk_pos": make_broom(key, angle, 1.0, False),
            "walk_neg": make_broom(key, angle, -1.0, False),
        }
        for name, image in poses.items():
            image.save(output / f"{key}_{name}.png")
        manifest["poses"][key] = {
            "idle": f"{key}_idle.png",
            "walkFrames": [
                f"{key}_idle.png",
                f"{key}_walk_pos.png", f"{key}_walk_pos.png", f"{key}_walk_pos.png",
                f"{key}_idle.png",
                f"{key}_walk_neg.png", f"{key}_walk_neg.png", f"{key}_walk_neg.png",
            ],
        }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    review_path.parent.mkdir(parents=True, exist_ok=True)
    board = Image.new("RGBA", (FRAME[0] * 3 * 4, FRAME[1]), (40, 60, 50, 255))
    for row, key in enumerate("senw"):
        for col, pose in enumerate(("idle", "walk_pos", "walk_neg")):
            image = Image.open(output / f"{key}_{pose}.png").convert("RGBA")
            board.alpha_composite(image, (row * FRAME[0] * 3 + col * FRAME[0], 0))
    board.save(review_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()
    build(args.output, args.manifest, args.review)
    print(f"Cleaner broom equipment written to {args.output}")
