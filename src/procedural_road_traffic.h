#pragma once

#include "procedural_road_vehicle_render_adapter.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// CH_PROCEDURAL_ROAD_TRAFFIC_V1
//
// Small runtime-facing owner for vehicles that follow continuous procedural-road
// routes. It deliberately stays parallel to TrafficVehicleManager while tile
// traffic remains the gameplay fallback. The manager owns route followers and
// exposes the same MobileEntityRenderData vocabulary already consumed by the
// City Horizon mobile renderer.
struct ProceduralRoadTrafficFollowingConfig {
    bool enabled = true;
    float lookahead_distance = 3.25F;
    float minimum_gap = 0.65F;
    float time_headway = 0.90F;
    float lane_tolerance = 0.42F;
    float elevation_tolerance = 0.45F;
    float same_direction_cosine = 0.50F;
};

struct ProceduralRoadJunctionReservationConfig {
    bool enabled = true;
    float request_lookahead = 2.75F;
    float stop_buffer = 0.30F;
};

enum class ProceduralRoadSignalPhase {
    east_west_green,
    all_red_to_north_south,
    north_south_green,
    all_red_to_east_west,
};

struct ProceduralRoadSignalTiming {
    float green_duration = 6.0F;
    float clearance_duration = 1.0F;
};

struct ProceduralRoadSignalState {
    ProceduralRoadNodeId node_id = kInvalidProceduralRoadNodeId;
    ProceduralRoadSignalPhase phase = ProceduralRoadSignalPhase::east_west_green;
    float elapsed = 0.0F;
    ProceduralRoadSignalTiming timing{};
};

struct ProceduralRoadTrafficInstance {
    std::string vehicle_id;
    ProceduralRoadVehicleFollower follower;
    ProceduralRoadVehicleFollowerConfig movement{};
    ProceduralRoadVehicleVisual visual{};
    std::string leader_vehicle_id;
    float leader_gap = std::numeric_limits<float>::infinity();
    ProceduralRoadNodeId reserved_junction = kInvalidProceduralRoadNodeId;
    ProceduralRoadNodeId blocked_junction = kInvalidProceduralRoadNodeId;
    ProceduralRoadNodeId signal_blocked_junction = kInvalidProceduralRoadNodeId;
};

struct ProceduralRoadJunctionReservation {
    ProceduralRoadNodeId node_id = kInvalidProceduralRoadNodeId;
    std::string vehicle_id;
};

class ProceduralRoadTrafficManager {
public:
    [[nodiscard]] bool add(
        std::string vehicle_id,
        std::vector<ProceduralRoadRoutePoint> route,
        ProceduralRoadVehicleVisual visual,
        const ProceduralRoadVehicleFollowerConfig movement = {}) {
        if (vehicle_id.empty() || contains(vehicle_id)) return false;

        ProceduralRoadTrafficInstance instance;
        instance.vehicle_id = std::move(vehicle_id);
        instance.visual = std::move(visual);
        instance.movement = movement;
        if (!instance.follower.set_route(std::move(route))) return false;
        instances_.push_back(std::move(instance));
        return true;
    }

    [[nodiscard]] bool remove(const std::string_view vehicle_id) {
        const auto found = std::find_if(instances_.begin(), instances_.end(), [&](const auto& instance) {
            return instance.vehicle_id == vehicle_id;
        });
        if (found == instances_.end()) return false;
        instances_.erase(found);
        std::erase_if(junction_reservations_, [&](const auto& reservation) {
            return reservation.vehicle_id == vehicle_id;
        });
        return true;
    }

