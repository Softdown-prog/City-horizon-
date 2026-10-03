#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STUDIO = REPO_ROOT / "tools" / "tycoon_photo_studio"
for path in (HERE, STUDIO):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

runpy.run_path(str(HERE / "rail_worker_task_v3.py"), run_name="__main__")
