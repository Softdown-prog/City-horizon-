#pragma once

#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "rail_construction_economy.h"
#include "rail_mapforge_input_adapter.h"
#include "rail_persistence.h"
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

inline constexpr const char* kChRailRuntimeBridgeContract = "CH_RAIL_RUNTIME_BRIDGE_V3";

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
    [[nodiscard]] RailPlacementMode selected_mode() const noexcept { return selected_mode_; }
    // The catalog uses the same transactional placement state as number shortcuts.
    void activate_placement_mode(const RailPlacementMode mode) {
        tool_active_ = true;
        select_mode(mode);
    }
    [[nodiscard]] const std::string& status_text() const noexcept { return status_; }
    [[nodiscard]] const RailPlacementGraph& graph() const noexcept { return graph_; }

    [[nodiscard]] RailPersistentState persistent_state() const {
        RailPersistentState state;
        state.nodes = graph_.nodes();
        state.edges = graph_.edges();
        state.actions = committed_actions_;
        state.turntables = turntables_;
        // A save captures only authoritative construction. A live ghost is
        // append-only after gesture_checkpoint_ and is never persisted.
        if (gesture_active_) {
            if (gesture_checkpoint_.node_count <= state.nodes.size()) {
                state.nodes.resize(gesture_checkpoint_.node_count);
            }
            if (gesture_checkpoint_.edge_count <= state.edges.size()) {
                state.edges.resize(gesture_checkpoint_.edge_count);
            }
        }
        return state;
    }

    [[nodiscard]] bool restore_persistent_state(const RailPersistentState& state) {
        std::string validation_error;
        if (!rail_persistence::validate(state, &validation_error)) return false;
        cancel_gesture(false);
        if (!graph_.restore_snapshot(state.nodes, state.edges)) return false;
        committed_actions_ = state.actions;
        turntables_ = state.turntables;
        selected_mode_ = RailPlacementMode::straight;
        connector_mode_ = false;
        connector_from_.reset();
        hovered_piece_.reset();
        new_root_heading_radians_ = 0.0F;
        tool_active_ = false;
        preview_valid_ = false;
        preview_cost_ = 0;
        refresh_status();
        return true;
    }

    void reset() {
        cancel_gesture(false);
        graph_.clear();
        committed_actions_.clear();
        turntables_.clear();
        hovered_piece_.reset();
        tool_active_ = false;
        selected_mode_ = RailPlacementMode::straight;
        connector_mode_ = false;
        connector_from_.reset();
        new_root_heading_radians_ = 0.0F;
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
                hovered_piece_.reset();
                tool_active_ = false;
                status_ = "RAIL MODE CLOSED BY MODAL";
            }
            return false;
        }

        if (event.type == SDL_EVENT_KEY_DOWN && !event.key.repeat) {
            if (event.key.scancode == SDL_SCANCODE_T) {
                if (tool_active_) {
                    cancel_gesture(false);
                    hovered_piece_.reset();
                    connector_mode_ = false;
                    connector_from_.reset();
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
                case SDL_SCANCODE_0:
                    if(gesture_active_)cancel_gesture(false);
                    toggle_turntable(context);
                    return true;
                case SDL_SCANCODE_9:
                    if (gesture_active_) cancel_gesture(false);
                    connector_mode_ = !connector_mode_;
                    connector_from_.reset();
                    refresh_status();
                    return true;
                case SDL_SCANCODE_Q:
                    if (!gesture_active_) rotate_new_root_heading(-1.0F);
                    return true;
                case SDL_SCANCODE_E:
                    if (!gesture_active_) rotate_new_root_heading(1.0F);
                    return true;
                case SDL_SCANCODE_DELETE:
                    if (gesture_active_) {
                        cancel_gesture(false);
                        status_ = "RAIL PREVIEW CANCELLED";
                    } else {
                        demolish_hovered_piece();
                    }
                    return true;
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
                        hovered_piece_.reset();
                        connector_mode_ = false;
                        connector_from_.reset();
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
            else if (connector_mode_) {
                connector_mode_ = false;
                connector_from_.reset();
                refresh_status();
            } else {
                hovered_piece_.reset();
                tool_active_ = false;
                status_ = "RAIL MODE CLOSED";
            }
            return true;
        }

        if (event.type == SDL_EVENT_MOUSE_BUTTON_DOWN && event.button.button == SDL_BUTTON_LEFT) {
            if (connector_mode_) click_siding_port(event.button.x, event.button.y, view, context);
            else begin_gesture(event.button.x, event.button.y, view, context);
            return true;
        }

        if (event.type == SDL_EVENT_MOUSE_MOTION) {
            if (gesture_active_) update_gesture(event.motion.x, event.motion.y, view, context);
            else update_hovered_piece(event.motion.x, event.motion.y, view);
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
        ProceduralRailRenderer::Palette hover_palette{};
        hover_palette.ballast = SDL_Color{111, 121, 129, 235};
        hover_palette.sleepers = SDL_Color{144, 111, 72, 255};
        hover_palette.rails = SDL_Color{237, 218, 128, 255};
        ProceduralRailRenderer::Palette valid_preview_palette{};
        valid_preview_palette.ballast = SDL_Color{124, 111, 74, 220};
        valid_preview_palette.sleepers = SDL_Color{125, 83, 42, 235};
        valid_preview_palette.rails = SDL_Color{219, 193, 95, 255};
        ProceduralRailRenderer::Palette invalid_preview_palette{};
        invalid_preview_palette.ballast = SDL_Color{129, 58, 54, 210};
        invalid_preview_palette.sleepers = SDL_Color{142, 58, 45, 235};
        invalid_preview_palette.rails = SDL_Color{232, 91, 76, 255};

        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (!edge.active) continue;
            const bool staged = gesture_active_ &&
                static_cast<std::size_t>(edge.id) >= gesture_checkpoint_.edge_count;
            const bool hovered = !staged && hovered_piece_.has_value() &&
                edge.piece_group == *hovered_piece_;
            const ProceduralRailRenderer::Palette& palette = staged
                ? (preview_valid_ ? valid_preview_palette : invalid_preview_palette)
                : (hovered ? hover_palette : committed_palette);
            (void)ProceduralRailRenderer::render_segment(
                renderer, edge.segment, profile_, camera,
                viewport_width, viewport_height, palette);
        }
    }

private:
    static constexpr float kPi = 3.14159265358979323846F;
    static constexpr float kHeadingStepRadians = kPi * 0.25F;
    static constexpr float kNodeSnapRadiusWorld = 0.36F;
    static constexpr float kPieceHoverRadiusWorld = 0.34F;
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
        connector_mode_ = false;
        connector_from_.reset();
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
            if (edge.active && edge.piece_group != kInvalidRailPlacementPieceId) pieces.insert(edge.piece_group);
        }
        return pieces.size();
    }

    void refresh_status() {
        if (!tool_active_) {
            status_ = "RAIL MODE READY | T TOGGLE";
            return;
        }
        if (connector_mode_) {
            status_ = connector_from_
                ? "RAIL CONNECT | SELECT SECOND OPEN ENDPOINT | RMB CANCEL"
                : "RAIL CONNECT | SELECT FIRST OPEN ENDPOINT | RMB CANCEL";
            return;
        }
        status_ = std::string("RAIL ") + mode_label(selected_mode_) +
            " | LMB DRAG | 1-6 PIECE | Q/E HEADING " + std::to_string(heading_degrees()) +
            " | DEL REMOVE | BACKSPACE LAST | 7 STATION | 8 RESTART | 9 CONNECT | 0 TURNTABLE | T EXIT | PIECES " + std::to_string(piece_count());
        if (hovered_piece_) status_ += " | HOVER " + std::to_string(*hovered_piece_);
    }

    [[nodiscard]] std::optional<RailPlacementNodeId> nearest_node(const RailDragWorldPoint& point) const {
        std::optional<RailPlacementNodeId> best;
        float best_distance_squared = kNodeSnapRadiusWorld * kNodeSnapRadiusWorld;
        for (const RailPlacementNode& node : graph_.nodes()) {
            if (!node.active) continue;
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

    [[nodiscard]] static float point_segment_distance_squared(const RailDragWorldPoint& point,
                                                               const RailWorldPoint3& a,
                                                               const RailWorldPoint3& b) {
        const float vx = b.x - a.x;
        const float vy = b.y - a.y;
        const float wx = point.x - a.x;
        const float wy = point.y - a.y;
        const float length_squared = vx * vx + vy * vy;
        if (length_squared <= 1.0e-9F) return wx * wx + wy * wy;
        const float t = std::clamp((wx * vx + wy * vy) / length_squared, 0.0F, 1.0F);
        const float dx = point.x - (a.x + vx * t);
        const float dy = point.y - (a.y + vy * t);
        return dx * dx + dy * dy;
    }

    [[nodiscard]] std::optional<RailPlacementPieceId> nearest_piece(const RailDragWorldPoint& point) const {
        std::optional<RailPlacementPieceId> best;
        float best_distance_squared = kPieceHoverRadiusWorld * kPieceHoverRadiusWorld;
        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (!edge.active || edge.piece_group == kInvalidRailPlacementPieceId) continue;
            const int samples = std::clamp(edge.segment.subdivisions, 8, 64);
            RailWorldPoint3 previous = RailMeshBuilder::sample_cubic(edge.segment, 0.0F);
            for (int index = 1; index <= samples; ++index) {
                const float t = static_cast<float>(index) / static_cast<float>(samples);
                const RailWorldPoint3 current = RailMeshBuilder::sample_cubic(edge.segment, t);
                const float distance_squared = point_segment_distance_squared(point, previous, current);
                if (distance_squared <= best_distance_squared) {
                    best_distance_squared = distance_squared;
                    best = edge.piece_group;
                }
                previous = current;
            }
        }
        return best;
    }

    void update_hovered_piece(const float screen_x,
                              const float screen_y,
                              const runtime_view::ViewSnapshot& view) {
        const auto world = RailMapForgeInputAdapter::screen_to_world(
            screen_x, screen_y, view.camera, view.viewport_width, view.viewport_height);
        hovered_piece_ = world ? nearest_piece(*world) : std::nullopt;
        refresh_status();
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
            const RailPlacementEdge& edge = graph_.edges()[edge_index];
            if (!edge.active) continue;
            const RailSplineSegment& segment = edge.segment;
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

    // Build a paid 7.2m rotating bridge centred over an existing straight.
    // The rail itself remains a normal graph edge; the persisted device alone
    // authorizes in-game locomotive rotation. No free hidden animation.
    void toggle_turntable(const InteractionContext& context) {
        if(!hovered_piece_) {
            status_="TURNTABLE: HOVER A LONG STRAIGHT TRACK FIRST";
            return;
        }
        const RailPlacementPieceId group=*hovered_piece_;
        const auto found=std::find_if(turntables_.begin(),turntables_.end(),
            [&](const RailPersistentTurntable& t){return t.piece_group==group;});
        CityEconomy* economy=CityEconomy::active_instance();
        if(economy==nullptr){status_="TURNTABLE: ECONOMY UNAVAILABLE";return;}
        if(found!=turntables_.end()){
            economy->credit_infrastructure_refund(found->refund_value);
            turntables_.erase(found);
            status_="TURNTABLE DISMANTLED: ENGINE RETURN NOW REQUIRES RESTART";
            return;
        }
        const RailPlacementEdge* target=nullptr;
        for(const auto& edge:graph_.edges()) {
            if(edge.active && edge.piece_group==group) {
                if(target!=nullptr || edge.kind!=RailPlacementEdgeKind::straight){
                    status_="TURNTABLE: MUST USE ONE STRAIGHT SECTION";
                    return;
                }
                target=&edge;
            }
        }
        if(target==nullptr ||
           rail_persistence::detail_unused_turntable_length(target->segment)<8.0) {
            status_="TURNTABLE: STRAIGHT MUST BE AT LEAST 8M LONG";
            return;
        }
        const auto& seg=target->segment;
        const auto center=RailMeshBuilder::sample_cubic(seg,0.5F);
        // A 7.2m diameter foundation is a construction footprint, not a
        // floating decorative disc. Validate 9x9 tiles and level ground.
        constexpr float kRadius=3.6F;
        for(int x=static_cast<int>(std::floor(center.x-kRadius));
                x<=static_cast<int>(std::floor(center.x+kRadius));++x) {
            for(int y=static_cast<int>(std::floor(center.y-kRadius));
                    y<=static_cast<int>(std::floor(center.y+kRadius));++y) {
                const float dx=(static_cast<float>(x)+0.5F)-center.x;
                const float dy=(static_cast<float>(y)+0.5F)-center.y;
                if(dx*dx+dy*dy>kRadius*kRadius)continue;
                std::string error;
                if(!tile_available(x,y,context,&error)){
                    status_="TURNTABLE: "+error;
                    return;
                }
                if(context.terrain!=nullptr) {
                    const float z=context.terrain->sample(
                        static_cast<float>(x)+0.5F,static_cast<float>(y)+0.5F);
                    if(!std::isfinite(z) || std::abs(z-center.z)>kTerrainLevelTolerance){
                        status_="TURNTABLE: REQUIRES LEVEL TERRAIN";
                        return;
                    }
                }
            }
        }
        // No different rail segment may enter the spinning deck.
        for(const auto& edge:graph_.edges()) {
            if(!edge.active || edge.piece_group==group)continue;
            const int samples=std::clamp(edge.segment.subdivisions,16,100);
            for(int i=0;i<=samples;++i){
                const auto point=RailMeshBuilder::sample_cubic(
                    edge.segment,static_cast<float>(i)/static_cast<float>(samples));
                const float dx=point.x-center.x,dy=point.y-center.y;
                if(dx*dx+dy*dy<kRadius*kRadius){
                    status_="TURNTABLE: OTHER RAIL INTERSECTS ROTATING DECK";
                    return;
                }
            }
        }
        constexpr std::int64_t kPrice=3500;
        if(!economy->can_afford(kPrice)||!economy->try_spend(kPrice)){
            status_="TURNTABLE: INSUFFICIENT FUNDS";
            return;
        }
        turntables_.push_back({group,kPrice,RailConstructionEconomy::demolition_refund(kPrice)});
        status_="TURNTABLE BUILT: $3500 | SAVED WITH CITY";
    }

    // Click-to-connect 2 authored, open rail nodes. This is a persistent,
    // fully priced construction rather than a test-only line drawn over ground.
    void click_siding_port(const float screen_x, const float screen_y,
                           const runtime_view::ViewSnapshot& view,
                           const InteractionContext& context) {
        const auto world = RailMapForgeInputAdapter::screen_to_world(
            screen_x, screen_y, view.camera, view.viewport_width, view.viewport_height);
        if (!world) {
            status_ = "RAIL CONNECT: INVALID WORLD POINT";
            return;
        }
        const auto target = nearest_node(*world);
        if (!target) {
            status_ = "RAIL CONNECT: CLICK AN EXISTING TRACK ENDPOINT";
            return;
        }
        // Reject shared turnouts/junctions and disconnected blank editor roots.
        const auto open_port = [&](RailPlacementNodeId node) {
            std::size_t count = 0U;
            for (const auto& edge : graph_.edges()) {
                if (edge.active && (edge.from == node || edge.to == node)) ++count;
            }
            return count == 1U;
        };
        if (!open_port(*target)) {
            status_ = "RAIL CONNECT: ENDPOINT MUST HAVE ONE TRACK";
            return;
        }
        if (!connector_from_) {
            connector_from_ = *target;
            refresh_status();
            return;
        }
        const auto from = *connector_from_;
        connector_from_.reset();
        if (from == *target || !open_port(from)) {
            status_ = "RAIL CONNECT: SELECT TWO DIFFERENT OPEN ENDPOINTS";
            return;
        }
        const auto checkpoint = graph_.checkpoint();
        const auto segment = graph_.append_smooth_connector(from, *target);
        if (!segment) {
            status_ = "RAIL CONNECT: CANNOT FIT A SAFE CONNECTING CURVE";
            return;
        }
        // Existing shared collision/level rules need gesture_active_ set
        // only while validating the newly appended edge. No pointer drag is
        // started and no staged section is persisted before payment.
        gesture_checkpoint_ = checkpoint;
        gesture_active_ = true;
        std::string validation_error;
        const bool terrain_safe = validate_staged(context, &validation_error);
        gesture_active_ = false;
        if (!terrain_safe) {
            (void)graph_.rollback(checkpoint);
            status_ = validation_error.empty() ? "RAIL CONNECT: GROUND BLOCKED" : validation_error;
            return;
        }
        const auto topology = rail::build_track_graph(graph_);
        if (!topology.valid) {
            (void)graph_.rollback(checkpoint);
            status_ = "RAIL CONNECT: TOPOLOGY REJECTED";
            return;
        }
        const auto quote = RailConstructionEconomy::quote(graph_, checkpoint.edge_count);
        CityEconomy* economy = CityEconomy::active_instance();
        if (!quote.valid || quote.build_cost <= 0 || economy == nullptr ||
            !economy->can_afford(quote.build_cost)) {
            (void)graph_.rollback(checkpoint);
            status_ = "RAIL CONNECT: INSUFFICIENT FUNDS OR INVALID PRICE";
            return;
        }
        if (!economy->try_spend(quote.build_cost)) {
            (void)graph_.rollback(checkpoint);
            status_ = "RAIL CONNECT: PAYMENT FAILED; ROLLED BACK";
            return;
        }
        const auto piece_group = graph_.edges()[segment->edge].piece_group;
        const auto refund = RailConstructionEconomy::demolition_refund(quote.build_cost);
        committed_actions_.push_back({piece_group, quote.build_cost, refund, true});
        status_ = "RAIL CONNECTED: " + money_label(quote.build_cost) +
            " SPENT | BOTH PORTS VALIDATED";
    }

    void begin_gesture(const float screen_x,
                       const float screen_y,
                       const runtime_view::ViewSnapshot& view,
                       const InteractionContext& context) {
        if (gesture_active_) cancel_gesture(false);
        hovered_piece_.reset();
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
        if (gesture_checkpoint_.edge_count >= graph_.edges().size()) {
            cancel_gesture(false);
            status_ = "RAIL COMMIT FAILED: NO LOGICAL PIECE";
            return;
        }
        const RailPlacementPieceId piece_group = graph_.edges()[gesture_checkpoint_.edge_count].piece_group;
        if (piece_group == kInvalidRailPlacementPieceId) {
            cancel_gesture(false);
            status_ = "RAIL COMMIT FAILED: PIECE ID INVALID";
            return;
        }
        for (std::size_t index = gesture_checkpoint_.edge_count; index < graph_.edges().size(); ++index) {
            if (!graph_.edges()[index].active || graph_.edges()[index].piece_group != piece_group) {
                cancel_gesture(false);
                status_ = "RAIL COMMIT FAILED: MIXED PIECE GROUP";
                return;
            }
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
            status_ = "RAIL COMMIT ROLLED BACK: PAYMENT FAILED";
            return;
        }

        const std::int64_t refund = RailConstructionEconomy::demolition_refund(committed_cost);
        committed_actions_.push_back({piece_group, committed_cost, refund, true});
        gesture_active_ = false;
        preview_valid_ = false;
        preview_cost_ = 0;
        status_ = "RAIL BUILT: " + money_label(committed_cost) +
            " SPENT | DEL HOVER REMOVE | BACKSPACE LAST | PIECES " + std::to_string(piece_count());
    }

    [[nodiscard]] RailPersistentAction* active_action(const RailPlacementPieceId piece_group) {
        for (RailPersistentAction& action : committed_actions_) {
            if (action.active && action.piece_group == piece_group) return &action;
        }
        return nullptr;
    }

    void demolish_piece(const RailPlacementPieceId piece_group) {
        CityEconomy* economy = CityEconomy::active_instance();
        if (economy == nullptr) {
            status_ = "RAIL DEMOLISH: ECONOMY UNAVAILABLE";
            return;
        }
        RailPersistentAction* action = active_action(piece_group);
        if (action == nullptr) {
            status_ = "RAIL DEMOLISH: PIECE HAS NO ACTIVE LEDGER ENTRY";
            return;
        }
        if (graph_.remove_piece(piece_group) == 0U) {
            status_ = "RAIL DEMOLISH FAILED: PIECE NOT LIVE";
            return;
        }

        const rail::RailPlacementTopologyBuildResult topology = rail::build_track_graph(graph_);
        if (!topology.valid) {
            (void)graph_.set_piece_active(piece_group, true);
            status_ = "RAIL DEMOLISH ROLLED BACK: TOPOLOGY REJECTED";
            return;
        }

        economy->credit_infrastructure_refund(action->refund_value);
        // The rotating device is a separately paid attachment to this rail.
        // Demolishing its host must also decommission and refund the device.
        const auto device=std::find_if(turntables_.begin(),turntables_.end(),
            [&](const RailPersistentTurntable& t){return t.piece_group==piece_group;});
        if(device!=turntables_.end()){
            economy->credit_infrastructure_refund(device->refund_value);
            turntables_.erase(device);
        }
        action->active = false;
        hovered_piece_.reset();
        preview_valid_ = false;
        preview_cost_ = 0;
        status_ = "RAIL DEMOLISHED | REFUND " + money_label(action->refund_value) +
            " | PIECES " + std::to_string(piece_count());
    }

    void demolish_hovered_piece() {
        if (!hovered_piece_) {
            status_ = "RAIL DEMOLISH: HOVER A TRACK PIECE FIRST";
            return;
        }
        demolish_piece(*hovered_piece_);
    }

    void demolish_last_committed_action() {
        for (auto it = committed_actions_.rbegin(); it != committed_actions_.rend(); ++it) {
            if (!it->active) continue;
            demolish_piece(it->piece_group);
            return;
        }
        status_ = "RAIL DEMOLISH: NO COMMITTED PIECE";
    }

    void cancel_gesture(const bool refresh) {
        if (input_.active()) (void)input_.cancel();
        if (gesture_active_) (void)graph_.rollback(gesture_checkpoint_);
        gesture_active_ = false;
        preview_valid_ = false;
        preview_cost_ = 0;
        if (refresh) refresh_status();
    }

    RailProfile profile_{};
    RailPlacementGraph graph_;
    RailPlacementController controller_;
    RailDragAdapter drag_;
    RailMapForgeInputAdapter input_;
    RailPlacementMode selected_mode_ = RailPlacementMode::straight;
    bool connector_mode_ = false;
    std::optional<RailPlacementNodeId> connector_from_{};
    RailPlacementCheckpoint gesture_checkpoint_{};
    std::vector<RailPersistentAction> committed_actions_;
    std::vector<RailPersistentTurntable> turntables_;
    std::optional<RailPlacementPieceId> hovered_piece_;
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
[[nodiscard]] inline RailPersistentState persistent_state() { return state().persistent_state(); }
[[nodiscard]] inline bool restore_persistent_state(const RailPersistentState& persistent) {
    return state().restore_persistent_state(persistent);
}

[[nodiscard]] inline RailPersistentState capture_persistence_callback() {
    return persistent_state();
}

[[nodiscard]] inline bool restore_persistence_callback(const RailPersistentState& persistent) {
    return restore_persistent_state(persistent);
}

inline const bool kRailPersistenceRuntimeRegistered = []() {
    rail_persistence::register_runtime(&capture_persistence_callback, &restore_persistence_callback);
    return true;
}();

[[nodiscard]] inline bool poll_event(SDL_Event* event,
                                     const bool interaction_allowed,
                                     const InteractionContext& context) {
    (void)kRailPersistenceRuntimeRegistered;
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
    (void)kRailPersistenceRuntimeRegistered;
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
