"""Declarative CH Blender authoring recipe executor."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from mathutils import Vector

from .character import CharacterAuthoring

CONTRACT = "CH_AUTHORING_RECIPE_V1"


def load_recipe(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}, got {data.get('contract')!r}")
    if not data.get("assetId"):
        raise RuntimeError("Authoring recipe requires assetId")
    if not isinstance(data.get("parts"), list):
        raise RuntimeError("Authoring recipe requires parts[]")
    return data


def _vec(value, points: Mapping[str, Vector]) -> Vector:
    if isinstance(value, str):
        if value not in points:
            raise KeyError(f"Unknown recipe point {value!r}")
        return points[value].copy()
    if isinstance(value, Sequence) and len(value) == 3:
        return Vector(tuple(float(v) for v in value))
    raise TypeError(f"Expected point name or xyz vector, got {value!r}")


def _material(builder: CharacterAuthoring, materials: dict, key: str):
    if key not in materials:
        raise KeyError(f"Unknown recipe material {key!r}")
    spec = materials[key]
    return builder.material(
        key,
        spec["color"],
        roughness=float(spec.get("roughness", 0.82)),
        specular=float(spec.get("specular", 0.16)),
        metallic=float(spec.get("metallic", 0.0)),
    )


def execute_recipe(recipe: dict, *, points: Mapping[str, Vector] | None = None) -> CharacterAuthoring:
    """Build one physical asset from a validated high-level recipe."""
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    points = points or {}
    builder = CharacterAuthoring(recipe["assetId"])
    materials = recipe.get("materials", {})

    for part in recipe.get("parts", []):
        key = part["id"]
        kind = part["type"]
        mat = _material(builder, materials, part["material"]) if part.get("material") else None

        if kind == "soft_form":
            builder.soft(
                key,
                _vec(part["location"], points),
                part["scale"],
                mat,
                rotation=tuple(part.get("rotation", (0.0, 0.0, 0.0))),
                segments=int(part.get("segments", 28)),
                rings=int(part.get("rings", 18)),
            )
        elif kind == "tapered_segment":
            builder.segment(
                key,
                _vec(part["start"], points),
                _vec(part["end"], points),
                float(part["radiusStart"]),
                float(part["radiusEnd"]),
                mat,
                vertices=int(part.get("vertices", 24)),
            )
        elif kind == "rounded_box":
            builder.box(
                key,
                _vec(part["location"], points),
                part["size"],
                mat,
                rotation=tuple(part.get("rotation", (0.0, 0.0, 0.0))),
                bevel=float(part.get("bevel", 0.04)),
                bevel_segments=int(part.get("bevelSegments", 3)),
            )
        elif kind == "curve_tube":
            builder.tube(
                key,
                [_vec(value, points) for value in part["points"]],
                float(part["radius"]),
                mat,
                resolution=int(part.get("resolution", 2)),
                bevel_resolution=int(part.get("bevelResolution", 3)),
                cyclic=bool(part.get("cyclic", False)),
            )
        elif kind == "torus":
            builder.ring(
                key,
                _vec(part["location"], points),
                float(part["majorRadius"]),
                float(part["minorRadius"]),
                mat,
                rotation=tuple(part.get("rotation", (0.0, 0.0, 0.0))),
            )
        else:
            raise RuntimeError(f"Unsupported CH authoring part type {kind!r}")

    return builder
