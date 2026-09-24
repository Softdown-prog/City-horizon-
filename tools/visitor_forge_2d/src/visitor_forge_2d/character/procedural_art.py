from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# V3 keeps the mass gained in V2, but redistributes it into a more organic game
# silhouette: sloped shoulders, a visible short neck, a tapered waist, softer
# limb transitions and feet that agree on the SOUTH 3/4 facing direction.
STYLE_CONTRACT = "CH_VISITOR_FORGE_2D_TYCOON_SHAPE_V3"
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
    """Create a neutral grayscale RGBA part intended for palette tinting."""
    width, height = size
    mask = Image.new("L", size, 0)
    draw_mask = ImageDraw.Draw(mask)
    paint_mask(draw_mask)
    if edge_blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(edge_blur))

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
    """Slightly smaller face mass with a built-in short neck."""

    def mask(draw: ImageDraw.ImageDraw) -> None:
        # Keep the readable stylized head but remove the V2 balloon effect.
        draw.ellipse((13, 7, 89, 87), fill=255)
        draw.rounded_rectangle((20, 39, 84, 94), radius=27, fill=255)
        # Near-side ear and cheek support the screen-right SOUTH 3/4 turn.
        draw.ellipse((80, 40, 96, 62), fill=236)
        draw.ellipse((78, 51, 92, 69), fill=216)
        # A real neck bridge prevents the head from floating on the collar.
        draw.rounded_rectangle((45, 80, 66, 103), radius=8, fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        # Far eye is smaller/lighter; near eye and nose carry the facing read.
        draw.ellipse((42, 42, 46, 46), fill=(106, 106, 106, 132))
        draw.ellipse((62, 40, 68, 46), fill=(70, 70, 70, 202))
        draw.line((68, 48, 74, 58), fill=(128, 128, 128, 176), width=3)
        draw.line((55, 70, 67, 70), fill=(118, 118, 118, 144), width=2)
        draw.ellipse((28, 34, 49, 55), fill=(255, 255, 255, 18))
        draw.arc((51, 49, 86, 89), 300, 78, fill=(90, 90, 90, 56), width=3)
        # Neck-side shade makes the collar connection readable at 128 px.
        draw.line((63, 83, 64, 100), fill=(90, 90, 90, 44), width=3)

    return _painted_part((104, 104), mask, paint_details=details, edge_blur=0.45)


def _hair() -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.pieslice((11, 2, 94, 81), 180, 360, fill=255)
        draw.polygon(
            [
                (13, 40),
                (16, 22),
                (30, 9),
                (50, 3),
                (71, 7),
                (88, 19),
                (94, 34),
                (92, 49),
                (80, 42),
                (69, 34),
                (57, 31),
                (46, 34),
                (32, 32),
                (20, 42),
            ],
            fill=255,
        )
        draw.polygon([(79, 34), (92, 41), (91, 59), (81, 55)], fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.arc((24, 8, 81, 49), 195, 330, fill=(255, 255, 255, 27), width=4)
        draw.line((52, 8, 47, 27), fill=(88, 88, 88, 86), width=2)
        draw.line((73, 13, 81, 32), fill=(76, 76, 76, 58), width=3)

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
    """Organic shirt silhouette: broad chest, sloped shoulders, tapered waist."""

    def mask(draw: ImageDraw.ImageDraw) -> None:
        # Chest stays substantial, but the sides now narrow through the waist
        # before opening slightly at the hem. This avoids the V2 rectangle.
        draw.polygon(
            [
                (29, 26),
                (50, 11),
                (82, 9),
                (113, 27),
                (122, 49),
                (117, 76),
                (109, 108),
                (99, 134),
                (45, 134),
                (33, 116),
                (25, 83),
                (18, 51),
            ],
            fill=255,
        )
        # Soft shoulder caps bridge into the articulated arms.
        draw.ellipse((17, 17, 61, 58), fill=255)
        draw.ellipse((78, 15, 128, 61), fill=255)
        # Rounded hem keeps the lower torso from ending in a hard box.
        draw.rounded_rectangle((34, 108, 108, 138), radius=15, fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        # Collar opens around the visible neck instead of touching the chin.
        draw.polygon(
            [(51, 13), (68, 30), (85, 12), (77, 8), (68, 20), (59, 8)],
            fill=(112, 112, 112, 102),
        )
        draw.line((70, 31, 71, 110), fill=(118, 118, 118, 42), width=3)
        draw.line((39, 119, 103, 119), fill=(88, 88, 88, 56), width=3)
        draw.line((31, 58, 106, 58), fill=(255, 255, 255, 16), width=3)
        # Near-side seam/shade strengthens the 3/4 turn without texture noise.
        draw.line((110, 37, 106, 108), fill=(74, 74, 74, 50), width=4)
        draw.arc((20, 15, 64, 62), 210, 320, fill=(255, 255, 255, 16), width=3)

    return _painted_part((144, 144), mask, paint_details=details, edge_blur=0.45)


def _tapered_limb(
    size: tuple[int, int],
    top_width: int,
    bottom_width: int,
    *,
    side: str,
    cuff: bool = False,
    curve: int = 0,
) -> Image.Image:
    """Paint a softly curved articulated segment instead of a straight tube."""
    width, height = size
    top_center = width // 2
    bottom_center = top_center + curve

    side_bonus = 2 if side == "right" else 0
    top_width += side_bonus
    bottom_width += side_bonus

    def mask(draw: ImageDraw.ImageDraw) -> None:
        mid_y = height // 2
        mid_center = round((top_center + bottom_center) / 2)
        mid_width = round((top_width + bottom_width) / 2)
        draw.polygon(
            [
                (top_center - top_width // 2, 3),
                (top_center + top_width // 2, 3),
                (mid_center + mid_width // 2, mid_y),
                (bottom_center + bottom_width // 2, height - 7),
                (bottom_center + bottom_width // 2 - 2, height - 2),
                (bottom_center - bottom_width // 2 + 2, height - 2),
                (bottom_center - bottom_width // 2, height - 7),
                (mid_center - mid_width // 2, mid_y),
            ],
            fill=255,
        )
        draw.ellipse(
            (top_center - top_width // 2, 0, top_center + top_width // 2, top_width),
            fill=255,
        )
        draw.ellipse(
            (
                bottom_center - bottom_width // 2,
                height - bottom_width - 2,
                bottom_center + bottom_width // 2,
                height - 2,
            ),
            fill=255,
        )

    def details(draw: ImageDraw.ImageDraw) -> None:
        highlight_x = top_center + (top_width // 4 if side == "right" else -top_width // 4)
        draw.line((highlight_x, 9, bottom_center, height - 11), fill=(255, 255, 255, 18), width=2)
        if cuff:
            draw.line(
                (
                    bottom_center - bottom_width // 2 + 2,
                    height - 13,
                    bottom_center + bottom_width // 2 - 2,
                    height - 13,
                ),
                fill=(88, 88, 88, 72),
                width=3,
            )

    return _painted_part(size, mask, paint_details=details, edge_blur=0.4)


def _hand(side: str) -> Image.Image:
    def mask(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((8, 4, 30, 34), fill=255)
        if side == "left":
            draw.ellipse((4, 16, 15, 29), fill=236)
        else:
            draw.ellipse((24, 15, 36, 29), fill=238)

    def details(draw: ImageDraw.ImageDraw) -> None:
        if side == "right":
            draw.arc((12, 9, 32, 31), 280, 70, fill=(92, 92, 92, 38), width=2)
        else:
            draw.arc((7, 9, 28, 31), 110, 250, fill=(92, 92, 92, 30), width=2)

    return _painted_part((40, 40), mask, paint_details=details, edge_blur=0.4)


def _lower_leg(side: str) -> Image.Image:
    """Continuous calf shape without a circular knee marker."""
    near_bonus = 2 if side == "right" else 0

    def mask(draw: ImageDraw.ImageDraw) -> None:
        left = 12 - near_bonus
        right = 48 + near_bonus
        draw.rounded_rectangle((left, 1, right, 34), radius=15, fill=255)
        draw.polygon(
            [
                (left + 2, 20),
                (right - 1, 20),
                (right - 5, 67),
                (right - 10, 78),
                (left + 10, 78),
                (left + 5, 67),
            ],
            fill=255,
        )
        draw.ellipse((left + 5, 61, right - 5, 80), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        x = 20 if side == "left" else 40
        draw.line((x, 14, x, 66), fill=(255, 255, 255, 16), width=2)
        # Only a faint cloth fold remains where the knee bends.
        draw.line((19, 30, 43, 31), fill=(82, 82, 82, 24), width=2)
        draw.line((19, 66, 42, 66), fill=(78, 78, 78, 28), width=2)

    return _painted_part((60, 82), mask, paint_details=details, edge_blur=0.4)


def _shoe(side: str) -> Image.Image:
    """Both feet point toward screen-right, matching the SOUTH 3/4 body turn."""

    def mask(draw: ImageDraw.ImageDraw) -> None:
        if side == "left":
            # Far foot: slightly smaller but still points in the same direction.
            draw.rounded_rectangle((9, 8, 51, 30), radius=9, fill=255)
            draw.ellipse((38, 10, 63, 33), fill=255)
        else:
            # Near foot carries a little more silhouette weight.
            draw.rounded_rectangle((8, 7, 55, 31), radius=10, fill=255)
            draw.ellipse((41, 9, 67, 34), fill=255)

    def details(draw: ImageDraw.ImageDraw) -> None:
        draw.line((7, 30, 62, 30), fill=(68, 68, 68, 92), width=3)
        draw.line((21, 13, 47, 14), fill=(255, 255, 255, 22), width=2)

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
    draw.ellipse((8, 8, 104, 30), fill=112)
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
        arm_curve = -3 if side == "left" else 3
        forearm_curve = 2 if side == "left" else -2
        parts[f"upper_arm_{side}"] = _tapered_limb(
            (54, 78), 35, 28, side=side, cuff=True, curve=arm_curve
        )
        parts[f"lower_arm_{side}"] = _tapered_limb(
            (50, 68), 28, 21, side=side, curve=forearm_curve
        )
        parts[f"hand_{side}"] = _hand(side)
        parts[f"upper_leg_{side}"] = _tapered_limb(
            (62, 86), 38, 31, side=side, curve=(1 if side == "right" else -1)
        )
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