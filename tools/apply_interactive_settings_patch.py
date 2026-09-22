from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Pattern changed: {label}")
    return text.replace(old, new, 1)


header_path = Path("src/ui_manager.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    struct UiThumbnail {
        SDL_Texture* texture = nullptr;
        float width = 0.0F;
        float height = 0.0F;
    };

    void add_button''',
    '''    struct UiThumbnail {
        SDL_Texture* texture = nullptr;
        float width = 0.0F;
        float height = 0.0F;
    };

    enum class SettingsDragTarget : std::uint8_t {
        none,
        master,
        effects,
    };

    void add_button''',
    "settings drag enum",
)
header = replace_once(
    header,
    '''    void add_panel(UiRect bounds);
    [[nodiscard]] const UiThumbnail* thumbnail_for(SDL_Renderer* renderer, const std::string& path) const;''',
    '''    void add_panel(UiRect bounds);
    void update_settings_draft_from_pointer(SettingsDragTarget target, float mouse_x);
    [[nodiscard]] const UiThumbnail* thumbnail_for(SDL_Renderer* renderer, const std::string& path) const;''',
    "settings helper declaration",
)
header = replace_once(
    header,
    '''    std::optional<UiRect> build_panel_bounds_;
    std::optional<UiRect> overlay_bounds_;
    int viewport_width_ = 1;''',
    '''    std::optional<UiRect> build_panel_bounds_;
    std::optional<UiRect> overlay_bounds_;
    std::optional<UiRect> settings_master_slider_bounds_;
    std::optional<UiRect> settings_effects_slider_bounds_;
    SettingsDragTarget settings_drag_target_ = SettingsDragTarget::none;
    int settings_draft_master_percent_ = 100;
    int settings_draft_effects_percent_ = 100;
    int viewport_width_ = 1;''',
    "settings draft members",
)
header_path.write_text(header, encoding="utf-8")


cpp_path = Path("src/ui_manager.cpp")
cpp = cpp_path.read_text(encoding="utf-8")
cpp = replace_once(
    cpp,
    '''void GameplayUi::update_layout(int viewport_width, int viewport_height, const GameplayUiModel& model) {
    model_ = model;
    viewport_width_ = std::max(viewport_width, 1);
    viewport_height_ = std::max(viewport_height, 1);
    buttons_.clear(); panels_.clear(); build_panel_bounds_.reset(); overlay_bounds_.reset();''',
    '''void GameplayUi::update_layout(int viewport_width, int viewport_height, const GameplayUiModel& model) {
    const UiOverlay previous_overlay = model_.overlay;
    const bool entering_settings = model.overlay == UiOverlay::settings && previous_overlay != UiOverlay::settings;
    model_ = model;
    viewport_width_ = std::max(viewport_width, 1);
    viewport_height_ = std::max(viewport_height, 1);
    buttons_.clear(); panels_.clear(); build_panel_bounds_.reset(); overlay_bounds_.reset();
    settings_master_slider_bounds_.reset();
    settings_effects_slider_bounds_.reset();
    if (entering_settings) {
        settings_draft_master_percent_ = std::clamp(model.master_volume_percent, 0, 100);
        settings_draft_effects_percent_ = std::clamp(model.effects_volume_percent, 0, 100);
        settings_drag_target_ = SettingsDragTarget::none;
    } else if (model.overlay != UiOverlay::settings) {
        settings_drag_target_ = SettingsDragTarget::none;
    }''',
    "update layout draft initialization",
)
cpp = replace_once(
    cpp,
    '''        overlay_bounds_ = panel;
        const float horizontal_padding = std::clamp(panel.width * 0.06F, 22.0F, 36.0F);
        const float button_gap = 12.0F;''',
    '''        overlay_bounds_ = panel;
        const float meter_x = panel.x + std::clamp(panel.width * 0.10F, 28.0F, 54.0F);
        const float meter_width = panel.width - (meter_x - panel.x) * 2.0F;
        settings_master_slider_bounds_ = UiRect{meter_x, panel.y + 157.0F, meter_width, 20.0F};
        settings_effects_slider_bounds_ = UiRect{meter_x, panel.y + 235.0F, meter_width, 20.0F};
        const float horizontal_padding = std::clamp(panel.width * 0.06F, 22.0F, 36.0F);
        const float button_gap = 12.0F;''',
    "settings slider geometry",
)
cpp = replace_once(
    cpp,
    '''void GameplayUi::handle_mouse_motion(float mouse_x, float mouse_y) {
    mouse_x_ = mouse_x; mouse_y_ = mouse_y;
    for (UiButton& button : buttons_) button.state = state_for(button, mouse_x_, mouse_y_, primary_pressed_);
}''',
    '''void GameplayUi::handle_mouse_motion(float mouse_x, float mouse_y) {
    mouse_x_ = mouse_x; mouse_y_ = mouse_y;
    if (primary_pressed_ && settings_drag_target_ != SettingsDragTarget::none) {
        update_settings_draft_from_pointer(settings_drag_target_, mouse_x_);
    }
    for (UiButton& button : buttons_) button.state = state_for(button, mouse_x_, mouse_y_, primary_pressed_);
}''',
    "settings drag motion",
)
cpp = replace_once(
    cpp,
    '''    if (!result.consumed || !primary_button) return result;
    primary_pressed_ = true;
    for (auto it = buttons_.rbegin(); it != buttons_.rend(); ++it) {
        UiButton& button = *it;
        button.state = state_for(button, mouse_x_, mouse_y_, true);
        if (!button.bounds.contains(mouse_x, mouse_y)) continue;
        if (button.enabled) result.action = UiActionEvent{button.action, button.payload};
        break;
    }
    return result;
}

void GameplayUi::handle_mouse_button_up(float mouse_x, float mouse_y) { primary_pressed_ = false; handle_mouse_motion(mouse_x, mouse_y); }''',
    '''    if (!result.consumed || !primary_button) return result;
    primary_pressed_ = true;
    if (model_.overlay == UiOverlay::settings) {
        if (settings_master_slider_bounds_ && settings_master_slider_bounds_->contains(mouse_x, mouse_y)) {
            settings_drag_target_ = SettingsDragTarget::master;
            update_settings_draft_from_pointer(settings_drag_target_, mouse_x);
            return result;
        }
        if (settings_effects_slider_bounds_ && settings_effects_slider_bounds_->contains(mouse_x, mouse_y)) {
            settings_drag_target_ = SettingsDragTarget::effects;
            update_settings_draft_from_pointer(settings_drag_target_, mouse_x);
            return result;
        }
    }
    for (auto it = buttons_.rbegin(); it != buttons_.rend(); ++it) {
        UiButton& button = *it;
        button.state = state_for(button, mouse_x_, mouse_y_, true);
        if (!button.bounds.contains(mouse_x, mouse_y)) continue;
        if (button.enabled) {
            if (button.action == UiAction::settings_reset) {
                settings_draft_master_percent_ = 100;
                settings_draft_effects_percent_ = 100;
            }
            std::string payload = button.payload;
            if (button.action == UiAction::settings_apply) {
                payload = std::to_string(settings_draft_master_percent_) + ":" +
                          std::to_string(settings_draft_effects_percent_);
            }
            result.action = UiActionEvent{button.action, std::move(payload)};
        }
        break;
    }
    return result;
}

