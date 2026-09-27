"""Build exact RGBA clothing masks for the approved CH Actor frames.

R marks the jacket, G the trousers, B stores the original light/shadow value,
and A copies the source alpha. The game replaces RGB only; silhouette and foot
anchor stay pixel-identical across all directions and walk phases.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


FRAME_DIR = Path("assets/characters/ch_actor_green_01/frames")
MASK_DIR = Path("assets/characters/ch_actor_green_01/masks")
PREVIEW_PATH = Path("tools/ch_actor_lab/art/color_masks_v1/review.png")


def clothing_channel(r: int, g: int, b: int, a: int, y: int) -> str | None:
    if a == 0:
        return None
    if 20 <= y <= 45 and g >= 54 and g * 100 >= b * 132 and g * 100 >= r * 125:
        return "jacket"
    if 36 <= y <= 59 and b >= 100 and b * 100 >= g * 155 and b * 100 >= r * 160:
        return "pants"
    return None


def build_mask(frame: Image.Image) -> Image.Image:
    mask = Image.new("RGBA", frame.size)
    for y in range(frame.height):
        for x in range(frame.width):
            r, g, b, a = frame.getpixel((x, y))
            channel = clothing_channel(r, g, b, a, y)
            if channel == "jacket":
                shade = min(255, max(48, round(g * 210 / 127)))
                mask.putpixel((x, y), (255, 0, shade, a))
            elif channel == "pants":
                shade = min(255, max(48, round(b * 210 / 200)))
                mask.putpixel((x, y), (0, 255, shade, a))
    return mask


def recolor(frame: Image.Image, mask: Image.Image, jacket: tuple[int, int, int],
            pants: tuple[int, int, int]) -> Image.Image:
    result = frame.copy()
    for y in range(frame.height):
        for x in range(frame.width):
            channel_r, channel_g, shade, _ = mask.getpixel((x, y))
            color = jacket if channel_r else pants if channel_g else None
            if color is not None:
                _, _, _, alpha = frame.getpixel((x, y))
                result.putpixel((x, y), (*(min(255, (component * shade + 127) // 255)
                                            for component in color), alpha))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, default=FRAME_DIR)
    parser.add_argument("--masks", type=Path, default=MASK_DIR)
    parser.add_argument("--preview", type=Path, default=PREVIEW_PATH)
    args = parser.parse_args()
    frames = sorted(args.frames.glob("*.png"))
    if len(frames) != 36:
        raise SystemExit(f"Expected 36 approved frames in {args.frames}, found {len(frames)}")
    args.masks.mkdir(parents=True, exist_ok=True)
    for path in frames:
        frame = Image.open(path).convert("RGBA")
        if frame.size != (48, 64):
            raise SystemExit(f"Unexpected frame dimensions: {path}")
        mask = build_mask(frame)
        if not mask.getchannel("R").getbbox() or not mask.getchannel("G").getbbox():
            raise SystemExit(f"Missing jacket or trousers in {path}")
        mask.save(args.masks / path.name)

    # This is a reproducible inspection board, not a game sprite.
    examples = [
        ("ORIGINAL", (21, 127, 61), (29, 76, 210)),
        ("BURGUNDY / DENIM", (178, 70, 91), (78, 102, 159)),
        ("OCHRE / SLATE", (181, 139, 65), (89, 102, 127)),
        ("TEAL / BROWN", (58, 150, 143), (121, 86, 65)),
    ]
    board = Image.new("RGB", (4 * 192, 4 * 300), (74, 109, 54))
    draw = ImageDraw.Draw(board)
    for col, (label, jacket, pants) in enumerate(examples):
        draw.text((col * 192 + 8, 10), label, fill=(247, 245, 219))
        for row, direction in enumerate("senw"):
            frame = Image.open(args.frames / f"{direction}_walk_03.png").convert("RGBA")
            mask = Image.open(args.masks / f"{direction}_walk_03.png").convert("RGBA")
            recolored = (frame if col == 0 else recolor(frame, mask, jacket, pants))
            recolored = recolored.resize((144, 192), Image.Resampling.NEAREST)
            board.paste(recolored, (col * 192 + 24, row * 300 + 46), recolored)
            draw.text((col * 192 + 8, row * 300 + 242), direction.upper(), fill=(247, 245, 219))
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    board.save(args.preview)
    print(f"Wrote {len(frames)} exact masks and {args.preview}")


if __name__ == "__main__":
    main()
