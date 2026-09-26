#include "ui_manager.h"

#include "fence_placement_controller.h"
#include "fence_system.h"
#include "src/ch_core/contracts.h"
#include "src/runtime_view_state.h"

#include <array>
#include <cmath>
#include <filesystem>
#include <string_view>

// Keep the established UI implementation intact while removing energy from the
// public gameplay surface. Compatibility names also let the Park fence tool
// intercept only the input it owns without duplicating the existing UI code.
#define update_layout update_layout_legacy
#define handle_mouse_motion handle_mouse_motion_legacy
#define handle_mouse_button_down handle_mouse_button_down_legacy
#define handle_mouse_button_up handle_mouse_button_up_legacy
#define render render_legacy
#include "ui_manager_legacy_impl.inl"
#undef render
#undef handle_mouse_button_up
#undef handle_mouse_button_down
#undef handle_mouse_motion
#undef update_layout

namespace {

constexpr std::string_view kParkCategory = "PARK";
constexpr std::string_view kLegacyParkCategory = "CITY PARK";
constexpr std::string_view kParkFenceToolId = "park_fence_classic_iron_v1";

FenceManager g_park_fences(ch::contracts::kMapMin, ch::contracts::kMapMax);
FencePlacementController g_park_fence_placement(g_park_fences);
bool g_park_fence_tool_active = false;
std::string g_park_fence_status = "GRADE DO PARQUE: CLIQUE E ARRASTE ENTRE AS BORDAS DOS TILES";
std::optional<UiRect> g_floor_catalog_bounds;

[[nodiscard]] std::string runtime_asset_path(const std::filesystem::path& relative) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / relative).string();
}

