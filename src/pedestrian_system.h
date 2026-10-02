#pragma once

#include "mobile_animation.h"
#include "navigation_network.h"

#include <cstdint>
#include <optional>
#include <random>
#include <string>
#include <vector>

enum class PedestrianState { idle, walking, visiting, resting };

enum class PedestrianProfession : std::uint8_t {
    resident,
    cleaner,
};

enum class PedestrianOutingPreference : std::uint8_t {
    balanced,
    outdoor_leisure,
    covered_commerce,
    essential_commerce,
};

enum class PedestrianNeed : std::uint8_t {
    hunger,
    thirst,
    fun,
};

struct PedestrianNeeds {
    float hunger = 100.0F;
    float thirst = 100.0F;
    float fun = 100.0F;
};

struct PedestrianOutingIntent {
    bool active = false;
    PedestrianOutingPreference preference = PedestrianOutingPreference::balanced;
    PedestrianNeed priority_need = PedestrianNeed::hunger;
};

struct PedestrianVisualDefinition {
    std::string animation_set_id;
    float art_scale = 0.45F;
    float sprite_anchor_x = 0.5F;
    float sprite_anchor_y = 0.88F;
    float movement_speed_tiles_per_second = 2.25F;
    float animation_playback_rate = 1.0F;
    float lane_ground_anchor_x = 0.5F;
    float lane_ground_anchor_y = 0.5F;
};

struct PedestrianInstance {
    std::uint64_t id = 0;
    MobileEntitySpatialState spatial;
    PedestrianState state = PedestrianState::idle;
    PedestrianProfession profession = PedestrianProfession::resident;
    std::vector<NavigationTile> route;
    std::size_t next_waypoint = 0;
    NavigationTile destination;
    float speed = 2.25F;
    bool replanned_after_network_change = false;
    MobileAnimationPlayer animation;
    MobileClothingTint clothing;
    MobileClothingColor umbrella_color;

    std::int64_t monthly_budget_capacity_cents = 5'000;
    std::int64_t monthly_budget_cents = 5'000;
    PedestrianNeeds needs;
    PedestrianOutingIntent outing_intent;
};

class PedestrianSystem {
public:
    static constexpr std::int64_t kDefaultMonthlyBudgetCents = 5'000;
    static constexpr std::uint32_t kDecisionShardCount = 8;
    static constexpr float kNeedMaximum = 100.0F;
    static constexpr float kNeedDecayPerSecond = 1.0F;

    explicit PedestrianSystem(PedestrianVisualDefinition visual_definition);

    void configure_visual_test(PedestrianVisualDefinition visual_definition);

    [[nodiscard]] std::optional<std::uint64_t> spawn_pedestrian(
        NavigationTile at, const NavigationNetwork& network);
    [[nodiscard]] bool despawn_pedestrian(std::uint64_t pedestrian_id);
    [[nodiscard]] bool send_pedestrian(std::uint64_t pedestrian_id, NavigationTile start,
                                       NavigationTile destination, const NavigationNetwork& network);
    [[nodiscard]] bool send_pedestrian(NavigationTile start, NavigationTile destination,
                                       const NavigationNetwork& network);

    [[nodiscard]] bool set_visiting(std::uint64_t pedestrian_id, bool visiting);
    [[nodiscard]] bool face_pedestrian(std::uint64_t pedestrian_id, MobileEntityDirection direction);
    [[nodiscard]] bool set_profession(std::uint64_t pedestrian_id, PedestrianProfession profession);
    [[nodiscard]] bool rest_at_home(std::uint64_t pedestrian_id, NavigationTile entrance);
    [[nodiscard]] bool rest_at_home(NavigationTile entrance);
    void wake_up(std::uint64_t pedestrian_id);
    void wake_up();

    [[nodiscard]] bool authorize_outing(std::uint64_t pedestrian_id, PedestrianOutingPreference preference,
                                        PedestrianNeed priority_need);
    [[nodiscard]] bool authorize_outing(PedestrianOutingPreference preference, PedestrianNeed priority_need);
    void clear_outing_intent(std::uint64_t pedestrian_id);
    [[nodiscard]] bool spend_monthly_budget(std::uint64_t pedestrian_id, std::int64_t cents);
    [[nodiscard]] std::int64_t monthly_budget_cents(std::uint64_t pedestrian_id) const;
    [[nodiscard]] std::int64_t monthly_budget_capacity_cents(std::uint64_t pedestrian_id) const;
    void reset_monthly_budgets();
    void sync_monthly_budget_cycle(int month, int year);

    [[nodiscard]] PedestrianNeeds needs(std::uint64_t pedestrian_id) const;
    [[nodiscard]] PedestrianNeed priority_need(std::uint64_t pedestrian_id) const;
    [[nodiscard]] bool restore_need(std::uint64_t pedestrian_id, PedestrianNeed need, float points);

    [[nodiscard]] static std::int64_t budget_capacity_for(std::uint64_t pedestrian_id);
    [[nodiscard]] static std::uint32_t decision_shard_for(std::uint64_t pedestrian_id);
    [[nodiscard]] static bool decision_due(std::uint64_t pedestrian_id, std::uint64_t simulation_tick);

    void clear();
    void update_tick(float tick_seconds, const NavigationNetwork& network);
    void interpolate_visual(float frame_seconds);
    void update_animation(float frame_seconds, const MobileAnimationCatalog& animations);
    [[nodiscard]] std::vector<MobileEntityRenderData> render_entities(const MobileAnimationCatalog& animations,
                                                                       bool raining = false) const;
    [[nodiscard]] const std::vector<PedestrianInstance>& instances() const;

private:
    [[nodiscard]] PedestrianInstance* find_instance(std::uint64_t pedestrian_id);
    [[nodiscard]] const PedestrianInstance* find_instance(std::uint64_t pedestrian_id) const;
    [[nodiscard]] PedestrianInstance& create_pedestrian(NavigationTile at);
    void assign_route(PedestrianInstance& pedestrian, NavigationTile start,
                      NavigationTile destination, const NavigationPathResult& path);
    void decay_needs(float seconds);
    [[nodiscard]] static MobileEntityDirection direction_to(NavigationTile from, NavigationTile to);
    [[nodiscard]] static std::string_view animation_state(PedestrianState state);
    [[nodiscard]] static bool remaining_route_is_valid(const PedestrianInstance& pedestrian, const NavigationNetwork& network);
    [[nodiscard]] bool replan_once_or_stop(PedestrianInstance& pedestrian, const NavigationNetwork& network);

    PedestrianVisualDefinition visual_definition_;
    std::vector<PedestrianInstance> instances_;
    std::uint64_t next_id_ = 1;
    int budget_month_ = 0;
    int budget_year_ = 0;
    std::mt19937 clothing_rng_{std::random_device{}()};
};
