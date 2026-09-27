#pragma once

#include "building_system.h"
#include "pedestrian_system.h"

#include <cstdint>
#include <optional>

class RoadManager;
class SidewalkManager;

// One resident's small decision node: take a reachable walk, come home, rest.
// No job or needs simulation is implied by the current city population count.
enum class PedestrianDecision { looking_for_activity, walking_to_activity, awaiting_activity, returning_home, resting_at_home };

class PedestrianDecisionNode {
public:
    void reset();
    void update(float seconds, PedestrianSystem& pedestrians, const NavigationNetwork& network,
                const BuildingManager& buildings, const BuildingCatalog& catalog,
                const RoadManager& roads, const SidewalkManager& sidewalks);
    [[nodiscard]] PedestrianDecision decision() const { return decision_; }
    [[nodiscard]] std::optional<std::uint64_t> home_id() const { return home_id_; }

private:
    [[nodiscard]] std::optional<NavigationTile> home_entrance(
        std::uint64_t id, const BuildingManager& buildings, const BuildingCatalog& catalog,
        const NavigationNetwork& network, std::optional<NavigationTile> from) const;
    [[nodiscard]] bool start_activity(NavigationTile from, PedestrianSystem& pedestrians,
                                      const NavigationNetwork& network);

    PedestrianDecision decision_ = PedestrianDecision::looking_for_activity;
    std::optional<std::uint64_t> home_id_;
    float retry_seconds_ = 0.0F;
};
