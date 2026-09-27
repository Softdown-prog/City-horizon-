from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


# CMake: dedicated crosswalk implementation + focused traffic regression.
replace_once(
    "CMakeLists.txt",
    "    src/building_system.cpp\n    src/economy_system.cpp\n",
    "    src/building_system.cpp\n    src/crosswalk_system.cpp\n    src/economy_system.cpp\n",
)
replace_once(
    "CMakeLists.txt",
    "    add_executable(navigation_network_test\n        src/navigation_network_test.cpp\n        src/fence_system.cpp\n",
    "    add_executable(navigation_network_test\n        src/navigation_network_test.cpp\n        src/crosswalk_system.cpp\n        src/fence_system.cpp\n",
)
weather = """    add_executable(weather_system_test
        src/weather_system_test.cpp
        src/weather_system.cpp
    )
    add_test(NAME weather_system_test COMMAND weather_system_test)
"""
traffic = """    add_executable(vehicle_traffic_test
        src/vehicle_traffic_test.cpp
        src/building_system.cpp
        src/crosswalk_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/navigation_network.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )
    target_link_libraries(vehicle_traffic_test PRIVATE ch_core)
    add_test(NAME vehicle_traffic_test COMMAND vehicle_traffic_test)

""" + weather
replace_once("CMakeLists.txt", weather, traffic)

# Vehicle braking consumes the same logical conflict zone used by pedestrians.
replace_once(
    "src/vehicle_system.h",
    "using VehicleDirection = MobileEntityDirection;\nenum class ServiceVehicleState",
    "class CrosswalkManager;\n\nusing VehicleDirection = MobileEntityDirection;\nenum class ServiceVehicleState",
)
replace_once(
    "src/vehicle_system.h",
    """    void update_tick(float tick_seconds,
                     const TrafficVehicleDefinition& definition,
                     const RoadManager& roads);
""",
    """    void update_tick(float tick_seconds,
                     const TrafficVehicleDefinition& definition,
                     const RoadManager& roads,
                     const CrosswalkManager* crosswalks = nullptr);
""",
)
replace_once(
    "src/vehicle_system.h",
    """    [[nodiscard]] bool vehicle_ahead(std::size_t index,
                                     float required_gap,
                                     float* distance = nullptr) const;
""",
    """    [[nodiscard]] bool vehicle_ahead(std::size_t index,
                                     float required_gap,
                                     float* distance = nullptr) const;
    [[nodiscard]] bool occupied_crosswalk_ahead(std::size_t index,
                                                float required_gap,
                                                const CrosswalkManager& crosswalks) const;
""",
)
replace_once(
    "src/vehicle_system.cpp",
    '#include "vehicle_system.h"\n',
    '#include "vehicle_system.h"\n#include "crosswalk_system.h"\n',
)
replace_once(
    "src/vehicle_system.cpp",
    """    if (distance != nullptr) *distance = nearest;
    return found;
}

void TrafficVehicleManager::update_tick(const float tick_seconds,
                                        const TrafficVehicleDefinition& definition,
                                        const RoadManager& roads) {
""",
    """    if (distance != nullptr) *distance = nearest;
    return found;
}

bool TrafficVehicleManager::occupied_crosswalk_ahead(const std::size_t index,
                                                     const float required_gap,
                                                     const CrosswalkManager& crosswalks) const {
    if (index >= instances_.size()) return false;
    const TrafficVehicleInstance& vehicle = instances_[index];
    if (vehicle.route.empty() || vehicle.segment_index + 1 >= vehicle.route.size()) return false;

    float distance = 1.0F - std::clamp(vehicle.segment_progress, 0.0F, 1.0F);
    for (std::size_t route_index = vehicle.segment_index + 1;
         route_index < vehicle.route.size() && distance <= required_gap + 1.0F;
         ++route_index) {
        const TileCoordinate tile = vehicle.route[route_index];
        if (crosswalks.pedestrian_occupied(tile.x, tile.y) && distance <= required_gap) return true;
        distance += 1.0F;
    }
    return false;
}

void TrafficVehicleManager::update_tick(const float tick_seconds,
                                        const TrafficVehicleDefinition& definition,
                                        const RoadManager& roads,
                                        const CrosswalkManager* crosswalks) {
""",
)
replace_once(
    "src/vehicle_system.cpp",
    """        const float required_gap = definition.safe_distance + vehicle.speed * definition.look_ahead_time;
        const bool blocked = vehicle_ahead(i, required_gap);
""",
    """        const float required_gap = definition.safe_distance + vehicle.speed * definition.look_ahead_time;
        const bool blocked = vehicle_ahead(i, required_gap) ||
            (crosswalks != nullptr && occupied_crosswalk_ahead(i, required_gap, *crosswalks));
""",
)

