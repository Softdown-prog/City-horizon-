#pragma once

#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "rail_construction_economy.h"
#include "rail_mapforge_input_adapter.h"
#include "rail_placement_track_graph_adapter.h"
#include "road_system.h"
#include "sidewalk_system.h"
#include "src/ch_core/contracts.h"
#include "src/ch_core/terrain_heightfield.h"
#include "src/ch_render/procedural_rail_renderer.h"
#include "src/runtime_map_renderer.h"
#include "src/runtime_view_state.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
#include <unordered_set>
#include <vector>

inline constexpr const char* kChRailRuntimeBridgeContract = "CH_RAIL_RUNTIME_BRIDGE_V2";

namespace ch::rail_runtime {

struct InteractionContext {
    const LandManager* lands = nullptr;
    const BuildingManager* buildings = nullptr;
    const RoadManager* roads = nullptr;
    const SidewalkManager* sidewalks = nullptr;
    const FarmingSystem* farming = nullptr;
    const TerrainHeightField* terrain = nullptr;
};

class RuntimeState final {
public:
    RuntimeState()
        : graph_(profile_), controller_(graph_), drag_(controller_), input_(drag_) {
        refresh_status();
    }

    [[nodiscard]] bool tool_active() const noexcept { return tool_active_; }
    [[nodiscard]] const std::string& status_text() const noexcept { return status_; }
    [[nodiscard]] const RailPlacementGraph& graph() const noexcept { return graph_; }

    void reset() {
        cancel_gesture(false);
        graph_.clear();
        committed_actions_.clear();
        tool_active_ = false;
        selected_mode_ = RailPlacementMode::straight;
        new_root_heading_radians_ = 0.0F;
        committed_edge_count_ = 0U;
        preview_valid_ = false;
        preview_cost_ = 0;
        refresh_status();
    }

    [[nodiscard]] bool consume_event(const SDL_Event& event,
                                     const bool interaction_allowed,
                                     const InteractionContext& context) {
        if (!interaction_allowed) {
            if (tool_active_) {
                cancel_gesture(false);
                tool_active_ = false;
                status_ = "RAIL MODE CLOSED BY MODAL";
            }
            return false;
        }

        if (event.type == SDL_EVENT_KEY_DOWN && !event.key.repeat) {
            if (event.key.scancode == SDL_SCANCODE_T) {
                if (tool_active_) {
                    cancel_gesture(false);
                    tool_active_ = false;
                    status_ = "RAIL MODE CLOSED";
                } else {
                    tool_active_ = true;
                    refresh_status();
                }
                return true;
            }
            if (!tool_active_) return false;

            switch (event.key.scancode) {
                case SDL_SCANCODE_1: select_mode(RailPlacementMode::straight); return true;
                case SDL_SCANCODE_2: select_mode(RailPlacementMode::curve_left); return true;
                case SDL_SCANCODE_3: select_mode(RailPlacementMode::curve_right); return true;
                case SDL_SCANCODE_4: select_mode(RailPlacementMode::turnout_left); return true;
                case SDL_SCANCODE_5: select_mode(RailPlacementMode::turnout_right); return true;
                case SDL_SCANCODE_6: select_mode(RailPlacementMode::crossing); return true;
                case SDL_SCANCODE_Q:
                    if (!gesture_active_) rotate_new_root_heading(-1.0F);
                    return true;
                case SDL_SCANCODE_E:
                    if (!gesture_active_) rotate_new_root_heading(1.0F);
                    return true;
                case SDL_SCANCODE_DELETE:
                case SDL_SCANCODE_BACKSPACE:
                    if (gesture_active_) {
                        cancel_gesture(false);
                        status_ = "RAIL PREVIEW CANCELLED";
                    } else {
                        demolish_last_committed_action();
                    }
                    return true;
                case SDL_SCANCODE_ESCAPE:
                    if (gesture_active_) {
                        cancel_gesture(true);
                    } else {
                        tool_active_ = false;
                        status_ = "RAIL MODE CLOSED";
                    }
                    return true;
                default:
                    return false;
            }
        }

        if (!tool_active_) return false;

        const runtime_view::ViewSnapshot view = runtime_view::snapshot();
        if (!view.valid || view.viewport_width <= 0.0F || view.viewport_height <= 0.0F) {
            return false;
        }

        if (event.type == SDL_EVENT_MOUSE_BUTTON_DOWN && event.button.button == SDL_BUTTON_RIGHT) {
            if (gesture_active_) cancel_gesture(true);
            else {
                tool_active_ = false;
                status_ = "RAIL MODE CLOSED";
            }
            return true;
        }

        if (event.type == SDL_EVENT_MOUSE_BUTTON_DOWN && event.button.button == SDL_BUTTON_LEFT) {
            begin_gesture(event.button.x, event.button.y, view, context);
            return true;
        }

        if (event.type == SDL_EVENT_MOUSE_MOTION && gesture_active_) {
            update_gesture(event.motion.x, event.motion.y, view, context);
            return true;
        }

        if (event.type == SDL_EVENT_MOUSE_BUTTON_UP && event.button.button == SDL_BUTTON_LEFT && gesture_active_) {
            finish_gesture(event.button.x, event.button.y, view, context);
            return true;
        }

        return false;
    }

