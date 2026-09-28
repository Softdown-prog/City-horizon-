"""Deterministic, bounded art author for the Forge's supported 2D families.

An agent can supply a structured brief or a short controlled-language prompt.
This module chooses a golden recipe, makes reproducible design decisions, then
hands the authored recipe to the existing render/audit workers. Unknown asset
families are reported explicitly; no model or image service is hidden here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image

from .workers import run_workers, validate_recipe

CONTRACT = "CH_2D_ART_BRIEF_V1"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
TEMPLATES = {
    "broadleaf": "park_tree_broadleaf_early_autumn_v1.json",
    "conifer": "pine_small_v1.json",
    "flower_bed": "flower_bed_01.json",
    "sign": "park_wayfinding_sign.json",
}
TERMS = {
    "conifer": ("pinheiro", "pine", "conifer", "abeto"),
    "broadleaf": ("broadleaf", "folhosa", "arvore", "tree", "decidua"),
    "flower_bed": ("canteiro", "flower bed", "flores", "flowerbed"),
    "sign": ("placa", "sinalizacao", "wayfinding sign", "sign"),
}
ALLOWED = {
    "broadleaf": {"season", "silhouette", "density", "palette", "seed"},
    "conifer": {"silhouette", "density", "palette", "seed"},
    "flower_bed": {"palette", "seed"},
    "sign": {"palette", "seed"},
}


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def interpret_prompt(prompt: str) -> dict:
    """Interpret only documented words; the result is visible and editable."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    words = _normalized(prompt)
    matches = [family for family, aliases in TERMS.items() if any(term in words for term in aliases)]
    if not matches:
        raise ValueError("unsupported subject; choose broadleaf, conifer, flower_bed or sign, or write a custom recipe")
    # 'Tree' can accompany 'pine'; an explicit specialist wins.
    family = "conifer" if "conifer" in matches else matches[0]
    if len(set(matches) - {"broadleaf", "conifer"}) or ("broadleaf" in matches and "conifer" not in matches and len(matches) > 1):
        raise ValueError("prompt mentions multiple asset families; submit one asset at a time")
    result = {"subject": family}
    if any(term in words for term in ("outono", "autumn", "amarel", "alaranj")):
        result["season"] = "early_autumn"
    if any(term in words for term in ("arredond", "rounded", "redonda")):
        result["silhouette"] = "rounded"
    elif any(term in words for term in ("larga", "wide", "broad")):
        result["silhouette"] = "wide"
    elif any(term in words for term in ("alta", "alto", "tall", "esguia", "esguio")):
        result["silhouette"] = "tall"
    if any(term in words for term in ("densa", "dense", "cheia")):
        result["density"] = "dense"
    elif any(term in words for term in ("rala", "sparse")):
        result["density"] = "sparse"
    return result


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError("art brief id must use lowercase letters, digits, _ or -")
    return value


def _apply_updates(target: dict, updates: dict, *, root: bool = True) -> None:
    """Patch authored fields that a template already defines, without changing contracts."""
    if not isinstance(updates, dict):
        raise ValueError("recipeUpdates must be an object")
    frozen = {"contract", "id", "camera", "rotation", "finishRecipe", "canvas", "anchor"}
    for key, value in updates.items():
        if key not in target or (root and key in frozen):
            raise ValueError(f"recipeUpdates cannot change unknown or frozen field {key!r}")
        if isinstance(target[key], dict):
            _apply_updates(target[key], value, root=False)
        elif type(value) is not type(target[key]):
            raise ValueError(f"recipeUpdates.{key} must keep its template type")
        else:
            target[key] = copy.deepcopy(value)


