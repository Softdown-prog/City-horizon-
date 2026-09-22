from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


header = Path("src/ui_manager.h")
cpp = Path("src/ui_manager.cpp")

replace_once(
    header,
    """    float build_scroll_offset_ = 0.0F;\n    float build_scroll_max_ = 0.0F;\n    mutable std::unordered_map<std::string, UiThumbnail> thumbnails_;\n""",
    """    float build_scroll_offset_ = 0.0F;\n    float build_scroll_max_ = 0.0F;\n    float build_panel_header_height_ = 42.0F;\n    std::string build_category_filter_ = \"TODOS\";\n    mutable std::unordered_map<std::string, UiThumbnail> thumbnails_;\n""",
    "header construction catalog state",
)

replace_once(
    cpp,
    """    const UiOverlay previous_overlay = model_.overlay;\n    const bool entering_settings = model.overlay == UiOverlay::settings && previous_overlay != UiOverlay::settings;\n    model_ = model;\n""",
    """    const UiOverlay previous_overlay = model_.overlay;\n    const bool entering_settings = model.overlay == UiOverlay::settings && previous_overlay != UiOverlay::settings;\n    const bool entering_build_panel = model.build_panel_open && !model_.build_panel_open;\n    model_ = model;\n    if (entering_build_panel) {\n        build_category_filter_ = \"TODOS\";\n        build_scroll_offset_ = 0.0F;\n    }\n""",
    "detect construction catalog opening",
)

