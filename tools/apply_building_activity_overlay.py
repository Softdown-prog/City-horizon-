from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Building contract and transient activity state
# -----------------------------------------------------------------------------
header_path = Path("src/building_system.h")
header = header_path.read_text(encoding="utf-8")

animation_anchor = '''struct BuildingAnimationDefinition {
    int frame_count = 1;
    int frame_duration_ms = 120;
    std::string layout = "horizontal";
    // "loop" preserves the legacy continuous animation contract.
    // "ambient_once" holds an idle frame, plays one action sequence, then
    // returns to idle before the next deterministic ambient cycle.
    std::string playback = "loop";
    int idle_frame = 0;
    int action_start_frame = 1;
    int action_frame_count = 0;
    int idle_hold_ms = 0;
};
'''
header = replace_once(
    header,
    animation_anchor,
    animation_anchor
    + '''
// CH_BUILDING_ACTIVITY_OVERLAY_V1. Transparent temporary visual activity,
// authored per rotation and deliberately independent from CH_COLOR_MASK_V1.
struct BuildingActivityOverlayDefinition {
    bool enabled = false;
    std::array<std::string, 4> sprite_paths;
    std::optional<BuildingAnimationDefinition> animation;
};
''',
    "BuildingAnimationDefinition",
)

header = replace_once(
    header,
    '''    std::optional<BuildingAnimationDefinition> animation;
    std::optional<BuildingColorMaskDefinition> color_mask;
''',
    '''    std::optional<BuildingAnimationDefinition> animation;
    std::optional<BuildingColorMaskDefinition> color_mask;
    std::optional<BuildingActivityOverlayDefinition> activity_overlay;
''',
    "BuildingDefinition activity_overlay",
)

header = replace_once(
    header,
    '''    BuildingColorTint wall_tint{};
    BuildingColorTint roof_tint{};
    [[nodiscard]] bool is_max_level(const BuildingDefinition& definition) const;
''',
    '''    BuildingColorTint wall_tint{};
    BuildingColorTint roof_tint{};

    // Runtime-only usage state. Multiple visitors may overlap; the overlay
    // remains active until the final activity source leaves.
    std::uint32_t activity_count = 0;
    [[nodiscard]] bool activity_active() const noexcept { return activity_count > 0; }

    [[nodiscard]] bool is_max_level(const BuildingDefinition& definition) const;
''',
    "BuildingInstance activity state",
)

header = replace_once(
    header,
    '''    [[nodiscard]] bool set_operational(std::uint64_t instance_id, bool operational);
    [[nodiscard]] bool set_service_price(std::uint64_t instance_id, const BuildingDefinition& definition,
''',
    '''    [[nodiscard]] bool set_operational(std::uint64_t instance_id, bool operational);
    [[nodiscard]] bool begin_activity(std::uint64_t instance_id);
    [[nodiscard]] bool end_activity(std::uint64_t instance_id);
    [[nodiscard]] bool set_service_price(std::uint64_t instance_id, const BuildingDefinition& definition,
''',
    "BuildingManager activity API",
)
header_path.write_text(header, encoding="utf-8")


# -----------------------------------------------------------------------------
# JSON parser + manager behavior
# -----------------------------------------------------------------------------
impl_path = Path("src/building_system.cpp")
impl = impl_path.read_text(encoding="utf-8")

