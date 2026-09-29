#pragma once

#include "road_system.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

// CH_PROCEDURAL_ROAD_JUNCTION_V1
//
// This first junction layer fills the central pavement shared by graph segments.
// It deliberately consumes explicit graph topology: geometric XY crossings are
// not junctions unless the segments share a ProceduralRoadNodeId.
enum class ProceduralRoadJunctionKind {
    invalid,
    isolated,
    end,
    continuation,
    tee,
    intersection,
    complex,
};

class RoadJunctionBuilder {
public:
    [[nodiscard]] static ProceduralRoadJunctionKind classify(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadNodeId node_id) {
        if (graph.node(node_id) == nullptr) return ProceduralRoadJunctionKind::invalid;
        switch (graph.degree(node_id)) {
            case 0U: return ProceduralRoadJunctionKind::isolated;
            case 1U: return ProceduralRoadJunctionKind::end;
            case 2U: return ProceduralRoadJunctionKind::continuation;
            case 3U: return ProceduralRoadJunctionKind::tee;
            case 4U: return ProceduralRoadJunctionKind::intersection;
            default: return ProceduralRoadJunctionKind::complex;
        }
    }

    // Builds one flat central pavement patch at the node elevation. Segment
    // ribbons still own the approaches. The patch extends a short distance down
    // every incident arm so antialiasing/subpixel sampling cannot expose a hole
    // between independently generated road ribbons.
    [[nodiscard]] static RoadMesh build_patch(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadNodeId node_id) {
        RoadMesh mesh;
        const ProceduralRoadNode* junction = graph.node(node_id);
        if (junction == nullptr || graph.degree(node_id) < 2U) return mesh;

        struct BoundaryPoint {
            RoadWorldPoint3 position{};
            float angle = 0.0F;
        };
        std::vector<BoundaryPoint> boundary;

        const std::vector<ProceduralRoadSegmentId> incident = graph.connected_segments(node_id);
        boundary.reserve(incident.size() * 2U);

        float uv_radius = 0.5F;
        for (const ProceduralRoadSegmentId segment_id : incident) {
            const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
            if (segment == nullptr) continue;

            RoadWorldPoint3 direction{};
            const ProceduralRoadNode* other = nullptr;
            if (segment->start_node == node_id) {
                direction = segment->start_handle;
                other = graph.node(segment->end_node);
            } else if (segment->end_node == node_id) {
                // end_handle points from the endpoint back toward control_b,
                // which is exactly the direction from this junction into the arm.
                direction = segment->end_handle;
                other = graph.node(segment->start_node);
            } else {
                continue;
            }

            float length = std::sqrt(direction.x * direction.x + direction.y * direction.y);
            if (length < 0.00001F && other != nullptr) {
                direction.x = other->position.x - junction->position.x;
                direction.y = other->position.y - junction->position.y;
                length = std::sqrt(direction.x * direction.x + direction.y * direction.y);
            }
            if (length < 0.00001F) continue;

            const float tangent_x = direction.x / length;
            const float tangent_y = direction.y / length;
            const float normal_x = -tangent_y;
            const float normal_y = tangent_x;
            const float half_width = std::max(0.01F, segment->width * 0.5F);
            const float reach = std::max(0.25F, segment->width * 0.75F);
            uv_radius = std::max(uv_radius, reach + half_width);

            const float center_x = junction->position.x + tangent_x * reach;
            const float center_y = junction->position.y + tangent_y * reach;
            const RoadWorldPoint3 left{
                center_x + normal_x * half_width,
                center_y + normal_y * half_width,
                junction->position.z,
            };
            const RoadWorldPoint3 right{
                center_x - normal_x * half_width,
                center_y - normal_y * half_width,
                junction->position.z,
            };
            boundary.push_back({left, std::atan2(left.y - junction->position.y,
                                                 left.x - junction->position.x)});
            boundary.push_back({right, std::atan2(right.y - junction->position.y,
                                                  right.x - junction->position.x)});
        }

        if (boundary.size() < 3U) return mesh;
        std::sort(boundary.begin(), boundary.end(), [](const BoundaryPoint& left, const BoundaryPoint& right) {
            return left.angle < right.angle;
        });

        // Triangle fan: vertex 0 is the graph node, boundary vertices follow in
        // angular order. Planar world-space UVs keep the junction compatible
        // with a future asphalt texture without requiring a special atlas tile.
        mesh.vertices.reserve(boundary.size() + 1U);
        mesh.indices.reserve(boundary.size() * 3U);
        mesh.vertices.push_back({junction->position, 0.5F, 0.5F});
        for (const BoundaryPoint& point : boundary) {
            const float u = 0.5F + (point.position.x - junction->position.x) / (2.0F * uv_radius);
            const float v = 0.5F + (point.position.y - junction->position.y) / (2.0F * uv_radius);
            mesh.vertices.push_back({point.position, u, v});
        }

        for (std::size_t index = 0; index < boundary.size(); ++index) {
            const std::uint32_t current = static_cast<std::uint32_t>(index + 1U);
            const std::uint32_t next = static_cast<std::uint32_t>(((index + 1U) % boundary.size()) + 1U);
            mesh.indices.push_back(0U);
            mesh.indices.push_back(current);
            mesh.indices.push_back(next);
        }
        return mesh;
    }
};
