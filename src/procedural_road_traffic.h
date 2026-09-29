#pragma once

#include "procedural_road_vehicle_render_adapter.h"

#include <algorithm>
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
struct ProceduralRoadTrafficInstance {
    std::string vehicle_id;
    ProceduralRoadVehicleFollower follower;
    ProceduralRoadVehicleFollowerConfig movement{};
    ProceduralRoadVehicleVisual visual{};
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
        for (ProceduralRoadTrafficInstance& instance : instances_) {
            instance.follower.update(tick_seconds, instance.movement);
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
    std::vector<ProceduralRoadTrafficInstance> instances_;
};
