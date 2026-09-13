#include "src/ch_core/validation.h"

namespace ch {

MapValidationReport validate_map_document(const MapDocument& document) {
    MapValidationReport report;
    const GridBounds bounds;

    for (const auto& t : document.terrain_tiles()) {
        if (!bounds.contains(t.tile_x, t.tile_y)) {
            report.errors.push_back("Terrain tile at (" + std::to_string(t.tile_x) + ", " +
                                    std::to_string(t.tile_y) + ") is out of map bounds.");
        }
    }

    for (const auto& b : document.buildings()) {
        if (!bounds.contains(b.tile_x, b.tile_y)) {
            report.errors.push_back("Building '" + b.definition_id + "' at (" +
                                    std::to_string(b.tile_x) + ", " + std::to_string(b.tile_y) +
                                    ") is out of map bounds.");
        }
    }

    for (const auto& r : document.roads()) {
        if (!bounds.contains(r.tile_x, r.tile_y)) {
            report.errors.push_back("Road tile at (" + std::to_string(r.tile_x) + ", " +
                                    std::to_string(r.tile_y) + ") is out of map bounds.");
        }
    }

    report.valid = report.errors.empty();
    return report;
}

} // namespace ch
