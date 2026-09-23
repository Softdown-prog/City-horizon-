"""Experimental MPFB2 probe for City Horizon Character Forge.

This script intentionally does not modify the canonical visitor pipeline. It is a
small capability test that runs inside Blender and reports whether MPFB2 can be
imported in the CH Blender environment. If available, it records candidate module
names and addon visibility so the next step can generate a single male SOUTH
proxy from a real human base mesh.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import bpy

CANDIDATES = (
    "mpfb",
    "mpfb2",
    "makehuman",
)


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    output = Path(argv[0] if argv else "out/character_forge/mpfb_probe.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    imported = {}
    for name in CANDIDATES:
        try:
            module = importlib.import_module(name)
            imported[name] = {
                "ok": True,
                "file": getattr(module, "__file__", None),
                "version": getattr(module, "__version__", None),
            }
        except Exception as exc:
            imported[name] = {"ok": False, "error": repr(exc)}

    addons = {}
    try:
        for mod in bpy.context.preferences.addons.keys():
            low = mod.lower()
            if "mpfb" in low or "makehuman" in low:
                addons[mod] = True
    except Exception as exc:
        addons["__error__"] = repr(exc)

    report = {
        "contract": "CH_CHARACTER_FORGE_MPFB_PROBE_V1",
        "blender": bpy.app.version_string,
        "python": sys.version,
        "imports": imported,
        "enabledAddons": addons,
        "mpfbAvailable": any(item.get("ok") for item in imported.values()) or bool(addons),
        "policy": "experimental_probe_only_no_runtime_promotion",
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    if not report["mpfbAvailable"]:
        raise SystemExit(42)


if __name__ == "__main__":
    main()
