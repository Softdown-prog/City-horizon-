#include "building_system.h"
#include "economy_system.h"
#include "road_system.h"

#include <iostream>

namespace {

bool require(bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) {
        return 1;
    }

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "catalog loads JSON definitions")) {
        return 1;
    }
    const BuildingDefinition* cafe = catalog.find("cafe_01");
    if (!require(cafe != nullptr, "cafe_01 definition is available") ||
        !require(cafe->footprint_width == 2 && cafe->footprint_height == 2, "footprint comes from JSON") ||
        !require(cafe->required_population_for_full_revenue == 20,
                 "cafe commercial demand requirement comes from JSON") ||
        !require(cafe->power_consumption == 3 && cafe->power_production == 0,
                 "cafe power consumption comes from JSON") ||
        !require(cafe->requires_road_access, "cafe requires logical road access for new placement") ||
        !require(resolved_road_access_mode(*cafe) == RoadAccessMode::any_perimeter,
                 "cafe declares any_perimeter road access contract") ||
        !require(!cafe->rotatable, "cafe is a fixed-orientation building") ||
        !require(cafe->texture_path_for(BuildingRotation::r0) == "assets/buildings/cafe_01_lvl1.png" &&
                 cafe->texture_path_for(BuildingRotation::r90) == "assets/buildings/cafe_01_lvl1.png",
                 "cafe resolves the canonical single sprite for any rotation")) {
        return 1;
    }

    const BuildingDefinition* house = catalog.find("house_suburban_01");
    if (!require(house != nullptr, "house_suburban_01 definition is available") ||
        !require(house->name == "Casa Suburbana" && house->category == "residential", "house identity comes from JSON") ||
        !require(house->footprint_width == 2 && house->footprint_height == 2 && !house->rotatable,
                 "house is a non-rotatable 2x2 building") ||
        !require(house->build_cost == 1'800 && house->tax_revenue_per_month == 0 &&
                     house->maintenance_per_month == 0 && house->property_tax_per_year == 240 &&
                     house->residential_capacity == 4 && house->power_consumption == 1 &&
                     house->power_production == 0 && house->requires_road_access,
                 "house economics come from JSON") ||
        !require(house->texture_path_for(BuildingRotation::r0) == "assets/buildings/house_suburban_01_lvl1.png" &&
                     house->texture_path_for(BuildingRotation::r90) == "assets/buildings/house_suburban_01_lvl1.png" &&
                     house->texture_path_for(BuildingRotation::r180) == "assets/buildings/house_suburban_01_lvl1.png" &&
                     house->texture_path_for(BuildingRotation::r270) == "assets/buildings/house_suburban_01_lvl1.png",
                 "house resolves single canonical PNG for all rotations")) {
        return 1;
    }

    const BuildingDefinition* second_house = catalog.find("house_suburban_02");
    if (!require(second_house != nullptr, "house_suburban_02 definition is available") ||
        !require(second_house->name == "Casa Suburbana 02" && second_house->category == "residential" &&
                     second_house->footprint_width == 2 && second_house->footprint_height == 2 &&
                     !second_house->rotatable && second_house->requires_road_access,
                 "second house uses the HUI V2 fixed-orientation contract") ||
        !require(second_house->texture_path_for(BuildingRotation::r0) ==
                     "assets/buildings/house_suburban_02_lvl1.png" &&
                     second_house->texture_path_for(BuildingRotation::r90) ==
                         "assets/buildings/house_suburban_02_lvl1.png" &&
                     second_house->texture_path_for(BuildingRotation::r180) ==
                         "assets/buildings/house_suburban_02_lvl1.png" &&
                     second_house->texture_path_for(BuildingRotation::r270) ==
                         "assets/buildings/house_suburban_02_lvl1.png",
                 "second house resolves single canonical PNG for all rotations")) {
        return 1;
    }

    const BuildingDefinition* bakery = catalog.find("bakery_01");
    if (!require(bakery != nullptr, "bakery_01 definition is available") ||
        !require(bakery->name == "Padaria" && bakery->category == "commercial" &&
                     bakery->footprint_width == 2 && bakery->footprint_height == 2 && !bakery->rotatable &&
                     bakery->requires_road_access,
                 "bakery uses the generic commercial definition contract") ||
        !require(bakery->texture_path_for(BuildingRotation::r0) == "assets/buildings/bakery_01_lvl1.png" &&
                     bakery->texture_path_for(BuildingRotation::r90) == "assets/buildings/bakery_01_lvl1.png",
                 "bakery resolves the canonical single sprite for any rotation")) {
        return 1;
    }

    const BuildingDefinition* city_hall = catalog.find("city_hall_01");
    if (!require(city_hall != nullptr, "city_hall_01 definition is available") ||
        !require(city_hall->name == "Prefeitura" && city_hall->category == "civic" &&
                     city_hall->footprint_width == 3 && city_hall->footprint_height == 3 && !city_hall->rotatable &&
                     city_hall->requires_road_access && city_hall->power_consumption == 4,
                 "city hall uses the generic civic definition contract") ||
        !require(city_hall->texture_path_for(BuildingRotation::r0) == "assets/buildings/city_hall_01_lvl1.png" &&
                     city_hall->texture_path_for(BuildingRotation::r90) == "assets/buildings/city_hall_01_lvl1.png",
                 "city hall selects the canonical single PNG for any logical rotation")) {
        return 1;
    }

    const BuildingDefinition* mini_market = catalog.find("mini_market_01");
    if (!require(mini_market != nullptr, "mini_market_01 definition is available") ||
        !require(mini_market->name == "Mercearia" && mini_market->category == "commercial" &&
                     mini_market->footprint_width == 2 && mini_market->footprint_height == 2 &&
                     !mini_market->rotatable && mini_market->requires_road_access,
                 "mini market uses the HUI V2 fixed-orientation contract") ||
        !require(mini_market->texture_path_for(BuildingRotation::r0) == "assets/buildings/mini_market_01_lvl1.png" &&
                     mini_market->texture_path_for(BuildingRotation::r90) == "assets/buildings/mini_market_01_lvl1.png" &&
                     mini_market->texture_path_for(BuildingRotation::r180) == "assets/buildings/mini_market_01_lvl1.png" &&
                     mini_market->texture_path_for(BuildingRotation::r270) == "assets/buildings/mini_market_01_lvl1.png",
                 "mini market resolves single canonical PNG for all rotations")) {
        return 1;
    }

    const BuildingDefinition* gas_station = catalog.find("gas_station_01");
    if (!require(gas_station != nullptr, "gas_station_01 definition is available") ||
        !require(gas_station->name == "Posto de Gasolina" && gas_station->category == "commercial" &&
                     gas_station->footprint_width == 2 && gas_station->footprint_height == 2 &&
                     !gas_station->rotatable && gas_station->requires_road_access,
                 "gas station uses the HUI V2 fixed-orientation contract") ||
        !require(gas_station->texture_path_for(BuildingRotation::r0) == "assets/buildings/gas_station_01_lvl1.png" &&
                     gas_station->texture_path_for(BuildingRotation::r90) == "assets/buildings/gas_station_01_lvl1.png" &&
                     gas_station->texture_path_for(BuildingRotation::r180) == "assets/buildings/gas_station_01_lvl1.png" &&
                     gas_station->texture_path_for(BuildingRotation::r270) == "assets/buildings/gas_station_01_lvl1.png",
                 "single gas station sprite used for all rotations")) {
        return 1;
    }

    const BuildingDefinition* plaza = catalog.find("plaza_01");
    if (!require(plaza != nullptr, "plaza_01 definition is available") ||
        !require(plaza->name == "Praça" && plaza->category == "civic" &&
                     plaza->footprint_width == 3 && plaza->footprint_height == 3 &&
                     !plaza->rotatable && !plaza->requires_road_access &&
                     plaza->texture_path_for(BuildingRotation::r0) == "assets/buildings/plaza_01_rot0.png",
                 "plaza is a fixed civic building without a road requirement")) {
        return 1;
    }

    const BuildingDefinition* basic_school = catalog.find("basic_school_01");
    if (!require(basic_school != nullptr, "basic_school_01 definition is available") ||
        !require(basic_school->name == "Escola Básica" && basic_school->category == "civic" &&
                     basic_school->footprint_width == 2 && basic_school->footprint_height == 2 &&
                     !basic_school->rotatable && basic_school->requires_road_access &&
                     basic_school->power_consumption == 6,
                 "basic school uses the generic civic definition contract") ||
        !require(basic_school->texture_path_for(BuildingRotation::r0) == "assets/buildings/basic_school_01_lvl1.png" &&
                     basic_school->texture_path_for(BuildingRotation::r90) == "assets/buildings/basic_school_01_lvl1.png",
                 "basic school selects the canonical single PNG for any logical rotation")) {
        return 1;
    }

    const BuildingDefinition* clinic = catalog.find("clinic_small_01");
    if (!require(clinic != nullptr, "clinic_small_01 definition is available") ||
        !require(clinic->name == "Clínica Pequena" && clinic->category == "civic" &&
                     clinic->footprint_width == 2 && clinic->footprint_height == 2 &&
                     !clinic->rotatable && clinic->requires_road_access && clinic->power_consumption == 5,
                 "small clinic uses the generic civic definition contract") ||
        !require(clinic->texture_path_for(BuildingRotation::r0) == "assets/buildings/clinic_small_01_lvl1.png" &&
                     clinic->texture_path_for(BuildingRotation::r90) == "assets/buildings/clinic_small_01_lvl1.png",
                 "small clinic selects the canonical single PNG for any logical rotation")) {
        return 1;
    }

    const BuildingDefinition* fire_station = catalog.find("fire_station_small_01");
    if (!require(fire_station != nullptr, "fire_station_small_01 definition is available") ||
        !require(fire_station->name == "Corpo de Bombeiros Pequeno" && fire_station->category == "civic" &&
                     fire_station->footprint_width == 2 && fire_station->footprint_height == 2 &&
                     !fire_station->rotatable && fire_station->requires_road_access &&
                     fire_station->power_consumption == 6,
                 "small fire station uses the generic civic definition contract") ||
        !require(fire_station->texture_path_for(BuildingRotation::r0) == "assets/buildings/fire_station_small_01_lvl1.png" &&
                     fire_station->texture_path_for(BuildingRotation::r90) == "assets/buildings/fire_station_small_01_lvl1.png",
                 "small fire station selects the canonical single PNG for any logical rotation")) {
        return 1;
    }

    BuildingDefinition rectangular;
    rectangular.id = "rotation_test";
    rectangular.name = "Rotation test";
    rectangular.category = "test";
    rectangular.texture_path = "assets/buildings/rotation_test_r0.png";
    rectangular.sprite_paths = {
        "assets/buildings/rotation_test_r0.png", "assets/buildings/rotation_test_r1.png",
        "assets/buildings/rotation_test_r2.png", "assets/buildings/rotation_test_r3.png",
    };
    rectangular.rotatable = true;
    rectangular.footprint_width = 2;
    rectangular.footprint_height = 3;
    rectangular.access_points = {{0, 0, GridDirection::north}};

    if (!require(rotate_clockwise(BuildingRotation::r0) == BuildingRotation::r90 &&
                 rotate_clockwise(BuildingRotation::r90) == BuildingRotation::r180 &&
                 rotate_clockwise(BuildingRotation::r180) == BuildingRotation::r270 &&
                 rotate_clockwise(BuildingRotation::r270) == BuildingRotation::r0,
                 "clockwise rotation cycles through four orientations") ||
        !require(rotate_counter_clockwise(BuildingRotation::r0) == BuildingRotation::r270,
                 "counter-clockwise rotation wraps correctly") ||
        !require(rotated_footprint(rectangular, BuildingRotation::r0).width == 2 &&
                 rotated_footprint(rectangular, BuildingRotation::r0).height == 3 &&
                 rotated_footprint(rectangular, BuildingRotation::r90).width == 3 &&
                 rotated_footprint(rectangular, BuildingRotation::r90).height == 2,
                 "rectangular footprint swaps dimensions at quarter rotations") ||
        !require(rectangular.texture_path_for(BuildingRotation::r180) == "assets/buildings/rotation_test_r2.png",
                 "rotatable building resolves an explicit pre-rendered sprite")) {
        return 1;
    }

    BuildingDefinition square = rectangular;
    square.footprint_width = 2;
    square.footprint_height = 2;
    if (!require(rotated_footprint(square, BuildingRotation::r90).width == 2 &&
                 rotated_footprint(square, BuildingRotation::r90).height == 2,
                 "square footprint remains square when rotated")) {
        return 1;
    }

    const BuildingAccessPoint access_r90 = rotate_access_point(rectangular, rectangular.access_points.front(), BuildingRotation::r90);
    const BuildingAccessPoint access_r180 = rotate_access_point(rectangular, rectangular.access_points.front(), BuildingRotation::r180);
    if (!require(access_r90.local_x == 2 && access_r90.local_y == 0 && access_r90.facing == GridDirection::east,
                 "access point rotates clockwise with its footprint") ||
        !require(access_r180.local_x == 1 && access_r180.local_y == 2 && access_r180.facing == GridDirection::south,
                 "access point transforms at half rotation")) {
        return 1;
    }

    BuildingDefinition fixed = rectangular;
    fixed.rotatable = false;
    fixed.texture_path = "assets/buildings/fixed.png";
    if (!require(rotated_footprint(fixed, BuildingRotation::r90).width == 2 &&
                 rotated_footprint(fixed, BuildingRotation::r90).height == 3 &&
                 fixed.texture_path_for(BuildingRotation::r90) == fixed.texture_path &&
                 rotate_access_point(fixed, fixed.access_points.front(), BuildingRotation::r90).facing == GridDirection::north,
                 "non-rotatable building ignores orientation for footprint, sprite and access point")) {
        return 1;
    }

    rectangular.road_access_mode = RoadAccessMode::front_edge;
    rectangular.road_access_mode_explicit = true;
    rectangular.front_edge = GridDirection::south;
    const std::vector<BuildingAccessPoint> front_r0 = front_edge_access_points(rectangular, BuildingRotation::r0);
    const std::vector<BuildingAccessPoint> front_r90 = front_edge_access_points(rectangular, BuildingRotation::r90);
    if (!require(front_r0.size() == 2 && front_r0[0].local_x == 0 && front_r0[0].local_y == 2 &&
                     front_r0[1].local_x == 1 && front_r0[1].facing == GridDirection::south,
                 "front-edge contract exposes every base south facade tile") ||
        !require(front_r90.size() == 2 && front_r90[0].local_x == 0 && front_r90[0].local_y == 0 &&
                     front_r90[1].local_x == 0 && front_r90[1].local_y == 1 &&
                     front_r90[0].facing == GridDirection::west,
                 "front-edge contract rotates with a rectangular footprint")) {
        return 1;
    }
    rectangular.road_access_mode_explicit = false;

    BuildingManager manager(-2, 5);
    const auto first_id = manager.place(*cafe, 0, 0);
    if (!require(first_id.has_value(), "first placement succeeds") ||
        !require(manager.instance_at(1, 1) != nullptr, "all footprint tiles map to the instance") ||
        !require(manager.instance_at(1, 1)->instance_id == *first_id, "occupied tile resolves the correct instance") ||
        !require(manager.validate(*cafe, 1, 1) == PlacementFailure::occupied, "overlap is rejected") ||
        !require(manager.validate(*cafe, 3, 0) == PlacementFailure::none, "free footprint is accepted") ||
        !require(manager.validate(*cafe, 5, 5) == PlacementFailure::outside_map, "outside-map footprint is rejected")) {
        return 1;
    }

    CityEconomy economy;
    if (!require(economy.funds() == 50'000, "initial funds") ||
        !require(economy.try_spend(cafe->build_cost), "affordable placement spends money") ||
        !require(economy.funds() == 47'500, "placement cost is deducted") ||
        !require(!economy.try_spend(50'000), "unaffordable placement is rejected")) {
        return 1;
    }

    RoadManager roads(-2, 5);
    if (!require(roads.validate_placement(0, 0, manager) == RoadPlacementFailure::building_occupied,
                 "road over building is rejected") ||
        !require(roads.place_tile(2, 2), "road on a free tile is placed") ||
        !require(roads.is_road(2, 2), "road lookup works") ||
        !require(manager.validate(*cafe, 2, 2) == PlacementFailure::none &&
                 roads.overlaps_building_footprint(*cafe, 2, 2),
                 "building placement layer rejects a footprint containing a road") ||
        !require(roads.validate_placement(2, 2, manager) == RoadPlacementFailure::road_occupied,
                 "duplicate road is rejected") ||
        !require(roads.validate_placement(6, 0, manager) == RoadPlacementFailure::outside_map,
                 "road map bounds are enforced")) {
        return 1;
    }

    CityEconomy road_economy;
    if (!require(road_economy.try_spend(kRoadCostPerTile * 3), "road segment cost is affordable") ||
        !require(road_economy.funds() == 49'700, "road segment cost is deducted per tile") ||
        !require(!road_economy.try_spend(50'000), "insufficient road funds are rejected")) {
        return 1;
    }

    RoadManager connectivity(-5, 5);
    if (!require(connectivity.place_tile(0, 0), "isolated road placement") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::isolated, "isolated road classification") ||
        !require(connectivity.place_tile(1, 0), "road end neighbor placement") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::end, "road end classification") ||
        !require(connectivity.place_tile(-1, 0), "straight neighbor placement") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::straight, "straight road classification") ||
        !require(connectivity.connection_mask(0, 0) == static_cast<std::uint8_t>(road_east | road_west),
                 "opposite connections are recorded") ||
        !require(connectivity.place_tile(3, 3) && connectivity.place_tile(4, 3) && connectivity.place_tile(3, 4),
                 "curve neighbor placement") ||
        !require(connectivity.visual_type(3, 3) == RoadVisualType::curve, "curve road classification") ||
        !require(connectivity.place_tile(0, 1), "T neighbor placement") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::tee, "T road classification") ||
        !require(connectivity.place_tile(0, -1), "cross neighbor placement") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::intersection, "crossroad classification") ||
        !require(connectivity.remove_tile(1, 0), "road removal succeeds") ||
        !require(connectivity.connection_mask(0, 0) == static_cast<std::uint8_t>(road_north | road_south | road_west),
                 "removal refreshes neighboring connection masks") ||
        !require(connectivity.visual_type(0, 0) == RoadVisualType::tee, "removal refreshes neighboring visual type")) {
        return 1;
    }

    RoadManager access_roads(-2, 5);
    if (!require(access_roads.place_tile(2, 0), "adjacent access road is placed") ||
        !require(access_roads.has_adjacent_road(*manager.find_by_id(*first_id), *cafe),
                 "building road access checks its complete footprint")) {
        return 1;
    }

    BuildingDefinition front_edge_def = *cafe;
    front_edge_def.road_access_mode = RoadAccessMode::front_edge;
    front_edge_def.road_access_mode_explicit = true;
    front_edge_def.front_edge = GridDirection::south;
    front_edge_def.rotatable = true;

    const auto has_required_access = [&front_edge_def](const int road_x, const int road_y) {
        RoadManager candidate(-4, 6);
        return candidate.place_tile(road_x, road_y) &&
            candidate.has_required_road_access(front_edge_def, 0, 0, BuildingRotation::r0);
    };
    RoadManager no_access_roads(-4, 6);
    RoadManager diagonal_only_roads(-4, 6);
    BuildingDefinition road_optional = *cafe;
    road_optional.requires_road_access = false;
    if (!require(has_required_access(1, 2), "road at the declared south entrance allows placement") ||
        !require(has_required_access(0, 2), "road at another tile along the south front edge allows placement") ||
        !require(!has_required_access(0, -1), "road away from the declared entrance is rejected") ||
        !require(!has_required_access(2, 0), "road touching a side without an entrance is rejected") ||
        !require(!has_required_access(-1, 0), "road touching the other side without an entrance is rejected") ||
        !require(!no_access_roads.has_required_road_access(*cafe, 0, 0), "isolated building is rejected") ||
        !require(diagonal_only_roads.place_tile(2, 2) &&
                     !diagonal_only_roads.has_required_road_access(*cafe, 0, 0),
                 "diagonal-only road contact is rejected") ||
        !require(no_access_roads.has_required_road_access(road_optional, 0, 0),
                 "road-optional definition remains valid without a road")) {
        return 1;
    }
    if (!require(no_access_roads.has_required_road_access(*plaza, 0, 0),
                 "plaza can be placed without an adjacent road")) {
        return 1;
    }

    // A compact street test proves that the same front-edge contract permits
    // a regular row without accepting the rear or side of each house.
    BuildingManager neighborhood(-4, 20);
    RoadManager neighborhood_roads(-4, 20);
    for (int x = 0; x < 12; ++x) {
        if (!require(neighborhood_roads.place_tile(x, 2), "neighborhood front road is placed")) return 1;
    }
    for (int house_index = 0; house_index < 6; ++house_index) {
        const int house_x = house_index * 2;
        if (!require(neighborhood_roads.has_required_road_access(*house, house_x, 0, BuildingRotation::r0),
                     "each house in a row sees its south front road") ||
            !require(neighborhood.place(*house, house_x, 0, BuildingRotation::r0).has_value(),
                     "each front-aligned house occupies a non-overlapping footprint")) {
            return 1;
        }
    }
    if (!require(neighborhood.instances().size() == 6, "six-house front-aligned street is constructed")) return 1;

    BuildingManager blocked_buildings(-4, 6);
    CityEconomy blocked_economy;
    std::optional<std::uint64_t> blocked_instance;
    if (no_access_roads.has_required_road_access(*cafe, 0, 0) &&
        blocked_buildings.validate(*cafe, 0, 0) == PlacementFailure::none) {
        blocked_instance = blocked_buildings.place(*cafe, 0, 0);
        if (blocked_instance) {
            (void)blocked_economy.spend_for_building(cafe->build_cost, {1, 1, 1}, *blocked_instance);
        }
    }
    if (!require(!blocked_instance && blocked_buildings.instances().empty() && blocked_economy.funds() == 50'000,
                 "road-access rejection creates no building and spends no funds")) {
        return 1;
    }

    BuildingManager rotated_manager(-2, 5);
    const auto rotated_id = rotated_manager.place(rectangular, 0, 0, BuildingRotation::r90);
    if (!require(rotated_id.has_value(), "rotated rectangular building can be placed") ||
        !require(rotated_manager.find_by_id(*rotated_id)->rotation == BuildingRotation::r90,
                 "placed instance persists its logical rotation") ||
        !require(rotated_manager.instance_at(2, 1) != nullptr && rotated_manager.instance_at(1, 2) == nullptr,
                 "rotated occupancy uses a 3x2 footprint") ||
        !require(rotated_manager.validate(rectangular, 2, 0, BuildingRotation::r0) == PlacementFailure::occupied,
                 "collision validation uses the rotated footprint already on the grid")) {
        return 1;
    }

    RoadManager rotated_roads(-2, 5);
    if (!require(rotated_roads.place_tile(2, 1), "road for rotated footprint test is placed") ||
        !require(rotated_roads.overlaps_building_footprint(rectangular, 0, 0, BuildingRotation::r90),
                 "road blocks rotated building footprint") ||
        !require(rotated_roads.validate_placement(0, 0, rotated_manager) == RoadPlacementFailure::building_occupied,
                 "rotated building blocks a road on every occupied tile")) {
        return 1;
    }

    RoadManager access_point_roads(-2, 5);
    if (!require(access_point_roads.place_tile(3, 0), "road at transformed access point is placed") ||
        !require(access_point_roads.has_road_at_access_point(*rotated_manager.find_by_id(*rotated_id), rectangular),
                 "access-point road query follows building rotation")) {
        return 1;
    }

    BuildingDefinition road_required_rectangular = rectangular;
    road_required_rectangular.requires_road_access = true;
    RoadManager rotation_access_roads(-4, 6);
    BuildingManager rotation_access_buildings(-4, 6);
    if (!require(rotation_access_roads.place_tile(3, 0) &&
                     rotation_access_roads.has_required_road_access(road_required_rectangular, 0, 0, BuildingRotation::r90),
                 "rotated footprint accepts an orthogonally adjacent road") ||
        !require(rotation_access_buildings.place(road_required_rectangular, 0, 0, BuildingRotation::r90).has_value(),
                 "road access does not change rotated building placement or its footprint")) {
        return 1;
    }

    BuildingManager house_manager(-2, 5);
    const auto house_id = house_manager.place(*house, 0, 0, BuildingRotation::r0);
    RoadManager house_roads(-2, 5);
    if (!require(house_id.has_value() && house_manager.find_by_id(*house_id)->rotation == BuildingRotation::r0,
                 "house placement persists its selected rotation") ||
        !require(house_roads.place_tile(2, 1) && house_roads.has_adjacent_road(*house_manager.find_by_id(*house_id), *house),
                 "house works with adjacent-road access checks") ||
        !require(house_roads.place_tile(1, 1) && house_roads.overlaps_building_footprint(*house, 0, 0, BuildingRotation::r0),
                 "road blocks the house footprint") ||
        !require(house_roads.validate_placement(0, 0, house_manager) == RoadPlacementFailure::building_occupied,
                 "house footprint blocks road placement")) {
        return 1;
    }

    const std::vector<TileCoordinate> segment = roads.line_between({-1, -1}, {2, 1});
    if (!require(segment.size() == 6, "road drag produces a contiguous tile segment")) {
        return 1;
    }

    std::cout << "Building and road system checks passed.\n";
    return 0;
}
