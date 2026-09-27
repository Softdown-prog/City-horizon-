#pragma once

#include "building_system.h"
#include "pedestrian_system.h"
#include "weather_system.h"

#include <cstdint>
#include <optional>
#include <random>

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

class PedestrianDecisionNode {
public:
    void reset();
    void update(float seconds, PedestrianSystem& pedestrians, const NavigationNetwork& network,
                const BuildingManager& buildings, const BuildingCatalog& catalog,
                const RoadManager& roads, const SidewalkManager& sidewalks, bool raining = false);
    [[nodiscard]] PedestrianDecision decision() const { return decision_; }
    [[nodiscard]] std::optional<std::uint64_t> home_id() const { return home_id_; }

    [[nodiscard]] static float outing_probability(WeatherState weather, bool essential_service_available);
    [[nodiscard]] static PedestrianOutingPreference preference_for_weather(
        WeatherState weather, bool essential_service_available);

private:
    [[nodiscard]] std::optional<NavigationTile> home_entrance(
        std::uint64_t id, const BuildingManager& buildings, const BuildingCatalog& catalog,
        const NavigationNetwork& network, std::optional<NavigationTile> from) const;
    [[nodiscard]] bool start_activity(NavigationTile from, PedestrianSystem& pedestrians,
                                      const NavigationNetwork& network);
    [[nodiscard]] bool essential_service_available(const BuildingManager& buildings,
                                                    const BuildingCatalog& catalog) const;
    [[nodiscard]] bool decide_to_leave(WeatherState weather, bool essential_service_available);

    PedestrianDecision decision_ = PedestrianDecision::looking_for_activity;
    std::optional<std::uint64_t> home_id_;
    float retry_seconds_ = 0.0F;
    std::mt19937 decision_rng_{0xC17A2026U};
};