def author_recipe(brief: dict, examples: Path = EXAMPLES) -> tuple[dict, dict]:
    """Return recipe and a trace of decisions without writing or rendering."""
    if not isinstance(brief, dict) or brief.get("contract") != CONTRACT:
        raise ValueError(f"art brief requires {CONTRACT}")
    asset_id = _safe_id(brief.get("id"))
    parsed = interpret_prompt(brief["prompt"]) if "prompt" in brief else {}
    subject = brief.get("subject", parsed.get("subject"))
    if subject not in TEMPLATES and subject != "custom":
        raise ValueError(f"unsupported subject {subject!r}; available: {', '.join(TEMPLATES)}, custom")
    if parsed and parsed["subject"] != subject:
        raise ValueError("prompt subject and structured subject disagree")
    intent = {**parsed, **{key: brief[key] for key in ("season", "silhouette", "density", "palette", "seed") if key in brief}}
    unknown = set(intent) - ALLOWED.get(subject, {"seed"}) - {"subject"}
    if unknown:
        raise ValueError(f"{subject} does not support {', '.join(sorted(unknown))}; use a custom recipe")

    if subject == "custom":
        filename = brief.get("template")
        if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*\.json", filename):
            raise ValueError("custom subject requires a versioned JSON filename under examples/")
    else:
        filename = TEMPLATES[subject]
    recipe = copy.deepcopy(json.loads((examples / filename).read_text(encoding="utf-8")))
    recipe["id"] = asset_id
    if "seed" in intent:
        if type(intent["seed"]) is not int or not 0 <= intent["seed"] < 2**32:
            raise ValueError("seed must be a non-negative 32-bit integer")
        recipe["seed"] = intent["seed"]
    else:
        fingerprint = json.dumps({"id": asset_id, "intent": intent}, sort_keys=True, ensure_ascii=False)
        recipe["seed"] = int.from_bytes(hashlib.sha256(fingerprint.encode()).digest()[:4], "big")

    decisions = [f"template={filename}", f"seed={recipe['seed']}"]
    if subject == "broadleaf":
        season = intent.get("season", "early_autumn")
        if season not in ("early_autumn", "summer"):
            raise ValueError("broadleaf supports early_autumn or summer; other seasons need a new palette recipe")
        if season == "summer":
            recipe["palette"].update({
                "back_top": "#3C6542", "back_bottom": "#243E2B",
                "mid_top": "#60844D", "mid_bottom": "#37583A",
                "front_top": "#83A65C", "front_bottom": "#4F7342",
                "highlight": "#A5C774", "occlusion": "#263D2C",
            })
        decisions.append(f"season={season}")
        density = intent.get("density", "balanced")
        if density not in ("sparse", "balanced", "dense"):
            raise ValueError("density must be sparse, balanced or dense")
        recipe["broadleafStructure"]["masses"] = {"sparse": 35, "balanced": 48, "dense": 59}[density]
        decisions.append(f"density={density}")
        silhouette = intent.get("silhouette", "rounded")
        if silhouette not in ("rounded", "wide", "tall"):
            raise ValueError("silhouette must be rounded, wide or tall")
        recipe["broadleafStructure"]["radius"] = {
            "rounded": [68, 72], "wide": [78, 64], "tall": [60, 78],
        }[silhouette]
        decisions.append(f"silhouette={silhouette}")
    elif subject == "conifer":
        if "palette" in intent and intent["palette"] != "evergreen":
            raise ValueError("conifer currently supports only the evergreen palette")
        silhouette = intent.get("silhouette", "rounded")
        conifer_templates = {"rounded": "pine_small_v1.json", "tall": "pine_tall_v1.json", "wide": "pine_robust_v1.json"}
        if silhouette not in conifer_templates:
            raise ValueError("conifer silhouette must be rounded, wide or tall")
        if silhouette != "rounded":
            recipe = copy.deepcopy(json.loads((examples / conifer_templates[silhouette]).read_text(encoding="utf-8")))
            recipe["id"] = asset_id
            recipe["seed"] = intent.get("seed", int.from_bytes(hashlib.sha256(
                json.dumps({"id": asset_id, "intent": intent}, sort_keys=True).encode()).digest()[:4], "big"))
            decisions[0] = f"template={conifer_templates[silhouette]}"
        if "density" in intent:
            density = intent["density"]
            if density not in ("sparse", "balanced", "dense"):
                raise ValueError("density must be sparse, balanced or dense")
            # Tier geometry stays stable; raster density is the safe variation.
            factor = {"sparse": .70, "balanced": 1.0, "dense": 1.28}[density]
            for key in ("shadowDabs", "highlightDabs", "needleStrokes", "finalGrain", "finalNeedles"):
                if key in recipe.get("raster", {}):
                    recipe["raster"][key] = round(recipe["raster"][key] * factor)
        decisions.append(f"silhouette={silhouette}")
    else:
        if "palette" in intent:
            raise ValueError(f"{subject} palette variants require a custom recipe or the draw-recipe palette CLI")
    if "palette" in intent and subject == "broadleaf":
        raise ValueError("choose broadleaf colors with season, or author a custom palette recipe")

    if "recipeUpdates" in brief:
        _apply_updates(recipe, brief["recipeUpdates"])
        decisions.append("recipeUpdates=explicit")

    recipe["authorIntent"] = {key: value for key, value in intent.items() if key != "subject"}
    validate_recipe(recipe)
    return recipe, {"subject": subject, "decisions": decisions, "interpreted": intent,
                    "freeTextPartiallyInterpreted": bool(brief.get("prompt")), "artApproved": False}


def _mechanical_review(recipe: dict, png: Path) -> dict:
    """Surface actionable measurements, never pretend to approve aesthetics."""
    with Image.open(png) as source:
        image = source.convert("RGBA")
    bounds = image.getchannel("A").getbbox()
    result = {"opaqueBounds": list(bounds), "status": "human_visual_review_required", "observations": []}
    if recipe.get("crownStyle") == "broadleaf":
        center = recipe["broadleafStructure"]["center"]
        radius = recipe["broadleafStructure"]["radius"]
        top = max(0, round(center[1] - radius[1] * .8))
        bottom = min(image.height, round(center[1] + radius[1] * .8))
        alpha = image.getchannel("A")
        occupied = [any(alpha.getpixel((x, y)) > 160 for x in range(max(0, center[0] - radius[0]),
                         min(image.width, center[0] + radius[0]))) for y in range(top, bottom)]
        longest = max((len(part) for part in "".join("1" if v else "0" for v in occupied).split("1")), default=0)
        result["canopyEmptyRowRunPx"] = longest
        if longest >= 5:
            result["observations"].append("canopy has a horizontal gap; inspect crown continuity")
    return result


def run_art_author(brief: dict, output_root: Path, examples: Path = EXAMPLES) -> dict:
    recipe, author = author_recipe(brief, examples)
    folder = output_root / recipe["id"]
    folder.mkdir(parents=True, exist_ok=True)
    recipe_path = folder / "authored_recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = run_workers(recipe_path, output_root)
    report = {"contract": "CH_2D_ART_AUTHOR_REPORT_V1", "id": recipe["id"],
              "author": author, "recipe": str(recipe_path), "render": result,
              "critique": _mechanical_review(recipe, Path(result["png"])),
              "status": "review_ready", "artApproved": False, "runtimePromotion": False}
    report_path = folder / "art_author_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"report": str(report_path), "recipe": str(recipe_path), "png": result["png"],
            "review": result["review"], "isometricReview": result["isometricReview"],
            "status": report["status"]}
