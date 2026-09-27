#pragma once

#include "ui_manager.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <string>

// Runtime-only top-bar camera controls. The world/camera logic stays in the
// existing gameplay loop; this wrapper contributes only two screen-space
// buttons that emit the already-supported rotate_left/rotate_right actions.
//
// Final art is authored offline by CH Blender and consumed as ordinary RGBA
// PNGs. Until those final PNGs are promoted, a lightweight fallback remains
// available so the control path can be compiled and exercised independently.
class ChGameplayUi : public GameplayUi {
public:
    ~ChGameplayUi() {
        destroy_camera_art();
    }

    void update_layout(const int viewport_width, const int viewport_height,
                       const GameplayUiModel& model) {
        GameplayUi::update_layout(viewport_width, viewport_height, model);
        viewport_width_ = std::max(viewport_width, 1);
        viewport_height_ = std::max(viewport_height, 1);
        camera_controls_enabled_ = model.overlay == UiOverlay::none &&
                                   model.placement_preview_path.empty();
        update_camera_control_bounds();
    }

    void handle_mouse_motion(const float mouse_x, const float mouse_y) {
        mouse_x_ = mouse_x;
        mouse_y_ = mouse_y;
        GameplayUi::handle_mouse_motion(mouse_x, mouse_y);
    }

    [[nodiscard]] bool handle_mouse_wheel(const float mouse_x, const float mouse_y,
                                          const float wheel_y) {
        if (camera_controls_visible_ &&
            (camera_left_bounds_.contains(mouse_x, mouse_y) ||
             camera_right_bounds_.contains(mouse_x, mouse_y))) {
            return true;
        }
        return GameplayUi::handle_mouse_wheel(mouse_x, mouse_y, wheel_y);
    }

    [[nodiscard]] UiInputResult handle_mouse_button_down(const float mouse_x,
                                                         const float mouse_y,
                                                         const bool primary_button) {
        mouse_x_ = mouse_x;
        mouse_y_ = mouse_y;
        if (camera_controls_visible_) {
            const bool left = camera_left_bounds_.contains(mouse_x, mouse_y);
            const bool right = camera_right_bounds_.contains(mouse_x, mouse_y);
            if (left || right) {
                camera_left_pressed_ = primary_button && left;
                camera_right_pressed_ = primary_button && right;
                UiInputResult result;
                result.consumed = true;
                if (primary_button) {
                    result.action = UiActionEvent{
                        left ? UiAction::rotate_left : UiAction::rotate_right,
                        left ? "camera_left" : "camera_right",
                    };
                }
                return result;
            }
        }
        return GameplayUi::handle_mouse_button_down(mouse_x, mouse_y, primary_button);
    }

    void handle_mouse_button_up(const float mouse_x, const float mouse_y) {
        mouse_x_ = mouse_x;
        mouse_y_ = mouse_y;
        camera_left_pressed_ = false;
        camera_right_pressed_ = false;
        GameplayUi::handle_mouse_button_up(mouse_x, mouse_y);
    }

    [[nodiscard]] bool consumes_point(const float mouse_x, const float mouse_y) const {
        if (camera_controls_visible_ &&
            (camera_left_bounds_.contains(mouse_x, mouse_y) ||
             camera_right_bounds_.contains(mouse_x, mouse_y))) {
            return true;
        }
        return GameplayUi::consumes_point(mouse_x, mouse_y);
    }

    void render(SDL_Renderer* renderer) const {
        GameplayUi::render(renderer);
        if (renderer == nullptr || !camera_controls_visible_) return;
        render_camera_control(renderer, camera_left_bounds_, true,
                              camera_left_pressed_, left_fx_, left_art_);
        render_camera_control(renderer, camera_right_bounds_, false,
                              camera_right_pressed_, right_fx_, right_art_);
    }

    void release_renderer_resources() {
        destroy_camera_art();
        GameplayUi::release_renderer_resources();
    }

private:
    struct CameraButtonFx {
        float hover = 0.0F;
        float press = 0.0F;
        Uint64 last_tick = 0;
    };

