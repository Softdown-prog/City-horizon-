#pragma once

#include "procedural_road_vehicle_render_adapter.h"

#include <algorithm>
#include <cmath>
#include <limits>
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

struct ProceduralRoadTrafficInstance {
    std::string vehicle_id;
    ProceduralRoadVehicleFollower follower;
    ProceduralRoadVehicleFollowerConfig movement{};
    ProceduralRoadVehicleVisual visual{};
    std::string leader_vehicle_id;
    float leader_gap = std::numeric_limits<float>::infinity();
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
        return true;
    }

    void update_tick(const float tick_seconds) {
        if (!(tick_seconds > 0.0F)) return;

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
            external_speed_caps[follower_index] = following_speed_cap(
                snapshot[follower_index], snapshot[leader.index], leader.longitudinal_gap,
                follower_instance.movement);
        }

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

    void clear() { instances_.clear(); }

    void set_following_config(const ProceduralRoadTrafficFollowingConfig& config) {
        following_ = config;
    }

    [[nodiscard]] const ProceduralRoadTrafficFollowingConfig& following_config() const {
        return following_;
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

private:
    struct LeaderObservation {
        std::size_t index = 0U;
        float longitudinal_gap = std::numeric_limits<float>::infinity();
        bool valid = false;
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

    std::vector<ProceduralRoadTrafficInstance> instances_;
    ProceduralRoadTrafficFollowingConfig following_{};
};