# Traffic focused test.
replace_once(
    "src/vehicle_traffic_test.cpp",
    '#include "road_system.h"\n#include "vehicle_system.h"\n',
    '#include "crosswalk_system.h"\n#include "road_system.h"\n#include "vehicle_system.h"\n',
)
replace_once(
    "src/vehicle_traffic_test.cpp",
    """    assert(traffic.instances().front().speed > 0.0F);
    assert(traffic.instances().front().state == TrafficVehicleState::cruising);

    std::cout << "vehicle_traffic_test: PASS\\n";
""",
    """    assert(traffic.instances().front().speed > 0.0F);
    assert(traffic.instances().front().state == TrafficVehicleState::cruising);

    CrosswalkManager crosswalks{-16, 16};
    assert(crosswalks.place(3, 0, CrosswalkAxis::north_south, roads));
    crosswalks.set_pedestrian_occupied(3, 0, true);
    traffic.clear();
    TrafficVehicleInstance crossing_car;
    crossing_car.route = valid_route;
    crossing_car.speed = suv.cruise_speed;
    assert(traffic.add(crossing_car, suv, roads));
    bool crossing_brake = false;
    for (int i = 0; i < 40; ++i) {
        traffic.update_tick(0.10F, suv, roads, &crosswalks);
        const auto& car = traffic.instances().front();
        crossing_brake = crossing_brake || car.state == TrafficVehicleState::braking || car.state == TrafficVehicleState::stopped;
        assert(car.map_x < 3.0F);
    }
    assert(crossing_brake);
    const float stopped_speed = traffic.instances().front().speed;
    crosswalks.set_pedestrian_occupied(3, 0, false);
    for (int i = 0; i < 8; ++i) traffic.update_tick(0.10F, suv, roads, &crosswalks);
    assert(traffic.instances().front().speed > stopped_speed);

    std::cout << "vehicle_traffic_test: PASS\\n";
""",
)

