"""Generate pre-rendered 2D dirt-path slope/stair sprites from approved path PNGs.

CH_PATH_SPRITE_PILOT_V1

This is deliberately an OFFLINE asset generator. Runtime code must not draw
free-form stair geometry from these recipes. The runtime will eventually select
one pre-rendered PNG by topology + discrete vertical profile.

The generator preserves the existing dirt-path artwork by deforming the
canonical straight path sprites themselves:
  - NS source: assets/terrain/paths/dirt_01/dirt_path_05_straight_ns.png
  - EW source: assets/terrain/paths/dirt_01/dirt_path_10_straight_ew.png

The flat path remains the existing 128x64 PNG. Slope sprites use a taller
transparent canvas so the raised endpoint can move upward without clipping.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE_W = 128
TILE_H = 64
CANVAS_H = 112
TOP_PAD = 32
HEIGHT_PX_PER_UNIT = 16.0

# Same screen-space connection ports used by generate_dirt_paths.py.
PORTS = {
    "n": (96.0, 16.0),
    "e": (96.0, 48.0),
    "s": (32.0, 48.0),
    "w": (32.0, 16.0),
}

AXES = {
    "ns": ("n", "s"),
    "ew": ("w", "e"),
}


@dataclass(frozen=True)
class Profile:
    name: str
    rise_px: int
    mode: str
    steps: int

    @property
    def rise_units(self) -> float:
        return self.rise_px / HEIGHT_PX_PER_UNIT


PROFILES = (
    # Two shallow ramps are useful for gentle terrain. The stair profiles are
    # discrete on purpose so adjacent sprite endpoints can match exactly.
    Profile("ramp_025", 4, "ramp", 0),
    Profile("ramp_050", 8, "ramp", 0),
    Profile("stairs_050_4", 8, "stairs", 4),
    Profile("stairs_075_6", 12, "stairs", 6),
    Profile("stairs_100_8", 16, "stairs", 8),
)


def load_source(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != (TILE_W, TILE_H):
        raise ValueError(f"{path}: expected {TILE_W}x{TILE_H}, got {image.size[0]}x{image.size[1]}")
    return image


def axis_t(x: float, y: float, axis: str, high_end: str) -> float:
    """Return normalized position 0..1 from the low endpoint to high endpoint."""
    a_name, b_name = AXES[axis]
    if high_end not in (a_name, b_name):
        raise ValueError(f"high_end={high_end} is not on axis={axis}")
    low_end = b_name if high_end == a_name else a_name
    x0, y0 = PORTS[low_end]
    x1, y1 = PORTS[high_end]
    vx, vy = x1 - x0, y1 - y0
    denom = vx * vx + vy * vy
    if denom <= 0.0:
        return 0.0
    t = ((x - x0) * vx + (y - y0) * vy) / denom
    return max(0.0, min(1.0, t))


def step_index(t: float, steps: int) -> int:
    if steps <= 1:
        return 0
    return min(steps - 1, max(0, int(math.floor(t * steps))))


def displacement(profile: Profile, t: float) -> int:
    if profile.mode == "ramp":
        return int(round(profile.rise_px * t))
    idx = step_index(t, profile.steps)
    return int(round(profile.rise_px * idx / max(1, profile.steps - 1)))


def darken(pixel: tuple[int, int, int, int], factor: float = 0.68) -> tuple[int, int, int, int]:
    r, g, b, a = pixel
    return (int(r * factor), int(g * factor), int(b * factor), a)


def render_variant(source: Image.Image, axis: str, high_end: str, profile: Profile) -> Image.Image:
    """Bake one slope/stair variant to a transparent PNG canvas.

    Treads are copied directly from the approved source texture. Stair risers
    are generated only at quantized step boundaries and are clipped by the
    source alpha, preventing the long free-form protruding lines seen in the
    runtime procedural proof.
    """
    src = source.load()
    out = Image.new("RGBA", (TILE_W, CANVAS_H), (0, 0, 0, 0))
    dst = out.load()

    # Riser layer first, so tread pixels remain crisp on top.
    if profile.mode == "stairs":
        boundary_half_width = 0.012
        per_step_rise = max(1, int(math.ceil(profile.rise_px / max(1, profile.steps - 1))))
        for y in range(TILE_H):
            for x in range(TILE_W):
                px = src[x, y]
                if px[3] == 0:
                    continue
                t = axis_t(x + 0.5, y + 0.5, axis, high_end)
                scaled = t * profile.steps
                nearest = round(scaled)
                if nearest <= 0 or nearest >= profile.steps:
                    continue
                if abs(scaled - nearest) > boundary_half_width * profile.steps:
                    continue
                disp = displacement(profile, t)
                oy = y + TOP_PAD - disp
                riser = darken(px)
                for dy in range(1, per_step_rise + 1):
                    py = oy + dy
                    if 0 <= py < CANVAS_H:
                        # Preserve the strongest alpha already present.
                        if riser[3] >= dst[x, py][3]:
                            dst[x, py] = riser

    # Tread/ramp surface: exact source pixels, only repositioned vertically.
    for y in range(TILE_H):
        for x in range(TILE_W):
            px = src[x, y]
            if px[3] == 0:
                continue
            t = axis_t(x + 0.5, y + 0.5, axis, high_end)
            oy = y + TOP_PAD - displacement(profile, t)
            if 0 <= oy < CANVAS_H:
                dst[x, oy] = px

    return out


def profile_filename(axis: str, high_end: str, profile: Profile) -> str:
    return f"dirt_path_straight_{axis}_{profile.name}_high_{high_end}.png"


def make_contact_sheet(flat_ns: Image.Image, flat_ew: Image.Image, variants: list[tuple[str, Image.Image]], path: Path) -> None:
    cell_w = 176
    cell_h = 148
    columns = 4
    rows = math.ceil((2 + len(variants)) / columns)
    sheet = Image.new("RGBA", (cell_w * columns, cell_h * rows), (75, 112, 56, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    entries: list[tuple[str, Image.Image]] = [
        ("LEGACY FLAT NS", flat_ns),
        ("LEGACY FLAT EW", flat_ew),
        *variants,
    ]

    for i, (label, image) in enumerate(entries):
        col = i % columns
        row = i // columns
        x0 = col * cell_w
        y0 = row * cell_h
        draw.rectangle((x0 + 4, y0 + 4, x0 + cell_w - 5, y0 + cell_h - 5), fill=(49, 75, 39, 255))
        px = x0 + (cell_w - image.width) // 2
        py = y0 + 22
        if image.height == TILE_H:
            py += TOP_PAD
        sheet.alpha_composite(image, (px, py))
        draw.text((x0 + 8, y0 + 7), label, fill=(240, 243, 236, 255), font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns-source", type=Path, default=Path("assets/terrain/paths/dirt_01/dirt_path_05_straight_ns.png"))
    parser.add_argument("--ew-source", type=Path, default=Path("assets/terrain/paths/dirt_01/dirt_path_10_straight_ew.png"))
    parser.add_argument("--output-dir", type=Path, default=Path("out/dirt_slope_sprite_pilot"))
    parser.add_argument("--contact-sheet", type=Path, default=Path("out/dirt_slope_sprite_pilot_sheet.png"))
    parser.add_argument("--manifest", type=Path, default=Path("out/dirt_slope_sprite_pilot_manifest.json"))
    args = parser.parse_args()

    ns = load_source(args.ns_source)
    ew = load_source(args.ew_source)
    sources = {"ns": ns, "ew": ew}
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "contract": "CH_PATH_SPRITE_PILOT_V1",
        "runtime_visual_policy": "sprite_select_only",
        "tile_size": [TILE_W, TILE_H],
        "sprite_canvas": [TILE_W, CANVAS_H],
        "legacy_surface_y": TOP_PAD,
        "height_px_per_unit": HEIGHT_PX_PER_UNIT,
        "sources": {"ns": str(args.ns_source), "ew": str(args.ew_source)},
        "variants": [],
    }
    sheet_variants: list[tuple[str, Image.Image]] = []

    for axis, (a, b) in AXES.items():
        for high_end in (a, b):
            for profile in PROFILES:
                image = render_variant(sources[axis], axis, high_end, profile)
                filename = profile_filename(axis, high_end, profile)
                image.save(args.output_dir / filename)
                variant = {
                    "file": filename,
                    "axis": axis,
                    "high_end": high_end,
                    "profile": profile.name,
                    "mode": profile.mode,
                    "rise_px": profile.rise_px,
                    "rise_units": profile.rise_units,
                    "steps": profile.steps,
                }
                manifest["variants"].append(variant)  # type: ignore[index]
                sheet_variants.append((f"{axis.upper()} {profile.name} high {high_end.upper()}", image))

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    make_contact_sheet(ns, ew, sheet_variants, args.contact_sheet)

    expected = len(AXES) * 2 * len(PROFILES)
    generated = len(list(args.output_dir.glob("*.png")))
    if generated != expected:
        raise SystemExit(f"expected {expected} PNG variants, generated {generated}")

    print(
        f"PASS contract=CH_PATH_SPRITE_PILOT_V1 generated={generated} "
        f"source_texture_preserved=true output={args.output_dir}"
    )


if __name__ == "__main__":
    main()
