#include "pedestrian_decision.h"

#include "road_system.h"
#include "sidewalk_system.h"

#include <algorithm>
#include <array>

namespace {

[[nodiscard]] NavigationTile outside(const BuildingInstance& building, const BuildingAccessPoint point) {
    static constexpr std::array<NavigationTile, 4> offsets = {{{0, -1}, {1, 0}, {0, 1}, {-1, 0}}};
    const NavigationTile offset = offsets[static_cast<std::size_t>(point.facing)];
    return {building.tile_x + point.local_x + offset.x, building.tile_y + point.local_y + offset.y};
}

} // namespace

void PedestrianDecisionNode::reset() {
    decision_ = PedestrianDecision::looking_for_activity;
    home_id_.reset();
    retry_seconds_ = 0.0F;
}

std::optional<NavigationTile> PedestrianDecisionNode::home_entrance(
    const std::uint64_t id, const BuildingManager& buildings, const BuildingCatalog& catalog,
    const NavigationNetwork& network, const std::optional<NavigationTile> from) const {
    const BuildingInstance* building = buildings.find_by_id(id);
    if (building == nullptr || !building->operational) return std::nullopt;
    const BuildingDefinition* definition = catalog.find(building->definition_id);
    if (definition == nullptr || definition->category != "residential" ||
        building->current_level_definition(*definition).residential_capacity == 0) return std::nullopt;

    const auto reachable = [&](NavigationTile tile) {
        return !buildings.is_occupied(tile.x, tile.y) && network.is_navigable(tile) &&
               (!from || find_navigation_path(network, *from, tile).status == NavigationPathStatus::found);
    };
    const auto candidates = road_access_candidates(*definition, building->rotation);
    for (const BuildingAccessPoint point : candidates) {
        const NavigationTile tile = outside(*building, point);
        if (reachable(tile)) return tile;
    }
    // Legacy residences without a declared facade admit any perimeter tile.
    if (resolved_road_access_mode(*definition) != RoadAccessMode::any_perimeter) return std::nullopt;
    const BuildingFootprint size = rotated_footprint(*definition, building->rotation);
    for (int x = 0; x < size.width; ++x) {
        for (const int y : {building->tile_y - 1, building->tile_y + size.height}) {
            const NavigationTile tile{building->tile_x + x, y};
            if (reachable(tile)) return tile;
        }
    }
    for (int y = 0; y < size.height; ++y) {
        for (const int x : {building->tile_x - 1, building->tile_x + size.width}) {
            const NavigationTile tile{x, building->tile_y + y};
            if (reachable(tile)) return tile;
        }
    }
    return std::nullopt;
}

bool PedestrianDecisionNode::start_activity(const NavigationTile from, PedestrianSystem& pedestrians,
                                             const NavigationNetwork& network) {
    constexpr std::size_t kMinimumWalkTiles = 6;
    const NavigationPathResult route = find_navigation_path_with_minimum_length(network, from, kMinimumWalkTiles);
    if (route.status != NavigationPathStatus::found ||
        !pedestrians.send_pedestrian(from, route.tiles.back(), network)) return false;
    decision_ = PedestrianDecision::walking_to_activity;
    return true;
}

