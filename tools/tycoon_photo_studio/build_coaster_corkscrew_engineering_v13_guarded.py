"""V13 ratio calibration wrapper for the analytic-core corkscrew.

Keeps the validated V11/V12 analytic helix architecture, but tightens the
pitch/radius ratio so the inversion reads as a recognizable corkscrew while
retaining the longitudinal openness gained in V12.
"""

from __future__ import annotations

import json
from pathlib import Path

import build_coaster_corkscrew_guarded as v11


# Focused ratio calibration from V12 visual review. Keep transition/straight
# lengths unchanged so this iteration isolates helix radius vs. pitch.
v11.HELIX_RADIUS = v11.base.TILE * 0.575
v11.HELIX_PITCH = v11.base.TILE * 4.35
v11.TRANSITION_LENGTH = v11.base.TILE * 1.45
v11.STRAIGHT_LENGTH = v11.base.TILE * 0.85
v11.HELIX_SAMPLES = 281
v11.TRANSITION_SAMPLES = 61
v11.STRAIGHT_SAMPLES = 25
v11.FOOTPRINT = {"widthTiles": 4, "depthTiles": 10}


_original_write_metadata = v11.write_metadata


def _write_metadata_v13(output: Path, piece: str, centerline, solved, solver_meta):
    _original_write_metadata(output, piece, centerline, solved, solver_meta)
    path = output / "track_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["profile"] = "single_inversion_v13_analytic_helix_ratio_calibrated"
    payload["engineeringCalibration"] = {
        "goal": "restore recognizable corkscrew inversion while retaining longitudinal openness",
        "referenceMode": "v12_south_proxy_plus_plan",
        "helixRadiusTiles": 0.575,
        "helixPitchTiles": 4.35,
        "transitionLengthTiles": 1.45,
        "straightLengthTiles": 0.85,
        "independentRollDegrees": 0.0,
        "isolatedVariables": ["helixRadiusTiles", "helixPitchTiles"],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


v11.write_metadata = _write_metadata_v13


if __name__ == "__main__":
    v11.main()
