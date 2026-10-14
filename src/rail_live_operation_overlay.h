#pragma once

#include "rail_live_operation_controller.h"
#include "rail_block_dispatcher.h"
#include "rail_two_service.h"
#include "rail_turntable_sprite_runtime.h"
#include "rail_articulated_consist.h"
#include "src/ch_core/projection.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <vector>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>

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
    // Buying a vehicle is an authoritative change: refresh the existing
    // operation controller before rendering the newly purchased unit.
    hash = mix(hash, state.fleet.locomotive_owned ? 1U : 0U);
    hash = mix(hash, state.fleet.coach_count);
    hash = mix(hash, state.secondary_fleet.locomotive_owned ? 1U : 0U);
    hash = mix(hash, state.secondary_fleet.coach_count);
    hash = mix(hash,state.turntables.size());
    for(const RailPersistentTurntable& table:state.turntables){
        hash=mix(hash,table.piece_group);
        hash=mix(hash,static_cast<std::uint64_t>(table.build_cost));
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
    [[nodiscard]] const ch::rail_two_service::AuxiliaryService& secondary_controller() const noexcept {
        return secondary_controller_;
    }
    // Click a placed rail station by its world-space projected center. This
    // selects existing rail-station entities; it never edits track construction.
    [[nodiscard]] std::optional<RailPlacementPieceId> select_station_at(
        const float mouse_x, const float mouse_y,
        const ch::CameraState& camera, const float viewport_width,
        const float viewport_height) {
        const auto persistent = rail_persistence::capture_runtime_state();
        if (!persistent) return std::nullopt;
        std::optional<RailPlacementPieceId> nearest;
        float best = 1.0F;
        const float zoom = std::max(0.35F, camera.zoom);
        for (const RailPersistentStation& station : persistent->stations) {
            const RailPlacementEdge* edge = detail::edge_for_group(*persistent, station.piece_group);
            if (edge == nullptr) continue;
            const RailWorldPoint3 middle = RailMeshBuilder::sample_cubic(edge->segment, 0.5F);
            const float dx = edge->segment.end.x - edge->segment.start.x;
            const float dy = edge->segment.end.y - edge->segment.start.y;
            const float length = std::hypot(dx, dy);
            const float nx = length > 0.0001F ? -dy / length : 0.0F;
            const float ny = length > 0.0001F ? dx / length : 1.0F;
            const ch::ScreenPoint center = ch::world_to_screen_point(
                middle.x + 2.4F * nx, middle.y + 2.4F * ny, middle.z,
                camera, viewport_width, viewport_height);
            // Limit picking to the visible 5x3 station silhouette, rather
            // than the entire large transparent PNG canvas.
            const float radius_x = 52.0F * zoom;
            const float radius_y = 32.0F * zoom;
            const float u = (mouse_x - center.x) / radius_x;
            const float v = (mouse_y - (center.y - 16.0F * zoom)) / radius_y;
            const float score = u * u + v * v;
            if (score < best) {
                best = score;
                nearest = station.piece_group;
            }
        }
        selected_station_ = nearest;
        return nearest;
    }

    void clear_station_selection() noexcept { selected_station_.reset(); }
    [[nodiscard]] std::optional<RailPlacementPieceId> selected_station() const noexcept {
        return selected_station_;
    }


    // Single authoritative production frame. Never copy the whole rail graph
    // once per segment: hundreds of tracks would otherwise become quadratic.
    void render_production_frame(SDL_Renderer* renderer, const ch::CameraState& camera,
                                 const float viewport_width, const float viewport_height,
                                 const bool hotkeys_allowed) {
        if (renderer == nullptr || viewport_width <= 0.0F || viewport_height <= 0.0F) return;
        const std::optional<RailPersistentState> captured = rail_persistence::capture_runtime_state();
        if (!captured) return;
        const std::uint64_t signature = detail::state_signature(*captured);
        if (!state_ready_ || signature != state_signature_) {
            if (!controller_.sync_from_persistent_state(*captured) ||
                !secondary_controller_.sync_from_state(*captured)) return;
            const auto refreshed = rail_persistence::capture_runtime_state();
            state_signature_ = refreshed ? detail::state_signature(*refreshed) : signature;
            state_ready_ = true;
            dispatcher_.clear();
            first_authority_ = false;
            second_authority_ = false;
            last_tick_ns_ = SDL_GetTicksNS();
        }
        if (hotkeys_allowed) handle_hotkeys(*captured, camera, viewport_width, viewport_height);
        else update_key_latches();
        update_clock();
        render_stations(renderer, *captured, camera, viewport_width, viewport_height);
        render_turntables(renderer,*captured,camera,viewport_width,viewport_height);
    }

    void render_after_segment(SDL_Renderer* renderer,
                              const RailSplineSegment& rendered_segment,
                              const ch::CameraState& camera,
                              const float viewport_width,
                              const float viewport_height) {
        if (production_sprites_) return; // Main runtime owns once-per-frame update.
        if (renderer == nullptr || viewport_width <= 0.0F || viewport_height <= 0.0F) return;
        const std::optional<RailPersistentState> captured = rail_persistence::capture_runtime_state();
        if (!captured) return;
        const RailPlacementEdge* last = detail::last_live_edge(*captured);
        if (last == nullptr || !detail::same_segment(rendered_segment, last->segment)) return;

        const std::uint64_t signature = detail::state_signature(*captured);
        if (!state_ready_ || signature != state_signature_) {
            if (!controller_.sync_from_persistent_state(*captured) ||
                !secondary_controller_.sync_from_state(*captured)) return;
            const auto refreshed = rail_persistence::capture_runtime_state();
            state_signature_ = refreshed ? detail::state_signature(*refreshed) : signature;
            state_ready_ = true;
            dispatcher_.clear();
            first_authority_ = false;
            second_authority_ = false;
            last_tick_ns_ = SDL_GetTicksNS();
        }

        handle_hotkeys(*captured, camera, viewport_width, viewport_height);
        update_clock();
        render_stations(renderer, *captured, camera, viewport_width, viewport_height);
        render_turntables(renderer,*captured,camera,viewport_width,viewport_height);
        if (!production_sprites_) render_train(renderer, camera, viewport_width, viewport_height);
    }

private:
    void update_key_latches() noexcept {
        int key_count = 0;
        const bool* keys = SDL_GetKeyboardState(&key_count);
        station_key_was_down_ = keys != nullptr && SDL_SCANCODE_7 < key_count && keys[SDL_SCANCODE_7];
        restart_key_was_down_ = keys != nullptr && SDL_SCANCODE_8 < key_count && keys[SDL_SCANCODE_8];
    }

    void handle_hotkeys(const RailPersistentState& state,
                        const ch::CameraState& camera,
                        const float viewport_width,
                        const float viewport_height) {
        int key_count = 0;
        const bool* keys = SDL_GetKeyboardState(&key_count);
        const bool station_down = keys != nullptr && SDL_SCANCODE_7 < key_count && keys[SDL_SCANCODE_7];
        const bool restart_down = keys != nullptr && SDL_SCANCODE_8 < key_count && keys[SDL_SCANCODE_8];

        if (station_down && !station_key_was_down_) {
            float mouse_x = 0.0F;
            float mouse_y = 0.0F;
            (void)SDL_GetMouseState(&mouse_x, &mouse_y);
            const ch::WorldPoint world = ch::screen_to_world_point(
                mouse_x, mouse_y, camera, viewport_width, viewport_height);
            const std::optional<RailPlacementPieceId> group =
                detail::nearest_piece(state, world.x, world.y);
            if (group && controller_.toggle_station(*group, 3.0)) {
                if (const std::optional<RailPersistentState> refreshed =
                        rail_persistence::capture_runtime_state()) {
                    // The hotkey updates the primary controller directly. The
                    // secondary service must see the new A2/B2 stations now,
                    // before caching the new signature or it will stay stale.
                    (void)secondary_controller_.sync_from_state(*refreshed);
                    dispatcher_.clear();
                    first_authority_ = false;
                    second_authority_ = false;
                    state_signature_ = detail::state_signature(*refreshed);
                }
            }
            last_tick_ns_ = SDL_GetTicksNS();
        }
        if (restart_down && !restart_key_was_down_) {
            (void)controller_.restart();
            dispatcher_.clear();
            first_authority_ = false;
            second_authority_ = false;
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
        // Scan the occupied blocks ahead, reserve a safe free prefix, and
        // set the real TrainRuntime braking target before moving either train.
        const auto* first_route = controller_.operational_route();
        const auto primary_pose = controller_.train_pose();
        const bool shunting = controller_.shunting_locomotive() ||
                              controller_.return_service_active();
        if (first_route && primary_pose) {
            if (shunting) {
                first_authority_ = dispatcher_.acquire_entire_route(1U, *first_route);
                (void)controller_.set_dispatch_signal_stop(std::nullopt);
            } else {
                const auto authority = dispatcher_.authorize(
                    1U, *first_route, primary_pose->distance_m,
                    std::max(0.0, primary_pose->speed_mps), controller_.coach_count());
                first_authority_ = authority.granted &&
                    controller_.set_dispatch_signal_stop(authority.signal_stop_m);
            }
        } else {
            dispatcher_.release(1U);
            first_authority_ = false;
            (void)controller_.set_dispatch_signal_stop(std::nullopt);
        }
        const auto* second_route = secondary_controller_.route();
        const auto secondary_pose = secondary_controller_.train_pose();
        if (second_route && secondary_pose) {
            const auto authority = dispatcher_.authorize(
                2U, *second_route, secondary_pose->distance_m,
                std::max(0.0, secondary_pose->speed_mps),
                secondary_controller_.coach_count());
            second_authority_ = authority.granted &&
                secondary_controller_.set_dispatch_signal_stop(authority.signal_stop_m);
        } else {
            dispatcher_.release(2U);
            second_authority_ = false;
            (void)secondary_controller_.set_dispatch_signal_stop(std::nullopt);
        }
        if (simulation_running_ && elapsed > 0.0) {
            if (first_authority_) controller_.update(elapsed);
            if (second_authority_) secondary_controller_.update(elapsed);
            // Only release rail pieces AFTER the last coach cleared them;
            // the previous lease protected every step of the elapsed frame.
            if (first_authority_ && !shunting) {
                const auto moved = controller_.train_pose();
                if (moved) {
                    const auto renewed = dispatcher_.authorize(
                        1U, *first_route, moved->distance_m,
                        std::max(0.0, moved->speed_mps), controller_.coach_count());
                    first_authority_ = renewed.granted &&
                        controller_.set_dispatch_signal_stop(renewed.signal_stop_m);
                }
            }
            if (second_authority_) {
                const auto moved = secondary_controller_.train_pose();
                if (moved) {
                    const auto renewed = dispatcher_.authorize(
                        2U, *second_route, moved->distance_m,
                        std::max(0.0, moved->speed_mps), secondary_controller_.coach_count());
                    second_authority_ = renewed.granted &&
                        secondary_controller_.set_dispatch_signal_stop(renewed.signal_stop_m);
                }
            }
        }
    }

    void render_stations(SDL_Renderer* renderer,
                         const RailPersistentState& state,
                         const ch::CameraState& camera,
                         const float viewport_width,
                         const float viewport_height) const {
        const float zoom = std::max(0.35F, camera.zoom);
        const auto& registered = controller_.stations();
        for (std::size_t station_index = 0U; station_index < registered.size(); ++station_index) {
            const rail_operation::StationDefinition& station = registered[station_index];
            const RailPlacementEdge* edge = detail::edge_for_group(state, station.piece_group);
            if (edge == nullptr) continue;
            const RailWorldPoint3 middle = RailMeshBuilder::sample_cubic(edge->segment, 0.5F);
            const ch::ScreenPoint screen = ch::world_to_screen_point(
                middle.x, middle.y, middle.z + 0.05F,
                camera, viewport_width, viewport_height);
            // The existing 7-key station marker uses a rail piece group.
            // Render the authored four-direction building instead of a flat
            // rectangle, while retaining a fallback when the PNG is absent.
            // Separate 5x3 placement/collision rules are still required before
            // this prototype becomes a purchasable construction.
            const float dx = edge->segment.end.x - edge->segment.start.x;
            const float dy = edge->segment.end.y - edge->segment.start.y;
            const bool horizontal = std::abs(dx) >= std::abs(dy);
            const char* direction = horizontal
                ? (dx >= 0.0F ? "south" : "north")
                : (dy >= 0.0F ? "east" : "west");
            const std::string property_key = std::string("ch.station.terminal_b.") + direction;
            const std::string path = std::string(
                "assets/buildings/rail_terminal_station_b_5x3_01/rail_terminal_station_b_")
                + direction + ".png";
            const SDL_PropertiesID props = SDL_GetRendererProperties(renderer);
            SDL_Texture* station_texture = props ? static_cast<SDL_Texture*>(
                SDL_GetPointerProperty(props, property_key.c_str(), nullptr)) : nullptr;
            if (!station_texture && props) {
                SDL_Surface* surface = SDL_LoadPNG(path.c_str());
                if (surface) {
                    SDL_Texture* created = SDL_CreateTextureFromSurface(renderer, surface);
                    SDL_DestroySurface(surface);
                    if (created) {
                        SDL_SetTextureBlendMode(created, SDL_BLENDMODE_BLEND);
                        if (SDL_SetPointerPropertyWithCleanup(
                                props, property_key.c_str(), created,
                                [](void*, void* value) {
                                    SDL_DestroyTexture(static_cast<SDL_Texture*>(value));
                                }, nullptr)) {
                            station_texture = created;
                        }
                    }
                }
            }
            if (selected_station_ == station.piece_group) {
                const ch::ScreenPoint marker = ch::world_to_screen_point(
                    middle.x, middle.y, middle.z + 0.16F,
                    camera, viewport_width, viewport_height);
                // Slightly wider than the station platform and drawn before
                // its sprite; the ends remain visible as selection handles.
                SDL_FRect outline{
                    marker.x - 34.0F * zoom, marker.y - 16.0F * zoom,
                    68.0F * zoom, 32.0F * zoom
                };
                SDL_SetRenderDrawColor(renderer, 255, 206, 70, 255);
                (void)SDL_RenderRect(renderer, &outline);
            }
            bool station_sprite_drawn = false;
            if (station_texture) {
                // The Blender model origin is centered on the 5x3 footprint.
                // Its railway lane sits at local Y=-2.4 world units; translate
                // the sprite origin from the selected rail center to the building.
                const float length = std::hypot(dx, dy);
                const float nx = length > 0.0001F ? -dy / length : 0.0F;
                const float ny = length > 0.0001F ? dx / length : 1.0F;
                const ch::ScreenPoint asset_center = ch::world_to_screen_point(
                    middle.x + 2.4F * nx, middle.y + 2.4F * ny, middle.z,
                    camera, viewport_width, viewport_height);
                const float image_scale = zoom * 0.50F;
                SDL_FRect dst{
                    asset_center.x - 512.0F * image_scale,
                    asset_center.y - 556.0F * image_scale,
                    1024.0F * image_scale,
                    1024.0F * image_scale
                };
                station_sprite_drawn = SDL_RenderTexture(renderer, station_texture, nullptr, &dst);
            }
            if (!station_sprite_drawn) {
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
            // The order of key-7 designations is the service identity. Make
            // it visible in the world rather than forcing players to guess.
            static constexpr const char* station_names[] = {"A1", "B1", "A2", "B2"};
            if (station_index < 4U) {
                const float label_y = screen.y - 28.0F * zoom;
                SDL_SetRenderDrawColor(renderer, 26, 37, 51, 225);
                const SDL_FRect tag{screen.x - 13.0F, label_y - 3.0F, 29.0F, 17.0F};
                (void)SDL_RenderFillRect(renderer, &tag);
                SDL_SetRenderDrawColor(renderer, 242, 210, 113, 255);
                (void)SDL_RenderRect(renderer, &tag);
                (void)SDL_RenderDebugText(renderer, screen.x - 8.0F, label_y,
                                          station_names[station_index]);
                // Automatic block signal indication: red (occupied/fault),
                // amber (approach), green (clear). Shared-route dispatch stays
                // locked out; these lamps do not authorize unsafe movements.
                const bool second_line = station_index >= 2U;
                const auto* route = second_line ? secondary_controller_.route()
                                               : controller_.operational_route();
                const auto pose = second_line ? secondary_controller_.train_pose()
                                              : controller_.train_pose();
                const auto& fleet = second_line ? state.secondary_fleet : state.fleet;
                ch::rail_signals::Aspect aspect = ch::rail_signals::Aspect::stop;
                if (route != nullptr) {
                    const auto it = std::find_if(route->stations.begin(), route->stations.end(),
                        [&](const rail_operation::StationStop& stop) {
                            return stop.piece_group == station.piece_group;
                        });
                    if (it != route->stations.end()) {
                        const bool transfer = !second_line &&
                            (controller_.shunting_locomotive() || controller_.return_service_active());
                        const bool signal_restricted = second_line
                            ? secondary_controller_.waiting_at_dispatch_signal()
                            : controller_.waiting_at_dispatch_signal();
                        aspect = ch::rail_signals::station_aspect(
                            (second_line ? second_authority_ : first_authority_) &&
                            !signal_restricted,
                            it->distance_m,
                            pose ? std::optional<double>{pose->distance_m} : std::nullopt,
                            fleet.coach_count, transfer);
                    }
                }
                const float x = screen.x + 23.0F * zoom;
                const float y = screen.y - 23.0F * zoom;
                SDL_SetRenderDrawColor(renderer, 65, 69, 72, 255);
                (void)SDL_RenderLine(renderer, x, y + 7.0F * zoom,
                                     x, y - 7.0F * zoom);
                SDL_FRect housing{x - 3.5F * zoom, y - 11.0F * zoom,
                                  7.0F * zoom, 8.0F * zoom};
                (void)SDL_RenderFillRect(renderer, &housing);
                if (aspect == ch::rail_signals::Aspect::stop)
                    SDL_SetRenderDrawColor(renderer, 231, 62, 55, 255);
                else if (aspect == ch::rail_signals::Aspect::approach)
                    SDL_SetRenderDrawColor(renderer, 243, 184, 45, 255);
                else SDL_SetRenderDrawColor(renderer, 67, 203, 104, 255);
                SDL_FRect lamp{x - 2.0F * zoom, y - 9.5F * zoom,
                               4.0F * zoom, 4.0F * zoom};
                (void)SDL_RenderFillRect(renderer, &lamp);
            }
        }
    }

    void render_turntables(SDL_Renderer* renderer,
                           const RailPersistentState& state,
                           const ch::CameraState& camera,
                           const float width, const float height) const {
        constexpr float pi=3.14159265358979323846F;
        constexpr float radius=3.6F;
        for(const auto& table:state.turntables) {
            const RailPlacementEdge* edge=detail::edge_for_group(state,table.piece_group);
            if(!edge || !edge->active || edge->kind!=RailPlacementEdgeKind::straight)continue;
            // CH Blender approved layer pair takes priority only when the
            // asset set is complete and this authored heading has a real view.
            // Never pivot all devices when only one locomotive turns.
            const double angle=controller_.rotating_turntable_group()==table.piece_group
                ? controller_.turntable_rotation_radians():0.0;
            if(ch::rail_turntable_visual::render(
                    renderer,*edge,angle,camera,width,height))continue;
            const auto c=RailMeshBuilder::sample_cubic(edge->segment,0.5F);
            const ch::ScreenPoint middle=ch::world_to_screen_point(
                c.x,c.y,c.z+0.02F,camera,width,height);
            std::vector<SDL_Vertex> vertices;
            vertices.reserve(34);
            vertices.push_back({{middle.x,middle.y},{0.18F,0.19F,0.18F,1.0F},{0,0}});
            std::vector<int> indices;
            indices.reserve(96);
            std::vector<SDL_FPoint> border;
            border.reserve(34);
            for(int n=0;n<=32;++n){
                const float angle=(2.0F*pi*n)/32.0F;
                const auto p=ch::world_to_screen_point(
                    c.x+radius*std::cos(angle),c.y+radius*std::sin(angle),
                    c.z+0.04F,camera,width,height);
                border.push_back({p.x,p.y});
                vertices.push_back({{p.x,p.y},{0.28F,0.30F,0.28F,1.0F},{0,0}});
                if(n<32){
                    indices.push_back(0);indices.push_back(n+1);indices.push_back(n+2);
                }
            }
            (void)SDL_RenderGeometry(renderer,nullptr,vertices.data(),
                                     static_cast<int>(vertices.size()),indices.data(),
                                     static_cast<int>(indices.size()));
            SDL_SetRenderDrawColor(renderer,186,155,97,255);
            (void)SDL_RenderLines(renderer,border.data(),static_cast<int>(border.size()));
            // The rotating steel bridge shares the locomotive's true
            // rotational phase. The PNG vehicle pivots at this very center.
            float turn=0.0F;
            if(controller_.rotating_turntable_group()==table.piece_group){
                turn=static_cast<float>(controller_.turntable_rotation_radians());
            }
            const float dx=edge->segment.end.x-edge->segment.start.x;
            const float dy=edge->segment.end.y-edge->segment.start.y;
            const float base=std::atan2(dy,dx)+turn;
            const float ax=std::cos(base),ay=std::sin(base);
            const float nx=-ay,ny=ax;
            for(int side=-1;side<=1;side+=2){
                const float offset=side*0.37F;
                const auto p1=ch::world_to_screen_point(
                    c.x-3.0F*ax+offset*nx,c.y-3.0F*ay+offset*ny,c.z+0.07F,
                    camera,width,height);
                const auto p2=ch::world_to_screen_point(
                    c.x+3.0F*ax+offset*nx,c.y+3.0F*ay+offset*ny,c.z+0.07F,
                    camera,width,height);
                SDL_SetRenderDrawColor(renderer,212,216,210,255);
                (void)SDL_RenderLine(renderer,p1.x,p1.y,p2.x,p2.y);
            }
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
    ch::rail_two_service::AuxiliaryService secondary_controller_{};
    ch::rail_dispatch::BlockDispatcher dispatcher_{};
    bool first_authority_ = false;
    bool second_authority_ = false;
    std::uint64_t state_signature_ = 0U;
    std::uint64_t last_tick_ns_ = 0U;
    bool state_ready_ = false;
    bool station_key_was_down_ = false;
    bool restart_key_was_down_ = false;
    std::optional<RailPlacementPieceId> selected_station_{};
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
