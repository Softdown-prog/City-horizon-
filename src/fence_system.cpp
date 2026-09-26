#include "fence_system.h"

#include <bit>

namespace {

[[nodiscard]] constexpr bool is_opposite_pair(const FenceConnection mask) {
    return mask == static_cast<FenceConnection>(fence_north | fence_south) ||
           mask == static_cast<FenceConnection>(fence_east | fence_west);
}

[[nodiscard]] constexpr FenceRotation end_rotation(const FenceConnection mask,
                                                   const FenceRotation fallback) {
    // Canonical End points from the node centre toward logical East.
    if (mask == fence_east) return FenceRotation::south;
    if (mask == fence_south) return FenceRotation::east;
    if (mask == fence_west) return FenceRotation::north;
    if (mask == fence_north) return FenceRotation::west;
    return fallback;
}

[[nodiscard]] constexpr FenceRotation straight_rotation(const FenceConnection mask,
                                                        const FenceRotation fallback) {
    // Canonical Straight lies on the logical West/East axis.
    if (mask == static_cast<FenceConnection>(fence_east | fence_west)) return FenceRotation::south;
    if (mask == static_cast<FenceConnection>(fence_north | fence_south)) return FenceRotation::east;
    return fallback;
}

[[nodiscard]] constexpr FenceRotation corner_rotation(const FenceConnection mask,
                                                      const FenceRotation fallback) {
    // Canonical Corner arms are West + South.
    if (mask == static_cast<FenceConnection>(fence_west | fence_south)) return FenceRotation::south;
    if (mask == static_cast<FenceConnection>(fence_north | fence_west)) return FenceRotation::east;
    if (mask == static_cast<FenceConnection>(fence_north | fence_east)) return FenceRotation::north;
    if (mask == static_cast<FenceConnection>(fence_south | fence_east)) return FenceRotation::west;
    return fallback;
}

[[nodiscard]] constexpr FenceRotation tee_rotation(const FenceConnection mask,
                                                   const FenceRotation fallback) {
    // Canonical Tee has West + East + South arms, so the open side is North.
    if (!has_connection(mask, CardinalDirection::north)) return FenceRotation::south;
    if (!has_connection(mask, CardinalDirection::east)) return FenceRotation::east;
    if (!has_connection(mask, CardinalDirection::south)) return FenceRotation::north;
    if (!has_connection(mask, CardinalDirection::west)) return FenceRotation::west;
    return fallback;
}

}  // namespace

FenceVisualState resolve_fence_visual(const FenceConnection connections,
                                      const FenceNodeKind kind,
                                      const FenceRotation orientation_hint) {
    const FenceConnection mask = static_cast<FenceConnection>(connections & 0x0FU);
    const int neighbors = std::popcount(mask);

    if (kind == FenceNodeKind::gate && neighbors == 2 && is_opposite_pair(mask)) {
        return {FenceVisualType::gate, straight_rotation(mask, orientation_hint), mask};
    }

    if (neighbors == 0) {
        return {FenceVisualType::isolated, orientation_hint, mask};
    }
    if (neighbors == 1) {
        return {FenceVisualType::end, end_rotation(mask, orientation_hint), mask};
    }
    if (neighbors == 2) {
        if (is_opposite_pair(mask)) {
            return {FenceVisualType::straight, straight_rotation(mask, orientation_hint), mask};
        }
        return {FenceVisualType::corner, corner_rotation(mask, orientation_hint), mask};
    }
    if (neighbors == 3) {
        return {FenceVisualType::tee, tee_rotation(mask, orientation_hint), mask};
    }
    return {FenceVisualType::cross, orientation_hint, mask};
}

FenceManager::FenceManager(const int map_min, const int map_max)
    : map_min_(map_min), map_max_(map_max) {}

bool FenceManager::is_inside_vertex_grid(const int vertex_x, const int vertex_y) const {
    // Terrain tiles occupy [map_min, map_max]. Their enclosing vertex grid has
    // one extra coordinate on the positive X/Y sides.
    return vertex_x >= map_min_ && vertex_x <= map_max_ + 1 &&
           vertex_y >= map_min_ && vertex_y <= map_max_ + 1;
}

bool FenceManager::has_fence(const int vertex_x, const int vertex_y) const {
    return node_at(vertex_x, vertex_y) != nullptr;
}

const FenceNode* FenceManager::node_at(const int vertex_x, const int vertex_y) const {
    if (!is_inside_vertex_grid(vertex_x, vertex_y)) return nullptr;
    const auto found = node_indices_.find(vertex_key(vertex_x, vertex_y));
    return found == node_indices_.end() ? nullptr : &nodes_[found->second];
}

