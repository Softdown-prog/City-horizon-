#!/usr/bin/env python3
"""Non-destructive rail PNG scale audit for CH_GRID_V1/CH_CAMERA_V1.

A PNG's 512x512 canvas is not its visible footprint. Compare visible alpha
bounds at preview scale against a canonical 128x64 diamond; report findings
without inventing approved anchor or game scale.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

PIECES = {
    "straight": ("south", "west"),
    "curve_left_90": ("south", "west", "north", "east"),
    "curve_right_90": ("south", "west", "north", "east"),
    "turnout_left": ("south", "west", "north", "east"),
    "turnout_right": ("south", "west", "north", "east"),
}


def audit(root: Path, preview_scale: float) -> dict:
    if preview_scale <= 0:
        raise ValueError("preview scale must be positive")
    entries = {}
    warnings = []
    for kind, directions in PIECES.items():
        for direction in directions:
            name = f"{kind}_{direction}.png"
            path = root / name
            if not path.is_file():
                raise FileNotFoundError(path)
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
                if rgba.size != (512, 512):
                    raise ValueError(f"{name}: expected 512x512; got {rgba.size}")
                alpha = rgba.getchannel("A")
                box = alpha.getbbox()
                if box is None:
                    raise ValueError(f"{name}: empty alpha bounds")
                width, height = box[2] - box[0], box[3] - box[1]
                if alpha.getextrema()[0] == 255:
                    raise ValueError(f"{name}: no transparent background")
                entry = {
                    "alphaBoundsPixels": list(box),
                    "visibleWidthPixels": width,
                    "visibleHeightPixels": height,
                    "previewScale": preview_scale,
                    "previewVisibleWidthPixels": round(width * preview_scale, 2),
                    "previewVisibleHeightPixels": round(height * preview_scale, 2),
                    "previewWidthIn128pxTiles": round(width * preview_scale / 128.0, 3),
                    "previewHeightIn64pxTiles": round(height * preview_scale / 64.0, 3),
                    "scaleFor128pxVisibleWidth": round(128.0 / width, 5),
                }
                entries[name] = entry
                if width * preview_scale > 128 * 1.5:
                    warnings.append(
                        f"{name}: preview width {width*preview_scale:.1f}px "
                        "exceeds 1.5 times the 128px grid diamond width"
                    )
    return {
        "contract": "CH_RAIL_PRERENDER_SCALE_AUDIT_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridTilePixels": [128, 64],
        "note": "Diagnostics only; projected port parity and per-piece anchors still require connected-route inspection.",
        "previewScale": preview_scale,
        "checked": len(entries),
        "entries": entries,
        "warnings": warnings,
        "approvedForRuntime": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("assets/rail/prerendered_v1"))
    parser.add_argument("--preview-scale", type=float, default=0.45)
    parser.add_argument("--output", type=Path, default=Path("out/rail-scale-audit.json"))
    args = parser.parse_args()
    report = audit(args.root, args.preview_scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Audited {report['checked']} real PNGs; {len(report['warnings'])} potential scale issues")
    for warning in report["warnings"]:
        print("WARNING:", warning)
