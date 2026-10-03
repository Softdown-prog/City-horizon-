#!/usr/bin/env python3
"""Hard guard against reintroducing the rejected City Horizon Viking lineage.

This file intentionally does not author geometry. It exists so future Viking work can
be validated before a Blender job is queued. The previous Viking builders/recipes were
removed after repeated visual convergence on the same rejected miniature-like family.
"""
from pathlib import Path
import sys

FORBIDDEN_TOKENS = (
    "build_viking_ship_guarded",
    "build_viking_ship_fullscale",
    "build_viking_ship_reference_mesh",
    "CITY_HORIZON_VIKING_SHIP_RIDE_V1",
    "CH_VIKING_SHIP_FULLSCALE_V1",
    "CH_VIKING_SHIP_REFERENCE_MESH_V1",
    "CH_TYCOON_MINIATURE_V1",
    "park_viking_ship_5x4",
    "rebuild_v2",
    "rebuild_v3",
    "rebuild_v4",
    "rebuild_v5",
    "rebuild_v6",
)


def validate(paths):
    violations = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            violations.append(f"missing:{path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path}:{token}")
    return violations


def main():
    violations = validate(sys.argv[1:])
    if violations:
        raise SystemExit("CH_VIKING_AUTHORING_RESET_REJECTED\n" + "\n".join(violations))
    print("CH_VIKING_AUTHORING_RESET_PASS")


if __name__ == "__main__":
    main()
