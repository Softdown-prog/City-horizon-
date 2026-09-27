#pragma once

#include "fence_placement_controller.h"
#include "fence_system.h"
#include "navigation_network.h"
#include "src/ch_core/contracts.h"

#include <algorithm>
#include <cstdint>
#include <optional>
#include <string_view>
#include <unordered_map>

namespace park_fence_runtime {

enum class ParkFenceStyle : std::uint8_t {
    classic_iron = 0,
    iron_stone = 1,
};

inline constexpr std::string_view kClassicIronFenceStyleId = "park_fence_classic_iron_v1";
inline constexpr std::string_view kIronStoneFenceStyleId = "park_iron_fence_01";

[[nodiscard]] inline std::string_view fence_style_id(const ParkFenceStyle style) {
    switch (style) {
        case ParkFenceStyle::iron_stone:
            return kIronStoneFenceStyleId;
        case ParkFenceStyle::classic_iron:
        default:
            return kClassicIronFenceStyleId;
    }
}

[[nodiscard]] inline std::optional<ParkFenceStyle> fence_style_from_id(const std::string_view id) {
    if (id == kClassicIronFenceStyleId) return ParkFenceStyle::classic_iron;
    if (id == kIronStoneFenceStyleId) return ParkFenceStyle::iron_stone;
    return std::nullopt;
}

[[nodiscard]] inline FenceManager& fences() {
    static FenceManager manager(ch::contracts::kMapMin, ch::contracts::kMapMax);
    return manager;
}

[[nodiscard]] inline FencePlacementController& placement() {
    static FencePlacementController controller(fences());
    return controller;
}

[[nodiscard]] inline std::uint64_t segment_style_key(const FenceVertex from, const FenceVertex to) {
    constexpr int span = ch::contracts::kMapMax - ch::contracts::kMapMin + 2;
    const auto vertex_key = [](const FenceVertex vertex) {
        return static_cast<std::uint32_t>(
            (vertex.y - ch::contracts::kMapMin) * span +
            (vertex.x - ch::contracts::kMapMin));
    };
    const std::uint32_t a = vertex_key(from);
    const std::uint32_t b = vertex_key(to);
    const std::uint32_t low = std::min(a, b);
    const std::uint32_t high = std::max(a, b);
    return (static_cast<std::uint64_t>(low) << 32U) | high;
}

[[nodiscard]] inline std::unordered_map<std::uint64_t, ParkFenceStyle>& segment_styles() {
    static std::unordered_map<std::uint64_t, ParkFenceStyle> styles;
    return styles;
}

[[nodiscard]] inline ParkFenceStyle segment_style(const FenceVertex from, const FenceVertex to) {
    const auto found = segment_styles().find(segment_style_key(from, to));
    return found == segment_styles().end() ? ParkFenceStyle::classic_iron : found->second;
}

[[nodiscard]] inline bool set_segment_style(const FenceVertex from, const FenceVertex to,
                                            const ParkFenceStyle style) {
    if (!fences().has_segment(from, to)) return false;
    const std::uint64_t key = segment_style_key(from, to);
    if (style == ParkFenceStyle::classic_iron) segment_styles().erase(key);
    else segment_styles()[key] = style;
    return true;
}

inline void clear_segment_styles() {
    segment_styles().clear();
}

inline void clear() {
    placement().cancel_drag();
    fences().clear();
    clear_segment_styles();
}

}  // namespace park_fence_runtime

// Drop-in replacement for the current pedestrian road-lane graph. Logical
// roads remain the source of walkable tiles, while Park fences veto crossings
// on their grid edge. Open gates deliberately do not veto the crossing.
class ParkFencePedestrianNavigationNetwork final : public NavigationNetwork {
public:
    explicit ParkFencePedestrianNavigationNetwork(const RoadManager& roads)
        : base_(roads) {}

    [[nodiscard]] bool is_navigable(const NavigationTile tile) const override {
        return base_.is_navigable(tile);
    }

    [[nodiscard]] bool is_connected(const NavigationTile tile,
                                    const CardinalDirection direction) const override {
        return base_.is_connected(tile, direction) &&
               !park_fence_runtime::fences().blocks_tile_crossing(tile.x, tile.y, direction);
    }

private:
    PedestrianLaneNavigationNetwork base_;
};