    void render(SDL_Renderer* renderer,
                const CameraState& camera,
                const float viewport_width,
                const float viewport_height) const {
        if (renderer == nullptr || graph_.edges().empty()) return;

        ProceduralRailRenderer::Palette committed_palette{};
        ProceduralRailRenderer::Palette valid_preview_palette{};
        valid_preview_palette.ballast = SDL_Color{124, 111, 74, 220};
        valid_preview_palette.sleepers = SDL_Color{125, 83, 42, 235};
        valid_preview_palette.rails = SDL_Color{219, 193, 95, 255};
        ProceduralRailRenderer::Palette invalid_preview_palette{};
        invalid_preview_palette.ballast = SDL_Color{129, 58, 54, 210};
        invalid_preview_palette.sleepers = SDL_Color{142, 58, 45, 235};
        invalid_preview_palette.rails = SDL_Color{232, 91, 76, 255};

        for (const RailPlacementEdge& edge : graph_.edges()) {
            const bool staged = gesture_active_ &&
                static_cast<std::size_t>(edge.id) >= gesture_checkpoint_.edge_count;
            const ProceduralRailRenderer::Palette& palette = staged
                ? (preview_valid_ ? valid_preview_palette : invalid_preview_palette)
                : committed_palette;
            (void)ProceduralRailRenderer::render_segment(
                renderer, edge.segment, profile_, camera,
                viewport_width, viewport_height, palette);
        }
    }

private:
    struct CommittedRailAction {
        RailPlacementCheckpoint checkpoint{};
        std::int64_t build_cost = 0;
    };

    static constexpr float kPi = 3.14159265358979323846F;
    static constexpr float kHeadingStepRadians = kPi * 0.25F;
    static constexpr float kNodeSnapRadiusWorld = 0.36F;
    static constexpr float kTerrainLevelTolerance = 0.12F;

    [[nodiscard]] static const char* mode_label(const RailPlacementMode mode) {
        switch (mode) {
            case RailPlacementMode::straight: return "STRAIGHT";
            case RailPlacementMode::curve_left: return "CURVE LEFT";
            case RailPlacementMode::curve_right: return "CURVE RIGHT";
            case RailPlacementMode::turnout_left: return "TURNOUT LEFT";
            case RailPlacementMode::turnout_right: return "TURNOUT RIGHT";
            case RailPlacementMode::crossing: return "CROSSING";
        }
        return "STRAIGHT";
    }

    [[nodiscard]] static std::string money_label(const std::int64_t amount) {
        return "$" + std::to_string(amount);
    }

    void select_mode(const RailPlacementMode mode) {
        if (gesture_active_) cancel_gesture(false);
        selected_mode_ = mode;
        refresh_status();
    }

    void rotate_new_root_heading(const float direction) {
        new_root_heading_radians_ += direction * kHeadingStepRadians;
        while (new_root_heading_radians_ < 0.0F) new_root_heading_radians_ += 2.0F * kPi;
        while (new_root_heading_radians_ >= 2.0F * kPi) new_root_heading_radians_ -= 2.0F * kPi;
        refresh_status();
    }

    [[nodiscard]] int heading_degrees() const {
        return static_cast<int>(std::lround(new_root_heading_radians_ * 180.0F / kPi)) % 360;
    }

    [[nodiscard]] std::size_t piece_count() const {
        std::unordered_set<RailPlacementPieceId> pieces;
        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (edge.piece_group != kInvalidRailPlacementPieceId) pieces.insert(edge.piece_group);
        }
        return pieces.size();
    }