    struct CameraButtonArt {
        SDL_Texture* texture = nullptr;
        float width = 0.0F;
        float height = 0.0F;
        bool attempted = false;
        bool final_asset = false;
    };

    [[nodiscard]] static std::filesystem::path runtime_root() {
        const char* base_path = SDL_GetBasePath();
        return base_path == nullptr ? std::filesystem::path(".")
                                    : std::filesystem::path(base_path);
    }

    static bool load_texture(SDL_Renderer* renderer, const std::filesystem::path& path,
                             CameraButtonArt& art, const bool final_asset) {
        SDL_Surface* surface = SDL_LoadPNG(path.string().c_str());
        if (surface == nullptr) return false;
        SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
        const float width = static_cast<float>(surface->w);
        const float height = static_cast<float>(surface->h);
        SDL_DestroySurface(surface);
        if (texture == nullptr) return false;
        SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);
        art.texture = texture;
        art.width = width;
        art.height = height;
        art.final_asset = final_asset;
        return true;
    }

    static void ensure_camera_art(SDL_Renderer* renderer, const bool left,
                                  CameraButtonArt& art) {
        if (art.attempted || renderer == nullptr) return;
        art.attempted = true;
        const std::filesystem::path root = runtime_root();
        const std::filesystem::path final_path = root / "assets/ui/topbar" /
            (left ? "camera_rotate_left_3d.png" : "camera_rotate_right_3d.png");
        if (std::filesystem::is_regular_file(final_path) &&
            load_texture(renderer, final_path, art, true)) {
            return;
        }
        const std::filesystem::path fallback_path = root / "assets/ui/icons/rotate.png";
        if (std::filesystem::is_regular_file(fallback_path)) {
            (void)load_texture(renderer, fallback_path, art, false);
        }
    }

    static void destroy_art(CameraButtonArt& art) {
        if (art.texture != nullptr) SDL_DestroyTexture(art.texture);
        art = {};
    }

    void destroy_camera_art() {
        destroy_art(left_art_);
        destroy_art(right_art_);
    }

    void update_camera_control_bounds() {
        // Match the established top HUD cluster. The camera pair lives directly
        // to the left of PAUSE and gracefully disappears at very narrow window
        // widths where it would collide with simulation controls.
        const float width = static_cast<float>(viewport_width_);
        const float settings_x = std::max(12.0F + 270.0F, width - 50.0F);
        const float administration_x = std::max(12.0F + 120.0F, settings_x - 112.0F);
        const float pause_x = std::max(12.0F, administration_x - 124.0F);
        camera_controls_visible_ = camera_controls_enabled_ && pause_x >= 96.0F;
        if (!camera_controls_visible_) {
            camera_left_bounds_ = {};
            camera_right_bounds_ = {};
            return;
        }
        camera_left_bounds_ = {pause_x - 76.0F, 27.0F, 34.0F, 32.0F};
        camera_right_bounds_ = {pause_x - 38.0F, 27.0F, 34.0F, 32.0F};
    }

    void render_camera_control(SDL_Renderer* renderer, const UiRect& bounds,
                               const bool left, const bool pressed,
                               CameraButtonFx& fx, CameraButtonArt& art) const {
        ensure_camera_art(renderer, left, art);

        const Uint64 now = SDL_GetTicks();
        if (fx.last_tick == 0) fx.last_tick = now;
        const float dt = std::clamp(static_cast<float>(now - fx.last_tick) / 1000.0F,
                                    0.0F, 0.05F);
        fx.last_tick = now;
        const bool hovered = bounds.contains(mouse_x_, mouse_y_);
        const float response = 1.0F - std::exp(-16.0F * dt);
        fx.hover += ((hovered ? 1.0F : 0.0F) - fx.hover) * response;
        fx.press += ((pressed ? 1.0F : 0.0F) - fx.press) * response;

        const float pulse = std::sin(static_cast<float>(now) * 0.008F +
                                     (left ? 0.0F : 1.7F)) * 0.55F * fx.hover *
                            (1.0F - fx.press);
        const float lift = -2.2F * fx.hover + 1.7F * fx.press + pulse;
        const float scale = 1.0F + 0.14F * fx.hover - 0.07F * fx.press;
        const float animated_w = bounds.width * scale;
        const float animated_h = bounds.height * scale;
        const SDL_FRect destination = {
            bounds.x - (animated_w - bounds.width) * 0.5F,
            bounds.y - (animated_h - bounds.height) * 0.5F + lift,
            animated_w,
            animated_h,
        };

        if (fx.hover > 0.01F) {
            const float grow = 2.0F + 2.0F * fx.hover;
            const SDL_FRect glow = {
                destination.x - grow,
                destination.y - grow,
                destination.w + grow * 2.0F,
                destination.h + grow * 2.0F,
            };
            SDL_SetRenderDrawColor(renderer, left ? 76 : 255, left ? 220 : 176,
                                   left ? 255 : 76,
                                   static_cast<Uint8>(std::clamp(90.0F * fx.hover *
                                                                 (1.0F - fx.press),
                                                                 0.0F, 90.0F)));
            SDL_RenderRect(renderer, &glow);
        }

        if (art.texture != nullptr && art.width > 0.0F && art.height > 0.0F) {
            const float fit = std::min(destination.w / art.width,
                                       destination.h / art.height);
            const SDL_FRect image = {
                destination.x + (destination.w - art.width * fit) * 0.5F,
                destination.y + (destination.h - art.height * fit) * 0.5F,
                art.width * fit,
                art.height * fit,
            };
            SDL_SetTextureAlphaMod(art.texture,
                static_cast<Uint8>(std::clamp(255.0F - 30.0F * fx.press,
                                             215.0F, 255.0F)));
            SDL_RenderTexture(renderer, art.texture, nullptr, &image);
            SDL_SetTextureAlphaMod(art.texture, 255);
            if (art.final_asset) return;
        } else {
            SDL_SetRenderDrawColor(renderer, left ? 34 : 224, left ? 133 : 92,
                                   left ? 220 : 52, SDL_ALPHA_OPAQUE);
            SDL_RenderFillRect(renderer, &destination);
            SDL_SetRenderDrawColor(renderer, 204, 244, 255, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &destination);
        }

        // Directional fallback remains unmistakable if the CH Blender final has
        // not yet been promoted. It disappears automatically once final art is
        // available, leaving the 3D curved-arrow button untouched.
        const float cx = destination.x + destination.w * 0.5F;
        const float cy = destination.y + destination.h * 0.5F;
        const float s = std::min(destination.w, destination.h) * 0.22F;
        SDL_SetRenderDrawColor(renderer, 248, 250, 236, SDL_ALPHA_OPAQUE);
        if (left) {
            SDL_RenderLine(renderer, cx + s, cy - s, cx - s, cy);
            SDL_RenderLine(renderer, cx - s, cy, cx + s, cy + s);
        } else {
            SDL_RenderLine(renderer, cx - s, cy - s, cx + s, cy);
            SDL_RenderLine(renderer, cx + s, cy, cx - s, cy + s);
        }
    }

    int viewport_width_ = 1;
    int viewport_height_ = 1;
    bool camera_controls_enabled_ = false;
    bool camera_controls_visible_ = false;
    bool camera_left_pressed_ = false;
    bool camera_right_pressed_ = false;
    float mouse_x_ = -1000.0F;
    float mouse_y_ = -1000.0F;
    UiRect camera_left_bounds_;
    UiRect camera_right_bounds_;
    mutable CameraButtonFx left_fx_;
    mutable CameraButtonFx right_fx_;
    mutable CameraButtonArt left_art_;
    mutable CameraButtonArt right_art_;
};
