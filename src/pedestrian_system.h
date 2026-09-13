#pragma once

#include "mobile_animation.h"
#include "navigation_network.h"

#include <cstdint>
#include <string>
#include <vector>

enum class PedestrianState { idle, walking };

struct PedestrianVisualDefinition {
    std::string animation_set_id;
    float art_scale = 0.45F;
    float sprite_anchor_x = 0.5F;
    float sprite_anchor_y = 0.88F;
    // Per-visual tuning belongs to the presentation definition; navigation
    // still supplies the continuous route and never knows animation timing.
    float movement_speed_tiles_per_second = 2.25F;
    float animation_playback_rate = 1.0F;
    // A shared lane offset inside each road tile. It deliberately moves only
    // the ground contact, not the source sprite pivot or world projection.
    float lane_ground_anchor_x = 0.5F;
    float lane_ground_anchor_y = 0.5F;
};

struct PedestrianInstance {
    std::uint64_t id = 0;
    MobileEntitySpatialState spatial;
    PedestrianState state = PedestrianState::idle;
    std::vector<NavigationTile> route;
    std::size_t next_waypoint = 0;
    NavigationTile destination;
    float speed = 2.25F;
    bool replanned_after_network_change = false;
    MobileAnimationPlayer animation;
};

// Runtime-only, deliberately small proof that a mobile entity can consume a
// topology-backed network without putting pedestrian logic into navigation or
// rendering. It is not part of population/save gameplay yet.
class PedestrianSystem {
public:
    explicit PedestrianSystem(PedestrianVisualDefinition visual_definition);

    // Test-only visual retune: it reuses the same entity, route and catalogue
    // while resetting the player so a new cadence begins at frame zero.
    void configure_visual_test(PedestrianVisualDefinition visual_definition);

    [[nodiscard]] bool send_test_pedestrian(NavigationTile start, NavigationTile destination,
                                            const NavigationNetwork& network);
    void update_tick(float tick_seconds, const NavigationNetwork& network);
    void interpolate_visual(float frame_seconds);
    void update_animation(float frame_seconds, const MobileAnimationCatalog& animations);
    [[nodiscard]] std::vector<MobileEntityRenderData> render_entities(const MobileAnimationCatalog& animations) const;
    [[nodiscard]] const std::vector<PedestrianInstance>& instances() const;

private:
    [[nodiscard]] static MobileEntityDirection direction_to(NavigationTile from, NavigationTile to);
    [[nodiscard]] static std::string_view animation_state(PedestrianState state);
    [[nodiscard]] static bool remaining_route_is_valid(const PedestrianInstance& pedestrian, const NavigationNetwork& network);
    [[nodiscard]] bool replan_once_or_stop(PedestrianInstance& pedestrian, const NavigationNetwork& network);

    PedestrianVisualDefinition visual_definition_;
    std::vector<PedestrianInstance> instances_;
    std::uint64_t next_id_ = 1;
};
