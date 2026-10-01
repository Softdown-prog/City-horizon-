#pragma once

#include "procedural_road_construction.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

// CH_PROCEDURAL_ROAD_PLACEMENT_BRIDGE_V1
//
// Mirrors an already-accepted legacy tile-road placement into the procedural
// road graph while RoadManager remains gameplay/save authority. Every occupied
// tile center becomes an explicit graph node in V1. This deliberately favors
// exact legacy topology and deterministic junction reuse over graph compression.
// Elevation participates in the node key, so coincident XY roads at different
// heights remain disconnected unless a future authoring operation explicitly
// joins them.
struct ProceduralRoadPlacementResult {
    std::vector<ProceduralRoadNodeId> nodes;
    std::vector<ProceduralRoadSegmentId> segments;
    std::size_t created_nodes = 0U;
    std::size_t reused_nodes = 0U;
    std::size_t created_segments = 0U;
    std::size_t reused_segments = 0U;

    [[nodiscard]] bool empty() const { return nodes.empty(); }
};

class ProceduralRoadPlacementBridge {
public:
    ProceduralRoadPlacementBridge() = default;

    // CH_PROCEDURAL_ROAD_SPATIAL_INDEX_V1
    //
    // Runtime visibility queries use a coarse 16x16-world-unit index owned by
    // the mirror itself. Save/load and gameplay remain tile-authoritative; this
    // is only an acceleration structure and can always be rebuilt from graph_.
    static constexpr float kSpatialChunkWorldSize = 16.0F;

    [[nodiscard]] std::optional<ProceduralRoadPlacementResult> mirror_tile_segment(
        const std::vector<TileCoordinate>& tiles,
        const ProceduralRoadClass road_class,
        const float elevation = 0.0F) {
        if (tiles.empty() || road_class == ProceduralRoadClass::unspecified || !std::isfinite(elevation)) {
            return std::nullopt;
        }
        for (std::size_t index = 1U; index < tiles.size(); ++index) {
            const int dx = std::abs(tiles[index].x - tiles[index - 1U].x);
            const int dy = std::abs(tiles[index].y - tiles[index - 1U].y);
            if (dx + dy != 1) return std::nullopt;
        }

        ProceduralRoadPlacementResult result;
        result.nodes.reserve(tiles.size());
        if (tiles.size() > 1U) result.segments.reserve(tiles.size() - 1U);

        for (const TileCoordinate tile : tiles) {
            const NodeKey key{tile.x, tile.y, elevation_key(elevation)};
            const auto found = node_by_key_.find(key);
            if (found != node_by_key_.end()) {
                result.nodes.push_back(found->second);
                ++result.reused_nodes;
                continue;
            }

            const ProceduralRoadNodeId node_id = graph_.add_node({
                static_cast<float>(tile.x) + 0.5F,
                static_cast<float>(tile.y) + 0.5F,
                elevation,
            });
            node_by_key_.emplace(key, node_id);
            index_spatial_node(node_id);
            result.nodes.push_back(node_id);
            ++result.created_nodes;
        }

        for (std::size_t index = 1U; index < result.nodes.size(); ++index) {
            const ProceduralRoadNodeId a = result.nodes[index - 1U];
            const ProceduralRoadNodeId b = result.nodes[index];
            const EdgeKey edge = normalized_edge(a, b);
            const auto found = segment_by_edge_.find(edge);
            if (found != segment_by_edge_.end()) {
                result.segments.push_back(found->second);
                ++result.reused_segments;
                continue;
            }

            const ProceduralRoadNode* start = graph_.node(a);
            const ProceduralRoadNode* end = graph_.node(b);
            if (start == nullptr || end == nullptr) return std::nullopt;

            const RoadWorldPoint3 delta{
                end->position.x - start->position.x,
                end->position.y - start->position.y,
                end->position.z - start->position.z,
            };
            const RoadWorldPoint3 start_handle{delta.x / 3.0F, delta.y / 3.0F, delta.z / 3.0F};
            const RoadWorldPoint3 end_handle{-delta.x / 3.0F, -delta.y / 3.0F, -delta.z / 3.0F};
            const auto segment_id = ProceduralRoadConstructionBuilder::add_segment(
                graph_, classes_, a, b, road_class, start_handle, end_handle);
            if (!segment_id) return std::nullopt;

            segment_by_edge_.emplace(edge, *segment_id);
            index_spatial_segment(*segment_id);
            result.segments.push_back(*segment_id);
            ++result.created_segments;
        }

        return result;
    }

