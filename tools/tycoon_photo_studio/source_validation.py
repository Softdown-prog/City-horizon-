"""Validate actual bake inputs before writing any postprocessed candidate pixels."""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image
from render_geometry import require_same_aspect, studio_fingerprint


def _size(value, field):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(type(v) is not int or v <= 0 for v in value):
        raise ValueError(f"CH_SOURCE_INVALID: {field} requires two positive pixel dimensions")
    return tuple(value)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_sources(directory: Path, metadata: dict, preset: dict, *, character=False):
    """Check topology, aspect, alpha and actual pixel sizes; shadow-only PNGs may be empty."""
    directory = directory.resolve()
    contract = "TYCOON_CHARACTER_BAKE_V1" if character else "TYCOON_ASSET_BAKE_V1"
    if metadata.get("contract") != contract:
        raise ValueError(f"CH_SOURCE_INVALID: expected {contract}")
    if metadata.get("studioPreset") != preset.get("id"):
        raise ValueError("CH_SOURCE_INVALID: source/preset studio identity differs")
    if metadata.get("studioFingerprint") and metadata["studioFingerprint"] != studio_fingerprint(preset):
        raise ValueError("CH_SOURCE_INVALID: source/preset lighting or color settings differ")
    resolution = _size(metadata.get("renderResolution"), "renderResolution")
    final = _size(metadata.get("finalResolution", preset["render"]["finalResolution"]), "finalResolution")
    require_same_aspect(resolution, final)
    order = metadata.get("directionOrder")
    if not isinstance(order, list) or not order or not all(isinstance(d, str) for d in order) or len(set(order)) != len(order):
        raise ValueError("CH_SOURCE_INVALID: direction order is missing or duplicated")
    if not character and order != ["south", "east", "west", "north"]:
        raise ValueError("CH_SOURCE_INVALID: canonical four-direction order changed")
    directions = metadata.get("directions", [])
    if not isinstance(directions, list) or not all(isinstance(d, dict) for d in directions) or [d.get("id") for d in directions] != order:
        raise ValueError("CH_SOURCE_INVALID: direction records must match the declared order exactly")
    frame_count = metadata.get("animation", {}).get("frameCount") if character else None
    if character and (type(frame_count) is not int or frame_count <= 0):
        raise ValueError("CH_SOURCE_INVALID: animation frameCount must be positive")
    seen = set()
    for direction in directions:
        frames = direction.get("frames", []) if character else [direction]
        if character and (not isinstance(frames, list) or not all(isinstance(f, dict) for f in frames) or
                          any(type(frame.get("frame")) is not int for frame in frames) or
                          [frame.get("frame") for frame in frames] != list(range(frame_count))):
            raise ValueError(f"CH_SOURCE_INVALID: {direction['id']} frames are missing, duplicated or reordered")
        for frame in frames:
            if character and (not _number(frame.get("phase")) or not 0 <= frame["phase"] < 1):
                raise ValueError("CH_SOURCE_INVALID: animation phase must be finite and within one cycle")
            pivot = frame.get("groundOriginSourcePx", {})
            if not isinstance(pivot, dict) or not all(_number(pivot.get(key)) for key in ("x", "y")):
                raise ValueError("CH_SOURCE_INVALID: projected ground pivot must be finite")
            roles = ["colorSource", "shadowSource"]
            if (metadata.get("colorMask") or {}).get("enabled"):
                roles.append("maskSource")
            for role in roles:
                name = frame.get(role)
                if not isinstance(name, str) or not name:
                    raise ValueError(f"CH_SOURCE_INVALID: missing {role}")
                path = (directory / name).resolve()
                if not path.is_relative_to(directory) or not path.is_file():
                    raise ValueError(f"CH_SOURCE_INVALID: {role} must be a file inside the bake source directory")
                if path in seen:
                    raise ValueError(f"CH_SOURCE_INVALID: a source PNG is reused across passes/directions/frames: {name}")
                seen.add(path)
                with Image.open(path) as image:
                    if image.format != "PNG" or image.mode != "RGBA" or image.size != resolution:
                        raise ValueError(f"CH_SOURCE_INVALID: {name} must be an RGBA PNG of declared size {resolution}")
                    image.load()
                    if role == "colorSource" and image.getchannel("A").getbbox() is None:
                        raise ValueError(f"CH_SOURCE_INVALID: {name} contains no visible asset")
    return final