text = cpp.read_text(encoding="utf-8")
start_marker = "    if (model.build_panel_open || model.farming_panel_open || model.active_tool == UiTool::decoration) {"
end_marker = "\n\n    if (model.land_details && model.active_tool == UiTool::land)"
start = text.index(start_marker)
end = text.index(end_marker, start)
new_layout = r'''    if (model.build_panel_open) {
        const float maximum_panel_width = std::max(320.0F, width - kMargin * 2.0F);
        const float panel_width = std::min(maximum_panel_width, std::clamp(width * 0.62F, 480.0F, 760.0F));
        const float panel_y = 84.0F;
        const float panel_height = std::max(180.0F, toolbar_y - panel_y - 8.0F);
        const UiRect panel_bounds = {kMargin, panel_y, panel_width, panel_height};
        add_panel(panel_bounds);
        build_panel_bounds_ = panel_bounds;

        std::vector<std::string> categories;
        for (const UiBuildItem& item : model.build_items) {
            if (std::find(categories.begin(), categories.end(), item.category) == categories.end()) categories.push_back(item.category);
        }
        if (build_category_filter_ != "TODOS" &&
            std::find(categories.begin(), categories.end(), build_category_filter_) == categories.end()) {
            build_category_filter_ = "TODOS";
            build_scroll_offset_ = 0.0F;
        }

        constexpr float tab_gap = 6.0F;
        constexpr float tab_height = 30.0F;
        constexpr float desired_tab_width = 138.0F;
        const float tabs_available_width = panel_width - 16.0F;
        const int tabs_per_row = std::max(1, static_cast<int>((tabs_available_width + tab_gap) / (desired_tab_width + tab_gap)));
        const std::size_t tab_count = categories.size() + 1U;
        const int tab_rows = std::max(1, static_cast<int>((tab_count + static_cast<std::size_t>(tabs_per_row) - 1U) /
                                                          static_cast<std::size_t>(tabs_per_row)));
        const float tab_width = (tabs_available_width - tab_gap * static_cast<float>(tabs_per_row - 1)) /
                                static_cast<float>(tabs_per_row);
        const float tabs_y = panel_y + 45.0F;
        build_panel_header_height_ = 51.0F + static_cast<float>(tab_rows) * (tab_height + tab_gap);

        std::vector<std::string> tab_labels;
        tab_labels.push_back("TODOS");
        tab_labels.insert(tab_labels.end(), categories.begin(), categories.end());
        for (std::size_t index = 0; index < tab_labels.size(); ++index) {
            const int row = static_cast<int>(index) / tabs_per_row;
            const int column = static_cast<int>(index) % tabs_per_row;
            const std::string& category = tab_labels[index];
            add_button({panel_bounds.x + 8.0F + static_cast<float>(column) * (tab_width + tab_gap),
                        tabs_y + static_cast<float>(row) * (tab_height + tab_gap), tab_width, tab_height},
                       category, UiAction::none, true, category == build_category_filter_, "build_category:" + category);
        }

        std::vector<const UiBuildItem*> filtered_items;
        for (const UiBuildItem& item : model.build_items) {
            if (build_category_filter_ == "TODOS" || item.category == build_category_filter_) filtered_items.push_back(&item);
        }

        constexpr float card_height = 108.0F;
        constexpr float card_gap = 8.0F;
        constexpr float horizontal_padding = 8.0F;
        const int columns = panel_width >= 620.0F ? 2 : 1;
        const float scrollbar_reserve = 8.0F;
        const float cards_width = panel_width - horizontal_padding * 2.0F - scrollbar_reserve;
        const float card_width = (cards_width - card_gap * static_cast<float>(columns - 1)) / static_cast<float>(columns);
        const float content_top = panel_y + build_panel_header_height_;
        const float visible_height = std::max(1.0F, panel_height - build_panel_header_height_ - 8.0F);
        const std::size_t row_count = (filtered_items.size() + static_cast<std::size_t>(columns) - 1U) /
                                      static_cast<std::size_t>(columns);
        const float content_height = static_cast<float>(row_count) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);

        for (std::size_t index = 0; index < filtered_items.size(); ++index) {
            const int row = static_cast<int>(index / static_cast<std::size_t>(columns));
            const int column = static_cast<int>(index % static_cast<std::size_t>(columns));
            const float card_x = panel_bounds.x + horizontal_padding + static_cast<float>(column) * (card_width + card_gap);
            const float card_y = content_top + static_cast<float>(row) * (card_height + card_gap) - build_scroll_offset_;
            const UiRect card_bounds = {card_x, card_y, card_width, card_height};
            if (card_bounds.y >= content_top && card_bounds.y + card_bounds.height <= panel_bounds.y + panel_bounds.height - 6.0F) {
                const UiBuildItem& item = *filtered_items[index];
                add_build_card(card_bounds, item, item.definition_id == model.selected_building_id, UiAction::select_building);
            }
        }
    } else if (model.farming_panel_open || model.active_tool == UiTool::decoration) {
        constexpr float panel_width = 410.0F;
        const float header_height = model.farming_panel_open ? 60.0F : 42.0F;
        build_panel_header_height_ = header_height;
        constexpr float card_height = 96.0F;
        constexpr float card_gap = 6.0F;
        const float panel_y = 84.0F;
        const float panel_height = std::max(120.0F, toolbar_y - panel_y - 8.0F);
        const UiRect panel_bounds = {kMargin, panel_y, panel_width, panel_height};
        add_panel(panel_bounds);
        build_panel_bounds_ = panel_bounds;
        const float visible_height = panel_height - header_height - 8.0F;
        const std::vector<UiBuildItem>& panel_items = model.farming_panel_open ? model.farming_items : model.decor_items;
        const UiAction panel_action = model.farming_panel_open ? UiAction::select_farming_item : UiAction::select_building;
        const std::string& panel_selected_id = model.farming_panel_open ? model.selected_farming_id : model.selected_building_id;
        const float content_height = static_cast<float>(panel_items.size()) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);
        float item_y = panel_y + header_height - build_scroll_offset_;
        for (const UiBuildItem& item : panel_items) {
            const UiRect card_bounds = {panel_bounds.x + 8.0F, item_y, panel_bounds.width - 16.0F, card_height};
            if (card_bounds.y >= panel_bounds.y + header_height && card_bounds.y + card_bounds.height <= panel_bounds.y + panel_bounds.height - 6.0F)
                add_build_card(card_bounds, item, item.definition_id == panel_selected_id, panel_action);
            item_y += card_height + card_gap;
        }
    } else {
        build_scroll_offset_ = 0.0F;
        build_scroll_max_ = 0.0F;
        build_panel_header_height_ = 42.0F;
    }'''
text = text[:start] + new_layout + text[end:]
cpp.write_text(text, encoding="utf-8")

replace_once(
    cpp,
    """        const float left_edge = (model.build_panel_open || model.farming_panel_open) ? 394.0F : kMargin;\n""",
    """        const float left_edge = build_panel_bounds_ ? build_panel_bounds_->x + build_panel_bounds_->width + 8.0F : kMargin;\n""",
    "status toast follows catalog width",
)

