#include "rail_construction_economy.h"

#include <cmath>
#include <iostream>

namespace {

[[nodiscard]] int fail(const char* message) {
    std::cerr << "rail construction economy regression failed: " << message << '\n';
    return 1;
}

}  // namespace

int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    if (!root) return fail("root creation");

    const RailPlacementCheckpoint before_straight = graph.checkpoint();
    const auto straight = graph.append_straight(*root, 4.0F);
    if (!straight || !straight->ok()) return fail("straight creation");

    const RailConstructionQuote straight_quote =
        RailConstructionEconomy::quote(graph, before_straight.edge_count);
    if (!straight_quote.valid || straight_quote.edge_count != 1U ||
        straight_quote.piece_count != 1U) {
        return fail("straight quote shape");
    }
    if (std::abs(straight_quote.route_length_world - 4.0) > 1.0e-3) {
        return fail("straight sampled length");
    }
    if (straight_quote.build_cost != 500) return fail("straight price");
    if (straight_quote.refund_value != 325) return fail("straight refund");

    const RailPlacementCheckpoint before_crossing = graph.checkpoint();
    const auto crossing = graph.append_crossing(straight->node, 4.0F);
    if (!crossing || !crossing->ok()) return fail("crossing creation");

    const RailConstructionQuote crossing_quote =
        RailConstructionEconomy::quote(graph, before_crossing.edge_count);
    if (!crossing_quote.valid || crossing_quote.edge_count != 2U ||
        crossing_quote.piece_count != 1U) {
        return fail("crossing must quote as one logical piece");
    }
    const RailPlacementEdge* primary = graph.edge(crossing->primary_edge);
    const RailPlacementEdge* secondary = graph.edge(crossing->secondary_edge);
    if (primary == nullptr || secondary == nullptr ||
        primary->piece_group != secondary->piece_group) {
        return fail("crossing piece grouping");
    }
    if (crossing_quote.build_cost <= straight_quote.build_cost) {
        return fail("crossing should cost more than equal-span straight");
    }

    if (!graph.rollback(before_crossing)) return fail("transaction rollback");
    if (graph.edges().size() != before_crossing.edge_count ||
        graph.nodes().size() != before_crossing.node_count) {
        return fail("rollback must remove whole crossing transaction");
    }

    RailConstructionPricing full_refund_pricing;
    full_refund_pricing.demolition_refund_percent = 100;
    if (RailConstructionEconomy::demolition_refund(500, full_refund_pricing) != 500) {
        return fail("full refund clamp");
    }

    std::cout << "rail construction economy regression ok"
              << " straight_cost=" << straight_quote.build_cost
              << " straight_refund=" << straight_quote.refund_value
              << " crossing_cost=" << crossing_quote.build_cost
              << '\n';
    return 0;
}