    void refresh_status() {
        if (!tool_active_) {
            status_ = "RAIL MODE READY | T TOGGLE";
            return;
        }
        status_ = std::string("RAIL ") + mode_label(selected_mode_) +
            " | LMB DRAG | 1-6 PIECE | Q/E HEADING " + std::to_string(heading_degrees()) +
            " | DEL UNDO | T EXIT | PIECES " + std::to_string(piece_count());
    }

    [[nodiscard]] std::optional<RailPlacementNodeId> nearest_node(const RailDragWorldPoint& point) const {
        std::optional<RailPlacementNodeId> best;
        float best_distance_squared = kNodeSnapRadiusWorld * kNodeSnapRadiusWorld;
        for (const RailPlacementNode& node : graph_.nodes()) {
            const float dx = node.position.x - point.x;
            const float dy = node.position.y - point.y;
            const float distance_squared = dx * dx + dy * dy;
            if (distance_squared <= best_distance_squared) {
                best_distance_squared = distance_squared;
                best = node.id;
            }
        }
        return best;
    }

    [[nodiscard]] static bool tile_available(const int tile_x,
                                             const int tile_y,
                                             const InteractionContext& context,
                                             std::string* error) {
        if (tile_x < contracts::kMapMin || tile_x > contracts::kMapMax ||
            tile_y < contracts::kMapMin || tile_y > contracts::kMapMax) {
            if (error) *error = "RAIL BLOCKED: OUTSIDE MAP";
            return false;
        }
        if (context.lands != nullptr && !context.lands->is_tile_owned(tile_x, tile_y)) {
            if (error) *error = "RAIL BLOCKED: BUY LAND FIRST";
            return false;
        }
        if (context.buildings != nullptr && context.buildings->is_occupied(tile_x, tile_y)) {
            if (error) *error = "RAIL BLOCKED: BUILDING OCCUPANCY";
            return false;
        }
        if (context.farming != nullptr && context.farming->is_occupied(tile_x, tile_y)) {
            if (error) *error = "RAIL BLOCKED: FARM OCCUPANCY";
            return false;
        }
        if (context.roads != nullptr && context.roads->is_road(tile_x, tile_y)) {
            if (error) *error = "RAIL BLOCKED: ROAD CROSSING NOT AUTHORED YET";
            return false;
        }
        if (context.sidewalks != nullptr && context.sidewalks->is_sidewalk(tile_x, tile_y)) {
            if (error) *error = "RAIL BLOCKED: PATH OCCUPANCY";
            return false;
        }
        return true;
    }

    [[nodiscard]] bool validate_staged(const InteractionContext& context, std::string* error) const {
        if (!gesture_active_) return false;
        if (graph_.edges().size() <= gesture_checkpoint_.edge_count) {
            if (error) *error = "RAIL PREVIEW TOO SHORT";
            return false;
        }

        for (std::size_t edge_index = gesture_checkpoint_.edge_count;
             edge_index < graph_.edges().size(); ++edge_index) {
            const RailSplineSegment& segment = graph_.edges()[edge_index].segment;
            const int samples = std::clamp(segment.subdivisions, 8, 64);
            for (int index = 0; index <= samples; ++index) {
                const float t = static_cast<float>(index) / static_cast<float>(samples);
                const RailWorldPoint3 point = RailMeshBuilder::sample_cubic(segment, t);
                const int tile_x = static_cast<int>(std::floor(point.x));
                const int tile_y = static_cast<int>(std::floor(point.y));
                if (!tile_available(tile_x, tile_y, context, error)) return false;
                if (context.terrain != nullptr) {
                    const float terrain_z = context.terrain->sample(point.x, point.y);
                    if (!std::isfinite(terrain_z) || std::abs(terrain_z - point.z) > kTerrainLevelTolerance) {
                        if (error) *error = "RAIL BLOCKED: LEVEL GROUND REQUIRED IN V1";
                        return false;
                    }
                }
            }
        }
        return true;
    }

