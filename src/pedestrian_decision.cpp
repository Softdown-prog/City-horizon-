#include "pedestrian_decision.h"

#include "population_system.h"
#include "road_system.h"
#include "sidewalk_system.h"

#include <algorithm>
#include <array>
#include <unordered_set>
#include <vector>

namespace {

[[nodiscard]] NavigationTile outside(const BuildingInstance& building, const BuildingAccessPoint point) {
    static constexpr std::array<NavigationTile, 4> offsets = {{{0, -1}, {1, 0}, {0, 1}, {-1, 0}}};
    const NavigationTile offset = offsets[static_cast<std::size_t>(point.facing)];
    return {building.tile_x + point.local_x + offset.x, building.tile_y + point.local_y + offset.y};
}

[[nodiscard]] bool is_essential_definition(const BuildingDefinition& definition) {
    return definition.id == "bakery_01" || definition.id == "mini_market_01";
}

[[nodiscard]] const PedestrianInstance* find_pedestrian(const PedestrianSystem& pedestrians,
                                                         const std::uint64_t pedestrian_id) {
    const auto found = std::find_if(pedestrians.instances().begin(), pedestrians.instances().end(),
                                    [pedestrian_id](const PedestrianInstance& pedestrian) {
        return pedestrian.id == pedestrian_id;
    });
    return found == pedestrians.instances().end() ? nullptr : &*found;
}

[[nodiscard]] PedestrianOutingPurpose outing_purpose_for(const PedestrianInstance& pedestrian,
                                                          const WeatherState weather) {
    const float weakest_need = std::min({pedestrian.needs.hunger, pedestrian.needs.thirst, pedestrian.needs.fun});
    // A materially depleted wellbeing bar remains authoritative. When the
    // citizen is comfortable, leaving home may instead be discretionary.
    if (weakest_need <= 70.0F) return PedestrianOutingPurpose::need;

    switch (weather) {
        case WeatherState::sunny: return PedestrianOutingPurpose::leisure_activity;
        case WeatherState::overcast: return PedestrianOutingPurpose::shopping;
        case WeatherState::raining:
        case WeatherState::thunderstorm: return PedestrianOutingPurpose::service;
    }
    return PedestrianOutingPurpose::shopping;
}

} // namespace

void PedestrianDecisionNode::reseed_for(const std::uint64_t pedestrian_id) {
    const std::uint32_t low = static_cast<std::uint32_t>(pedestrian_id & 0xFFFFFFFFULL);
    const std::uint32_t high = static_cast<std::uint32_t>((pedestrian_id >> 32U) & 0xFFFFFFFFULL);
    std::seed_seq seed{0xC17A2026U, low, high, low ^ 0x9E3779B9U};
    decision_rng_.seed(seed);
}

void PedestrianDecisionNode::reset() {
    pedestrian_id_ = 0;
    decision_ = PedestrianDecision::looking_for_activity;
    home_id_.reset();
    retry_seconds_ = 0.0F;
    decision_rng_.seed(0xC17A2026U);
}

void PedestrianDecisionNode::reset_for(const std::uint64_t pedestrian_id) {
    pedestrian_id_ = pedestrian_id;
    decision_ = PedestrianDecision::looking_for_activity;
    home_id_.reset();
    retry_seconds_ = 0.0F;
    reseed_for(pedestrian_id);
}

float PedestrianDecisionNode::outing_probability(const WeatherState weather,
                                                  const bool essential_service_available_value) {
    switch (weather) {
        case WeatherState::sunny: return 0.85F;
        case WeatherState::overcast: return 0.45F;
        case WeatherState::raining: return essential_service_available_value ? 0.45F : 0.12F;
        case WeatherState::thunderstorm: return essential_service_available_value ? 0.35F : 0.10F;
    }
    return 0.45F;
}

PedestrianOutingPreference PedestrianDecisionNode::preference_for_weather(
    const WeatherState weather, const bool essential_service_available_value) {
    switch (weather) {
        case WeatherState::sunny: return PedestrianOutingPreference::outdoor_leisure;
        case WeatherState::overcast: return PedestrianOutingPreference::balanced;
        case WeatherState::raining:
        case WeatherState::thunderstorm:
            return essential_service_available_value
                ? PedestrianOutingPreference::essential_commerce
                : PedestrianOutingPreference::covered_commerce;
    }
    return PedestrianOutingPreference::balanced;
}

