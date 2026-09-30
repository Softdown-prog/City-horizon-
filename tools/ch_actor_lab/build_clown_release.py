"""Generate and validate the CH Clown V4 costume package in one command."""
from __future__ import annotations

import argparse
from pathlib import Path

from build_clown_costume import DEFAULT_REVIEW, DEFAULT_ROOT, build
from validate_clown_costume import validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    args = parser.parse_args()

    build(args.root, args.review)
    errors = validate(args.root)
    if errors:
        print(f"CH Clown V4 release FAILED ({len(errors)} error(s))")
        for error in errors:
            print(f" - {error}")
        return 1

    print("CH Clown V4 release package OK")
    print(f" - package: {args.root}")
    print(f" - review board: {args.review}")
    print(" - 36 overlays + 36 masks validated")
    print(" - 48x64 RGBA / ground anchor [24, 60]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