# Pedestrian regression: ordinary road is forbidden; explicit crosswalk bridges it.
replace_once(
    "src/navigation_network_test.cpp",
    '#include "navigation_network.h"\n#include "park_fence_runtime.h"\n',
    '#include "crosswalk_system.h"\n#include "navigation_network.h"\n#include "park_fence_runtime.h"\n',
)
old_test = """void test_pedestrian_surface_route() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    assert(sidewalks.place_tile(1, 0, "sand_path"));
    assert(sidewalks.place_tile(2, 0, "dirt_path"));
    assert(roads.place_tile(3, 0));
    assert(roads.place_tile(3, 1));
    assert(sidewalks.place_tile(2, 1, "grass"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    assert_path(find_navigation_path(network, {0, 0}, {3, 1}), {0, 0}, {3, 1}, 5);
    assert(network.can_move({1, 0}, CardinalDirection::east));
    assert(!network.is_navigable({2, 1}));
    assert(!network.can_move({2, 0}, CardinalDirection::south));
    assert(sidewalks.remove_tile(1, 0));
    assert(find_navigation_path(network, {0, 0}, {3, 1}).status == NavigationPathStatus::no_path);
}
"""
new_test = """void test_pedestrian_surface_route() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 2, "concrete_01"));
    assert(roads.place_tile(1, 1));

    PedestrianSurfaceNavigationNetwork floors{roads, sidewalks};
    assert(!floors.is_navigable({1, 1}));
    assert(find_navigation_path(floors, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);

    CrosswalkManager crosswalks{-8, 8};
    PedestrianCrosswalkNavigationNetwork crossings{roads, sidewalks, crosswalks};
    assert(find_navigation_path(crossings, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);
    assert(crosswalks.place(1, 1, CrosswalkAxis::north_south, roads));
    assert(crosswalks.is_active_portal(1, 1, sidewalks));
    assert_path(find_navigation_path(crossings, {1, 0}, {1, 2}), {1, 0}, {1, 2}, 3);
    assert(crossings.can_move({1, 0}, CardinalDirection::south));
    assert(!crossings.can_move({1, 1}, CardinalDirection::east));

    assert(sidewalks.remove_tile(1, 2));
    assert(!crosswalks.is_active_portal(1, 1, sidewalks));
    assert(find_navigation_path(crossings, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);
}
"""
replace_once("src/navigation_network_test.cpp", old_test, new_test)

# UI PISO palette gains the two authored crossing axes.
old_ui = """    if (model.active_tool == UiTool::sidewalks) {
        const float button_y = toolbar_y + 39.0F;
        const float button_width = (context_width - 24.0F) / 3.0F;
        add_button({context_x + 6.0F, button_y, button_width, 28.0F}, "TERRA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "dirt_path", "dirt_path");
        add_button({context_x + 12.0F + button_width, button_y, button_width, 28.0F}, "AREIA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "sand_path", "sand_path");
        add_button({context_x + 18.0F + button_width * 2.0F, button_y, button_width, 28.0F}, "GRAMA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "grass", "grass");
    }
"""
new_ui = """    if (model.active_tool == UiTool::sidewalks) {
        const float button_y = toolbar_y + 39.0F;
        const float button_width = (context_width - 36.0F) / 5.0F;
        add_button({context_x + 4.0F, button_y, button_width, 28.0F}, "TERRA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "dirt_path", "dirt_path");
        add_button({context_x + 8.0F + button_width, button_y, button_width, 28.0F}, "AREIA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "sand_path", "sand_path");
        add_button({context_x + 12.0F + button_width * 2.0F, button_y, button_width, 28.0F}, "GRAMA", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "grass", "grass");
        add_button({context_x + 16.0F + button_width * 3.0F, button_y, button_width, 28.0F}, "FX N-S", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "crosswalk_ns", "crosswalk_ns");
        add_button({context_x + 20.0F + button_width * 4.0F, button_y, button_width, 28.0F}, "FX L-O", UiAction::select_sidewalk_style,
                   true, model.sidewalk_style == "crosswalk_ew", "crosswalk_ew");
    }
"""
replace_once("src/ui_manager_legacy_impl.inl", old_ui, new_ui)

# Runtime integration + free building placement.
replace_once(
    "src/main_runtime_impl.cpp",
    '#include "building_system.h"\n',
    '#include "building_system.h"\n#include "crosswalk_runtime.h"\n',
)
replace_once(
    "src/main_runtime_impl.cpp",
    """        return failure == PlacementFailure::none && affordable && !on_road && !on_sidewalk && !on_farm &&
               on_owned_land && on_allowed_terrain && has_road_access;
""",
    """        return failure == PlacementFailure::none && affordable && !on_road && !on_sidewalk && !on_farm &&
               on_owned_land && on_allowed_terrain;
""",
)
replace_once(
    "src/main_runtime_impl.cpp",
    """    if (!validation.has_road_access) {
        return validation.accepts_path_access ? "ROAD OR PATH ADJACENCY REQUIRED" : "ROAD AT ENTRANCE REQUIRED";
    }
""",
    "",
)
replace_once(
    "src/main_runtime_impl.cpp",
    """    std::string label = definition.requires_road_or_path_access
        ? "RUA OU CAMINHO ADJACENTE"
        : (definition.requires_road_access ? "RUA OBRIGATORIA" : "SEM RUA");
""",
    '    std::string label = "POSICIONAMENTO LIVRE";\n',
)

