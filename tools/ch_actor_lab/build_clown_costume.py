"""Build a frame-aligned clown costume for the approved CH Actor.

CH_ACTOR_COSTUME_V1 keeps the approved 48x64 body/walk intact. The generated
overlay adds clown-only pixels (wig, makeup, bow tie, trouser accents and shoes).
The mask uses R=primary costume, G=secondary costume, B=wig/hair and A=overlay
alpha. Makeup and red nose are fixed authored colors and remain outside tint
channels.
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


def tint_pixel(draw: ImageDraw.ImageDraw, mask_draw: ImageDraw.ImageDraw,
               primitive: str, xy, fill, channel: str, **kwargs) -> None:
    getattr(draw, primitive)(xy, fill=fill, **kwargs)
    select = {"R": (255, 0, 0, 255), "G": (0, 255, 0, 255), "B": (0, 0, 255, 255)}[channel]
    getattr(mask_draw, primitive)(xy, fill=select, **kwargs)


def leg_points(sign: int, sine: float, cosine: float, direction: float):
    swing = sign * sine
    hip = (sign * .078, .405, 0)
    z = .145 * swing + .025 * sign * cosine
    lifted = max(0, swing) * .032 + max(0, sign * cosine) * .012
    foot = (sign * (.082 + .008 * abs(sine)), .035 + lifted, z)
    knee = (sign * .08, .225 + lifted * .33,
            z * .42 - .028 * max(0, swing))
    return project(hip, direction), project(knee, direction), project(foot, direction)


def build_frame(direction_key: str, direction: float, phase: float, idle: bool):
    overlay = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    mask = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    mask_draw = ImageDraw.Draw(mask)
    sine, cosine, bob = phase_state(phase, idle)

    for sign, channel, fill in ((-1, "R", (210, 210, 210, 230)),
                                (1, "G", (175, 175, 175, 230))):
        hip, knee, foot = leg_points(sign, sine, cosine, direction)
        coords = [(round(hip[0]), round(hip[1])),
                  (round(knee[0]), round(knee[1])),
                  (round(foot[0]), round(foot[1]))]
        tint_pixel(draw, mask_draw, "line", coords, fill, channel, width=3, joint="curve")
        fx, fy = coords[-1]
        toe_dx = 3 if sign > 0 else -3
        shoe = [(fx - 2, fy - 1), (fx + toe_dx + 2, fy - 1),
                (fx + toe_dx + 3, fy + 2), (fx - 2, fy + 2)]
        tint_pixel(draw, mask_draw, "polygon", shoe, fill, channel)

    facing = math.cos(direction - YAW)
    chest = project((0, .67 + bob, .11), direction)
    lower = project((0, .53 + bob, .11), direction)
    if facing > .2:
        cx, cy = map(round, chest)
        left = [(cx - 5, cy), (cx - 1, cy - 3), (cx - 1, cy + 3)]
        right = [(cx + 5, cy), (cx + 1, cy - 3), (cx + 1, cy + 3)]
        tint_pixel(draw, mask_draw, "polygon", left, (210, 210, 210, 255), "R")
        tint_pixel(draw, mask_draw, "polygon", right, (180, 180, 180, 255), "G")
        draw.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=(245, 224, 78, 255))
        lx, ly = map(round, lower)
        for off, channel, shade in ((-5, "R", 215), (0, "G", 180), (5, "R", 205)):
            tint_pixel(draw, mask_draw, "ellipse",
                       (lx + off - 1, ly - 1, lx + off + 1, ly + 1),
                       (shade, shade, shade, 235), channel)

    head = project((0, .875 + bob, 0), direction)
    hx, hy = head
    puffs = [(-7, -2, 4), (-4, -6, 4), (0, -7, 4),
             (4, -6, 4), (7, -2, 4), (-6, 3, 3), (6, 3, 3)]
    if facing <= .2:
        puffs += [(0, 2, 6)]
    for dx, dy, radius in puffs:
        box = (round(hx + dx - radius), round(hy + dy - radius),
               round(hx + dx + radius), round(hy + dy + radius))
        tint_pixel(draw, mask_draw, "ellipse", box, (195, 195, 195, 255), "B",
                   outline=(78, 54, 40, 255), width=1)

    if facing > .2:
        face = project((0, .858 + bob, .113), direction)
        fx, fy = map(round, face)
        draw.ellipse((fx - 5, fy - 5, fx + 5, fy + 5),
                     fill=(245, 242, 232, 245), outline=(215, 210, 201, 255))
        draw.rectangle((fx - 3, fy - 1, fx - 2, fy), fill=(45, 37, 33, 255))
        draw.rectangle((fx + 2, fy - 1, fx + 3, fy), fill=(45, 37, 33, 255))
        draw.ellipse((fx - 2, fy, fx + 2, fy + 4), fill=(210, 44, 52, 255))
        draw.arc((fx - 4, fy + 1, fx + 4, fy + 6), 10, 170,
                 fill=(193, 44, 58, 255), width=1)
        draw.polygon([(fx - 4, fy - 3), (fx - 2, fy - 5), (fx - 1, fy - 2)],
                     fill=(62, 130, 204, 220))
        draw.polygon([(fx + 4, fy - 3), (fx + 2, fy - 5), (fx + 1, fy - 2)],
                     fill=(62, 130, 204, 220))

    return overlay, mask


def build(root: Path, review_path: Path) -> None:
    frame_dir = root / "frames"
    mask_dir = root / "masks"
    frame_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    angles = {logical.lower(): angle for logical, _, angle in DIRECTIONS}
    entries = []

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
        "contract": "CH_ACTOR_COSTUME_V1",
        "actor": "ch_actor_green_01",
        "costume": "clown_01",
        "frame": {"width": FRAME[0], "height": FRAME[1], "groundAnchor": list(ANCHOR)},
        "maskChannels": {"R": "primary_costume", "G": "secondary_costume", "B": "wig", "A": "overlay_alpha"},
        "fixedArt": ["white_face_makeup", "red_nose", "red_mouth", "blue_eye_makeup"],
        "frames": entries,
        "notes": [
            "Overlay names match the approved CH Actor frame names one-for-one.",
            "The approved body/walk PNGs are never rewritten.",
            "Tint shading is derived from overlay luminance at runtime."
        ]
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    review_path.parent.mkdir(parents=True, exist_ok=True)
    board = Image.new("RGBA", (4 * 144, 3 * 192), (42, 65, 56, 255))
    for col, key in enumerate("senw"):
        for row, filename in enumerate((f"{key}_idle.png", f"{key}_walk_02.png", f"{key}_walk_06.png")):
            image = Image.open(frame_dir / filename).convert("RGBA").resize((144, 192), Image.Resampling.NEAREST)
            board.alpha_composite(image, (col * 144, row * 192))
    board.save(review_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()
    build(args.root, args.review)
    print(f"Wrote clown costume to {args.root}")


if __name__ == "__main__":
    main()
