from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# V2 keeps the original procedural language, but adds a deliberate mass pass:
# broader torso/limbs, chunkier hands and shoes, a fuller head silhouette and a
# stronger near/far read for the SOUTH 3/4 view. The goal is game readability,
# not realistic anatomy.
STYLE_CONTRACT = "CH_VISITOR_FORGE_2D_TYCOON_MASS_V2"
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
    """Fuller stylized head with a stronger SOUTH 3/4 read."""

    def mask(draw: ImageDraw.ImageDraw) -> None:
        # Wider cranium and jaw than V1. The right-side ear/nose direction keeps
        # the character from reading as a perfectly frontal paper doll.
        draw.ellipse((10, 4, 91, 89), fill=255)
        draw.rounded_rectangle((17, 38, 86, 96), radius=29, fill=255)
        draw.ellipse((82, 39, 99, 62), fill=238)
        draw.ellipse((79, 50, 94, 70), fill=220)

    def details(draw: ImageDraw.ImageDraw) -> None:
        # Facial marks stay intentionally broad. They should suggest direction
        # at 128 px, not become a miniature portrait.
        draw.ellipse((60, 41, 66, 47), fill=(70, 70, 70, 205))
        draw.ellipse((40, 42, 45, 47), fill=(104, 104, 104, 142))
        draw.line((65, 49, 71, 59), fill=(132, 132, 132, 178), width=3)
        draw.line((52, 71, 65, 71), fill=(118, 118, 118, 150), width=2)
        draw.ellipse((25, 34, 50, 58), fill=(255, 255, 255, 20))
        # Small jaw-side tone supports the 3/4 turn after downscale.
        draw.arc((50, 48, 87, 91), 300, 80, fill=(92, 92, 92, 62), width=3)

    return _painted_part((104, 104), mask, paint_details=details, edge_blur=0.45)


