#include "src/ch_core/budgeted_resource_cache.h"
#include "src/ch_core/contracts.h"
#include "src/ch_core/game_command.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"
#include "src/developer_console.h"
#include "src/ride_state_machine.h"
#include "src/scenario_test_harness.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <optional>
#include <string>

namespace {

class TestGameCommand final : public ch::IGameCommand {
public:
    explicit TestGameCommand(bool valid = true) : valid_(valid) {}

    [[nodiscard]] ch::GameCommandPlan prepare() const override {
        ++prepare_calls;
        ch::GameCommandPlan plan;
        plan.valid = valid_;
        plan.failure = valid_ ? ch::GameCommandFailure::none : ch::GameCommandFailure::blocked;
        plan.message = valid_ ? "ok" : "blocked";
        plan.cost_units = 750;
        plan.affected_tiles = {{3, 4}, {4, 4}};
        plan.transaction.description = "test command";
        plan.transaction.action_type = ch::TransactionActionType::set_road;
        return plan;
    }

    [[nodiscard]] bool apply(const ch::GameCommandPlan& prepared, std::string&) override {
        ++apply_calls;
        applied_cost = prepared.cost_units;
        return true;
    }

    mutable int prepare_calls = 0;
    int apply_calls = 0;
    std::int64_t applied_cost = 0;

private:
    bool valid_ = true;
};

}  // namespace