bool PedestrianDecisionNode::decide_to_leave(const WeatherState weather,
                                              const bool essential_service_available_value) {
    const float roll = std::uniform_real_distribution<float>{0.0F, 1.0F}(decision_rng_);
    return roll < outing_probability(weather, essential_service_available_value);
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
    const NavigationNetwork& network, const std::optional<NavigationTile> from) {
    const BuildingInstance* building = buildings.find_by_id(id);
    if (building == nullptr || !building->operational) return std::nullopt;
    const BuildingDefinition* definition = catalog.find(building->definition_id);
    if (definition == nullptr || definition->category != "residential" ||
        building->current_level_definition(*definition).residential_capacity == 0) return std::nullopt;

    const auto reachable = [&](const NavigationTile tile) {
        return !buildings.is_occupied(tile.x, tile.y) && network.is_navigable(tile) &&
               (!from || tile == *from || find_navigation_path(network, *from, tile).status == NavigationPathStatus::found);
    };
    const auto candidates = road_access_candidates(*definition, building->rotation);
    for (const BuildingAccessPoint point : candidates) {
        const NavigationTile tile = outside(*building, point);
        if (reachable(tile)) return tile;
    }
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

bool PedestrianDecisionNode::start_activity(const std::uint64_t pedestrian_id, const NavigationTile from,
                                             PedestrianSystem& pedestrians, const NavigationNetwork& network) {
    constexpr std::size_t kMinimumWalkTiles = 6;
    const NavigationPathResult route = find_navigation_path_with_minimum_length(network, from, kMinimumWalkTiles);
    if (route.status != NavigationPathStatus::found ||
        !pedestrians.send_pedestrian(pedestrian_id, from, route.tiles.back(), network)) return false;
    decision_ = PedestrianDecision::walking_to_activity;
    return true;
}

void PedestrianDecisionNode::update(const float seconds, PedestrianSystem& pedestrians,
                                     const NavigationNetwork& network, const BuildingManager& buildings,
                                     const BuildingCatalog& catalog, const RoadManager& roads,
                                     const SidewalkManager& sidewalks, const bool raining) {
    // Backward-compatible single-actor bootstrap used by focused tests and old
    // developer controls. The scalable runtime path uses PedestrianDecisionSystem.
    if (pedestrians.instances().empty()) {
        std::optional<NavigationTile> entrance;
        std::optional<std::uint64_t> chosen_home;
        for (const BuildingInstance& building : buildings.instances()) {
            entrance = home_entrance(building.instance_id, buildings, catalog, network, std::nullopt);
            if (entrance) {
                chosen_home = building.instance_id;
                break;
            }
        }
        if (entrance && pedestrians.send_pedestrian(*entrance, *entrance, network)) {
            const std::uint64_t id = pedestrians.instances().front().id;
            reset_for(id);
            home_id_ = chosen_home;
            (void)pedestrians.rest_at_home(id, *entrance);
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }

        const auto bootstrap_activity = [&](const NavigationTile start) {
            constexpr std::size_t kMinimumWalkTiles = 6;
            const NavigationPathResult route = find_navigation_path_with_minimum_length(network, start, kMinimumWalkTiles);
            if (route.status != NavigationPathStatus::found ||
                !pedestrians.send_pedestrian(start, route.tiles.back(), network)) return false;
            reset_for(pedestrians.instances().front().id);
            decision_ = PedestrianDecision::walking_to_activity;
            return true;
        };
        for (const SidewalkTile& tile : sidewalks.tiles()) {
            if (bootstrap_activity({tile.tile_x, tile.tile_y})) return;
        }
        for (const RoadTile& tile : roads.tiles()) {
            if (bootstrap_activity({tile.tile_x, tile.tile_y})) return;
        }
        retry_seconds_ = 2.0F;
        return;
    }

    const std::uint64_t id = pedestrians.instances().front().id;
    if (pedestrian_id_ != id) reset_for(id);
    update_for(id, seconds, pedestrians, network, buildings, catalog, roads, sidewalks, raining);
}

void PedestrianDecisionNode::update_for(const std::uint64_t pedestrian_id, const float seconds,
                                         PedestrianSystem& pedestrians, const NavigationNetwork& network,
                                         const BuildingManager& buildings, const BuildingCatalog& catalog,
                                         const RoadManager& roads, const SidewalkManager& sidewalks,
                                         const bool raining) {
    (void)roads;
    (void)sidewalks;
    if (pedestrian_id_ != pedestrian_id) reset_for(pedestrian_id);

    const PedestrianInstance* target = find_pedestrian(pedestrians, pedestrian_id);
    if (target == nullptr) return;
    const NavigationTile at{target->spatial.logical_tile_x, target->spatial.logical_tile_y};

    if (target->state == PedestrianState::walking || target->state == PedestrianState::visiting) {
        if (decision_ == PedestrianDecision::awaiting_activity) retry_seconds_ = 0.0F;
        return;
    }

    std::optional<NavigationTile> entrance;
    if (home_id_) entrance = home_entrance(*home_id_, buildings, catalog, network, at);
    if (!entrance) {
        home_id_.reset();
        for (const BuildingInstance& building : buildings.instances()) {
            entrance = home_entrance(building.instance_id, buildings, catalog, network, at);
            if (entrance) {
                home_id_ = building.instance_id;
                break;
            }
        }
        if (target->state == PedestrianState::resting && !entrance) {
            pedestrians.wake_up(pedestrian_id);
            decision_ = PedestrianDecision::looking_for_activity;
        }
    }

    if (retry_seconds_ > 0.0F) {
        retry_seconds_ = std::max(0.0F, retry_seconds_ - std::max(0.0F, seconds));
        return;
    }

    target = find_pedestrian(pedestrians, pedestrian_id);
    if (target == nullptr) return;

    if (decision_ == PedestrianDecision::returning_home && entrance && at == *entrance &&
        pedestrians.rest_at_home(pedestrian_id, *entrance)) {
        decision_ = PedestrianDecision::resting_at_home;
        retry_seconds_ = 6.0F;
        return;
    }

    if (decision_ == PedestrianDecision::resting_at_home || target->state == PedestrianState::resting) {
        if (!entrance || at != *entrance) {
            pedestrians.wake_up(pedestrian_id);
            decision_ = PedestrianDecision::looking_for_activity;
            retry_seconds_ = 1.0F;
            return;
        }

        target = find_pedestrian(pedestrians, pedestrian_id);
        if (target == nullptr) return;
        if (target->monthly_budget_cents <= 0) {
            retry_seconds_ = 6.0F;
            return;
        }

        WeatherState weather = WeatherSystem::observed_state();
        if (raining && weather != WeatherState::thunderstorm) weather = WeatherState::raining;
        const bool essential = essential_service_available(buildings, catalog);
        if (!decide_to_leave(weather, essential)) {
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }

        const PedestrianNeed need = pedestrians.priority_need(pedestrian_id);
        const PedestrianOutingPurpose purpose = outing_purpose_for(*target, weather);
        if (pedestrians.authorize_outing(pedestrian_id, preference_for_weather(weather, essential), need)) {
            (void)pedestrians.set_outing_purpose(pedestrian_id, purpose);
            decision_ = PedestrianDecision::awaiting_activity;
            retry_seconds_ = 2.0F;
            return;
        }
        decision_ = PedestrianDecision::resting_at_home;
        retry_seconds_ = 6.0F;
        return;
    }

    if (decision_ == PedestrianDecision::awaiting_activity) {
        pedestrians.clear_outing_intent(pedestrian_id);
        if (entrance) {
            if (at == *entrance && pedestrians.rest_at_home(pedestrian_id, *entrance)) {
                decision_ = PedestrianDecision::resting_at_home;
                retry_seconds_ = 6.0F;
                return;
            }
            if (pedestrians.send_pedestrian(pedestrian_id, at, *entrance, network)) {
                decision_ = PedestrianDecision::returning_home;
                return;
            }
        }
        decision_ = PedestrianDecision::looking_for_activity;
        retry_seconds_ = 2.0F;
        return;
    }

    if (decision_ == PedestrianDecision::walking_to_activity) {
        decision_ = PedestrianDecision::awaiting_activity;
        retry_seconds_ = 1.0F;
        return;
    }

    if (decision_ == PedestrianDecision::returning_home) {
        if (entrance && at != *entrance && pedestrians.send_pedestrian(pedestrian_id, at, *entrance, network)) return;
        if (entrance && at == *entrance && pedestrians.rest_at_home(pedestrian_id, *entrance)) {
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }
    }

    if (entrance) {
        if (at != *entrance && pedestrians.send_pedestrian(pedestrian_id, at, *entrance, network)) {
            decision_ = PedestrianDecision::returning_home;
            return;
        }
        if (at == *entrance && pedestrians.rest_at_home(pedestrian_id, *entrance)) {
            decision_ = PedestrianDecision::resting_at_home;
            retry_seconds_ = 6.0F;
            return;
        }
    }

    if (start_activity(pedestrian_id, at, pedestrians, network)) return;
    decision_ = PedestrianDecision::looking_for_activity;
    retry_seconds_ = 2.0F;
}

void PedestrianDecisionSystem::reset() {
    nodes_.clear();
    simulation_tick_ = 0;
    population_sync_seconds_ = kPopulationSyncIntervalSeconds;
}

std::size_t PedestrianDecisionSystem::target_active_citizens(const PopulationSystem& population) {
    return std::min<std::size_t>(population.current_population(), kMaxActiveCitizens);
}

void PedestrianDecisionSystem::prune_missing(const PedestrianSystem& pedestrians) {
    std::unordered_set<std::uint64_t> alive;
    alive.reserve(pedestrians.instances().size());
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) alive.insert(pedestrian.id);
    for (auto it = nodes_.begin(); it != nodes_.end();) {
        if (!alive.contains(it->first)) it = nodes_.erase(it);
        else ++it;
    }
}

