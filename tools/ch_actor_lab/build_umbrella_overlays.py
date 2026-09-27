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
    overlay = Image.new("RGBA", (48, 64))
    mask = Image.new("RGBA", (48, 64))
    paint = ImageDraw.Draw(overlay)
    shade_mask = ImageDraw.Draw(mask)

    # A narrow angled shaft joins the canopy to the selected hand. The hand
    # pixels punch through its last two pixels to make the grip read naturally.
    shaft_top = (centre, 13)
    shaft_bottom = (hand_x, hand_y + 2)
    paint.line((shaft_top, shaft_bottom), fill=(20, 34, 42, 255), width=2)
    paint.line(((centre - 1, 15), (hand_x - 1, hand_y - 2)), fill=(103, 123, 131, 255), width=1)
    paint.arc((hand_x - 1, hand_y, hand_x + 3, hand_y + 5), 0, 170, fill=(24, 41, 49, 255), width=1)

    # Raised dome with five fabric gores and a scalloped rim. The umbrella
    # clears more of the approved hair than the first flat, three-panel study.
    canopy = [(centre, 0), (centre + 5, 1), (centre + 11, 4), (centre + 15, 7),
              (centre + 17, 11), (centre + 16, 13), (centre + 12, 11),
              (centre + 9, 14), (centre + 5, 12), (centre, 15),
              (centre - 5, 12), (centre - 9, 14), (centre - 12, 11),
              (centre - 16, 13), (centre - 17, 11), (centre - 15, 7),
              (centre - 11, 4), (centre - 5, 1)]
    paint.polygon(canopy, fill=(19, 40, 48, 255))
    # Each colorable gore has its own light value. Mask B stores that value so
    # the weather palette preserves the dome instead of flattening it.
    sections = [
        ([(centre - 1, 2), (centre - 6, 3), (centre - 11, 5), (centre - 14, 8),
          (centre - 15, 11), (centre - 12, 10), (centre - 9, 12), (centre - 8, 8)], 162),
        ([(centre, 2), (centre - 5, 3), (centre - 8, 8), (centre - 9, 12),
          (centre - 5, 10), (centre - 3, 12)], 204),
        ([(centre, 2), (centre - 3, 4), (centre - 4, 10), (centre, 13),
          (centre + 4, 10), (centre + 3, 4)], 240),
        ([(centre, 2), (centre + 5, 3), (centre + 8, 8), (centre + 9, 12),
          (centre + 5, 10), (centre + 3, 12)], 195),
        ([(centre + 1, 2), (centre + 6, 3), (centre + 11, 5), (centre + 14, 8),
          (centre + 15, 11), (centre + 12, 10), (centre + 9, 12), (centre + 8, 8)], 153),
    ]
    for polygon, shade in sections:
        rgb = tuple((component * shade + 127) // 255 for component in DEFAULT_FABRIC)
        paint.polygon(polygon, fill=(*rgb, 255))
        shade_mask.polygon(polygon, fill=(255, 0, shade, 255))
    # A fine pale piping and a small metal ferrule add readable material
    # details at 1x without putting high-frequency noise on the canopy.
    piping = [(centre - 13, 10), (centre - 9, 12), (centre - 5, 10),
              (centre, 13), (centre + 5, 10), (centre + 9, 12), (centre + 13, 10)]
    paint.line(piping, fill=(146, 185, 190, 255), width=1)
    shade_mask.line(piping, fill=(0, 0, 0, 0), width=1)
    paint.line(((centre - 2, 4), (centre - 4, 8)), fill=(210, 229, 224, 255), width=1)
    shade_mask.line(((centre - 2, 4), (centre - 4, 8)), fill=(0, 0, 0, 0), width=1)
    paint.line(((centre, 0), (centre, 2)), fill=(167, 184, 181, 255), width=1)
    shade_mask.line(((centre, 0), (centre, 2)), fill=(0, 0, 0, 0), width=1)

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
    """Visual simulation using a clean MapForge crop, never an SDL capture."""
    source = Image.open(capture).convert("RGBA")
    # MapForge's raw 1280x853 screenshot contains no pedestrian. The older
    # 760x760 actor board already contains a retired standing character.
    if source.width >= 640 and source.height >= 690:
        background = source.crop((260, 310, 640, 690))
    elif source.size == (380, 380):
        background = source
    else:
        raise ValueError(f"Expected a clean MapForge capture or 380x380 crop: {capture}")
    background.save(review.parent / "map_background.png")
    colors = {"s": (208, 79, 77), "e": (225, 181, 66),
              "w": (119, 102, 172), "n": (69, 151, 183)}
    positions = [("s", 222, 232), ("e", 602, 232),
                 ("w", 222, 612), ("n", 602, 612)]
    sequence = []
    for index in range(8):
        canvas = Image.new("RGBA", (760, 760))
        for col in range(2):
            for row in range(2):
                canvas.alpha_composite(background, (col * 380, row * 380))
        canvas = Image.alpha_composite(canvas, Image.new("RGBA", canvas.size, (25, 37, 57, 48)))
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
    parser.add_argument("--map-capture", type=Path, help="Raw pedestrian-free MapForge capture or clean 380x380 crop")
    args = parser.parse_args()
    build(args.frames, args.output, args.review)
    if args.map_capture:
        build_map_review(args.frames, args.output, args.map_capture, args.review)


if __name__ == "__main__":
    main()
