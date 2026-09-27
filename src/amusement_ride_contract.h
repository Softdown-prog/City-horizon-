#pragma once

#include <SDL3/SDL.h>

#include "building_system.h"

#include <charconv>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace ch::amusement_ride {

// CH_AMUSEMENT_RIDE_V1 is deliberately loaded from the authored building JSON
// instead of branching on concrete attraction ids. This keeps the visitor/ride
// runtime unchanged when the park grows from a handful of rides to dozens.
struct RuntimeDefinition {
    std::uint32_t capacity = 0;
    std::uint32_t boarding_timeout_ms = 0;
    std::uint32_t cycle_duration_ms = 0;
    std::uint32_t seat_count = 0;
    std::string passenger_overlay_contract;
    std::string actor_source;
    std::string palette_mode;
    std::string seat_assignment;
};

namespace detail {

[[nodiscard]] inline std::string read_text(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) return {};
    std::ostringstream stream;
    stream << input.rdbuf();
    return stream.str();
}

[[nodiscard]] inline std::size_t skip_whitespace(const std::string_view text, std::size_t position) {
    while (position < text.size()) {
        const char value = text[position];
        if (value != ' ' && value != '\t' && value != '\r' && value != '\n') break;
        ++position;
    }
    return position;
}

[[nodiscard]] inline std::optional<std::size_t> value_position(const std::string_view json,
                                                               const std::string_view key) {
    const std::string quoted = "\"" + std::string(key) + "\"";
    const std::size_t key_position = json.find(quoted);
    if (key_position == std::string_view::npos) return std::nullopt;
    const std::size_t colon = json.find(':', key_position + quoted.size());
    if (colon == std::string_view::npos) return std::nullopt;
    return skip_whitespace(json, colon + 1);
}

[[nodiscard]] inline std::optional<std::string_view> json_object(const std::string_view json,
                                                                  const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '{') return std::nullopt;
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t index = *position; index < json.size(); ++index) {
        const char value = json[index];
        if (in_string) {
            if (escaped) escaped = false;
            else if (value == '\\') escaped = true;
            else if (value == '"') in_string = false;
            continue;
        }
        if (value == '"') in_string = true;
        else if (value == '{') ++depth;
        else if (value == '}' && --depth == 0) return json.substr(*position, index - *position + 1);
    }
    return std::nullopt;
}

[[nodiscard]] inline std::optional<std::string> json_string(const std::string_view json,
                                                              const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '"') return std::nullopt;
    std::string result;
    bool escaped = false;
    for (std::size_t index = *position + 1; index < json.size(); ++index) {
        const char value = json[index];
        if (escaped) {
            switch (value) {
                case '\\': result += '\\'; break;
                case '"': result += '"'; break;
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                default: return std::nullopt;
            }
            escaped = false;
        } else if (value == '\\') {
            escaped = true;
        } else if (value == '"') {
            return result;
        } else {
            result += value;
        }
    }
    return std::nullopt;
}

[[nodiscard]] inline std::optional<std::uint32_t> json_uint(const std::string_view json,
                                                             const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size()) return std::nullopt;
    std::uint64_t parsed_value = 0;
    const char* first = json.data() + *position;
    const char* last = json.data() + json.size();
    const auto parsed = std::from_chars(first, last, parsed_value);
    if (parsed.ec != std::errc{} || parsed.ptr == first ||
        parsed_value > std::numeric_limits<std::uint32_t>::max()) return std::nullopt;
    return static_cast<std::uint32_t>(parsed_value);
}

[[nodiscard]] inline std::optional<bool> json_bool(const std::string_view json,
                                                    const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) return std::nullopt;
    if (json.substr(*position, 4) == "true") return true;
    if (json.substr(*position, 5) == "false") return false;
    return std::nullopt;
}