    // Rebuild is the safe synchronization primitive for load and demolition
    // while legacy RoadManager remains authoritative. Only E/S neighbors are
    // emitted after all nodes exist, so every logical adjacency becomes one
    // undirected procedural edge exactly once.
    [[nodiscard]] bool rebuild_from_legacy_tiles(
        const std::vector<RoadTile>& tiles,
        const ProceduralRoadClass road_class = ProceduralRoadClass::local,
        const float elevation = 0.0F) {
        if (road_class == ProceduralRoadClass::unspecified || !std::isfinite(elevation)) return false;

        clear();
        if (tiles.empty()) return true;

        std::unordered_set<std::uint64_t> occupied;
        occupied.reserve(tiles.size() * 2U);
        for (const RoadTile& tile : tiles) {
            occupied.insert(tile_key(tile.tile_x, tile.tile_y));
            if (!mirror_tile_segment({TileCoordinate{tile.tile_x, tile.tile_y}}, road_class, elevation)) {
                clear();
                return false;
            }
        }

        for (const RoadTile& tile : tiles) {
            for (const TileCoordinate neighbor : {
                     TileCoordinate{tile.tile_x + 1, tile.tile_y},
                     TileCoordinate{tile.tile_x, tile.tile_y + 1}}) {
                if (!occupied.contains(tile_key(neighbor.x, neighbor.y))) continue;
                if (!mirror_tile_segment(
                        {TileCoordinate{tile.tile_x, tile.tile_y}, neighbor}, road_class, elevation)) {
                    clear();
                    return false;
                }
            }
        }
        return true;
    }

    [[nodiscard]] bool set_existing_edge_class(
        const ProceduralRoadSegmentId segment_id,
        const ProceduralRoadClass road_class) {
        if (road_class == ProceduralRoadClass::unspecified || graph_.segment(segment_id) == nullptr) return false;
        if (!classes_.assign(graph_, segment_id, road_class)) return false;
        const ProceduralRoadConstructionProfile profile = procedural_road_construction_profile(road_class);
        ProceduralRoadGraphSegment* segment = graph_.segment(segment_id);
        segment->width = profile.width;
        segment->lane_count = profile.lane_count;
        segment->subdivisions = profile.subdivisions;
        segment->texture_repeat_world_units = profile.texture_repeat_world_units;
        // Width participates in the conservative chunk envelope. Class changes
        // are rare editor/gameplay mutations, so rebuild here keeps runtime
        // queries exact without adding per-frame validation cost.
        rebuild_spatial_index();
        return true;
    }

    [[nodiscard]] std::vector<ProceduralRoadNodeId> spatial_nodes_in_bounds(
        const float min_x,
        const float min_y,
        const float max_x,
        const float max_y) const {
        return query_spatial_index(node_spatial_chunks_, min_x, min_y, max_x, max_y);
    }

    [[nodiscard]] std::vector<ProceduralRoadSegmentId> spatial_segments_in_bounds(
        const float min_x,
        const float min_y,
        const float max_x,
        const float max_y) const {
        return query_spatial_index(segment_spatial_chunks_, min_x, min_y, max_x, max_y);
    }