parser_anchor = '''            definition.color_mask = mask;
        }
    }

    if (const auto serialized_access_points = json_array_objects(json, "accessPoints")) {
'''
activity_parser = '''            definition.color_mask = mask;
        }
    }

    if (const auto serialized_activity = json_object(json, "activityOverlay")) {
        const bool enabled = json_bool(*serialized_activity, "enabled").value_or(true);
        if (enabled) {
            if (json_string(*serialized_activity, "contract").value_or("") !=
                "CH_BUILDING_ACTIVITY_OVERLAY_V1") {
                return std::nullopt;
            }
            const auto activity_sprites = json_object(*serialized_activity, "sprites");
            if (!activity_sprites) return std::nullopt;

            BuildingActivityOverlayDefinition activity;
            activity.enabled = true;
            for (std::size_t index = 0; index < activity.sprite_paths.size(); ++index) {
                activity.sprite_paths[index] =
                    json_string(*activity_sprites, std::to_string(index)).value_or("");
                // Never mirror or synthesize an overlay for an authored orientation.
                if (definition.available_rotations[index] && activity.sprite_paths[index].empty()) {
                    return std::nullopt;
                }
            }

            if (const auto overlay_animation = json_object(*serialized_activity, "animation")) {
                const int frame_count = json_number<int>(*overlay_animation, "frameCount").value_or(1);
                if (frame_count < 1) return std::nullopt;
                if (frame_count > 1) {
                    BuildingAnimationDefinition parsed_animation;
                    parsed_animation.frame_count = frame_count;
                    parsed_animation.frame_duration_ms = std::max(
                        1, json_number<int>(*overlay_animation, "frameDurationMs").value_or(120));
                    parsed_animation.layout =
                        json_string(*overlay_animation, "layout").value_or("horizontal");
                    parsed_animation.playback =
                        json_string(*overlay_animation, "playback").value_or("loop");
                    if (parsed_animation.layout != "horizontal" ||
                        (parsed_animation.playback != "loop" && parsed_animation.playback != "ambient_once")) {
                        return std::nullopt;
                    }
                    parsed_animation.idle_frame = std::clamp(
                        json_number<int>(*overlay_animation, "idleFrame").value_or(0), 0, frame_count - 1);
                    parsed_animation.action_start_frame = std::clamp(
                        json_number<int>(*overlay_animation, "actionStartFrame").value_or(1), 0, frame_count - 1);
                    const int available_action_frames = frame_count - parsed_animation.action_start_frame;
                    parsed_animation.action_frame_count = std::clamp(
                        json_number<int>(*overlay_animation, "actionFrameCount").value_or(available_action_frames),
                        0, available_action_frames);
                    parsed_animation.idle_hold_ms = std::max(
                        0, json_number<int>(*overlay_animation, "idleHoldMs").value_or(0));
                    activity.animation = parsed_animation;
                }
            }
            definition.activity_overlay = activity;
        }
    }

    if (const auto serialized_access_points = json_array_objects(json, "accessPoints")) {
'''
impl = replace_once(impl, parser_anchor, activity_parser, "activityOverlay parser")

impl = replace_once(
    impl,
    '''    BuildingInstance instance = serialized;
    if (!definition.rotatable) {
''',
    '''    BuildingInstance instance = serialized;
    // Activity represents visitors currently inside and is intentionally not
    // restored from a save session.
    instance.activity_count = 0;
    if (!definition.rotatable) {
''',
    "restore transient activity",
)

service_anchor = '''bool BuildingManager::set_service_price(const std::uint64_t instance_id, const BuildingDefinition& definition,
                                        const std::int64_t service_price) {
'''
activity_methods = '''bool BuildingManager::begin_activity(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    if (found->activity_count < std::numeric_limits<std::uint32_t>::max()) {
        ++found->activity_count;
    }
    return true;
}

bool BuildingManager::end_activity(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end() || found->activity_count == 0) return false;
    --found->activity_count;
    return true;
}

'''
impl = replace_once(impl, service_anchor, activity_methods + service_anchor, "activity manager methods")
impl_path.write_text(impl, encoding="utf-8")


