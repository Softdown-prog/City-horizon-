#!/usr/bin/env python3
"""Final guarded four-direction baker for building.ice_cream_shop.01.

Reuses the canonical small-commercial final baker (including CH_COLOR_MASK_V1)
while swapping in the approved ice-cream-shop V3 deterministic expander.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_small_commercial_guarded as guarded  # noqa: E402
import generate_ice_cream_shop_asset_v3 as ice_cream  # noqa: E402

# Keep all canonical preflight/final/color-mask behavior; only specialize the
# recipe expander for the approved sorveteria design.
guarded.commercial = SimpleNamespace(expand=ice_cream.expand)


if __name__ == "__main__":
    guarded.main()