FenceConnection FenceManager::connection_mask(const int vertex_x, const int vertex_y) const {
    const FenceNode* node = node_at(vertex_x, vertex_y);
    return node == nullptr ? 0 : node->connections;
}

FenceVisualState FenceManager::visual_state(const int vertex_x, const int vertex_y) const {
    const FenceNode* node = node_at(vertex_x, vertex_y);
    if (node == nullptr) return {};
    return resolve_fence_visual(node->connections, node->kind, node->orientation_hint);
}

bool FenceManager::place_node(const int vertex_x, const int vertex_y,
                              const FenceRotation orientation_hint) {
    if (!is_inside_vertex_grid(vertex_x, vertex_y) || has_fence(vertex_x, vertex_y)) return false;

    node_indices_.emplace(vertex_key(vertex_x, vertex_y), nodes_.size());
    nodes_.push_back({vertex_x, vertex_y, 0, FenceNodeKind::regular, orientation_hint});
    refresh_connections_around(vertex_x, vertex_y);
    return true;
}

std::vector<FenceVertex> FenceManager::line_between(FenceVertex start, const FenceVertex end) const {
    std::vector<FenceVertex> result;
    result.push_back(start);
    while (start.x != end.x) {
        start.x += start.x < end.x ? 1 : -1;
        result.push_back(start);
    }
    while (start.y != end.y) {
        start.y += start.y < end.y ? 1 : -1;
        result.push_back(start);
    }
    return result;
}

int FenceManager::place_run(const std::vector<FenceVertex>& vertices,
                            const FenceRotation orientation_hint) {
    int placed = 0;
    for (const FenceVertex vertex : vertices) {
        if (place_node(vertex.x, vertex.y, orientation_hint)) ++placed;
    }
    return placed;
}

bool FenceManager::remove_node(const int vertex_x, const int vertex_y) {
    const auto found = node_indices_.find(vertex_key(vertex_x, vertex_y));
    if (found == node_indices_.end()) return false;

    const std::size_t index = found->second;
    const std::size_t last = nodes_.size() - 1;
    if (index != last) {
        nodes_[index] = nodes_[last];
        node_indices_[vertex_key(nodes_[index].vertex_x, nodes_[index].vertex_y)] = index;
    }
    nodes_.pop_back();
    node_indices_.erase(found);
    refresh_connections_around(vertex_x, vertex_y);
    return true;
}

void FenceManager::clear() {
    nodes_.clear();
    node_indices_.clear();
}

bool FenceManager::set_gate(const int vertex_x, const int vertex_y, const bool enabled) {
    const auto found = node_indices_.find(vertex_key(vertex_x, vertex_y));
    if (found == node_indices_.end()) return false;

    FenceNode& node = nodes_[found->second];
    if (!enabled) {
        node.kind = FenceNodeKind::regular;
        return true;
    }
    if (!can_resolve_gate(vertex_x, vertex_y)) return false;
    node.kind = FenceNodeKind::gate;
    return true;
}

bool FenceManager::can_resolve_gate(const int vertex_x, const int vertex_y) const {
    const FenceNode* node = node_at(vertex_x, vertex_y);
    return node != nullptr && std::popcount(node->connections) == 2 && is_opposite_pair(node->connections);
}

const std::vector<FenceNode>& FenceManager::nodes() const {
    return nodes_;
}

int FenceManager::vertex_key(const int vertex_x, const int vertex_y) const {
    const int span = map_max_ - map_min_ + 2;
    return (vertex_y - map_min_) * span + (vertex_x - map_min_);
}

void FenceManager::refresh_connections_around(const int vertex_x, const int vertex_y) {
    refresh_connections(vertex_x, vertex_y);
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        refresh_connections(vertex_x + offset.x, vertex_y + offset.y);
    }
}

void FenceManager::refresh_connections(const int vertex_x, const int vertex_y) {
    const auto found = node_indices_.find(vertex_key(vertex_x, vertex_y));
    if (found == node_indices_.end()) return;

    FenceConnection mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        if (has_fence(vertex_x + offset.x, vertex_y + offset.y)) {
            mask = static_cast<FenceConnection>(mask | connection_bit(direction));
        }
    }
    nodes_[found->second].connections = mask;

    // A former straight gate that becomes a corner/junction remains stored as
    // a gate request, but resolve_fence_visual deliberately falls back to the
    // topology piece until the node is straight again.
}
