#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"CH_RASPADINHA_PLACEMENT_PATCH_MISMATCH: {path}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_exact_count(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"CH_RASPADINHA_PLACEMENT_PATCH_MISMATCH: {path}: expected {expected} matches, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


header = ROOT / "src/building_system.h"
replace_once(
    header,
    '''    bool requires_road_access = false;\n    RoadAccessMode road_access_mode = RoadAccessMode::any_perimeter;''',
    '''    bool requires_road_access = false;\n    // Small roadside/pathside props may accept either a road edge or a path\n    // edge while still occupying their own grass tile. This is independent\n    // from the stricter building entrance road contract above.\n    bool requires_road_or_path_access = false;\n    bool grass_only = false;\n    RoadAccessMode road_access_mode = RoadAccessMode::any_perimeter;''',
)

source = ROOT / "src/building_system.cpp"
replace_once(
    source,
    '''    definition.requires_road_access = json_bool(json, "requiresRoadAccess").value_or(false);\n    definition.footprint_width = json_number<int>(*footprint, "width").value_or(0);''',
    '''    definition.requires_road_access = json_bool(json, "requiresRoadAccess").value_or(false);\n    definition.requires_road_or_path_access = json_bool(json, "requiresRoadOrPathAccess").value_or(false);\n    definition.grass_only = json_bool(json, "grassOnly").value_or(false);\n    definition.footprint_width = json_number<int>(*footprint, "width").value_or(0);''',
)

main = ROOT / "src/main.cpp"
replace_once(
    main,
    '''[[nodiscard]] const char* placement_failure_text(PlacementFailure failure);\n\nstruct BuildingPlacementValidation {''',
    '''[[nodiscard]] bool building_has_required_edge_access(const BuildingDefinition& definition,\n                                                        const BuildingRotation rotation,\n                                                        const int tile_x, const int tile_y,\n                                                        const RoadManager& roads,\n                                                        const SidewalkManager& sidewalks) {\n    if (!definition.requires_road_or_path_access) {\n        return roads.has_required_road_access(definition, tile_x, tile_y, rotation);\n    }\n\n    const BuildingFootprint footprint = rotated_footprint(definition, rotation);\n    const auto edge_is_accessible = [&](const int x, const int y) {\n        return roads.is_road(x, y) || sidewalks.is_sidewalk(x, y);\n    };\n    for (int x = 0; x < footprint.width; ++x) {\n        if (edge_is_accessible(tile_x + x, tile_y - 1) ||\n            edge_is_accessible(tile_x + x, tile_y + footprint.height)) {\n            return true;\n        }\n    }\n    for (int y = 0; y < footprint.height; ++y) {\n        if (edge_is_accessible(tile_x - 1, tile_y + y) ||\n            edge_is_accessible(tile_x + footprint.width, tile_y + y)) {\n            return true;\n        }\n    }\n    return false;\n}\n\n[[nodiscard]] bool building_footprint_is_grass(const BuildingDefinition& definition,\n                                                const BuildingRotation rotation,\n                                                const int tile_x, const int tile_y,\n                                                const ch::MapDocument* map_document) {\n    if (!definition.grass_only || map_document == nullptr) return true;\n    const BuildingFootprint footprint = rotated_footprint(definition, rotation);\n    for (int y = 0; y < footprint.height; ++y) {\n        for (int x = 0; x < footprint.width; ++x) {\n            const auto terrain = map_document->get_terrain_at(tile_x + x, tile_y + y);\n            // The runtime's implicit base terrain is grass. Explicit terrain\n            // entries must identify themselves as grass; water, sand and\n            // unresolved legacy terrain fail closed for grass-only props.\n            if (terrain && terrain->terrain_definition != "grass") return false;\n        }\n    }\n    return true;\n}\n\n[[nodiscard]] const char* placement_failure_text(PlacementFailure failure);\n\nstruct BuildingPlacementValidation {''',
)

replace_once(
    main,
    '''    bool on_owned_land = false;\n    bool has_road_access = false;\n    bool has_power = false;''',
    '''    bool on_owned_land = false;\n    bool on_allowed_terrain = true;\n    bool accepts_path_access = false;\n    bool has_road_access = false;\n    bool has_power = false;''',
)

replace_once(
    main,
    '''        return failure == PlacementFailure::none && affordable && !on_road && !on_sidewalk && !on_farm &&\n               on_owned_land && has_road_access;''',
    '''        return failure == PlacementFailure::none && affordable && !on_road && !on_sidewalk && !on_farm &&\n               on_owned_land && on_allowed_terrain && has_road_access;''',
)

