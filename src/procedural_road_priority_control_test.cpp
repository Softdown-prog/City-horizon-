#include "procedural_road_traffic.h"

#include <cassert>
#include <cmath>
#include <vector>

namespace {

std::vector<ProceduralRoadRoutePoint> crossing_route(
    const bool horizontal,
    const ProceduralRoadNodeId junction) {
    std::vector<ProceduralRoadRoutePoint> route;
    for (int step = 0; step <= 30; ++step) {
        const float coordinate = -3.0F + static_cast<float>(step) * 0.2F;
        const bool inside = std::fabs(coordinate) <= 0.4001F;
        route.push_back({
            horizontal ? RoadWorldPoint3{coordinate, 0.0F, 0.0F}
                       : RoadWorldPoint3{0.0F, coordinate, 0.0F},
            inside ? ProceduralRoadRoutePointKind::junction_connector
                   : ProceduralRoadRoutePointKind::lane,
            inside ? kInvalidProceduralRoadSegmentId
                   : static_cast<ProceduralRoadSegmentId>(horizontal ? 10 : 20),
            inside ? junction : kInvalidProceduralRoadNodeId,
            ProceduralRoadTurnKind::straight,
        });
    }
    return route;
}

ProceduralRoadVehicleVisual visual() {
    ProceduralRoadVehicleVisual value;
    value.sprite_south = "south.png";
    value.sprite_east = "east.png";
    value.sprite_north = "north.png";
    value.sprite_west = "west.png";
    value.animation_set_id = "vehicle.priority-test";
    return value;
}

ProceduralRoadVehicleFollowerConfig movement() {
    ProceduralRoadVehicleFollowerConfig value;
    value.cruise_speed = 1.0F;
    value.junction_speed = 0.75F;
    value.turn_speed = 0.70F;
    value.acceleration = 4.0F;
    value.braking = 4.0F;
    return value;
}

ProceduralRoadTrafficManager base_manager() {
    ProceduralRoadTrafficManager traffic;
    ProceduralRoadTrafficFollowingConfig following;
    following.enabled = false;
    traffic.set_following_config(following);

    ProceduralRoadJunctionReservationConfig reservation;
    reservation.request_lookahead = 3.0F;
    reservation.stop_buffer = 0.25F;
    traffic.set_junction_reservation_config(reservation);
    return traffic;
}

void test_priority_beats_yield_even_when_yield_id_sorts_first() {
    constexpr ProceduralRoadNodeId junction = 201;
    auto traffic = base_manager();

    ProceduralRoadJunctionPriorityPolicy policy;
    policy.node_id = junction;
    policy.east_west = ProceduralRoadApproachControl::priority;
    policy.north_south = ProceduralRoadApproachControl::yield;
    assert(traffic.set_junction_priority_policy(policy));

    assert(traffic.add("car.a.yield", crossing_route(false, junction), visual(), movement()));
    assert(traffic.add("car.z.priority", crossing_route(true, junction), visual(), movement()));

    traffic.update_tick(0.05F);
    assert(traffic.junction_owner(junction) == "car.z.priority");
    const auto* yield_car = traffic.find("car.a.yield");
    assert(yield_car != nullptr);
    assert(yield_car->blocked_junction == junction);
    assert(yield_car->priority_blocked_junction == junction);

    bool priority_entered = false;
    bool yield_entered_after = false;
    for (int step = 0; step < 800; ++step) {
        traffic.update_tick(0.05F);
        const auto* priority_car = traffic.find("car.z.priority");
        yield_car = traffic.find("car.a.yield");
        assert(priority_car != nullptr && yield_car != nullptr);

        const bool priority_inside = priority_car->follower.pose().kind ==
            ProceduralRoadRoutePointKind::junction_connector;
        const bool yield_inside = yield_car->follower.pose().kind ==
            ProceduralRoadRoutePointKind::junction_connector;
        assert(!(priority_inside && yield_inside));
        if (priority_inside) priority_entered = true;
        if (yield_inside) {
            yield_entered_after = priority_entered;
            break;
        }
    }
    assert(priority_entered);
    assert(yield_entered_after);
}

void test_stop_requires_full_stop_and_hold_before_reservation() {
    constexpr ProceduralRoadNodeId junction = 202;
    auto traffic = base_manager();

    ProceduralRoadJunctionPriorityPolicy policy;
    policy.node_id = junction;
    policy.east_west = ProceduralRoadApproachControl::stop;
    policy.north_south = ProceduralRoadApproachControl::priority;
    policy.stop_hold_duration = 0.30F;
    policy.stop_speed_threshold = 0.08F;
    assert(traffic.set_junction_priority_policy(policy));

    assert(traffic.add("car.stop", crossing_route(true, junction), visual(), movement()));
    traffic.update_tick(0.05F);
    assert(traffic.junction_owner(junction).empty());

    bool saw_stopped_wait = false;
    bool got_reservation_after_hold = false;
    bool entered_after_hold = false;
    for (int step = 0; step < 600; ++step) {
        traffic.update_tick(0.05F);
        const auto* car = traffic.find("car.stop");
        assert(car != nullptr);

        if (car->stop_wait_junction == junction && car->follower.pose().speed <= 0.08F) {
            saw_stopped_wait = true;
            if (car->stop_wait_elapsed + 0.0001F < policy.stop_hold_duration) {
                assert(traffic.junction_owner(junction).empty());
            }
        }
        if (traffic.junction_owner(junction) == "car.stop") {
            assert(car->stop_wait_elapsed + 0.0001F >= policy.stop_hold_duration);
            got_reservation_after_hold = true;
        }
        if (car->follower.pose().kind == ProceduralRoadRoutePointKind::junction_connector) {
            entered_after_hold = got_reservation_after_hold;
            break;
        }
    }

    assert(saw_stopped_wait);
    assert(got_reservation_after_hold);
    assert(entered_after_hold);
}

void test_signal_control_overrides_priority_policy() {
    constexpr ProceduralRoadNodeId junction = 203;
    auto traffic = base_manager();

    ProceduralRoadJunctionPriorityPolicy policy;
    policy.node_id = junction;
    policy.east_west = ProceduralRoadApproachControl::yield;
    policy.north_south = ProceduralRoadApproachControl::priority;
    assert(traffic.set_junction_priority_policy(policy));

    ProceduralRoadSignalTiming timing;
    timing.green_duration = 2.0F;
    timing.clearance_duration = 0.25F;
    assert(traffic.add_signalized_junction(
        junction, timing, ProceduralRoadSignalPhase::east_west_green));

    assert(traffic.add("car.east-west", crossing_route(true, junction), visual(), movement()));
    assert(traffic.add("car.north-south", crossing_route(false, junction), visual(), movement()));
    traffic.update_tick(0.05F);

    assert(traffic.junction_owner(junction) == "car.east-west");
    const auto* north_south = traffic.find("car.north-south");
    assert(north_south != nullptr);
    assert(north_south->signal_blocked_junction == junction);
}

} // namespace

int main() {
    test_priority_beats_yield_even_when_yield_id_sorts_first();
    test_stop_requires_full_stop_and_hold_before_reservation();
    test_signal_control_overrides_priority_policy();
}
