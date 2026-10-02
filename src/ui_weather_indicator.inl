// Included inside GameplayUi::render(). Keep this widget presentation-only:
// WeatherSystem remains authoritative for the current simulation state.
extern int ch_weather_ui_state_code();

if (renderer != nullptr && model_.overlay == UiOverlay::none && !panels_.empty()) {
    const int weather_widget_state = ch_weather_ui_state_code();
    const UiRect& weather_widget_hud = panels_.front();
    const float weather_widget_controls_width = 154.0F;
    const float weather_widget_available_width =
        std::max(360.0F, weather_widget_hud.width - weather_widget_controls_width - 24.0F);
    const float weather_widget_block_width = weather_widget_available_width / 4.0F;
    const float weather_widget_block_x = weather_widget_hud.x + 16.0F;

    const SDL_FRect weather_widget_rect{
        weather_widget_block_x + weather_widget_block_width * 3.0F - 4.0F,
        weather_widget_hud.y + 4.0F,
        std::max(86.0F, weather_widget_block_width - 8.0F),
        std::max(48.0F, weather_widget_hud.height - 8.0F),
    };

    // Cover the retired fourth HUD slot first, then apply the same runtime
    // nine-slice chrome used by the rest of the City Horizon interface.
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 16, 39, 56, 252);
    SDL_RenderFillRect(renderer, &weather_widget_rect);
    if (const UiThumbnail* weather_widget_skin =
            thumbnail_for(renderer, runtime_asset_path("assets/ui/chrome/panel_window_9slice_v2.png"));
        weather_widget_skin != nullptr && weather_widget_skin->texture != nullptr) {
        (void)ch::ui::render_nine_slice(
            renderer,
            weather_widget_skin->texture,
            weather_widget_skin->width,
            weather_widget_skin->height,
            weather_widget_rect,
            {32.0F, 32.0F, 32.0F, 32.0F});
    }

    const float weather_widget_icon_x = weather_widget_rect.x + 11.0F;
    const float weather_widget_icon_y = weather_widget_rect.y + 16.0F;

    // 0 sunny, 1 overcast, 2 raining, 3 thunderstorm.
    if (weather_widget_state == 0) {
        SDL_SetRenderDrawColor(renderer, 245, 194, 66, SDL_ALPHA_OPAQUE);
        const SDL_FRect sun_core{weather_widget_icon_x + 7.0F, weather_widget_icon_y + 5.0F, 11.0F, 11.0F};
        SDL_RenderFillRect(renderer, &sun_core);
        SDL_RenderLine(renderer, weather_widget_icon_x + 12.5F, weather_widget_icon_y,
                       weather_widget_icon_x + 12.5F, weather_widget_icon_y + 4.0F);
        SDL_RenderLine(renderer, weather_widget_icon_x + 12.5F, weather_widget_icon_y + 17.0F,
                       weather_widget_icon_x + 12.5F, weather_widget_icon_y + 21.0F);
        SDL_RenderLine(renderer, weather_widget_icon_x + 1.0F, weather_widget_icon_y + 10.5F,
                       weather_widget_icon_x + 5.0F, weather_widget_icon_y + 10.5F);
        SDL_RenderLine(renderer, weather_widget_icon_x + 20.0F, weather_widget_icon_y + 10.5F,
                       weather_widget_icon_x + 24.0F, weather_widget_icon_y + 10.5F);
    } else {
        SDL_SetRenderDrawColor(renderer, 196, 209, 217, SDL_ALPHA_OPAQUE);
        const SDL_FRect cloud_a{weather_widget_icon_x + 2.0F, weather_widget_icon_y + 8.0F, 22.0F, 9.0F};
        const SDL_FRect cloud_b{weather_widget_icon_x + 7.0F, weather_widget_icon_y + 4.0F, 9.0F, 8.0F};
        const SDL_FRect cloud_c{weather_widget_icon_x + 14.0F, weather_widget_icon_y + 6.0F, 8.0F, 7.0F};
        SDL_RenderFillRect(renderer, &cloud_a);
        SDL_RenderFillRect(renderer, &cloud_b);
        SDL_RenderFillRect(renderer, &cloud_c);
        if (weather_widget_state >= 2) {
            SDL_SetRenderDrawColor(renderer, 104, 180, 220, SDL_ALPHA_OPAQUE);
            SDL_RenderLine(renderer, weather_widget_icon_x + 6.0F, weather_widget_icon_y + 20.0F,
                           weather_widget_icon_x + 4.0F, weather_widget_icon_y + 25.0F);
            SDL_RenderLine(renderer, weather_widget_icon_x + 13.0F, weather_widget_icon_y + 20.0F,
                           weather_widget_icon_x + 11.0F, weather_widget_icon_y + 25.0F);
            SDL_RenderLine(renderer, weather_widget_icon_x + 20.0F, weather_widget_icon_y + 20.0F,
                           weather_widget_icon_x + 18.0F, weather_widget_icon_y + 25.0F);
        }
        if (weather_widget_state == 3) {
            SDL_SetRenderDrawColor(renderer, 245, 202, 75, SDL_ALPHA_OPAQUE);
            SDL_RenderLine(renderer, weather_widget_icon_x + 16.0F, weather_widget_icon_y + 17.0F,
                           weather_widget_icon_x + 12.0F, weather_widget_icon_y + 23.0F);
            SDL_RenderLine(renderer, weather_widget_icon_x + 12.0F, weather_widget_icon_y + 23.0F,
                           weather_widget_icon_x + 17.0F, weather_widget_icon_y + 23.0F);
            SDL_RenderLine(renderer, weather_widget_icon_x + 17.0F, weather_widget_icon_y + 23.0F,
                           weather_widget_icon_x + 13.0F, weather_widget_icon_y + 29.0F);
        }
    }

    const char* weather_widget_label = "SOL";
    switch (weather_widget_state) {
        case 1: weather_widget_label = "NUBLADO"; break;
        case 2: weather_widget_label = "CHUVA"; break;
        case 3: weather_widget_label = "TEMPESTADE"; break;
        default: break;
    }
    draw_text(renderer, weather_widget_rect.x + 42.0F, weather_widget_rect.y + 13.0F,
              "CLIMA", 151, 229, 240);
    draw_text_fit(renderer, weather_widget_rect.x + 42.0F, weather_widget_rect.y + 31.0F,
                  weather_widget_rect.w - 48.0F, weather_widget_label,
                  238, 246, 249);
}
