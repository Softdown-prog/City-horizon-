"""Bake 48x64 umbrella overlays and R/shade masks for the approved actor.

The hand contact is sampled from each *approved* RGBA pose. The actor PNGs
themselves are never rewritten. R=255 selects the umbrella fabric, B stores
the fabric shade, and A matches the colored overlay pixel's alpha.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw


FRAME_DIR = Path("assets/characters/ch_actor_green_01/frames")
OUT_DIR = Path("assets/characters/ch_actor_green_01/umbrella")
REVIEW = Path("tools/ch_actor_lab/art/umbrella_v1/review.png")
DEFAULT_FABRIC = (69, 151, 183)


def is_hand_pixel(rgba: tuple[int, int, int, int]) -> bool:
    r, g, b, a = rgba
    return a > 180 and r > 130 and r > g * 1.08 and g > b * 1.08


def hand_contact(frame: Image.Image, direction: str) -> tuple[int, int]:
    # Both arms have independent walk phases. Use the outward hand on the
    # right for S/N and left for E/W, so the handle never swaps hands mid-loop.
    right_hand = direction in "sn"
    points = [(x, y) for y in range(33, 47) for x in range(48)
              if (x >= 25 if right_hand else x <= 24)
              and is_hand_pixel(frame.getpixel((x, y)))]
    if not points:
        raise ValueError(f"Missing outward hand in {direction} pose")
    extreme = max(x for x, _ in points) if right_hand else min(x for x, _ in points)
    hand = [(x, y) for x, y in points if abs(x - extreme) <= 4]
    contact = round(median(x for x, _ in hand)), round(median(y for _, y in hand))
    if not (10 <= contact[0] <= 38 and 33 <= contact[1] <= 46):
        raise ValueError(f"Unexpected hand position: {direction} {contact}")
    return contact


def make_overlay(frame: Image.Image, direction: str) -> tuple[Image.Image, Image.Image, tuple[int, int]]:
    hand_x, hand_y = hand_contact(frame, direction)
    centre = 25 if direction in "sn" else 22
    canopy_y = 2
    overlay = Image.new("RGBA", (48, 64))
    mask = Image.new("RGBA", (48, 64))
    paint = ImageDraw.Draw(overlay)
    shade_mask = ImageDraw.Draw(mask)

    # A narrow angled shaft joins the canopy to the selected hand. The hand
    # pixels punch through its last two pixels to make the grip read naturally.
    shaft_top = (centre, 15)
    shaft_bottom = (hand_x, hand_y + 2)
    paint.line((shaft_top, shaft_bottom), fill=(20, 34, 42, 255), width=2)
    paint.line(((centre - 1, 16), (hand_x - 1, hand_y - 2)), fill=(103, 123, 131, 255), width=1)
    paint.arc((hand_x - 1, hand_y, hand_x + 3, hand_y + 5), 0, 170, fill=(24, 41, 49, 255), width=1)

    canopy = [(centre, canopy_y), (centre + 5, 3), (centre + 11, 5), (centre + 15, 8),
              (centre + 17, 12), (centre + 16, 14), (centre + 12, 13),
              (centre + 9, 16), (centre + 5, 14), (centre, 17),
              (centre - 5, 14), (centre - 9, 16), (centre - 12, 13),
              (centre - 16, 14), (centre - 17, 12), (centre - 15, 8),
              (centre - 11, 5), (centre - 5, 3)]
    paint.polygon(canopy, fill=(19, 40, 48, 255))
    # Colorable faceted panels leave a one-pixel dark rim and seams. Mask B
    # carries the same lighting for every randomly chosen fabric color.
    sections = [
        ([(centre, 4), (centre - 5, 4), (centre - 10, 6), (centre - 14, 9),
          (centre - 15, 12), (centre - 12, 11), (centre - 9, 14), (centre - 5, 12)], 190),
        ([(centre, 4), (centre - 4, 5), (centre - 5, 12), (centre, 15),
          (centre + 4, 12)], 238),
        ([(centre, 4), (centre + 5, 4), (centre + 10, 6), (centre + 14, 9),
          (centre + 15, 12), (centre + 12, 11), (centre + 9, 14),
          (centre + 5, 12), (centre, 15)], 172),
    ]
    for polygon, shade in sections:
        rgb = tuple((component * shade + 127) // 255 for component in DEFAULT_FABRIC)
        paint.polygon(polygon, fill=(*rgb, 255))
        shade_mask.polygon(polygon, fill=(255, 0, shade, 255))
    paint.point((centre, 2), fill=(175, 192, 198, 255))

    # Remove the shaft over the contact skin, but retain the colored canopy.
    for y in range(hand_y - 2, hand_y + 3):
        for x in range(hand_x - 2, hand_x + 3):
            if is_hand_pixel(frame.getpixel((x, y))):
                overlay.putpixel((x, y), (0, 0, 0, 0))
    return overlay, mask, (hand_x, hand_y)


def recolor(overlay: Image.Image, mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    result = overlay.copy()
    for y in range(result.height):
        for x in range(result.width):
            r, _, shade, a = mask.getpixel((x, y))
            if r == 255 and a == 255:
                result.putpixel((x, y), (*(component * shade // 255 for component in color), 255))
    return result


def build(frames: Path, output: Path, review: Path) -> None:
    paths = sorted(frames.glob("*.png"))
    if len(paths) != 36:
        raise ValueError(f"Expected 36 approved frames, found {len(paths)}")
    (output / "frames").mkdir(parents=True, exist_ok=True)
    (output / "masks").mkdir(parents=True, exist_ok=True)
    board = Image.new("RGB", (3 * 164, 4 * 218), (74, 109, 54))
    palette = [(208, 79, 77), (225, 181, 66), (69, 151, 183), (119, 102, 172)]
    draw = ImageDraw.Draw(board)
    for path in paths:
        direction = path.stem[0]
        frame = Image.open(path).convert("RGBA")
        if frame.size != (48, 64):
            raise ValueError(f"Unexpected size: {path}")
        overlay, mask, _ = make_overlay(frame, direction)
        assert overlay.getbbox() and mask.getchannel("R").getbbox()
        overlay.save(output / "frames" / path.name)
        mask.save(output / "masks" / path.name)
        if path.stem not in {f"{d}_{pose}" for d in "senw" for pose in ("idle", "walk_02", "walk_06")}:
            continue
        row = "senw".index(direction)
        col = {"idle": 0, "walk_02": 1, "walk_06": 2}[path.stem[2:]]
        combined = Image.alpha_composite(frame, recolor(overlay, mask, palette[row]))
        x, y = col * 164 + 10, row * 218 + 18
        # Place each pose at 3x. The source canvas remains at its exact 48x64.
        preview = combined.resize((144, 192), Image.Resampling.NEAREST)
        board.paste(preview, (x, y), preview)
        draw.text((x, y - 14), path.stem, fill=(246, 245, 224))
    review.parent.mkdir(parents=True, exist_ok=True)
    board.save(review)
    print(f"Wrote {len(paths)} overlays and masks to {output}; review: {review}")


def build_map_review(frames: Path, overlays: Path, capture: Path, review: Path) -> None:
    """Visual simulation at 1x on an existing map capture, never an SDL capture."""
    background = Image.open(capture).convert("RGBA")
    if background.size != (760, 760):
        raise ValueError(f"Expected 760x760 four-direction map capture: {capture}")
    colors = {"s": (208, 79, 77), "e": (225, 181, 66),
              "w": (119, 102, 172), "n": (69, 151, 183)}
    positions = [("s", 222, 232), ("e", 602, 232),
                 ("w", 222, 612), ("n", 602, 612)]
    sequence = []
    for index in range(8):
        canvas = Image.alpha_composite(background, Image.new("RGBA", background.size, (25, 37, 57, 48)))
        for direction, x, y in positions:
            name = f"{direction}_walk_{index:02}.png"
            actor = Image.open(frames / name).convert("RGBA")
            overlay = Image.open(overlays / "frames" / name).convert("RGBA")
            mask = Image.open(overlays / "masks" / name).convert("RGBA")
            canvas.alpha_composite(Image.alpha_composite(actor, recolor(overlay, mask, colors[direction])), (x, y))
        sequence.append(canvas.convert("RGB"))
    sequence[2].save(review.parent / "map_review.png")
    sequence[0].save(review.parent / "walk_review.gif", save_all=True,
                     append_images=sequence[1:], duration=150, loop=0, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, default=FRAME_DIR)
    parser.add_argument("--output", type=Path, default=OUT_DIR)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--map-capture", type=Path, help="Existing 760x760 map board for a visual simulation")
    args = parser.parse_args()
    build(args.frames, args.output, args.review)
    if args.map_capture:
        build_map_review(args.frames, args.output, args.map_capture, args.review)


if __name__ == "__main__":
    main()
