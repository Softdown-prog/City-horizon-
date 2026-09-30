#!/usr/bin/env python3
"""Run the V2 four-direction builder with V2.2 refined directional art."""
from __future__ import annotations

import build_clown_four_directions_v2 as base
from clown_directional_art_v22 import build_direction

base.build_direction = build_direction

if __name__ == "__main__":
    raise SystemExit(base.main())
