#pragma once

#include "procedural_road_route_sampler.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <optional>
#include <vector>

// CH_PROCEDURAL_ROAD_VEHICLE_FOLLOWER_V1
//
// Lightweight logical follower for the continuous procedural-road route. It is
// intentionally parallel to TrafficVehicleManager while the tile traffic path
// remains the runtime fallback. Movement is distance-based over the sampled
// (x,y,z) polyline, so vehicles do not snap from tile to tile or teleport across
// graph junctions.
struct ProceduralRoadVehicleFollowerConfig {
    float cruise_speed = 1.35F;          // world units / second
    float junction_speed = 0.85F;        // cap inside any junction connector
    float turn_speed = 0.70F;            // cap for left/right junction turns
    float acceleration = 1.10F;          // world units / second^2
    float braking = 2.75F;               // world units / second^2
};

struct ProceduralRoadVehiclePose {
    RoadWorldPoint3 position{};
    RoadWorldPoint3 forward{1.0F, 0.0F, 0.0F};
    float heading_radians = 0.0F;
    float speed = 0.0F;
    float route_distance = 0.0F;
    float route_length = 0.0F;
    ProceduralRoadRoutePointKind kind = ProceduralRoadRoutePointKind::lane;
    ProceduralRoadTurnKind turn = ProceduralRoadTurnKind::straight;
    ProceduralRoadNodeId junction_node = kInvalidProceduralRoadNodeId;
    bool finished = false;
    ProceduralRoadClass road_class = ProceduralRoadClass::unspecified;
};

struct ProceduralRoadUpcomingJunction {
    ProceduralRoadNodeId node_id = kInvalidProceduralRoadNodeId;
    float distance = std::numeric_limits<float>::infinity();
    bool inside = false;
};

class ProceduralRoadVehicleFollower {
public:
    [[nodiscard]] bool set_route(std::vector<ProceduralRoadRoutePoint> route) {
        clear();
        if (route.size() < 2U) return false;
        route_ = std::move(route);
        cumulative_.reserve(route_.size());
        cumulative_.push_back(0.0F);
        for (std::size_t index = 1U; index < route_.size(); ++index) {
            const float step = distance(route_[index - 1U].position, route_[index].position);
            if (!(step > 0.000001F)) return clear_and_fail();
            cumulative_.push_back(cumulative_.back() + step);
        }
        if (!(cumulative_.back() > 0.0F)) return clear_and_fail();
        valid_ = true;
        pose_ = pose_at_distance(0.0F);
        return true;
    }

    void clear() {
        route_.clear();
        cumulative_.clear();
        pose_ = {};
        valid_ = false;
    }

    [[nodiscard]] bool valid() const { return valid_; }
    [[nodiscard]] const ProceduralRoadVehiclePose& pose() const { return pose_; }

    [[nodiscard]] std::optional<ProceduralRoadUpcomingJunction> upcoming_junction(
        const float lookahead_distance = std::numeric_limits<float>::infinity()) const {
        if (!valid_ || pose_.finished || route_.size() < 2U) return std::nullopt;
        const float lookahead = std::max(0.0F, lookahead_distance);
        const float d = std::clamp(pose_.route_distance, 0.0F, route_length());

        auto upper = std::upper_bound(cumulative_.begin(), cumulative_.end(), d);
        std::size_t next_index = static_cast<std::size_t>(std::distance(cumulative_.begin(), upper));
        if (next_index == 0U) next_index = 1U;
        if (next_index >= route_.size()) next_index = route_.size() - 1U;
        const std::size_t previous_index = next_index - 1U;

        const auto& previous = route_[previous_index];
        if (previous.kind == ProceduralRoadRoutePointKind::junction_connector &&
            previous.junction_node != kInvalidProceduralRoadNodeId) {
            return ProceduralRoadUpcomingJunction{previous.junction_node, 0.0F, true};
        }
        const auto& next = route_[next_index];
        if (next.kind == ProceduralRoadRoutePointKind::junction_connector &&
            next.junction_node != kInvalidProceduralRoadNodeId &&
            d >= cumulative_[next_index] - 0.00001F) {
            return ProceduralRoadUpcomingJunction{next.junction_node, 0.0F, true};
        }

        for (std::size_t index = next_index; index < route_.size(); ++index) {
            const auto& point = route_[index];
            if (point.kind != ProceduralRoadRoutePointKind::junction_connector ||
                point.junction_node == kInvalidProceduralRoadNodeId) {
                continue;
            }
            const float distance_to_junction = std::max(0.0F, cumulative_[index] - d);
            if (distance_to_junction > lookahead) return std::nullopt;
            return ProceduralRoadUpcomingJunction{point.junction_node, distance_to_junction, false};
        }
        return std::nullopt;
    }

