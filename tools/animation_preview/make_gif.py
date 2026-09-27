#!/usr/bin/env python3
"""Build deterministic review GIFs from ordered PNG frame sequences.

GIFs produced here are review artifacts only. Runtime animation continues to use
PNG frames / overlays and their own metadata contracts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

CONTRACT = "CH_ANIMATION_PREVIEW_V1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CONTRACT:
        raise ValueError(f"Expected {CONTRACT}, got {payload.get('contract')!r}")
    return payload


def _resolve_frames(manifest_path: Path, manifest: dict) -> list[Path]:
    base = manifest_path.parent
    explicit = manifest.get("frames")
    if explicit:
        frames = [(base / item).resolve() for item in explicit]
    else:
        frame_dir = (base / manifest.get("frameDir", "frames")).resolve()
        pattern = manifest.get("pattern", "frame_*.png")
        frames = sorted(frame_dir.glob(pattern))
    if len(frames) < 2:
        raise ValueError("Animation preview requires at least two PNG frames")
    missing = [str(path) for path in frames if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing animation frames: {missing}")
    return frames


def _rgb_background(value: object) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        return (24, 30, 36)
    return tuple(max(0, min(255, int(v))) for v in value)  # type: ignore[return-value]


def _flatten(frame: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    rgba = frame.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, (*background, 255))
    canvas.alpha_composite(rgba)
    return canvas.convert("RGB")


def _shared_palette(frames: list[Image.Image]) -> Image.Image:
    thumbs: list[Image.Image] = []
    for frame in frames:
        # Pillow only accepts RGB/L inputs when quantizing against a palette. Keep the
        # shared palette source explicitly RGB even if an upstream renderer changes
        # the PNG mode in the future (RGBA, P, LA, etc.).
        thumb = frame.convert("RGB")
        thumb.thumbnail((160, 160), Image.Resampling.LANCZOS)
        thumbs.append(thumb)
    width = max(img.width for img in thumbs)
    height = sum(img.height for img in thumbs)
    strip = Image.new("RGB", (width, height))
    y = 0
    for img in thumbs:
        strip.paste(img, (0, y))
        y += img.height
    return strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def _contact_sheet(frames: list[Image.Image], output: Path, labels: bool = True) -> None:
    cols = min(6, len(frames))
    rows = (len(frames) + cols - 1) // cols
    cell_w = 320
    cell_h = 340 if labels else 320
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (24, 30, 36))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        copy = frame.convert("RGB")
        copy.thumbnail((cell_w - 12, 310), Image.Resampling.LANCZOS)
        col = index % cols
        row = index // cols
        x = col * cell_w + (cell_w - copy.width) // 2
        y = row * cell_h + 8
        sheet.paste(copy, (x, y))
        if labels:
            draw.text((col * cell_w + 8, row * cell_h + 316), f"frame {index:02d}", fill=(235, 235, 235))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")


def build_from_manifest(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    frames_paths = _resolve_frames(manifest_path, manifest)
    background = _rgb_background(manifest.get("background"))
    duration_ms = max(20, int(manifest.get("durationMs", 90)))
    loop = max(0, int(manifest.get("loop", 0)))
    ping_pong = bool(manifest.get("pingPong", False))

    loaded = [_flatten(Image.open(path), background) for path in frames_paths]
    ordered = loaded
    ordered_paths = frames_paths
    if ping_pong and len(loaded) > 2:
        ordered = loaded + loaded[-2:0:-1]
        ordered_paths = frames_paths + frames_paths[-2:0:-1]

    palette = _shared_palette(ordered)
    paletted = [
        # Explicit conversion is intentional. Some Pillow/plugin combinations can
        # preserve a non-RGB mode even after compositing, and palette quantization
        # rejects RGBA/P/LA inputs. This makes GIF generation renderer-agnostic.
        frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in ordered
    ]

    output = (manifest_path.parent / manifest.get("output", "animation_preview.gif")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    paletted[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=paletted[1:],
        duration=duration_ms,
        loop=loop,
        optimize=False,
        disposal=2,
    )

    contact = manifest.get("contactSheet")
    contact_path = None
    if contact:
        contact_path = (manifest_path.parent / str(contact)).resolve()
        _contact_sheet(ordered, contact_path)

    report = {
        "contract": CONTRACT,
        "status": "ok",
        "id": manifest.get("id"),
        "reviewOnly": bool(manifest.get("reviewOnly", True)),
        "manifest": str(manifest_path),
        "output": str(output),
        "outputSha256": _sha256(output),
        "frameCount": len(ordered),
        "sourceFrameCount": len(frames_paths),
        "durationMs": duration_ms,
        "loop": loop,
        "pingPong": ping_pong,
        "size": list(loaded[0].size),
        "frameSha256": [_sha256(path) for path in ordered_paths],
        "contactSheet": str(contact_path) if contact_path else None,
    }
    report_path = output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def discover(root: Path) -> Iterable[Path]:
    yield from sorted(root.resolve().rglob("animation_preview_manifest.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build City Horizon review GIFs from PNG frame sequences")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path)
    group.add_argument("--discover-root", type=Path)
    args = parser.parse_args()

    manifests = [args.manifest] if args.manifest else list(discover(args.discover_root))
    if not manifests:
        print(json.dumps({"contract": CONTRACT, "status": "ok", "built": 0}))
        return 0

    reports = [build_from_manifest(path) for path in manifests]
    print(json.dumps({"contract": CONTRACT, "status": "ok", "built": len(reports), "reports": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