int main(int argc, char** argv) {
    static_assert(ch::contracts::kTileWidth == 128);
    static_assert(ch::contracts::kTileHeight == 64);
    static_assert(ch::contracts::kDiamondRatio == 2.0);
    static_assert(ch::contracts::kMapMin == -80);
    static_assert(ch::contracts::kMapMax == 79);
    assert(std::string(ch::contracts::kGridContract) == "CH_GRID_V1");
    assert(std::string(ch::kGameCommandContract) == "CH_GAME_COMMAND_V1");
    assert(std::string(kRideStateMachineContract) == "CH_RIDE_STATE_MACHINE_V1");
    assert(std::string(kDeveloperConsoleContract) == "CH_DEVELOPER_CONSOLE_V1");
    assert(std::string(kScenarioTestHarnessContract) == "CH_SCENARIO_TEST_HARNESS_V1");

    ch::GridCoord c1{5, -10};
    ch::GridCoord c2{5, -10};
    ch::GridCoord c3{5, 10};
    assert(c1 == c2);
    assert(!(c1 == c3));

    ch::GridBounds bounds;
    assert(bounds.contains(0, 0));
    assert(bounds.contains(-80, 79));
    assert(!bounds.contains(-81, 0));
    assert(!bounds.contains(0, 80));
    assert(ch::tile_key(5, -10) != ch::tile_key(-10, 5));

    ch::CameraState camera;
    camera.pan_x = 100.0F;
    camera.pan_y = 50.0F;
    camera.zoom = 1.0F;
    camera.rotation = ch::CameraRotation::r0;

    ch::ScreenPoint sp = ch::world_to_screen_point(10.0F, 5.0F, camera, 1280.0F, 720.0F);
    ch::GridCoord gc = ch::screen_to_tile_coord(sp.x, sp.y, camera, 1280.0F, 720.0F);
    assert(gc.x == 10);
    assert(gc.y == 5);

    float depth_r0 = ch::camera_depth_key(10.0F, 5.0F, camera);
    assert(std::abs(depth_r0 - 15.0F) < 0.001F);

    ch::WorldPoint top_r0 = ch::tile_visual_top_world(10, 5, ch::CameraRotation::r0);
    assert(top_r0.x == 10.0F && top_r0.y == 5.0F);
    ch::WorldPoint top_r90 = ch::tile_visual_top_world(10, 5, ch::CameraRotation::r90);
    assert(top_r90.x == 11.0F && top_r90.y == 5.0F);
    ch::WorldPoint b_ground = ch::building_visual_ground_world(10, 5, 2, 2, ch::CameraRotation::r0);
    assert(b_ground.x == 12.0F && b_ground.y == 7.0F);

    if (argc > 1) {
        std::string scenario_path = argv[1];
        auto doc = ch::MapDocument::load_from_file(scenario_path);
        assert(doc.has_value());
        assert(!doc->terrain_tiles().empty());
        assert(!doc->buildings().empty());
        auto report = ch::validate_map_document(*doc);
        assert(report.valid);
        assert(report.errors.empty());
    }

    std::string test_json = R"({
        "terrain": [{"tileX": 0, "tileY": 0, "texture": "grass"}],
        "terrainHeights": [{"x": 0, "y": 0, "height": 1.5}, {"x": 1, "y": 0, "height": -0.5}],
        "buildings": [{"instanceId": 1, "definitionId": "bakery", "tileX": 1, "tileY": 1, "rotation": 0}],
        "roads": [{"tileX": 2, "tileY": 2}]
    })";
    ch::MapDocument inline_doc(test_json);
    assert(inline_doc.terrain_tiles().size() == 1);
    assert(std::abs(inline_doc.terrain_height_at(0, 0) - 1.5F) < 0.001F);
    assert(std::abs(inline_doc.terrain_height_at(1, 0) + 0.5F) < 0.001F);
    assert(std::abs(inline_doc.terrain_heightfield().sample(0.5F, 0.0F) - 0.5F) < 0.001F);
    assert(inline_doc.buildings().size() == 1);
    assert(inline_doc.roads().size() == 1);
    assert(inline_doc.get_terrain_at(0, 0).has_value());
    assert(inline_doc.get_terrain_at(0, 0)->texture == "grass");
    assert(inline_doc.get_building_at(1, 1).has_value());
    assert(inline_doc.get_building_at(1, 1)->definition_id == "bakery");
    assert(inline_doc.is_road_at(2, 2));
    assert(!inline_doc.is_road_at(0, 0));
    auto inline_report = ch::validate_map_document(inline_doc);
    assert(inline_report.valid);

    TestGameCommand preview_command;
    const ch::GameCommandResult preview = ch::GameCommandExecutor::run(preview_command, ch::GameCommandMode::preview);
    assert(preview.success);
    assert(!preview.applied);
    assert(preview.cost_units == 750);
    assert(preview.affected_tiles.size() == 2);
    assert(preview_command.prepare_calls == 1);
    assert(preview_command.apply_calls == 0);

    TestGameCommand execute_command;
    const ch::GameCommandResult executed = ch::GameCommandExecutor::run(execute_command, ch::GameCommandMode::execute);
    assert(executed.success);
    assert(executed.applied);
    assert(execute_command.prepare_calls == 1);
    assert(execute_command.apply_calls == 1);
    assert(execute_command.applied_cost == executed.cost_units);

    TestGameCommand blocked_command(false);
    const ch::GameCommandResult blocked = ch::GameCommandExecutor::run(blocked_command, ch::GameCommandMode::execute);
    assert(!blocked.success);
    assert(!blocked.applied);
    assert(blocked.failure == ch::GameCommandFailure::blocked);
    assert(blocked_command.apply_calls == 0);

    int evicted = 0;
    ch::BudgetedResourceCache<std::string, int> resource_cache(8, [&](int&) { ++evicted; });
    auto load_value = [](const int value) {
        return [value]() -> std::optional<int> { return value; };
    };
    assert(resource_cache.get_or_load("a", 4, load_value(10)) != nullptr);
    assert(resource_cache.get_or_load("b", 4, load_value(20)) != nullptr);
    assert(resource_cache.get("a") != nullptr);
    assert(resource_cache.get_or_load("c", 4, load_value(30)) != nullptr);
    assert(resource_cache.get("b") == nullptr);
    assert(resource_cache.resident_bytes() == 8);
    assert(evicted == 1);
    assert(resource_cache.pin("a"));
    resource_cache.set_budget_bytes(4);
    assert(resource_cache.get("a") != nullptr);
    assert(resource_cache.get("c") == nullptr);
    assert(resource_cache.resident_bytes() == 4);
    resource_cache.set_budget_bytes(2);
    assert(resource_cache.budget_stats().over_budget_events >= 1);
    assert(resource_cache.unpin("a"));
    resource_cache.set_budget_bytes(2);
    assert(resource_cache.resident_bytes() == 0);

    RideStateDurations ride_durations;
    ride_durations.boarding_ms = 1000;
    ride_durations.starting_ms = 200;
    ride_durations.running_ms = 2000;
    ride_durations.stopping_ms = 200;
    ride_durations.unloading_ms = 600;
    RideStateMachine ride(ride_durations);
    ride.request_dispatch();
    assert(ride.snapshot().state == RideOperatingState::boarding);
    ride.update(1100);
    assert(ride.snapshot().state == RideOperatingState::starting);
    assert(ride.snapshot().elapsed_in_state_ms == 100);
    ride.update(1100);
    assert(ride.snapshot().state == RideOperatingState::running);
    assert(ride.snapshot().elapsed_in_state_ms == 1000);
    assert(std::abs(ride.snapshot().normalized_running_phase(ride_durations) - 0.5F) < 0.001F);
    ride.update(2800);
    assert(ride.snapshot().state == RideOperatingState::idle);
    assert(!ride.snapshot().dispatch_requested);

    DeveloperConsoleRegistry console;
    assert(console.register_command({"echo", "echo <args...>", "Echo arguments for diagnostics", true},
        [](const DeveloperConsoleRegistry::Arguments& args) {
            std::string joined;
            for (const std::string& arg : args) {
                if (!joined.empty()) joined += '|';
                joined += arg;
            }
            return DeveloperConsoleResult{true, joined};
        }));
    const DeveloperConsoleResult console_result = console.execute("echo citizen \"Roda Gigante\"");
    assert(console_result.success);
    assert(console_result.output == "citizen|Roda Gigante");
    const DeveloperConsoleResult help_result = console.help("echo");
    assert(help_result.success);
    assert(help_result.output.find("echo <args...>") != std::string::npos);
    assert(help_result.output.find("[read-only]") != std::string::npos);
    assert(!console.execute("unknown").success);
    assert(console.history().size() == 2);
    console.clear_history();
    assert(console.history().empty());

    int scenario_state = 0;
    ScenarioTestHarness scenario("happy-path");
    assert(scenario.add_step("prepare", [&]() {
        scenario_state = 1;
        return ScenarioStepResult{true, {}};
    }));
    assert(scenario.add_step("validate", [&]() {
        return ScenarioStepResult{scenario_state == 1, "state not prepared"};
    }));
    const ScenarioRunResult scenario_result = scenario.run();
    assert(scenario_result.success);
    assert(scenario_result.scenario_name == "happy-path");
    assert(scenario_result.completed_steps == 2);

    ScenarioTestHarness failing_scenario("failure-path");
    assert(failing_scenario.add_step("fail-here", []() {
        return ScenarioStepResult{false, "expected failure"};
    }));
    const ScenarioRunResult failed_scenario = failing_scenario.run();
    assert(!failed_scenario.success);
    assert(failed_scenario.failed_step == "fail-here");
    assert(failed_scenario.completed_steps == 0);

    ScenarioTestSuite suite;
    assert(suite.add(std::move(scenario)));
    ScenarioTestHarness second("second");
    assert(second.add_step("ok", []() { return ScenarioStepResult{true, {}}; }));
    assert(suite.add(std::move(second)));
    const ScenarioSuiteRunResult suite_result = suite.run();
    assert(suite_result.success);
    assert(suite_result.completed_scenarios == 2);
    assert(suite_result.results.size() == 2);

    std::cout << "ch_core_test passed successfully!\n";
    return 0;
}