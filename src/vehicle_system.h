#pragma once

#include <filesystem>
#include <functional>
#include <string>
#include <string_view>
#include <unordered_set>
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
    // Logical movement/task progress is advanced by the fixed mobile tick.
    void update_tick(float tick_seconds, const ServiceVehicleCatalog& catalog, const TraversableTile& traversable);
    // Rendering calls this every frame to keep logical tick movement smooth.
    void interpolate_visual(float frame_seconds);
    // Frame-only visual update; task, route and field work remain on the
    // simulation tick in update_tick.
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
    [[nodiscard]] static std::string tile_key(int x, int y);
    [[nodiscard]] static std::string_view animation_state(ServiceVehicleState state);
    std::vector<ServiceVehicleInstance> instances_;
    std::vector<ServiceVehicleTask> tasks_;
    std::unordered_set<std::string> reserved_tiles_;
    std::vector<TileCoordinate> completed_tiles_;
    unsigned int next_task_number_ = 1;
};
