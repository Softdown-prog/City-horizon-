// Post-pass for modal screens. This file is included inside GameplayUi::render
// after the legacy renderer, so it can reuse the real modal geometry, button
// states and canonical City Horizon PNG assets without duplicating UI logic.
if (renderer != nullptr && model_.overlay != UiOverlay::none && overlay_bounds_) {
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    const UiRect& ch_modal_panel = *overlay_bounds_;

    // Strengthen the modal focus only outside the panel. This hides legacy HUD
    // details behind the dialog without repainting or obscuring its contents.
    const float ch_view_w = static_cast<float>(std::max(viewport_width_, 1));
    const float ch_view_h = static_cast<float>(std::max(viewport_height_, 1));
    const auto ch_dim_rect = [&](const SDL_FRect& rect) {
        if (rect.w <= 0.0F || rect.h <= 0.0F) return;
        SDL_SetRenderDrawColor(renderer, 1, 8, 13, 78);
        SDL_RenderFillRect(renderer, &rect);
    };
    ch_dim_rect({0.0F, 0.0F, ch_view_w, std::max(0.0F, ch_modal_panel.y)});
    ch_dim_rect({0.0F, ch_modal_panel.y + ch_modal_panel.height, ch_view_w,
                 std::max(0.0F, ch_view_h - (ch_modal_panel.y + ch_modal_panel.height))});
    ch_dim_rect({0.0F, ch_modal_panel.y, std::max(0.0F, ch_modal_panel.x), ch_modal_panel.height});
    ch_dim_rect({ch_modal_panel.x + ch_modal_panel.width, ch_modal_panel.y,
                 std::max(0.0F, ch_view_w - (ch_modal_panel.x + ch_modal_panel.width)), ch_modal_panel.height});

    // Add a second bevel pass over the existing panel. The legacy geometry is
    // intentionally preserved; this only makes the frame read like a tactile
    // pre-rendered tycoon UI element.
    const SDL_FRect ch_outer = {ch_modal_panel.x - 2.0F, ch_modal_panel.y - 2.0F,
                                ch_modal_panel.width + 4.0F, ch_modal_panel.height + 4.0F};
    const SDL_FRect ch_inner = {ch_modal_panel.x + 3.0F, ch_modal_panel.y + 3.0F,
                                std::max(0.0F, ch_modal_panel.width - 6.0F),
                                std::max(0.0F, ch_modal_panel.height - 6.0F)};
    SDL_SetRenderDrawColor(renderer, 7, 17, 24, 220);
    SDL_RenderRect(renderer, &ch_outer);
    SDL_SetRenderDrawColor(renderer, 99, 177, 202, 190);
    SDL_RenderRect(renderer, &ch_inner);
    SDL_SetRenderDrawColor(renderer, 190, 239, 248, 82);
    SDL_RenderLine(renderer, ch_modal_panel.x + 5.0F, ch_modal_panel.y + 5.0F,
                   ch_modal_panel.x + ch_modal_panel.width - 5.0F, ch_modal_panel.y + 5.0F);
    SDL_RenderLine(renderer, ch_modal_panel.x + 5.0F, ch_modal_panel.y + 5.0F,
                   ch_modal_panel.x + 5.0F, ch_modal_panel.y + ch_modal_panel.height - 5.0F);
    SDL_SetRenderDrawColor(renderer, 4, 15, 22, 190);
    SDL_RenderLine(renderer, ch_modal_panel.x + 5.0F, ch_modal_panel.y + ch_modal_panel.height - 5.0F,
                   ch_modal_panel.x + ch_modal_panel.width - 5.0F, ch_modal_panel.y + ch_modal_panel.height - 5.0F);
    SDL_RenderLine(renderer, ch_modal_panel.x + ch_modal_panel.width - 5.0F, ch_modal_panel.y + 5.0F,
                   ch_modal_panel.x + ch_modal_panel.width - 5.0F, ch_modal_panel.y + ch_modal_panel.height - 5.0F);

    const auto ch_draw_icon = [&](const char* name, const SDL_FRect& bounds, const Uint8 alpha = 255) {
        if (name == nullptr) return;
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {
                bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                icon->width * scale,
                icon->height * scale,
            };
            SDL_SetTextureAlphaMod(icon->texture, alpha);
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
            SDL_SetTextureAlphaMod(icon->texture, 255);
        }
    };

    // Every modal gets a canonical City Horizon icon badge instead of a new
    // unrelated icon set. These assets already ship in assets/ui/icons.
    const char* ch_header_icon = nullptr;
    switch (model_.overlay) {
        case UiOverlay::settings: ch_header_icon = "settings"; break;
        case UiOverlay::pause: ch_header_icon = "pause"; break;
        case UiOverlay::main_menu: ch_header_icon = "buildings"; break;
        case UiOverlay::save_load: ch_header_icon = "save"; break;
        case UiOverlay::quit_confirm: ch_header_icon = "close"; break;
        case UiOverlay::administration: ch_header_icon = "buildings"; break;
        case UiOverlay::reports: ch_header_icon = "funds"; break;
        default: break;
    }
    if (ch_header_icon != nullptr) {
        const SDL_FRect badge_shadow = {ch_modal_panel.x + 18.0F, ch_modal_panel.y + 19.0F, 46.0F, 46.0F};
        const SDL_FRect badge = {badge_shadow.x - 2.0F, badge_shadow.y - 3.0F, badge_shadow.w, badge_shadow.h};
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 105);
        SDL_RenderFillRect(renderer, &badge_shadow);
        SDL_SetRenderDrawColor(renderer, 24, 58, 76, 245);
        SDL_RenderFillRect(renderer, &badge);
        SDL_SetRenderDrawColor(renderer, 102, 184, 207, 220);
        SDL_RenderRect(renderer, &badge);
        SDL_SetRenderDrawColor(renderer, 210, 244, 250, 72);
        SDL_RenderLine(renderer, badge.x + 2.0F, badge.y + 2.0F,
                       badge.x + badge.w - 2.0F, badge.y + 2.0F);
        ch_draw_icon(ch_header_icon, {badge.x + 7.0F, badge.y + 7.0F, 32.0F, 32.0F});
    }

    const auto ch_button_icon_name = [&](const UiButton& button) -> const char* {
        switch (button.action) {
            case UiAction::settings_reset: return "rotate";
            case UiAction::settings_cancel: return "close";
            case UiAction::settings_apply: return "save";
            case UiAction::save_game: return "save";
            case UiAction::load_game: return "load";
            case UiAction::open_save_load: return "save";
            case UiAction::open_settings: return "settings";
            case UiAction::start_new_city: return "land";
            case UiAction::continue_saved_city: return "load";
            case UiAction::open_quit_confirm: return "close";
            case UiAction::quit_game: return "close";
            default: return nullptr;
        }
    };

    // Canonical icons are drawn after the modal dimmer so they remain crisp.
    for (const UiButton& button : buttons_) {
        const char* icon_name = ch_button_icon_name(button);
        if (icon_name == nullptr || !button.enabled) continue;
        const float center_x = button.bounds.x + button.bounds.width * 0.5F;
        const float center_y = button.bounds.y + button.bounds.height * 0.5F;
        if (!ch_modal_panel.contains(center_x, center_y)) continue;

        const float press_offset = button.state == UiButtonState::pressed ? 1.0F : 0.0F;
        const SDL_FRect icon_plate = {button.bounds.x + 7.0F + press_offset,
                                      button.bounds.y + (button.bounds.height - 26.0F) * 0.5F + press_offset,
                                      26.0F, 26.0F};
        SDL_SetRenderDrawColor(renderer, 5, 21, 30, button.state == UiButtonState::hover ? 190 : 150);
        SDL_RenderFillRect(renderer, &icon_plate);
        SDL_SetRenderDrawColor(renderer, button.state == UiButtonState::hover ? 123 : 72,
                               button.state == UiButtonState::hover ? 216 : 143,
                               button.state == UiButtonState::hover ? 233 : 166, 210);
        SDL_RenderRect(renderer, &icon_plate);
        ch_draw_icon(icon_name, {icon_plate.x + 3.0F, icon_plate.y + 3.0F, 20.0F, 20.0F},
                     button.state == UiButtonState::pressed ? 215 : 255);
    }

    if (model_.overlay == UiOverlay::settings) {
        // Keep the proven slider hitboxes and behavior, but make them look like
        // the same raised/inset material language used by the catalog cards.
        const auto ch_polish_slider = [&](const std::optional<UiRect>& slider_bounds, const int percent) {
            if (!slider_bounds) return;
            const UiRect& slider = *slider_bounds;
            const SDL_FRect outer_track = {slider.x - 2.0F, slider.y, slider.width + 4.0F, 20.0F};
            SDL_SetRenderDrawColor(renderer, 2, 14, 21, 215);
            SDL_RenderRect(renderer, &outer_track);
            SDL_SetRenderDrawColor(renderer, 116, 185, 204, 110);
            SDL_RenderLine(renderer, slider.x, slider.y + 1.0F,
                           slider.x + slider.width, slider.y + 1.0F);
            SDL_SetRenderDrawColor(renderer, 3, 13, 19, 210);
            SDL_RenderLine(renderer, slider.x, slider.y + 19.0F,
                           slider.x + slider.width, slider.y + 19.0F);

            const float normalized = static_cast<float>(std::clamp(percent, 0, 100)) / 100.0F;
            const float knob_x = slider.x + std::clamp(slider.width * normalized, 4.0F, slider.width - 4.0F);
            const SDL_FRect knob_shadow = {knob_x - 6.0F + 2.0F, slider.y - 3.0F + 3.0F, 12.0F, 26.0F};
            const SDL_FRect knob = {knob_x - 6.0F, slider.y - 3.0F, 12.0F, 26.0F};
            SDL_SetRenderDrawColor(renderer, 0, 0, 0, 105);
            SDL_RenderFillRect(renderer, &knob_shadow);
            SDL_SetRenderDrawColor(renderer, 200, 238, 247, 245);
            SDL_RenderRect(renderer, &knob);
            SDL_SetRenderDrawColor(renderer, 255, 255, 255, 125);
            SDL_RenderLine(renderer, knob.x + 2.0F, knob.y + 2.0F,
                           knob.x + knob.w - 2.0F, knob.y + 2.0F);
            SDL_SetRenderDrawColor(renderer, 38, 87, 108, 200);
            SDL_RenderLine(renderer, knob.x + 2.0F, knob.y + knob.h - 2.0F,
                           knob.x + knob.w - 2.0F, knob.y + knob.h - 2.0F);
        };
        ch_polish_slider(settings_master_slider_bounds_, settings_draft_master_percent_);
        ch_polish_slider(settings_effects_slider_bounds_, settings_draft_effects_percent_);
    }
}
