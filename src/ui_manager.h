#pragma once

#include <SDL3/SDL.h>

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

// This is intentionally a small gameplay UI layer. It owns only screen-space
// interaction and presentation; city systems remain the source of all state.
struct UiRect {
    float x = 0.0F;
    float y = 0.0F;
    float width = 0.0F;
    float height = 0.0F;

    [[nodiscard]] bool contains(float point_x, float point_y) const;
};

enum class UiButtonState : std::uint8_t {
    normal,
    hover,
    pressed,
    disabled,
};

enum class UiTool : std::uint8_t {
    none,
    buildings,
    roads,
    sidewalks,
    land,
    remove,
    agriculture,
    decoration,
};

enum class UiAction : std::uint8_t {
    none,
    open_build_panel,
    select_building,
    activate_roads,
    activate_sidewalks,
    activate_land,
    activate_remove,
    open_agriculture_panel,
    select_farming_item,
    activate_decoration,
    rotate_left,
    rotate_right,
    toggle_pause,
    resume_game,
    open_administration,
    open_reports,
    open_settings,
    open_main_menu,
    start_new_city,
    continue_saved_city,
    open_save_load,
    save_game,
    load_game,
    back_to_pause,
    back_from_save_load,
    open_quit_confirm,
    cancel_quit,
    quit_game,
    close_modal,
    settings_reset,
    settings_cancel,
    settings_apply,
    decrease_service_price,
    increase_service_price,
    set_wall_color,
    set_roof_color,
    reset_building_colors,
    close_selection,
    upgrade_building,
};

// These are presentation states only.  Simulation, finance and audio remain
// owned by their existing systems and are supplied through GameplayUiModel.
enum class UiOverlay : std::uint8_t {
    none,
    pause,
    administration,
    reports,
    settings,
    main_menu,
    save_load,
    quit_confirm,
};

struct UiActionEvent {
    UiAction action = UiAction::none;
    std::string payload;
};

struct UiInputResult {
    bool consumed = false;
    std::optional<UiActionEvent> action;
};

struct UiBuildItem {
    std::string definition_id;
    std::string name;
    std::string category;
    std::string build_cost;
    bool enabled = true;
    // This is a small, fixed-canvas catalog asset, deliberately separate
    // from the world sprite. It keeps the build menu legible even when the
    // source art includes large transparent padding or ground decoration.
    std::string thumbnail_path;
    std::string footprint;
    std::string requirements;
};

struct UiSelectedBuilding {
    std::string name;
    std::string category;
    std::string cost;
    std::string monthly_tax;
    std::string monthly_maintenance;
    std::string monthly_net;
    std::string rotation;
    std::string road_access;
    std::string instance_id;
    // Empty for definitions that do not opt into population-driven demand.
    std::string commercial_demand;
    std::string thumbnail_path;
    std::string road_access_requirement;
    std::string energy_consumption;
    std::string energy_production;
    std::string residential_capacity;
    std::string property_tax_per_year;
    std::string commercial_current_revenue;
    std::string local_supply;
    std::string level_label;
    std::string upgrade_button_text;
    bool can_upgrade = false;
    bool is_max_level = false;
    std::string service_name;
    std::string service_price;
    std::string service_price_range;
    bool has_service_pricing = false;
    bool can_decrease_service_price = false;
    bool can_increase_service_price = false;
    bool has_color_customization = false;
    bool wall_color_customized = false;
    bool roof_color_customized = false;
    int wall_tint_r = 255;
    int wall_tint_g = 255;
    int wall_tint_b = 255;
    int roof_tint_r = 255;
    int roof_tint_g = 255;
    int roof_tint_b = 255;
};

struct UiLandDetails {
    std::string parcel_id;
    std::string price;
    std::string state;
};