void GameplayUi::handle_mouse_button_up(float mouse_x, float mouse_y) {
    primary_pressed_ = false;
    settings_drag_target_ = SettingsDragTarget::none;
    handle_mouse_motion(mouse_x, mouse_y);
}''',
    "settings click and apply payload",
)
cpp = replace_once(
    cpp,
    '''            const float meter_x = panel.x + std::clamp(panel.width * 0.10F, 28.0F, 54.0F);
            const float meter_width = panel.width - (meter_x - panel.x) * 2.0F;
            const auto draw_meter = [&](const float y, const char* label, int percent) {
                percent = std::clamp(percent, 0, 100);
                draw_text(renderer, meter_x, y, label, 219, 232, 238);
                draw_text_fit(renderer, meter_x + meter_width - 48.0F, y, 48.0F, std::to_string(percent) + "%", 238, 246, 249);
                const SDL_FRect track = {meter_x, y + 25.0F, meter_width, 16.0F};
                SDL_SetRenderDrawColor(renderer, 25, 48, 61, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &track);
                SDL_SetRenderDrawColor(renderer, 64, 91, 104, SDL_ALPHA_OPAQUE);
                SDL_RenderRect(renderer, &track);
                const float fill_width = (meter_width - 4.0F) * static_cast<float>(percent) / 100.0F;
                const SDL_FRect fill = {meter_x + 2.0F, y + 27.0F, fill_width, 12.0F};
                SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &fill);
            };
            draw_meter(panel.y + 132.0F, "VOLUME GERAL", model_.master_volume_percent);
            draw_meter(panel.y + 210.0F, "EFEITOS", model_.effects_volume_percent);
            draw_text_centered(renderer, panel, panel.y + 286.0F, "CONTROLES INTERATIVOS ENTRAM NA PROXIMA ETAPA", 118, 151, 166);''',
    '''            const auto draw_meter = [&](const UiRect& slider, const char* label, int percent) {
                percent = std::clamp(percent, 0, 100);
                const float label_y = slider.y - 25.0F;
                draw_text(renderer, slider.x, label_y, label, 219, 232, 238);
                draw_text_fit(renderer, slider.x + slider.width - 48.0F, label_y, 48.0F,
                              std::to_string(percent) + "%", 238, 246, 249);
                const SDL_FRect track = {slider.x, slider.y + 2.0F, slider.width, 16.0F};
                SDL_SetRenderDrawColor(renderer, 25, 48, 61, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &track);
                SDL_SetRenderDrawColor(renderer, 64, 91, 104, SDL_ALPHA_OPAQUE);
                SDL_RenderRect(renderer, &track);
                const float fill_width = (slider.width - 4.0F) * static_cast<float>(percent) / 100.0F;
                const SDL_FRect fill = {slider.x + 2.0F, slider.y + 4.0F, fill_width, 12.0F};
                SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &fill);
                const float knob_x = slider.x + 2.0F + fill_width;
                const SDL_FRect knob = {std::clamp(knob_x - 4.0F, slider.x, slider.x + slider.width - 8.0F),
                                        slider.y - 1.0F, 8.0F, 22.0F};
                SDL_SetRenderDrawColor(renderer, 218, 242, 251, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &knob);
            };
            if (settings_master_slider_bounds_) {
                draw_meter(*settings_master_slider_bounds_, "VOLUME GERAL", settings_draft_master_percent_);
            }
            if (settings_effects_slider_bounds_) {
                draw_meter(*settings_effects_slider_bounds_, "EFEITOS", settings_draft_effects_percent_);
            }
            draw_text_centered(renderer, panel, panel.y + 286.0F, "CLIQUE OU ARRASTE PARA AJUSTAR", 158, 186, 199);
            draw_text_centered(renderer, panel, panel.y + 306.0F, "AS ALTERACOES SO SAO SALVAS AO APLICAR", 118, 151, 166);''',
    "settings interactive meter render",
)
cpp = replace_once(
    cpp,
    '''void GameplayUi::add_panel(UiRect bounds) { panels_.push_back(bounds); }

