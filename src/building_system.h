#pragma once

#include <array>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

enum class BuildingRotation : std::uint8_t {
    r0 = 0,
    r90 = 1,
    r180 = 2,
    r270 = 3,
};

enum class GridDirection : std::uint8_t {
    north = 0,
    east = 1,
    south = 2,
    west = 3,
};

// Road access is a placement contract, not a rendering convention.  It lets
// content choose between a whole building facade, named doors/driveways, or
// the permissive legacy perimeter rule.
enum class RoadAccessMode : std::uint8_t {
    any_perimeter,
    access_points,
    front_edge,
};

struct BuildingFootprint {
    int width = 1;
    int height = 1;
};

// local_x/local_y identify a tile inside the unrotated footprint. facing points
// from that tile to the adjacent access tile outside the building footprint.
struct BuildingAccessPoint {
    int local_x = 0;
    int local_y = 0;
    GridDirection facing = GridDirection::south;
};

// Optional data-only placement for a new city.  It removes the need for the
// application bootstrap to know a concrete building id or its coordinates.
struct InitialBuildingPlacement {
    int tile_x = 0;
    int tile_y = 0;
    BuildingRotation rotation = BuildingRotation::r0;
};

struct BuildingResourceInput {
    std::string resource_id;
    int amount_per_month = 0;
    std::int64_t local_supply_bonus = 0;
};

struct BuildingLevelDefinition {
    int level = 1;
    std::int64_t upgrade_cost = 0;
    std::uint32_t residential_capacity = 0;
    std::uint32_t power_consumption = 0;
    std::int64_t maintenance_per_month = 0;
    std::int64_t tax_revenue_per_month = 0;

    std::array<std::string, 4> sprite_paths;
    std::array<float, 4> sprite_anchor_x = {0.5F, 0.5F, 0.5F, 0.5F};
    std::array<float, 4> sprite_anchor_y = {1.0F, 1.0F, 1.0F, 1.0F};
};

struct BuildingAnimationDefinition {
    int frame_count = 1;
    int frame_duration_ms = 120;
    std::string layout = "horizontal";
    // "loop" preserves the legacy continuous animation contract.
    // "ambient_once" holds an idle frame, plays one action sequence, then
    // returns to idle before the next deterministic ambient cycle.
    std::string playback = "loop";
    int idle_frame = 0;
    int action_start_frame = 1;
    int action_frame_count = 0;
    int idle_hold_ms = 0;
};

struct BuildingDefinition {
    std::string id;
    std::string name;
    std::string category;
    // Legacy single-sprite definitions use this path for every logical rotation.
    std::string texture_path;
    std::array<std::string, 4> sprite_paths;
    // Empty sprite entries are intentionally unavailable. Placement rotation
    // skips them; the renderer never invents a mirrored or rotated texture.
    std::array<bool, 4> available_rotations = {true, true, true, true};
    bool rotatable = false;
    // New player placement must have a road next to the logical footprint when
    // this is true. Save restoration deliberately does not retroactively apply
    // this gameplay rule to older cities.
    bool requires_road_access = false;
    // Small roadside/pathside props may accept either a road edge or a path
    // edge while still occupying their own grass tile. This is independent
    // from the stricter building entrance road contract above.
    bool requires_road_or_path_access = false;
    bool grass_only = false;
    RoadAccessMode road_access_mode = RoadAccessMode::any_perimeter;
    // Lets code distinguish absent legacy data from an explicit
    // roadAccessMode: "any_perimeter" declaration.
    bool road_access_mode_explicit = false;
    std::optional<GridDirection> front_edge;
    int footprint_width = 1;
    int footprint_height = 1;
    std::int64_t build_cost = 0;
    std::int64_t maintenance_per_month = 0;
    std::int64_t tax_revenue_per_month = 0;
    // Annual property tax paid by each instance during the fiscal month. It is
    // deliberately independent from population occupancy.
    std::int64_t property_tax_per_year = 0;
    // Zero disables population-driven commercial demand. Commercial revenue
    // reaches its configured total when current population reaches this value.
    std::uint32_t required_population_for_full_revenue = 0;
    // Optional player-controlled customer price. Zero disables service pricing.
    std::string service_name;
    std::int64_t default_service_price = 0;
    std::int64_t minimum_service_price = 0;
    std::int64_t maximum_service_price = 0;
    // Zero for non-residential definitions. Capacity is owned by the
    // PopulationSystem; it does not determine property-tax revenue.
    std::uint32_t residential_capacity = 0;
    // Global infrastructure values, rebuilt by PowerSystem from active
    // instances. Zero means this building neither consumes nor produces power.
    std::uint32_t power_consumption = 0;
    std::uint32_t power_production = 0;
    std::uint32_t generation_capacity = 0;
    std::uint32_t water_intake_capacity = 0;
    bool preplaced = false;
    bool player_buildable = true;
    std::string unlock_requirement;
    std::uint32_t agricultural_storage_capacity = 0;
    std::uint32_t grain_storage_capacity = 0;
    bool provides_agricultural_storage = false;
    std::string agricultural_infrastructure_role;
    std::vector<std::string> accepted_storage_classes;
    std::vector<BuildingResourceInput> resource_inputs;
    float art_scale = 1.0F;
    float anchor_x = 0.5F;
    float anchor_y = 1.0F;
    // Authored directional sprites often have different transparent padding.
    // These anchors align the visible ground contact per frame while keeping a
    // definition's old single `anchor` fully backwards compatible.
    std::array<float, 4> sprite_anchor_x = {0.5F, 0.5F, 0.5F, 0.5F};
    std::array<float, 4> sprite_anchor_y = {1.0F, 1.0F, 1.0F, 1.0F};
    std::vector<BuildingAccessPoint> access_points;
    std::optional<InitialBuildingPlacement> initial_placement;
    std::optional<BuildingAnimationDefinition> animation;

