"""
Native Bridge for City Horizon Map Forge.
Enforces strict single-authority C++20 core loading via city_horizon_native.pyd.
"""

import sys
import os

MAP_FORGE_STRICT_NATIVE = True

_NATIVE_MODULE = None

def _try_load_native():
    global _NATIVE_MODULE
    if _NATIVE_MODULE is not None:
        return _NATIVE_MODULE

    # Known binary search paths
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    search_paths = [
        os.path.join(repo_root, "build", "map_forge_native", "Debug"),
        os.path.join(repo_root, "build", "map_forge_native", "Release"),
        os.path.join(repo_root, "build", "map_forge_native"),
        os.path.join(repo_root, "tools", "map_forge", "native"),
    ]
    dll_paths = search_paths + [
        os.path.join(repo_root, "build", "Debug"),
        os.path.join(repo_root, "build", "Release"),
        os.path.join(repo_root, "build", "_deps", "sdl3-build", "Debug"),
        os.path.join(repo_root, "build", "_deps", "sdl3-build", "Release"),
    ]

    for path in search_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

    if hasattr(os, "add_dll_directory"):
        for path in dll_paths:
            if os.path.exists(path):
                try:
                    os.add_dll_directory(path)
                except Exception:
                    pass

    try:
        import city_horizon_native as ch
        _NATIVE_MODULE = ch
        return ch
    except ImportError as e:
        if MAP_FORGE_STRICT_NATIVE:
            raise RuntimeError(
                f"MAP FORGE NATIVE CORE UNAVAILABLE\n"
                f"city_horizon_native could not be loaded ({e}).\n"
                f"Editing/validation disabled."
            ) from e
        return None

def get_native_core():
    """Returns the loaded city_horizon_native module or raises in strict mode."""
    return _try_load_native()