void PedestrianDecisionNode::update(const float seconds, PedestrianSystem& pedestrians, const NavigationNetwork& network,
                                     const BuildingManager& buildings, const BuildingCatalog& catalog,
                                     const RoadManager& roads, const SidewalkManager& sidewalks, const bool raining) {
    const bool exists = !pedestrians.instances().empty();
    const std::optional<NavigationTile> current = exists ? std::optional<NavigationTile>{{
        pedestrians.instances().front().spatial.logical_tile_x, pedestrians.instances().front().spatial.logical_tile_y}}
        : std::nullopt;
    std::optional<NavigationTile> entrance;
    if (home_id_) entrance = home_entrance(*home_id_, buildings, catalog, network, current);
    if (!entrance) {
        home_id_.reset();
        for (const BuildingInstance& building : buildings.instances()) {
            entrance = home_entrance(building.instance_id, buildings, catalog, network, current);
            if (entrance) { home_id_ = building.instance_id; break; }
        }
        if (exists && pedestrians.instances().front().state == PedestrianState::resting && !entrance) {
            pedestrians.wake_up();
            decision_ = PedestrianDecision::looking_for_activity;
        }
    }
    // The commercial/attraction visitor bridge owns its route and dwell state.
    if (exists && (pedestrians.instances().front().state == PedestrianState::walking ||
                   pedestrians.instances().front().state == PedestrianState::visiting)) return;
    if (raining && entrance) {
        // Let a walk or indoor visit finish before redirecting. Never snap a
        // moving pedestrian to a new route just because the weather changed.
        retry_seconds_ = 0.0F;
        if (!exists) {
            if (pedestrians.send_pedestrian(*entrance, *entrance, network)) {
                (void)pedestrians.rest_at_home(*entrance);
                decision_ = PedestrianDecision::resting_at_home;
            }
        } else if (*current == *entrance && pedestrians.instances().front().state == PedestrianState::resting) {
            decision_ = PedestrianDecision::resting_at_home;
        } else if (*current == *entrance && pedestrians.rest_at_home(*entrance)) {
            decision_ = PedestrianDecision::resting_at_home;
        } else if (pedestrians.send_pedestrian(*current, *entrance, network)) {
            decision_ = PedestrianDecision::returning_home;
        }
        return;
    }
    if (exists && decision_ == PedestrianDecision::walking_to_activity) {
        // Give the visitor bridge a visible idle window to choose a shop or
        // ticketed attraction before the decision node sends the walker home.
        decision_ = PedestrianDecision::awaiting_activity;
        retry_seconds_ = 1.0F;
        return;
    }
    if (retry_seconds_ > 0.0F) {
        retry_seconds_ = std::max(0.0F, retry_seconds_ - std::max(0.0F, seconds));
        return;
    }

    if (!exists) {
        if (entrance) {
            // Spawning at the doorstep has no visible entry animation.
            if (pedestrians.send_pedestrian(*entrance, *entrance, network)) {
                (void)pedestrians.rest_at_home(*entrance);
                decision_ = PedestrianDecision::resting_at_home;
                retry_seconds_ = 3.0F;
            }
            return;
        }
        // Cities without a residence retain the old visible street preview.
        for (const SidewalkTile& tile : sidewalks.tiles()) {
            if (start_activity({tile.tile_x, tile.tile_y}, pedestrians, network)) return;
        }
        for (const RoadTile& tile : roads.tiles()) {
            if (start_activity({tile.tile_x, tile.tile_y}, pedestrians, network)) return;
        }
        retry_seconds_ = 2.0F;
        return;
    }

    const NavigationTile at = *current;
    if (decision_ == PedestrianDecision::returning_home && entrance && at == *entrance &&
        pedestrians.rest_at_home(*entrance)) {
        decision_ = PedestrianDecision::resting_at_home;
        retry_seconds_ = 6.0F;
        return;
    }
    if (decision_ == PedestrianDecision::awaiting_activity || decision_ == PedestrianDecision::returning_home) {
        decision_ = PedestrianDecision::looking_for_activity;
        if (entrance) {
            if (at == *entrance && pedestrians.rest_at_home(*entrance)) {
                decision_ = PedestrianDecision::resting_at_home;
                retry_seconds_ = 6.0F;
                return;
            }
            if (pedestrians.send_pedestrian(at, *entrance, network)) {
                decision_ = PedestrianDecision::returning_home;
                return;
            }
        }
        retry_seconds_ = 2.0F;
        return;
    }
    if (decision_ == PedestrianDecision::resting_at_home && (!entrance || at != *entrance)) {
        pedestrians.wake_up();
        decision_ = PedestrianDecision::looking_for_activity;
    }
    if (start_activity(at, pedestrians, network)) return;
    if (entrance && at != *entrance && pedestrians.send_pedestrian(at, *entrance, network)) {
        decision_ = PedestrianDecision::returning_home;
        return;
    }
    if (entrance && at == *entrance && pedestrians.rest_at_home(*entrance)) {
        decision_ = PedestrianDecision::resting_at_home;
    } else {
        decision_ = PedestrianDecision::looking_for_activity;
    }
    retry_seconds_ = 2.0F;
}
