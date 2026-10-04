#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import build_pirate_ship_swing_passengers_direction as directional


def _arg_value(flag: str) -> str:
    argv = sys.argv
    if flag not in argv:
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_REQUIRED_ARG:{flag}")
    index = argv.index(flag)
    if index + 1 >= len(argv):
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_MISSING_VALUE:{flag}")
    return argv[index + 1]


def main() -> None:
    # Capture these before the delegated builder consumes --direction.
    direction = _arg_value("--direction").lower()
    output = Path(_arg_value("--output")).resolve()

    directional.main()

    # CH Blender's guarded proxy contract always checks for proxy_south.png.
    # Directional workers additionally emit proxy_<direction>.png; keep that
    # authoritative directional file and provide this compatibility alias so a
    # successful directional bake is not reported as EXPECTED_OUTPUT_MISSING.
    source = output / f"proxy_{direction}.png"
    canonical = output / "proxy_south.png"
    if not source.is_file():
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_PROXY_MISSING:{source}")
    if source != canonical:
        shutil.copyfile(source, canonical)


if __name__ == "__main__":
    main()
