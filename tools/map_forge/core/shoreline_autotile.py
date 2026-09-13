"""
Shoreline Autotile Manager for Map Forge.
Invokes native C++20 CH_SHORELINE_V1 autotiling engine via city_horizon_native.
"""

import json
from typing import Dict, Any, List
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.native_bridge import get_native_core


def run_shoreline_autotile(map_model: MapModel, min_x: int = -24, min_y: int = -24, max_x: int = 23, max_y: int = 23) -> Any:
    """
    Evaluates shoreline autotiling over the map model using C++20 CH_SHORELINE_V1 engine.
    Does not mutate raw scenario terrain semantics (LAND vs WATER).
    Returns native AutotileResult containing tile coordinates and ShorelineRecipe pieces.
    """
    ch = get_native_core()
    raw_json_str = map_model.raw_json
    doc = ch.MapDocument(raw_json_str)
    result = ch.evaluate_shoreline(doc, min_x, min_y, max_x, max_y)
    return result