# Crosswalk is rendered as a transparent road decal, below people/buildings.
render_anchor = "void render_buildings(SDL_Renderer* renderer, const BuildingManager& manager, const BuildingCatalog& catalog,\n"
render_helper = """void render_crosswalks(SDL_Renderer* renderer, const CrosswalkManager& crosswalks,
                       TextureCache& textures, const std::filesystem::path& asset_root,
                       const Camera& camera, const float viewport_width, const float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    const bool quarter_turn = (camera_rotation_turns(camera.rotation) % 2U) != 0U;
    for (const CrosswalkPortal& portal : crosswalks.portals()) {
        CrosswalkAxis visual_axis = portal.axis;
        if (quarter_turn) {
            visual_axis = visual_axis == CrosswalkAxis::north_south
                ? CrosswalkAxis::east_west : CrosswalkAxis::north_south;
        }
        const std::filesystem::path path = asset_root / "assets/roads/crosswalk_01" /
            (visual_axis == CrosswalkAxis::north_south ? "crosswalk_south.png" : "crosswalk_east.png");
        const TextureAsset* texture = textures.load(renderer, path);
        if (texture != nullptr) {
            ch::MapRenderer::render_road_sprite(renderer, *texture, portal.tile_x, portal.tile_y,
                                                cs, viewport_width, viewport_height);
        }
    }
}

"""
replace_once("src/main_runtime_impl.cpp", render_anchor, render_helper + render_anchor)

replace_once(
    "src/main_runtime_impl.cpp",
    """            case UiAction::select_sidewalk_style:
                if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "grass") {
""",
    """            case UiAction::select_sidewalk_style:
                if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "grass" ||
                    action.payload == "crosswalk_ns" || action.payload == "crosswalk_ew") {
""",
)

old_floor = """                if (sidewalk_mode && sidewalk_dragging) {
                    int changed = 0, blocked = 0;
                    for (const TileCoordinate& tile : roads.line_between(sidewalk_drag_start,
                                                                           {released_tile.first, released_tile.second})) {
                        const SidewalkPlacementFailure failure = sidewalks.validate_placement(tile.x, tile.y, roads, buildings);
                        if (!lands.is_tile_owned(tile.x, tile.y) || !editable_ground(tile.x, tile.y) ||
                            (failure != SidewalkPlacementFailure::none &&
                             failure != SidewalkPlacementFailure::sidewalk_occupied) ||
                            farming.is_occupied(tile.x, tile.y)) {
                            ++blocked;
                            continue;
                        }
                        bool changed_tile = false;
                        if (sidewalk_style == "grass") {
                            changed_tile = sidewalks.remove_tile(tile.x, tile.y);
                        } else {
                            changed_tile = sidewalks.paint_tile(tile.x, tile.y, sidewalk_style);
                        }
                        if (restore_grass(tile.x, tile.y)) changed_tile = true;
                        if (changed_tile) ++changed;
                    }
"""
new_floor = """                if (sidewalk_mode && sidewalk_dragging) {
                    int changed = 0, blocked = 0;
                    const bool placing_crosswalk = sidewalk_style == "crosswalk_ns" || sidewalk_style == "crosswalk_ew";
                    for (const TileCoordinate& tile : roads.line_between(sidewalk_drag_start,
                                                                           {released_tile.first, released_tile.second})) {
                        if (placing_crosswalk) {
                            if (!lands.is_tile_owned(tile.x, tile.y) || !roads.is_drivable(tile.x, tile.y)) {
                                ++blocked;
                                continue;
                            }
                            const CrosswalkAxis axis = sidewalk_style == "crosswalk_ns"
                                ? CrosswalkAxis::north_south : CrosswalkAxis::east_west;
                            if (crosswalk_runtime::crosswalks().place(tile.x, tile.y, axis, roads)) ++changed;
                            else ++blocked;
                            continue;
                        }
                        const SidewalkPlacementFailure failure = sidewalks.validate_placement(tile.x, tile.y, roads, buildings);
                        if (!lands.is_tile_owned(tile.x, tile.y) || !editable_ground(tile.x, tile.y) ||
                            (failure != SidewalkPlacementFailure::none &&
                             failure != SidewalkPlacementFailure::sidewalk_occupied) ||
                            farming.is_occupied(tile.x, tile.y)) {
                            ++blocked;
                            continue;
                        }
                        bool changed_tile = false;
                        if (sidewalk_style == "grass") {
                            changed_tile = sidewalks.remove_tile(tile.x, tile.y);
                        } else {
                            changed_tile = sidewalks.paint_tile(tile.x, tile.y, sidewalk_style);
                        }
                        if (restore_grass(tile.x, tile.y)) changed_tile = true;
                        if (changed_tile) ++changed;
                    }
"""
replace_once("src/main_runtime_impl.cpp", old_floor, new_floor)

