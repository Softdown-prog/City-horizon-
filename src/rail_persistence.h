#pragma once

#include "rail_placement_graph.h"

#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

inline constexpr const char* kChRailPersistenceContract = "CH_RAIL_PERSISTENCE_V2";
inline constexpr const char* kChRailPersistenceLegacyContract = "CH_RAIL_PERSISTENCE_V1";

struct RailPersistentAction {
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    std::int64_t build_cost = 0;
    std::int64_t refund_value = 0;
    bool active = true;
};

struct RailPersistentStation {
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    double dwell_seconds = 3.0;
};

struct RailPersistentState {
    std::vector<RailPlacementNode> nodes;
    std::vector<RailPlacementEdge> edges;
    std::vector<RailPersistentAction> actions;
    std::vector<RailPersistentStation> stations;
};

namespace ch::rail_persistence {

// Keep the original JSON extension key so existing city saves remain discoverable.
// The payload header below carries the V1/V2 schema distinction.
inline constexpr std::string_view kCityJsonKey = "railRuntimeV1";

struct ReadResult {
    RailPersistentState state;
    bool valid = true;
    bool present = false;
    std::string error;
};

using CaptureRuntimeFn = RailPersistentState (*)();
using RestoreRuntimeFn = bool (*)(const RailPersistentState&);

inline CaptureRuntimeFn g_capture_runtime = nullptr;
inline RestoreRuntimeFn g_restore_runtime = nullptr;
inline std::vector<RailPersistentStation> g_runtime_stations;

inline void register_runtime(const CaptureRuntimeFn capture, const RestoreRuntimeFn restore) noexcept {
    g_capture_runtime = capture;
    g_restore_runtime = restore;
}

[[nodiscard]] inline bool runtime_registered() noexcept {
    return g_capture_runtime != nullptr && g_restore_runtime != nullptr;
}

inline void set_runtime_stations(std::vector<RailPersistentStation> stations) {
    g_runtime_stations = std::move(stations);
}

[[nodiscard]] inline const std::vector<RailPersistentStation>& runtime_stations() noexcept {
    return g_runtime_stations;
}

inline void clear_runtime_stations() noexcept {
    g_runtime_stations.clear();
}

[[nodiscard]] inline std::optional<RailPersistentState> capture_runtime_state() {
    if (g_capture_runtime == nullptr) return std::nullopt;
    RailPersistentState state = g_capture_runtime();
    state.stations = g_runtime_stations;
    return state;
}

[[nodiscard]] inline bool restore_runtime_state(const RailPersistentState& state) {
    if (g_restore_runtime == nullptr) {
        if (!state.nodes.empty() || !state.edges.empty() || !state.actions.empty() || !state.stations.empty()) {
            return false;
        }
        clear_runtime_stations();
        return true;
    }
    if (!g_restore_runtime(state)) return false;
    g_runtime_stations = state.stations;
    return true;
}

[[nodiscard]] inline bool validate(const RailPersistentState& state, std::string* error = nullptr) {
    RailPlacementGraph graph;
    if (!graph.restore_snapshot(state.nodes, state.edges)) {
        if (error) *error = "rail graph snapshot is structurally invalid";
        return false;
    }

    // Every edge in a logical piece must share one active/tombstoned state.
    std::unordered_map<RailPlacementPieceId, bool> group_activity;
    for (const RailPlacementEdge& edge : state.edges) {
        const auto found = group_activity.find(edge.piece_group);
        if (found == group_activity.end()) {
            group_activity.emplace(edge.piece_group, edge.active);
        } else if (found->second != edge.active) {
            if (error) *error = "rail logical piece mixes live and tombstoned routes";
            return false;
        }
    }

    std::unordered_map<RailPlacementPieceId, const RailPersistentAction*> actions;
    for (const RailPersistentAction& action : state.actions) {
        if (action.piece_group == kInvalidRailPlacementPieceId || action.build_cost <= 0 ||
            action.refund_value < 0 || action.refund_value > action.build_cost ||
            actions.contains(action.piece_group)) {
            if (error) *error = "rail action ledger is invalid";
            return false;
        }
        actions.emplace(action.piece_group, &action);
    }

    if (actions.size() != group_activity.size()) {
        if (error) *error = "rail action ledger does not cover every logical piece";
        return false;
    }
    for (const auto& [group, active] : group_activity) {
        const auto found = actions.find(group);
        if (found == actions.end() || found->second->active != active) {
            if (error) *error = "rail action state disagrees with graph tombstones";
            return false;
        }
    }

    std::unordered_map<RailPlacementPieceId, bool> station_groups;
    for (const RailPersistentStation& station : state.stations) {
        const auto piece = group_activity.find(station.piece_group);
        if (station.piece_group == kInvalidRailPlacementPieceId ||
            !std::isfinite(station.dwell_seconds) || station.dwell_seconds < 0.0 ||
            station_groups.contains(station.piece_group) ||
            piece == group_activity.end() || !piece->second) {
            if (error) *error = "rail station references an invalid or tombstoned logical piece";
            return false;
        }
        station_groups.emplace(station.piece_group, true);
    }
    return true;
}

[[nodiscard]] inline std::string serialize_payload(const RailPersistentState& state) {
    std::string validation_error;
    if (!validate(state, &validation_error)) return {};

    std::ostringstream output;
    output << kChRailPersistenceContract << '\n' << std::setprecision(17);
    for (const RailPlacementNode& node : state.nodes) {
        output << "N " << node.id << ' '
               << node.position.x << ' ' << node.position.y << ' ' << node.position.z << ' '
               << node.heading_radians << '\n';
    }
    for (const RailPlacementEdge& edge : state.edges) {
        output << "E " << edge.id << ' ' << edge.from << ' ' << edge.to << ' '
               << static_cast<int>(edge.kind) << ' ' << edge.piece_group << ' '
               << (edge.active ? 1 : 0) << ' '
               << edge.segment.start.x << ' ' << edge.segment.start.y << ' ' << edge.segment.start.z << ' '
               << edge.segment.control_a.x << ' ' << edge.segment.control_a.y << ' ' << edge.segment.control_a.z << ' '
               << edge.segment.control_b.x << ' ' << edge.segment.control_b.y << ' ' << edge.segment.control_b.z << ' '
               << edge.segment.end.x << ' ' << edge.segment.end.y << ' ' << edge.segment.end.z << ' '
               << edge.segment.subdivisions << '\n';
    }
    for (const RailPersistentAction& action : state.actions) {
        output << "A " << action.piece_group << ' ' << action.build_cost << ' '
               << action.refund_value << ' ' << (action.active ? 1 : 0) << '\n';
    }
    for (const RailPersistentStation& station : state.stations) {
        output << "S " << station.piece_group << ' ' << station.dwell_seconds << '\n';
    }
    return output.str();
}

[[nodiscard]] inline bool deserialize_payload(const std::string& payload,
                                              RailPersistentState& state,
                                              std::string* error = nullptr) {
    std::istringstream input(payload);
    std::string header;
    if (!std::getline(input, header) ||
        (header != kChRailPersistenceContract && header != kChRailPersistenceLegacyContract)) {
        if (error) *error = "unsupported rail persistence payload";
        return false;
    }
    const bool legacy_v1 = header == kChRailPersistenceLegacyContract;

    RailPersistentState parsed;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) continue;
        std::istringstream row(line);
        char kind = '\0';
        row >> kind;
        if (kind == 'N') {
            RailPlacementNode node;
            if (!(row >> node.id >> node.position.x >> node.position.y >> node.position.z >> node.heading_radians)) {
                if (error) *error = "invalid rail node row";
                return false;
            }
            node.active = false;
            parsed.nodes.push_back(node);
        } else if (kind == 'E') {
            RailPlacementEdge edge;
            int edge_kind = -1;
            int active = -1;
            if (!(row >> edge.id >> edge.from >> edge.to >> edge_kind >> edge.piece_group >> active
                      >> edge.segment.start.x >> edge.segment.start.y >> edge.segment.start.z
                      >> edge.segment.control_a.x >> edge.segment.control_a.y >> edge.segment.control_a.z
                      >> edge.segment.control_b.x >> edge.segment.control_b.y >> edge.segment.control_b.z
                      >> edge.segment.end.x >> edge.segment.end.y >> edge.segment.end.z
                      >> edge.segment.subdivisions) ||
                edge_kind < static_cast<int>(RailPlacementEdgeKind::straight) ||
                edge_kind > static_cast<int>(RailPlacementEdgeKind::crossing_secondary) ||
                (active != 0 && active != 1)) {
                if (error) *error = "invalid rail edge row";
                return false;
            }
            edge.kind = static_cast<RailPlacementEdgeKind>(edge_kind);
            edge.active = active != 0;
            parsed.edges.push_back(edge);
        } else if (kind == 'A') {
            RailPersistentAction action;
            int active = -1;
            if (!(row >> action.piece_group >> action.build_cost >> action.refund_value >> active) ||
                (active != 0 && active != 1)) {
                if (error) *error = "invalid rail action row";
                return false;
            }
            action.active = active != 0;
            parsed.actions.push_back(action);
        } else if (kind == 'S' && !legacy_v1) {
            RailPersistentStation station;
            if (!(row >> station.piece_group >> station.dwell_seconds)) {
                if (error) *error = "invalid rail station row";
                return false;
            }
            parsed.stations.push_back(station);
        } else {
            if (error) *error = "unknown rail persistence row";
            return false;
        }
        row >> std::ws;
        if (!row.eof()) {
            if (error) *error = "rail persistence row has trailing data";
            return false;
        }
    }

    std::string validation_error;
    if (!validate(parsed, &validation_error)) {
        if (error) *error = validation_error;
        return false;
    }
    state = std::move(parsed);
    return true;
}

