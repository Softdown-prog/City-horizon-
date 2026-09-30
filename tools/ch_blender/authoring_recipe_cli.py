#!/usr/bin/env python3
"""Validate CH_AUTHORING_RECIPE_V1 without launching Blender."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CONTRACT = "CH_AUTHORING_RECIPE_V1"
KINDS = {
    "soft_form": ("location", "scale"),
    "tapered_segment": ("start", "end", "radiusStart", "radiusEnd"),
    "loft_form": ("location", "profiles"),
    "rounded_box": ("location", "size"),
    "curve_tube": ("points", "radius"),
    "torus": ("location", "majorRadius", "minorRadius"),
}


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("contract") != CONTRACT:
        errors.append(f"contract must be {CONTRACT}")
    if not isinstance(data.get("assetId"), str) or not data.get("assetId"):
        errors.append("assetId must be a non-empty string")

    materials = data.get("materials")
    if not isinstance(materials, dict):
        errors.append("materials must be an object")
        materials = {}
    else:
        for key, spec in materials.items():
            if not isinstance(spec, dict):
                errors.append(f"material {key}: must be an object")
                continue
            color = spec.get("color")
            if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
                errors.append(f"material {key}: color must be #RRGGBB")

    parts = data.get("parts")
    if not isinstance(parts, list):
        errors.append("parts must be an array")
        return errors

    ids: set[str] = set()
    for index, part in enumerate(parts):
        prefix = f"parts[{index}]"
        if not isinstance(part, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        part_id = part.get("id")
        if not isinstance(part_id, str) or not part_id:
            errors.append(f"{prefix}: id must be a non-empty string")
        elif part_id in ids:
            errors.append(f"{prefix}: duplicate id {part_id!r}")
        else:
            ids.add(part_id)

        kind = part.get("type")
        if kind not in KINDS:
            errors.append(f"{prefix}: unsupported type {kind!r}")
            continue
        for field in KINDS[kind]:
            if field not in part:
                errors.append(f"{prefix} ({part_id}): missing {field}")

        if kind == "loft_form":
            profiles = part.get("profiles")
            if not isinstance(profiles, list) or len(profiles) < 2:
                errors.append(f"{prefix} ({part_id}): profiles must contain at least two entries")
            else:
                previous_z = None
                for profile_index, profile in enumerate(profiles):
                    pp = f"{prefix} ({part_id}) profiles[{profile_index}]"
                    if not isinstance(profile, dict):
                        errors.append(f"{pp}: must be an object")
                        continue
                    for field in ("z", "width", "depth"):
                        if field not in profile or not isinstance(profile[field], (int, float)):
                            errors.append(f"{pp}: {field} must be numeric")
                    if all(isinstance(profile.get(field), (int, float)) for field in ("z", "width", "depth")):
                        if float(profile["width"]) <= 0 or float(profile["depth"]) <= 0:
                            errors.append(f"{pp}: width/depth must be > 0")
                        z = float(profile["z"])
                        if previous_z is not None and z <= previous_z:
                            errors.append(f"{pp}: z values must be strictly increasing")
                        previous_z = z

        material = part.get("material")
        if material is not None and material not in materials:
            errors.append(f"{prefix} ({part_id}): unknown material {material!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    data = json.loads(args.recipe.read_text(encoding="utf-8"))
    errors = validate(data)
    report = {
        "contract": "CH_AUTHORING_RECIPE_VALIDATION_V1",
        "recipe": str(args.recipe),
        "status": "error" if errors else "ok",
        "errors": errors,
        "partCount": len(data.get("parts", [])) if isinstance(data.get("parts"), list) else 0,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