    void begin_gesture(const float screen_x,
                       const float screen_y,
                       const runtime_view::ViewSnapshot& view,
                       const InteractionContext& context) {
        if (gesture_active_) cancel_gesture(false);
        const auto world = RailMapForgeInputAdapter::screen_to_world(
            screen_x, screen_y, view.camera, view.viewport_width, view.viewport_height);
        if (!world) {
            status_ = "RAIL INPUT INVALID";
            return;
        }

        gesture_checkpoint_ = graph_.checkpoint();
        std::optional<RailPlacementNodeId> source = nearest_node(*world);
        if (!source) {
            const int tile_x = static_cast<int>(std::floor(world->x));
            const int tile_y = static_cast<int>(std::floor(world->y));
            std::string placement_error;
            if (!tile_available(tile_x, tile_y, context, &placement_error)) {
                status_ = placement_error;
                return;
            }
            const float z = context.terrain == nullptr ? 0.0F : context.terrain->sample(world->x, world->y);
            source = graph_.add_root({world->x, world->y, z}, new_root_heading_radians_);
            if (!source) {
                status_ = "RAIL ROOT COULD NOT BE CREATED";
                return;
            }
        }

        if (!input_.begin(*source, selected_mode_, screen_x, screen_y,
                          view.camera, view.viewport_width, view.viewport_height)) {
            (void)graph_.rollback(gesture_checkpoint_);
            status_ = "RAIL DRAG COULD NOT START";
            return;
        }

        gesture_active_ = true;
        preview_valid_ = false;
        preview_cost_ = 0;
        status_ = std::string("RAIL ") + mode_label(selected_mode_) + " | DRAG TO SIZE";
    }

    void update_gesture(const float screen_x,
                        const float screen_y,
                        const runtime_view::ViewSnapshot& view,
                        const InteractionContext& context) {
        if (!gesture_active_ || !input_.active()) return;
        const auto preview = input_.update(
            screen_x, screen_y, view.camera, view.viewport_width, view.viewport_height);
        if (!preview || !preview->ok()) {
            preview_valid_ = false;
            preview_cost_ = 0;
            status_ = "RAIL PREVIEW INVALID: DRAG FARTHER";
            return;
        }

        std::string validation_error;
        if (!validate_staged(context, &validation_error)) {
            preview_valid_ = false;
            preview_cost_ = 0;
            status_ = validation_error;
            return;
        }

        const RailConstructionQuote quote =
            RailConstructionEconomy::quote(graph_, gesture_checkpoint_.edge_count);
        if (!quote.valid || quote.build_cost <= 0) {
            preview_valid_ = false;
            preview_cost_ = 0;
            status_ = "RAIL QUOTE INVALID";
            return;
        }

        CityEconomy* economy = CityEconomy::active_instance();
        preview_cost_ = quote.build_cost;
        if (economy == nullptr) {
            preview_valid_ = false;
            status_ = "RAIL ECONOMY UNAVAILABLE";
            return;
        }
        if (!economy->can_afford(preview_cost_)) {
            preview_valid_ = false;
            status_ = "RAIL NEEDS " + money_label(preview_cost_) +
                " | FUNDS " + money_label(economy->funds());
            return;
        }

        preview_valid_ = true;
        status_ = std::string("RAIL ") + mode_label(selected_mode_) +
            " PREVIEW OK | COST " + money_label(preview_cost_) + " | RELEASE TO BUILD";
    }

    void finish_gesture(const float screen_x,
                        const float screen_y,
                        const runtime_view::ViewSnapshot& view,
                        const InteractionContext& context) {
        update_gesture(screen_x, screen_y, view, context);
        if (!preview_valid_) {
            cancel_gesture(false);
            if (status_.empty()) status_ = "RAIL PLACEMENT CANCELLED";
            return;
        }

        const rail::RailPlacementTopologyBuildResult topology = rail::build_track_graph(graph_);
        if (!topology.valid) {
            const std::string error = topology.error.empty() ? "TOPOLOGY REJECTED" : topology.error;
            cancel_gesture(false);
            status_ = "RAIL TOPOLOGY REJECTED: " + error;
            return;
        }

        CityEconomy* economy = CityEconomy::active_instance();
        const std::int64_t committed_cost = preview_cost_;
        if (economy == nullptr || committed_cost <= 0 || !economy->can_afford(committed_cost)) {
            cancel_gesture(false);
            status_ = "RAIL COMMIT BLOCKED: FUNDS CHANGED";
            return;
        }

        if (!input_.confirm()) {
            cancel_gesture(false);
            status_ = "RAIL COMMIT FAILED";
            return;
        }

        // The geometry becomes authoritative only after the controller commits.
        // Money is charged afterwards; if that final charge unexpectedly fails,
        // the same pre-gesture checkpoint restores the graph atomically.
        if (!economy->try_spend(committed_cost)) {
            (void)graph_.rollback(gesture_checkpoint_);
            gesture_active_ = false;
            preview_valid_ = false;
            preview_cost_ = 0;
            committed_edge_count_ = graph_.edges().size();
            status_ = "RAIL COMMIT ROLLED BACK: PAYMENT FAILED";
            return;
        }

        committed_actions_.push_back({gesture_checkpoint_, committed_cost});
        committed_edge_count_ = graph_.edges().size();
        gesture_active_ = false;
        preview_valid_ = false;
        preview_cost_ = 0;
        status_ = "RAIL BUILT: " + money_label(committed_cost) +
            " SPENT | DEL UNDO | PIECES " + std::to_string(piece_count());
    }