void PedestrianDecisionSystem::sync_population(const PopulationSystem& population, PedestrianSystem& pedestrians,
                                               const NavigationNetwork& network, const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) {
    const std::size_t target = target_active_citizens(population);

    std::vector<std::uint64_t> active_ids;
    active_ids.reserve(pedestrians.instances().size());
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) active_ids.push_back(pedestrian.id);
    std::sort(active_ids.begin(), active_ids.end());

    // PopulationSystem remains authoritative. If population contracts, retire
    // the newest runtime actors first so older citizens keep their clothes,
    // budget identity and stable home assignment.
    while (active_ids.size() > target) {
        const std::uint64_t id = active_ids.back();
        active_ids.pop_back();
        (void)pedestrians.despawn_pedestrian(id);
        nodes_.erase(id);
    }

    std::vector<std::uint64_t> desired_homes;
    desired_homes.reserve(target);
    for (const BuildingInstance& building : buildings.instances()) {
        if (desired_homes.size() >= target) break;
        const BuildingDefinition* definition = catalog.find(building.definition_id);
        if (definition == nullptr ||
            building.current_level_definition(*definition).residential_capacity == 0) continue;
        const std::size_t assigned = population.residents_for(building, buildings, catalog);
        const std::size_t remaining = target - desired_homes.size();
        const std::size_t visible_here = std::min(assigned, remaining);
        desired_homes.insert(desired_homes.end(), visible_here, building.instance_id);
    }

    // Existing actors are matched deterministically to the aggregate residency
    // order. Rebuilding a district therefore does not reshuffle everyone each tick.
    const std::size_t existing_to_bind = std::min(active_ids.size(), desired_homes.size());
    for (std::size_t index = 0; index < existing_to_bind; ++index) {
        auto [it, inserted] = nodes_.try_emplace(active_ids[index]);
        if (inserted || it->second.pedestrian_id() != active_ids[index]) it->second.reset_for(active_ids[index]);
        it->second.set_home_id(desired_homes[index]);
    }

    // Materialize only residents that have a valid pedestrian entrance. A house
    // with broken access still counts in aggregate simulation exactly as before,
    // but it cannot emit a visible actor into an invalid navigation tile.
    for (std::size_t index = active_ids.size(); index < desired_homes.size(); ++index) {
        const std::uint64_t home = desired_homes[index];
        const std::optional<NavigationTile> entrance = PedestrianDecisionNode::home_entrance(
            home, buildings, catalog, network, std::nullopt);
        if (!entrance) continue;
        const std::optional<std::uint64_t> id = pedestrians.spawn_pedestrian(*entrance, network);
        if (!id) continue;
        (void)pedestrians.rest_at_home(*id, *entrance);
        PedestrianDecisionNode node;
        node.reset_for(*id);
        node.set_home_id(home);
        nodes_.insert_or_assign(*id, std::move(node));
    }

    prune_missing(pedestrians);
}

