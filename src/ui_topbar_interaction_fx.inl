// Shared hover/press animation for the compact top HUD controls.
// Included inside GameplayUi::render after the legacy UI pass. The animation
// deliberately uses the existing UiButton hitboxes/states, so no input logic is
// duplicated. CH Blender final PNGs are preferred automatically when present;
// canonical legacy icons remain the fallback during art iteration.
if (renderer != nullptr && model_.overlay == UiOverlay::none) {
    struct ChTopbarIconFxState {
        float hover = 0.0F;
        float press = 0.0F;
        Uint64 last_tick = 0;
    };
    static std::unordered_map<int, ChTopbarIconFxState> ch_topbar_icon_fx;

    const Uint64 ch_now = SDL_GetTicks();
    const auto ch_action_icon = [](const UiAction action) -> const char* {
        switch (action) {
            case UiAction::toggle_pause: return "pause";
            case UiAction::open_administration: return "administration";
            case UiAction::open_settings: return "settings";
            default: return nullptr;
        }
    };
    const auto ch_final_icon_path = [](const UiAction action) -> std::filesystem::path {
        switch (action) {
            case UiAction::toggle_pause: return "assets/ui/topbar/pause_3d.png";
            case UiAction::open_administration: return "assets/ui/topbar/administration_3d.png";
            case UiAction::open_settings: return "assets/ui/topbar/settings_3d.png";
            default: return {};
        }
    };
    const auto ch_fallback_icon = [](const UiAction action) -> const char* {
        switch (action) {
            case UiAction::toggle_pause: return "pause";
            case UiAction::open_administration: return "buildings";
            case UiAction::open_settings: return "settings";
            default: return nullptr;
        }
    };

    for (const UiButton& button : buttons_) {
        const char* semantic_icon = ch_action_icon(button.action);
        if (semantic_icon == nullptr || !button.enabled) continue;

        ChTopbarIconFxState& fx = ch_topbar_icon_fx[static_cast<int>(button.action)];
        if (fx.last_tick == 0) fx.last_tick = ch_now;
        const float dt = std::clamp(static_cast<float>(ch_now - fx.last_tick) / 1000.0F, 0.0F, 0.05F);
        fx.last_tick = ch_now;

        const bool hovered = button.state == UiButtonState::hover || button.state == UiButtonState::pressed;
        const bool pressed = button.state == UiButtonState::pressed;
        const float response = 1.0F - std::exp(-dt * 15.0F);
        fx.hover += ((hovered ? 1.0F : 0.0F) - fx.hover) * response;
        fx.press += ((pressed ? 1.0F : 0.0F) - fx.press) * response;

        if (fx.hover < 0.002F && fx.press < 0.002F) continue;

        // A short ease-out lift plus a tiny living pulse makes the icon feel
        // responsive without turning the HUD into a constantly moving panel.
        const float pulse = std::sin(static_cast<float>(ch_now) * 0.008F +
                                     static_cast<float>(static_cast<int>(button.action))) *
                            0.65F * fx.hover * (1.0F - fx.press);
        const float lift = -2.4F * fx.hover + 1.8F * fx.press + pulse;
        const float scale_boost = 1.0F + 0.15F * fx.hover - 0.07F * fx.press;

        float icon_size = std::min(button.bounds.height - 8.0F, 28.0F);
        icon_size = std::max(icon_size, 18.0F);
        const bool compact = button.bounds.width <= 40.0F;
        const float icon_x = compact
            ? button.bounds.x + (button.bounds.width - icon_size) * 0.5F
            : button.bounds.x + 5.0F;
        const float icon_y = button.bounds.y + (button.bounds.height - icon_size) * 0.5F;
        const float animated_size = icon_size * scale_boost;
        const SDL_FRect icon_bounds = {
            icon_x - (animated_size - icon_size) * 0.5F,
            icon_y - (animated_size - icon_size) * 0.5F + lift,
            animated_size,
            animated_size,
        };

        // Two soft outlines read as a glow on hover. Pressing collapses the
        // glow while the icon sinks, giving immediate click feedback.
        const Uint8 glow_alpha = static_cast<Uint8>(std::clamp(92.0F * fx.hover * (1.0F - fx.press), 0.0F, 92.0F));
        if (glow_alpha > 0) {
            const float grow = 2.0F + 2.0F * fx.hover;
            const SDL_FRect glow_outer = {icon_bounds.x - grow, icon_bounds.y - grow,
                                          icon_bounds.w + grow * 2.0F, icon_bounds.h + grow * 2.0F};
            const SDL_FRect glow_inner = {icon_bounds.x - 1.0F, icon_bounds.y - 1.0F,
                                          icon_bounds.w + 2.0F, icon_bounds.h + 2.0F};
            SDL_SetRenderDrawColor(renderer, 83, 224, 246, glow_alpha / 2);
            SDL_RenderRect(renderer, &glow_outer);
            SDL_SetRenderDrawColor(renderer, 197, 247, 255, glow_alpha);
            SDL_RenderRect(renderer, &glow_inner);
        }

        const UiThumbnail* icon = nullptr;
        const std::filesystem::path final_path = ch_final_icon_path(button.action);
        if (!final_path.empty()) icon = thumbnail_for(renderer, runtime_asset_path(final_path));
        if (icon == nullptr) {
            const char* fallback = ch_fallback_icon(button.action);
            if (fallback != nullptr) icon = thumbnail_for(renderer, ui_icon_path(fallback));
        }
        if (icon == nullptr) continue;

        const float fit = std::min(icon_bounds.w / icon->width, icon_bounds.h / icon->height);
        const SDL_FRect destination = {
            icon_bounds.x + (icon_bounds.w - icon->width * fit) * 0.5F,
            icon_bounds.y + (icon_bounds.h - icon->height * fit) * 0.5F,
            icon->width * fit,
            icon->height * fit,
        };
        const Uint8 alpha = static_cast<Uint8>(std::clamp(255.0F - 28.0F * fx.press, 210.0F, 255.0F));
        SDL_SetTextureAlphaMod(icon->texture, alpha);
        SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        SDL_SetTextureAlphaMod(icon->texture, 255);
    }
}