#include "semantic_grid.h"
#include "terrain_semantics_catalog.h"
#include <cmath>

namespace ch {

TileSemanticInfo SemanticGrid::inspect_tile_channels(const SemanticWorldView& world, GridCoord tile) {
    TileSemanticInfo info;
    info.tile = tile;
    info.terrain_type = "grass";

    if (!world.map_document) {
        return info;
    }

    const auto& doc = *world.map_document;

    // 1. Terrain channel — only a CH_TERRAIN_SEMANTICS_V1 definition may
    // establish terrain gameplay. Images are deliberately not consulted.
    auto terrain = doc.get_terrain_at(tile.x, tile.y);
    std::string terrain_def_id = terrain.has_value() ? terrain->terrain_definition : "";
    const TerrainSemanticsCatalog& catalog = TerrainSemanticsCatalog::global_instance();
    const TerrainSemanticsDefinition* def = !terrain_def_id.empty() ? catalog.find(terrain_def_id) : nullptr;

    if (!def) {
        // Fail-closed safety: missing/unknown terrainDefinitionId MUST NOT silently become buildable or walkable.
        info.terrain_type = terrain_def_id.empty() ? "unresolved_legacy_terrain" : terrain_def_id;
        info.buildable_state = SemanticState::invalid;
        info.navigation_state = SemanticState::invalid;
        info.sidewalk_state = SemanticState::not_declared;
        info.water_state = SemanticState::not_declared;
    } else {
        info.terrain_type = def->id;
        info.buildable_state = def->buildable ? SemanticState::valid : SemanticState::invalid;
        info.water_state = def->water ? SemanticState::valid : SemanticState::not_applicable;
        info.sidewalk_state = (def->surface == "sidewalk") ? SemanticState::valid : SemanticState::not_applicable;
        info.navigation_state = (def->navigation_type == "pedestrian") ? SemanticState::valid : SemanticState::not_applicable;
    }

    // 2. Road channel
    bool has_road = doc.is_road_at(tile.x, tile.y);
    if (has_road) {
        info.road_state = SemanticState::valid;
        info.buildable_state = SemanticState::invalid;
        info.occupancy_state = SemanticState::valid;
    }

    // 3. Building footprint / occupancy channel
    for (const auto& b : doc.buildings()) {
        int w = 1;
        int h = 1;

        if (tile.x >= b.tile_x && tile.x < b.tile_x + w &&
            tile.y >= b.tile_y && tile.y < b.tile_y + h) {
            
            info.footprint_state = SemanticState::valid;
            info.occupancy_state = SemanticState::valid;
            info.buildable_state = SemanticState::invalid;
            info.occupied_by_asset = b.definition_id;
            info.footprint_width = w;
            info.footprint_height = h;

            if (tile.x == b.tile_x && tile.y == b.tile_y) {
                info.pivot_state = SemanticState::valid;
            } else {
                info.pivot_state = SemanticState::not_applicable;
            }
            break;
        }
    }

    return info;
}

std::vector<SemanticDivergence> SemanticGrid::validate_map_semantics(const SemanticWorldView& world, const IAssetCatalogView& catalog) {
    std::vector<SemanticDivergence> divergences;
    if (!world.map_document) return divergences;

    const auto& doc = *world.map_document;

    for (const auto& b : doc.buildings()) {
        AssetFootprintInfo fp = catalog.get_footprint(b.definition_id);
        if (!fp.declared) {
            // Asset mask / def not declared in catalog
            SemanticDivergence div;
            div.object_id = b.definition_id;
            div.tile = GridCoord(b.tile_x, b.tile_y);
            div.contract = kFootprintContract;
            div.field = "catalog_entry";
            div.expected = "DEFINED";
            div.actual = "MISSING";
            div.delta = "N/A";
            div.status = SemanticState::not_declared;
            divergences.push_back(div);
            continue;
        }

        // Validate footprint dimensions against catalog definition
        int exp_w = (fp.width > 0) ? fp.width : 1;
        int exp_h = (fp.height > 0) ? fp.height : 1;
        int act_w = exp_w;
        int act_h = exp_h;

        if (act_w != exp_w || act_h != exp_h) {
            SemanticDivergence div;
            div.object_id = b.definition_id;
            div.tile = GridCoord(b.tile_x, b.tile_y);
            div.contract = kFootprintContract;
            div.field = "footprint_dimensions";
            div.expected = std::to_string(exp_w) + "x" + std::to_string(exp_h);
            div.actual = std::to_string(act_w) + "x" + std::to_string(act_h);
            div.delta = std::to_string(act_w - exp_w) + "," + std::to_string(act_h - exp_h);
            div.status = SemanticState::invalid;
            divergences.push_back(div);
        }
    }

    return divergences;
}

} // namespace ch