void PedestrianDecisionSystem::update(const float seconds, const PopulationSystem& population,
                                      PedestrianSystem& pedestrians, const NavigationNetwork& network,
                                      const BuildingManager& buildings, const BuildingCatalog& catalog,
                                      const RoadManager& roads, const SidewalkManager& sidewalks,
                                      const bool raining) {
    population_sync_seconds_ += std::max(0.0F, seconds);
    if (population_sync_seconds_ >= kPopulationSyncIntervalSeconds) {
        sync_population(population, pedestrians, network, buildings, catalog);
        population_sync_seconds_ = 0.0F;
    } else {
        prune_missing(pedestrians);
    }

    ++simulation_tick_;
    const float shard_seconds = std::max(0.0F, seconds) * static_cast<float>(PedestrianSystem::kDecisionShardCount);
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        if (!PedestrianSystem::decision_due(pedestrian.id, simulation_tick_)) continue;
        auto [it, inserted] = nodes_.try_emplace(pedestrian.id);
        if (inserted || it->second.pedestrian_id() != pedestrian.id) it->second.reset_for(pedestrian.id);
        it->second.update_for(pedestrian.id, shard_seconds, pedestrians, network,
                              buildings, catalog, roads, sidewalks, raining);
    }
}

std::optional<PedestrianDecision> PedestrianDecisionSystem::decision(const std::uint64_t pedestrian_id) const {
    const auto found = nodes_.find(pedestrian_id);
    return found == nodes_.end() ? std::nullopt : std::optional(found->second.decision());
}

std::optional<std::uint64_t> PedestrianDecisionSystem::home_id(const std::uint64_t pedestrian_id) const {
    const auto found = nodes_.find(pedestrian_id);
    return found == nodes_.end() ? std::nullopt : found->second.home_id();
}
