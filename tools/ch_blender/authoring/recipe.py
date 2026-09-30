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


def _offset(value) -> Vector:
    if value is None:
        return Vector((0.0, 0.0, 0.0))
    if isinstance(value, Sequence) and len(value) == 3:
        return Vector(tuple(float(v) for v in value))
    raise TypeError(f"Expected xyz offset, got {value!r}")


def _vec(value, points: Mapping[str, Vector]) -> Vector:
    """Resolve absolute xyz, rig point name, or {point, offset}."""
    if isinstance(value, str):
        if value not in points:
            raise KeyError(f"Unknown recipe point {value!r}")
        return points[value].copy()
    if isinstance(value, Mapping):
        name = value.get("point")
        if not isinstance(name, str) or name not in points:
            raise KeyError(f"Unknown recipe point {name!r}")
        return points[name].copy() + _offset(value.get("offset"))
    if isinstance(value, Sequence) and len(value) == 3:
        return Vector(tuple(float(v) for v in value))
    raise TypeError(f"Expected point name, point+offset, or xyz vector, got {value!r}")


def _profile_value(profile: Mapping[str, object], key: str) -> float:
    value = float(profile.get(key, 1.0))
    if not 0.55 <= value <= 1.45:
        raise ValueError(f"proportions.{key} must be in [0.55, 1.45], got {value}")
    return value


def apply_proportion_profile(
    recipe: Mapping[str, object],
    points: Mapping[str, Vector],
) -> dict[str, Vector]:
    """Apply semantic character proportions while keeping feet planted.

    ``legLength`` scales hip/knee/ankle from each foot so the ground contact is
    unchanged. The resulting average hip shift moves pelvis/torso with the legs.
    ``torsoLength`` scales upper-body landmarks from the shifted pelvis and
    ``armLength`` scales elbow/hand from each transformed shoulder. Defaults are
    1.0, so existing assets are unchanged until they opt in.
    """
    profile = recipe.get("proportions", {})
    if not isinstance(profile, Mapping) or not profile:
        return {name: point.copy() for name, point in points.items()}

    leg_length = _profile_value(profile, "legLength")
    torso_length = _profile_value(profile, "torsoLength")
    arm_length = _profile_value(profile, "armLength")

    out = {name: point.copy() for name, point in points.items()}
    old_hip_mid = (points["hip_L"] + points["hip_R"]) * 0.5

    for label in ("L", "R"):
        foot = points[f"foot_{label}"]
        for joint in ("ankle", "knee", "hip"):
            key = f"{joint}_{label}"
            out[key] = foot + (points[key] - foot) * leg_length

    new_hip_mid = (out["hip_L"] + out["hip_R"]) * 0.5
    hip_shift = new_hip_mid - old_hip_mid
    out["pelvis"] = points["pelvis"] + hip_shift

    for name in ("chest", "neck", "head", "head_top"):
        out[name] = out["pelvis"] + (points[name] - points["pelvis"]) * torso_length

    for label in ("L", "R"):
        shoulder_key = f"shoulder_{label}"
        old_shoulder = points[shoulder_key]
        out[shoulder_key] = out["pelvis"] + (old_shoulder - points["pelvis"]) * torso_length
        for joint in ("elbow", "hand"):
            key = f"{joint}_{label}"
            out[key] = out[shoulder_key] + (points[key] - old_shoulder) * arm_length

    return out


def _material(
    builder: CharacterAuthoring,
    materials: dict,
    key: str,
    material_overrides: Mapping[str, str],
):
    if key not in materials:
        raise KeyError(f"Unknown recipe material {key!r}")
    spec = materials[key]
    color = material_overrides.get(key, spec["color"])
    return builder.material(
        key,
        color,
        roughness=float(spec.get("roughness", 0.82)),
        specular=float(spec.get("specular", 0.16)),
        metallic=float(spec.get("metallic", 0.0)),
    )


def _blob_elements(part: dict, points: Mapping[str, Vector]) -> list[dict]:
    result: list[dict] = []
    for item in part["elements"]:
        resolved = {
            "location": _vec(item["location"], points),
            "radius": float(item["radius"]),
        }
        if "stiffness" in item:
            resolved["stiffness"] = float(item["stiffness"])
        result.append(resolved)
    return result


def execute_recipe(
    recipe: dict,
    *,
    points: Mapping[str, Vector] | None = None,
    material_overrides: Mapping[str, str] | None = None,
) -> CharacterAuthoring:
    """Build one physical asset from a validated high-level recipe."""
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    points = points or {}
    material_overrides = material_overrides or {}
    builder = CharacterAuthoring(recipe["assetId"])
    materials = recipe.get("materials", {})

    for part in recipe.get("parts", []):
        key = part["id"]
        kind = part["type"]
        mat = (
            _material(builder, materials, part["material"], material_overrides)
            if part.get("material")
            else None
        )

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
                round_caps=bool(part.get("roundCaps", True)),
            )
        elif kind == "loft_form":
            builder.loft(
                key,
                _vec(part["location"], points),
                part["profiles"],
                mat,
                rotation=tuple(part.get("rotation", (0.0, 0.0, 0.0))),
                segments=int(part.get("segments", 28)),
                cap_ends=bool(part.get("capEnds", True)),
            )
        elif kind == "blob_cluster":
            builder.blob(
                key,
                _blob_elements(part, points),
                mat,
                resolution=float(part.get("resolution", 0.035)),
                render_resolution=float(part.get("renderResolution", 0.018)),
                threshold=float(part.get("threshold", 0.60)),
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
