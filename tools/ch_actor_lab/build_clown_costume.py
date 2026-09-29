"""Build the refined frame-aligned clown costume for the approved CH Actor.

CH_ACTOR_COSTUME_V2 never rewrites locomotion. It produces 48x64 RGBA overlays
whose file names, frame count and ground anchor match the approved CH Actor.
The art pass improves face readability, hair silhouette and costume volume while
keeping the original walk phases untouched.

Mask channels:
  R = primary costume
  G = secondary costume
  B = wig / hair
  A = overlay coverage

Face makeup, nose, mouth, collar and buttons are fixed authored details.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from software_render import ANCHOR, DIRECTIONS, ELEVATION, FRAME, SCALE, YAW

DEFAULT_ROOT = Path("assets/characters/ch_actor_green_01/costumes/clown_01")
DEFAULT_REVIEW = Path("tools/ch_actor_lab/art/costumes/clown_01_review.png")

PRIMARY_SHADE = (206, 206, 206, 245)
PRIMARY_LIGHT = (232, 232, 232, 255)
SECONDARY_SHADE = (170, 170, 170, 245)
SECONDARY_LIGHT = (203, 203, 203, 255)
WIG_BASE = (188, 188, 188, 255)
WIG_LIGHT = (220, 220, 220, 255)
OUTLINE = (59, 49, 43, 235)
FACE = (244, 239, 224, 250)
FACE_SHADOW = (218, 202, 185, 245)
NOSE = (226, 50, 43, 255)
MOUTH = (165, 49, 53, 255)
EYE = (49, 45, 44, 255)
EYE_MAKEUP = (65, 126, 194, 225)
COLLAR = (239, 239, 224, 255)
BUTTON = (246, 213, 63, 255)


def project(point: tuple[float, float, float], direction: float) -> tuple[float, float]:
    x, y, z = point
    c, s = math.cos(direction), math.sin(direction)
    x, z = c * x + s * z, -s * x + c * z
    right = math.cos(YAW) * x - math.sin(YAW) * z
    up = math.cos(ELEVATION) * y - math.sin(ELEVATION) * (
        math.sin(YAW) * x + math.cos(YAW) * z)
    return ANCHOR[0] + SCALE * right, ANCHOR[1] - SCALE * up


def phase_state(phase: float, idle: bool) -> tuple[float, float, float]:
    if idle:
        return 0.0, 0.0, 0.0
    sine = math.sin(2 * math.pi * phase)
    cosine = math.cos(2 * math.pi * phase)
    bob = .004 * abs(math.sin(4 * math.pi * phase))
    return sine, cosine, bob


def tint_primitive(draw: ImageDraw.ImageDraw, mask_draw: ImageDraw.ImageDraw,
                   primitive: str, xy, fill, channel: str, **kwargs) -> None:
    getattr(draw, primitive)(xy, fill=fill, **kwargs)
    select = {
        "R": (255, 0, 0, 255),
        "G": (0, 255, 0, 255),
        "B": (0, 0, 255, 255),
    }[channel]
    getattr(mask_draw, primitive)(xy, fill=select, **kwargs)


def leg_points(sign: int, sine: float, cosine: float, direction: float):
    # Identical kinematics to V1: visual refinements must never change locomotion.
    swing = sign * sine
    hip = (sign * .078, .405, 0)
    z = .145 * swing + .025 * sign * cosine
    lifted = max(0, swing) * .032 + max(0, sign * cosine) * .012
    foot = (sign * (.082 + .008 * abs(sine)), .035 + lifted, z)
    knee = (sign * .08, .225 + lifted * .33,
            z * .42 - .028 * max(0, swing))
    return project(hip, direction), project(knee, direction), project(foot, direction)


def draw_leg_and_shoe(draw, mask_draw, sign, channel, sine, cosine, direction):
    hip, knee, foot = leg_points(sign, sine, cosine, direction)
    coords = [(round(hip[0]), round(hip[1])),
              (round(knee[0]), round(knee[1])),
              (round(foot[0]), round(foot[1]))]
    shade = PRIMARY_SHADE if channel == "R" else SECONDARY_SHADE
    light = PRIMARY_LIGHT if channel == "R" else SECONDARY_LIGHT
    tint_primitive(draw, mask_draw, "line", coords, shade, channel,
                   width=4, joint="curve")

    # One-pixel highlight gives the trouser cylinder volume without changing pose.
    hi = [(x - 1, y) for x, y in coords]
    tint_primitive(draw, mask_draw, "line", hi, light, channel,
                   width=1, joint="curve")

    fx, fy = coords[-1]
    toe_dx = 4 if sign > 0 else -4
    shoe = [(fx - 2, fy - 1), (fx + toe_dx + 2, fy - 1),
            (fx + toe_dx + 3, fy + 1), (fx + toe_dx + 2, fy + 2),
            (fx - 2, fy + 2)]
    tint_primitive(draw, mask_draw, "polygon", shoe, shade, channel)
    # Shoe cap highlight; never draw below fy+2 so the approved ground anchor stays intact.
    cap_x = fx + toe_dx
    tint_primitive(draw, mask_draw, "line",
                   [(fx, fy), (cap_x + (1 if sign > 0 else -1), fy)],
                   light, channel, width=1)


def draw_costume_front(draw, mask_draw, chest, lower):
    cx, cy = map(round, chest)
    lx, ly = map(round, lower)

    # Broader split jacket with a darker outer edge and brighter inner plane.
    left = [(cx - 6, cy - 1), (cx - 1, cy - 4),
            (cx - 1, cy + 5), (cx - 5, cy + 4)]
    right = [(cx + 6, cy - 1), (cx + 1, cy - 4),
             (cx + 1, cy + 5), (cx + 5, cy + 4)]
    tint_primitive(draw, mask_draw, "polygon", left, PRIMARY_SHADE, "R")
    tint_primitive(draw, mask_draw, "polygon", right, SECONDARY_SHADE, "G")
    tint_primitive(draw, mask_draw, "line",
                   [(cx - 4, cy), (cx - 2, cy - 2), (cx - 2, cy + 3)],
                   PRIMARY_LIGHT, "R", width=1)
    tint_primitive(draw, mask_draw, "line",
                   [(cx + 4, cy), (cx + 2, cy - 2), (cx + 2, cy + 3)],
                   SECONDARY_LIGHT, "G", width=1)

    # White ruff/collar: small, readable and clearly separate from face makeup.
    draw.polygon([(cx - 5, cy - 4), (cx - 2, cy - 5), (cx, cy - 3),
                  (cx + 2, cy - 5), (cx + 5, cy - 4), (cx + 3, cy - 1),
                  (cx, cy - 2), (cx - 3, cy - 1)], fill=COLLAR)

    # Center seam and two buttons improve readability at gameplay scale.
    draw.line((cx, cy - 1, cx, cy + 5), fill=(69, 59, 54, 150), width=1)
    draw.point((cx, cy + 1), fill=BUTTON)
    draw.point((cx, cy + 4), fill=BUTTON)

    # Subtle waist accents; keep them inside the body silhouette.
    for off, channel, shade in ((-4, "R", PRIMARY_LIGHT),
                                (4, "G", SECONDARY_LIGHT)):
        tint_primitive(draw, mask_draw, "ellipse",
                       (lx + off - 1, ly - 1, lx + off + 1, ly + 1),
                       shade, channel)


def draw_wig(draw, mask_draw, hx: float, hy: float, facing: float):
    # Irregular authored tufts replace the V1 row of repeated circular blobs.
    # The asymmetry is intentional and gives a readable 3/4 silhouette.
    puffs = [
        (-7, -1, 3), (-6, -5, 3), (-3, -7, 4), (1, -8, 4),
        (5, -6, 4), (7, -2, 3), (6, 2, 3), (-6, 2, 3),
    ]
    if facing <= .2:
        puffs += [(-2, 1, 4), (2, 1, 4)]

    for i, (dx, dy, radius) in enumerate(puffs):
        box = (round(hx + dx - radius), round(hy + dy - radius),
               round(hx + dx + radius), round(hy + dy + radius))
        fill = WIG_LIGHT if i in (2, 3, 4) else WIG_BASE
        tint_primitive(draw, mask_draw, "ellipse", box, fill, "B",
                       outline=OUTLINE, width=1)

    # Tiny inner shadow breaks the flower-like silhouette without adding noise.
    draw.arc((round(hx - 6), round(hy - 8), round(hx + 7), round(hy + 5)),
             205, 340, fill=(79, 53, 42, 170), width=1)


def draw_face(draw, fx: int, fy: int):
    # Slight vertical oval reads more naturally in the 45/30 camera than a circle.
    draw.ellipse((fx - 5, fy - 6, fx + 5, fy + 5),
                 fill=FACE, outline=FACE_SHADOW, width=1)

    # Preserve a thin side shadow so the makeup still looks wrapped around a head.
    draw.arc((fx - 5, fy - 6, fx + 5, fy + 5), 70, 125,
             fill=FACE_SHADOW, width=1)

    # Eyes are one compact dark mark each. Blue makeup stays above/outside the eyes.
    draw.rectangle((fx - 3, fy - 2, fx - 2, fy - 1), fill=EYE)
    draw.rectangle((fx + 2, fy - 2, fx + 3, fy - 1), fill=EYE)
    draw.polygon([(fx - 4, fy - 3), (fx - 3, fy - 5), (fx - 2, fy - 3)],
                 fill=EYE_MAKEUP)
    draw.polygon([(fx + 4, fy - 3), (fx + 3, fy - 5), (fx + 2, fy - 3)],
                 fill=EYE_MAKEUP)

    # V1 nose covered too much of the mouth. V2 uses a clean 3x3 bulb.
    draw.ellipse((fx - 1, fy - 1, fx + 1, fy + 1), fill=NOSE)
    draw.point((fx, fy - 1), fill=(245, 92, 75, 255))

    # Small curved smile with separate cheek pixels; no muddy red face patch.
    draw.arc((fx - 3, fy, fx + 3, fy + 4), 15, 165, fill=MOUTH, width=1)
    draw.point((fx - 4, fy + 1), fill=(204, 92, 82, 210))
    draw.point((fx + 4, fy + 1), fill=(204, 92, 82, 210))


def build_frame(direction_key: str, direction: float, phase: float, idle: bool):
    overlay = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    mask = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    mask_draw = ImageDraw.Draw(mask)
    sine, cosine, bob = phase_state(phase, idle)

    draw_leg_and_shoe(draw, mask_draw, -1, "R", sine, cosine, direction)
    draw_leg_and_shoe(draw, mask_draw, 1, "G", sine, cosine, direction)

    facing = math.cos(direction - YAW)
    chest = project((0, .67 + bob, .11), direction)
    lower = project((0, .53 + bob, .11), direction)
    if facing > .2:
        draw_costume_front(draw, mask_draw, chest, lower)

    head = project((0, .875 + bob, 0), direction)
    hx, hy = head
    draw_wig(draw, mask_draw, hx, hy, facing)

    if facing > .2:
        face = project((0, .858 + bob, .113), direction)
        fx, fy = map(round, face)
        draw_face(draw, fx, fy)

    return overlay, mask


def build(root: Path, review_path: Path) -> None:
    frame_dir = root / "frames"
    mask_dir = root / "masks"
    frame_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    angles = {logical.lower(): angle for logical, _, angle in DIRECTIONS}
    entries: list[str] = []

    for key in "senw":
        direction = angles[key]
        names = [(f"{key}_idle.png", 0.0, True)]
        names += [(f"{key}_walk_{i:02d}.png", i / 8.0, False) for i in range(8)]
        for filename, phase, idle in names:
            overlay, mask = build_frame(key, direction, phase, idle)
            overlay.save(frame_dir / filename)
            mask.save(mask_dir / filename)
            entries.append(filename)

    manifest = {
        "contract": "CH_ACTOR_COSTUME_V2",
        "actor": "ch_actor_green_01",
        "costume": "clown_01",
        "motionPolicy": "reuse_approved_actor_frames_without_pose_changes",
        "frame": {
            "width": FRAME[0],
            "height": FRAME[1],
            "groundAnchor": list(ANCHOR),
        },
        "maskChannels": {
            "R": "primary_costume",
            "G": "secondary_costume",
            "B": "wig",
            "A": "overlay_alpha",
        },
        "fixedArt": [
            "white_face_makeup", "red_nose", "red_mouth",
            "blue_eye_makeup", "white_ruff", "gold_buttons",
        ],
        "visualRevision": {
            "version": 2,
            "goals": [
                "cleaner_face_readability",
                "asymmetric_volumetric_wig",
                "stronger_three_quarter_costume_volume",
                "preserve_approved_walk_and_ground_anchor",
            ],
        },
        "frames": entries,
        "notes": [
            "Overlay names match approved CH Actor frame names one-for-one.",
            "Approved body/walk PNGs are never rewritten.",
            "No costume primitive is allowed below the approved foot extent.",
            "Tint shading is derived from overlay luminance at runtime.",
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    review_path.parent.mkdir(parents=True, exist_ok=True)
    board = Image.new("RGBA", (4 * 144, 3 * 192), (42, 65, 56, 255))
    for col, key in enumerate("senw"):
        for row, filename in enumerate(
                (f"{key}_idle.png", f"{key}_walk_02.png", f"{key}_walk_06.png")):
            image = Image.open(frame_dir / filename).convert("RGBA").resize(
                (144, 192), Image.Resampling.NEAREST)
            board.alpha_composite(image, (col * 144, row * 192))
    board.save(review_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()
    build(args.root, args.review)
    print(f"Wrote refined clown costume V2 to {args.root}")


if __name__ == "__main__":
    main()
