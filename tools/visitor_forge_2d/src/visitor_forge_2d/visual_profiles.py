"""Versioned visual-profile support for Visitor Forge 2D art authoring."""
from __future__ import annotations

import copy
import json
from pathlib import Path

CONTRACT = "CH_2D_TREE_VISUAL_REFERENCE_V1"
DEFAULT_LIBRARY = "reference_profiles/tree_visual_profiles_v1.json"


def load_visual_profiles(examples: Path, library: str = DEFAULT_LIBRARY) -> dict:
    path = examples / library
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CONTRACT or not isinstance(payload.get("profiles"), dict):
        raise ValueError(f"visual profile library must declare {CONTRACT}")
    return payload["profiles"]


def resolve_visual_profile(examples: Path, name: str) -> dict:
    if not isinstance(name, str) or not name:
        raise ValueError("visualProfile must be a non-empty string")
    profiles = load_visual_profiles(examples)
    if name not in profiles:
        raise ValueError(f"unknown visualProfile {name!r}; choose {', '.join(sorted(profiles))}")
    profile = copy.deepcopy(profiles[name])
    authoring = profile.get("authoring")
    if not isinstance(authoring, dict) or authoring.get("subject") not in {"broadleaf", "custom"}:
        raise ValueError(f"visualProfile {name!r} is missing supported authoring metadata")
    return profile


def apply_profile_defaults(brief: dict, profile: dict) -> dict:
    """Return a copy of the brief with profile defaults filled, never overriding explicit intent."""
    authored = copy.deepcopy(brief)
    defaults = profile["authoring"]
    if "subject" not in authored:
        authored["subject"] = defaults["subject"]
    elif authored["subject"] != defaults["subject"]:
        raise ValueError(
            f"visualProfile requires subject {defaults['subject']!r}, got {authored['subject']!r}"
        )
    for key in ("species", "style", "leaf_detail", "season", "silhouette", "density", "palette", "template"):
        if key not in authored and key in defaults:
            authored[key] = copy.deepcopy(defaults[key])
    return authored
