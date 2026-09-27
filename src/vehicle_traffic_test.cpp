#include "crosswalk_system.h"
#include "road_system.h"
#include "vehicle_system.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>

namespace {
bool near(const float a, const float b, const float epsilon = 0.001F) {
    return std::abs(a - b) <= epsilon;
}

void build_straight_road(RoadManager& roads, const int x0, const int x1, const int y) {
    for (int x = x0; x <= x1; ++x) {
        assert(roads.place_tile(x, y));
    }
}
}

int main() {
    TrafficVehicleDefinition suv;
    suv.id = "vehicle.road.suv_01";
    suv.cruise_speed = 1.30F;
    suv.acceleration = 1.20F;
    suv.braking = 3.00F;
    suv.safe_distance = 0.72F;
    suv.look_ahead_time = 0.65F;
    suv.lane_offset = 0.18F;

    RoadManager roads(-16, 16);
    build_straight_road(roads, 0, 6, 0);

    // CH right-hand traffic anchor: eastbound uses the south/right half of the
    // logical road tile; westbound uses the north/right half.
    const auto east_anchor = TrafficVehicleManager::lane_anchor({2, 0}, VehicleDirection::east, suv.lane_offset);
    const auto west_anchor = TrafficVehicleManager::lane_anchor({2, 0}, VehicleDirection::west, suv.lane_offset);
    assert(near(east_anchor.first, 2.0F));
    assert(near(east_anchor.second, 0.18F));
    assert(near(west_anchor.first, 2.0F));
    assert(near(west_anchor.second, -0.18F));

    // A traffic route is road-only and must follow actual RoadManager
    // connectivity; grass/off-road coordinates are rejected at spawn time.
    const std::vector<TileCoordinate> valid_route = {{0,0},{1,0},{2,0},{3,0},{4,0},{5,0},{6,0}};
    const std::vector<TileCoordinate> offroad_route = {{0,0},{0,1}};
    assert(TrafficVehicleManager::route_is_drivable(valid_route, roads));
    assert(!TrafficVehicleManager::route_is_drivable(offroad_route, roads));

    TrafficVehicleManager traffic;
    TrafficVehicleInstance invalid;
    invalid.route = offroad_route;
    assert(!traffic.add(invalid, suv, roads));

    // Static lead vehicle on the same eastbound lane. The follower accelerates,
    // detects the lead anchor inside its speed-dependent safety envelope, brakes
    // progressively and must never cross the lead vehicle's anchor.
    TrafficVehicleInstance lead;
    lead.route = {{3,0}};
    lead.direction = VehicleDirection::east;
    assert(traffic.add(lead, suv, roads));

    TrafficVehicleInstance follower;
    follower.route = valid_route;
    follower.speed = 0.0F;
    assert(traffic.add(follower, suv, roads));

    bool saw_braking = false;
    bool saw_motion = false;
    for (int i = 0; i < 80; ++i) {
        traffic.update_tick(0.10F, suv, roads);
        const auto& cars = traffic.instances();
        assert(cars.size() == 2);
        const auto& rear = cars[1];
        saw_motion = saw_motion || rear.map_x > 0.05F;
        saw_braking = saw_braking || rear.state == TrafficVehicleState::braking ||
                                      rear.state == TrafficVehicleState::stopped;
        assert(rear.map_x < cars[0].map_x - 0.30F);
        assert(roads.is_drivable(static_cast<int>(std::lround(rear.map_x)), 0));
    }
    assert(saw_motion);
    assert(saw_braking);

    // With no lead car, the same SUV is allowed to accelerate normally on road.
    traffic.clear();
    TrafficVehicleInstance free_car;
    free_car.route = valid_route;
    assert(traffic.add(free_car, suv, roads));
    for (int i = 0; i < 10; ++i) traffic.update_tick(0.10F, suv, roads);
    assert(traffic.instances().front().speed > 0.0F);
    assert(traffic.instances().front().state == TrafficVehicleState::cruising);

    CrosswalkManager crosswalks{-16, 16};
    assert(crosswalks.place(3, 0, CrosswalkAxis::north_south, roads));
    crosswalks.set_pedestrian_occupied(3, 0, true);
    traffic.clear();
    TrafficVehicleInstance crossing_car;
    crossing_car.route = valid_route;
    crossing_car.speed = suv.cruise_speed;
    assert(traffic.add(crossing_car, suv, roads));
    bool crossing_brake = false;
    for (int i = 0; i < 40; ++i) {
        traffic.update_tick(0.10F, suv, roads, &crosswalks);
        const auto& car = traffic.instances().front();
        crossing_brake = crossing_brake || car.state == TrafficVehicleState::braking || car.state == TrafficVehicleState::stopped;
        assert(car.map_x < 3.0F);
    }
    assert(crossing_brake);
    const float stopped_speed = traffic.instances().front().speed;
    crosswalks.set_pedestrian_occupied(3, 0, false);
    for (int i = 0; i < 8; ++i) traffic.update_tick(0.10F, suv, roads, &crosswalks);
    assert(traffic.instances().front().speed > stopped_speed);

    std::cout << "vehicle_traffic_test: PASS\n";
    return 0;
}