    // Multi-level progression data (Nível 1 a Nível N).
    std::vector<BuildingLevelDefinition> levels;

    [[nodiscard]] const BuildingLevelDefinition& level_definition(int level = 1) const;
    [[nodiscard]] const std::string& texture_path_for(BuildingRotation rotation, int level = 1) const;
    [[nodiscard]] float anchor_x_for(BuildingRotation rotation, int level = 1) const;
    [[nodiscard]] float anchor_y_for(BuildingRotation rotation, int level = 1) const;
    [[nodiscard]] bool supports_rotation(BuildingRotation rotation) const;
    [[nodiscard]] BuildingRotation next_supported_rotation(BuildingRotation rotation, bool clockwise) const;
};

class CityEconomy;
struct GameDate;

struct BuildingInstance {
    std::uint64_t instance_id = 0;
    std::string definition_id;
    int tile_x = 0;
    int tile_y = 0;

    // Persist this logical orientation. The renderer selects a pre-rendered PNG;
    // it never rotates a texture at runtime.
    BuildingRotation rotation = BuildingRotation::r0;
    int current_level = 1;
    bool operational = true;
    // Per-instance customer price so two shops may use different strategies.
    std::int64_t service_price = 0;

    [[nodiscard]] bool is_max_level(const BuildingDefinition& definition) const;
    [[nodiscard]] const BuildingLevelDefinition& current_level_definition(const BuildingDefinition& definition) const;
    [[nodiscard]] const BuildingLevelDefinition* next_level_definition(const BuildingDefinition& definition) const;
    [[nodiscard]] bool try_upgrade(const BuildingDefinition& definition, CityEconomy& economy, const GameDate& date);
};

[[nodiscard]] BuildingRotation rotate_clockwise(BuildingRotation rotation);
[[nodiscard]] BuildingRotation rotate_counter_clockwise(BuildingRotation rotation);
[[nodiscard]] const char* rotation_label(BuildingRotation rotation);
[[nodiscard]] BuildingFootprint rotated_footprint(const BuildingDefinition& definition, BuildingRotation rotation);
[[nodiscard]] BuildingAccessPoint rotate_access_point(const BuildingDefinition& definition,
                                                       BuildingAccessPoint access_point,
                                                       BuildingRotation rotation);
[[nodiscard]] std::vector<BuildingAccessPoint> rotated_access_points(const BuildingDefinition& definition,
                                                                       BuildingRotation rotation);
[[nodiscard]] RoadAccessMode resolved_road_access_mode(const BuildingDefinition& definition);
[[nodiscard]] const char* road_access_mode_label(RoadAccessMode mode);
[[nodiscard]] std::vector<BuildingAccessPoint> front_edge_access_points(const BuildingDefinition& definition,
                                                                           BuildingRotation rotation);
[[nodiscard]] std::vector<BuildingAccessPoint> road_access_candidates(const BuildingDefinition& definition,
                                                                         BuildingRotation rotation);

class BuildingCatalog {
public:
    bool load_from_directory(const std::filesystem::path& directory);
    [[nodiscard]] const BuildingDefinition* find(std::string_view id) const;
    [[nodiscard]] const std::vector<BuildingDefinition>& definitions() const;

private:
    std::vector<BuildingDefinition> definitions_;
};

enum class PlacementFailure {
    none,
    unavailable_rotation,
    outside_map,
    occupied,
};

class BuildingManager {
public:
    BuildingManager(int map_min, int map_max);

    [[nodiscard]] PlacementFailure validate(const BuildingDefinition& definition, int tile_x, int tile_y,
                                            BuildingRotation rotation = BuildingRotation::r0) const;
    [[nodiscard]] std::optional<std::uint64_t> place(const BuildingDefinition& definition, int tile_x, int tile_y,
                                                      BuildingRotation rotation = BuildingRotation::r0);
    // Load-only reconstruction: preserves serialized ids while rebuilding the
    // normal occupancy map through the same footprint validation as placement.
    [[nodiscard]] bool restore_instance(const BuildingDefinition& definition, const BuildingInstance& instance);
    void clear();
    void set_next_instance_id(std::uint64_t next_instance_id);
    [[nodiscard]] std::uint64_t next_instance_id() const;
    [[nodiscard]] const BuildingInstance* find_by_id(std::uint64_t instance_id) const;
    [[nodiscard]] const BuildingInstance* instance_at(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_occupied(int tile_x, int tile_y) const;
    [[nodiscard]] bool remove_instance(const BuildingDefinition& definition, std::uint64_t instance_id);
    [[nodiscard]] bool set_operational(std::uint64_t instance_id, bool operational);
    [[nodiscard]] bool set_service_price(std::uint64_t instance_id, const BuildingDefinition& definition,
                                         std::int64_t service_price);
    std::size_t set_operational_by_definition(std::string_view definition_id, bool operational);
    [[nodiscard]] const std::vector<BuildingInstance>& instances() const;

private:
    [[nodiscard]] bool is_inside_map(int tile_x, int tile_y) const;
    [[nodiscard]] int tile_key(int tile_x, int tile_y) const;

    int map_min_;
    int map_max_;
    std::uint64_t next_instance_id_ = 1;
    std::vector<BuildingInstance> instances_;
    std::unordered_map<int, std::uint64_t> occupancy_;
};