replace_once(
    cpp,
    """        if (button.enabled) {\n            if (button.action == UiAction::settings_reset) {\n""",
    """        if (button.enabled) {\n            if (button.action == UiAction::none && button.payload.rfind(\"build_category:\", 0) == 0) {\n                build_category_filter_ = button.payload.substr(std::string(\"build_category:\").size());\n                build_scroll_offset_ = 0.0F;\n                update_layout(viewport_width_, viewport_height_, model_);\n                return result;\n            }\n            if (button.action == UiAction::settings_reset) {\n""",
    "construction category click",
)

text = cpp.read_text(encoding="utf-8")
start_marker = "    if (build_panel_bounds_) {"
end_marker = "\n    if (model_.land_details && model_.active_tool == UiTool::land)"
start = text.index(start_marker)
end = text.index(end_marker, start)
new_render = r'''    if (build_panel_bounds_) {
        const UiRect& panel = *build_panel_bounds_;
        if (model_.build_panel_open) {
            std::size_t filtered_count = 0;
            for (const UiBuildItem& item : model_.build_items) {
                if (build_category_filter_ == "TODOS" || item.category == build_category_filter_) ++filtered_count;
            }
            draw_text(renderer, panel.x + 12.0F, panel.y + 10.0F, "CATALOGO DE CONSTRUCAO", 232, 240, 244);
            draw_text_fit(renderer, panel.x + 12.0F, panel.y + 26.0F, panel.width - 24.0F,
                          std::to_string(filtered_count) + " DE " + std::to_string(model_.build_items.size()) +
                          " ITENS  |  " + build_category_filter_, 151, 178, 192);
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            const float separator_y = panel.y + build_panel_header_height_ - 5.0F;
            SDL_RenderLine(renderer, panel.x + 8.0F, separator_y, panel.x + panel.width - 8.0F, separator_y);
        } else {
            const bool farming = model_.farming_panel_open;
            draw_text(renderer, panel.x + 12.0F, panel.y + 12.0F, farming ? "AGRICULTURA" : "DECORACAO", 232, 240, 244);
            if (farming) {
                draw_text_fit(renderer, panel.x + 12.0F, panel.y + 27.0F, panel.width - 24.0F, model_.farming_infrastructure, 151, 178, 192);
                draw_text_fit(renderer, panel.x + 12.0F, panel.y + 42.0F, panel.width - 24.0F,
                              model_.farming_stock + " | " + model_.farming_tile_status, 151, 178, 192);
            } else {
                draw_text(renderer, panel.x + 12.0F, panel.y + 27.0F,
                          std::to_string(model_.decor_items.size()) + " ITENS", 151, 178, 192);
            }
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            const float separator_y = panel.y + build_panel_header_height_ - 4.0F;
            SDL_RenderLine(renderer, panel.x + 8.0F, separator_y, panel.x + panel.width - 8.0F, separator_y);
        }
        if (build_scroll_max_ > 0.0F) {
            const float track_y = panel.y + build_panel_header_height_;
            const float track_height = std::max(20.0F, panel.height - build_panel_header_height_ - 8.0F);
            const float visible_height = track_height;
            const float content_height = visible_height + build_scroll_max_;
            const float thumb_height = std::max(20.0F, track_height * visible_height / content_height);
            const float thumb_y = track_y + (track_height - thumb_height) * (build_scroll_offset_ / build_scroll_max_);
            const SDL_FRect track = {panel.x + panel.width - 7.0F, track_y, 3.0F, track_height};
            const SDL_FRect thumb = {panel.x + panel.width - 8.0F, thumb_y, 5.0F, thumb_height};
            SDL_SetRenderDrawColor(renderer, 35, 68, 85, SDL_ALPHA_OPAQUE);
            SDL_RenderFillRect(renderer, &track);
            SDL_SetRenderDrawColor(renderer, 113, 163, 185, SDL_ALPHA_OPAQUE);
            SDL_RenderFillRect(renderer, &thumb);
        }
    }'''
text = text[:start] + new_render + text[end:]
cpp.write_text(text, encoding="utf-8")
