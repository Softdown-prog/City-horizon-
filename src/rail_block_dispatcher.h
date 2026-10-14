#pragma once

#include "rail_operation_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <unordered_map>
#include <unordered_set>

// CH_RAIL_BLOCK_DISPATCHER_V1
// Per-piece movement authority. Each train acquires, in one transaction, the
// physical rail pieces under its full consist and a forward safety margin.
// Leases are released behind the last coach only AFTER a successful advance.
// This deliberately does not authorize two trains on the same named route:
// route/path conflict validation and siding/shunt interlocking are separate.
namespace ch::rail_dispatch {
using BlockId = ch::track::PieceInstanceId;
using TrainId = std::uint8_t;

class BlockDispatcher final {
public:
    static constexpr double kLocomotiveLengthM = 5.2;
    static constexpr double kCoachPitchM = 3.9 + 0.42;
    static constexpr double kTailMarginM = 2.0;
    static constexpr double kLookAheadM = 12.0;

    [[nodiscard]] static double consist_length_m(const std::uint32_t coaches) noexcept {
        return kLocomotiveLengthM + static_cast<double>(coaches) * kCoachPitchM;
    }

    [[nodiscard]] bool acquire(const TrainId train,
                               const rail_operation::OperationalRoute& route,
                               const double lead_distance_m,
                               const std::uint32_t coaches,
                               const double lookahead_m = kLookAheadM) {
        if (train == 0U || !route.valid || route.graph_route.steps.empty() ||
            !(route.length_m > 0.0) || !std::isfinite(lead_distance_m) ||
            lead_distance_m < 0.0 || lead_distance_m > route.length_m + 0.1 ||
            coaches > 7U || !std::isfinite(lookahead_m) || lookahead_m < 0.0)
            return false;
        const double rear = std::max(0.0, lead_distance_m -
            consist_length_m(coaches) - kTailMarginM);
        const double ahead = std::min(route.length_m, lead_distance_m + lookahead_m);
        return acquire_range(train, route, rear, ahead);
    }

    // During locomotive decoupling and return, the main line cannot be
    // partially released: the parked coaches and detached engine must stay
    // protected until the maneuver is over.
    [[nodiscard]] bool acquire_entire_route(
        const TrainId train, const rail_operation::OperationalRoute& route) {
        if (train == 0U || !route.valid || route.graph_route.steps.empty()) return false;
        return acquire_range(train, route, 0.0, route.length_m);
    }

    void release(const TrainId train) {
        for (auto it = owners_.begin(); it != owners_.end();) {
            if (it->second == train) it = owners_.erase(it);
            else ++it;
        }
    }

    void clear() noexcept { owners_.clear(); }

    [[nodiscard]] bool owned_by(const TrainId train, const BlockId block) const {
        const auto it = owners_.find(block);
        return train != 0U && it != owners_.end() && it->second == train;
    }

    [[nodiscard]] bool reserved(const BlockId block) const {
        return owners_.contains(block);
    }

    [[nodiscard]] std::size_t reserved_count(const TrainId train) const {
        std::size_t count = 0U;
        for (const auto& item : owners_) if (item.second == train) ++count;
        return count;
    }

private:
    [[nodiscard]] bool acquire_range(const TrainId train,
                                     const rail_operation::OperationalRoute& route,
                                     const double rear, const double ahead) {
        if (!std::isfinite(rear) || !std::isfinite(ahead) || rear < 0.0 ||
            ahead < rear || ahead > route.length_m + 0.1) return false;

        std::unordered_set<BlockId> wanted;
        double cursor = 0.0;
        for (const auto& step : route.graph_route.steps) {
            const auto* piece = route.topology.piece(step.piece);
            if (piece == nullptr || step.route >= piece->descriptor.routes.size()) return false;
            const double length = rail_operation::detail::route_length(
                piece->descriptor.routes[step.route]);
            if (!(length > 0.0) || !std::isfinite(length)) return false;
            // Touching either boundary conservatively reserves both sections.
            if (cursor <= ahead + 1e-6 && cursor + length >= rear - 1e-6)
                wanted.insert(step.piece);
            cursor += length;
        }
        if (wanted.empty() || !std::isfinite(cursor) ||
            std::abs(cursor - route.length_m) > std::max(1.0, route.length_m * 0.02))
            return false;

        // Check ALL requested blocks before changing any lease.
        for (const auto piece : wanted) {
            const auto found = owners_.find(piece);
            if (found != owners_.end() && found->second != train) return false;
        }
        // Only now release the blocks behind the last carriage.
        for (auto it = owners_.begin(); it != owners_.end();) {
            if (it->second == train && !wanted.contains(it->first))
                it = owners_.erase(it);
            else ++it;
        }
        for (const auto piece : wanted) owners_[piece] = train;
        return true;
    }

    std::unordered_map<BlockId, TrainId> owners_{};
};
} // namespace ch::rail_dispatch
