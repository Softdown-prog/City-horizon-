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

[[nodiscard]] bool is_essential_definition(const BuildingDefinition& definition) {
    // Explicit V1 list. These are the two current neighbourhood-needs services.
    // A later content pass may promote this to authored metadata when more service
    // families exist; keeping the list here avoids inventing a jobs/needs system.
    return definition.id == "bakery_01" || definition.id == "mini_market_01";
}

} // namespace

void PedestrianDecisionNode::reset() {
    decision_ = PedestrianDecision::looking_for_activity;
    home_id_.reset();
    retry_seconds_ = 0.0F;
    decision_rng_.seed(0xC17A2026U);
}

float PedestrianDecisionNode::outing_probability(const WeatherState weather,
                                                  const bool essential_service_available) {
    switch (weather) {
        case WeatherState::sunny: return 0.85F;
        case WeatherState::overcast: return 0.45F;
        case WeatherState::raining: return essential_service_available ? 0.45F : 0.12F;
        case WeatherState::thunderstorm: return essential_service_available ? 0.35F : 0.10F;
    }
    return 0.45F;
}

PedestrianOutingPreference PedestrianDecisionNode::preference_for_weather(
    const WeatherState weather, const bool essential_service_available) {
    switch (weather) {
        case WeatherState::sunny:
            return PedestrianOutingPreference::outdoor_leisure;
        case WeatherState::overcast:
            return PedestrianOutingPreference::balanced;
        case WeatherState::raining:
        case WeatherState::thunderstorm:
            return essential_service_available
                ? PedestrianOutingPreference::essential_commerce
                : PedestrianOutingPreference::covered_commerce;
    }
    return PedestrianOutingPreference::balanced;
}

bool PedestrianDecisionNode::decide_to_leave(const WeatherState weather,
                                              const bool essential_service_available) {
    const float roll = std::uniform_real_distribution<float>{0.0F, 1.0F}(decision_rng_);
    return roll < outing_probability(weather, essential_service_available);
}

bool PedestrianDecisionNode::essential_service_available(const BuildingManager& buildings,
                                                          const BuildingCatalog& catalog) const {
    for (const BuildingInstance& building : buildings.instances()) {
        if (!building.operational) continue;
        const BuildingDefinition* definition = catalog.find(building.definition_id);
        if (definition != nullptr && is_essential_definition(*definition)) return true;
    }
    return false;
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
               (!from || tile == *from || find_navigation_path(network, *from, tile).status == NavigationPathStatus::found);
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

    // Critical contract: once the resident is in transit or consuming, weather
    // is irrelevant. Never cancel/recalculate a live trip because the sky changed.
    if (exists && (pedestrians.instances().front().state == PedestrianState::walking ||
                   pedestrians.instances().front().state == PedestrianState::visiting)) {
        if (decision_ == PedestrianDecision::awaiting_activity) retry_seconds_ = 0.0F;
        return;
    }

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

    if (retry_seconds_ > 0.0F) {
        retry_seconds_ = std::max(0.0F, retry_seconds_ - std::max(0.0F, seconds));
        return;
    }

    if (!exists) {
        if (entrance) {
            // Spawn logically at the doorstep, then stay hidden in AtHome.
            if (pedestrians.send_pedestrian(*entrance, *entrance, network)) {
                (void)pedestrians.rest_at_home(*entrance);
                decision_ = PedestrianDecision::resting_at_home;
                retry_seconds_ = 6.0F;
            }
            return;
        }
        // Cities without a residence retain the developer-visible street preview.
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

    if (decision_ == PedestrianDecision::resting_at_home) {
        if (!entrance || at != *entrance) {
            pedestrians.wake_up();
            decision_ = PedestrianDecision::looking_for_activity;
            retry_seconds_ = 1.0F;
            return;
        }

        const PedestrianInstance& resident = pedestrians.instances().front();
        if (resident.monthly_budget_cents <= 0) {
            retry_seconds_ = 6.0F;
            return;
        }

        WeatherState weather = WeatherSystem::observed_state();
        // Keep the legacy bool meaningful for isolated tests/callers that have no
        // live WeatherSystem instance while preserving exact overcast at runtime.
        if (raining && weather != WeatherState::thunderstorm) weather = WeatherState::raining;
        const bool essential = essential_service_available(buildings, catalog);
        if (!decide_to_leave(weather, essential)) {
            retry_seconds_ = 6.0F;
            return;
        }

        if (pedestrians.authorize_outing(preference_for_weather(weather, essential))) {
            // The building-visit bridge consumes the intent and sends the actor
            // directly from the home entrance to an eligible destination.
            decision_ = PedestrianDecision::awaiting_activity;
            retry_seconds_ = 2.0F;
            return;
        }
        retry_seconds_ = 6.0F;
        return;
    }

    if (decision_ == PedestrianDecision::awaiting_activity) {
        // If the visit bridge could not find an affordable/reachable destination,
        // cancel the one-shot intent and go back inside. If a visit did happen,
        // the bridge clears the intent and this same branch sends the citizen home.
        pedestrians.clear_outing_intent(pedestrians.instances().front().id);
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
        decision_ = PedestrianDecision::looking_for_activity;
        retry_seconds_ = 2.0F;
        return;
    }

    if (decision_ == PedestrianDecision::walking_to_activity) {
        // Legacy/no-home street preview keeps the old visible idle window.
        decision_ = PedestrianDecision::awaiting_activity;
        retry_seconds_ = 1.0F;
        return;
    }

    if (decision_ == PedestrianDecision::returning_home) {
        if (entrance && at != *entrance && pedestrians.send_pedestrian(at, *entrance, network)) return;
        if (entrance && at == *entrance && pedestrians.rest_at_home(*entrance)) {
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }
    }

    // Residence-backed agents do not wander arbitrarily anymore. Their only
    // autonomous departure is the explicit AtHome decision above.
    if (entrance) {
        if (at != *entrance && pedestrians.send_pedestrian(at, *entrance, network)) {
            decision_ = PedestrianDecision::returning_home;
            return;
        }
        if (at == *entrance && pedestrians.rest_at_home(*entrance)) {
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }
    }

    if (start_activity(at, pedestrians, network)) return;
    decision_ = PedestrianDecision::looking_for_activity;
    retry_seconds_ = 2.0F;
}
