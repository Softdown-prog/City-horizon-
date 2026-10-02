#pragma once

#include "building_system.h"
#include "pedestrian_system.h"
#include "weather_system.h"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <random>
#include <unordered_map>

class PopulationSystem;
class RoadManager;
class SidewalkManager;

// Citizen lifecycle V1:
// AtHome -> WalkingTo/visit -> WalkingHome -> AtHome.
// The weather test is performed only when AtHome rest expires. Once a route or
// visit has started, weather is intentionally ignored until the citizen returns.
enum class PedestrianDecision {
    looking_for_activity,
    walking_to_activity,
    awaiting_activity,
    returning_home,
    resting_at_home,
};

// Per-citizen decision state. The legacy update() entry point still controls
// the first actor for isolated tests/developer controls; production multi-agent
// code should call update_for() through PedestrianDecisionSystem.
class PedestrianDecisionNode {
public:
    void reset();
    void reset_for(std::uint64_t pedestrian_id);
    void set_home_id(std::optional<std::uint64_t> home_id) { home_id_ = home_id; }

    void update(float seconds, PedestrianSystem& pedestrians, const NavigationNetwork& network,
                const BuildingManager& buildings, const BuildingCatalog& catalog,
                const RoadManager& roads, const SidewalkManager& sidewalks, bool raining = false);
    void update_for(std::uint64_t pedestrian_id, float seconds, PedestrianSystem& pedestrians,
                    const NavigationNetwork& network, const BuildingManager& buildings,
                    const BuildingCatalog& catalog, const RoadManager& roads,
                    const SidewalkManager& sidewalks, bool raining = false);

    [[nodiscard]] PedestrianDecision decision() const { return decision_; }
    [[nodiscard]] std::optional<std::uint64_t> home_id() const { return home_id_; }
    [[nodiscard]] std::uint64_t pedestrian_id() const { return pedestrian_id_; }

    [[nodiscard]] static float outing_probability(WeatherState weather, bool essential_service_available);
    [[nodiscard]] static PedestrianOutingPreference preference_for_weather(
        WeatherState weather, bool essential_service_available);

private:
    friend class PedestrianDecisionSystem;

    [[nodiscard]] static std::optional<NavigationTile> home_entrance(
        std::uint64_t id, const BuildingManager& buildings, const BuildingCatalog& catalog,
        const NavigationNetwork& network, std::optional<NavigationTile> from);
    [[nodiscard]] bool start_activity(std::uint64_t pedestrian_id, NavigationTile from,
                                      PedestrianSystem& pedestrians, const NavigationNetwork& network);
    [[nodiscard]] bool essential_service_available(const BuildingManager& buildings,
                                                    const BuildingCatalog& catalog) const;
    [[nodiscard]] bool decide_to_leave(WeatherState weather, bool essential_service_available);
    void reseed_for(std::uint64_t pedestrian_id);

    std::uint64_t pedestrian_id_ = 0;
    PedestrianDecision decision_ = PedestrianDecision::looking_for_activity;
    std::optional<std::uint64_t> home_id_;
    float retry_seconds_ = 0.0F;
    std::mt19937 decision_rng_{0xC17A2026U};
};

// Scalable runtime controller. PopulationSystem stays authoritative for how
// many people live in the city; this layer materializes a bounded number of
// visible actors, gives each one independent home/decision state, and shards
// expensive decisions across simulation ticks.
class PedestrianDecisionSystem {
public:
    static constexpr std::size_t kMaxActiveCitizens = 256;
    static constexpr float kPopulationSyncIntervalSeconds = 1.0F;

    void reset();
    void sync_population(const PopulationSystem& population, PedestrianSystem& pedestrians,
                         const NavigationNetwork& network, const BuildingManager& buildings,
                         const BuildingCatalog& catalog);
    void update(float seconds, const PopulationSystem& population, PedestrianSystem& pedestrians,
                const NavigationNetwork& network, const BuildingManager& buildings,
                const BuildingCatalog& catalog, const RoadManager& roads,
                const SidewalkManager& sidewalks, bool raining = false);

    [[nodiscard]] std::size_t active_decision_count() const { return nodes_.size(); }
    [[nodiscard]] std::optional<PedestrianDecision> decision(std::uint64_t pedestrian_id) const;
    [[nodiscard]] std::optional<std::uint64_t> home_id(std::uint64_t pedestrian_id) const;
    [[nodiscard]] static std::size_t target_active_citizens(const PopulationSystem& population);

private:
    void prune_missing(const PedestrianSystem& pedestrians);

    std::unordered_map<std::uint64_t, PedestrianDecisionNode> nodes_;
    std::uint64_t simulation_tick_ = 0;
    float population_sync_seconds_ = kPopulationSyncIntervalSeconds;
};
