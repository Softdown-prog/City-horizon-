"""Plain-Python entrypoint for the loading splash illustration renderer.

The renderer also runs under Blender and therefore accepts arguments after `--`.
This wrapper preserves that contract while allowing the lightweight GitHub
workflow to invoke it with ordinary Python arguments.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("build_loading_splash_illustration_2d.py")

if "--" not in sys.argv:
    sys.argv.insert(1, "--")

runpy.run_path(str(SCRIPT), run_name="__main__")