[[nodiscard]] inline std::string json_escape(const std::string_view value) {
    std::string escaped;
    escaped.reserve(value.size() + value.size() / 8U);
    for (const char c : value) {
        switch (c) {
            case '\\': escaped += "\\\\"; break;
            case '"': escaped += "\\\""; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default: escaped += c; break;
        }
    }
    return escaped;
}

[[nodiscard]] inline bool extract_json_string(const std::string& json,
                                              const std::string_view key,
                                              std::string& value,
                                              bool& present) {
    present = false;
    const std::string needle = "\"" + std::string(key) + "\"";
    const std::size_t key_position = json.find(needle);
    if (key_position == std::string::npos) return true;
    present = true;
    const std::size_t colon = json.find(':', key_position + needle.size());
    if (colon == std::string::npos) return false;
    std::size_t position = colon + 1U;
    while (position < json.size() && (json[position] == ' ' || json[position] == '\t' ||
                                      json[position] == '\r' || json[position] == '\n')) {
        ++position;
    }
    if (position >= json.size() || json[position] != '"') return false;

    std::string decoded;
    bool escaped = false;
    for (++position; position < json.size(); ++position) {
        const char c = json[position];
        if (escaped) {
            switch (c) {
                case '\\': decoded += '\\'; break;
                case '"': decoded += '"'; break;
                case 'n': decoded += '\n'; break;
                case 'r': decoded += '\r'; break;
                case 't': decoded += '\t'; break;
                default: return false;
            }
            escaped = false;
        } else if (c == '\\') {
            escaped = true;
        } else if (c == '"') {
            value = std::move(decoded);
            return true;
        } else {
            decoded += c;
        }
    }
    return false;
}

