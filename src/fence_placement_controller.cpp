#include "fence_placement_controller.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <unordered_set>

namespace {

[[nodiscard]] std::int64_t preview_key(const FenceVertex vertex) {
    return (static_cast<std::int64_t>(vertex.x) << 32) ^
           static_cast<std::uint32_t>(vertex.y);
}

[[nodiscard]] FenceVertex offset_vertex(const FenceVertex vertex,
                                        const CardinalDirection direction) {
    const TileOffset offset = direction_offset(direction);
    return {vertex.x + offset.x, vertex.y + offset.y};
}

}  // namespace

FencePlacementController::FencePlacementController(FenceManager& fences)
    : fences_(fences) {}

void FencePlacementController::begin_drag(const FenceVertex start,
                                          const FenceRotation orientation_hint) {
    dragging_ = true;
    orientation_hint_ = orientation_hint;
    start_ = start;
    current_ = start;
    rebuild_preview_route();
}

void FencePlacementController::update_drag(const FenceVertex current) {
    if (!dragging_) return;
    current_ = current;
    rebuild_preview_route();
}

void FencePlacementController::cancel_drag() {
    dragging_ = false;
    start_.reset();
    current_.reset();
    preview_route_.clear();
}

bool FencePlacementController::dragging() const {
    return dragging_;
}

std::optional<FenceVertex> FencePlacementController::drag_start() const {
    return start_;
}

std::optional<FenceVertex> FencePlacementController::drag_current() const {
    return current_;
}

const std::vector<FenceVertex>& FencePlacementController::preview_route() const {
    return preview_route_;
}

bool FencePlacementController::preview_contains(const FenceVertex vertex) const {
    return std::any_of(preview_route_.begin(), preview_route_.end(),
                       [vertex](const FenceVertex candidate) {
                           return candidate.x == vertex.x && candidate.y == vertex.y;
                       });
}

bool FencePlacementController::virtual_has_fence(const FenceVertex vertex) const {
    return fences_.has_fence(vertex.x, vertex.y) || preview_contains(vertex);
}

FenceConnection FencePlacementController::virtual_connections(const FenceVertex vertex) const {
    FenceConnection mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        if (virtual_has_fence(offset_vertex(vertex, direction))) {
            mask = static_cast<FenceConnection>(mask | connection_bit(direction));
        }
    }
    return mask;
}

std::vector<FencePlacementPreviewNode> FencePlacementController::preview_nodes() const {
    if (!dragging_ || preview_route_.empty()) return {};

    // Route nodes plus their existing neighbours are the only nodes that can
    // change topology during this preview.
    std::vector<FenceVertex> candidates;
    candidates.reserve(preview_route_.size() * 5U);
    std::unordered_set<std::int64_t> seen;

    const auto add_candidate = [&](const FenceVertex vertex) mutable {
        if (!fences_.is_inside_vertex_grid(vertex.x, vertex.y)) return;
        if (seen.insert(preview_key(vertex)).second) candidates.push_back(vertex);
    };

    for (const FenceVertex route_vertex : preview_route_) {
        add_candidate(route_vertex);
        for (const CardinalDirection direction : kCardinalDirections) {
            const FenceVertex neighbour = offset_vertex(route_vertex, direction);
            if (fences_.has_fence(neighbour.x, neighbour.y)) add_candidate(neighbour);
        }
    }

    std::vector<FencePlacementPreviewNode> result;
    result.reserve(candidates.size());
    for (const FenceVertex vertex : candidates) {
        const FenceNode* existing = fences_.node_at(vertex.x, vertex.y);
        const FenceNodeKind kind = existing == nullptr ? FenceNodeKind::regular : existing->kind;
        const FenceRotation hint = existing == nullptr ? orientation_hint_ : existing->orientation_hint;
        const FenceConnection connections = virtual_connections(vertex);
        result.push_back({vertex,
                          resolve_fence_visual(connections, kind, hint),
                          existing != nullptr});
    }

    return result;
}

int FencePlacementController::commit_drag() {
    if (!dragging_ || preview_route_.empty()) return 0;

    const int placed = fences_.place_run(preview_route_, orientation_hint_);
    cancel_drag();
    return placed;
}

bool FencePlacementController::place_open_gate(const FenceVertex vertex) {
    return fences_.set_gate(vertex.x, vertex.y, true);
}

void FencePlacementController::rebuild_preview_route() {
    preview_route_.clear();
    if (!dragging_ || !start_ || !current_) return;
    preview_route_ = fences_.line_between(*start_, *current_);
}