replace_once(
    "src/main_runtime_impl.cpp",
    """                            if (sidewalks.remove_tile(x, y)) ++removed_floors;
                            if (roads.remove_tile(x, y)) ++removed_roads;
""",
    """                            if (sidewalks.remove_tile(x, y)) ++removed_floors;
                            (void)crosswalk_runtime::crosswalks().remove(x, y);
                            if (roads.remove_tile(x, y)) ++removed_roads;
""",
)

replace_once(
    "src/main_runtime_impl.cpp",
    """            if (automatic_pedestrian) {
                pedestrian_decisions.update(scheduled.mobile_tick_seconds, pedestrians, pedestrian_surfaces,
                                            buildings, catalog, roads, sidewalks, weather.is_raining());
            }
""",
    """            if (automatic_pedestrian) {
                pedestrian_decisions.update(scheduled.mobile_tick_seconds, pedestrians, pedestrian_surfaces,
                                            buildings, catalog, roads, sidewalks, weather.is_raining());
            }
            crosswalk_runtime::crosswalks().clear_occupancy();
            for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
                const int px = pedestrian.spatial.logical_tile_x;
                const int py = pedestrian.spatial.logical_tile_y;
                if (crosswalk_runtime::crosswalks().is_crosswalk(px, py)) {
                    crosswalk_runtime::crosswalks().set_pedestrian_occupied(px, py, true);
                }
            }
""",
)

replace_once(
    "src/main_runtime_impl.cpp",
    """        render_roads(renderer, roads, road_visuals, textures, asset_root, camera,
                     static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_sidewalks(renderer, sidewalks, textures, asset_root, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
""",
    """        render_roads(renderer, roads, road_visuals, textures, asset_root, camera,
                     static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_crosswalks(renderer, crosswalk_runtime::crosswalks(), textures, asset_root, camera,
                          static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_sidewalks(renderer, sidewalks, textures, asset_root, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
""",
)

# Any road demolition invalidates a crosswalk on the same tile.
# New-city reset is intentionally added only if the current action block has the known shape.
main_path = Path("src/main_runtime_impl.cpp")
main_text = main_path.read_text()
needle = "case UiAction::start_new_city:"
if needle in main_text and "crosswalk_runtime::clear();" not in main_text:
    pos = main_text.index(needle)
    clear_pos = main_text.find("pedestrians.clear();", pos, pos + 1200)
    if clear_pos != -1:
        line_end = main_text.find("\n", clear_pos)
        main_text = main_text[: line_end + 1] + "                crosswalk_runtime::clear();\n" + main_text[line_end + 1 :]
        main_path.write_text(main_text)

print("crosswalk integration patch applied")
