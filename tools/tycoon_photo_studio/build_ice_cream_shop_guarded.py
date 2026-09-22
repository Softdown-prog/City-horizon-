"""Guarded SOUTH review builder for the procedural animated ice cream shop.

This intentionally reuses the canonical small-commercial gate for preflight and
human proxy review, while swapping only the deterministic expander. The final
animated bake is performed only after the reviewed SOUTH proxy is approved.
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

# Reuse the proven gate, camera, lighting, color-mask validation and proxy
# rendering. Replace the guarded builder's expander reference without mutating
# generate_small_commercial_asset itself: the ice-cream specialization calls
# that base expander internally, so mutating the shared module would recurse.
guarded.commercial = SimpleNamespace(expand=ice_cream.expand)


def main():
    # This builder is the visual gate. Keep final animation baking separate so
    # an unreviewed procedural design cannot accidentally become production art.
    if "--stage" in sys.argv:
        idx = sys.argv.index("--stage")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "final":
            raise RuntimeError(
                "ICE_CREAM_FINAL_IS_ANIMATED: approve the SOUTH proxy first, then use the animated final baker"
            )
    guarded.main()


if __name__ == "__main__":
    main()
