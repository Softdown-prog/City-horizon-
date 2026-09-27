#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <string_view>
#include <unordered_set>
#include <utility>
#include <vector>

#include "mobile_entity.h"
#include "mobile_animation.h"
#include "road_system.h"

using VehicleDirection = MobileEntityDirection;
enum class ServiceVehicleState { idle, moving_to_job, working, returning };

struct ServiceVehicleDefinition {
    std::string id;
    std::string display_name;
    std::string category;
    std::string role;
    int purchase_cost = 0;
    int monthly_maintenance = 0;
    float move_speed = 0.0F;
    float work_speed = 0.0F;
    std::string sprite_south;
    std::string sprite_east;
    std::string sprite_north;
    std::string sprite_west;
    std::string animation_set_id;
    bool requires_owned_farm_vehicle = true;
    std::string work_tool;
    float art_scale = 0.12F;
    float anchor_x = 0.5F;
    float anchor_y = 0.82F;
    [[nodiscard]] const std::string& sprite_for(VehicleDirection direction) const;
};

struct ServiceVehicleInstance {
    std::string vehicle_id;
    float map_x = 0.0F;
    float map_y = 0.0F;
    float visual_x = 0.0F;
    float visual_y = 0.0F;
    float origin_x = 0.0F;
    float origin_y = 0.0F;
    VehicleDirection direction = VehicleDirection::south;
    ServiceVehicleState state = ServiceVehicleState::idle;
    std::string task_id;
    bool owned = true;
    std::vector<TileCoordinate> route;
    std::size_t route_index = 0;
    float travel_progress = 0.0F;
    float work_progress = 0.0F;
    MobileAnimationPlayer animation;
};

struct ServiceVehicleTask {
    std::string id;
    std::string required_role;
    std::size_t vehicle_index = 0;
    std::vector<TileCoordinate> tiles;
    std::size_t next_tile = 0;
};

class ServiceVehicleCatalog {
public:
    bool load_from_directory(const std::filesystem::path& directory);
    [[nodiscard]] const ServiceVehicleDefinition* find(std::string_view id) const;
    [[nodiscard]] const std::vector<ServiceVehicleDefinition>& definitions() const;
private:
    std::vector<ServiceVehicleDefinition> definitions_;
};

class ServiceVehicleManager {
public:
    using TraversableTile = std::function<bool(int, int)>;
    [[nodiscard]] bool add(ServiceVehicleInstance instance, const ServiceVehicleCatalog& catalog);
    [[nodiscard]] bool has_idle_vehicle_for_role(std::string_view role, const ServiceVehicleCatalog& catalog) const;
    [[nodiscard]] bool create_task(std::string_view role, std::vector<TileCoordinate> tiles,
                                   const ServiceVehicleCatalog& catalog, const TraversableTile& traversable,
                                   std::string* assigned_vehicle_name = nullptr);
    [[nodiscard]] bool cancel_active_task(const ServiceVehicleCatalog& catalog, const TraversableTile& traversable);
    [[nodiscard]] bool is_reserved(int x, int y) const;
    [[nodiscard]] bool has_active_task() const;
    void update_tick(float tick_seconds, const ServiceVehicleCatalog& catalog, const TraversableTile& traversable);
    void interpolate_visual(float frame_seconds);
    void update_animation(float frame_seconds, const MobileAnimationCatalog& animations);
    [[nodiscard]] std::vector<MobileEntityRenderData> render_entities(const ServiceVehicleCatalog& catalog,
                                                                       const MobileAnimationCatalog& animations) const;
    [[nodiscard]] std::vector<TileCoordinate> take_completed_tiles();
    void clear();
    [[nodiscard]] const std::vector<ServiceVehicleInstance>& instances() const;
private:
    [[nodiscard]] std::vector<TileCoordinate> find_route(const TileCoordinate& from, const TileCoordinate& to,
                                                          const TraversableTile& traversable) const;
    void begin_return(ServiceVehicleInstance& vehicle, const ServiceVehicleCatalog& catalog,
                      const TraversableTile& traversable);
    [[nodiscard]] static std::uint64_t tile_key(int x, int y);
    [[nodiscard]] static std::string_view animation_state(ServiceVehicleState state);
    std::vector<ServiceVehicleInstance> instances_;
    std::vector<ServiceVehicleTask> tasks_;
    std::unordered_set<std::uint64_t> reserved_tiles_;
    std::vector<TileCoordinate> completed_tiles_;
    unsigned int next_task_number_ = 1;
};

// -----------------------------------------------------------------------------
// CH_ROAD_TRAFFIC_V1
// Lightweight city traffic contract. Runtime sprites stay 2D; this layer owns
// only the logical road anchor, right-hand lane offset, car-to-car separation
// and acceleration/braking. It deliberately does not own road topology.
// -----------------------------------------------------------------------------
enum class TrafficVehicleState { cruising, braking, stopped };

struct TrafficVehicleDefinition {
    std::string id = "vehicle.road.suv_01";
    float cruise_speed = 1.35F;       // tiles / second
    float acceleration = 1.10F;       // tiles / second^2
    float braking = 2.75F;            // tiles / second^2
    float safe_distance = 0.72F;      // logical anchor distance in tiles
    float look_ahead_time = 0.65F;    // adds speed-dependent stopping margin
    float lane_offset = 0.18F;        // right-hand traffic offset from tile centre
    float sprite_anchor_x = 0.5F;
    float sprite_anchor_y = 0.88F;    // ground contact under the wheels
};

struct TrafficVehicleInstance {
    std::string vehicle_id = "vehicle.road.suv_01";
    std::vector<TileCoordinate> route; // includes the spawn tile at index 0
    std::size_t segment_index = 0;     // segment route[i] -> route[i + 1]
    float segment_progress = 0.0F;     // 0..1 along current road segment
    float speed = 0.0F;
    float map_x = 0.0F;                // logical road/lane anchor
    float map_y = 0.0F;
    float visual_x = 0.0F;
    float visual_y = 0.0F;
    VehicleDirection direction = VehicleDirection::south;
    TrafficVehicleState state = TrafficVehicleState::stopped;
};

class TrafficVehicleManager {
public:
    [[nodiscard]] bool add(TrafficVehicleInstance instance,
                           const TrafficVehicleDefinition& definition,
                           const RoadManager& roads);
    void update_tick(float tick_seconds,
                     const TrafficVehicleDefinition& definition,
                     const RoadManager& roads);
    void interpolate_visual(float frame_seconds);
    void clear();
    [[nodiscard]] const std::vector<TrafficVehicleInstance>& instances() const;

    [[nodiscard]] static bool route_is_drivable(const std::vector<TileCoordinate>& route,
                                                const RoadManager& roads);
    [[nodiscard]] static std::pair<float, float> lane_anchor(const TileCoordinate& tile,
                                                              VehicleDirection direction,
                                                              float lane_offset);

private:
    [[nodiscard]] static VehicleDirection direction_between(const TileCoordinate& from,
                                                            const TileCoordinate& to);
    [[nodiscard]] bool vehicle_ahead(std::size_t index,
                                     float required_gap,
                                     float* distance = nullptr) const;
    void refresh_anchor(TrafficVehicleInstance& vehicle,
                        const TrafficVehicleDefinition& definition) const;

    std::vector<TrafficVehicleInstance> instances_;
};