    void update_tick(const float tick_seconds) {
        if (!(tick_seconds > 0.0F)) return;

        update_signals(tick_seconds);

        std::vector<ProceduralRoadVehiclePose> snapshot;
        snapshot.reserve(instances_.size());
        for (const ProceduralRoadTrafficInstance& instance : instances_) {
            snapshot.push_back(instance.follower.pose());
        }

        std::vector<float> external_speed_caps(
            instances_.size(), std::numeric_limits<float>::infinity());

        for (std::size_t follower_index = 0U; follower_index < instances_.size(); ++follower_index) {
            ProceduralRoadTrafficInstance& follower_instance = instances_[follower_index];
            follower_instance.leader_vehicle_id.clear();
            follower_instance.leader_gap = std::numeric_limits<float>::infinity();
            if (!following_.enabled || snapshot[follower_index].finished) continue;

            const LeaderObservation leader = find_leader(follower_index, snapshot);
            if (!leader.valid) continue;

            follower_instance.leader_vehicle_id = instances_[leader.index].vehicle_id;
            follower_instance.leader_gap = leader.longitudinal_gap;
            external_speed_caps[follower_index] = std::min(
                external_speed_caps[follower_index],
                following_speed_cap(
                    snapshot[follower_index], snapshot[leader.index], leader.longitudinal_gap,
                    follower_instance.movement));
        }

        update_junction_reservations(external_speed_caps);

        for (std::size_t index = 0U; index < instances_.size(); ++index) {
            instances_[index].follower.update(
                tick_seconds, instances_[index].movement, external_speed_caps[index]);
        }
    }

    [[nodiscard]] std::vector<MobileEntityRenderData> render_entities() const {
        std::vector<MobileEntityRenderData> result;
        result.reserve(instances_.size());
        for (const ProceduralRoadTrafficInstance& instance : instances_) {
            const ProceduralRoadVehiclePose& pose = instance.follower.pose();
            const std::string_view state = pose.finished || pose.speed <= 0.0001F ? "stopped" : "moving";
            result.push_back(ProceduralRoadVehicleRenderAdapter::make_render_data(
                pose, instance.visual, state));
        }
        return result;
    }

    void clear() {
        instances_.clear();
        junction_reservations_.clear();
        signal_states_.clear();
    }

    void set_following_config(const ProceduralRoadTrafficFollowingConfig& config) {
        following_ = config;
    }

    [[nodiscard]] const ProceduralRoadTrafficFollowingConfig& following_config() const {
        return following_;
    }

    void set_junction_reservation_config(const ProceduralRoadJunctionReservationConfig& config) {
        junctions_ = config;
        if (!junctions_.enabled) junction_reservations_.clear();
    }

    [[nodiscard]] const ProceduralRoadJunctionReservationConfig& junction_reservation_config() const {
        return junctions_;
    }

    [[nodiscard]] bool add_signalized_junction(
        const ProceduralRoadNodeId node_id,
        const ProceduralRoadSignalTiming timing = {},
        const ProceduralRoadSignalPhase initial_phase = ProceduralRoadSignalPhase::east_west_green) {
        if (node_id == kInvalidProceduralRoadNodeId || signal_state(node_id) != nullptr) return false;
        signal_states_.push_back({node_id, initial_phase, 0.0F, timing});
        return true;
    }

    [[nodiscard]] bool remove_signalized_junction(const ProceduralRoadNodeId node_id) {
        const auto found = std::find_if(signal_states_.begin(), signal_states_.end(), [&](const auto& signal) {
            return signal.node_id == node_id;
        });
        if (found == signal_states_.end()) return false;
        signal_states_.erase(found);
        return true;
    }

    [[nodiscard]] bool is_signalized_junction(const ProceduralRoadNodeId node_id) const {
        return signal_state(node_id) != nullptr;
    }

    [[nodiscard]] std::optional<ProceduralRoadSignalPhase> junction_signal_phase(
        const ProceduralRoadNodeId node_id) const {
        const ProceduralRoadSignalState* signal = signal_state(node_id);
        if (signal == nullptr) return std::nullopt;
        return signal->phase;
    }

    [[nodiscard]] bool junction_signal_allows(
        const ProceduralRoadNodeId node_id,
        const RoadWorldPoint3 forward) const {
        const ProceduralRoadSignalState* signal = signal_state(node_id);
        if (signal == nullptr) return true;

        const bool east_west_approach = std::fabs(forward.x) >= std::fabs(forward.y);
        switch (signal->phase) {
            case ProceduralRoadSignalPhase::east_west_green:
                return east_west_approach;
            case ProceduralRoadSignalPhase::north_south_green:
                return !east_west_approach;
            case ProceduralRoadSignalPhase::all_red_to_north_south:
            case ProceduralRoadSignalPhase::all_red_to_east_west:
                return false;
        }
        return false;
    }

