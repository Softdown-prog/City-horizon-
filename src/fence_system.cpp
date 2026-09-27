#include "fence_system.h"

#include <algorithm>
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

[[nodiscard]] constexpr bool adjacent_vertices(const FenceVertex a, const FenceVertex b) {
    const int dx = a.x - b.x;
    const int dy = a.y - b.y;
    return (dx == 0 && (dy == 1 || dy == -1)) ||
           (dy == 0 && (dx == 1 || dx == -1));
}

[[nodiscard]] constexpr std::pair<FenceVertex, FenceVertex> tile_crossing_segment(
    const int tile_x, const int tile_y, const CardinalDirection direction) {
    switch (direction) {
        case CardinalDirection::north:
            return {{tile_x, tile_y}, {tile_x + 1, tile_y}};
        case CardinalDirection::east:
            return {{tile_x + 1, tile_y}, {tile_x + 1, tile_y + 1}};
        case CardinalDirection::south:
            return {{tile_x, tile_y + 1}, {tile_x + 1, tile_y + 1}};
        case CardinalDirection::west:
            return {{tile_x, tile_y}, {tile_x, tile_y + 1}};
    }
    return {};
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

    if (neighbors == 0) return {FenceVisualType::isolated, orientation_hint, mask};
    if (neighbors == 1) return {FenceVisualType::end, end_rotation(mask, orientation_hint), mask};
    if (neighbors == 2) {
        if (is_opposite_pair(mask)) return {FenceVisualType::straight, straight_rotation(mask, orientation_hint), mask};
        return {FenceVisualType::corner, corner_rotation(mask, orientation_hint), mask};
    }
    if (neighbors == 3) return {FenceVisualType::tee, tee_rotation(mask, orientation_hint), mask};
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

    const FenceVertex removed{vertex_x, vertex_y};
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        const FenceVertex neighbour{vertex_x + offset.x, vertex_y + offset.y};
        open_gate_segments_.erase(segment_key(removed, neighbour));
    }

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
    open_gate_segments_.clear();
}

bool FenceManager::has_segment(const FenceVertex from, const FenceVertex to) const {
    if (!adjacent_vertices(from, to) || !has_fence(from.x, from.y) || !has_fence(to.x, to.y)) return false;
    const FenceNode* node = node_at(from.x, from.y);
    if (node == nullptr) return false;
    if (to.x == from.x + 1) return has_connection(node->connections, CardinalDirection::east);
    if (to.x == from.x - 1) return has_connection(node->connections, CardinalDirection::west);
    if (to.y == from.y + 1) return has_connection(node->connections, CardinalDirection::south);
    return has_connection(node->connections, CardinalDirection::north);
}

bool FenceManager::set_open_gate(const FenceVertex from, const FenceVertex to, const bool enabled) {
    if (!has_segment(from, to)) return false;
    const std::uint64_t key = segment_key(from, to);
    if (enabled) open_gate_segments_.insert(key);
    else open_gate_segments_.erase(key);
    return true;
}

bool FenceManager::is_open_gate(const FenceVertex from, const FenceVertex to) const {
    return has_segment(from, to) && open_gate_segments_.contains(segment_key(from, to));
}

std::vector<FenceSegment> FenceManager::segments() const {
    std::vector<FenceSegment> result;
    result.reserve(nodes_.size() * 2U);
    for (const FenceNode& node : nodes_) {
        const FenceVertex from{node.vertex_x, node.vertex_y};
        if (has_connection(node.connections, CardinalDirection::east)) {
            const FenceVertex to{node.vertex_x + 1, node.vertex_y};
            result.push_back({from, to, is_open_gate(from, to)});
        }
        if (has_connection(node.connections, CardinalDirection::south)) {
            const FenceVertex to{node.vertex_x, node.vertex_y + 1};
            result.push_back({from, to, is_open_gate(from, to)});
        }
    }
    return result;
}

bool FenceManager::blocks_tile_crossing(const int tile_x, const int tile_y,
                                        const CardinalDirection direction) const {
    const auto [from, to] = tile_crossing_segment(tile_x, tile_y, direction);
    return has_segment(from, to) && !is_open_gate(from, to);
}

bool FenceManager::is_open_gate_crossing(const int tile_x, const int tile_y,
                                         const CardinalDirection direction) const {
    const auto [from, to] = tile_crossing_segment(tile_x, tile_y, direction);
    return is_open_gate(from, to);
}

std::optional<FenceGateCrossing> FenceManager::open_gate_crossing(
    FenceVertex from, FenceVertex to) const {
    if (!is_open_gate(from, to)) return std::nullopt;

    if (from.y == to.y) {
        const int x = std::min(from.x, to.x);
        const int y = from.y;
        return FenceGateCrossing{{x, y - 1}, {x, y}};
    }
    if (from.x == to.x) {
        const int x = from.x;
        const int y = std::min(from.y, to.y);
        return FenceGateCrossing{{x - 1, y}, {x, y}};
    }
    return std::nullopt;
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

std::uint64_t FenceManager::segment_key(const FenceVertex from, const FenceVertex to) const {
    const auto from_key = static_cast<std::uint32_t>(vertex_key(from.x, from.y));
    const auto to_key = static_cast<std::uint32_t>(vertex_key(to.x, to.y));
    const std::uint32_t low = std::min(from_key, to_key);
    const std::uint32_t high = std::max(from_key, to_key);
    return (static_cast<std::uint64_t>(low) << 32U) | high;
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
}
