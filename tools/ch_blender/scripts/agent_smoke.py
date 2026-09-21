"""Minimal Blender-side smoke probe for the CH Blender agent worker."""
from __future__ import annotations

import json
import os
from pathlib import Path

import bpy

out_dir = Path(os.environ["CH_AGENT_OUTPUT_DIR"])
out_dir.mkdir(parents=True, exist_ok=True)

payload = {
    "contract": "CH_BLENDER_AGENT_SMOKE_V1",
    "status": "ok",
    "blenderVersion": bpy.app.version_string,
    "background": bool(bpy.app.background),
    "factoryStartupExpected": True,
}

(out_dir / "smoke.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print("CH_BLENDER_AGENT_SMOKE_OK")
