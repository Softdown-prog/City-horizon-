#pragma once

#include "building_system.h"
#include "economy_system.h"
#include "road_system.h"
#include "src/ch_core/game_command.h"
#include "src/ch_core/map_document.h"

#include <cstdint>
#include <functional>
#include <string>
#include <utility>

class RoadPlacementCommand final : public ch::IGameCommand {
public:
    using TileOwnershipQuery = std::function<bool(int, int)>;

    RoadPlacementCommand(RoadManager& roads, const BuildingManager& buildings,
                         TileOwnershipQuery tile_owned, CityEconomy& economy,
                         const int tile_x, const int tile_y)
        : roads_(roads), buildings_(buildings), tile_owned_(std::move(tile_owned)), economy_(economy),
          tile_x_(tile_x), tile_y_(tile_y) {}

    [[nodiscard]] ch::GameCommandPlan prepare() const override {
        ch::GameCommandPlan plan;
        plan.cost_units = kRoadCostPerTile;
        plan.affected_tiles = {{tile_x_, tile_y_}};
        plan.transaction.description = "place road";
        plan.transaction.action_type = ch::TransactionActionType::set_road;
        plan.transaction.payloads.push_back(ch::RoadStateSnapshot{
            .tile_x = tile_x_,
            .tile_y = tile_y_,
            .previous_present = roads_.is_road(tile_x_, tile_y_),
            .new_present = true,
        });

        const RoadPlacementFailure placement = roads_.validate_placement(tile_x_, tile_y_, buildings_);
        if (placement != RoadPlacementFailure::none) {
            plan.valid = false;
            switch (placement) {
                case RoadPlacementFailure::outside_map:
                    plan.failure = ch::GameCommandFailure::out_of_bounds;
                    plan.message = "road tile is outside the map";
                    break;
                case RoadPlacementFailure::road_occupied:
                case RoadPlacementFailure::building_occupied:
                    plan.failure = ch::GameCommandFailure::conflicting_state;
                    plan.message = "road tile is occupied";
                    break;
                case RoadPlacementFailure::none:
                    break;
            }
            return plan;
        }

        if (!tile_owned_ || !tile_owned_(tile_x_, tile_y_)) {
            plan.valid = false;
            plan.failure = ch::GameCommandFailure::blocked;
            plan.message = "road tile is not owned";
            return plan;
        }

        if (!economy_.can_afford(plan.cost_units)) {
            plan.valid = false;
            plan.failure = ch::GameCommandFailure::insufficient_funds;
            plan.message = "insufficient funds for road";
            return plan;
        }

        plan.valid = true;
        plan.failure = ch::GameCommandFailure::none;
        plan.message = "road placement ready";
        return plan;
    }

    [[nodiscard]] bool apply(const ch::GameCommandPlan& prepared, std::string& error) override {
        if (!prepared.valid || prepared.cost_units < 0) {
            error = "invalid prepared road command";
            return false;
        }
        if (roads_.validate_placement(tile_x_, tile_y_, buildings_) != RoadPlacementFailure::none ||
            !tile_owned_ || !tile_owned_(tile_x_, tile_y_)) {
            error = "road placement changed after preview";
            return false;
        }
        if (!economy_.try_spend(prepared.cost_units)) {
            error = "funds changed after preview";
            return false;
        }
        if (!roads_.place_tile(tile_x_, tile_y_)) {
            economy_.credit_infrastructure_refund(prepared.cost_units);
            error = "road manager rejected prepared placement";
            return false;
        }
        return true;
    }

private:
    RoadManager& roads_;
    const BuildingManager& buildings_;
    TileOwnershipQuery tile_owned_;
    CityEconomy& economy_;
    int tile_x_ = 0;
    int tile_y_ = 0;
};

class TerrainPaintCommand final : public ch::IGameCommand {
public:
    using TileOwnershipQuery = std::function<bool(int, int)>;

