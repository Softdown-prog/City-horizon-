#include "pedestrian_system.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <utility>

namespace {

// Restrained colors readable at 48x64, applied to authored shade masks. Only
// clothing changes; anatomy, face, shirt, hair and shoes stay on the base PNG.
constexpr std::array<MobileClothingColor, 7> kJacketColors = {{{21, 155, 88}, {178, 70, 91},
    {181, 139, 65}, {58, 150, 143}, {121, 104, 164}, {172, 103, 62}, {84, 124, 174}}};
constexpr std::array<MobileClothingColor, 5> kPantsColors = {{{38, 89, 220}, {78, 102, 159},
    {89, 102, 127}, {121, 86, 65}, {82, 113, 96}}};
constexpr std::array<MobileClothingColor, 7> kUmbrellaColors = {{{208, 79, 77}, {225, 181, 66},
    {69, 151, 183}, {119, 102, 172}, {89, 164, 114}, {223, 122, 81}, {176, 86, 130}}};

[[nodiscard]] CardinalDirection topology_direction_to(const NavigationTile from, const NavigationTile to) {
    if (to.x > from.x) return CardinalDirection::east;
    if (to.x < from.x) return CardinalDirection::west;
    return to.y > from.y ? CardinalDirection::south : CardinalDirection::north;
}

} // namespace

PedestrianSystem::PedestrianSystem(PedestrianVisualDefinition visual_definition)
    : visual_definition_(std::move(visual_definition)) {}

void PedestrianSystem::configure_visual_test(PedestrianVisualDefinition visual_definition) {
    visual_definition_ = std::move(visual_definition);
    for (PedestrianInstance& pedestrian : instances_) {
        pedestrian.speed = visual_definition_.movement_speed_tiles_per_second;
        pedestrian.animation.animation_set_id = visual_definition_.animation_set_id;
        pedestrian.animation.clip_id.clear();
        pedestrian.animation.frame_index = 0;
        pedestrian.animation.accumulated_seconds = 0.0F;
        pedestrian.animation.playback_rate = visual_definition_.animation_playback_rate;
    }
}

bool PedestrianSystem::send_pedestrian(const NavigationTile start, const NavigationTile destination,
                                       const NavigationNetwork& network) {
    // A visitor aligning at a door or hidden inside a building is intentionally
    // unavailable to the ordinary autonomous route scheduler until released.
    if (!instances_.empty() && instances_.front().state == PedestrianState::visiting) return false;

    const NavigationPathResult path = find_navigation_path(network, start, destination);
    if (path.status != NavigationPathStatus::found) return false;

    if (instances_.empty()) {
        PedestrianInstance pedestrian;
        pedestrian.id = next_id_++;
        pedestrian.animation.animation_set_id = visual_definition_.animation_set_id;
        pedestrian.clothing.jacket = kJacketColors[
            std::uniform_int_distribution<std::size_t>{0, kJacketColors.size() - 1}(clothing_rng_)];
        pedestrian.clothing.pants = kPantsColors[
            std::uniform_int_distribution<std::size_t>{0, kPantsColors.size() - 1}(clothing_rng_)];
        pedestrian.umbrella_color = kUmbrellaColors[
            std::uniform_int_distribution<std::size_t>{0, kUmbrellaColors.size() - 1}(clothing_rng_)];
        instances_.push_back(std::move(pedestrian));
    }
    PedestrianInstance& pedestrian = instances_.front();
    pedestrian.speed = visual_definition_.movement_speed_tiles_per_second;
    pedestrian.animation.playback_rate = visual_definition_.animation_playback_rate;
    pedestrian.spatial.logical_world_x = static_cast<float>(start.x);
    pedestrian.spatial.logical_world_y = static_cast<float>(start.y);
    pedestrian.spatial.logical_tile_x = start.x;
    pedestrian.spatial.logical_tile_y = start.y;
    pedestrian.spatial.visual_world_x = pedestrian.spatial.logical_world_x;
    pedestrian.spatial.visual_world_y = pedestrian.spatial.logical_world_y;
    pedestrian.spatial.ground_anchor_x = visual_definition_.lane_ground_anchor_x;
    pedestrian.spatial.ground_anchor_y = visual_definition_.lane_ground_anchor_y;
    pedestrian.route = path.tiles;
    pedestrian.next_waypoint = path.tiles.size() > 1 ? 1 : path.tiles.size();
    pedestrian.destination = destination;
    pedestrian.replanned_after_network_change = false;
    pedestrian.state = pedestrian.next_waypoint < pedestrian.route.size() ? PedestrianState::walking : PedestrianState::idle;
    if (pedestrian.state == PedestrianState::walking) {
        pedestrian.spatial.direction = direction_to(start, pedestrian.route[pedestrian.next_waypoint]);
    }
    return true;
}