[[nodiscard]] inline std::optional<RuntimeDefinition> parse(const std::string_view json,
                                                             const BuildingDefinition& building) {
    const auto ride = json_object(json, "amusementRide");
    if (!ride || json_string(*ride, "contract").value_or("") != "CH_AMUSEMENT_RIDE_V1")
        return std::nullopt;

    // Park rides are intentionally reachable only through their paired ticket
    // booth. They must also satisfy fun so autonomous visitors can discover them
    // without any attraction-specific code.
    if (building.category != "city_park" || !building.requires_ticket_booth ||
        building.is_park_ticket_booth || building.needs_effect.fun <= 0.0F) return std::nullopt;

    const auto queue = json_object(*ride, "queue");
    const auto cycle = json_object(*ride, "cycle");
    const auto passengers = json_object(*ride, "passengers");
    if (!queue || !cycle || !passengers) return std::nullopt;

    const auto capacity = json_uint(*ride, "capacity");
    const auto enabled = json_bool(*queue, "enabled");
    const auto boarding_timeout = json_uint(*queue, "boardingTimeoutMs");
    const auto cycle_duration = json_uint(*cycle, "durationMs");
    const auto seat_count = json_uint(*passengers, "seatCount");
    if (!capacity || !enabled || !*enabled || !boarding_timeout || !cycle_duration || !seat_count)
        return std::nullopt;

    constexpr std::uint32_t kMaximumRideCapacity = 512;
    if (*capacity == 0 || *capacity > kMaximumRideCapacity || *seat_count < *capacity ||
        *seat_count > kMaximumRideCapacity || *boarding_timeout == 0 || *cycle_duration == 0)
        return std::nullopt;

    if (json_string(*queue, "contract").value_or("") != "CH_AMUSEMENT_RIDE_QUEUE_V1" ||
        json_string(*queue, "boardingPolicy").value_or("") != "fifo" ||
        json_string(*queue, "dispatchPolicy").value_or("") != "full_or_timeout")
        return std::nullopt;

    RuntimeDefinition result;
    result.capacity = *capacity;
    result.boarding_timeout_ms = *boarding_timeout;
    result.cycle_duration_ms = *cycle_duration;
    result.seat_count = *seat_count;
    result.passenger_overlay_contract = json_string(*passengers, "overlayContract").value_or("");
    result.actor_source = json_string(*passengers, "actorSource").value_or("");
    result.palette_mode = json_string(*passengers, "paletteMode").value_or("");
    result.seat_assignment = json_string(*passengers, "seatAssignment").value_or("");

    if (result.passenger_overlay_contract != "CH_RIDE_PASSENGER_OVERLAY_V1" ||
        result.actor_source.empty() || result.palette_mode != "stable_per_visitor" ||
        result.seat_assignment != "queue_order_next_free_slot") return std::nullopt;
    return result;
}

[[nodiscard]] inline std::vector<std::filesystem::path> definition_paths(const std::string& id) {
    std::vector<std::filesystem::path> paths;
    if (const char* base = SDL_GetBasePath(); base != nullptr && *base != '\0') {
        paths.emplace_back(std::filesystem::path(base) / "assets" / "definitions" / (id + ".json"));
    }
    paths.emplace_back(std::filesystem::path("assets") / "definitions" / (id + ".json"));
    return paths;
}

}  // namespace detail

[[nodiscard]] inline const RuntimeDefinition* find(const BuildingDefinition& definition) {
    // Cache both successes and failures. A production asset definition is immutable
    // during one game session, so the runtime never performs per-frame disk IO.
    static std::unordered_map<std::string, std::optional<RuntimeDefinition>> cache;
    const auto existing = cache.find(definition.id);
    if (existing != cache.end()) return existing->second ? &*existing->second : nullptr;

    std::optional<RuntimeDefinition> parsed;
    for (const std::filesystem::path& path : detail::definition_paths(definition.id)) {
        const std::string json = detail::read_text(path);
        if (json.empty()) continue;
        parsed = detail::parse(json, definition);
        break;
    }

    auto [stored, _] = cache.emplace(definition.id, std::move(parsed));
    return stored->second ? &*stored->second : nullptr;
}

}  // namespace ch::amusement_ride
