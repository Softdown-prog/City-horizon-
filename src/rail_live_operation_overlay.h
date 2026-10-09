#pragma once

#include "rail_live_operation_controller.h"
#include "rail_articulated_consist.h"
#include "src/ch_core/projection.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>

inline constexpr const char* kChRailLiveOperationOverlayContract = "CH_RAIL_LIVE_OPERATION_OVERLAY_V2";

namespace ch::rail_live_operation {

namespace detail {

[[nodiscard]] inline bool nearly_equal(const float a, const float b) noexcept {
    return std::abs(a - b) <= 1.0e-5F;
}

[[nodiscard]] inline bool same_segment(const RailSplineSegment& a,
                                       const RailSplineSegment& b) noexcept {
    return nearly_equal(a.start.x, b.start.x) && nearly_equal(a.start.y, b.start.y) &&
           nearly_equal(a.start.z, b.start.z) && nearly_equal(a.end.x, b.end.x) &&
           nearly_equal(a.end.y, b.end.y) && nearly_equal(a.end.z, b.end.z) &&
           nearly_equal(a.control_a.x, b.control_a.x) && nearly_equal(a.control_a.y, b.control_a.y) &&
           nearly_equal(a.control_b.x, b.control_b.x) && nearly_equal(a.control_b.y, b.control_b.y);
}

[[nodiscard]] inline std::uint64_t mix(std::uint64_t hash, const std::uint64_t value) noexcept {
    hash ^= value;
    hash *= 1099511628211ULL;
    return hash;
}

[[nodiscard]] inline std::uint64_t state_signature(const RailPersistentState& state) noexcept {
    std::uint64_t hash = 14695981039346656037ULL;
    hash = mix(hash, state.nodes.size());
    hash = mix(hash, state.edges.size());
    for (const RailPlacementEdge& edge : state.edges) {
        hash = mix(hash, edge.id);
        hash = mix(hash, edge.piece_group);
        hash = mix(hash, edge.active ? 1U : 0U);
        const auto quantize = [](const float value) -> std::uint64_t {
            return static_cast<std::uint64_t>(static_cast<std::int64_t>(std::llround(value * 10000.0F)));
        };
        hash = mix(hash, quantize(edge.segment.start.x));
        hash = mix(hash, quantize(edge.segment.start.y));
        hash = mix(hash, quantize(edge.segment.end.x));
        hash = mix(hash, quantize(edge.segment.end.y));
    }
    hash = mix(hash, state.stations.size());
    for (const RailPersistentStation& station : state.stations) {
        hash = mix(hash, station.piece_group);
        hash = mix(hash, static_cast<std::uint64_t>(
            static_cast<std::int64_t>(std::llround(station.dwell_seconds * 1000.0))));
    }
    return hash;
}

[[nodiscard]] inline std::optional<RailPlacementPieceId> nearest_piece(
    const RailPersistentState& state,
    const float world_x,
    const float world_y,
    const float maximum_distance = 0.38F) {
    std::optional<RailPlacementPieceId> best;
    float best_squared = maximum_distance * maximum_distance;
    for (const RailPlacementEdge& edge : state.edges) {
        if (!edge.active || edge.piece_group == kInvalidRailPlacementPieceId) continue;
        const int samples = std::clamp(edge.segment.subdivisions, 8, 64);
        RailWorldPoint3 previous = RailMeshBuilder::sample_cubic(edge.segment, 0.0F);
        for (int index = 1; index <= samples; ++index) {
            const float t = static_cast<float>(index) / static_cast<float>(samples);
            const RailWorldPoint3 current = RailMeshBuilder::sample_cubic(edge.segment, t);
            const float vx = current.x - previous.x;
            const float vy = current.y - previous.y;
            const float wx = world_x - previous.x;
            const float wy = world_y - previous.y;
            const float length_squared = vx * vx + vy * vy;
            const float projection = length_squared > 1.0e-9F
                ? std::clamp((wx * vx + wy * vy) / length_squared, 0.0F, 1.0F)
                : 0.0F;
            const float dx = world_x - (previous.x + vx * projection);
            const float dy = world_y - (previous.y + vy * projection);
            const float distance_squared = dx * dx + dy * dy;
            if (distance_squared <= best_squared) {
                best_squared = distance_squared;
                best = edge.piece_group;
            }
            previous = current;
        }
    }
    return best;
}

[[nodiscard]] inline const RailPlacementEdge* edge_for_group(
    const RailPersistentState& state,
    const RailPlacementPieceId group) noexcept {
    for (const RailPlacementEdge& edge : state.edges) {
        if (edge.active && edge.piece_group == group) return &edge;
    }
    return nullptr;
}

[[nodiscard]] inline const RailPlacementEdge* last_live_edge(const RailPersistentState& state) noexcept {
    for (auto it = state.edges.rbegin(); it != state.edges.rend(); ++it) {
        if (it->active) return &*it;
    }
    return nullptr;
}

} // namespace detail

class LiveOperationOverlay final {
public:
    // Production sprites are drawn by the game's shared texture cache, never
    // by the low-level procedural track renderer. Keep debug fallback opt-in.
    void use_production_sprites(const bool enabled) noexcept { production_sprites_ = enabled; }
    void set_simulation_running(const bool running) noexcept { simulation_running_ = running; }
    [[nodiscard]] const LiveOperationController& controller() const noexcept { return controller_; }
    void render_after_segment(SDL_Renderer* renderer,
                              const RailSplineSegment& rendered_segment,
                              const ch::CameraState& camera,
                              const float viewport_width,
                              const float viewport_height) {
        if (renderer == nullptr || viewport_width <= 0.0F || viewport_height <= 0.0F) return;
        const std::optional<RailPersistentState> captured = rail_persistence::capture_runtime_state();
        if (!captured) return;
        const RailPlacementEdge* last = detail::last_live_edge(*captured);
        if (last == nullptr || !detail::same_segment(rendered_segment, last->segment)) return;

        const std::uint64_t signature = detail::state_signature(*captured);
        if (!state_ready_ || signature != state_signature_) {
            if (!controller_.sync_from_persistent_state(*captured)) return;
            state_signature_ = detail::state_signature(*rail_persistence::capture_runtime_state());
            state_ready_ = true;
            last_tick_ns_ = SDL_GetTicksNS();
        }

        handle_hotkeys(*captured, camera, viewport_width, viewport_height);
        update_clock();
        render_stations(renderer, *captured, camera, viewport_width, viewport_height);
        if (!production_sprites_) render_train(renderer, camera, viewport_width, viewport_height);
    }

private:
    void handle_hotkeys(const RailPersistentState& state,
                        const ch::CameraState& camera,
                        const float viewport_width,
                        const float viewport_height) {
        int key_count = 0;
        const bool* keys = SDL_GetKeyboardState(&key_count);
        const bool station_down = keys != nullptr && SDL_SCANCODE_7 < key_count && keys[SDL_SCANCODE_7];
        const bool restart_down = keys != nullptr && SDL_SCANCODE_R < key_count && keys[SDL_SCANCODE_R];

        if (station_down && !station_key_was_down_) {
            float mouse_x = 0.0F;
            float mouse_y = 0.0F;
            (void)SDL_GetMouseState(&mouse_x, &mouse_y);
            const ch::WorldPoint world = ch::screen_to_world_point(
                mouse_x, mouse_y, camera, viewport_width, viewport_height);
            const std::optional<RailPlacementPieceId> group =
                detail::nearest_piece(state, world.x, world.y);
            if (group) (void)controller_.toggle_station(*group, 3.0);
            if (const std::optional<RailPersistentState> refreshed = rail_persistence::capture_runtime_state()) {
                state_signature_ = detail::state_signature(*refreshed);
            }
            last_tick_ns_ = SDL_GetTicksNS();
        }
        if (restart_down && !restart_key_was_down_) {
            (void)controller_.restart();
            last_tick_ns_ = SDL_GetTicksNS();
        }
        station_key_was_down_ = station_down;
        restart_key_was_down_ = restart_down;
    }