bool PedestrianSystem::set_visiting(const std::uint64_t pedestrian_id, const bool visiting) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [pedestrian_id](const PedestrianInstance& pedestrian) {
        return pedestrian.id == pedestrian_id;
    });
    if (found == instances_.end()) return false;

    if (visiting) {
        // Entry is committed only after the pedestrian reaches its door tile.
        if (found->state == PedestrianState::walking) return false;
        found->state = PedestrianState::visiting;
    } else if (found->state == PedestrianState::visiting) {
        found->state = PedestrianState::idle;
    }
    return true;
}

bool PedestrianSystem::face_pedestrian(const std::uint64_t pedestrian_id, const MobileEntityDirection direction) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [pedestrian_id](const PedestrianInstance& pedestrian) {
        return pedestrian.id == pedestrian_id;
    });
    if (found == instances_.end() || found->state == PedestrianState::walking) return false;
    found->spatial.direction = direction;
    return true;
}

void PedestrianSystem::clear() { instances_.clear(); }

bool PedestrianSystem::rest_at_home(const NavigationTile entrance) {
    if (instances_.empty()) return false;
    PedestrianInstance& pedestrian = instances_.front();
    if (pedestrian.state != PedestrianState::idle ||
        pedestrian.spatial.logical_tile_x != entrance.x || pedestrian.spatial.logical_tile_y != entrance.y) return false;
    pedestrian.state = PedestrianState::resting;
    pedestrian.route.clear();
    pedestrian.next_waypoint = 0;
    return true;
}

void PedestrianSystem::wake_up() {
    if (!instances_.empty() && instances_.front().state == PedestrianState::resting) {
        instances_.front().state = PedestrianState::idle;
    }
}

MobileEntityDirection PedestrianSystem::direction_to(const NavigationTile from, const NavigationTile to) {
    if (to.x > from.x) return MobileEntityDirection::east;
    if (to.x < from.x) return MobileEntityDirection::west;
    return to.y > from.y ? MobileEntityDirection::south : MobileEntityDirection::north;
}

std::string_view PedestrianSystem::animation_state(const PedestrianState state) {
    return state == PedestrianState::walking ? "walking" : "idle";
}

bool PedestrianSystem::remaining_route_is_valid(const PedestrianInstance& pedestrian, const NavigationNetwork& network) {
    if (pedestrian.route.empty() || pedestrian.next_waypoint == 0 || pedestrian.next_waypoint >= pedestrian.route.size()) return true;
    for (std::size_t index = pedestrian.next_waypoint; index < pedestrian.route.size(); ++index) {
        const NavigationTile from = pedestrian.route[index - 1];
        const NavigationTile to = pedestrian.route[index];
        if (!network.is_navigable(from) || !network.is_navigable(to) ||
            !network.can_move(from, topology_direction_to(from, to))) return false;
    }
    return true;
}

bool PedestrianSystem::replan_once_or_stop(PedestrianInstance& pedestrian, const NavigationNetwork& network) {
    const NavigationTile current{pedestrian.spatial.logical_tile_x, pedestrian.spatial.logical_tile_y};
    pedestrian.spatial.logical_world_x = static_cast<float>(current.x);
    pedestrian.spatial.logical_world_y = static_cast<float>(current.y);
    if (pedestrian.replanned_after_network_change) {
        pedestrian.state = PedestrianState::idle;
        pedestrian.route.clear();
        pedestrian.next_waypoint = 0;
        return false;
    }
    pedestrian.replanned_after_network_change = true;
    const NavigationPathResult replacement = find_navigation_path(network, current, pedestrian.destination);
    if (replacement.status != NavigationPathStatus::found || replacement.tiles.size() <= 1) {
        pedestrian.state = PedestrianState::idle;
        pedestrian.route.clear();
        pedestrian.next_waypoint = 0;
        return false;
    }
    pedestrian.route = replacement.tiles;
    pedestrian.next_waypoint = 1;
    pedestrian.spatial.direction = direction_to(current, pedestrian.route.front() == current
        ? pedestrian.route[pedestrian.next_waypoint] : pedestrian.route.front());
    return true;
}