    // Explicit recovery hook for editor-only code that mutates graph() directly.
    // RoadManager's production mirror does not require this because its changes
    // flow through mirror_tile_segment/rebuild_from_legacy_tiles.
    void rebuild_spatial_index() {
        node_spatial_chunks_.clear();
        segment_spatial_chunks_.clear();
        for (const ProceduralRoadNode& node : graph_.nodes()) index_spatial_node(node.id);
        for (const ProceduralRoadGraphSegment& segment : graph_.segments()) index_spatial_segment(segment.id);
    }

    void clear() {
        graph_.clear();
        classes_.clear();
        node_by_key_.clear();
        segment_by_edge_.clear();
        node_spatial_chunks_.clear();
        segment_spatial_chunks_.clear();
    }

    [[nodiscard]] const ProceduralRoadGraph& graph() const { return graph_; }
    [[nodiscard]] ProceduralRoadGraph& graph() { return graph_; }
    [[nodiscard]] const ProceduralRoadClassCatalog& classes() const { return classes_; }
    [[nodiscard]] ProceduralRoadClassCatalog& classes() { return classes_; }

private:
    struct NodeKey {
        int x = 0;
        int y = 0;
        std::int32_t elevation = 0;

        [[nodiscard]] bool operator==(const NodeKey&) const = default;
    };

    struct NodeKeyHash {
        [[nodiscard]] std::size_t operator()(const NodeKey& key) const noexcept {
            std::size_t seed = static_cast<std::size_t>(static_cast<std::uint32_t>(key.x));
            seed ^= static_cast<std::size_t>(static_cast<std::uint32_t>(key.y)) + 0x9e3779b9U + (seed << 6U) + (seed >> 2U);
            seed ^= static_cast<std::size_t>(static_cast<std::uint32_t>(key.elevation)) + 0x9e3779b9U + (seed << 6U) + (seed >> 2U);
            return seed;
        }
    };

    struct EdgeKey {
        ProceduralRoadNodeId a = kInvalidProceduralRoadNodeId;
        ProceduralRoadNodeId b = kInvalidProceduralRoadNodeId;

        [[nodiscard]] bool operator==(const EdgeKey&) const = default;
    };

    struct EdgeKeyHash {
        [[nodiscard]] std::size_t operator()(const EdgeKey& key) const noexcept {
            std::size_t seed = static_cast<std::size_t>(key.a);
            seed ^= static_cast<std::size_t>(key.b) + 0x9e3779b97f4a7c15ULL + (seed << 6U) + (seed >> 2U);
            return seed;
        }
    };

    struct SpatialChunkKey {
        int x = 0;
        int y = 0;

        [[nodiscard]] bool operator==(const SpatialChunkKey&) const = default;
    };

    struct SpatialChunkKeyHash {
        [[nodiscard]] std::size_t operator()(const SpatialChunkKey& key) const noexcept {
            std::size_t seed = static_cast<std::size_t>(static_cast<std::uint32_t>(key.x));
            seed ^= static_cast<std::size_t>(static_cast<std::uint32_t>(key.y)) +
                    0x9e3779b97f4a7c15ULL + (seed << 6U) + (seed >> 2U);
            return seed;
        }
    };

    template <typename Id>
    using SpatialIndex = std::unordered_map<SpatialChunkKey, std::vector<Id>, SpatialChunkKeyHash>;

    [[nodiscard]] static std::int32_t elevation_key(const float elevation) {
        return static_cast<std::int32_t>(std::lround(static_cast<double>(elevation) * 1000.0));
    }

    [[nodiscard]] static EdgeKey normalized_edge(
        const ProceduralRoadNodeId a,
        const ProceduralRoadNodeId b) {
        return a < b ? EdgeKey{a, b} : EdgeKey{b, a};
    }