    [[nodiscard]] std::string_view junction_owner(const ProceduralRoadNodeId node_id) const {
        const auto found = std::find_if(junction_reservations_.begin(), junction_reservations_.end(),
                                        [&](const auto& reservation) {
                                            return reservation.node_id == node_id;
                                        });
        return found == junction_reservations_.end() ? std::string_view{} : std::string_view(found->vehicle_id);
    }

    [[nodiscard]] std::size_t junction_reservation_count() const {
        return junction_reservations_.size();
    }

    [[nodiscard]] bool contains(const std::string_view vehicle_id) const {
        return std::any_of(instances_.begin(), instances_.end(), [&](const auto& instance) {
            return instance.vehicle_id == vehicle_id;
        });
    }

    [[nodiscard]] const ProceduralRoadTrafficInstance* find(const std::string_view vehicle_id) const {
        const auto found = std::find_if(instances_.begin(), instances_.end(), [&](const auto& instance) {
            return instance.vehicle_id == vehicle_id;
        });
        return found == instances_.end() ? nullptr : &*found;
    }

    [[nodiscard]] std::size_t size() const { return instances_.size(); }
    [[nodiscard]] bool empty() const { return instances_.empty(); }
    [[nodiscard]] const std::vector<ProceduralRoadTrafficInstance>& instances() const { return instances_; }
    [[nodiscard]] const std::vector<ProceduralRoadSignalState>& signal_states() const { return signal_states_; }

private:
    struct LeaderObservation {
        std::size_t index = 0U;
        float longitudinal_gap = std::numeric_limits<float>::infinity();
        bool valid = false;
    };

    struct JunctionRequest {
        std::size_t instance_index = 0U;
        ProceduralRoadNodeId node_id = kInvalidProceduralRoadNodeId;
        float distance = std::numeric_limits<float>::infinity();
        bool inside = false;
    };

    [[nodiscard]] LeaderObservation find_leader(
        const std::size_t follower_index,
        const std::vector<ProceduralRoadVehiclePose>& snapshot) const {
        LeaderObservation best;
        const ProceduralRoadVehiclePose& follower = snapshot[follower_index];
        const float follower_xy_length = std::sqrt(
            follower.forward.x * follower.forward.x + follower.forward.y * follower.forward.y);
        if (follower_xy_length < 0.000001F) return best;

        const float forward_x = follower.forward.x / follower_xy_length;
        const float forward_y = follower.forward.y / follower_xy_length;
        const float lookahead = std::max(0.0F, following_.lookahead_distance);
        const float lane_tolerance = std::max(0.0F, following_.lane_tolerance);
        const float elevation_tolerance = std::max(0.0F, following_.elevation_tolerance);
        const float direction_threshold = std::clamp(following_.same_direction_cosine, -1.0F, 1.0F);

        for (std::size_t candidate_index = 0U; candidate_index < snapshot.size(); ++candidate_index) {
            if (candidate_index == follower_index) continue;
            const ProceduralRoadVehiclePose& candidate = snapshot[candidate_index];

            const float candidate_xy_length = std::sqrt(
                candidate.forward.x * candidate.forward.x + candidate.forward.y * candidate.forward.y);
            if (candidate_xy_length < 0.000001F) continue;
            const float candidate_forward_x = candidate.forward.x / candidate_xy_length;
            const float candidate_forward_y = candidate.forward.y / candidate_xy_length;
            const float direction_dot = forward_x * candidate_forward_x + forward_y * candidate_forward_y;
            if (direction_dot < direction_threshold) continue;

            const float dx = candidate.position.x - follower.position.x;
            const float dy = candidate.position.y - follower.position.y;
            const float dz = candidate.position.z - follower.position.z;
            if (std::fabs(dz) > elevation_tolerance) continue;

            const float longitudinal = dx * forward_x + dy * forward_y;
            if (!(longitudinal > 0.0001F) || longitudinal > lookahead) continue;

            const float lateral = std::fabs(dx * forward_y - dy * forward_x);
            if (lateral > lane_tolerance) continue;

            if (!best.valid || longitudinal < best.longitudinal_gap) {
                best.index = candidate_index;
                best.longitudinal_gap = longitudinal;
                best.valid = true;
            }
        }
        return best;
    }