void PedestrianSystem::update_tick(const float tick_seconds, const NavigationNetwork& network) {
    for (PedestrianInstance& pedestrian : instances_) {
        if (pedestrian.state != PedestrianState::walking) continue;
        if (!remaining_route_is_valid(pedestrian, network) && !replan_once_or_stop(pedestrian, network)) continue;

        float remaining_distance = std::max(0.0F, tick_seconds) * pedestrian.speed;
        while (remaining_distance > 0.0F && pedestrian.state == PedestrianState::walking &&
               pedestrian.next_waypoint < pedestrian.route.size()) {
            const NavigationTile target = pedestrian.route[pedestrian.next_waypoint];
            const float target_x = static_cast<float>(target.x);
            const float target_y = static_cast<float>(target.y);
            const float distance_x = target_x - pedestrian.spatial.logical_world_x;
            const float distance_y = target_y - pedestrian.spatial.logical_world_y;
            const float distance = std::sqrt(distance_x * distance_x + distance_y * distance_y);
            if (distance <= 0.0001F) {
                pedestrian.spatial.logical_world_x = target_x;
                pedestrian.spatial.logical_world_y = target_y;
                pedestrian.spatial.logical_tile_x = target.x;
                pedestrian.spatial.logical_tile_y = target.y;
                ++pedestrian.next_waypoint;
                if (pedestrian.next_waypoint >= pedestrian.route.size()) {
                    pedestrian.state = PedestrianState::idle;
                } else {
                    pedestrian.spatial.direction = direction_to(target, pedestrian.route[pedestrian.next_waypoint]);
                }
                continue;
            }
            const float travel = std::min(remaining_distance, distance);
            pedestrian.spatial.direction = direction_to({pedestrian.spatial.logical_tile_x, pedestrian.spatial.logical_tile_y}, target);
            pedestrian.spatial.logical_world_x += distance_x / distance * travel;
            pedestrian.spatial.logical_world_y += distance_y / distance * travel;
            remaining_distance -= travel;
        }
    }
}

void PedestrianSystem::interpolate_visual(const float frame_seconds) {
    const float interpolation = std::clamp(frame_seconds * 10.0F, 0.0F, 1.0F);
    for (PedestrianInstance& pedestrian : instances_) {
        pedestrian.spatial.visual_world_x += (pedestrian.spatial.logical_world_x - pedestrian.spatial.visual_world_x) * interpolation;
        pedestrian.spatial.visual_world_y += (pedestrian.spatial.logical_world_y - pedestrian.spatial.visual_world_y) * interpolation;
    }
}

void PedestrianSystem::update_animation(const float frame_seconds, const MobileAnimationCatalog& animations) {
    for (PedestrianInstance& pedestrian : instances_) {
        animations.update_player(pedestrian.animation, animation_state(pedestrian.state), pedestrian.spatial.direction, frame_seconds);
    }
}

std::vector<MobileEntityRenderData> PedestrianSystem::render_entities(const MobileAnimationCatalog& animations,
                                                                      const bool raining) const {
    std::vector<MobileEntityRenderData> result;
    result.reserve(instances_.size());
    for (const PedestrianInstance& pedestrian : instances_) {
        MobileEntityRenderData entity;
        entity.spatial = pedestrian.spatial;
        entity.logical_state = std::string(animation_state(pedestrian.state));
        if (const std::string* frame = animations.current_frame(pedestrian.animation)) entity.sprite_asset = *frame;
        entity.animation_set_id = visual_definition_.animation_set_id;
        entity.animation_clip_id = pedestrian.animation.clip_id;
        entity.animation_frame_index = pedestrian.animation.frame_index;
        entity.art_scale = visual_definition_.art_scale;
        entity.sprite_anchor_x = visual_definition_.sprite_anchor_x;
        entity.sprite_anchor_y = visual_definition_.sprite_anchor_y;
        entity.clothing = pedestrian.clothing;
        entity.clothing.enabled = visual_definition_.animation_set_id == "ch_actor_green_01";
        entity.umbrella.enabled = entity.clothing.enabled && raining &&
            pedestrian.state != PedestrianState::visiting && pedestrian.state != PedestrianState::resting;
        entity.umbrella.fabric = pedestrian.umbrella_color;
        result.push_back(std::move(entity));
    }
    return result;
}

const std::vector<PedestrianInstance>& PedestrianSystem::instances() const { return instances_; }
