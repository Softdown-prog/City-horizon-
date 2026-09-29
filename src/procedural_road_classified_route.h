#pragma once

#include "procedural_road_route_sampler.h"

#include <optional>
#include <vector>

// CH_PROCEDURAL_ROAD_CLASS_V1
//
// Decorates the canonical continuous route with class metadata from the stable
// segment-id catalog. Existing unclassified route sampling remains unchanged.
class ProceduralRoadClassifiedRouteSampler {
public:
    static void annotate(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadClassCatalog& classes,
        std::vector<ProceduralRoadRoutePoint>& sampled) {
        ProceduralRoadClass incoming_class = ProceduralRoadClass::unspecified;
        for (ProceduralRoadRoutePoint& point : sampled) {
            if (point.kind == ProceduralRoadRoutePointKind::lane &&
                point.segment_id != kInvalidProceduralRoadSegmentId) {
                incoming_class = classes.road_class(graph, point.segment_id);
                point.road_class = incoming_class;
                continue;
            }

            if (point.kind == ProceduralRoadRoutePointKind::junction_connector) {
                // A connector inherits the class of the approach that committed
                // to the junction. The outgoing lane updates class as soon as
                // the route leaves the connector.
                point.road_class = incoming_class;
            }
        }
    }

    [[nodiscard]] static std::optional<std::vector<ProceduralRoadRoutePoint>> sample_right_hand_route(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadRoute& route,
        const ProceduralRoadClassCatalog& classes,
        const float lane_offset,
        const int samples_per_segment = 24,
        const int samples_per_connector = 12) {
        auto sampled = ProceduralRoadRouteSampler::sample_right_hand_route(
            graph, route, lane_offset, samples_per_segment, samples_per_connector);
        if (!sampled) return std::nullopt;
        annotate(graph, classes, *sampled);
        return sampled;
    }
};
