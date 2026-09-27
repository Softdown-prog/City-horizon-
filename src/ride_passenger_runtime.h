#pragma once

#include "building_visit_runtime.h"
#include "pedestrian_system.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

namespace ch::ride_passenger_runtime {

inline constexpr const char* kSeatBindingContract = "CH_RIDE_PASSENGER_SEAT_BINDING_V1";

// Renderer-facing bridge between the synchronized ride queue and authored seat
// layouts. A binding exists only for a visitor that actually boarded the current
// ride batch. The clothing values come from that same citizen instance.
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

[[nodiscard]] inline std::vector<SeatBinding> all_active_seat_bindings(
    const PedestrianSystem& pedestrians) {
    std::vector<SeatBinding> result;
    for (const auto& [ride_instance_id, queue] : building_visit_runtime::ride_queues()) {
        if (queue.riding.empty()) continue;
        std::vector<SeatBinding> ride = active_seat_bindings(ride_instance_id, pedestrians);
        result.insert(result.end(), std::make_move_iterator(ride.begin()), std::make_move_iterator(ride.end()));
    }
    std::sort(result.begin(), result.end(), [](const SeatBinding& left, const SeatBinding& right) {
        if (left.ride_instance_id != right.ride_instance_id)
            return left.ride_instance_id < right.ride_instance_id;
        if (left.seat_index != right.seat_index) return left.seat_index < right.seat_index;
        return left.pedestrian_id < right.pedestrian_id;
    });
    return result;
}

[[nodiscard]] inline bool has_duplicate_or_invalid_seat(const std::vector<SeatBinding>& bindings,
                                                        const std::size_t seat_count) {
    std::vector<bool> occupied(seat_count, false);
    for (const SeatBinding& binding : bindings) {
        if (binding.seat_index < 0 || static_cast<std::size_t>(binding.seat_index) >= seat_count)
            return true;
        const std::size_t index = static_cast<std::size_t>(binding.seat_index);
        if (occupied[index]) return true;
        occupied[index] = true;
    }
    return false;
}

}  // namespace ch::ride_passenger_runtime