    [[nodiscard]] float following_speed_cap(
        const ProceduralRoadVehiclePose& follower,
        const ProceduralRoadVehiclePose& leader,
        const float longitudinal_gap,
        const ProceduralRoadVehicleFollowerConfig& movement) const {
        const float minimum_gap = std::max(0.0F, following_.minimum_gap);
        const float headway = std::max(0.05F, following_.time_headway);
        if (longitudinal_gap <= minimum_gap) return 0.0F;

        const float desired_gap = minimum_gap + std::max(0.0F, follower.speed) * headway;
        const float gap_error = longitudinal_gap - desired_gap;
        const float leader_speed = std::max(0.0F, leader.speed);
        const float proportional_cap = leader_speed + gap_error / headway;
        return std::clamp(proportional_cap, 0.0F, std::max(0.0F, movement.cruise_speed));
    }

    void update_junction_reservations(std::vector<float>& external_speed_caps) {
        for (ProceduralRoadTrafficInstance& instance : instances_) {
            instance.reserved_junction = kInvalidProceduralRoadNodeId;
            instance.blocked_junction = kInvalidProceduralRoadNodeId;
            instance.signal_blocked_junction = kInvalidProceduralRoadNodeId;
        }
        if (!junctions_.enabled) {
            junction_reservations_.clear();
            return;
        }

        reconcile_junction_reservations();
        allocate_junction_reservations();

        const float lookahead = std::max(0.0F, junctions_.request_lookahead);
        for (std::size_t index = 0U; index < instances_.size(); ++index) {
            ProceduralRoadTrafficInstance& instance = instances_[index];
            const auto upcoming = instance.follower.upcoming_junction(lookahead);
            if (!upcoming) continue;

            const std::string_view owner = junction_owner(upcoming->node_id);
            if (owner == instance.vehicle_id) {
                instance.reserved_junction = upcoming->node_id;
                continue;
            }

            const bool signal_permits = upcoming->inside ||
                junction_signal_allows(upcoming->node_id, instance.follower.pose().forward);
            if (!signal_permits) {
                instance.blocked_junction = upcoming->node_id;
                instance.signal_blocked_junction = upcoming->node_id;
                external_speed_caps[index] = std::min(
                    external_speed_caps[index],
                    junction_stop_speed_cap(upcoming->distance, instance.movement));
                continue;
            }

            if (owner.empty()) continue;

            instance.blocked_junction = upcoming->node_id;
            external_speed_caps[index] = std::min(
                external_speed_caps[index],
                junction_stop_speed_cap(upcoming->distance, instance.movement));
        }
    }

    void reconcile_junction_reservations() {
        std::erase_if(junction_reservations_, [&](const ProceduralRoadJunctionReservation& reservation) {
            const ProceduralRoadTrafficInstance* owner = find(reservation.vehicle_id);
            if (owner == nullptr) return true;
            const auto upcoming = owner->follower.upcoming_junction();
            if (!upcoming || upcoming->node_id != reservation.node_id) return true;
            if (upcoming->inside) return false;
            return !junction_signal_allows(reservation.node_id, owner->follower.pose().forward);
        });
    }