[[nodiscard]] std::array<UiBuildItem, 3> floor_catalog_items() {
    return {{
        {"dirt_path", "Tile de Terra", "PISO", "$0 / TILE", true,
         runtime_asset_path("assets/terrain/paths/dirt_01/dirt_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1},
        {"sand_path", "Tile de Areia", "PISO", "$0 / TILE", true,
         runtime_asset_path("assets/terrain/paths/sand_01/sand_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1},
        {"grass", "Tile de Grama", "PISO", "$0 / TILE", true,
         runtime_asset_path("assets/terrain/grass_isometric_01.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1},
    }};
}

[[nodiscard]] std::string park_fence_thumbnail_path() {
    return runtime_asset_path("assets/ui/thumbnails/buildings/park_fence_classic_iron_v1.png");
}

void deactivate_park_fence_tool() {
    g_park_fence_placement.cancel_drag();
    g_park_fence_tool_active = false;
}

bool contains_energy_term(const std::string& value) {
    return value.find("ENERGIA") != std::string::npos ||
           value.find("POWER") != std::string::npos;
}

std::string remove_energy_segments(const std::string& value, const std::string& separator) {
    std::string result;
    std::size_t start = 0;
    while (start <= value.size()) {
        const std::size_t end = value.find(separator, start);
        const std::string part = value.substr(
            start, end == std::string::npos ? std::string::npos : end - start);
        if (!part.empty() && !contains_energy_term(part)) {
            if (!result.empty()) result += separator;
            result += part;
        }
        if (end == std::string::npos) break;
        start = end + separator.size();
    }
    return result;
}

GameplayUiModel runtime_ui_model(GameplayUiModel model) {
    model.power_demand.clear();
    model.power_capacity.clear();
    model.administration_services = remove_energy_segments(model.administration_services, " / ");

    if (model.selected_building) {
        model.selected_building->energy_consumption.clear();
        model.selected_building->energy_production.clear();
        if (model.selected_building->category == kLegacyParkCategory) {
            model.selected_building->category = std::string(kParkCategory);
        }
    }

    for (UiBuildItem& item : model.build_items) {
        item.requirements = remove_energy_segments(item.requirements, " | ");
        if (item.category == kLegacyParkCategory) item.category = std::string(kParkCategory);
    }
    for (UiBuildItem& item : model.decor_items) {
        item.requirements = remove_energy_segments(item.requirements, " | ");
        if (item.category == kLegacyParkCategory) item.category = std::string(kParkCategory);
    }

    const bool already_has_fence = std::any_of(
        model.build_items.begin(), model.build_items.end(), [](const UiBuildItem& item) {
            return item.definition_id == kParkFenceToolId;
        });
    if (!already_has_fence) {
        model.build_items.push_back({
            std::string(kParkFenceToolId),
            "Grade Classica do Parque",
            std::string(kParkCategory),
            "SEM CUSTO",
            true,
            park_fence_thumbnail_path(),
            "BORDA DO GRID",
            "CLIQUE E ARRASTE | CONEXAO AUTOMATICA",
            1,
        });
    }

    model.debug_lines.erase(
        std::remove_if(model.debug_lines.begin(), model.debug_lines.end(),
                       [](const std::string& line) { return contains_energy_term(line); }),
        model.debug_lines.end());

    const std::size_t deficit = model.status.find(" | POWER DEFICIT");
    if (deficit != std::string::npos) model.status.erase(deficit);

    if (g_park_fence_tool_active) {
        model.selected_building_id = std::string(kParkFenceToolId);
        model.placement_preview_path = park_fence_thumbnail_path();
        model.placement_preview_frame_count = 1;
        model.placement_rotatable = false;
        model.placement_rotation_label = "AUTO";
        model.status = g_park_fence_status;
    }

    return model;
}

[[nodiscard]] std::optional<FenceVertex> nearest_fence_vertex(const float screen_x, const float screen_y) {
    const ch::runtime_view::ViewSnapshot& view = ch::runtime_view::snapshot();
    if (!view.valid) return std::nullopt;

    const ch::GridCoord tile = ch::screen_to_tile_coord(
        screen_x, screen_y, view.camera, view.viewport_width, view.viewport_height);
    const std::array<FenceVertex, 4> candidates = {{
        {tile.x, tile.y},
        {tile.x + 1, tile.y},
        {tile.x, tile.y + 1},
        {tile.x + 1, tile.y + 1},
    }};

    std::optional<FenceVertex> nearest;
    float nearest_distance = 0.0F;
    for (const FenceVertex vertex : candidates) {
        if (!g_park_fences.is_inside_vertex_grid(vertex.x, vertex.y)) continue;
        const ch::ScreenPoint projected = ch::world_to_screen_point(
            static_cast<float>(vertex.x), static_cast<float>(vertex.y),
            view.camera, view.viewport_width, view.viewport_height);
        const float dx = projected.x - screen_x;
        const float dy = projected.y - screen_y;
        const float distance = dx * dx + dy * dy;
        if (!nearest || distance < nearest_distance) {
            nearest = vertex;
            nearest_distance = distance;
        }
    }
    return nearest;
}

void set_fence_draw_color(SDL_Renderer* renderer, const bool preview, const bool highlight) {
    if (preview) {
        SDL_SetRenderDrawColor(renderer, highlight ? 132 : 96, highlight ? 232 : 205,
                               highlight ? 156 : 124, 225);
    } else {
        SDL_SetRenderDrawColor(renderer, highlight ? 63 : 37, highlight ? 118 : 78,
                               highlight ? 78 : 55, 245);
    }
}

void draw_fence_post(SDL_Renderer* renderer, const FenceVertex vertex,
                     const ch::runtime_view::ViewSnapshot& view, const bool preview) {
    const ch::ScreenPoint ground = ch::world_to_screen_point(
        static_cast<float>(vertex.x), static_cast<float>(vertex.y),
        view.camera, view.viewport_width, view.viewport_height);
    const float height = 31.0F * view.camera.zoom;
    const float half_width = std::max(1.0F, 1.4F * view.camera.zoom);
    set_fence_draw_color(renderer, preview, false);
    SDL_RenderLine(renderer, ground.x - half_width, ground.y, ground.x - half_width, ground.y - height);
    SDL_RenderLine(renderer, ground.x, ground.y, ground.x, ground.y - height);
    SDL_RenderLine(renderer, ground.x + half_width, ground.y, ground.x + half_width, ground.y - height);
    set_fence_draw_color(renderer, preview, true);
    SDL_RenderLine(renderer, ground.x - half_width, ground.y - height, ground.x + half_width, ground.y - height);
}

void draw_fence_segment(SDL_Renderer* renderer, const FenceVertex from, const FenceVertex to,
                        const ch::runtime_view::ViewSnapshot& view, const bool preview) {
    const ch::ScreenPoint a = ch::world_to_screen_point(
        static_cast<float>(from.x), static_cast<float>(from.y),
        view.camera, view.viewport_width, view.viewport_height);
    const ch::ScreenPoint b = ch::world_to_screen_point(
        static_cast<float>(to.x), static_cast<float>(to.y),
        view.camera, view.viewport_width, view.viewport_height);
    const float lower = 10.0F * view.camera.zoom;
    const float upper = 22.0F * view.camera.zoom;
    const float thickness = std::max(1.0F, view.camera.zoom);

    set_fence_draw_color(renderer, preview, false);
    for (const float y_offset : {lower, upper}) {
        SDL_RenderLine(renderer, a.x, a.y - y_offset, b.x, b.y - y_offset);
        SDL_RenderLine(renderer, a.x, a.y - y_offset - thickness, b.x, b.y - y_offset - thickness);
    }
    set_fence_draw_color(renderer, preview, true);
    SDL_RenderLine(renderer, a.x, a.y - upper - thickness, b.x, b.y - upper - thickness);
}

void render_fence_connections(SDL_Renderer* renderer, const FenceVertex vertex,
                              const FenceConnection connections,
                              const ch::runtime_view::ViewSnapshot& view, const bool preview) {
    if (has_connection(connections, CardinalDirection::east)) {
        draw_fence_segment(renderer, vertex, {vertex.x + 1, vertex.y}, view, preview);
    }
    if (has_connection(connections, CardinalDirection::south)) {
        draw_fence_segment(renderer, vertex, {vertex.x, vertex.y + 1}, view, preview);
    }
}

void render_park_fences(SDL_Renderer* renderer) {
    if (renderer == nullptr) return;
    const ch::runtime_view::ViewSnapshot& view = ch::runtime_view::snapshot();
    if (!view.valid) return;

    for (const FenceNode& node : g_park_fences.nodes()) {
        render_fence_connections(renderer, {node.vertex_x, node.vertex_y}, node.connections, view, false);
    }
    for (const FenceNode& node : g_park_fences.nodes()) {
        draw_fence_post(renderer, {node.vertex_x, node.vertex_y}, view, false);
    }

    if (!g_park_fence_tool_active || !g_park_fence_placement.dragging()) return;
    const std::vector<FencePlacementPreviewNode> preview = g_park_fence_placement.preview_nodes();
    for (const FencePlacementPreviewNode& node : preview) {
        render_fence_connections(renderer, node.vertex, node.state.connections, view, true);
    }
    for (const FencePlacementPreviewNode& node : preview) {
        draw_fence_post(renderer, node.vertex, view, true);
    }
}

void fill_rect(SDL_Renderer* renderer, const SDL_FRect& rect,
               const Uint8 r, const Uint8 g, const Uint8 b,
               const Uint8 a = SDL_ALPHA_OPAQUE) {
    SDL_SetRenderDrawColor(renderer, r, g, b, a);
    SDL_RenderFillRect(renderer, &rect);
}

}  // namespace

void GameplayUi::update_layout(const int viewport_width, const int viewport_height,
                               const GameplayUiModel& model) {
    if (g_park_fence_tool_active &&
        (!model.build_panel_open || model.overlay != UiOverlay::none ||
         model.active_tool != UiTool::buildings ||
         (!model.selected_building_id.empty() && model.selected_building_id != kParkFenceToolId))) {
        deactivate_park_fence_tool();
    }

    GameplayUiModel runtime_model = runtime_ui_model(model);
    update_layout_legacy(viewport_width, viewport_height, runtime_model);
    g_floor_catalog_bounds.reset();

    const float width = static_cast<float>(std::max(viewport_width, 1));
    const float height = static_cast<float>(std::max(viewport_height, 1));
    const float toolbar_y = height - kToolbarHeight - kMargin;
    const float drawer_x = 6.0F;
    const float drawer_y = 84.0F;
    const float drawer_width = std::min(std::max(330.0F, width * 0.29F), 390.0F);
    const float drawer_height = std::max(180.0F, toolbar_y - drawer_y - 8.0F);

    const auto erase_legacy_catalog = [&]() {
        if (!build_panel_bounds_) return;
        const UiRect old = *build_panel_bounds_;
        panels_.erase(
            std::remove_if(panels_.begin(), panels_.end(), [&](const UiRect& panel) {
                return std::fabs(panel.x - old.x) < 0.1F && std::fabs(panel.y - old.y) < 0.1F &&
                       std::fabs(panel.width - old.width) < 0.1F && std::fabs(panel.height - old.height) < 0.1F;
            }),
            panels_.end());
        buttons_.erase(
            std::remove_if(buttons_.begin(), buttons_.end(), [&](const UiButton& button) {
                const float center_x = button.bounds.x + button.bounds.width * 0.5F;
                const float center_y = button.bounds.y + button.bounds.height * 0.5F;
                return old.contains(center_x, center_y);
            }),
            buttons_.end());
        build_panel_bounds_.reset();
        placement_preview_bounds_.reset();
    };

    if (runtime_model.overlay == UiOverlay::none && runtime_model.build_panel_open) {
        erase_legacy_catalog();

        const UiRect panel = {drawer_x, drawer_y, drawer_width, drawer_height};
        add_panel(panel);
        build_panel_bounds_ = panel;
        add_button({panel.x + panel.width - 29.0F, panel.y + 9.0F, 19.0F, 19.0F},
                   "X", UiAction::close_tool_panel);

        std::vector<std::string> categories;
        for (const UiBuildItem& item : runtime_model.build_items) {
            if (std::find(categories.begin(), categories.end(), item.category) == categories.end()) {
                categories.push_back(item.category);
            }
        }
        if (build_category_filter_ != "TODOS" &&
            std::find(categories.begin(), categories.end(), build_category_filter_) == categories.end()) {
            build_category_filter_ = "TODOS";
            build_scroll_offset_ = 0.0F;
        }

        std::vector<std::string> tab_labels = {"TODOS"};
        tab_labels.insert(tab_labels.end(), categories.begin(), categories.end());
        constexpr int tab_columns = 2;
        constexpr float tab_gap = 4.0F;
        constexpr float tab_height = 26.0F;
        const float tab_width = (panel.width - 16.0F - tab_gap) / 2.0F;
        const float tabs_y = panel.y + 43.0F;
        const int tab_rows = std::max(1, static_cast<int>((tab_labels.size() + 1U) / 2U));
        for (std::size_t index = 0; index < tab_labels.size(); ++index) {
            const int row = static_cast<int>(index) / tab_columns;
            const int column = static_cast<int>(index) % tab_columns;
            const std::string& category = tab_labels[index];
            add_button({panel.x + 8.0F + static_cast<float>(column) * (tab_width + tab_gap),
                        tabs_y + static_cast<float>(row) * (tab_height + tab_gap),
                        tab_width, tab_height},
                       category, UiAction::none, true, category == build_category_filter_,
                       "build_category:" + category);
        }

        build_panel_header_height_ = 49.0F + static_cast<float>(tab_rows) * (tab_height + tab_gap);
        constexpr float preview_height = 72.0F;
        placement_preview_bounds_ = {panel.x + 8.0F, panel.y + build_panel_header_height_ + 2.0F,
                                     panel.width - 16.0F, preview_height};
        const float arrows_y = placement_preview_bounds_->y + preview_height + 5.0F;
        const bool can_rotate = !runtime_model.selected_building_id.empty() && runtime_model.placement_rotatable;
        add_button({panel.x + 48.0F, arrows_y, 82.0F, 28.0F}, "< ESQ", UiAction::rotate_left, can_rotate);
        add_button({panel.x + panel.width - 130.0F, arrows_y, 82.0F, 28.0F}, "DIR >", UiAction::rotate_right, can_rotate);
        build_panel_header_height_ += preview_height + 38.0F;

        std::vector<const UiBuildItem*> filtered_items;
        for (const UiBuildItem& item : runtime_model.build_items) {
            if (build_category_filter_ == "TODOS" || item.category == build_category_filter_) {
                filtered_items.push_back(&item);
            }
        }

        constexpr float card_height = 90.0F;
        constexpr float card_gap = 6.0F;
        const float content_top = panel.y + build_panel_header_height_;
        const float visible_height = std::max(1.0F, panel.height - build_panel_header_height_ - 8.0F);
        const float content_height = static_cast<float>(filtered_items.size()) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);

        float card_y = content_top - build_scroll_offset_;
        for (const UiBuildItem* item : filtered_items) {
            const UiRect card = {panel.x + 8.0F, card_y, panel.width - 16.0F, card_height};
            if (card.y >= content_top && card.y + card.height <= panel.y + panel.height - 7.0F) {
                add_build_card(card, *item, item->definition_id == runtime_model.selected_building_id,
                               UiAction::select_building);
            }
            card_y += card_height + card_gap;
        }
    } else if (runtime_model.overlay == UiOverlay::none &&
               (runtime_model.farming_panel_open || runtime_model.active_tool == UiTool::decoration)) {
        erase_legacy_catalog();

        const UiRect panel = {drawer_x, drawer_y, drawer_width, drawer_height};
        add_panel(panel);
        build_panel_bounds_ = panel;
        add_button({panel.x + panel.width - 29.0F, panel.y + 9.0F, 19.0F, 19.0F},
                   "X", UiAction::close_tool_panel);

        const bool farming = runtime_model.farming_panel_open;
        build_panel_header_height_ = farming ? 60.0F : 42.0F;
        const std::vector<UiBuildItem>& items = farming ? runtime_model.farming_items : runtime_model.decor_items;
        const UiAction action = farming ? UiAction::select_farming_item : UiAction::select_building;
        const std::string& selected = farming ? runtime_model.selected_farming_id : runtime_model.selected_building_id;

        constexpr float card_height = 90.0F;
        constexpr float card_gap = 6.0F;
        const float content_top = panel.y + build_panel_header_height_;
        const float visible_height = std::max(1.0F, panel.height - build_panel_header_height_ - 8.0F);
        const float content_height = static_cast<float>(items.size()) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);

        float card_y = content_top - build_scroll_offset_;
        for (const UiBuildItem& item : items) {
            const UiRect card = {panel.x + 8.0F, card_y, panel.width - 16.0F, card_height};
            if (card.y >= content_top && card.y + card.height <= panel.y + panel.height - 7.0F) {
                add_build_card(card, item, item.definition_id == selected, action);
            }
            card_y += card_height + card_gap;
        }
    } else if (runtime_model.overlay == UiOverlay::none && runtime_model.active_tool == UiTool::sidewalks) {
        // PISO uses the same card language as buildings, but in the same narrow
        // corner drawer used by the other gameplay catalogues.
        buttons_.erase(
            std::remove_if(buttons_.begin(), buttons_.end(), [](const UiButton& button) {
                return button.action == UiAction::select_sidewalk_style;
            }),
            buttons_.end());

        const float desired_height = 52.0F + 3.0F * 90.0F + 2.0F * 6.0F + 9.0F;
        const UiRect panel = {drawer_x, drawer_y, drawer_width, std::min(drawer_height, desired_height)};
        add_panel(panel);
        g_floor_catalog_bounds = panel;
        add_button({panel.x + panel.width - 29.0F, panel.y + 9.0F, 19.0F, 19.0F},
                   "X", UiAction::close_tool_panel);

        const std::array<UiBuildItem, 3> items = floor_catalog_items();
        float card_y = panel.y + 52.0F;
        for (const UiBuildItem& item : items) {
            const UiRect card = {panel.x + 8.0F, card_y, panel.width - 16.0F, 90.0F};
            add_build_card(card, item, item.definition_id == runtime_model.sidewalk_style,
                           UiAction::select_sidewalk_style);
            card_y += 96.0F;
        }
    }
}

void GameplayUi::handle_mouse_motion(const float mouse_x, const float mouse_y) {
    handle_mouse_motion_legacy(mouse_x, mouse_y);
    if (!g_park_fence_tool_active || !g_park_fence_placement.dragging() ||
        consumes_point(mouse_x, mouse_y)) {
        return;
    }
    if (const std::optional<FenceVertex> vertex = nearest_fence_vertex(mouse_x, mouse_y)) {
        g_park_fence_placement.update_drag(*vertex);
    }
}

UiInputResult GameplayUi::handle_mouse_button_down(const float mouse_x, const float mouse_y,
                                                   const bool primary_button) {
    UiInputResult result = handle_mouse_button_down_legacy(mouse_x, mouse_y, primary_button);

    if (result.consumed) {
        if (result.action && result.action->action == UiAction::select_building &&
            result.action->payload == kParkFenceToolId) {
            g_park_fence_tool_active = true;
            g_park_fence_placement.cancel_drag();
            g_park_fence_status = "GRADE DO PARQUE: CLIQUE E ARRASTE ENTRE AS BORDAS DOS TILES";
            result.action.reset();
        } else if (result.action && result.action->action != UiAction::none) {
            deactivate_park_fence_tool();
        }
        if (g_park_fence_tool_active && build_category_filter_ != kParkCategory) {
            deactivate_park_fence_tool();
        }
        return result;
    }

    if (!g_park_fence_tool_active || model_.overlay != UiOverlay::none) return result;

    result.consumed = true;
    result.action.reset();
    if (!primary_button) {
        deactivate_park_fence_tool();
        g_park_fence_status = "GRADE DO PARQUE CANCELADA";
        return result;
    }

    const std::optional<FenceVertex> vertex = nearest_fence_vertex(mouse_x, mouse_y);
    if (!vertex) {
        g_park_fence_status = "GRADE DO PARQUE: FORA DO MAPA";
        return result;
    }

    g_park_fence_placement.begin_drag(*vertex);
    g_park_fence_status = "GRADE DO PARQUE: ARRASTE E SOLTE PARA CONSTRUIR";
    return result;
}

void GameplayUi::handle_mouse_button_up(const float mouse_x, const float mouse_y) {
    const bool released_over_ui = consumes_point(mouse_x, mouse_y);
    handle_mouse_button_up_legacy(mouse_x, mouse_y);

    if (!g_park_fence_tool_active || !g_park_fence_placement.dragging()) return;
    if (released_over_ui) {
        g_park_fence_placement.cancel_drag();
        g_park_fence_status = "GRADE DO PARQUE: ARRASTE CANCELADO SOBRE A INTERFACE";
        return;
    }

    if (const std::optional<FenceVertex> vertex = nearest_fence_vertex(mouse_x, mouse_y)) {
        g_park_fence_placement.update_drag(*vertex);
        const int placed = g_park_fence_placement.commit_drag();
        g_park_fence_status = placed > 0
            ? "GRADE DO PARQUE CONSTRUIDA: " + std::to_string(placed) + " PONTO(S) | CONTINUE ARRASTANDO"
            : "GRADE DO PARQUE: TRECHO JA EXISTE";
    } else {
        g_park_fence_placement.cancel_drag();
        g_park_fence_status = "GRADE DO PARQUE: FORA DO MAPA";
    }
}

void GameplayUi::render(SDL_Renderer* renderer) const {
    if (model_.overlay == UiOverlay::none) render_park_fences(renderer);
    render_legacy(renderer);
    if (renderer == nullptr || panels_.empty()) return;

    if (model_.overlay == UiOverlay::none && model_.active_tool == UiTool::sidewalks && g_floor_catalog_bounds) {
        const UiRect& panel = *g_floor_catalog_bounds;
        const SDL_FRect title_background = {panel.x + 1.0F, panel.y + 1.0F, panel.width - 38.0F, 45.0F};
        fill_rect(renderer, title_background, 16, 25, 30, 238);
        draw_text(renderer, panel.x + 12.0F, panel.y + 10.0F, "CATALOGO DE PISOS", 232, 240, 244);
        draw_text_fit(renderer, panel.x + 12.0F, panel.y + 27.0F, panel.width - 58.0F,
                      "3 TILES | PRECO POR TILE | CLIQUE PARA SELECIONAR", 151, 178, 192);
        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, panel.x + 8.0F, panel.y + 47.0F,
                       panel.x + panel.width - 8.0F, panel.y + 47.0F);
    }

    const UiRect& hud = panels_.front();
    const float width = static_cast<float>(viewport_width_);
    const float settings_x = std::max(kMargin + 270.0F, width - 50.0F);
    const float administration_x = std::max(kMargin + 120.0F, settings_x - 112.0F);
    const float pause_x = std::max(kMargin, administration_x - 124.0F);

    // Redraw the normal top HUD as three stats. This removes both the energy
    // number and the lightning icon without disturbing the existing controls.
    if (model_.overlay == UiOverlay::none) {
        const float stats_left = hud.x + 2.0F;
        const float stats_right = std::max(stats_left, pause_x);
        const SDL_FRect stats_background = {
            stats_left,
            hud.y + 2.0F,
            std::max(0.0F, stats_right - stats_left),
            std::max(0.0F, hud.height - 4.0F),
        };
        fill_rect(renderer, stats_background, 16, 39, 56, 244);
        SDL_SetRenderDrawColor(renderer, 35, 71, 92, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, stats_left, hud.y + hud.height - 2.0F,
                       stats_right, hud.y + hud.height - 2.0F);

        const float block_x = hud.x + 16.0F;
        const float block_width = std::max(1.0F, (stats_right - block_x) / 3.0F);
        draw_hud_stat(renderer, block_x, HudIcon::coins, "FUNDOS", model_.funds);
        draw_hud_stat(renderer, block_x + block_width, HudIcon::calendar, "DATA",
                      model_.day_month.empty() ? model_.date : model_.day_month,
                      model_.year);
        draw_hud_stat(renderer, block_x + block_width * 2.0F, HudIcon::people,
                      "POPULACAO", model_.population + " / " + model_.residential_capacity);

        const auto draw_icon = [&](const char* name, const SDL_FRect& bounds) {
            if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
                const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
                const SDL_FRect destination = {
                    bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                    bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                    icon->width * scale,
                    icon->height * scale,
                };
                SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
            }
        };
        draw_icon("funds", {block_x - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_icon("calendar", {block_x + block_width - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_icon("population", {block_x + block_width * 2.0F - 1.0F, 28.0F, 22.0F, 24.0F});

        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        for (int separator = 1; separator < 3; ++separator) {
            const float separator_x = block_x + block_width * static_cast<float>(separator) - 12.0F;
            SDL_RenderLine(renderer, separator_x, hud.y + 12.0F,
                           separator_x, hud.y + hud.height - 12.0F);
        }
    }

    // Legacy modal layouts still reserve the old row. Paint only that retired
    // row back to the card background so Administration/Reports contain no
    // energy label or value.
    if (model_.overlay == UiOverlay::administration && overlay_bounds_) {
        const UiRect& panel = *overlay_bounds_;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float gap = 12.0F;
        const float card_width = (panel.width - padding * 2.0F - gap) * 0.5F;
        const float right_x = panel.x + padding + card_width + gap;
        fill_rect(renderer,
                  {right_x + 8.0F, panel.y + 145.0F, card_width - 16.0F, 28.0F},
                  20, 44, 59, 252);
    } else if (model_.overlay == UiOverlay::reports && overlay_bounds_) {
        const UiRect& panel = *overlay_bounds_;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float content_x = panel.x + padding;
        const float content_width = panel.width - padding * 2.0F;
        const float gap = 12.0F;
        const float card_width = (content_width - gap) * 0.5F;
        const float right_x = content_x + card_width + gap;
        fill_rect(renderer,
                  {right_x + 8.0F, panel.y + 172.0F, card_width - 16.0F, 51.0F},
                  20, 44, 59, 252);
    }
}
