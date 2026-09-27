#pragma once

#include "building_system.h"
#include "crosswalk_runtime.h"
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
    chainlink = 2,
};

inline constexpr std::string_view kClassicIronFenceStyleId = "park_fence_classic_iron_v1";
inline constexpr std::string_view kIronStoneFenceStyleId = "park_iron_fence_01";
inline constexpr std::string_view kChainlinkFenceStyleId = "park_chainlink_fence_01";

[[nodiscard]] inline std::string_view fence_style_id(const ParkFenceStyle style) {
    switch (style) {
        case ParkFenceStyle::iron_stone:
            return kIronStoneFenceStyleId;
        case ParkFenceStyle::chainlink:
            return kChainlinkFenceStyleId;
        case ParkFenceStyle::classic_iron:
        default:
            return kClassicIronFenceStyleId;
    }
}

[[nodiscard]] inline std::optional<ParkFenceStyle> fence_style_from_id(const std::string_view id) {
    if (id == kClassicIronFenceStyleId) return ParkFenceStyle::classic_iron;
    if (id == kIronStoneFenceStyleId) return ParkFenceStyle::iron_stone;
    if (id == kChainlinkFenceStyleId) return ParkFenceStyle::chainlink;
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

// Collision-aware pedestrian graph. Buildings remove occupied cells and closed
// fence segments veto only their edge. Roads are vehicle-only; a pedestrian
// may enter a road cell only through an active CrosswalkPortal, whose two sides
// must both connect to walkable pedestrian floor.
class PedestrianCollisionNavigationNetwork final : public NavigationNetwork {
public:
    PedestrianCollisionNavigationNetwork(const RoadManager& roads,
                                         const SidewalkManager& sidewalks,
                                         const BuildingManager& buildings)
        : base_(roads, sidewalks, crosswalk_runtime::crosswalks()), buildings_(buildings) {}

    [[nodiscard]] bool is_navigable(const NavigationTile tile) const override {
        return base_.is_navigable(tile) && !buildings_.is_occupied(tile.x, tile.y);
    }

    [[nodiscard]] bool is_connected(const NavigationTile tile,
                                    const CardinalDirection direction) const override {
        if (!base_.is_connected(tile, direction)) return false;
        if (fences().blocks_tile_crossing(tile.x, tile.y, direction)) return false;

        if (fences().is_open_gate_crossing(tile.x, tile.y, direction)) {
            const TileOffset offset = direction_offset(direction);
            const NavigationTile other{tile.x + offset.x, tile.y + offset.y};
            return is_navigable(tile) && is_navigable(other);
        }
        return true;
    }

    [[nodiscard]] bool is_walkable_open_gate(const FenceSegment& segment) const {
        const auto crossing = fences().open_gate_crossing(segment.from, segment.to);
        if (!crossing) return false;
        return is_navigable({crossing->first.x, crossing->first.y}) &&
               is_navigable({crossing->second.x, crossing->second.y});
    }

private:
    PedestrianCrosswalkNavigationNetwork base_;
    const BuildingManager& buildings_;
};

}  // namespace park_fence_runtime

// Legacy road-only adapter kept for compatibility with focused tests and older
// call sites. New runtime pedestrians should use PedestrianCollisionNavigationNetwork.
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
