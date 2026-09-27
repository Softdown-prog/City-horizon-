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
            case UiAction::cancel_quit: return "close";
            case UiAction::quit_game: return "close";
            case UiAction::back_to_pause: return "pause";
            case UiAction::back_from_save_load: return "pause";
            case UiAction::open_administration: return "buildings";
            case UiAction::open_reports: return "funds";
            case UiAction::close_modal: return "close";
            default: return nullptr;
        }
    };

    const auto ch_is_primary_action = [](const UiAction action) {
        return action == UiAction::resume_game ||
               action == UiAction::start_new_city ||
               action == UiAction::continue_saved_city ||
               action == UiAction::save_game ||
               action == UiAction::settings_apply;
    };
    const auto ch_is_destructive_action = [](const UiAction action) {
        return action == UiAction::open_quit_confirm || action == UiAction::quit_game;
    };

    // Repaint modal controls as complete tactile buttons, not just flat legacy
    // rectangles with an icon laid on top. The original hitboxes and actions
    // remain untouched; this is a pure render post-pass.
    for (const UiButton& button : buttons_) {
        if (button.action == UiAction::none || button.build_card || button.color_swatch) continue;
        const float center_x = button.bounds.x + button.bounds.width * 0.5F;
        const float center_y = button.bounds.y + button.bounds.height * 0.5F;
        if (!ch_modal_panel.contains(center_x, center_y)) continue;

        const bool enabled = button.enabled;
        const bool hovered = enabled && button.state == UiButtonState::hover;
        const bool pressed = enabled && button.state == UiButtonState::pressed;
        const bool primary = enabled && ch_is_primary_action(button.action);
        const bool destructive = enabled && ch_is_destructive_action(button.action);
        const float sink = pressed ? 2.0F : 0.0F;

        Uint8 fill_r = 25;
        Uint8 fill_g = 68;
        Uint8 fill_b = 86;
        Uint8 border_r = 75;
        Uint8 border_g = 144;
        Uint8 border_b = 165;
        Uint8 text_r = 235;
        Uint8 text_g = 244;
        Uint8 text_b = 247;

        if (!enabled) {
            fill_r = 29; fill_g = 39; fill_b = 45;
            border_r = 55; border_g = 70; border_b = 77;
            text_r = 109; text_g = 123; text_b = 130;
        } else if (destructive) {
            fill_r = hovered ? 124 : 96;
            fill_g = hovered ? 50 : 40;
            fill_b = hovered ? 43 : 39;
            border_r = hovered ? 244 : 195;
            border_g = hovered ? 132 : 101;
            border_b = hovered ? 113 : 91;
            if (pressed) {
                fill_r = 74; fill_g = 32; fill_b = 31;
            }
        } else if (primary) {
            fill_r = hovered ? 34 : 27;
            fill_g = hovered ? 111 : 91;
            fill_b = hovered ? 125 : 108;
            border_r = hovered ? 126 : 90;
            border_g = hovered ? 222 : 188;
            border_b = hovered ? 227 : 204;
            if (pressed) {
                fill_r = 20; fill_g = 70; fill_b = 82;
            }
        } else if (hovered) {
            fill_r = 31; fill_g = 87; fill_b = 108;
            border_r = 104; border_g = 196; border_b = 216;
        } else if (pressed) {
            fill_r = 18; fill_g = 52; fill_b = 69;
        }

        const SDL_FRect shadow = {button.bounds.x + 3.0F, button.bounds.y + 4.0F,
                                  button.bounds.width, button.bounds.height};
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, enabled ? 104 : 62);
        SDL_RenderFillRect(renderer, &shadow);

        const SDL_FRect face = {button.bounds.x + sink, button.bounds.y + sink,
                                button.bounds.width, button.bounds.height};
        SDL_SetRenderDrawColor(renderer, fill_r, fill_g, fill_b, 252);
        SDL_RenderFillRect(renderer, &face);
        SDL_SetRenderDrawColor(renderer, border_r, border_g, border_b, enabled ? 245 : 185);
        SDL_RenderRect(renderer, &face);

        // Top/left highlight and lower/right shade make normal/hover controls
        // read as raised. Pressing reverses the lighting and visibly sinks them.
        if (!pressed) {
            SDL_SetRenderDrawColor(renderer,
                                   destructive ? 255 : 184,
                                   destructive ? 179 : 232,
                                   destructive ? 155 : 241,
                                   enabled ? 112 : 40);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + 2.0F,
                           face.x + face.w - 2.0F, face.y + 2.0F);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + 2.0F,
                           face.x + 2.0F, face.y + face.h - 2.0F);
            SDL_SetRenderDrawColor(renderer, 2, 13, 19, 205);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + face.h - 2.0F,
                           face.x + face.w - 2.0F, face.y + face.h - 2.0F);
            SDL_RenderLine(renderer, face.x + face.w - 2.0F, face.y + 2.0F,
                           face.x + face.w - 2.0F, face.y + face.h - 2.0F);
        } else {
            SDL_SetRenderDrawColor(renderer, 1, 10, 15, 210);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + 2.0F,
                           face.x + face.w - 2.0F, face.y + 2.0F);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + 2.0F,
                           face.x + 2.0F, face.y + face.h - 2.0F);
            SDL_SetRenderDrawColor(renderer, 146, 218, 232, 84);
            SDL_RenderLine(renderer, face.x + 2.0F, face.y + face.h - 2.0F,
                           face.x + face.w - 2.0F, face.y + face.h - 2.0F);
        }

        if (hovered) {
            const SDL_FRect hover_inner = {face.x + 3.0F, face.y + 3.0F,
                                           std::max(0.0F, face.w - 6.0F),
                                           std::max(0.0F, face.h - 6.0F)};
            SDL_SetRenderDrawColor(renderer,
                                   destructive ? 255 : 139,
                                   destructive ? 171 : 230,
                                   destructive ? 145 : 241,
                                   90);
            SDL_RenderRect(renderer, &hover_inner);
        }

        const char* icon_name = ch_button_icon_name(button);
        const float content_offset = sink;
        if (icon_name != nullptr && button.bounds.width >= 72.0F && button.bounds.height >= 26.0F) {
            const float plate_size = std::clamp(button.bounds.height - 10.0F, 20.0F, 28.0F);
            const SDL_FRect icon_plate = {button.bounds.x + 7.0F + content_offset,
                                          button.bounds.y + (button.bounds.height - plate_size) * 0.5F + content_offset,
                                          plate_size, plate_size};
            SDL_SetRenderDrawColor(renderer, 4, 18, 27, enabled ? 186 : 112);
            SDL_RenderFillRect(renderer, &icon_plate);
            SDL_SetRenderDrawColor(renderer, border_r, border_g, border_b, enabled ? 205 : 120);
            SDL_RenderRect(renderer, &icon_plate);
            const float icon_padding = std::max(3.0F, plate_size * 0.16F);
            ch_draw_icon(icon_name,
                         {icon_plate.x + icon_padding, icon_plate.y + icon_padding,
                          plate_size - icon_padding * 2.0F, plate_size - icon_padding * 2.0F},
                         enabled ? (pressed ? 218 : 255) : 105);

            const float text_x = icon_plate.x + icon_plate.w + 9.0F;
            const float text_y = button.bounds.y + std::max(8.0F, (button.bounds.height - 8.0F) * 0.5F) + content_offset;
            draw_text_fit(renderer, text_x, text_y,
                          std::max(1.0F, button.bounds.x + button.bounds.width - text_x - 8.0F),
                          button.label, text_r, text_g, text_b);
        } else {
            draw_text_centered_fit(renderer,
                                   {button.bounds.x + content_offset, button.bounds.y + content_offset,
                                    button.bounds.width, button.bounds.height},
                                   button.bounds.y + std::max(8.0F, (button.bounds.height - 8.0F) * 0.5F) + content_offset,
                                   button.label, text_r, text_g, text_b);
        }
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
