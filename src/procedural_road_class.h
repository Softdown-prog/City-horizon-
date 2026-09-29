#pragma once

#include "road_system.h"

#include <algorithm>
#include <limits>
#include <string_view>
#include <unordered_map>

// CH_PROCEDURAL_ROAD_CLASS_V1
//
// Stable traffic metadata keyed by ProceduralRoadSegmentId. The graph geometry
// remains unchanged; class data is a parallel authored/runtime catalog so the
// existing graph ID and topology contract stays stable while class-aware traffic
// is proven.
enum class ProceduralRoadClass {
    unspecified,
    local,
    collector,
    arterial,
};

struct ProceduralRoadClassProfile {
    float speed_limit = std::numeric_limits<float>::infinity();
    int priority_rank = 0;
};

[[nodiscard]] inline constexpr ProceduralRoadClassProfile procedural_road_class_profile(
    const ProceduralRoadClass road_class) {
    switch (road_class) {
        case ProceduralRoadClass::local:
            return {1.35F, 1};
        case ProceduralRoadClass::collector:
            return {1.70F, 2};
        case ProceduralRoadClass::arterial:
            return {2.10F, 3};
        case ProceduralRoadClass::unspecified:
            return {std::numeric_limits<float>::infinity(), 0};
    }
    return {std::numeric_limits<float>::infinity(), 0};
}

[[nodiscard]] inline constexpr std::string_view procedural_road_class_name(
    const ProceduralRoadClass road_class) {
    switch (road_class) {
        case ProceduralRoadClass::local: return "local";
        case ProceduralRoadClass::collector: return "collector";
        case ProceduralRoadClass::arterial: return "arterial";
        case ProceduralRoadClass::unspecified: return "unspecified";
    }
    return "unspecified";
}

class ProceduralRoadClassCatalog {
public:
    [[nodiscard]] bool assign(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadSegmentId segment_id,
        const ProceduralRoadClass road_class) {
        if (segment_id == kInvalidProceduralRoadSegmentId || graph.segment(segment_id) == nullptr ||
            road_class == ProceduralRoadClass::unspecified) {
            return false;
        }
        classes_[segment_id] = road_class;
        return true;
    }

    [[nodiscard]] bool remove(const ProceduralRoadSegmentId segment_id) {
        return classes_.erase(segment_id) > 0U;
    }

    void clear() { classes_.clear(); }

    void set_default_class(const ProceduralRoadClass road_class) {
        default_class_ = road_class == ProceduralRoadClass::unspecified
            ? ProceduralRoadClass::local
            : road_class;
    }

    [[nodiscard]] ProceduralRoadClass default_class() const { return default_class_; }

    [[nodiscard]] ProceduralRoadClass road_class(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadSegmentId segment_id) const {
        if (segment_id == kInvalidProceduralRoadSegmentId || graph.segment(segment_id) == nullptr) {
            return ProceduralRoadClass::unspecified;
        }
        const auto found = classes_.find(segment_id);
        return found == classes_.end() ? default_class_ : found->second;
    }

    [[nodiscard]] bool has_explicit_class(const ProceduralRoadSegmentId segment_id) const {
        return classes_.contains(segment_id);
    }

private:
    ProceduralRoadClass default_class_ = ProceduralRoadClass::local;
    std::unordered_map<ProceduralRoadSegmentId, ProceduralRoadClass> classes_;
};
