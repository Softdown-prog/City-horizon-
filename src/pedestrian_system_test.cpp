#include "navigation_network.h"
#include "pedestrian_decision.h"
#include "pedestrian_system.h"
#include "road_system.h"
#include "sidewalk_system.h"

#include <array>
#include <cassert>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <string_view>
#include <vector>

namespace {

PedestrianSystem make_pedestrian_system() {
    return PedestrianSystem{{"citizen_common", 0.45F, 0.5F, 0.88F}};
}

MobileAnimationCatalog make_render_animation_catalog() {
    const auto fixture = std::filesystem::temp_directory_path() / "ch_pedestrian_animation_fixture";
    std::filesystem::remove_all(fixture);
    std::filesystem::create_directories(fixture);

    const auto write_set = [&fixture](const std::string_view set_id) {
        static constexpr std::array<std::string_view, 2> states = {"idle", "walking"};
        static constexpr std::array<std::string_view, 4> directions = {"north", "east", "south", "west"};
        std::ofstream out(fixture / (std::string(set_id) + ".json"));
        out << "{\"id\":\"" << set_id << "\",\"clips\":[";
        bool first = true;
        for (const std::string_view state : states) {
            for (const std::string_view direction : directions) {
                if (!first) out << ',';
                first = false;
                out << "{\"id\":\"" << set_id << '_' << state << '_' << direction
                    << "\",\"state\":\"" << state << "\",\"direction\":\"" << direction
                    << "\",\"frames\":[\"dummy.png\"],\"fps\":4,\"loop\":true}";
            }
        }
        out << "]}";
    };

    write_set("citizen_common");
    write_set("ch_actor_green_01");

    MobileAnimationCatalog animations;
    assert(animations.load_from_directory(fixture));
    std::filesystem::remove_all(fixture);
    return animations;
}

class CountingNavigationNetwork final : public NavigationNetwork {
public:
    explicit CountingNavigationNetwork(const NavigationNetwork& inner) : inner_(inner) {}

    [[nodiscard]] bool is_navigable(const NavigationTile tile) const override {
        ++query_count_;
        return inner_.is_navigable(tile);
    }

    [[nodiscard]] bool is_connected(const NavigationTile tile, const CardinalDirection direction) const override {
        ++query_count_;
        return inner_.is_connected(tile, direction);
    }

    void reset_query_count() { query_count_ = 0; }
    [[nodiscard]] std::size_t query_count() const { return query_count_; }

private:
    const NavigationNetwork& inner_;
    mutable std::size_t query_count_ = 0;
};

void advance_until_idle(PedestrianSystem& pedestrians, const NavigationNetwork& network) {
    for (int tick = 0; tick < 32 && pedestrians.instances().front().state == PedestrianState::walking; ++tick) {
        pedestrians.update_tick(0.25F, network);
        pedestrians.interpolate_visual(1.0F / 60.0F);
    }
}

void test_sidewalk_route_and_turns() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    SidewalkNavigationNetwork network{sidewalks};
    const std::vector<NavigationTile> tiles = {{0, 0}, {1, 0}, {2, 0}, {2, 1}, {2, 2}, {1, 1}};
    for (const NavigationTile tile : tiles) assert(sidewalks.place_tile(tile.x, tile.y, "concrete_01"));

    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {2, 2}, network));
    assert(pedestrians.instances().front().state == PedestrianState::walking);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::east);
    advance_until_idle(pedestrians, network);
    const PedestrianInstance& pedestrian = pedestrians.instances().front();
    assert(pedestrian.state == PedestrianState::idle);
    assert(pedestrian.spatial.logical_tile_x == 2 && pedestrian.spatial.logical_tile_y == 2);
    assert(pedestrian.spatial.direction == MobileEntityDirection::south);
}