    void allocate_junction_reservations() {
        const float lookahead = std::max(0.0F, junctions_.request_lookahead);
        std::vector<JunctionRequest> requests;
        requests.reserve(instances_.size());
        for (std::size_t index = 0U; index < instances_.size(); ++index) {
            const auto upcoming = instances_[index].follower.upcoming_junction(lookahead);
            if (!upcoming || upcoming->node_id == kInvalidProceduralRoadNodeId) continue;
            if (!junction_owner(upcoming->node_id).empty()) continue;
            if (!upcoming->inside &&
                !junction_signal_allows(upcoming->node_id, instances_[index].follower.pose().forward)) {
                continue;
            }
            requests.push_back({index, upcoming->node_id, upcoming->distance, upcoming->inside});
        }

        std::sort(requests.begin(), requests.end(), [&](const JunctionRequest& a, const JunctionRequest& b) {
            if (a.inside != b.inside) return a.inside > b.inside;
            if (std::fabs(a.distance - b.distance) > 0.0001F) return a.distance < b.distance;
            return instances_[a.instance_index].vehicle_id < instances_[b.instance_index].vehicle_id;
        });

        for (const JunctionRequest& request : requests) {
            if (!junction_owner(request.node_id).empty()) continue;
            junction_reservations_.push_back({request.node_id, instances_[request.instance_index].vehicle_id});
        }
    }

    void update_signals(const float tick_seconds) {
        for (ProceduralRoadSignalState& signal : signal_states_) {
            signal.elapsed += tick_seconds;
            int guard = 0;
            while (guard++ < 128) {
                const float duration = signal_phase_duration(signal);
                if (signal.elapsed + 0.000001F < duration) break;
                signal.elapsed -= duration;
                signal.phase = next_signal_phase(signal.phase);
            }
        }
    }

    [[nodiscard]] static ProceduralRoadSignalPhase next_signal_phase(
        const ProceduralRoadSignalPhase phase) {
        switch (phase) {
            case ProceduralRoadSignalPhase::east_west_green:
                return ProceduralRoadSignalPhase::all_red_to_north_south;
            case ProceduralRoadSignalPhase::all_red_to_north_south:
                return ProceduralRoadSignalPhase::north_south_green;
            case ProceduralRoadSignalPhase::north_south_green:
                return ProceduralRoadSignalPhase::all_red_to_east_west;
            case ProceduralRoadSignalPhase::all_red_to_east_west:
                return ProceduralRoadSignalPhase::east_west_green;
        }
        return ProceduralRoadSignalPhase::east_west_green;
    }

    [[nodiscard]] static float signal_phase_duration(const ProceduralRoadSignalState& signal) {
        const bool green = signal.phase == ProceduralRoadSignalPhase::east_west_green ||
                           signal.phase == ProceduralRoadSignalPhase::north_south_green;
        return std::max(0.01F, green ? signal.timing.green_duration : signal.timing.clearance_duration);
    }

    [[nodiscard]] ProceduralRoadSignalState* signal_state(const ProceduralRoadNodeId node_id) {
        const auto found = std::find_if(signal_states_.begin(), signal_states_.end(), [&](const auto& signal) {
            return signal.node_id == node_id;
        });
        return found == signal_states_.end() ? nullptr : &*found;
    }

    [[nodiscard]] const ProceduralRoadSignalState* signal_state(const ProceduralRoadNodeId node_id) const {
        const auto found = std::find_if(signal_states_.begin(), signal_states_.end(), [&](const auto& signal) {
            return signal.node_id == node_id;
        });
        return found == signal_states_.end() ? nullptr : &*found;
    }

    [[nodiscard]] float junction_stop_speed_cap(
        const float distance_to_junction,
        const ProceduralRoadVehicleFollowerConfig& movement) const {
        const float stop_buffer = std::max(0.0F, junctions_.stop_buffer);
        const float available_distance = distance_to_junction - stop_buffer;
        if (!(available_distance > 0.0F)) return 0.0F;
        const float braking = std::max(0.05F, movement.braking);
        const float kinematic_cap = std::sqrt(2.0F * braking * available_distance);
        return std::clamp(kinematic_cap, 0.0F, std::max(0.0F, movement.cruise_speed));
    }

    std::vector<ProceduralRoadTrafficInstance> instances_;
    ProceduralRoadTrafficFollowingConfig following_{};
    ProceduralRoadJunctionReservationConfig junctions_{};
    std::vector<ProceduralRoadJunctionReservation> junction_reservations_;
    std::vector<ProceduralRoadSignalState> signal_states_;
};