    void demolish_last_committed_action() {
        if (committed_actions_.empty()) {
            status_ = "RAIL DEMOLISH: NO COMMITTED PIECE";
            return;
        }
        CityEconomy* economy = CityEconomy::active_instance();
        if (economy == nullptr) {
            status_ = "RAIL DEMOLISH: ECONOMY UNAVAILABLE";
            return;
        }

        const CommittedRailAction action = committed_actions_.back();
        if (!graph_.rollback(action.checkpoint)) {
            status_ = "RAIL DEMOLISH FAILED: CHECKPOINT REJECTED";
            return;
        }

        const std::int64_t refund = RailConstructionEconomy::demolition_refund(action.build_cost);
        economy->credit_infrastructure_refund(refund);
        committed_actions_.pop_back();
        committed_edge_count_ = graph_.edges().size();
        preview_valid_ = false;
        preview_cost_ = 0;
        status_ = "RAIL DEMOLISHED | REFUND " + money_label(refund) +
            " | PIECES " + std::to_string(piece_count());
    }

    void cancel_gesture(const bool refresh) {
        if (input_.active()) (void)input_.cancel();
        if (gesture_active_) (void)graph_.rollback(gesture_checkpoint_);
        gesture_active_ = false;
        preview_valid_ = false;
        preview_cost_ = 0;
        committed_edge_count_ = graph_.edges().size();
        if (refresh) refresh_status();
    }

    RailProfile profile_{};
    RailPlacementGraph graph_;
    RailPlacementController controller_;
    RailDragAdapter drag_;
    RailMapForgeInputAdapter input_;
    RailPlacementMode selected_mode_ = RailPlacementMode::straight;
    RailPlacementCheckpoint gesture_checkpoint_{};
    std::vector<CommittedRailAction> committed_actions_;
    std::size_t committed_edge_count_ = 0U;
    std::int64_t preview_cost_ = 0;
    float new_root_heading_radians_ = 0.0F;
    bool tool_active_ = false;
    bool gesture_active_ = false;
    bool preview_valid_ = false;
    std::string status_;
};

[[nodiscard]] inline RuntimeState& state() {
    static RuntimeState instance;
    return instance;
}

inline void reset() { state().reset(); }
[[nodiscard]] inline bool tool_active() { return state().tool_active(); }
[[nodiscard]] inline const std::string& status_text() { return state().status_text(); }
[[nodiscard]] inline const RailPlacementGraph& graph() { return state().graph(); }

[[nodiscard]] inline bool poll_event(SDL_Event* event,
                                     const bool interaction_allowed,
                                     const InteractionContext& context) {
    if (event == nullptr) return false;
    while (SDL_PollEvent(event)) {
        if (state().consume_event(*event, interaction_allowed, context)) continue;
        return true;
    }
    return false;
}

inline void render(SDL_Renderer* renderer,
                   const CameraState& camera,
                   const float viewport_width,
                   const float viewport_height) {
    state().render(renderer, camera, viewport_width, viewport_height);
}

} // namespace ch::rail_runtime

namespace ch {

// Runtime composition layer: keep the existing road renderer authoritative and
// append the procedural railway immediately above roads and below sidewalks.
class ChRailRuntimeMapRenderer : public RuntimeMapRenderer {
public:
    static void render_roads(
        SDL_Renderer* renderer, const RoadManager& roads,
        const RoadVisualCatalog& visuals,
        const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
        const std::filesystem::path& asset_root, const CameraState& camera,
        const float viewport_width, const float viewport_height,
        const MapDocument* document = nullptr) {
        RuntimeMapRenderer::render_roads(
            renderer, roads, visuals, find_texture, asset_root,
            camera, viewport_width, viewport_height, document);
        rail_runtime::render(renderer, camera, viewport_width, viewport_height);
    }
};

} // namespace ch
