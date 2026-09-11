#include "road_system.h"
#include "sidewalk_system.h"

#include <cassert>

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

    assert(roads.place_tile(0, 0));
    assert(roads.place_tile(0, 1));
    assert(roads.is_drivable(0, 0));
    assert(roads.is_connected_to(0, 0, CardinalDirection::south));
    assert(roads.is_connected_to(0, 1, CardinalDirection::north));
}
