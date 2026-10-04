#!/usr/bin/env python3
"""Optional soft material-transition worker for City Horizon ground tiles.

This worker is intentionally NOT part of the mandatory atomic-path contract.
Use it only for terrain materials that should visually feather into the surface
below (sand->grass, mud->grass, gravel->grass, etc.).

It preserves the authored material in the center and only reduces alpha inside a
small perimeter band of the canonical 128x64 isometric diamond. A deterministic
low-amplitude irregularity avoids a perfectly mechanical border without painting
or inventing new material artwork.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tile_geometry import diamond_mask

W, H = 128, 64


def _hash01(x: int, y: int, seed: int) -> float:
    n = (x * 374761393 + y * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    n ^= n >> 13
    n = (n * 1274126177) & 0xFFFFFFFFFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFF) / 65535.0


def _diamond_depth(x: int, y: int) -> float:
    """Approximate inward depth from the 2:1 diamond edge, in screen pixels."""
    cx = (W - 1) / 2.0
    cy = (H - 1) / 2.0
    d = abs(x - cx) / (W / 2.0) + abs(y - cy) / (H / 2.0)
    return max(0.0, (1.0 - d) * (H / 2.0))


def make_transition(source: Image.Image, fade_pixels: float, irregularity: float, seed: int) -> Image.Image:
    source = source.convert("RGBA")
    if source.size != (W, H):
        raise ValueError(f"source must be exactly {W}x{H}; got {source.width}x{source.height}")
    if fade_pixels <= 0:
        raise ValueError("fade_pixels must be > 0")

    result = source.copy()
    src = source.load()
    dst = result.load()
    mask = diamond_mask().load()

    for y in range(H):
        for x in range(W):
            if mask[x, y] == 0:
                dst[x, y] = (0, 0, 0, 0)
                continue

            r, g, b, a = src[x, y]
            depth = _diamond_depth(x, y)
            jitter = (_hash01(x, y, seed) - 0.5) * 2.0 * irregularity
            threshold = max(0.5, fade_pixels + jitter)
            t = min(1.0, max(0.0, depth / threshold))
            # Smoothstep keeps the blend subtle and avoids a visible alpha ring.
            t = t * t * (3.0 - 2.0 * t)
            dst[x, y] = (r, g, b, round(a * t))

    return result


def composite_preview(overlay: Image.Image, underlay: Image.Image, output: Path) -> None:
    underlay = underlay.convert("RGBA")
    if underlay.size != (W, H):
        underlay = underlay.resize((W, H), Image.Resampling.LANCZOS)
    canvas = Image.alpha_composite(underlay, overlay)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an optional feathered terrain-material overlay.")
    parser.add_argument("--source", type=Path, required=True, help="Prepared 128x64 RGBA material tile")
    parser.add_argument("--output", type=Path, required=True, help="Output RGBA transition overlay")
    parser.add_argument("--fade-pixels", type=float, default=5.0, help="Approximate inward feather width")
    parser.add_argument("--irregularity", type=float, default=1.5, help="Deterministic edge variation in pixels")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--underlay", type=Path, help="Optional surface image used only for visual preview")
    parser.add_argument("--preview", type=Path, help="Optional composited preview path")
    args = parser.parse_args()

    source = Image.open(args.source).convert("RGBA")
    overlay = make_transition(source, args.fade_pixels, args.irregularity, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(args.output, "PNG")

    if args.preview:
        if not args.underlay:
            parser.error("--preview requires --underlay")
        underlay = Image.open(args.underlay).convert("RGBA")
        composite_preview(overlay, underlay, args.preview)

    print(
        f"PASS terrain transition overlay -> {args.output} "
        f"fade={args.fade_pixels} irregularity={args.irregularity} seed={args.seed}"
    )


if __name__ == "__main__":
    main()