    void update_clock() {
        const std::uint64_t now = SDL_GetTicksNS();
        if (last_tick_ns_ == 0U) {
            last_tick_ns_ = now;
            return;
        }
        const double elapsed = std::clamp(
            static_cast<double>(now - last_tick_ns_) / 1000000000.0,
            0.0,
            0.1);
        last_tick_ns_ = now;
        if (simulation_running_) controller_.update(elapsed);
    }

    void render_stations(SDL_Renderer* renderer,
                         const RailPersistentState& state,
                         const ch::CameraState& camera,
                         const float viewport_width,
                         const float viewport_height) const {
        const float zoom = std::max(0.35F, camera.zoom);
        for (const rail_operation::StationDefinition& station : controller_.stations()) {
            const RailPlacementEdge* edge = detail::edge_for_group(state, station.piece_group);
            if (edge == nullptr) continue;
            const RailWorldPoint3 middle = RailMeshBuilder::sample_cubic(edge->segment, 0.5F);
            const ch::ScreenPoint screen = ch::world_to_screen_point(
                middle.x, middle.y, middle.z + 0.05F,
                camera, viewport_width, viewport_height);
            SDL_FRect platform{
                screen.x - 14.0F * zoom,
                screen.y - 4.0F * zoom,
                28.0F * zoom,
                8.0F * zoom,
            };
            SDL_SetRenderDrawColor(renderer, 174, 146, 78, 235);
            (void)SDL_RenderFillRect(renderer, &platform);
            SDL_SetRenderDrawColor(renderer, 235, 222, 175, 255);
            (void)SDL_RenderRect(renderer, &platform);
        }
    }