void test_demolition_replans_once_then_stops_safely() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    SidewalkNavigationNetwork network{sidewalks};
    const std::vector<NavigationTile> tiles = {{0, 0}, {1, 0}, {2, 0}, {0, 1}, {1, 1}, {2, 1}};
    for (const NavigationTile tile : tiles) assert(sidewalks.place_tile(tile.x, tile.y, "concrete_01"));
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {2, 0}, network));
    assert(sidewalks.remove_tile(1, 0));
    pedestrians.update_tick(0.05F, network);
    assert(pedestrians.instances().front().state == PedestrianState::walking);
    assert(pedestrians.instances().front().replanned_after_network_change);
    advance_until_idle(pedestrians, network);
    assert(pedestrians.instances().front().spatial.logical_tile_x == 2);
    assert(pedestrians.instances().front().spatial.logical_tile_y == 0);

    SidewalkManager broken_sidewalks{-8, 8};
    SidewalkNavigationNetwork broken_network{broken_sidewalks};
    assert(broken_sidewalks.place_tile(0, 0, "concrete_01"));
    assert(broken_sidewalks.place_tile(1, 0, "concrete_01"));
    assert(broken_sidewalks.place_tile(2, 0, "concrete_01"));
    PedestrianSystem stranded = make_pedestrian_system();
    assert(stranded.send_pedestrian({0, 0}, {2, 0}, broken_network));
    assert(broken_sidewalks.remove_tile(1, 0));
    stranded.update_tick(0.05F, broken_network);
    assert(stranded.instances().front().state == PedestrianState::idle);
    assert(stranded.instances().front().spatial.logical_tile_x == 0);
    assert(stranded.instances().front().spatial.logical_tile_y == 0);
}

void test_surface_turn_and_idle() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    assert(sidewalks.place_tile(1, 0, "sand_path"));
    assert(sidewalks.place_tile(1, 1, "cement_path"));
    assert(roads.place_tile(2, 2));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    assert(!network.is_navigable({2, 2}));

    MobileAnimationCatalog animations = make_render_animation_catalog();
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 1}, network));
    const auto rendered = pedestrians.render_entities(animations, true);
    assert(!rendered.empty());
    assert(!rendered.front().umbrella.enabled);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::east);
    pedestrians.update_tick(0.46F, network);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::south);
    pedestrians.update_tick(0.46F, network);
    assert(pedestrians.instances().front().state == PedestrianState::idle);
    assert(pedestrians.send_pedestrian({1, 1}, {0, 0}, network));
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::north);
    pedestrians.clear();
    assert(pedestrians.instances().empty());
}

void test_visiting_state_blocks_reroute_and_faces_door() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};

    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 0}, network));
    advance_until_idle(pedestrians, network);

    const std::uint64_t id = pedestrians.instances().front().id;
    assert(pedestrians.face_pedestrian(id, MobileEntityDirection::north));
    assert(pedestrians.set_visiting(id, true));
    assert(pedestrians.instances().front().state == PedestrianState::visiting);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::north);
    assert(!pedestrians.send_pedestrian({1, 0}, {0, 0}, network));

    assert(pedestrians.set_visiting(id, false));
    assert(pedestrians.instances().front().state == PedestrianState::idle);
    assert(pedestrians.send_pedestrian({1, 0}, {0, 0}, network));
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::west);
}

void test_clothing_is_chosen_once_per_actor_birth() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    for (int x = 0; x <= 2; ++x) assert(sidewalks.place_tile(x, 0, "cement_path"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    MobileAnimationCatalog animations = make_render_animation_catalog();
    PedestrianSystem pedestrians{{"ch_actor_green_01", 1.0F, 0.5F, 60.0F / 64.0F}};
    assert(pedestrians.send_pedestrian({0, 0}, {2, 0}, network));
    pedestrians.update_animation(0.25F, animations);
    assert(!pedestrians.instances().front().animation.clip_id.empty());

    const std::uint64_t born_id = pedestrians.instances().front().id;
    const auto born_render = pedestrians.render_entities(animations);
    const auto rainy_born_render = pedestrians.render_entities(animations, true);
    assert(!born_render.empty());
    assert(!rainy_born_render.empty());
    const MobileClothingTint born_outfit = born_render.front().clothing;
    const MobileUmbrellaTint born_umbrella = rainy_born_render.front().umbrella;
    assert(born_outfit.enabled);
    assert(born_umbrella.enabled);
    assert(born_umbrella.fabric != MobileClothingColor{});
    assert(!born_render.front().umbrella.enabled);
    assert(born_outfit.jacket != MobileClothingColor{});
    assert(born_outfit.pants != MobileClothingColor{});

    advance_until_idle(pedestrians, network);
    assert(pedestrians.send_pedestrian({2, 0}, {0, 0}, network));
    assert(pedestrians.instances().front().id == born_id);
    assert(pedestrians.render_entities(animations).front().clothing == born_outfit);
    assert(pedestrians.render_entities(animations, true).front().umbrella.fabric == born_umbrella.fabric);
    advance_until_idle(pedestrians, network);
    assert(pedestrians.render_entities(animations, true).front().umbrella.enabled);
    assert(pedestrians.set_visiting(born_id, true));
    assert(!pedestrians.render_entities(animations, true).front().umbrella.enabled);
    assert(pedestrians.set_visiting(born_id, false));
    assert(pedestrians.rest_at_home({0, 0}));
    assert(pedestrians.instances().front().clothing.jacket == born_outfit.jacket);
    assert(pedestrians.instances().front().clothing.pants == born_outfit.pants);
    assert(pedestrians.render_entities(animations).empty());
    assert(pedestrians.render_entities(animations, true).empty());

    pedestrians.wake_up();
    assert(pedestrians.render_entities(animations).front().clothing == born_outfit);
    assert(pedestrians.render_entities(animations, true).front().umbrella.fabric == born_umbrella.fabric);
    pedestrians.clear();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 0}, network));
    assert(pedestrians.instances().front().id != born_id);
}

