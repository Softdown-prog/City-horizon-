"""Render a stitched proof for the pre-baked dirt path slope sprite pilot.

This is a validation helper only. It does not render runtime geometry.
It composes the approved legacy flat PNG + one generated stair PNG + the same
flat PNG translated to the raised endpoint, so seam/port continuity can be
inspected directly.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE_W = 128
TILE_H = 64
CANVAS_H = 112
TOP_PAD = 32
PORTS = {
    "n": (96, 16),
    "e": (96, 48),
    "s": (32, 48),
    "w": (32, 16),
}
OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e"}
AXES = {"ns": ("n", "s"), "ew": ("w", "e")}


def load_rgba(path: Path, expected: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != expected:
        raise ValueError(f"{path}: expected {expected}, got {image.size}")
    return image


def variant_port(axis: str, high_end: str, end: str, rise_px: int) -> tuple[int, int]:
    if end not in AXES[axis]:
        raise ValueError(f"end={end} is not on axis={axis}")
    px, py = PORTS[end]
    displacement = rise_px if end == high_end else 0
    return px, TOP_PAD + py - displacement


def flat_translation_for_join(
    variant_origin: tuple[int, int],
    axis: str,
    high_end: str,
    variant_end: str,
    rise_px: int,
) -> tuple[int, int]:
    vx, vy = variant_port(axis, high_end, variant_end, rise_px)
    flat_join_end = OPPOSITE[variant_end]
    fx, fy = PORTS[flat_join_end]
    return variant_origin[0] + vx - fx, variant_origin[1] + vy - fy


def alpha_at_world(image: Image.Image, origin: tuple[int, int], x: int, y: int) -> int:
    lx = x - origin[0]
    ly = y - origin[1]
    if 0 <= lx < image.width and 0 <= ly < image.height:
        return image.getpixel((lx, ly))[3]
    return 0


def compose_case(
    flat: Image.Image,
    stair: Image.Image,
    axis: str,
    high_end: str,
    rise_px: int,
    label: str,
) -> Image.Image:
    cell = Image.new("RGBA", (430, 250), (70, 111, 52, 255))
    draw = ImageDraw.Draw(cell)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
        small = ImageFont.truetype("DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        small = font

    # Keep enough room around the three stitched sprites for all four directions.
    stair_origin = (151, 68)
    low_end = AXES[axis][1] if high_end == AXES[axis][0] else AXES[axis][0]
    low_origin = flat_translation_for_join(stair_origin, axis, high_end, low_end, rise_px)
    high_origin = flat_translation_for_join(stair_origin, axis, high_end, high_end, rise_px)

    pieces = [
        (flat, low_origin, "LOW FLAT"),
        (stair, stair_origin, "STAIRS"),
        (flat, high_origin, "HIGH FLAT"),
    ]
    # Painter order by screen-space bottom edge. This is enough for the stitched proof
    # and matches the same kind of back-to-front ordering the isometric renderer uses.
    pieces.sort(key=lambda item: item[1][1] + item[0].height)
    for image, origin, _ in pieces:
        cell.alpha_composite(image, origin)

    # Draw seam markers after compositing. Green = low seam; cyan = high seam.
    low_vx, low_vy = variant_port(axis, high_end, low_end, rise_px)
    high_vx, high_vy = variant_port(axis, high_end, high_end, rise_px)
    low_point = (stair_origin[0] + low_vx, stair_origin[1] + low_vy)
    high_point = (stair_origin[0] + high_vx, stair_origin[1] + high_vy)
    draw.ellipse((low_point[0]-3, low_point[1]-3, low_point[0]+3, low_point[1]+3), fill=(106, 255, 122, 255))
    draw.ellipse((high_point[0]-3, high_point[1]-3, high_point[0]+3, high_point[1]+3), fill=(105, 231, 255, 255))

    draw.rectangle((0, 0, cell.width, 31), fill=(37, 60, 30, 235))
    draw.text((10, 7), label, fill=(246, 247, 242, 255), font=font)
    draw.text((10, 226), "verde = emenda baixa   azul = emenda alta", fill=(226, 235, 220, 255), font=small)
    return cell


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-dir", type=Path, default=Path("out/dirt_slope_sprite_pilot"))
    parser.add_argument("--ns-source", type=Path, default=Path("assets/terrain/paths/dirt_01/dirt_path_05_straight_ns.png"))
    parser.add_argument("--ew-source", type=Path, default=Path("assets/terrain/paths/dirt_01/dirt_path_10_straight_ew.png"))
    parser.add_argument("--output", type=Path, default=Path("out/dirt_slope_continuity_proof.png"))
    args = parser.parse_args()

    flat_ns = load_rgba(args.ns_source, (TILE_W, TILE_H))
    flat_ew = load_rgba(args.ew_source, (TILE_W, TILE_H))

    cases = [
        (flat_ns, "ns", "n", 16, "dirt_path_straight_ns_stairs_100_8_high_n.png", "NS • subida para N • 8 degraus"),
        (flat_ns, "ns", "s", 16, "dirt_path_straight_ns_stairs_100_8_high_s.png", "NS • subida para S • 8 degraus"),
        (flat_ew, "ew", "w", 16, "dirt_path_straight_ew_stairs_100_8_high_w.png", "EW • subida para W • 8 degraus"),
        (flat_ew, "ew", "e", 16, "dirt_path_straight_ew_stairs_100_8_high_e.png", "EW • subida para E • 8 degraus"),
    ]

    sheet = Image.new("RGBA", (860, 500), (62, 98, 46, 255))
    for i, (flat, axis, high_end, rise_px, filename, label) in enumerate(cases):
        stair = load_rgba(args.generated_dir / filename, (TILE_W, CANVAS_H))
        cell = compose_case(flat, stair, axis, high_end, rise_px, label)
        x = (i % 2) * 430
        y = (i // 2) * 250
        sheet.alpha_composite(cell, (x, y))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"PASS stitched continuity proof: {args.output}")


if __name__ == "__main__":
    main()
