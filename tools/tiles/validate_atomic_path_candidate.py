#!/usr/bin/env python3
"""Worker wrapper for validating atomic-path candidates safely.

This prevents workflows from accidentally calling validate_ground_tiles.py with
an incomplete CLI. Every candidate passed here is validated against the
canonical `atomic-path` profile.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one or more City Horizon atomic-path PNG candidates.")
    parser.add_argument("files", nargs="+", type=Path, help="candidate PNGs")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    cmd = [sys.executable, "tools/validate_ground_tiles.py", "--profile", "atomic-path"]
    for path in args.files:
        cmd.extend(["--file", str(path)])
    if args.debug:
        cmd.append("--debug")

    print("atomic-path worker:", " ".join(cmd))
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
