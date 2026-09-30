#!/usr/bin/env python3
"""Compose clown_01 over the immutable approved CH Actor PNG frames.

This script NEVER regenerates or rewrites locomotion. Production body pixels come
from assets/characters/ch_actor_green_01/frames. Costume overlays are matched by
filename and alpha-composited at (0, 0), preserving the approved 48x64 frame and
[24, 60] ground anchor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

FRAME = (48, 64)
ANCHOR = (24, 60)
DIRECTIONS = "sewn"
BASE_DIR = Path("assets/characters/ch_actor_green_01/frames")
BASE_MASK_DIR = Path("assets/characters/ch_actor_green_01/masks")
DEFAULT_OVERLAY = Path("assets/characters/ch_actor_green_01/costumes/clown_01")
DEFAULT_OUTPUT = Path("out/ch_actor_clown_validated")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_names() -> list[str]:
    names: list[str] = []
    for d in DIRECTIONS:
        names.append(f"{d}_idle.png")
        names.extend(f"{d}_walk_{i:02d}.png" for i in range(8))
    return names


def load_rgba(path: Path) -> Image.Image:
    if not path.is_file():
        raise SystemExit(f"Missing required file: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != FRAME:
        raise SystemExit(f"Unexpected frame size {image.size} for {path}; expected {FRAME}")
    return image


def coverage_ratio(mask: Image.Image, overlay: Image.Image) -> float:
    mask_a = mask.getchannel("A")
    overlay_a = overlay.getchannel("A")
    covered = total = 0
    for ma, oa in zip(mask_a.getdata(), overlay_a.getdata()):
        if ma > 0:
            total += 1
            if oa > 32:
                covered += 1
    return covered / total if total else 1.0


def build_sheet(frames: Path, out: Path) -> None:
    sheet = Image.new("RGBA", (FRAME[0] * 8, FRAME[1] * 4), (0, 0, 0, 0))
    for row, d in enumerate(DIRECTIONS):
        for i in range(8):
            frame = load_rgba(frames / f"{d}_walk_{i:02d}.png")
            sheet.alpha_composite(frame, (i * FRAME[0], row * FRAME[1]))
    sheet.save(out)


def build_idle_strip(frames: Path, out: Path) -> None:
    strip = Image.new("RGBA", (FRAME[0] * 4, FRAME[1]), (0, 0, 0, 0))
    for col, d in enumerate(DIRECTIONS):
        strip.alpha_composite(load_rgba(frames / f"{d}_idle.png"), (col * FRAME[0], 0))
    strip.save(out)


def checker(frame: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", FRAME, (45, 58, 65, 255))
    draw = ImageDraw.Draw(bg)
    for y in range(0, FRAME[1], 4):
        for x in range(0, FRAME[0], 4):
            if ((x // 4) + (y // 4)) & 1:
                draw.rectangle((x, y, min(x + 3, 47), min(y + 3, 63)), fill=(57, 73, 80, 255))
    bg.alpha_composite(frame)
    return bg


def build_review_gif(frames: Path, out: Path) -> None:
    ticks = []
    positions = ((0, 0), (192, 0), (0, 256), (192, 256))
    for i in range(8):
        board = Image.new("RGBA", (384, 512), (35, 45, 52, 255))
        for d, pos in zip(DIRECTIONS, positions):
            frame = checker(load_rgba(frames / f"{d}_walk_{i:02d}.png"))
            board.alpha_composite(frame.resize((192, 256), Image.Resampling.NEAREST), pos)
        ticks.append(board.convert("P", palette=Image.Palette.ADAPTIVE))
    ticks[0].save(out, save_all=True, append_images=ticks[1:], duration=138, loop=0, disposal=2)


def compose(overlay_root: Path, output: Path) -> dict:
    overlay_frames = overlay_root / "frames"
    output_frames = output / "frames"
    output_frames.mkdir(parents=True, exist_ok=True)
    records = []
    for name in expected_names():
        base_path = BASE_DIR / name
        mask_path = BASE_MASK_DIR / name
        overlay_path = overlay_frames / name
        base = load_rgba(base_path)
        mask = load_rgba(mask_path)
        overlay = load_rgba(overlay_path)
        final = base.copy()
        final.alpha_composite(overlay, (0, 0))
        final_path = output_frames / name
        final.save(final_path)
        records.append({
            "frame": name,
            "approvedBaseSha256": sha256(base_path),
            "approvedMaskSha256": sha256(mask_path),
            "costumeOverlaySha256": sha256(overlay_path),
            "finalSha256": sha256(final_path),
            "clothingCoverageByOverlay": round(coverage_ratio(mask, overlay), 6),
        })

    build_sheet(output_frames, output / "clown_01_walk_8x4.png")
    build_idle_strip(output_frames, output / "clown_01_idle_4dir.png")
    build_review_gif(output_frames, output / "clown_01_walk_4dir.gif")
    manifest = {
        "contract": "CH_ACTOR_APPROVED_BASE_COMPOSITE_V1",
        "actor": "ch_actor_green_01",
        "skin": "clown_01",
        "productionBase": BASE_DIR.as_posix(),
        "productionMasks": BASE_MASK_DIR.as_posix(),
        "costumeOverlay": overlay_root.as_posix(),
        "frame": {"size": list(FRAME), "groundAnchor": list(ANCHOR)},
        "sourceFrameCount": 36,
        "walkFrameCount": 32,
        "idleFrameCount": 4,
        "directions": list(DIRECTIONS),
        "motionPolicy": "approved_png_frames_are_immutable_and_never_retimed_or_repositioned",
        "composition": "approved_base + costume_overlay at exact pixel origin (0,0)",
        "records": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-root", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = compose(args.overlay_root, args.output)
    ratios = [r["clothingCoverageByOverlay"] for r in manifest["records"]]
    print("CH Actor approved-base clown composite OK")
    print(f" - approved source frames: {manifest['sourceFrameCount']}")
    print(f" - frame / anchor: {FRAME} / {ANCHOR}")
    print(f" - minimum clothing overlay coverage: {min(ratios):.3f}")
    print(f" - output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