    void update(
        const float dt_seconds,
        const ProceduralRoadVehicleFollowerConfig& config = {},
        const float external_speed_cap = std::numeric_limits<float>::infinity()) {
        if (!valid_ || pose_.finished || !(dt_seconds > 0.0F)) return;

        const float target_speed = effective_speed_limit(pose_, config, external_speed_cap);
        float next_speed = pose_.speed;
        if (next_speed < target_speed) {
            next_speed = std::min(target_speed, next_speed + std::max(0.0F, config.acceleration) * dt_seconds);
        } else if (next_speed > target_speed) {
            next_speed = std::max(target_speed, next_speed - std::max(0.0F, config.braking) * dt_seconds);
        }

        const float next_distance = std::min(route_length(), pose_.route_distance + next_speed * dt_seconds);
        ProceduralRoadVehiclePose next_pose = pose_at_distance(next_distance);
        next_pose.speed = std::min(next_speed, effective_speed_limit(next_pose, config, external_speed_cap));
        if (next_distance >= route_length() - 0.00001F) {
            next_pose.finished = true;
            next_pose.speed = 0.0F;
        }
        pose_ = next_pose;
    }

    [[nodiscard]] ProceduralRoadVehiclePose pose_at_distance(const float requested_distance) const {
        ProceduralRoadVehiclePose result;
        if (!valid_ || route_.size() < 2U) return result;

        const float total = route_length();
        const float d = std::clamp(requested_distance, 0.0F, total);
        auto upper = std::upper_bound(cumulative_.begin(), cumulative_.end(), d);
        std::size_t next_index = static_cast<std::size_t>(std::distance(cumulative_.begin(), upper));
        if (next_index == 0U) next_index = 1U;
        if (next_index >= route_.size()) next_index = route_.size() - 1U;
        const std::size_t previous_index = next_index - 1U;

        const float start_d = cumulative_[previous_index];
        const float end_d = cumulative_[next_index];
        const float segment_length = std::max(0.000001F, end_d - start_d);
        const float t = std::clamp((d - start_d) / segment_length, 0.0F, 1.0F);

        result.position = lerp(route_[previous_index].position, route_[next_index].position, t);
        result.forward = normalized(route_[next_index].position, route_[previous_index].position);
        result.heading_radians = std::atan2(result.forward.y, result.forward.x);
        result.route_distance = d;
        result.route_length = total;
        result.kind = route_[next_index].kind;
        result.turn = route_[next_index].turn;
        result.junction_node = route_[next_index].junction_node;
        result.road_class = route_[next_index].road_class;
        result.finished = d >= total - 0.00001F;
        return result;
    }

private:
    [[nodiscard]] static float distance(const RoadWorldPoint3& a, const RoadWorldPoint3& b) {
        const float dx = b.x - a.x;
        const float dy = b.y - a.y;
        const float dz = b.z - a.z;
        return std::sqrt(dx * dx + dy * dy + dz * dz);
    }

    [[nodiscard]] static RoadWorldPoint3 lerp(const RoadWorldPoint3& a, const RoadWorldPoint3& b, const float t) {
        return {a.x + (b.x - a.x) * t,
                a.y + (b.y - a.y) * t,
                a.z + (b.z - a.z) * t};
    }

    [[nodiscard]] static RoadWorldPoint3 normalized(const RoadWorldPoint3& to, const RoadWorldPoint3& from) {
        RoadWorldPoint3 value{to.x - from.x, to.y - from.y, to.z - from.z};
        const float length = std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
        if (length < 0.000001F) return {1.0F, 0.0F, 0.0F};
        value.x /= length;
        value.y /= length;
        value.z /= length;
        return value;
    }

    [[nodiscard]] static float local_speed_limit(const ProceduralRoadVehiclePose& pose,
                                                 const ProceduralRoadVehicleFollowerConfig& config) {
        float limit = std::max(0.0F, config.cruise_speed);
        const ProceduralRoadClassProfile class_profile = procedural_road_class_profile(pose.road_class);
        if (std::isfinite(class_profile.speed_limit)) {
            limit = std::min(limit, std::max(0.0F, class_profile.speed_limit));
        }
        if (pose.kind == ProceduralRoadRoutePointKind::junction_connector) {
            limit = std::min(limit, std::max(0.0F, config.junction_speed));
            if (pose.turn == ProceduralRoadTurnKind::left || pose.turn == ProceduralRoadTurnKind::right ||
                pose.turn == ProceduralRoadTurnKind::u_turn) {
                limit = std::min(limit, std::max(0.0F, config.turn_speed));
            }
        }
        return limit;
    }

    [[nodiscard]] static float effective_speed_limit(
        const ProceduralRoadVehiclePose& pose,
        const ProceduralRoadVehicleFollowerConfig& config,
        const float external_speed_cap) {
        float limit = local_speed_limit(pose, config);
        if (std::isfinite(external_speed_cap)) {
            limit = std::min(limit, std::max(0.0F, external_speed_cap));
        }
        return limit;
    }

    [[nodiscard]] float route_length() const {
        return cumulative_.empty() ? 0.0F : cumulative_.back();
    }

    [[nodiscard]] bool clear_and_fail() {
        clear();
        return false;
    }

    std::vector<ProceduralRoadRoutePoint> route_;
    std::vector<float> cumulative_;
    ProceduralRoadVehiclePose pose_{};
    bool valid_ = false;
};
