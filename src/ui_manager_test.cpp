#include "ui_manager.h"
#include "ui_nine_slice.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>

int ch_weather_ui_state_code() {
    return 0;
}

namespace {

void require(const bool condition, const char* message) {
    if (!condition) {
        std::cerr << "ui manager test failed: " << message << '\n' << std::flush;
        std::quick_exit(1);
    }
}

bool nearly_equal(const float lhs, const float rhs) {
    return std::abs(lhs - rhs) < 0.001F;
}

GameplayUiModel base_model() {
    GameplayUiModel model;
    model.funds = "$50.000";
    model.date = "DAY 1 / MONTH 1 / YEAR 1";
    model.monthly_revenue = "$0";
    model.monthly_expenses = "$0";
    model.monthly_balance = "$0";
    model.population = "0";
    model.residential_capacity = "5";
    model.speed = "1x";
    model.build_items.push_back({"coffee_shop_01", "Cafeteria", "Commerce", "$0", true});
    model.build_items.push_back({"residential_popular_house_01", "Casa popular", "Residential", "$4.000", true});
    return model;
}

}  // namespace

int main() {
    std::cerr << "ui_manager_test: start\n" << std::flush;

    GameplayUi ui;
    GameplayUiModel model = base_model();
    ui.update_layout(1280, 800, model);
    std::cerr << "ui_manager_test: initial layout\n" << std::flush;

    require(UiRect{10, 10, 20, 20}.contains(10, 10), "rect hit-test includes edge");
    require(!UiRect{10, 10, 20, 20}.contains(31, 31), "rect hit-test excludes outside");

    const ch::ui::NineSliceRegions slice = ch::ui::make_nine_slice_regions(
        48.0F, 48.0F, SDL_FRect{10.0F, 20.0F, 200.0F, 100.0F},
        ch::ui::NineSliceInsets{8.0F, 8.0F, 8.0F, 8.0F});
    const auto& center = slice[static_cast<std::size_t>(ch::ui::NineSlicePatch::center)];
    require(nearly_equal(center.source.x, 8.0F) && nearly_equal(center.source.w, 32.0F) &&
                nearly_equal(center.destination.w, 184.0F),
            "nine-slice center remains stable");

    ui.handle_mouse_motion(40, 765);
    const auto build_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::open_build_panel;
    });
    require(build_button != ui.buttons().end() && build_button->state == UiButtonState::hover,
            "toolbar exposes build button hover");
    const UiInputResult build_click = ui.handle_mouse_button_down(40, 765, true);
    require(build_click.consumed && build_click.action && build_click.action->action == UiAction::open_build_panel,
            "build toolbar click dispatches action");
    ui.handle_mouse_button_up(40, 765);

    model.build_panel_open = true;
    model.active_tool = UiTool::buildings;
    ui.update_layout(1280, 800, model);
    std::cerr << "ui_manager_test: building panel\n" << std::flush;

    const auto coffee_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "coffee_shop_01";
    });
    const auto house_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "residential_popular_house_01";
    });
    require(coffee_card != ui.buttons().end(), "current coffee shop appears in build catalogue");
    require(house_card != ui.buttons().end(), "current popular house appears in build catalogue");

    const UiInputResult coffee_click = ui.handle_mouse_button_down(
        coffee_card->bounds.x + 4.0F, coffee_card->bounds.y + 4.0F, true);
    require(coffee_click.action && coffee_click.action->action == UiAction::select_building &&
                coffee_click.action->payload == "coffee_shop_01",
            "current coffee shop dispatches selection");

    model.build_items.front().enabled = false;
    ui.update_layout(1280, 800, model);
    const auto disabled_coffee = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "coffee_shop_01";
    });
    require(disabled_coffee != ui.buttons().end(), "disabled catalogue item remains visible");
    const UiInputResult disabled_click = ui.handle_mouse_button_down(
        disabled_coffee->bounds.x + 4.0F, disabled_coffee->bounds.y + 4.0F, true);
    require(disabled_click.consumed && !disabled_click.action,
            "disabled catalogue item consumes input without dispatching");

    model.build_items.front().enabled = true;
    model.selected_building_id = "coffee_shop_01";
    model.placement_rotatable = true;
    model.placement_rotation_label = "R0";
    ui.update_layout(1280, 800, model);
    const auto rotate = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::rotate_right;
    });
    require(rotate != ui.buttons().end() && rotate->enabled,
            "selected rotatable building enables preview rotation");

    model.build_panel_open = false;
    model.active_tool = UiTool::sidewalks;
    ui.update_layout(1280, 800, model);
    for (const std::string& style : {"dirt_path", "sand_path", "grass"}) {
        const auto floor_style = std::find_if(ui.buttons().begin(), ui.buttons().end(), [&style](const UiButton& button) {
            return button.action == UiAction::select_sidewalk_style && button.payload == style;
        });
        require(floor_style != ui.buttons().end(), "all current floor styles appear in the floor tool");
    }

    model.active_tool = UiTool::land;
    ui.update_layout(1280, 800, model);
    require(!std::any_of(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
                return button.action == UiAction::paint_grass || button.action == UiAction::paint_sand;
            }),
            "land panel remains reserved for parcel purchase");

    require(!ui.consumes_point(700, 500), "map point is not consumed by UI");
    require(ui.consumes_point(20, 20), "top UI consumes input");

    std::cerr << "ui_manager_test: complete\n" << std::flush;
    std::quick_exit(0);
}
