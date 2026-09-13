#pragma once

#include "grid.h"
#include <string>
#include <cstdint>

namespace ch {

// Canonical Contract Version Constants
inline constexpr const char* kAnchorContract = "CH_ANCHOR_V1";
inline constexpr const char* kFootprintContract = "CH_FOOTPRINT_V1";
inline constexpr const char* kConnectorContract = "CH_CONNECTOR_V1";
inline constexpr const char* kSemanticOverlayContract = "CH_SEMANTIC_OVERLAY_V1";
inline constexpr const char* kSemanticStateContract = "CH_SEMANTIC_STATE_V1";

// Three/Four-value Semantic Governance State
enum class SemanticState : uint8_t {
    valid = 0,
    invalid = 1,
    not_declared = 2,
    not_applicable = 3
};

inline const char* to_string(SemanticState state) {
    switch (state) {
        case SemanticState::valid:          return "VALID";
        case SemanticState::invalid:        return "INVALID";
        case SemanticState::not_declared:   return "NOT_DECLARED";
        case SemanticState::not_applicable: return "NOT_APPLICABLE";
        default:                            return "UNKNOWN";
    }
}

// Semantic Contact Anchor Types
enum class AnchorType : uint8_t {
    ground_anchor = 0,
    trunk_contact = 1,
    feet_contact = 2,
    tile_center = 3,
    land_water_connector = 4
};

inline const char* to_string(AnchorType type) {
    switch (type) {
        case AnchorType::ground_anchor:        return "GROUND_ANCHOR";
        case AnchorType::trunk_contact:        return "TRUNK_CONTACT";
        case AnchorType::feet_contact:         return "FEET_CONTACT";
        case AnchorType::tile_center:          return "TILE_CENTER";
        case AnchorType::land_water_connector: return "LAND_WATER_CONNECTOR";
        default:                               return "UNKNOWN";
    }
}

// Semantic Connector Types
enum class ConnectorType : uint8_t {
    road_n = 0,
    road_e = 1,
    road_s = 2,
    road_w = 3,
    sidewalk = 4,
    entrance = 5,
    ground = 6,
    water_edge = 7,
    pedestrian = 8,
    service = 9
};

inline const char* to_string(ConnectorType type) {
    switch (type) {
        case ConnectorType::road_n:     return "ROAD_N";
        case ConnectorType::road_e:     return "ROAD_E";
        case ConnectorType::road_s:     return "ROAD_S";
        case ConnectorType::road_w:     return "ROAD_W";
        case ConnectorType::sidewalk:   return "SIDEWALK";
        case ConnectorType::entrance:   return "ENTRANCE";
        case ConnectorType::ground:     return "GROUND";
        case ConnectorType::water_edge: return "WATER_EDGE";
        case ConnectorType::pedestrian: return "PEDESTRIAN";
        case ConnectorType::service:    return "SERVICE";
        default:                        return "UNKNOWN";
    }
}

// Bitmask Flags for 13 Semantic Channels
enum class SemanticChannel : uint32_t {
    none       = 0,
    terrain    = 1 << 0,
    footprint  = 1 << 1,
    occupancy  = 1 << 2,
    buildable  = 1 << 3,
    road       = 1 << 4,
    sidewalk   = 1 << 5,
    water      = 1 << 6,
    pivot      = 1 << 7,
    entrance   = 1 << 8,
    connector  = 1 << 9,
    no_build   = 1 << 10,
    navigation = 1 << 11,
    region     = 1 << 12,
    all        = 0x1FFF
};

inline constexpr SemanticChannel operator|(SemanticChannel a, SemanticChannel b) {
    return static_cast<SemanticChannel>(static_cast<uint32_t>(a) | static_cast<uint32_t>(b));
}

inline constexpr SemanticChannel operator&(SemanticChannel a, SemanticChannel b) {
    return static_cast<SemanticChannel>(static_cast<uint32_t>(a) & static_cast<uint32_t>(b));
}

// Detailed Semantic Tile Inspection Record
struct TileSemanticInfo {
    GridCoord tile{0, 0};
    std::string terrain_type{"grass"};
    
    SemanticState footprint_state{SemanticState::not_applicable};
    SemanticState occupancy_state{SemanticState::not_applicable};
    SemanticState buildable_state{SemanticState::not_applicable};
    SemanticState road_state{SemanticState::not_applicable};
    SemanticState sidewalk_state{SemanticState::not_applicable};
    SemanticState water_state{SemanticState::not_applicable};
    SemanticState pivot_state{SemanticState::not_applicable};
    SemanticState entrance_state{SemanticState::not_applicable};
    SemanticState connector_state{SemanticState::not_applicable};
    SemanticState no_build_state{SemanticState::not_applicable};
    SemanticState navigation_state{SemanticState::not_applicable};
    SemanticState region_state{SemanticState::not_applicable};
    
    std::string occupied_by_asset;
    int footprint_width{0};
    int footprint_height{0};
};

// Zero-tolerance Divergence Report
struct SemanticDivergence {
    std::string object_id;
    GridCoord tile{0, 0};
    std::string contract;
    std::string field;
    std::string expected;
    std::string actual;
    std::string delta;
    SemanticState status{SemanticState::invalid};

    std::string to_formatted_string() const {
        std::string res;
        res += "CH_SEMANTIC_DIVERGENCE\n";
        res += "object: " + object_id + "\n";
        res += "tile: " + std::to_string(tile.x) + "," + std::to_string(tile.y) + "\n";
        res += "contract: " + contract + "\n";
        res += "field: " + field + "\n";
        res += "expected: " + expected + "\n";
        res += "actual: " + actual + "\n";
        res += "delta: " + delta + "\n";
        res += "status: ";
        res += (status == SemanticState::invalid ? "REJECTED" : to_string(status));
        return res;
    }
};

} // namespace ch
