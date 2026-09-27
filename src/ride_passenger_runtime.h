#pragma once

#include "building_visit_runtime.h"
#include "pedestrian_system.h"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

namespace ch::ride_passenger_runtime {

// CH_RIDE_PASSENGER_SEAT_BINDING_V1 is the renderer-facing bridge between the
// synchronized ride queue and authored seat layouts. A binding exists only for
// a visitor that actually boarded the current ride batch.
struct SeatBinding {
    std::uint64_t ride_instance_id = 0;
    std::uint64_t pedestrian_id = 0;
    int seat_index = -1;
    std::string actor_source;
    MobileClothingTint clothing;
};

[[nodiscard]] inline const PedestrianInstance* find_pedestrian(
    const PedestrianSystem& pedestrians, const std::uint64_t pedestrian_id) {
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        if (pedestrian.id == pedestrian_id) return &pedestrian;
    }
    return nullptr;
}

[[nodiscard]] inline std::vector<SeatBinding> active_seat_bindings(
    const std::uint64_t attraction_instance_id, const PedestrianSystem& pedestrians) {
    std::vector<SeatBinding> result;
    const auto queue = building_visit_runtime::ride_queues().find(attraction_instance_id);
    if (queue == building_visit_runtime::ride_queues().end()) return result;

    result.reserve(queue->second.riding.size());
    for (const std::uint64_t pedestrian_id : queue->second.riding) {
        const auto state = building_visit_runtime::states().find(pedestrian_id);
        if (state == building_visit_runtime::states().end() ||
            state->second.phase != building_visit_runtime::VisitPhase::inside ||
            state->second.building_instance_id != attraction_instance_id ||
            state->second.ride_seat_index < 0) {
            continue;
        }

        const PedestrianInstance* pedestrian = find_pedestrian(pedestrians, pedestrian_id);
        if (pedestrian == nullptr) continue;

        SeatBinding binding;
        binding.ride_instance_id = attraction_instance_id;
        binding.pedestrian_id = pedestrian_id;
        binding.seat_index = state->second.ride_seat_index;
        binding.actor_source = pedestrian->animation.animation_set_id;
        binding.clothing = pedestrian->clothing;
        result.push_back(std::move(binding));
    }

    std::sort(result.begin(), result.end(), [](const SeatBinding& left, const SeatBinding& right) {
        if (left.seat_index != right.seat_index) return left.seat_index < right.seat_index;
        return left.pedestrian_id < right.pedestrian_id;
    });
    return result;
}

[[nodiscard]] inline bool has_duplicate_or_invalid_seat(const std::vector<SeatBinding>& bindings,
                                                        const std::size_t seat_count) {
    int previous = -1;
    for (const SeatBinding& binding : bindings) {
        if (binding.seat_index < 0 || static_cast<std::size_t>(binding.seat_index) >= seat_count ||
            binding.seat_index == previous) {
            return true;
        }
        previous = binding.seat_index;
    }
    return false;
}

}  // namespace ch::ride_passenger_runtime
