#pragma once

#include "mobile_animation.h"
#include "navigation_network.h"

#include <cstdint>
#include <optional>
#include <random>
#include <string>
#include <vector>

enum class PedestrianState { idle, walking, visiting, resting };

enum class PedestrianOutingPreference : std::uint8_t {
    balanced,
    outdoor_leisure,
    covered_commerce,
    essential_commerce,
};

struct PedestrianOutingIntent {
    bool active = false;
    PedestrianOutingPreference preference = PedestrianOutingPreference::balanced;
};

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
    MobileClothingTint clothing;
    MobileClothingColor umbrella_color;

    // Citizen Economy V2. Currency is stored in cents so CH_SERVICE_PRICE_V1
    // can be charged exactly without migrating the aggregate city treasury.
    // Each citizen keeps an authored-by-rule monthly allowance; there is no
    // explicit social-class gameplay model, profession or salary location.
    std::int64_t monthly_budget_capacity_cents = 5'000;
    std::int64_t monthly_budget_cents = 5'000;
    PedestrianOutingIntent outing_intent;
};

// Runtime pedestrians remain contiguous in one vector for cache locality. The
// legacy no-id helpers still target the first actor, while id-addressable APIs
// let the same storage safely scale to many simultaneously active citizens.
class PedestrianSystem {
public:
    static constexpr std::int64_t kDefaultMonthlyBudgetCents = 5'000; // lowest household-spending baseline.
    static constexpr std::int64_t kMiddleMonthlyBudgetCents = 9'000;
    static constexpr std::int64_t kUpperMonthlyBudgetCents = 15'000;
    static constexpr std::int64_t kHighMonthlyBudgetCents = 20'000;
    static constexpr std::uint32_t kDecisionShardCount = 8;

    explicit PedestrianSystem(PedestrianVisualDefinition visual_definition);

    // Debug visual retune reuses the same entities and routes.
    void configure_visual_test(PedestrianVisualDefinition visual_definition);

    // Multi-citizen foundation. Spawn creates one idle actor at a valid
    // navigation tile; routing/behaviour commands can then address that actor by id.
    [[nodiscard]] std::optional<std::uint64_t> spawn_pedestrian(
        NavigationTile at, const NavigationNetwork& network);
    [[nodiscard]] bool send_pedestrian(std::uint64_t pedestrian_id, NavigationTile start,
                                       NavigationTile destination, const NavigationNetwork& network);
    [[nodiscard]] bool send_pedestrian(NavigationTile start, NavigationTile destination,
                                       const NavigationNetwork& network);

    // Building visits protect an idle pedestrian from the ordinary autonomous
    // route scheduler while it aligns to the door or remains hidden inside.
    // Presentation resolves this state through the normal idle directional clip.
    [[nodiscard]] bool set_visiting(std::uint64_t pedestrian_id, bool visiting);
    // Door alignment changes only presentation facing. It never moves the foot
    // contact and therefore cannot bypass the navigation surface contract.
    [[nodiscard]] bool face_pedestrian(std::uint64_t pedestrian_id, MobileEntityDirection direction);
    // Rest only at the home's walkable entrance after arriving there.
    [[nodiscard]] bool rest_at_home(std::uint64_t pedestrian_id, NavigationTile entrance);
    [[nodiscard]] bool rest_at_home(NavigationTile entrance);
    void wake_up(std::uint64_t pedestrian_id);
    void wake_up();

    // A citizen may decide to leave only while resting at home. The visit bridge
    // consumes this one-shot intent when it starts a concrete destination route.
    [[nodiscard]] bool authorize_outing(std::uint64_t pedestrian_id, PedestrianOutingPreference preference);
    [[nodiscard]] bool authorize_outing(PedestrianOutingPreference preference);
    void clear_outing_intent(std::uint64_t pedestrian_id);
    [[nodiscard]] bool spend_monthly_budget(std::uint64_t pedestrian_id, std::int64_t cents);
    [[nodiscard]] std::int64_t monthly_budget_cents(std::uint64_t pedestrian_id) const;
    [[nodiscard]] std::int64_t monthly_budget_capacity_cents(std::uint64_t pedestrian_id) const;
    [[nodiscard]] static std::int64_t budget_capacity_for_id(std::uint64_t pedestrian_id);
    void reset_monthly_budgets();
    // Observe the game calendar once from any runtime call site. The system owns
    // the last-seen month/year, so multiple render paths cannot reset a budget twice.
    void sync_monthly_budget_cycle(int month, int year);

    // Stable deterministic time slicing: expensive citizen decisions may process
    // one shard per simulation tick while route movement continues every mobile tick.
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
