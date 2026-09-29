#!/usr/bin/env python3
"""Build deterministic review videos from ordered PNG frame sequences.

Videos produced here are review/validation artifacts only. Runtime animation
continues to use PNG frames / overlays and their own metadata contracts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from PIL import Image

CONTRACT = "CH_VIDEO_PREVIEW_V1"
SUPPORTED_SUFFIXES = {".mp4", ".webm"}


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
        raise ValueError("Video preview requires at least two PNG frames")
    missing = [str(path) for path in frames if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing video frames: {missing}")
    return frames


def _rgb_background(value: object) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        return (24, 30, 36)
    return tuple(max(0, min(255, int(v))) for v in value)  # type: ignore[return-value]


def _ordered_frames(frames: list[Path], ping_pong: bool) -> list[Path]:
    if ping_pong and len(frames) > 2:
        return frames + frames[-2:0:-1]
    return frames


def _prepare_frames(
    frames: list[Path],
    destination: Path,
    background: tuple[int, int, int],
) -> tuple[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    expected_size: tuple[int, int] | None = None
    output_size: tuple[int, int] | None = None

    for index, source in enumerate(frames):
        with Image.open(source) as image:
            rgba = image.convert("RGBA")
            if expected_size is None:
                expected_size = rgba.size
            elif rgba.size != expected_size:
                raise ValueError(
                    f"All video frames must have the same size; "
                    f"expected {expected_size}, got {rgba.size} for {source}"
                )

            canvas = Image.new("RGBA", rgba.size, (*background, 255))
            canvas.alpha_composite(rgba)
            rgb = canvas.convert("RGB")

            # yuv420p encoders require even dimensions. Padding one pixel on the
            # right/bottom preserves the source image without rescaling it.
            padded_w = rgb.width + (rgb.width % 2)
            padded_h = rgb.height + (rgb.height % 2)
            if (padded_w, padded_h) != rgb.size:
                padded = Image.new("RGB", (padded_w, padded_h), background)
                padded.paste(rgb, (0, 0))
                rgb = padded
            output_size = rgb.size
            rgb.save(destination / f"frame_{index:06d}.png", format="PNG")

    if output_size is None:
        raise ValueError("No frames prepared for video")
    return output_size


def _ffmpeg_command(frame_dir: Path, output: Path, fps: int) -> list[str]:
    common = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        "0",
        "-i",
        str(frame_dir / "frame_%06d.png"),
        "-an",
    ]

    if output.suffix.lower() == ".mp4":
        return common + [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]

    if output.suffix.lower() == ".webm":
        return common + [
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "24",
            "-b:v",
            "0",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]

    raise ValueError(f"Unsupported video output extension: {output.suffix}")


def _probe(output: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_frames",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def build_from_manifest(manifest_path: Path) -> dict:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required for CH Video Preview")

    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    source_frames = _resolve_frames(manifest_path, manifest)
    ping_pong = bool(manifest.get("pingPong", False))
    ordered_frames = _ordered_frames(source_frames, ping_pong)
    background = _rgb_background(manifest.get("background"))
    fps = max(1, min(120, int(manifest.get("fps", 30))))

    output = (manifest_path.parent / manifest.get("output", "video_preview.mp4")).resolve()
    if output.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("video output must end in .mp4 or .webm")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ch_video_preview_") as temp_name:
        temp_dir = Path(temp_name)
        size = _prepare_frames(ordered_frames, temp_dir, background)
        subprocess.run(_ffmpeg_command(temp_dir, output, fps), check=True)

    probe = _probe(output)
    report = {
        "contract": CONTRACT,
        "status": "ok",
        "id": manifest.get("id"),
        "reviewOnly": bool(manifest.get("reviewOnly", True)),
        "manifest": str(manifest_path),
        "output": str(output),
        "outputSha256": _sha256(output),
        "format": output.suffix.lower().lstrip("."),
        "fps": fps,
        "frameCount": len(ordered_frames),
        "sourceFrameCount": len(source_frames),
        "durationSeconds": len(ordered_frames) / fps,
        "pingPong": ping_pong,
        "size": list(size),
        "sourceFrameSha256": [_sha256(path) for path in ordered_frames],
        "probe": probe,
    }
    report_path = output.with_suffix(output.suffix + ".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def discover(root: Path) -> Iterable[Path]:
    yield from sorted(root.resolve().rglob("video_preview_manifest.json"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build City Horizon review videos from PNG frame sequences"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path)
    group.add_argument("--discover-root", type=Path)
    args = parser.parse_args()

    manifests = [args.manifest] if args.manifest else list(discover(args.discover_root))
    if not manifests:
        print(json.dumps({"contract": CONTRACT, "status": "ok", "built": 0}))
        return 0

    reports = [build_from_manifest(path) for path in manifests]
    print(
        json.dumps(
            {"contract": CONTRACT, "status": "ok", "built": len(reports), "reports": reports},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
