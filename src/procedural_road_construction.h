#pragma once

#include "procedural_road_class.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>

// CH_PROCEDURAL_ROAD_CONSTRUCTION_V1
//
// Canonical construction presets for authored procedural roads. This is the
// single bridge between a player/editor road class choice and the geometry
// created in ProceduralRoadGraph. Traffic keeps reading the class catalog and
// does not duplicate width/lane/cost rules.
struct ProceduralRoadConstructionProfile {
    ProceduralRoadClass road_class = ProceduralRoadClass::local;
    float width = 0.72F;
    std::uint8_t lane_count = 2;
    int subdivisions = 24;
    float texture_repeat_world_units = 1.0F;
    std::int64_t build_cost_per_world_unit = 100;
};

[[nodiscard]] inline constexpr ProceduralRoadConstructionProfile procedural_road_construction_profile(
    const ProceduralRoadClass road_class) {
    switch (road_class) {
        case ProceduralRoadClass::local:
            return {ProceduralRoadClass::local, 0.72F, 2, 24, 1.0F, 100};
        case ProceduralRoadClass::collector:
            return {ProceduralRoadClass::collector, 0.94F, 2, 32, 1.0F, 160};
        case ProceduralRoadClass::arterial:
            return {ProceduralRoadClass::arterial, 1.32F, 4, 40, 1.0F, 260};
        case ProceduralRoadClass::unspecified:
            return {ProceduralRoadClass::local, 0.72F, 2, 24, 1.0F, 100};
    }
    return {ProceduralRoadClass::local, 0.72F, 2, 24, 1.0F, 100};
}

class ProceduralRoadConstructionBuilder {
public:
    [[nodiscard]] static std::optional<ProceduralRoadSegmentId> add_segment(
        ProceduralRoadGraph& graph,
        ProceduralRoadClassCatalog& classes,
        const ProceduralRoadNodeId start_node,
        const ProceduralRoadNodeId end_node,
        const ProceduralRoadClass road_class,
        const RoadWorldPoint3 start_handle = {1.0F, 0.0F, 0.0F},
        const RoadWorldPoint3 end_handle = {-1.0F, 0.0F, 0.0F}) {
        if (road_class == ProceduralRoadClass::unspecified) return std::nullopt;
        const ProceduralRoadConstructionProfile profile = procedural_road_construction_profile(road_class);
        const auto segment_id = graph.add_segment(
            start_node, end_node, start_handle, end_handle, profile.width, profile.lane_count);
        if (!segment_id) return std::nullopt;

        ProceduralRoadGraphSegment* segment = graph.segment(*segment_id);
        if (segment == nullptr || !classes.assign(graph, *segment_id, road_class)) {
            (void)graph.remove_segment(*segment_id);
            return std::nullopt;
        }
        segment->subdivisions = profile.subdivisions;
        segment->texture_repeat_world_units = profile.texture_repeat_world_units;
        return segment_id;
    }

    [[nodiscard]] static std::int64_t estimated_build_cost(
        const RoadWorldPoint3& start,
        const RoadWorldPoint3& end,
        const ProceduralRoadClass road_class) {
        const ProceduralRoadConstructionProfile profile = procedural_road_construction_profile(road_class);
        const double dx = static_cast<double>(end.x - start.x);
        const double dy = static_cast<double>(end.y - start.y);
        const double dz = static_cast<double>(end.z - start.z);
        const double length = std::sqrt(dx * dx + dy * dy + dz * dz);
        return static_cast<std::int64_t>(std::ceil(length * static_cast<double>(profile.build_cost_per_world_unit)));
    }
};
