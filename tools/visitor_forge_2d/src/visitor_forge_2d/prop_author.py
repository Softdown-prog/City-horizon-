"""High-level deterministic prop author for Visitor Forge 2D.

This is the first scene-authoring layer above raw Scene Composer recipes.  A
small structured brief or controlled-language prompt chooses an approved scene
grammar, derives a stable seed and adjusts bounded material wear.  It is meant
to grow into the generic author for boats, piers, signs and other 2D props while
keeping every decision explicit and reproducible.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .workers import run_workers, validate_recipe

CONTRACT = "CH_2D_PROP_BRIEF_V1"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
TEMPLATES = {
    "rowboat": "prop_rowboat_scene_v4.json",
    "pier": "prop_pier_scene_v4.json",
    "sign": "park_wayfinding_sign.json",
}
ALIASES = {
    "rowboat": ("barco", "barquinho", "boat", "rowboat", "bote"),
    "pier": ("pier", "pier", "píer", "cais", "doca", "dock"),
    "sign": ("placa", "sinalizacao", "sinalização", "sign", "wayfinding"),
}
CONDITIONS = {
    "pristine": ("novo", "nova", "limpo", "limpa", "pristine", "new", "clean"),
    "used": ("usado", "usada", "uso", "used", "worn"),
    "weathered": ("envelhecido", "envelhecida", "gasto", "gasta", "weathered", "aged", "rustico", "rústico"),
}


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError("prop brief id must use lowercase letters, digits, _ or -")
    return value


def interpret_prop_prompt(prompt: str) -> dict:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    text = _normalized(prompt)
    archetypes = [name for name, aliases in ALIASES.items() if any(_normalized(alias) in text for alias in aliases)]
    if len(archetypes) != 1:
        if not archetypes:
            raise ValueError("unsupported prop; choose rowboat, pier or sign")
        raise ValueError("prompt mentions multiple prop archetypes; author one asset at a time")
    result = {"archetype": archetypes[0]}
    conditions = [name for name, aliases in CONDITIONS.items() if any(_normalized(alias) in text for alias in aliases)]
    if len(conditions) > 1:
        raise ValueError("prompt mentions conflicting prop conditions")
    if conditions:
        result["condition"] = conditions[0]
    return result


def _condition_scene(recipe: dict, condition: str) -> None:
    if condition not in ("pristine", "used", "weathered"):
        raise ValueError("condition must be pristine, used or weathered")
    if recipe.get("contract") != "CH_2D_SCENE_RECIPE_V4":
        if condition != "pristine":
            raise ValueError("non-scene prop templates currently support only pristine condition")
        return
    finish = recipe.setdefault("finish", {})
    regions = recipe.setdefault("finishRegions", [])
    if condition == "pristine":
        finish["surfaceVariation"] = min(float(finish.get("surfaceVariation", 0.04)), 0.035)
        finish["brushStamps"] = min(int(finish.get("brushStamps", 12)), 10)
        for region in regions:
            region["opacity"] = round(min(float(region.get("opacity", 0.1)), 0.07), 3)
            region["stamps"] = max(0, round(int(region.get("stamps", 12)) * 0.55))
    elif condition == "weathered":
        finish["surfaceVariation"] = round(min(0.18, float(finish.get("surfaceVariation", 0.06)) * 1.45), 3)
        finish["brushStamps"] = min(120, max(int(finish.get("brushStamps", 18)), 34))
        for region in regions:
            region["opacity"] = round(min(0.30, float(region.get("opacity", 0.1)) * 1.45), 3)
            region["stamps"] = min(120, max(1, round(int(region.get("stamps", 12)) * 1.35)))
    # 'used' deliberately preserves the template's authored baseline.


def author_prop_recipe(brief: dict, examples: Path = EXAMPLES) -> tuple[dict, dict]:
    if not isinstance(brief, dict) or brief.get("contract") != CONTRACT:
        raise ValueError(f"prop brief requires {CONTRACT}")
    asset_id = _safe_id(brief.get("id"))
    parsed = interpret_prop_prompt(brief["prompt"]) if "prompt" in brief else {}
    archetype = brief.get("archetype", parsed.get("archetype"))
    if archetype not in TEMPLATES:
        raise ValueError(f"unsupported prop archetype {archetype!r}; choose {', '.join(TEMPLATES)}")
    if parsed and parsed["archetype"] != archetype:
        raise ValueError("prompt archetype and structured archetype disagree")
    condition = brief.get("condition", parsed.get("condition", "used" if archetype in ("rowboat", "pier") else "pristine"))
    if "condition" in parsed and "condition" in brief and parsed["condition"] != brief["condition"]:
        raise ValueError("prompt condition and structured condition disagree")
    unknown = set(brief) - {"contract", "id", "prompt", "archetype", "condition", "seed"}
    if unknown:
        raise ValueError(f"prop brief contains unsupported fields: {', '.join(sorted(unknown))}")

    filename = TEMPLATES[archetype]
    recipe = copy.deepcopy(json.loads((examples / filename).read_text(encoding="utf-8")))
    recipe["id"] = asset_id
    if "seed" in brief:
        seed = brief["seed"]
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("seed must be a non-negative 32-bit integer")
    else:
        fingerprint = json.dumps({"id": asset_id, "archetype": archetype, "condition": condition}, sort_keys=True)
        seed = int.from_bytes(hashlib.sha256(fingerprint.encode()).digest()[:4], "big")
    recipe["seed"] = seed
    _condition_scene(recipe, condition)
    recipe["authorIntent"] = {"archetype": archetype, "condition": condition}
    validate_recipe(recipe)
    report = {
        "contract": "CH_2D_PROP_AUTHOR_REPORT_V1",
        "id": asset_id,
        "archetype": archetype,
        "condition": condition,
        "template": filename,
        "seed": seed,
        "artApproved": False,
        "runtimePromotion": False,
    }
    return recipe, report


def run_prop_author(brief: dict, output_root: Path, examples: Path = EXAMPLES) -> dict:
    recipe, author = author_prop_recipe(brief, examples)
    folder = output_root / recipe["id"]
    folder.mkdir(parents=True, exist_ok=True)
    recipe_path = folder / "authored_prop_recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = run_workers(recipe_path, output_root)
    report = {**author, "render": result, "status": "review_ready"}
    report_path = folder / "prop_author_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"report": str(report_path), "recipe": str(recipe_path), "png": result["png"],
            "review": result["review"], "isometricReview": result["isometricReview"],
            "status": "review_ready"}