const GameplayUi::UiThumbnail* GameplayUi::thumbnail_for''',
    '''void GameplayUi::add_panel(UiRect bounds) { panels_.push_back(bounds); }

void GameplayUi::update_settings_draft_from_pointer(SettingsDragTarget target, float mouse_x) {
    const std::optional<UiRect>* bounds = nullptr;
    if (target == SettingsDragTarget::master) bounds = &settings_master_slider_bounds_;
    else if (target == SettingsDragTarget::effects) bounds = &settings_effects_slider_bounds_;
    if (bounds == nullptr || !*bounds || (*bounds)->width <= 0.0F) return;

    const float normalized = std::clamp((mouse_x - (*bounds)->x) / (*bounds)->width, 0.0F, 1.0F);
    const int percent = std::clamp(static_cast<int>(normalized * 100.0F + 0.5F), 0, 100);
    if (target == SettingsDragTarget::master) settings_draft_master_percent_ = percent;
    else if (target == SettingsDragTarget::effects) settings_draft_effects_percent_ = percent;
}

const GameplayUi::UiThumbnail* GameplayUi::thumbnail_for''',
    "settings draft pointer helper",
)
cpp_path.write_text(cpp, encoding="utf-8")


main_path = Path("src/main.cpp")
main = main_path.read_text(encoding="utf-8")
main = replace_once(
    main,
    '''            case UiAction::settings_reset:
                // The controls are visually present and their data contract is
                // ready.  Sliders are intentionally not wired until their
                // input behavior is implemented as a cohesive settings pass.
                status = "SETTINGS DEFAULTS READY TO APPLY";
                (void)audio.play(SoundEvent::ui_click);
                break;
            case UiAction::settings_apply:
                active_overlay = UiOverlay::none;
                status = "SETTINGS APPLIED";
                (void)audio.play(SoundEvent::ui_confirm);
                break;''',
    '''            case UiAction::settings_reset:
                status = "SETTINGS DEFAULTS READY TO APPLY";
                (void)audio.play(SoundEvent::ui_click);
                break;
            case UiAction::settings_apply: {
                const std::size_t separator = action.payload.find(':');
                if (separator == std::string::npos) {
                    status = "INVALID SETTINGS PAYLOAD";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const int master_percent = std::clamp(std::stoi(action.payload.substr(0, separator)), 0, 100);
                const int effects_percent = std::clamp(std::stoi(action.payload.substr(separator + 1)), 0, 100);
                AudioVolumeSettings volumes = audio.volume_settings();
                volumes.master = static_cast<float>(master_percent) / 100.0F;
                volumes.effects = static_cast<float>(effects_percent) / 100.0F;
                audio.set_volume_settings(volumes);
                active_overlay = UiOverlay::none;
                status = "SETTINGS APPLIED";
                (void)audio.play(SoundEvent::ui_confirm);
                break;
            }''',
    "apply audio settings payload",
)
main_path.write_text(main, encoding="utf-8")