replace_once(
    main,
    '''    const BuildingManager& buildings, const RoadManager& roads, const LandManager& lands,\n    const SidewalkManager& sidewalks, const FarmingSystem& farming, const CityEconomy& economy, const PowerSystem& power) {\n    return {\n        buildings.validate(definition, tile_x, tile_y, rotation),\n        economy.can_afford(definition.build_cost),\n        building_overlaps_road(definition, rotation, tile_x, tile_y, roads),\n        building_overlaps_sidewalk(definition, rotation, tile_x, tile_y, sidewalks),\n        building_overlaps_farm(definition, rotation, tile_x, tile_y, farming),\n        building_is_on_owned_land(definition, rotation, tile_x, tile_y, lands),\n        roads.has_required_road_access(definition, tile_x, tile_y, rotation),\n        power.can_support(definition),\n    };\n}''',
    '''    const BuildingManager& buildings, const RoadManager& roads, const LandManager& lands,\n    const SidewalkManager& sidewalks, const FarmingSystem& farming, const CityEconomy& economy, const PowerSystem& power,\n    const ch::MapDocument* map_document) {\n    return {\n        buildings.validate(definition, tile_x, tile_y, rotation),\n        economy.can_afford(definition.build_cost),\n        building_overlaps_road(definition, rotation, tile_x, tile_y, roads),\n        building_overlaps_sidewalk(definition, rotation, tile_x, tile_y, sidewalks),\n        building_overlaps_farm(definition, rotation, tile_x, tile_y, farming),\n        building_is_on_owned_land(definition, rotation, tile_x, tile_y, lands),\n        building_footprint_is_grass(definition, rotation, tile_x, tile_y, map_document),\n        definition.requires_road_or_path_access,\n        building_has_required_edge_access(definition, rotation, tile_x, tile_y, roads, sidewalks),\n        power.can_support(definition),\n    };\n}''',
)

replace_once(
    main,
    '''    if (!validation.has_road_access) {\n        return "ROAD AT ENTRANCE REQUIRED";\n    }''',
    '''    if (!validation.on_allowed_terrain) {\n        return "REQUIRES GRASS TILE";\n    }\n    if (!validation.has_road_access) {\n        return validation.accepts_path_access ? "ROAD OR PATH ADJACENCY REQUIRED" : "ROAD AT ENTRANCE REQUIRED";\n    }''',
)

replace_exact_count(
    main,
    '''buildings, roads, lands, sidewalks, farming, economy, power);''',
    '''buildings, roads, lands, sidewalks, farming, economy, power, active_map_doc ? &*active_map_doc : nullptr);''',
    3,
)

replace_once(
    main,
    '''    std::string label = definition.requires_road_access ? "RUA OBRIGATORIA" : "SEM RUA";''',
    '''    std::string label = definition.requires_road_or_path_access\n        ? "RUA OU CAMINHO ADJACENTE"\n        : (definition.requires_road_access ? "RUA OBRIGATORIA" : "SEM RUA");\n    if (definition.grass_only) label += " | SOMENTE GRAMA";''',
)

replace_once(
    main,
    '''                        roads.has_required_road_access(*definition, instance->tile_x, instance->tile_y, instance->rotation)\n                            ? "ROAD CONNECTED"\n                            : "NO ROAD",''',
    '''                        building_has_required_edge_access(*definition, instance->rotation, instance->tile_x, instance->tile_y, roads, sidewalks)\n                            ? (definition->requires_road_or_path_access ? "ROAD/PATH CONNECTED" : "ROAD CONNECTED")\n                            : (definition->requires_road_or_path_access ? "NO ROAD/PATH" : "NO ROAD"),''',
)

replace_once(
    main,
    '''                        definition->requires_road_access ? "REQUIRED" : "NOT REQUIRED",''',
    '''                        definition->requires_road_or_path_access ? "ROAD OR PATH" :\n                            (definition->requires_road_access ? "REQUIRED" : "NOT REQUIRED"),''',
)

definition_path = ROOT / "assets/definitions/raspadinha_vendor_01.json"
definition = {
    "id": "raspadinha_vendor_01",
    "name": "Carrinho de Raspadinha",
    "category": "decor",
    "texture": "assets/props/raspadinha_vendor/raspadinha_vendor_anim_south.png",
    "sprites": {
        "0": "assets/props/raspadinha_vendor/raspadinha_vendor_anim_south.png",
        "1": "assets/props/raspadinha_vendor/raspadinha_vendor_anim_west.png",
        "2": "assets/props/raspadinha_vendor/raspadinha_vendor_anim_north.png",
        "3": "assets/props/raspadinha_vendor/raspadinha_vendor_anim_east.png"
    },
    "spriteAnchors": {
        "0": {"x": 0.5, "y": 0.66796875},
        "1": {"x": 0.5, "y": 0.66796875},
        "2": {"x": 0.5, "y": 0.66796875},
        "3": {"x": 0.5, "y": 0.66796875}
    },
    "rotatable": True,
    "requiresRoadAccess": False,
    "requiresRoadOrPathAccess": True,
    "grassOnly": True,
    "roadAccessMode": "any_perimeter",
    "footprint": {"width": 1, "height": 1},
    "buildCost": 0,
    "maintenancePerMonth": 0,
    "taxRevenuePerMonth": 0,
    "powerConsumption": 0,
    "artScale": 1.0,
    "animation": {
        "layout": "horizontal",
        "frameCount": 5,
        "frameDurationMs": 180,
        "playback": "ambient_once",
        "idleFrame": 0,
        "actionStartFrame": 1,
        "actionFrameCount": 4,
        "idleHoldMs": 7000
    },
    "playerBuildable": True,
    "productionStatus": "runtime_placement_candidate"
}
definition_path.parent.mkdir(parents=True, exist_ok=True)
definition_path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("CH_RASPADINHA_PLACEMENT_PATCH_OK")
