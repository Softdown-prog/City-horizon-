#!/usr/bin/env python3
"""Run four-direction V2 builder with the V2.1 refined directional masters."""
from __future__ import annotations

import build_clown_four_directions_v2 as base
from clown_directional_art_v21 import build_direction

base.build_direction = build_direction

if __name__ == "__main__":
    raise SystemExit(base.main())
