#ifndef CITY_HORIZON_CH_CORE_TRANSACTION_CONTRACTS_H
#define CITY_HORIZON_CH_CORE_TRANSACTION_CONTRACTS_H

#include <string>
#include <string_view>
#include <vector>
#include <variant>

namespace ch {

constexpr std::string_view kTransactionContract = "CH_TRANSACTION_V1";

enum class TransactionActionType {
    paint_terrain,
    place_building,
    demolish_building,
    set_road,
    batch_transaction
};

struct TerrainStateSnapshot {
    int tile_x = 0;
    int tile_y = 0;
    std::string previous_texture;
    std::string new_texture;
    // Added compatibly after the original texture-only snapshot. Older aggregate
    // initializers keep these empty; semantic terrain/water commands populate
    // them so undo/redo can restore gameplay meaning rather than only artwork.
    std::string previous_definition;
    std::string new_definition;
};

struct BuildingStateSnapshot {
    std::size_t instance_id = 0;
    std::string definition_id;
    int tile_x = 0;
    int tile_y = 0;
    int previous_rotation = 0;
    int new_rotation = 0;
    bool was_present = false;
    bool is_present = false;
};

struct RoadStateSnapshot {
    int tile_x = 0;
    int tile_y = 0;
    bool previous_present = false;
    bool new_present = false;
};

using TransactionPayload = std::variant<TerrainStateSnapshot, BuildingStateSnapshot, RoadStateSnapshot>;

struct CommandRecord {
    std::string description;
    TransactionActionType action_type = TransactionActionType::paint_terrain;
    std::vector<TransactionPayload> payloads;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_TRANSACTION_CONTRACTS_H