    void render_train(SDL_Renderer* renderer,
                      const ch::CameraState& camera,
                      const float viewport_width,
                      const float viewport_height) const {
        const std::optional<rail_operation::TrainPose> pose = controller_.train_pose();
        if (!pose) return;
        const ch::ScreenPoint center = ch::world_to_screen_point(
            static_cast<float>(pose->x), static_cast<float>(pose->y), static_cast<float>(pose->z + 0.13),
            camera, viewport_width, viewport_height);
        const ch::ScreenPoint nose = ch::world_to_screen_point(
            static_cast<float>(pose->x + pose->tangent_x * 0.45),
            static_cast<float>(pose->y + pose->tangent_y * 0.45),
            static_cast<float>(pose->z + pose->tangent_z * 0.45 + 0.13),
            camera, viewport_width, viewport_height);

        const float zoom = std::max(0.35F, camera.zoom);
        SDL_FRect body{
            center.x - 7.0F * zoom,
            center.y - 5.0F * zoom,
            14.0F * zoom,
            10.0F * zoom,
        };
        SDL_SetRenderDrawColor(renderer, pose->dwelling ? 208 : 150, 55, 45, 255);
        (void)SDL_RenderFillRect(renderer, &body);
        SDL_SetRenderDrawColor(renderer, 246, 226, 170, 255);
        (void)SDL_RenderRect(renderer, &body);
        SDL_SetRenderDrawColor(renderer, 248, 238, 203, 255);
        (void)SDL_RenderLine(renderer, center.x, center.y, nose.x, nose.y);
    }

    LiveOperationController controller_{};
    std::uint64_t state_signature_ = 0U;
    std::uint64_t last_tick_ns_ = 0U;
    bool state_ready_ = false;
    bool station_key_was_down_ = false;
    bool restart_key_was_down_ = false;
    bool production_sprites_ = false;
    bool simulation_running_ = true;
};

[[nodiscard]] inline LiveOperationOverlay& overlay() {
    static LiveOperationOverlay instance;
    return instance;
}

inline void render_after_segment(SDL_Renderer* renderer,
                                 const RailSplineSegment& segment,
                                 const ch::CameraState& camera,
                                 const float viewport_width,
                                 const float viewport_height) {
    overlay().render_after_segment(renderer, segment, camera, viewport_width, viewport_height);
}

} // namespace ch::rail_live_operation