    TerrainPaintCommand(ch::MapDocument& document, TileOwnershipQuery tile_owned, CityEconomy& economy,
                        const int tile_x, const int tile_y, std::string terrain_definition,
                        std::string texture_path, const std::int64_t cost_units)
        : document_(document), tile_owned_(std::move(tile_owned)), economy_(economy), tile_x_(tile_x), tile_y_(tile_y),
          terrain_definition_(std::move(terrain_definition)), texture_path_(std::move(texture_path)),
          cost_units_(cost_units) {}

    [[nodiscard]] ch::GameCommandPlan prepare() const override {
        ch::GameCommandPlan plan;
        plan.cost_units = cost_units_;
        plan.affected_tiles = {{tile_x_, tile_y_}};
        plan.transaction.description = "paint terrain";
        plan.transaction.action_type = ch::TransactionActionType::paint_terrain;

        if (terrain_definition_.empty() || cost_units_ < 0) {
            plan.failure = ch::GameCommandFailure::invalid_request;
            plan.message = "terrain command has invalid definition or cost";
            return plan;
        }
        if (!tile_owned_ || !tile_owned_(tile_x_, tile_y_)) {
            plan.failure = ch::GameCommandFailure::blocked;
            plan.message = "terrain tile is not owned";
            return plan;
        }

        const std::optional<ch::TerrainTileEntry> current = document_.get_terrain_at(tile_x_, tile_y_);
        const std::string previous_definition = current ? current->terrain_definition : "grass";
        const std::string previous_texture = current ? current->texture : "";
        plan.transaction.payloads.push_back(ch::TerrainStateSnapshot{
            .tile_x = tile_x_,
            .tile_y = tile_y_,
            .previous_texture = previous_texture,
            .new_texture = texture_path_,
            .previous_definition = previous_definition,
            .new_definition = terrain_definition_,
        });

        if (previous_definition == terrain_definition_ && previous_texture == texture_path_) {
            plan.failure = ch::GameCommandFailure::conflicting_state;
            plan.message = "terrain tile already has requested surface";
            return plan;
        }
        if (!economy_.can_afford(plan.cost_units)) {
            plan.failure = ch::GameCommandFailure::insufficient_funds;
            plan.message = "insufficient funds for terrain change";
            return plan;
        }

        plan.valid = true;
        plan.failure = ch::GameCommandFailure::none;
        plan.message = "terrain change ready";
        return plan;
    }

    [[nodiscard]] bool apply(const ch::GameCommandPlan& prepared, std::string& error) override {
        if (!prepared.valid || prepared.transaction.payloads.size() != 1 || !tile_owned_ ||
            !tile_owned_(tile_x_, tile_y_)) {
            error = "invalid prepared terrain command";
            return false;
        }
        const auto* snapshot = std::get_if<ch::TerrainStateSnapshot>(&prepared.transaction.payloads.front());
        if (snapshot == nullptr) {
            error = "prepared terrain snapshot is missing";
            return false;
        }
        const std::optional<ch::TerrainTileEntry> current = document_.get_terrain_at(tile_x_, tile_y_);
        const std::string current_definition = current ? current->terrain_definition : "grass";
        const std::string current_texture = current ? current->texture : "";
        if (current_definition != snapshot->previous_definition || current_texture != snapshot->previous_texture) {
            error = "terrain state changed after preview";
            return false;
        }
        if (!economy_.try_spend(prepared.cost_units)) {
            error = "funds changed after preview";
            return false;
        }
        document_.paint_terrain_at(tile_x_, tile_y_, terrain_definition_, texture_path_);
        return true;
    }

private:
    ch::MapDocument& document_;
    TileOwnershipQuery tile_owned_;
    CityEconomy& economy_;
    int tile_x_ = 0;
    int tile_y_ = 0;
    std::string terrain_definition_;
    std::string texture_path_;
    std::int64_t cost_units_ = 0;
};
