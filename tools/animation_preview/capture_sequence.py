#!/usr/bin/env python3
"""Run a deterministic sequence of frame-capture commands and build a review GIF.

The capture command is supplied by JSON so the same orchestration can drive MapForge,
engine debug capture, Blender scripts, or any other deterministic renderer that accepts
an output PNG path. This tool does not screen-scrape a desktop; it asks the authoritative
renderer to write each frame.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from make_gif import CONTRACT as GIF_CONTRACT, build_from_manifest

CAPTURE_CONTRACT = "CH_FRAME_CAPTURE_SEQUENCE_V1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CAPTURE_CONTRACT:
        raise ValueError(f"Expected {CAPTURE_CONTRACT}, got {payload.get('contract')!r}")
    return payload


def _format(value: str, index: int, output: Path) -> str:
    return value.replace("{index}", str(index)).replace("{index03}", f"{index:03d}").replace("{output}", str(output))


def capture(recipe_path: Path) -> dict:
    recipe_path = recipe_path.resolve()
    recipe = _load(recipe_path)
    base = recipe_path.parent
    output_dir = (base / recipe.get("outputDir", "capture_output")).resolve()
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    capture_cfg = recipe.get("capture", {})
    command = capture_cfg.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError("capture.command must be a non-empty argv array")
    frame_count = int(recipe.get("frameCount", 0))
    if frame_count < 2:
        raise ValueError("frameCount must be >= 2")
    cwd = (base / capture_cfg.get("cwd", ".")).resolve()
    env = None

    frames: list[Path] = []
    for index in range(frame_count):
        output = frame_dir / f"frame_{index:03d}.png"
        argv = [_format(str(arg), index, output) for arg in command]
        subprocess.run(argv, cwd=cwd, env=env, check=True)
        if not output.is_file():
            raise RuntimeError(f"Capture command did not create {output}")
        frames.append(output)

    gif_cfg = recipe.get("gif", {})
    manifest = {
        "contract": GIF_CONTRACT,
        "id": recipe.get("id"),
        "reviewOnly": bool(recipe.get("reviewOnly", True)),
        "frames": [str(path.relative_to(output_dir)) for path in frames],
        "durationMs": int(gif_cfg.get("durationMs", 90)),
        "loop": int(gif_cfg.get("loop", 0)),
        "pingPong": bool(gif_cfg.get("pingPong", False)),
        "background": gif_cfg.get("background", [24, 30, 36]),
        "output": gif_cfg.get("output", "animation_preview.gif"),
        "contactSheet": gif_cfg.get("contactSheet", "animation_preview_contact_sheet.png"),
    }
    manifest_path = output_dir / "animation_preview_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = build_from_manifest(manifest_path)
    report["captureContract"] = CAPTURE_CONTRACT
    report["captureRecipe"] = str(recipe_path)
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture sequential PNG frames and build a review GIF")
    parser.add_argument("--recipe", type=Path, required=True)
    args = parser.parse_args()
    capture(args.recipe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
