"""Visual Reference Gate — Building Composer PNG MAE comparison.

Compares a candidate PNG (freshly rendered by MapForge2ComposerPreview) against
a stored golden reference.  Fails with exit code 1 if the Mean Absolute Error
(per channel, per pixel) exceeds the threshold.

On first run (no golden exists) the candidate is promoted automatically as the
new golden and the gate passes.  This lets the gate be added to CI before a
golden file is committed.

Usage
-----
    python tools/visual_reference_gate.py \\
        --candidate dist/MapForge2/visual_tests/building_composer_pilot_review.png \\
        --golden    C++/MapForge2/examples/golden_building_composer_pilot_review.png \\
        --diff-out  dist/MapForge2/visual_tests/visual_reference_diff.png \\
        --report    dist/MapForge2/visual_tests/visual_reference_gate.json \\
        --threshold 2.0
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageChops
except ImportError as exc:  # pragma: no cover
    print(
        f"[ERROR] Missing dependency: {exc}. "
        "Install with: pip install pillow numpy",
        file=sys.stderr,
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visual Reference Gate — pixel-level MAE gate for Building Composer output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--candidate",
        required=True,
        metavar="PATH",
        help="Path to the freshly rendered candidate PNG",
    )
    parser.add_argument(
        "--golden",
        required=True,
        metavar="PATH",
        help="Path to the stored golden reference PNG",
    )
    parser.add_argument(
        "--diff-out",
        default=None,
        metavar="PATH",
        help="Output path for the pixel-difference image (optional)",
    )
    parser.add_argument(
        "--report",
        default=None,
        metavar="PATH",
        help="Output path for the JSON gate report (optional)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=2.0,
        metavar="FLOAT",
        help="Maximum allowed MAE (per channel, per pixel, 0–255). Default: 2.0",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


def compute_mae(candidate: Image.Image, golden: Image.Image) -> tuple[float, Image.Image]:
    """Return (MAE, difference_image). Both images must be RGB."""
    if candidate.size != golden.size:
        golden = golden.resize(candidate.size, Image.Resampling.LANCZOS)

    diff = ImageChops.difference(candidate, golden)
    mae = float(np.array(diff, dtype=np.float32).mean())
    return mae, diff


def run_gate(args: argparse.Namespace) -> int:
    candidate_path = Path(args.candidate)
    golden_path = Path(args.golden)
    diff_out = Path(args.diff_out) if args.diff_out else None
    report_out = Path(args.report) if args.report else None
    threshold = args.threshold

    # ── Validate candidate exists ─────────────────────────────────────────
    if not candidate_path.is_file():
        print(f"[ERROR] Candidate PNG not found: {candidate_path}", file=sys.stderr)
        return 1

    # ── Auto-promote if no golden yet ─────────────────────────────────────
    if not golden_path.is_file():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate_path, golden_path)
        result = {
            "status": "golden_promoted",
            "mae": 0.0,
            "threshold": threshold,
            "candidate": str(candidate_path),
            "golden": str(golden_path),
            "message": (
                "No golden reference existed. "
                "Candidate promoted as the new golden. "
                "Commit this file to lock the visual reference."
            ),
        }
        _print_result(result)
        if report_out:
            report_out.parent.mkdir(parents=True, exist_ok=True)
            report_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0

    # ── Load and compare ──────────────────────────────────────────────────
    try:
        candidate_img = Image.open(candidate_path).convert("RGB")
        golden_img = Image.open(golden_path).convert("RGB")
    except Exception as exc:
        print(f"[ERROR] Failed to open PNG: {exc}", file=sys.stderr)
        return 1

    mae, diff_img = compute_mae(candidate_img, golden_img)
    passed = mae < threshold

    # ── Write diff image ──────────────────────────────────────────────────
    if diff_out:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
        diff_img.save(diff_out)

    # ── Compose report ────────────────────────────────────────────────────
    result = {
        "status": "passed" if passed else "failed",
        "mae": round(mae, 4),
        "threshold": threshold,
        "candidate": str(candidate_path),
        "golden": str(golden_path),
        "diffImage": str(diff_out) if diff_out else None,
    }
    if not passed:
        result["message"] = (
            f"Visual regression detected: MAE={mae:.4f} exceeds threshold={threshold}. "
            "If this change is intentional, update the golden reference by replacing "
            f"'{golden_path}' with the new candidate and committing."
        )

    _print_result(result)

    if report_out:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return 0 if passed else 1


def _print_result(result: dict) -> None:
    status = result["status"].upper()
    mae = result.get("mae", 0.0)
    threshold = result.get("threshold", 2.0)
    print(f"[visual-reference-gate] {status}  MAE={mae:.4f}  threshold={threshold}")
    if "message" in result:
        print(f"[visual-reference-gate] {result['message']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    return run_gate(args)


if __name__ == "__main__":
    sys.exit(main())
