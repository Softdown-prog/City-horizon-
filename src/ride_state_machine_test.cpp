#include "ride_state_machine.h"

#include <cassert>
#include <cmath>

int main() {
    RideStateDurations durations;
    durations.boarding_ms = 1000;
    durations.starting_ms = 200;
    durations.running_ms = 2000;
    durations.stopping_ms = 200;
    durations.unloading_ms = 600;

    RideStateMachine ride(durations);
    assert(ride.snapshot().state == RideOperatingState::idle);

    ride.request_dispatch();
    assert(ride.snapshot().state == RideOperatingState::boarding);

    // Large fixed-step updates may cross multiple phases deterministically.
    ride.update(1100);
    assert(ride.snapshot().state == RideOperatingState::starting);
    assert(ride.snapshot().elapsed_in_state_ms == 100);

    ride.update(1100);
    assert(ride.snapshot().state == RideOperatingState::running);
    assert(ride.snapshot().elapsed_in_state_ms == 1000);
    assert(std::abs(ride.snapshot().normalized_running_phase(durations) - 0.5F) < 0.001F);

    ride.update(2200);
    assert(ride.snapshot().state == RideOperatingState::unloading);
    assert(ride.snapshot().elapsed_in_state_ms == 0);

    ride.update(600);
    assert(ride.snapshot().state == RideOperatingState::idle);
    assert(!ride.snapshot().dispatch_requested);
    assert(ride.snapshot().normalized_running_phase(durations) == 0.0F);

    return 0;
}