struct GameplayUiModel {
    std::string funds;
    std::string date;
    std::string day_month;
    std::string year;
    std::string monthly_revenue;
    std::string monthly_expenses;
    std::string monthly_balance;
    std::string population;
    std::string residential_capacity;
    std::string power_demand;
    std::string power_capacity;
    std::string speed;
    std::string status;
    UiOverlay overlay = UiOverlay::none;
    // Live values used by the Administration screen.  Keeping them in the
    // view model makes the art panel safe to bind without giving UI code
    // authority over the city simulation.
    std::string administration_services;
    std::string administration_alerts;
    int master_volume_percent = 100;
    int effects_volume_percent = 100;
    bool save_available = false;
    bool startup_main_menu = false;
    UiTool active_tool = UiTool::none;
    bool build_panel_open = false;
    bool farming_panel_open = false;
    std::string selected_farming_id;
    std::vector<UiBuildItem> farming_items;
    std::string farming_infrastructure;
    std::string farming_stock;
    std::string farming_tile_status;
    bool placement_rotatable = false;
    std::string selected_building_id;
    bool paused = false;
    std::vector<UiBuildItem> build_items;
    std::vector<UiBuildItem> decor_items;
    std::optional<UiSelectedBuilding> selected_building;
    std::optional<UiLandDetails> land_details;
    bool debug_visible = false;
    std::vector<std::string> debug_lines;
};

struct UiButton {
    UiRect bounds;
    std::string label;
    UiAction action = UiAction::none;
    std::string payload;
    bool enabled = true;
    bool active = false;
    UiButtonState state = UiButtonState::normal;
    std::string detail;
    std::string requirements;
    std::string thumbnail_path;
    bool build_card = false;
    bool color_swatch = false;
    Uint8 swatch_r = 255;
    Uint8 swatch_g = 255;
    Uint8 swatch_b = 255;
};

class GameplayUi {
public:
    ~GameplayUi() = default;
    void update_layout(int viewport_width, int viewport_height, const GameplayUiModel& model);
    void handle_mouse_motion(float mouse_x, float mouse_y);
    [[nodiscard]] bool handle_mouse_wheel(float mouse_x, float mouse_y, float wheel_y);
    void release_renderer_resources();
    [[nodiscard]] UiInputResult handle_mouse_button_down(float mouse_x, float mouse_y, bool primary_button);
    void handle_mouse_button_up(float mouse_x, float mouse_y);
    [[nodiscard]] bool consumes_point(float mouse_x, float mouse_y) const;
    void render(SDL_Renderer* renderer) const;

    [[nodiscard]] const std::vector<UiButton>& buttons() const;
    [[nodiscard]] const std::vector<UiRect>& panels() const;

private:
    struct UiThumbnail {
        SDL_Texture* texture = nullptr;
        float width = 0.0F;
        float height = 0.0F;
    };

    enum class SettingsDragTarget : std::uint8_t {
        none,
        master,
        effects,
    };

    void add_button(UiRect bounds, std::string label, UiAction action, bool enabled = true,
                    bool active = false, std::string payload = {});
    void add_build_card(UiRect bounds, const UiBuildItem& item, bool active, UiAction action = UiAction::select_building);
    void add_panel(UiRect bounds);
    void update_settings_draft_from_pointer(SettingsDragTarget target, float mouse_x);
    [[nodiscard]] const UiThumbnail* thumbnail_for(SDL_Renderer* renderer, const std::string& path) const;
    void render_build_card(SDL_Renderer* renderer, const UiButton& button) const;
    [[nodiscard]] static UiButtonState state_for(const UiButton& button, float mouse_x, float mouse_y,
                                                  bool pressed);

    GameplayUiModel model_;
    std::vector<UiButton> buttons_;
    std::vector<UiRect> panels_;
    float mouse_x_ = -1.0F;
    float mouse_y_ = -1.0F;
    bool primary_pressed_ = false;
    std::optional<UiRect> build_panel_bounds_;
    std::optional<UiRect> overlay_bounds_;
    std::optional<UiRect> settings_master_slider_bounds_;
    std::optional<UiRect> settings_effects_slider_bounds_;
    SettingsDragTarget settings_drag_target_ = SettingsDragTarget::none;
    int settings_draft_master_percent_ = 100;
    int settings_draft_effects_percent_ = 100;
    int viewport_width_ = 1;
    int viewport_height_ = 1;
    float build_scroll_offset_ = 0.0F;
    float build_scroll_max_ = 0.0F;
    float build_panel_header_height_ = 42.0F;
    std::string build_category_filter_ = "TODOS";
    mutable std::unordered_map<std::string, UiThumbnail> thumbnails_;
};
