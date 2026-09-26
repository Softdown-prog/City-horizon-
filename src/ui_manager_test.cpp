#include "ui_manager.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "ui manager test failed: " << message << '\n';
        std::exit(1);
    }
}

GameplayUiModel base_model() {
    GameplayUiModel model;
    model.funds = "$50.000";
    model.date = "DAY 1 / MONTH 1 / YEAR 1";
    model.monthly_revenue = "$220";
    model.monthly_expenses = "$80";
    model.monthly_balance = "+$140";
    model.population = "0";
    model.residential_capacity = "4";
    model.power_demand = "4";
    model.power_capacity = "20";
    model.speed = "1x";
    model.build_items.push_back({"cafe_01", "Cafeteria", "Commerce", "$2.500", true});
    model.build_items.push_back({"house_suburban_01", "Casa Suburbana", "Residential", "$1.800", true});
    return model;
}

}  // namespace

int main() {
    GameplayUi ui;
    GameplayUiModel model = base_model();
    ui.update_layout(1280, 800, model);

    require(UiRect{10, 10, 20, 20}.contains(10, 10), "rect hit-test includes edge");
    require(!UiRect{10, 10, 20, 20}.contains(31, 31), "rect hit-test excludes outside");

    ui.handle_mouse_motion(40, 765);
    const auto build_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::open_build_panel;
    });
    require(build_button != ui.buttons().end() && build_button->state == UiButtonState::hover, "toolbar hover state");
    const UiInputResult build_click = ui.handle_mouse_button_down(40, 765, true);
    require(build_click.consumed && build_click.action && build_click.action->action == UiAction::open_build_panel,
            "build button click is consumed");
    ui.handle_mouse_button_up(40, 765);

    model.build_panel_open = true;
    model.active_tool = UiTool::buildings;
    ui.update_layout(1280, 800, model);
    const auto cafe_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "cafe_01";
    });
    require(cafe_card != ui.buttons().end(), "catalog contains cafe build item");
    const UiInputResult item_click = ui.handle_mouse_button_down(cafe_card->bounds.x + 4.0F, cafe_card->bounds.y + 4.0F, true);
    require(item_click.consumed && item_click.action && item_click.action->action == UiAction::select_building &&
            item_click.action->payload == "cafe_01", "catalog build item click");

    const auto house_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "house_suburban_01";
    });
    require(house_card != ui.buttons().end(), "catalog contains house build item");
    const UiInputResult house_item_click = ui.handle_mouse_button_down(house_card->bounds.x + 4.0F, house_card->bounds.y + 4.0F, true);
    require(house_item_click.consumed && house_item_click.action && house_item_click.action->action == UiAction::select_building &&
                house_item_click.action->payload == "house_suburban_01", "residential catalog item click");

    ui.update_layout(960, 500, model);
    const auto compact_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "cafe_01";
    });
    require(compact_card != ui.buttons().end(), "compact window retains a selectable catalog item");
    ui.update_layout(1280, 800, model);

    model.build_items.front().enabled = false;
    ui.update_layout(1280, 800, model);
    const auto disabled_cafe_card = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::select_building && button.payload == "cafe_01";
    });
    require(disabled_cafe_card != ui.buttons().end(), "disabled catalogue item remains visible");
    const UiInputResult disabled_click = ui.handle_mouse_button_down(disabled_cafe_card->bounds.x + 4.0F,
                                                                       disabled_cafe_card->bounds.y + 4.0F, true);
    require(disabled_click.consumed && !disabled_click.action, "disabled item consumes without dispatching");
    model.build_items.front().enabled = true;

    model.placement_rotatable = true;
    ui.update_layout(1280, 800, model);
    const auto left_arrow = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::rotate_left;
    });
    require(left_arrow != ui.buttons().end() && !left_arrow->enabled,
            "preview arrows wait for a selected building");
    model.selected_building_id = "cafe_01";
    model.placement_rotation_label = "R0";
    ui.update_layout(1280, 800, model);
    const auto enabled_arrow = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::rotate_right;
    });
    require(enabled_arrow != ui.buttons().end() && enabled_arrow->enabled,
            "selected building enables preview rotation");
    const UiInputResult rotation_click = ui.handle_mouse_button_down(enabled_arrow->bounds.x + 4.0F,
                                                                       enabled_arrow->bounds.y + 4.0F, true);
    require(rotation_click.action && rotation_click.action->action == UiAction::rotate_right,
            "preview arrow dispatches placement rotation");
    const auto panel_close = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::close_tool_panel && button.bounds.y < 200.0F;
    });
    require(panel_close != ui.buttons().end(), "build panel has a close control");
    const UiInputResult panel_close_click = ui.handle_mouse_button_down(panel_close->bounds.x + 4.0F,
                                                                           panel_close->bounds.y + 4.0F, true);
    require(panel_close_click.action && panel_close_click.action->action == UiAction::close_tool_panel,
            "build panel close dispatches cancellation");

    model.selected_building = UiSelectedBuilding{"Cafeteria", "Commercial", "$2.500", "$220", "$80", "+$140", "R0", "ROAD CONNECTED", "7", "10%"};
    ui.update_layout(1280, 800, model);
    const auto close_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::close_selection;
    });
    require(close_button != ui.buttons().end(), "contextual panel creates a close button");
    const UiInputResult close_click = ui.handle_mouse_button_down(close_button->bounds.x + 4.0F, close_button->bounds.y + 4.0F, true);
    require(close_click.consumed && close_click.action && close_click.action->action == UiAction::close_selection,
            "contextual panel close button");

    model.selected_building->road_access_requirement =
        "RUA CONECTADA AO MAPA E ACESSO GARANTIDO PELA ENTRADA PRINCIPAL DO EDIFICIO";
    model.selected_building->has_service_pricing = true;
    ui.update_layout(1280, 800, model);
    const auto expanded_context_panel = std::find_if(ui.panels().begin(), ui.panels().end(), [](const UiRect& panel) {
        return panel.width == 330.0F && panel.y == 84.0F;
    });
    require(expanded_context_panel != ui.panels().end() && expanded_context_panel->height > 308.0F,
            "long building details expand contextual panel instead of clipping");
    model.selected_building.reset();

    model.build_panel_open = false;
    model.active_tool = UiTool::roads;
    ui.update_layout(1280, 800, model);
    const auto road_close = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::close_tool_panel;
    });
    require(road_close != ui.buttons().end(), "road tool has a close control");
    const auto road_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::activate_roads;
    });
    require(road_button != ui.buttons().end(), "road toolbar button exists");
    const UiInputResult road_click = ui.handle_mouse_button_down(road_button->bounds.x + 4.0F, road_button->bounds.y + 4.0F, true);
    require(road_click.consumed && road_click.action && road_click.action->action == UiAction::activate_roads,
            "road mode button");

    model.active_tool = UiTool::sidewalks;
    ui.update_layout(1280, 800, model);
    const auto cement_path_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::activate_sidewalks && button.label == "PISO";
    });
    require(cement_path_button != ui.buttons().end(), "cement path toolbar button exists beside roads");
    const UiInputResult cement_path_click = ui.handle_mouse_button_down(cement_path_button->bounds.x + 4.0F,
                                                                         cement_path_button->bounds.y + 4.0F, true);
    require(cement_path_click.consumed && cement_path_click.action &&
                cement_path_click.action->action == UiAction::activate_sidewalks,
            "cement path mode button");

    model.active_tool = UiTool::land;
    ui.update_layout(1280, 800, model);
    const auto land_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::activate_land;
    });
    require(land_button != ui.buttons().end(), "land toolbar button exists");
    const UiInputResult land_click = ui.handle_mouse_button_down(land_button->bounds.x + 4.0F, land_button->bounds.y + 4.0F, true);
    require(land_click.consumed && land_click.action && land_click.action->action == UiAction::activate_land,
            "land mode button");

    model.active_tool = UiTool::remove;
    ui.update_layout(1280, 800, model);
    const auto remove_button = std::find_if(ui.buttons().begin(), ui.buttons().end(), [](const UiButton& button) {
        return button.action == UiAction::activate_remove;
    });
    require(remove_button != ui.buttons().end(), "remove toolbar button exists");
    const UiInputResult remove_click = ui.handle_mouse_button_down(remove_button->bounds.x + 4.0F, remove_button->bounds.y + 4.0F, true);
    require(remove_click.consumed && remove_click.action && remove_click.action->action == UiAction::activate_remove,
            "remove mode button");

    require(!ui.consumes_point(700, 500), "map point is not consumed by UI");
    require(ui.consumes_point(20, 20), "top UI consumes input");

    std::cout << "ui manager tests passed\n";
    return 0;
}