def _hair() -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.pieslice((8, 0, 96, 84), 180, 360, fill=255)
        draw.polygon(
            [
                (10, 40),
                (13, 21),
                (28, 7),
                (49, 1),
                (72, 6),
                (90, 19),
                (96, 34),
                (94, 50),
                (81, 42),
                (70, 34),
                (57, 31),
                (45, 34),
                (31, 31),
                (18, 42),
            ],
            fill=255,
        )
        draw.polygon([(80, 33), (94, 40), (93, 62), (82, 57)], fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.arc((22, 6, 82, 50), 195, 330, fill=(255, 255, 255, 28), width=4)
        draw.line((52, 6, 46, 28), fill=(88, 88, 88, 90), width=2)
        draw.line((74, 12, 83, 32), fill=(76, 76, 76, 62), width=3)

    return _painted_part(
        (104, 104),
        mask,
        paint_details=details,
        edge_blur=0.35,
        top_value=238,
        bottom_value=166,
        right_shade=28,
    )


def _torso() -> Image.Image:
    """Broader, heavier shirt mass with asymmetric SOUTH 3/4 silhouette."""

    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon(
            [
                (27, 21),
                (52, 8),
                (83, 8),
                (118, 27),
                (124, 54),
                (116, 119),
                (99, 136),
                (43, 136),
                (22, 119),
                (16, 53),
            ],
            fill=255,
        )
        # Shoulder caps deliberately differ: the screen-right side is the near
        # side in this SOUTH 3/4 gate and carries slightly more visual weight.
        draw.ellipse((15, 16, 62, 60), fill=255)
        draw.ellipse((78, 15, 131, 64), fill=255)
        draw.rounded_rectangle((25, 95, 117, 139), radius=18, fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.polygon(
            [(51, 12), (68, 29), (86, 11), (77, 7), (68, 20), (59, 7)],
            fill=(112, 112, 112, 104),
        )
        # Center seam is shifted slightly toward the near side rather than dead
        # center, reinforcing that the torso is turned.
        draw.line((70, 30, 72, 112), fill=(118, 118, 118, 45), width=3)
        draw.line((34, 118, 105, 118), fill=(88, 88, 88, 62), width=4)
        draw.line((31, 58, 106, 58), fill=(255, 255, 255, 18), width=4)
        draw.line((111, 35, 108, 112), fill=(74, 74, 74, 54), width=4)
        draw.arc((20, 12, 66, 64), 210, 320, fill=(255, 255, 255, 16), width=3)

    return _painted_part((144, 144), mask, paint_details=details, edge_blur=0.4)


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

    # Near side receives a little more silhouette weight. This is intentionally
    # subtle because z-order does most of the 3/4 work.
    side_bonus = 2 if side == "right" else 0
    top_width += side_bonus
    bottom_width += side_bonus

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
        shade_x = center - top_width // 3 if side == "left" else center + top_width // 3
        draw.line((shade_x, 10, shade_x, height - 11), fill=(76, 76, 76, 30), width=2)
        if cuff:
            draw.line(
                (
                    center - bottom_width // 2 + 2,
                    height - 13,
                    center + bottom_width // 2 - 2,
                    height - 13,
                ),
                fill=(88, 88, 88, 82),
                width=3,
            )

    return _painted_part(size, mask, paint_details=details, edge_blur=0.35)


def _hand(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        # Hand is intentionally mitten-like: a readable game shape, not fingers.
        draw.ellipse((7, 3, 31, 34), fill=255)
        if side == "left":
            draw.ellipse((3, 15, 15, 29), fill=240)
        else:
            draw.ellipse((25, 15, 37, 29), fill=240)

    def details(draw: ImageDraw.ImageDraw) -> None:
        if side == "right":
            draw.arc((12, 8, 33, 31), 280, 70, fill=(92, 92, 92, 42), width=2)
        else:
            draw.arc((7, 8, 28, 31), 110, 250, fill=(92, 92, 92, 34), width=2)

    return _painted_part((40, 40), mask, paint_details=details, edge_blur=0.4)


def _lower_leg(side: str) -> Image.Image:
    width_bonus = 2 if side == "right" else 0

    def mask(draw: ImageDraw.ImageDraw) -> None:
        left = 10 - width_bonus
        right = 50 + width_bonus
        draw.polygon(
            [(left, 2), (right, 2), (right - 3, 72), (right - 8, 78), (left + 9, 78), (left + 4, 72)],
            fill=255,
        )
        draw.ellipse((left, 0, right, 36), fill=255)
        draw.ellipse((left + 3, 59, right - 3, 80), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        x = 18 if side == "left" else 43
        draw.line((x, 13, x, 68), fill=(255, 255, 255, 18), width=2)
        draw.arc((10, 0, 50, 34), 10, 170, fill=(96, 96, 96, 52), width=2)
        draw.line((17, 64, 45, 64), fill=(78, 78, 78, 34), width=2)

    return _painted_part((60, 82), mask, paint_details=details, edge_blur=0.35)


def _shoe(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        if side == "left":
            draw.rounded_rectangle((10, 7, 58, 31), radius=9, fill=255)
            draw.ellipse((2, 10, 29, 34), fill=255)
        else:
            draw.rounded_rectangle((9, 7, 57, 31), radius=9, fill=255)
            draw.ellipse((39, 10, 66, 34), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.line((6, 30, 61, 30), fill=(68, 68, 68, 96), width=3)
        if side == "left":
            draw.line((17, 13, 39, 15), fill=(255, 255, 255, 24), width=2)
        else:
            draw.line((28, 15, 50, 13), fill=(255, 255, 255, 24), width=2)

    return _painted_part(
        (68, 38),
        mask,
        paint_details=details,
        edge_blur=0.35,
        top_value=235,
        bottom_value=154,
    )


def _ground_shadow() -> Image.Image:
    mask = Image.new("L", (112, 36), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((8, 8, 104, 30), fill=118)
    mask = mask.filter(ImageFilter.GaussianBlur(5))
    image = Image.new("RGBA", (112, 36), (28, 31, 34, 0))
    image.putalpha(mask)
    return image


def build_v1_south_parts() -> dict[str, Image.Image]:
    """Return the deterministic SOUTH visual library in neutral RGBA."""
    parts: dict[str, Image.Image] = {
        "ground_shadow": _ground_shadow(),
        "head": _head(),
        "hair": _hair(),
        "torso": _torso(),
    }
    for side in ("left", "right"):
        parts[f"upper_arm_{side}"] = _tapered_limb((54, 78), 36, 29, side=side, cuff=True)
        parts[f"lower_arm_{side}"] = _tapered_limb((50, 68), 29, 22, side=side)
        parts[f"hand_{side}"] = _hand(side)
        parts[f"upper_leg_{side}"] = _tapered_limb((62, 86), 40, 34, side=side)
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
