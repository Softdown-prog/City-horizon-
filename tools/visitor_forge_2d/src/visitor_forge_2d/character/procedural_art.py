from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

STYLE_CONTRACT = "CH_VISITOR_FORGE_2D_TYCOON_V1"
CHARACTER_ID = "visitor_male_01"
DIRECTION = "south"

MaskPainter = Callable[[ImageDraw.ImageDraw], None]
DetailPainter = Callable[[ImageDraw.ImageDraw], None]


def _painted_part(
    size: tuple[int, int],
    paint_mask: MaskPainter,
    *,
    paint_details: DetailPainter | None = None,
    edge_blur: float = 0.35,
    top_value: int = 248,
    bottom_value: int = 184,
    right_shade: int = 22,
) -> Image.Image:
    """Create a neutral grayscale RGBA part intended for palette tinting.

    The source art is deliberately neutral. The compositor multiplies it by the
    character palette later, so one painted silhouette/shading pass can be
    reused with different skin, hair and clothing colors.
    """
    width, height = size
    mask = Image.new("L", size, 0)
    draw_mask = ImageDraw.Draw(mask)
    paint_mask(draw_mask)
    if edge_blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(edge_blur))

    # Broad top-left light and bottom-right shade. It intentionally avoids
    # micro-detail so the volume survives the 512 -> 128 gameplay downscale.
    vertical = Image.new("L", size)
    vdraw = ImageDraw.Draw(vertical)
    for y in range(height):
        t = y / max(1, height - 1)
        value = round(top_value * (1.0 - t) + bottom_value * t)
        vdraw.line((0, y, width, y), fill=value)

    horizontal = Image.new("L", size)
    hdraw = ImageDraw.Draw(horizontal)
    for x in range(width):
        t = x / max(1, width - 1)
        value = 255 - round(right_shade * t)
        hdraw.line((x, 0, x, height), fill=value)

    tone = ImageChops.multiply(vertical, horizontal)

    highlight = Image.new("L", size, 0)
    hldraw = ImageDraw.Draw(highlight)
    hldraw.ellipse(
        (
            -round(width * 0.05),
            -round(height * 0.03),
            round(width * 0.58),
            round(height * 0.52),
        ),
        fill=34,
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(max(2.0, min(size) * 0.08)))
    tone = ImageChops.add(tone, highlight, scale=1.0, offset=0)

    rgba = Image.merge("RGBA", (tone, tone, tone, mask))
    if paint_details is not None:
        details = Image.new("RGBA", size, (0, 0, 0, 0))
        paint_details(ImageDraw.Draw(details))
        rgba = Image.alpha_composite(rgba, details)
    return rgba


def _head() -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((11, 5, 82, 84), fill=255)
        draw.rounded_rectangle((18, 39, 78, 88), radius=25, fill=255)
        # SOUTH uses a mild 3/4 presentation rather than a passport-photo front.
        draw.ellipse((75, 38, 89, 58), fill=235)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((55, 39, 60, 44), fill=(72, 72, 72, 205))
        draw.ellipse((37, 40, 41, 44), fill=(102, 102, 102, 145))
        draw.line((57, 47, 61, 55), fill=(135, 135, 135, 175), width=2)
        draw.line((47, 65, 58, 65), fill=(122, 122, 122, 155), width=2)
        draw.ellipse((26, 34, 46, 55), fill=(255, 255, 255, 20))

    return _painted_part((96, 96), mask, paint_details=details, edge_blur=0.45)


