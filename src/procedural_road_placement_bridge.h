#pragma once

#include "procedural_road_construction.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <unordered_map>
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
            result.segments.push_back(*segment_id);
            ++result.created_segments;
        }

        return result;
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
        return true;
    }

    void clear() {
        graph_.clear();
        classes_.clear();
        node_by_key_.clear();
        segment_by_edge_.clear();
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

    [[nodiscard]] static std::int32_t elevation_key(const float elevation) {
        return static_cast<std::int32_t>(std::lround(static_cast<double>(elevation) * 1000.0));
    }

    [[nodiscard]] static EdgeKey normalized_edge(
        const ProceduralRoadNodeId a,
        const ProceduralRoadNodeId b) {
        return a < b ? EdgeKey{a, b} : EdgeKey{b, a};
    }

    ProceduralRoadGraph graph_;
    ProceduralRoadClassCatalog classes_;
    std::unordered_map<NodeKey, ProceduralRoadNodeId, NodeKeyHash> node_by_key_;
    std::unordered_map<EdgeKey, ProceduralRoadSegmentId, EdgeKeyHash> segment_by_edge_;
};