void test_budget_distribution() {
    std::size_t low = 0;
    std::size_t middle = 0;
    std::size_t upper = 0;
    std::size_t high = 0;
    for (std::uint64_t id = 1; id <= 100; ++id) {
        const std::int64_t budget = PedestrianSystem::budget_capacity_for(id);
        if (budget == 5'000) ++low;
        else if (budget == 9'000) ++middle;
        else if (budget == 15'000) ++upper;
        else if (budget == 20'000) ++high;
        else assert(false);
    }
    assert(low == 70);
    assert(middle == 20);
    assert(upper == 8);
    assert(high == 2);
}

void test_need_decay_priority_and_restore() {
    RoadManager roads{-4, 4};
    SidewalkManager sidewalks{-4, 4};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {0, 0}, network));
    const std::uint64_t id = pedestrians.instances().front().id;

    pedestrians.update_tick(10.0F, network);
    const PedestrianNeeds after_ten = pedestrians.needs(id);
    assert(std::abs(after_ten.hunger - 90.0F) < 0.001F);
    assert(std::abs(after_ten.thirst - 90.0F) < 0.001F);
    assert(std::abs(after_ten.fun - 90.0F) < 0.001F);

    assert(pedestrians.restore_need(id, PedestrianNeed::hunger, 5.0F));
    assert(pedestrians.restore_need(id, PedestrianNeed::fun, 8.0F));
    assert(pedestrians.priority_need(id) == PedestrianNeed::thirst);
    assert(pedestrians.restore_need(id, PedestrianNeed::thirst, 1000.0F));
    assert(std::abs(pedestrians.needs(id).thirst - 100.0F) < 0.001F);
}

void test_weather_policy_and_monthly_budget() {
    assert(std::abs(PedestrianDecisionNode::outing_probability(WeatherState::sunny, false) - 0.85F) < 0.001F);
    assert(std::abs(PedestrianDecisionNode::outing_probability(WeatherState::overcast, false) - 0.45F) < 0.001F);
    assert(std::abs(PedestrianDecisionNode::outing_probability(WeatherState::raining, false) - 0.12F) < 0.001F);
    assert(std::abs(PedestrianDecisionNode::outing_probability(WeatherState::raining, true) - 0.45F) < 0.001F);
    assert(PedestrianDecisionNode::preference_for_weather(WeatherState::sunny, false) == PedestrianOutingPreference::outdoor_leisure);
    assert(PedestrianDecisionNode::preference_for_weather(WeatherState::overcast, false) == PedestrianOutingPreference::balanced);
    assert(PedestrianDecisionNode::preference_for_weather(WeatherState::raining, false) == PedestrianOutingPreference::covered_commerce);
    assert(PedestrianDecisionNode::preference_for_weather(WeatherState::raining, true) == PedestrianOutingPreference::essential_commerce);

    RoadManager roads{-4, 4};
    SidewalkManager sidewalks{-4, 4};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {0, 0}, network));
    assert(pedestrians.rest_at_home({0, 0}));
    const std::uint64_t id = pedestrians.instances().front().id;
    assert(pedestrians.monthly_budget_capacity_cents(id) == PedestrianSystem::kDefaultMonthlyBudgetCents);
    assert(pedestrians.monthly_budget_cents(id) == PedestrianSystem::kDefaultMonthlyBudgetCents);
    assert(pedestrians.spend_monthly_budget(id, 300));
    assert(pedestrians.monthly_budget_cents(id) == 4'700);
    assert(!pedestrians.spend_monthly_budget(id, 4'701));
    assert(pedestrians.authorize_outing(PedestrianOutingPreference::covered_commerce, PedestrianNeed::thirst));
    assert(pedestrians.instances().front().outing_intent.active);
    assert(pedestrians.instances().front().outing_intent.priority_need == PedestrianNeed::thirst);
    pedestrians.clear_outing_intent(id);
    assert(!pedestrians.instances().front().outing_intent.active);
    assert(pedestrians.spend_monthly_budget(id, 4'700));
    assert(pedestrians.monthly_budget_cents(id) == 0);
    assert(pedestrians.rest_at_home({0, 0}));
    assert(!pedestrians.authorize_outing(PedestrianOutingPreference::balanced, PedestrianNeed::fun));

    pedestrians.sync_monthly_budget_cycle(1, 1);
    pedestrians.sync_monthly_budget_cycle(1, 1);
    assert(pedestrians.monthly_budget_cents(id) == 0);
    pedestrians.sync_monthly_budget_cycle(2, 1);
    assert(pedestrians.monthly_budget_cents(id) == pedestrians.monthly_budget_capacity_cents(id));
    assert(pedestrians.spend_monthly_budget(id, 300));
    pedestrians.sync_monthly_budget_cycle(2, 1);
    assert(pedestrians.monthly_budget_cents(id) == 4'700);
    pedestrians.sync_monthly_budget_cycle(1, 2);
    assert(pedestrians.monthly_budget_cents(id) == pedestrians.monthly_budget_capacity_cents(id));
    assert(pedestrians.authorize_outing(PedestrianOutingPreference::balanced, PedestrianNeed::hunger));
}

void test_resident_at_home_decision_and_weather_immunity_in_transit() {
    const auto fixture = std::filesystem::temp_directory_path() / "ch_pedestrian_decision_fixture";
    std::filesystem::create_directories(fixture);
    {
        std::ofstream out(fixture / "house.json");
        out << R"({"id":"test_home","name":"Home","category":"residential","texture":"house.png",
            "footprint":{"width":3,"height":3},"residentialCapacity":5,
            "roadAccessMode":"front_edge","frontEdge":"south"})";
    }
    BuildingCatalog catalog;
    assert(catalog.load_from_directory(fixture));
    const BuildingDefinition* house = catalog.find("test_home");
    assert(house != nullptr);
    BuildingManager buildings{-12, 12};
    const auto id = buildings.place(*house, 0, 0);
    assert(id);
    RoadManager roads{-12, 12};
    SidewalkManager sidewalks{-12, 12};
    for (int y = 3; y <= 8; ++y) assert(sidewalks.place_tile(1, y, "cement_path"));
    PedestrianSurfaceNavigationNetwork surface_network{roads, sidewalks};
    CountingNavigationNetwork network{surface_network};
    PedestrianSystem pedestrians = make_pedestrian_system();
    PedestrianDecisionNode decisions;

    decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(decisions.home_id() == id);
    assert(decisions.decision() == PedestrianDecision::resting_at_home);
    assert(pedestrians.instances().front().state == PedestrianState::resting);
    assert(pedestrians.instances().front().spatial.logical_tile_x == 1);
    assert(pedestrians.instances().front().spatial.logical_tile_y == 3);

    bool authorized = false;
    for (int i = 0; i < 120; ++i) {
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks, false);
        authorized = pedestrians.instances().front().outing_intent.active;
        if (authorized) break;
    }
    assert(authorized);
    assert(decisions.decision() == PedestrianDecision::awaiting_activity);
    assert(pedestrians.instances().front().state == PedestrianState::idle);

    const std::uint64_t pedestrian_id = pedestrians.instances().front().id;
    pedestrians.clear_outing_intent(pedestrian_id);
    assert(pedestrians.send_pedestrian({1, 3}, {1, 8}, network));
    network.reset_query_count();
    decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks, true);
    assert(pedestrians.instances().front().state == PedestrianState::walking);
    assert(network.query_count() == 0);

    advance_until_idle(pedestrians, network);
    for (int i = 0; i < 80 && decisions.decision() != PedestrianDecision::resting_at_home; ++i) {
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks, true);
        pedestrians.update_tick(0.25F, network);
    }
    assert(decisions.decision() == PedestrianDecision::resting_at_home);
    assert(pedestrians.instances().front().state == PedestrianState::resting);

    assert(buildings.remove_instance(*house, *id));
    decisions.update(3.0F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(!decisions.home_id());
    assert(pedestrians.instances().front().state != PedestrianState::resting);
    std::filesystem::remove_all(fixture);
}

} // namespace

int main() {
    test_sidewalk_route_and_turns();
    test_demolition_replans_once_then_stops_safely();
    test_surface_turn_and_idle();
    test_resident_at_home_decision_and_weather_immunity_in_transit();
    test_visiting_state_blocks_reroute_and_faces_door();
    test_clothing_is_chosen_once_per_actor_birth();
    test_budget_distribution();
    test_need_decay_priority_and_restore();
    test_weather_policy_and_monthly_budget();
}