[[nodiscard]] inline std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) return {};
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

[[nodiscard]] inline bool inject_city_extension(const std::filesystem::path& path,
                                                const RailPersistentState& state,
                                                std::string* error = nullptr) {
    const std::string payload = serialize_payload(state);
    if (payload.empty() && (!state.nodes.empty() || !state.edges.empty() ||
                            !state.actions.empty() || !state.stations.empty())) {
        if (error) *error = "rail state failed validation before save";
        return false;
    }

    std::string json = read_text_file(path);
    if (json.empty()) {
        if (error) *error = "staged city save is empty";
        return false;
    }
    std::size_t close = json.find_last_not_of(" \t\r\n");
    if (close == std::string::npos || json[close] != '}') {
        if (error) *error = "staged city save is not a JSON object";
        return false;
    }

    const std::string extension = ",\n  \"" + std::string(kCityJsonKey) + "\": \"" +
                                  json_escape(payload) + "\"\n";
    json.insert(close, extension);

    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        if (error) *error = "staged city save could not be reopened for rail extension";
        return false;
    }
    output << json;
    output.flush();
    if (!output) {
        if (error) *error = "rail extension could not be written";
        return false;
    }
    return true;
}

[[nodiscard]] inline ReadResult read_city_extension(const std::filesystem::path& path) {
    ReadResult result;
    const std::string json = read_text_file(path);
    if (json.empty()) {
        result.valid = false;
        result.error = "city save is empty while reading rail extension";
        return result;
    }

    std::string payload;
    bool present = false;
    if (!extract_json_string(json, kCityJsonKey, payload, present)) {
        result.valid = false;
        result.present = true;
        result.error = "railRuntimeV1 JSON string is malformed";
        return result;
    }
    result.present = present;
    if (!present) return result; // Legacy city save: empty railway state.

    if (!deserialize_payload(payload, result.state, &result.error)) {
        result.valid = false;
        return result;
    }
    return result;
}

}  // namespace ch::rail_persistence
