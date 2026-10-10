#!/usr/bin/env python3
"""Fail closed if the approved rail sprite catalog has missing artwork.

An illustrated procedural rail line is not proof of real pre-rendered track assets.
Run this gate before labeling a train video 'on approved pre-rendered rails'.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "src/rail_2d_visual_catalog.cpp"

def main() -> int:
    source = CATALOG.read_text(encoding="utf-8")
    paths = sorted(set(re.findall(r'assets/rail/prerendered_v1/[A-Za-z0-9_/-]+\.png', source)))
    if len(paths) != 18:
        print(f"FAIL: expected 18 distinct approved rail sprite paths, found {len(paths)}")
        return 1
    missing = [p for p in paths if not (ROOT / p).is_file()]
    if missing:
        print("BLOCKED: cannot claim on-asset real-rail visual proof.")
        print(f"Missing {len(missing)} of {len(paths)} referenced pre-rendered rail PNGs:")
        for path in missing:
            print(f" - {path}")
        return 2
    print(f"PASS: {len(paths)} approved rail visuals exist; geometry and placement still need video validation.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