# -----------------------------------------------------------------------------
# Renderer activity pass
# -----------------------------------------------------------------------------
renderer_path = Path("src/ch_render/map_renderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
render_call = '''            render_building(renderer, *definition, *instance, visual_rot, texture->texture, texture->source_width, texture->source_height,
                            camera, viewport_width, viewport_height, SDL_ALPHA_OPAQUE, r, g, b);
'''
overlay_pass = '''

            // CH_BUILDING_ACTIVITY_OVERLAY_V1: transparent temporary effects are
            // rendered over the approved base sprite only while the instance is active.
            if (instance->activity_active() && definition->activity_overlay.has_value() &&
                definition->activity_overlay->enabled) {
                const BuildingActivityOverlayDefinition& activity = *definition->activity_overlay;
                const std::size_t activity_rotation = static_cast<std::size_t>(visual_rot);
                if (activity_rotation < activity.sprite_paths.size() &&
                    !activity.sprite_paths[activity_rotation].empty()) {
                    const TextureAsset* overlay_texture =
                        find_texture(asset_root / activity.sprite_paths[activity_rotation]);
                    if (overlay_texture != nullptr) {
                        // Use the base sprite frame geometry so the effect shares the
                        // exact same ground anchor, scale and rotation alignment.
                        const BuildingSpriteGeometry geometry = building_sprite_geometry(
                            *definition, *instance, visual_rot,
                            texture->source_width, texture->source_height,
                            camera, viewport_width, viewport_height);
                        SDL_Texture* overlay = overlay_texture->texture;
                        SDL_SetTextureAlphaMod(overlay, SDL_ALPHA_OPAQUE);
                        SDL_SetTextureColorMod(overlay, 255, 255, 255);

                        if (activity.animation.has_value() && activity.animation->frame_count > 1) {
                            const BuildingAnimationDefinition& animation = *activity.animation;
                            const int frame_count = std::max(1, animation.frame_count);
                            const int duration_ms = std::max(1, animation.frame_duration_ms);
                            int frame_index = 0;

                            if (animation.playback == "ambient_once") {
                                const int idle_frame = std::clamp(animation.idle_frame, 0, frame_count - 1);
                                const int action_start = std::clamp(
                                    animation.action_start_frame, 0, frame_count - 1);
                                const int action_count = std::clamp(
                                    animation.action_frame_count, 0, frame_count - action_start);
                                frame_index = idle_frame;
                                if (action_count > 0) {
                                    const std::uint64_t idle_hold_ms = static_cast<std::uint64_t>(
                                        std::max(0, animation.idle_hold_ms));
                                    const std::uint64_t action_duration_ms =
                                        static_cast<std::uint64_t>(action_count) *
                                        static_cast<std::uint64_t>(duration_ms);
                                    const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;
                                    const std::uint64_t phase_ms = cycle_duration_ms > 0
                                        ? (static_cast<std::uint64_t>(SDL_GetTicks()) +
                                           instance->instance_id * 977ULL) % cycle_duration_ms
                                        : 0;
                                    if (phase_ms >= idle_hold_ms && action_duration_ms > 0) {
                                        frame_index = action_start + std::min(
                                            action_count - 1,
                                            static_cast<int>((phase_ms - idle_hold_ms) /
                                                             static_cast<std::uint64_t>(duration_ms)));
                                    }
                                }
                            } else {
                                frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);
                            }

                            const float frame_width =
                                overlay_texture->source_width / static_cast<float>(frame_count);
                            const SDL_FRect source = {
                                frame_width * frame_index,
                                0.0F,
                                frame_width,
                                overlay_texture->source_height,
                            };
                            SDL_RenderTexture(renderer, overlay, &source, &geometry.sprite_bounds);
                        } else {
                            SDL_RenderTexture(renderer, overlay, nullptr, &geometry.sprite_bounds);
                        }

                        SDL_SetTextureColorMod(overlay, 255, 255, 255);
                        SDL_SetTextureAlphaMod(overlay, SDL_ALPHA_OPAQUE);
                    }
                }
            }
'''
renderer = replace_once(renderer, render_call, render_call + overlay_pass, "renderer activity pass")
renderer_path.write_text(renderer, encoding="utf-8")


# -----------------------------------------------------------------------------
# Canonical authoring contract
# -----------------------------------------------------------------------------
doc = Path("docs/BUILDING_ACTIVITY_OVERLAY_V1.md")
doc.write_text(
    '''# CH_BUILDING_ACTIVITY_OVERLAY_V1

Status: runtime contract v1.

This contract defines transparent RGBA layers for temporary building activity:
window/light glow, steam, door motion, machinery, signs, or similar small effects.
The base building remains unchanged. Activity overlays are not color masks.

## Runtime order

1. Render the approved building sprite.
2. Apply normal building customization/state passes.
3. When `BuildingInstance::activity_count > 0`, render `activityOverlay`.
4. Continue with normal selection/debug presentation.

The activity counter is transient. Save restoration resets it to zero.

## Building definition

```json
"activityOverlay": {
  "contract": "CH_BUILDING_ACTIVITY_OVERLAY_V1",
  "enabled": true,
  "sprites": {
    "0": "assets/buildings/example/example_south_activity.png",
    "1": "assets/buildings/example/example_west_activity.png",
    "2": "assets/buildings/example/example_north_activity.png",
    "3": "assets/buildings/example/example_east_activity.png"
  },
  "animation": {
    "layout": "horizontal",
    "frameCount": 4,
    "frameDurationMs": 160,
    "playback": "loop"
  }
}
```

`animation` is optional. A static overlay is the preferred form for a simple
state such as an illuminated window. Animated overlays use the same horizontal
spritesheet timing model already used by building animations (`loop` or
`ambient_once`).

## Art rules

- PNG RGBA with transparent background.
- Draw only the temporary effect; do not duplicate the whole building.
- Provide one overlay for every rotation supported by the building.
- Each overlay frame must use the same canvas and ground anchor as the matching
  base-building frame. Runtime never mirrors, rotates, or invents alignment.
- All frames of an animated overlay use the same canvas dimensions.
- `CH_COLOR_MASK_V1` remains reserved for permanent wall/roof recoloring.

## Gameplay trigger

`BuildingManager::begin_activity(instance_id)` increments the per-instance
activity counter. `BuildingManager::end_activity(instance_id)` decrements it.
This means overlapping visitors are safe: the effect is removed only when the
last activity source leaves.

The renderer does not know why the building is active. A pedestrian/customer
system, production system, scripted event, or another gameplay system can use
the same trigger without coupling itself to rendering.
''',
    encoding="utf-8",
)
