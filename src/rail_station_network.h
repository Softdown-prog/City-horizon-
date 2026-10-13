#pragma once
#include "rail_placement_graph.h"
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace ch::rail_network {
using StationId = std::uint64_t;
inline constexpr StationId invalid_station_id = 0;
inline constexpr const char* contract = "CH_RAIL_STATION_NETWORK_V1";

struct Station {
    StationId id = invalid_station_id;
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    std::string name;
    double dwell_seconds = 3.0;
};

struct Service {
    std::uint64_t id = 0;
    std::vector<StationId> stops;
    bool repeat = false;
};

// Stable station IDs are independent of the display name, track direction,
// service ordering and the former A/B terminal-pair demonstration.
class StationRegistry {
public:
    [[nodiscard]] std::optional<StationId> add(
        const RailPlacementGraph& graph, RailPlacementPieceId piece,
        std::string name = {}, double dwell_seconds = 3.0) {
        if (!piece_exists(graph, piece) || !std::isfinite(dwell_seconds) ||
            dwell_seconds < 0.0 || by_piece_.count(piece) || next_id_ == invalid_station_id ||
            next_id_ == std::numeric_limits<StationId>::max()) return std::nullopt;
        const StationId id = next_id_++;
        if (name.empty()) name = "Estação " + std::to_string(id);
        stations_.emplace(id, Station{id, piece, std::move(name), dwell_seconds});
        by_piece_.emplace(piece, id);
        return id;
    }

    [[nodiscard]] const Station* find(StationId id) const {
        auto it = stations_.find(id);
        return it == stations_.end() ? nullptr : &it->second;
    }

    [[nodiscard]] std::optional<StationId> station_at(RailPlacementPieceId piece) const {
        auto it = by_piece_.find(piece);
        return it == by_piece_.end() ? std::nullopt : std::optional<StationId>{it->second};
    }

    [[nodiscard]] bool rename(StationId id, std::string name) {
        auto it = stations_.find(id);
        if (it == stations_.end() || name.empty()) return false;
        it->second.name = std::move(name);
        return true;
    }

    [[nodiscard]] bool erase(StationId id) {
        auto it = stations_.find(id);
        if (it == stations_.end()) return false;
        by_piece_.erase(it->second.piece_group);
        stations_.erase(it);
        return true;
    }

    // Prevent silent rebinding to a demolished piece. IDs are never reused.
    [[nodiscard]] bool valid_on(const RailPlacementGraph& graph, StationId id) const {
        const Station* station = find(id);
        return station && piece_exists(graph, station->piece_group);
    }

    [[nodiscard]] bool validate_service(const RailPlacementGraph& graph,
                                        const Service& service) const {
        if (service.id == 0 || service.stops.size() < 2) return false;
        std::unordered_set<StationId> seen;
        for (StationId id : service.stops) {
            if (!valid_on(graph, id)) return false;
            if (!seen.insert(id).second) {
                // A terminal return may revisit its origin only as the last stop.
                if (id != service.stops.front() || id != service.stops.back() ||
                    seen.size() != service.stops.size() - 1) return false;
            }
        }
        return true;
    }

    [[nodiscard]] const std::unordered_map<StationId, Station>& stations() const { return stations_; }

private:
    [[nodiscard]] static bool piece_exists(const RailPlacementGraph& graph,
                                            RailPlacementPieceId group) {
        if (group == kInvalidRailPlacementPieceId) return false;
        for (const auto& edge : graph.edges()) {
            if (edge.active && (edge.piece_group == kInvalidRailPlacementPieceId
                 ? static_cast<RailPlacementPieceId>(edge.id) : edge.piece_group) == group)
                return true;
        }
        return false;
    }
    StationId next_id_ = 1;
    std::unordered_map<StationId, Station> stations_;
    std::unordered_map<RailPlacementPieceId, StationId> by_piece_;
};
} // namespace ch::rail_network