def _hair() -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.pieslice((9, 0, 87, 79), 180, 360, fill=255)
        draw.polygon(
            [
                (11, 37),
                (14, 20),
                (27, 7),
                (46, 2),
                (66, 6),
                (82, 17),
                (87, 31),
                (85, 46),
                (73, 38),
                (63, 31),
                (52, 29),
                (42, 31),
                (30, 29),
                (18, 39),
            ],
            fill=255,
        )
        draw.polygon([(73, 31), (84, 38), (83, 57), (74, 52)], fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.arc((22, 6, 76, 46), 195, 330, fill=(255, 255, 255, 28), width=4)
        draw.line((48, 6, 43, 25), fill=(88, 88, 88, 90), width=2)

    return _painted_part(
        (96, 96),
        mask,
        paint_details=details,
        edge_blur=0.35,
        top_value=238,
        bottom_value=166,
        right_shade=26,
    )


def _torso() -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon(
            [
                (30, 18),
                (50, 8),
                (78, 9),
                (103, 23),
                (110, 48),
                (103, 112),
                (89, 128),
                (43, 128),
                (25, 113),
                (19, 50),
            ],
            fill=255,
        )
        draw.ellipse((19, 15, 58, 54), fill=255)
        draw.ellipse((73, 14, 113, 55), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon(
            [(50, 12), (64, 26), (79, 12), (71, 8), (64, 17), (57, 8)],
            fill=(118, 118, 118, 98),
        )
        draw.line((64, 27, 64, 105), fill=(126, 126, 126, 44), width=2)
        draw.line((34, 111, 96, 111), fill=(92, 92, 92, 62), width=3)
        draw.line((31, 55, 98, 55), fill=(255, 255, 255, 18), width=3)

    return _painted_part((128, 132), mask, paint_details=details, edge_blur=0.4)


def _tapered_limb(
    size: tuple[int, int],
    top_width: int,
    bottom_width: int,
    *,
    side: str,
    cuff: bool = False,
) -> Image.Image:
    width, height = size
    center = width // 2

    def mask(draw: ImageDraw.ImageDraw) -> None:
        points = [
            (center - top_width // 2, 2),
            (center + top_width // 2, 2),
            (center + bottom_width // 2, height - 7),
            (center + bottom_width // 2 - 2, height - 2),
            (center - bottom_width // 2 + 2, height - 2),
            (center - bottom_width // 2, height - 7),
        ]
        draw.polygon(points, fill=255)
        draw.ellipse(
            (center - top_width // 2, 0, center + top_width // 2, top_width),
            fill=255,
        )
        draw.ellipse(
            (
                center - bottom_width // 2,
                height - bottom_width - 2,
                center + bottom_width // 2,
                height - 2,
            ),
            fill=255,
        )

    def details(draw: ImageDraw.ImageDraw) -> None:
        x = center + (top_width // 4 if side == "right" else -top_width // 4)
        draw.line((x, 8, x, height - 10), fill=(255, 255, 255, 20), width=2)
        if cuff:
            draw.line(
                (
                    center - bottom_width // 2 + 2,
                    height - 12,
                    center + bottom_width // 2 - 2,
                    height - 12,
                ),
                fill=(88, 88, 88, 82),
                width=3,
            )

    return _painted_part(size, mask, paint_details=details, edge_blur=0.35)


def _hand(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((7, 3, 26, 28), fill=255)
        if side == "left":
            draw.ellipse((4, 13, 13, 24), fill=240)
        else:
            draw.ellipse((20, 13, 29, 24), fill=240)

    return _painted_part((32, 34), mask, edge_blur=0.4)


def _lower_leg(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon([(12, 2), (44, 2), (42, 67), (38, 72), (18, 72), (14, 67)], fill=255)
        draw.ellipse((12, 0, 44, 31), fill=255)
        draw.ellipse((14, 55, 42, 73), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        x = 18 if side == "left" else 37
        draw.line((x, 12, x, 61), fill=(255, 255, 255, 18), width=2)
        draw.arc((12, 0, 44, 28), 10, 170, fill=(96, 96, 96, 52), width=2)

    return _painted_part((56, 74), mask, paint_details=details, edge_blur=0.35)


def _shoe(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        if side == "left":
            draw.rounded_rectangle((8, 7, 50, 28), radius=8, fill=255)
            draw.ellipse((2, 9, 24, 30), fill=255)
        else:
            draw.rounded_rectangle((10, 7, 52, 28), radius=8, fill=255)
            draw.ellipse((36, 9, 59, 30), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.line((6, 26, 54, 26), fill=(68, 68, 68, 96), width=3)
        if side == "left":
            draw.line((16, 12, 35, 14), fill=(255, 255, 255, 24), width=2)
        else:
            draw.line((25, 14, 44, 12), fill=(255, 255, 255, 24), width=2)

    return _painted_part(
        (60, 34),
        mask,
        paint_details=details,
        edge_blur=0.35,
        top_value=235,
        bottom_value=154,
    )


def _ground_shadow() -> Image.Image:
    mask = Image.new("L", (96, 32), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((8, 8, 88, 26), fill=118)
    mask = mask.filter(ImageFilter.GaussianBlur(5))
    image = Image.new("RGBA", (96, 32), (28, 31, 34, 0))
    image.putalpha(mask)
    return image


def build_v1_south_parts() -> dict[str, Image.Image]:
    """Return the deterministic first SOUTH visual library in neutral RGBA."""
    parts: dict[str, Image.Image] = {
        "ground_shadow": _ground_shadow(),
        "head": _head(),
        "hair": _hair(),
        "torso": _torso(),
    }
    for side in ("left", "right"):
        parts[f"upper_arm_{side}"] = _tapered_limb((48, 72), 30, 24, side=side, cuff=True)
        parts[f"lower_arm_{side}"] = _tapered_limb((44, 62), 24, 18, side=side)
        parts[f"hand_{side}"] = _hand(side)
        parts[f"upper_leg_{side}"] = _tapered_limb((56, 80), 34, 28, side=side)
        parts[f"lower_leg_{side}"] = _lower_leg(side)
        parts[f"shoe_{side}"] = _shoe(side)
    return parts


def generate_v1_south_assets(asset_root: str | Path) -> list[Path]:
    """Write the deterministic V1 source parts used by the layer compositor."""
    destination = Path(asset_root) / CHARACTER_ID / DIRECTION
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for part_id, image in build_v1_south_parts().items():
        path = destination / f"{part_id}.png"
        image.convert("RGBA").save(path, format="PNG", optimize=False)
        written.append(path)
    return written
