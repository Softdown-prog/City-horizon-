#ifndef CITY_HORIZON_CH_CORE_SHORELINE_CONTRACTS_H
#define CITY_HORIZON_CH_CORE_SHORELINE_CONTRACTS_H

#include "grid.h"
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>
#include <algorithm>

namespace ch {

constexpr std::string_view kShorelineContract = "CH_SHORELINE_V1";

// Neighborhood Bitmask Constants (8-neighbor layout)
constexpr uint8_t kNeighborN  = 1;   // 1 << 0
constexpr uint8_t kNeighborNE = 2;   // 1 << 1
constexpr uint8_t kNeighborE  = 4;   // 1 << 2
constexpr uint8_t kNeighborSE = 8;   // 1 << 3
constexpr uint8_t kNeighborS  = 16;  // 1 << 4
constexpr uint8_t kNeighborSW = 32;  // 1 << 5
constexpr uint8_t kNeighborW  = 64;  // 1 << 6
constexpr uint8_t kNeighborNW = 128; // 1 << 7

enum class ShorelinePiece : uint8_t {
    border_north = 0,
    border_east  = 1,
    border_south = 2,
    border_west  = 3,
    outer_ne     = 4,
    outer_se     = 5,
    outer_sw     = 6,
    outer_nw     = 7,
    inner_ne     = 8,
    inner_se     = 9,
    inner_sw     = 10,
    inner_nw     = 11
};

enum class QuarterTurn : uint8_t {
    R0   = 0,
    R90  = 1,
    R180 = 2,
    R270 = 3
};

inline const char* to_string(ShorelinePiece piece) {
    switch (piece) {
        case ShorelinePiece::border_north: return "border_north";
        case ShorelinePiece::border_east:  return "border_east";
        case ShorelinePiece::border_south: return "border_south";
        case ShorelinePiece::border_west:  return "border_west";
        case ShorelinePiece::outer_ne:     return "outer_ne";
        case ShorelinePiece::outer_se:     return "outer_se";
        case ShorelinePiece::outer_sw:     return "outer_sw";
        case ShorelinePiece::outer_nw:     return "outer_nw";
        case ShorelinePiece::inner_ne:     return "inner_ne";
        case ShorelinePiece::inner_se:     return "inner_se";
        case ShorelinePiece::inner_sw:     return "inner_sw";
        case ShorelinePiece::inner_nw:     return "inner_nw";
        default: return "unknown";
    }
}

struct ShorelineRecipe {
    std::vector<ShorelinePiece> pieces;

    void normalize() {
        // Remove duplicates
        std::sort(pieces.begin(), pieces.end());
        pieces.erase(std::unique(pieces.begin(), pieces.end()), pieces.end());
    }

    bool operator==(const ShorelineRecipe& other) const {
        return pieces == other.pieces;
    }
};

struct ShorelineEdit {
    GridCoord tile;
    ShorelineRecipe recipe;
};

struct AutotileResult {
    std::vector<ShorelineEdit> edits;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_SHORELINE_CONTRACTS_H