    [[nodiscard]] static std::uint64_t tile_key(const int x, const int y) {
        return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32U) |
               static_cast<std::uint64_t>(static_cast<std::uint32_t>(y));
    }

    [[nodiscard]] static int spatial_chunk_coord(const float value) {
        return static_cast<int>(std::floor(value / kSpatialChunkWorldSize));
    }

    template <typename Id>
    [[nodiscard]] static std::vector<Id> query_spatial_index(
        const SpatialIndex<Id>& index,
        const float min_x,
        const float min_y,
        const float max_x,
        const float max_y) {
        std::vector<Id> result;
        if (!std::isfinite(min_x) || !std::isfinite(min_y) ||
            !std::isfinite(max_x) || !std::isfinite(max_y) ||
            min_x > max_x || min_y > max_y) {
            return result;
        }

        const int min_chunk_x = spatial_chunk_coord(min_x);
        const int max_chunk_x = spatial_chunk_coord(max_x);
        const int min_chunk_y = spatial_chunk_coord(min_y);
        const int max_chunk_y = spatial_chunk_coord(max_y);
        std::unordered_set<Id> seen;

        for (int chunk_y = min_chunk_y; chunk_y <= max_chunk_y; ++chunk_y) {
            for (int chunk_x = min_chunk_x; chunk_x <= max_chunk_x; ++chunk_x) {
                const auto found = index.find({chunk_x, chunk_y});
                if (found == index.end()) continue;
                for (const Id id : found->second) {
                    if (seen.insert(id).second) result.push_back(id);
                }
            }
        }
        return result;
    }

    void index_spatial_node(const ProceduralRoadNodeId node_id) {
        const ProceduralRoadNode* node = graph_.node(node_id);
        if (node == nullptr) return;
        node_spatial_chunks_[{
            spatial_chunk_coord(node->position.x),
            spatial_chunk_coord(node->position.y),
        }].push_back(node_id);
    }

    void index_spatial_segment(const ProceduralRoadSegmentId segment_id) {
        const ProceduralRoadGraphSegment* segment = graph_.segment(segment_id);
        if (segment == nullptr) return;
        const ProceduralRoadNode* start = graph_.node(segment->start_node);
        const ProceduralRoadNode* end = graph_.node(segment->end_node);
        if (start == nullptr || end == nullptr) return;

        const float dx = end->position.x - start->position.x;
        const float dy = end->position.y - start->position.y;
        const float length = std::sqrt(dx * dx + dy * dy);
        // Visual corner smoothing can move a control handle by ~0.46 of the
        // incident edge length. Half an edge plus road half-width and a small
        // guard keeps the coarse index conservative before exact spline culling.
        const float guard = std::max(1.0F, length * 0.5F + segment->width * 0.5F + 0.25F);
        const float min_x = std::min(start->position.x, end->position.x) - guard;
        const float max_x = std::max(start->position.x, end->position.x) + guard;
        const float min_y = std::min(start->position.y, end->position.y) - guard;
        const float max_y = std::max(start->position.y, end->position.y) + guard;

        const int min_chunk_x = spatial_chunk_coord(min_x);
        const int max_chunk_x = spatial_chunk_coord(max_x);
        const int min_chunk_y = spatial_chunk_coord(min_y);
        const int max_chunk_y = spatial_chunk_coord(max_y);
        for (int chunk_y = min_chunk_y; chunk_y <= max_chunk_y; ++chunk_y) {
            for (int chunk_x = min_chunk_x; chunk_x <= max_chunk_x; ++chunk_x) {
                segment_spatial_chunks_[{chunk_x, chunk_y}].push_back(segment_id);
            }
        }
    }

    ProceduralRoadGraph graph_;
    ProceduralRoadClassCatalog classes_;
    std::unordered_map<NodeKey, ProceduralRoadNodeId, NodeKeyHash> node_by_key_;
    std::unordered_map<EdgeKey, ProceduralRoadSegmentId, EdgeKeyHash> segment_by_edge_;
    SpatialIndex<ProceduralRoadNodeId> node_spatial_chunks_;
    SpatialIndex<ProceduralRoadSegmentId> segment_spatial_chunks_;
};
