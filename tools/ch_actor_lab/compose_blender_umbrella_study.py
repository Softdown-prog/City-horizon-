"""Compose a CH Blender SOUTH canopy proxy with animated actor hand contacts.

Candidate output only: never writes to the runtime assets directory. The
Blender color and emission-mask passes must come from the same proxy job.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from build_umbrella_overlays import FRAME_DIR, hand_contact, is_hand_pixel

GAMEPLAY_COLOR = (69, 151, 183)


def fit_canopy(color: Image.Image, fabric: Image.Image) -> tuple[Image.Image, Image.Image]:
    if color.size != fabric.size or color.mode != "RGBA" or fabric.mode != "RGBA":
        raise ValueError("CH Blender color and fabric mask must be matching RGBA passes")
    bbox = color.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Empty Blender canopy proxy")
    source = color.crop(bbox)
    source_mask = fabric.crop(bbox)
    # Fit without stretching the dome. The canopy has a 35x20 pixel budget;
    # the framed actor remains 48x64 with the original (24, 60) anchor.
    factor = min(35 / source.width, 20 / source.height)
    width = max(1, round(source.width * factor))
    height = max(1, round(source.height * factor))
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    source_mask = source_mask.resize((width, height), Image.Resampling.LANCZOS)
    return source, source_mask


def grade_for_gameplay(canopy: Image.Image, fabric: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Keep Blender's dome lighting but recover contrast at 48x64.

    The emission pass selects fabric; the fixed binding and ferrule retain
    their rendered hue. No silhouette, ribs or volume are painted in 2D.
    """
    graded = canopy.copy()
    selection = Image.new("RGBA", canopy.size)
    for y in range(canopy.height):
        for x in range(canopy.width):
            r, g, b, a = canopy.getpixel((x, y))
            coverage = fabric.getpixel((x, y))[3]
            if a < 96 or coverage < max(128, a * 3 // 4):
                continue
            # Match the established umbrella palette while using the value
            # differences baked by the CH Blender studio for each gore.
            luminance = (54 * r + 183 * g + 19 * b) / 256
            shade = max(137, min(242, round(luminance / 157 * 207)))
            rgb = tuple((component * shade + 127) // 255 for component in GAMEPLAY_COLOR)
            graded.putpixel((x, y), (*rgb, a))
            selection.putpixel((x, y), (255, 0, shade, a))
    return graded, selection


def overlay_for_pose(actor: Image.Image, canopy: Image.Image, fabric: Image.Image,
                     direction: str) -> tuple[Image.Image, Image.Image]:
    overlay = Image.new("RGBA", (48, 64))
    mask = Image.new("RGBA", (48, 64))
    hand_x, hand_y = hand_contact(actor, direction)
    centre = 25 if direction in "sn" else 22
    top = (48 - canopy.width) // 2 + (centre - 24)
    # Lower shaft follows this pose's hand; the 3D canopy stays fixed above
    # the head and is never re-rendered at every walk phase.
    painter = ImageDraw.Draw(overlay)
    painter.line((centre, 11, hand_x, hand_y + 2), fill=(29, 42, 45, 255), width=2)
    painter.line((centre - 1, 13, hand_x - 1, hand_y - 2), fill=(108, 127, 127, 255))
    painter.arc((hand_x - 1, hand_y, hand_x + 3, hand_y + 5), 0, 170,
                fill=(29, 42, 45, 255))
    graded, selection = grade_for_gameplay(canopy, fabric)
    # A one-pixel dark rim is drawn behind the rendered canopy. It restores
    # its silhouette against streets and roofs without covering Blender ribs.
    silhouette = canopy.getchannel("A").point(lambda a: 255 if a >= 96 else 0)
    outside = Image.new("RGBA", canopy.size, (20, 43, 51, 0))
    outside.putalpha(silhouette.filter(ImageFilter.MaxFilter(3)))
    overlay.alpha_composite(outside, (top, 1))
    overlay.alpha_composite(graded, (top, 1))
    mask.paste(selection, (top, 1))
    for y in range(1, 1 + selection.height):
        for x in range(top, top + selection.width):
            if 0 <= x < 48 and mask.getpixel((x, y))[0] == 255:
                r, g, shade, _ = mask.getpixel((x, y))
                mask.putpixel((x, y), (r, g, shade, overlay.getpixel((x, y))[3]))

    for y in range(hand_y - 2, hand_y + 3):
        for x in range(hand_x - 2, hand_x + 3):
            if is_hand_pixel(actor.getpixel((x, y))):
                overlay.putpixel((x, y), (0, 0, 0, 0))
                mask.putpixel((x, y), (0, 0, 0, 0))
    return overlay, mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path("tools/ch_actor_lab/art/umbrella_blender_study"))
    args = parser.parse_args()
    color = Image.open(args.proxy_dir / "proxy_south.png").convert("RGBA")
    fabric = Image.open(args.proxy_dir / "fabric_mask_south.png").convert("RGBA")
    canopy, fabric = fit_canopy(color, fabric)
    (args.output / "frames").mkdir(parents=True, exist_ok=True)
    (args.output / "masks").mkdir(parents=True, exist_ok=True)
    board = Image.new("RGBA", (3 * 150, 2 * 200), (67, 91, 52, 255))
    draw = ImageDraw.Draw(board)
    for index, stem in enumerate(("s_idle", "s_walk_02", "s_walk_06")):
        actor = Image.open(FRAME_DIR / (stem + ".png")).convert("RGBA")
        overlay, mask = overlay_for_pose(actor, canopy, fabric, "s")
        overlay.save(args.output / "frames" / (stem + ".png"))
        mask.save(args.output / "masks" / (stem + ".png"))
        current = Image.open(Path("assets/characters/ch_actor_green_01/umbrella/frames")
                             / (stem + ".png")).convert("RGBA")
        for row, prop in enumerate((current, overlay)):
            composed = Image.alpha_composite(actor, prop).resize((144, 192), Image.Resampling.NEAREST)
            board.alpha_composite(composed, (index * 150, row * 200 + 8))
            draw.text((index * 150 + 2, row * 200 + 1),
                      f"{'atual' if row == 0 else 'CH Blender'} {stem}", fill="white")
    board.convert("RGB").save(args.output / "comparison.png")
    print(f"Candidate SOUTH overlays/masks and comparison: {args.output}")


if __name__ == "__main__":
    main()
