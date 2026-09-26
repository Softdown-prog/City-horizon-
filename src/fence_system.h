#pragma once

#include "tile_topology.h"

#include <cstdint>
#include <unordered_map>
#include <vector>

// Fence topology lives on grid vertices rather than terrain-tile occupancy.
// That matches classic tycoon behaviour: fences delimit tile edges without
// consuming the tile itself. Connections use the shared stable N/E/S/W mask.
using FenceConnection = TileConnectionMask;
inline constexpr FenceConnection fence_north = tile_connection_north;
inline constexpr FenceConnection fence_east = tile_connection_east;
inline constexpr FenceConnection fence_south = tile_connection_south;
inline constexpr FenceConnection fence_west = tile_connection_west;

struct FenceVertex {
    int x = 0;
    int y = 0;
};

enum class FenceNodeKind : std::uint8_t {
    regular,
    gate,
};

enum class FenceVisualType : std::uint8_t {
    isolated,
    end,
    straight,
    corner,
    tee,
    cross,
    gate,
};

// Quarter-turn contract matches the rest of the game: South is the canonical
// authored orientation, followed clockwise by East, North and West.
enum class FenceRotation : std::uint8_t {
    south = 0,
    east = 1,
    north = 2,
    west = 3,
};

struct FenceVisualState {
    FenceVisualType type = FenceVisualType::isolated;
    FenceRotation rotation = FenceRotation::south;
    FenceConnection connections = 0;
};

struct FenceNode {
    int vertex_x = 0;
    int vertex_y = 0;
    FenceConnection connections = 0;
    FenceNodeKind kind = FenceNodeKind::regular;
    // Used only while a node has too little topology to infer an orientation.
    FenceRotation orientation_hint = FenceRotation::south;
};

class FenceManager {
public:
    FenceManager(int map_min, int map_max);

    [[nodiscard]] bool is_inside_vertex_grid(int vertex_x, int vertex_y) const;
    [[nodiscard]] bool has_fence(int vertex_x, int vertex_y) const;
    [[nodiscard]] const FenceNode* node_at(int vertex_x, int vertex_y) const;
    [[nodiscard]] FenceConnection connection_mask(int vertex_x, int vertex_y) const;
    [[nodiscard]] FenceVisualState visual_state(int vertex_x, int vertex_y) const;

    // Place one network node. Adjacent fence nodes immediately reconnect and
    // can therefore change from end -> straight -> corner -> tee -> cross
    // without any explicit rotation command from the player.
    [[nodiscard]] bool place_node(int vertex_x, int vertex_y,
                                  FenceRotation orientation_hint = FenceRotation::south);

    // Classic tycoon-style drag helper. The route follows X first, then Y;
    // the resulting bend is represented by a corner selected from topology.
    [[nodiscard]] std::vector<FenceVertex> line_between(FenceVertex start, FenceVertex end) const;
    int place_run(const std::vector<FenceVertex>& vertices,
                  FenceRotation orientation_hint = FenceRotation::south);

    [[nodiscard]] bool remove_node(int vertex_x, int vertex_y);
    void clear();

    // A gate is a presentation/traffic state on an existing fence node. It is
    // only resolved as a gate when the node forms a straight two-sided run;
    // otherwise the normal topology piece wins so junctions never disappear.
    [[nodiscard]] bool set_gate(int vertex_x, int vertex_y, bool enabled = true);
    [[nodiscard]] bool can_resolve_gate(int vertex_x, int vertex_y) const;

    [[nodiscard]] const std::vector<FenceNode>& nodes() const;

private:
    [[nodiscard]] int vertex_key(int vertex_x, int vertex_y) const;
    void refresh_connections_around(int vertex_x, int vertex_y);
    void refresh_connections(int vertex_x, int vertex_y);

    int map_min_;
    int map_max_;
    std::vector<FenceNode> nodes_;
    std::unordered_map<int, std::size_t> node_indices_;
};

[[nodiscard]] FenceVisualState resolve_fence_visual(FenceConnection connections,
                                                    FenceNodeKind kind,
                                                    FenceRotation orientation_hint = FenceRotation::south);
