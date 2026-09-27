"""Export approved-size review sprites from genuine transparent 2D masters.

This deliberately rejects JPEG/screenshots and does no background extraction.
The source artwork must have its own alpha channel before it enters this step.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


DEFAULT_DIR = Path(__file__).resolve().parent / "art/concepts/nature_2d_generated_v2"


def export_sprite(source: Path, canvas: tuple[int, int], maximum: tuple[int, int],
                  ground_y: int) -> Image.Image:
    with Image.open(source) as input_image:
        if input_image.format != "PNG" or input_image.mode != "RGBA":
            raise ValueError(f"Expected a genuine RGBA PNG master: {source}")
        image = input_image.copy()

    alpha = image.getchannel("A")
    if alpha.getpixel((0, 0)) != 0 or alpha.getpixel((image.width - 1, 0)) != 0:
        raise ValueError(f"Master has no clear transparent margin: {source}")
    meaningful = alpha.point(lambda value: 255 if value > 25 else 0).getbbox()
    if not meaningful:
        raise ValueError(f"Master has no visible content: {source}")
    l, t, r, b = meaningful
    image = image.crop((max(0, l - 3), max(0, t - 3),
                        min(image.width, r + 3), min(image.height, b + 3)))
    image.thumbnail(maximum, Image.Resampling.LANCZOS)
    result = Image.new("RGBA", canvas)
    result.alpha_composite(image, ((canvas[0] - image.width) // 2, ground_y - image.height))
    return result


def draw_tile(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    points = [(x, y - 32), (x + 64, y), (x, y + 32), (x - 64, y)]
    draw.polygon(points, fill="#567f40")
    draw.line(points + [points[0]], fill="#b4cb82", width=1)


def review(pine: Image.Image, flower: Image.Image) -> Image.Image:
    sheet = Image.new("RGB", (1024, 800), "#4b7136")
    draw = ImageDraw.Draw(sheet)
    draw_tile(draw, 163, 369)
    draw_tile(draw, 165, 670)
    draw_tile(draw, 740, 670)
    sheet.paste(pine, (35, 13), pine)
    sheet.paste(flower, (37, 519), flower)
    pine_detail = pine.crop((25, 25, 232, 232)).resize((414, 414), Image.Resampling.NEAREST)
    sheet.paste(pine_detail, (550, 15), pine_detail)
    flower_detail = flower.resize((512, 320), Image.Resampling.NEAREST)
    sheet.paste(flower_detail, (484, 470), flower_detail)
    draw.text((22, 0), "PINE / 1x", fill="#edf0d2")
    draw.text((550, 0), "PINE / 2x crown detail", fill="#edf0d2")
    draw.text((22, 490), "FLOWER BED / 1x", fill="#edf0d2")
    draw.text((484, 450), "FLOWER BED / 2x", fill="#edf0d2")
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    sources = args.directory / "sources"
    pine = export_sprite(sources / "pine_master_rgba.png", (256, 368), (220, 330), 357)
    flower = export_sprite(sources / "flower_bed_master_rgba.png", (256, 160),
                           (226, 143), 151)
    pine.save(args.directory / "pine_2d_candidate.png")
    flower.save(args.directory / "flower_bed_2d_candidate.png")
    review(pine, flower).save(args.directory / "nature_2d_review.png")


if __name__ == "__main__":
    main()
