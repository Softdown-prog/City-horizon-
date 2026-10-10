#!/usr/bin/env python3
"""Validate promoted CH Blender V2 train diagonals without changing approved art."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
VIEWS = ("north_east", "east_south", "south_west", "west_north")
ROLES = {"locomotive": 641, "coach": 684}
SIGNATURE = b"\x89PNG\r\n\x1a\n"

def verify() -> None:
    errors = []
    for role, expected_y in ROLES.items():
        directory = ROOT / "assets" / "vehicles" / f"steam_train_{role}_01"
        manifest_path = directory / "steam_train_diagonal_runtime.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{manifest_path}: {exc}")
            continue
        for key, expected in (
            ("contract", "CH_RAIL_DIAGONAL_RUNTIME_V1"),
            ("unitRole", role),
            ("cameraContract", "CH_CAMERA_V1"),
            ("approvedForRuntime", True),
            ("originalCardinalViewsPreserved", True),
            ("runtimePixelScaleCompensation", 1.28),
        ):
            if manifest.get(key) != expected:
                errors.append(f"{manifest_path}: {key} must be {expected!r}")
        views = manifest.get("views")
        if not isinstance(views, dict) or set(views) != set(VIEWS):
            errors.append(f"{manifest_path}: expected exactly {VIEWS}")
            continue
        for direction in VIEWS:
            entry = views[direction]
            filename = f"steam_train_{role}_{direction}.png"
            if not isinstance(entry, dict) or entry.get("file") != filename:
                errors.append(f"{manifest_path}: bad filename in {direction}")
                continue
            if entry.get("pivot") != {"x": 512, "y": expected_y}:
                errors.append(f"{manifest_path}: bad {direction} ground pivot")
            path = directory / filename
            try:
                data = path.read_bytes()
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            if not data.startswith(SIGNATURE) or len(data) < 33 or data[12:16] != b"IHDR":
                errors.append(f"{path}: invalid PNG header")
                continue
            width, height = struct.unpack(">II", data[16:24])
            if (width, height) != (1024, 1024):
                errors.append(f"{path}: expected 1024x1024, got {width}x{height}")
            actual = hashlib.sha256(data).hexdigest()
            if entry.get("sha256") != actual:
                errors.append(f"{path}: SHA-256 differs from approved manifest")
        for direction in ("south", "west", "north", "east"):
            if not (directory / f"steam_train_{role}_{direction}.png").is_file():
                errors.append(f"{directory}: missing original fallback {direction}")
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print("PASS: all 8 approved diagonal PNGs, manifests, pivots and 4-view fallbacks validated")

if __name__ == "__main__":
    verify()
