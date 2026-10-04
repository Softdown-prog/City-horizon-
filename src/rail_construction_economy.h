#pragma once

#include "rail_placement_graph.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <unordered_map>

inline constexpr const char* kChRailConstructionEconomyContract = "CH_RAIL_CONSTRUCTION_ECONOMY_V2";

// City Horizon-owned railway pricing. The quote is derived only from our
// procedural geometry and logical piece grouping, so preview and execution can
// share one deterministic calculation without mutating the city economy.
struct RailConstructionPricing {
    std::int64_t base_cost_per_world_unit = 125;
    std::int32_t straight_percent = 100;
    std::int32_t curve_percent = 120;
    std::int32_t turnout_percent = 135;
    std::int32_t crossing_percent = 120;
    std::int32_t demolition_refund_percent = 65;
};

struct RailConstructionQuote {
    std::int64_t build_cost = 0;
    std::int64_t refund_value = 0;
    double route_length_world = 0.0;
    std::size_t edge_count = 0U;
    std::size_t piece_count = 0U;
    bool valid = false;
};

class RailConstructionEconomy final {
public:
    [[nodiscard]] static RailConstructionQuote quote(
        const RailPlacementGraph& graph,
        const std::size_t first_edge,
        const RailConstructionPricing& pricing = {}) {
        RailConstructionQuote result;
        const auto& edges = graph.edges();
        if (first_edge > edges.size() || pricing.base_cost_per_world_unit <= 0 ||
            pricing.demolition_refund_percent < 0 || pricing.demolition_refund_percent > 100) {
            return result;
        }
        if (first_edge == edges.size()) return result;

        struct PieceAccumulator {
            double route_length = 0.0;
            std::int32_t multiplier_percent = 0;
        };
        std::unordered_map<RailPlacementPieceId, PieceAccumulator> pieces;

        for (std::size_t index = first_edge; index < edges.size(); ++index) {
            const RailPlacementEdge& edge = edges[index];
            // A deleted historical slot must never contribute to a later quote.
            // Preview edges are always appended active after the checkpoint.
            if (!edge.active) continue;
            if (edge.piece_group == kInvalidRailPlacementPieceId) return {};
            const double length = sampled_length(edge.segment);
            if (!std::isfinite(length) || length <= 0.0) return {};

            PieceAccumulator& piece = pieces[edge.piece_group];
            piece.route_length += length;
            piece.multiplier_percent = std::max(
                piece.multiplier_percent,
                multiplier_for(edge.kind, pricing));
            result.route_length_world += length;
            ++result.edge_count;
        }

        long double total_cost = 0.0L;
        for (const auto& [piece_id, piece] : pieces) {
            (void)piece_id;
            if (!std::isfinite(piece.route_length) || piece.route_length <= 0.0 ||
                piece.multiplier_percent <= 0) {
                return {};
            }
            total_cost += std::ceil(
                static_cast<long double>(piece.route_length) *
                static_cast<long double>(pricing.base_cost_per_world_unit) *
                static_cast<long double>(piece.multiplier_percent) / 100.0L);
        }

        if (total_cost <= 0.0L ||
            total_cost > static_cast<long double>(std::numeric_limits<std::int64_t>::max())) {
            return {};
        }

        result.build_cost = static_cast<std::int64_t>(total_cost);
        result.refund_value = demolition_refund(result.build_cost, pricing);
        result.piece_count = pieces.size();
        result.valid = result.edge_count > 0U && result.piece_count > 0U;
        return result;
    }

    [[nodiscard]] static std::int64_t demolition_refund(
        const std::int64_t paid_cost,
        const RailConstructionPricing& pricing = {}) {
        if (paid_cost <= 0 || pricing.demolition_refund_percent <= 0) return 0;
        if (pricing.demolition_refund_percent >= 100) return paid_cost;
        return paid_cost * static_cast<std::int64_t>(pricing.demolition_refund_percent) / 100;
    }

private:
    [[nodiscard]] static std::int32_t multiplier_for(
        const RailPlacementEdgeKind kind,
        const RailConstructionPricing& pricing) {
        switch (kind) {
            case RailPlacementEdgeKind::straight:
                return pricing.straight_percent;
            case RailPlacementEdgeKind::curve:
                return pricing.curve_percent;
            case RailPlacementEdgeKind::turnout_through:
            case RailPlacementEdgeKind::turnout_diverging:
                return pricing.turnout_percent;
            case RailPlacementEdgeKind::crossing_primary:
            case RailPlacementEdgeKind::crossing_secondary:
                return pricing.crossing_percent;
        }
        return 0;
    }

    [[nodiscard]] static double sampled_length(const RailSplineSegment& segment) {
        const int samples = std::clamp(segment.subdivisions, 8, 96);
        RailWorldPoint3 previous = RailMeshBuilder::sample_cubic(segment, 0.0F);
        double length = 0.0;
        for (int index = 1; index <= samples; ++index) {
            const float t = static_cast<float>(index) / static_cast<float>(samples);
            const RailWorldPoint3 current = RailMeshBuilder::sample_cubic(segment, t);
            const double dx = static_cast<double>(current.x - previous.x);
            const double dy = static_cast<double>(current.y - previous.y);
            const double dz = static_cast<double>(current.z - previous.z);
            const double step = std::sqrt(dx * dx + dy * dy + dz * dz);
            if (!std::isfinite(step)) return std::numeric_limits<double>::quiet_NaN();
            length += step;
            previous = current;
        }
        return length;
    }
};
