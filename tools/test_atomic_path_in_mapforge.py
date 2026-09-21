#!/usr/bin/env python3
"""Deterministic one-command visual test for City Horizon atomic path tiles.

Pipeline:
  source image
    -> normalize_atomic_path_tile.py (128x64 RGBA)
    -> MAPFORGE_CAPTURE_REQUEST_V1 request
    -> MapForge2CLI capture (or MapForge2MapCapture fallback)
    -> JSON summary + PNG capture

This worker deliberately reuses the existing canonical normalizer and MapForge capture
entry points. It does not duplicate renderer or projection logic.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / "tools" / "normalize_atomic_path_tile.py"
DEFAULT_OUT = ROOT / "out" / "tile_test"


def _find_capture_executable(explicit: str | None) -> tuple[list[str], str]:
    if explicit:
        exe = Path(explicit)
        if not exe.exists():
            raise SystemExit(f"MapForge executable not found: {exe}")
        name = exe.name.lower()
        if "mapforge2cli" in name:
            return [str(exe), "capture"], "MapForge2CLI"
        return [str(exe)], "MapForge2MapCapture"

    candidates = []
    env_cli = os.environ.get("MAPFORGE2_CLI")
    env_capture = os.environ.get("MAPFORGE2_MAP_CAPTURE")
    if env_cli:
        candidates.append((Path(env_cli), True))
    if env_capture:
        candidates.append((Path(env_capture), False))

    for name, is_cli in (("MapForge2CLI", True), ("MapForge2CLI.exe", True),
                         ("MapForge2MapCapture", False), ("MapForge2MapCapture.exe", False)):
        located = shutil.which(name)
        if located:
            candidates.append((Path(located), is_cli))

    common = [
        ROOT / "build" / "C++" / "MapForge2" / "MapForge2CLI",
        ROOT / "build" / "C++" / "MapForge2" / "MapForge2CLI.exe",
        ROOT / "build" / "C++" / "MapForge2" / "MapForge2MapCapture",
        ROOT / "build" / "C++" / "MapForge2" / "MapForge2MapCapture.exe",
        ROOT / "C++" / "MapForge2" / "build" / "MapForge2CLI",
        ROOT / "C++" / "MapForge2" / "build" / "MapForge2CLI.exe",
        ROOT / "C++" / "MapForge2" / "build" / "MapForge2MapCapture",
        ROOT / "C++" / "MapForge2" / "build" / "MapForge2MapCapture.exe",
    ]
    for path in common:
        candidates.append((path, "cli" in path.name.lower()))

    for path, is_cli in candidates:
        if path.exists():
            return ([str(path), "capture"] if is_cli else [str(path)]), ("MapForge2CLI" if is_cli else "MapForge2MapCapture")

    raise SystemExit(
        "No MapForge capture executable found. Build MapForge2CLI or MapForge2MapCapture, "
        "or pass --mapforge-exe / set MAPFORGE2_CLI."
    )


def _capture_request() -> dict:
    # Repeated coordinates expose scale and seams better than a single tile.
    tiles = [[-2, 0], [-1, 0], [0, 0], [1, 0], [2, 0],
             [0, -2], [0, -1], [0, 1], [0, 2],
             [-1, -1], [1, 1]]
    return {
        "contract": "MAPFORGE_CAPTURE_REQUEST_V1",
        "source": {"workflow": "local-or-agent-worker", "file": "normalized_atomic_path.png"},
        "output": {"file": "mapforge_atomic_path_capture.png"},
        "capture": {
            "canvas": {"width": 1024, "height": 768, "background": "#313934"},
            "camera": {"zoom": 0.92, "focusTile": [0, 0], "focusScreen": [0.5, 0.56]},
            "stage": {
                "minTile": -6,
                "maxTile": 6,
                "groundColor": "#708963",
                "alternateGroundColor": "#768f69",
                "gridColor": "#3e4f3b",
                "drawGrid": True,
                "drawGrassTexture": True,
                "grassSpeckleColor": "#5f7f50",
            },
            "candidate": {
                "tile": [0, 0],
                "tiles": tiles,
                "footprint": [1, 1],
                "scale": 1.0,
                "offsetPixels": [0, 0],
                "showFootprint": False,
                "showAnchor": False,
                "renderAsGroundTile": True,
            },
        },
    }


def run(source: Path, out_dir: Path, mapforge_exe: str | None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized = out_dir / "normalized_atomic_path_128x64.png"
    request_path = out_dir / "capture_request.json"
    capture_path = out_dir / "mapforge_atomic_path_capture.png"

    subprocess.run([sys.executable, str(NORMALIZER), str(source), str(normalized)], check=True, cwd=ROOT)

    request_path.write_text(json.dumps(_capture_request(), indent=2), encoding="utf-8")

    prefix, backend = _find_capture_executable(mapforge_exe)
    command = prefix + [str(capture_path), str(normalized), str(request_path)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)

    result = {
        "contract": "CITY_HORIZON_TILE_TEST_RESULT_V1",
        "ok": completed.returncode == 0 and capture_path.exists(),
        "source": str(source.resolve()),
        "normalized": str(normalized.resolve()),
        "normalizedSpec": {"width": 128, "height": 64, "mode": "RGBA"},
        "capture": str(capture_path.resolve()),
        "request": str(request_path.resolve()),
        "backend": backend,
        "exitCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize an atomic path tile and render it in MapForge.")
    parser.add_argument("input", type=Path, help="Source PNG/JPG to test")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--mapforge-exe", help="Optional explicit MapForge2CLI or MapForge2MapCapture executable")
    args = parser.parse_args()

    source = args.input if args.input.is_absolute() else (ROOT / args.input)
    if not source.exists():
        raise SystemExit(f"source image not found: {source}")

    result = run(source, args.out_dir, args.mapforge_exe)
    print(json.dumps(result, separators=(",", ":")))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
