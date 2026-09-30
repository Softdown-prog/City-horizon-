"""V12 engineering calibration wrapper for the analytic-core corkscrew.

This iteration keeps the validated analytic helix architecture from V11 but
changes the engineering proportions so the inversion advances much farther
along the track axis while using a smaller vertical/lateral radius.  The goal
is to match the plan/elevation reading of a real corkscrew instead of the tall
compressed S silhouette seen in the SOUTH proxy.
"""

from __future__ import annotations

import json
from pathlib import Path

import build_coaster_corkscrew_guarded as v11


# Calibrated from the visual comparison against the supplied coaster plan:
# more longitudinal travel, lower vertical excursion, longer tangent shoulders.
v11.HELIX_RADIUS = v11.base.TILE * 0.50
v11.HELIX_PITCH = v11.base.TILE * 5.40
v11.TRANSITION_LENGTH = v11.base.TILE * 1.45
v11.STRAIGHT_LENGTH = v11.base.TILE * 0.85
v11.HELIX_SAMPLES = 281
v11.TRANSITION_SAMPLES = 61
v11.STRAIGHT_SAMPLES = 25
v11.FOOTPRINT = {"widthTiles": 4, "depthTiles": 10}


_original_write_metadata = v11.write_metadata


def _write_metadata_v12(output: Path, piece: str, centerline, solved, solver_meta):
    _original_write_metadata(output, piece, centerline, solved, solver_meta)
    path = output / "track_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["profile"] = "single_inversion_v12_analytic_helix_engineering_calibrated"
    payload["engineeringCalibration"] = {
        "goal": "increase longitudinal advance and reduce vertical-wall silhouette",
        "referenceMode": "plan_plus_elevation_plus_south_proxy",
        "helixRadiusTiles": 0.50,
        "helixPitchTiles": 5.40,
        "transitionLengthTiles": 1.45,
        "straightLengthTiles": 0.85,
        "independentRollDegrees": 0.0,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


v11.write_metadata = _write_metadata_v12


if __name__ == "__main__":
    v11.main()
