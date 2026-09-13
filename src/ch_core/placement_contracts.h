#pragma once

#include "semantic_contracts.h"
#include "grid.h"
#include <string>
#include <vector>
#include <cstdint>

namespace ch {

// Canonical Contract Version Constant
inline constexpr const char* kPlacementContract = "CH_PLACEMENT_V1";

// Placement Entity Categories
enum class PlacementCategory : uint8_t {
    building = 0,
    road = 1,
    tree = 2,
    decoration = 3,
    water_structure = 4
};

inline const char* to_string(PlacementCategory cat) {
    switch (cat) {
        case PlacementCategory::building:        return "BUILDING";
        case PlacementCategory::road:            return "ROAD";
        case PlacementCategory::tree:            return "TREE";
        case PlacementCategory::decoration:      return "DECORATION";
        case PlacementCategory::water_structure:  return "WATER_STRUCTURE";
        default:                                 return "UNKNOWN";
    }
}

// Stable Placement Violation Codes
enum class PlacementViolation : uint8_t {
    bounds_exceeded = 0,
    occupied = 1,
    terrain_incompatible = 2,
    anchor_invalid = 3,
    connector_missing = 4,
    road_required = 5,
    water_required = 6,
    category_rule = 7
};

inline const char* to_string(PlacementViolation v) {
    switch (v) {
        case PlacementViolation::bounds_exceeded:     return "CH_PLACE_BOUNDS";
        case PlacementViolation::occupied:            return "CH_PLACE_OCCUPIED";
        case PlacementViolation::terrain_incompatible: return "CH_PLACE_TERRAIN";
        case PlacementViolation::anchor_invalid:       return "CH_PLACE_ANCHOR";
        case PlacementViolation::connector_missing:    return "CH_PLACE_CONNECTOR";
        case PlacementViolation::road_required:        return "CH_PLACE_ROAD_REQUIRED";
        case PlacementViolation::water_required:       return "CH_PLACE_WATER_REQUIRED";
        case PlacementViolation::category_rule:        return "CH_PLACE_CATEGORY_RULE";
        default:                                       return "CH_PLACE_UNKNOWN";
    }
}

// Deterministic Placement Evaluation Request
struct PlacementRequest {
    std::string object_id;
    PlacementCategory category{PlacementCategory::building};
    GridCoord origin{0, 0};
    int rotation{0};
};

// Placement Evaluation Result
struct PlacementResult {
    std::string object_id;
    SemanticState state{SemanticState::valid};
    std::vector<PlacementViolation> violations;
    std::vector<GridCoord> affected_tiles;
    GridCoord resolved_origin{0, 0};
    GridCoord conflicting_tile{0, 0};
    std::string expected_connector;

    std::string to_formatted_string() const {
        if (state == SemanticState::valid) {
            return "CH_PLACEMENT_VALID";
        }
        std::string res;
        res += "CH_PLACEMENT_REJECTED\n";
        res += "object: " + object_id + "\n";
        res += "origin: " + std::to_string(resolved_origin.x) + "," + std::to_string(resolved_origin.y) + "\n";
        res += "violations:\n";
        for (const auto& v : violations) {
            res += std::string("- ") + to_string(v) + "\n";
        }
        if (conflicting_tile.x != 0 || conflicting_tile.y != 0) {
            res += "conflicting_tile: " + std::to_string(conflicting_tile.x) + "," + std::to_string(conflicting_tile.y) + "\n";
        }
        if (!expected_connector.empty()) {
            res += "expected_connector: " + expected_connector + "\n";
        }
        return res;
    }
};

} // namespace ch
