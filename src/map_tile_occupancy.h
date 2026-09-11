#pragma once

#include "building_system.h"
#include "farming_system.h"
#include "road_system.h"
#include "sidewalk_system.h"

// Read-only, cross-layer view used by placement, diagnostics and future
// navigation. It deliberately does not encode gameplay rules such as where a
// tractor may work; callers decide those rules from these stable layer facts.
struct MapTileOccupancy {
    bool building = false;
    bool road = false;
    bool sidewalk = false;
    bool farm = false;

    [[nodiscard]] bool is_empty_terrain() const {
        return !building && !road && !sidewalk && !farm;
    }

    [[nodiscard]] bool is_pedestrian_walkable() const {
        return sidewalk && !building && !road && !farm;
    }

    [[nodiscard]] bool is_vehicle_drivable() const {
        return road && !building && !sidewalk && !farm;
    }
};

[[nodiscard]] inline MapTileOccupancy inspect_map_tile(const BuildingManager& buildings, const RoadManager& roads,
                                                        const SidewalkManager& sidewalks, const FarmingSystem& farming,
                                                        const int tile_x, const int tile_y) {
    return {
        .building = buildings.is_occupied(tile_x, tile_y),
        .road = roads.is_road(tile_x, tile_y),
        .sidewalk = sidewalks.is_sidewalk(tile_x, tile_y),
        .farm = farming.is_occupied(tile_x, tile_y),
    };
}
