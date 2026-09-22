#include "road_system.h"
#include "sidewalk_system.h"

#include <cassert>
#include <cstdint>

int main() {
    RoadManager roads{-4, 4};
    SidewalkManager sidewalks{-4, 4};

    // A straight run: each endpoint has one reciprocal connection and the
    // centre connects to both sides.
    assert(sidewalks.place_tile(0, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    assert(sidewalks.place_tile(2, 0, "concrete_01"));
    assert(sidewalks.connection_mask(0, 0) == tile_connection_east);
    assert(sidewalks.connection_mask(1, 0) == (tile_connection_west | tile_connection_east));
    assert(sidewalks.connection_mask(2, 0) == tile_connection_west);
    assert(sidewalks.is_walkable(1, 0));
    assert(sidewalks.is_connected_to(1, 0, CardinalDirection::east));
    assert(!sidewalks.is_connected_to(1, 0, CardinalDirection::north));

    // Adding and removing a branch must refresh only the centre and its direct
    // neighbors, while keeping their masks reciprocal.
    assert(sidewalks.place_tile(1, -1, "concrete_01"));
    assert(sidewalks.connection_mask(1, 0) ==
           (tile_connection_north | tile_connection_east | tile_connection_west));
    assert(sidewalks.connection_mask(1, -1) == tile_connection_south);
    assert(sidewalks.remove_tile(1, -1));
    assert(sidewalks.connection_mask(1, 0) == (tile_connection_west | tile_connection_east));
    assert(sidewalks.connection_mask(1, -1) == 0);

    // Dirt-path regression: the runtime path topology is the 4-bit N/E/S/W
    // mask consumed by the 16 authored dirt sprites. Exercise every mask so a
    // future topology change cannot silently select the wrong corner/end/T.
    for (std::uint8_t expected = 0; expected < 16; ++expected) {
        SidewalkManager dirt{-2, 2};
        assert(dirt.place_tile(0, 0, "dirt_path"));
        if ((expected & tile_connection_north) != 0) assert(dirt.place_tile(0, -1, "dirt_path"));
        if ((expected & tile_connection_east) != 0) assert(dirt.place_tile(1, 0, "dirt_path"));
        if ((expected & tile_connection_south) != 0) assert(dirt.place_tile(0, 1, "dirt_path"));
        if ((expected & tile_connection_west) != 0) assert(dirt.place_tile(-1, 0, "dirt_path"));
        const SidewalkTile* centre = dirt.tile_at(0, 0);
        assert(centre != nullptr);
        assert(centre->style_id == "dirt_path");
        assert(dirt.connection_mask(0, 0) == expected);
    }

    assert(roads.place_tile(0, 0));
    assert(roads.place_tile(0, 1));
    assert(roads.is_drivable(0, 0));
    assert(roads.is_connected_to(0, 0, CardinalDirection::south));
    assert(roads.is_connected_to(0, 1, CardinalDirection::north));
}
