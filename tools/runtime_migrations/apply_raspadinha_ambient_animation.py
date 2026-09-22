#!/usr/bin/env python3
"""One-shot guarded migration for stateful ambient building sprite playback.

This script intentionally uses exact source contracts and fails instead of
silently editing an unexpected revision. The workflow that invokes it removes
both the script and itself after the source patch lands.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"CH_RUNTIME_ANIM_PATCH_MISMATCH: {path}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


header = ROOT / "src/building_system.h"
replace_once(
    header,
    '''struct BuildingAnimationDefinition {\n    int frame_count = 1;\n    int frame_duration_ms = 120;\n    std::string layout = "horizontal";\n};''',
    '''struct BuildingAnimationDefinition {\n    int frame_count = 1;\n    int frame_duration_ms = 120;\n    std::string layout = "horizontal";\n    // "loop" preserves the legacy continuous animation contract.\n    // "ambient_once" holds an idle frame, plays one action sequence, then\n    // returns to idle before the next deterministic ambient cycle.\n    std::string playback = "loop";\n    int idle_frame = 0;\n    int action_start_frame = 1;\n    int action_frame_count = 0;\n    int idle_hold_ms = 0;\n};''',
)

source = ROOT / "src/building_system.cpp"
replace_once(
    source,
    '''    if (const auto anim = json_object(json, "animation")) {\n        const int frame_count = json_number<int>(*anim, "frameCount").value_or(1);\n        const int frame_duration_ms = json_number<int>(*anim, "frameDurationMs").value_or(120);\n        const std::string layout = json_string(*anim, "layout").value_or("horizontal");\n        if (frame_count > 1) {\n            definition.animation = {frame_count, frame_duration_ms, layout};\n        }\n    }''',
    '''    if (const auto anim = json_object(json, "animation")) {\n        const int frame_count = json_number<int>(*anim, "frameCount").value_or(1);\n        if (frame_count > 1) {\n            BuildingAnimationDefinition parsed_animation;\n            parsed_animation.frame_count = frame_count;\n            parsed_animation.frame_duration_ms =\n                std::max(1, json_number<int>(*anim, "frameDurationMs").value_or(120));\n            parsed_animation.layout = json_string(*anim, "layout").value_or("horizontal");\n            parsed_animation.playback = json_string(*anim, "playback").value_or("loop");\n            if (parsed_animation.playback != "loop" && parsed_animation.playback != "ambient_once") {\n                return std::nullopt;\n            }\n            parsed_animation.idle_frame = std::clamp(\n                json_number<int>(*anim, "idleFrame").value_or(0), 0, frame_count - 1);\n            parsed_animation.action_start_frame = std::clamp(\n                json_number<int>(*anim, "actionStartFrame").value_or(1), 0, frame_count - 1);\n            const int available_action_frames = frame_count - parsed_animation.action_start_frame;\n            parsed_animation.action_frame_count = std::clamp(\n                json_number<int>(*anim, "actionFrameCount").value_or(available_action_frames),\n                0, available_action_frames);\n            parsed_animation.idle_hold_ms =\n                std::max(0, json_number<int>(*anim, "idleHoldMs").value_or(0));\n            definition.animation = parsed_animation;\n        }\n    }''',
)

renderer = ROOT / "src/ch_render/map_renderer.cpp"
replace_once(
    renderer,
    '''#include <array>\n#include <cmath>\n#include <iomanip>''',
    '''#include <array>\n#include <cmath>\n#include <cstdint>\n#include <iomanip>''',
)
replace_once(
    renderer,
    '''    if (definition.animation.has_value() && definition.animation->frame_count > 1) {\n        const int frame_count = std::max(1, definition.animation->frame_count);\n        const int duration_ms = std::max(1, definition.animation->frame_duration_ms);\n        const int frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);\n        const float frame_w = source_width / static_cast<float>(frame_count);\n        const float frame_h = source_height;\n        const SDL_FRect src_rect = { frame_index * frame_w, 0.0F, frame_w, frame_h };\n        SDL_RenderTexture(renderer, texture, &src_rect, &geometry.sprite_bounds);\n    } else {''',
    '''    if (definition.animation.has_value() && definition.animation->frame_count > 1) {\n        const BuildingAnimationDefinition& animation = *definition.animation;\n        const int frame_count = std::max(1, animation.frame_count);\n        const int duration_ms = std::max(1, animation.frame_duration_ms);\n        int frame_index = 0;\n\n        if (animation.playback == "ambient_once") {\n            const int idle_frame = std::clamp(animation.idle_frame, 0, frame_count - 1);\n            const int action_start = std::clamp(animation.action_start_frame, 0, frame_count - 1);\n            const int action_count = std::clamp(animation.action_frame_count, 0, frame_count - action_start);\n            frame_index = idle_frame;\n\n            if (action_count > 0) {\n                const std::uint64_t idle_hold_ms = static_cast<std::uint64_t>(std::max(0, animation.idle_hold_ms));\n                const std::uint64_t action_duration_ms =\n                    static_cast<std::uint64_t>(action_count) * static_cast<std::uint64_t>(duration_ms);\n                const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;\n                // Stable per-instance staggering avoids a row of vendors waving\n                // in perfect synchrony while remaining deterministic across runs.\n                const std::uint64_t instance_offset_ms = instance.instance_id * 977ULL;\n                const std::uint64_t phase_ms = cycle_duration_ms > 0\n                    ? (static_cast<std::uint64_t>(SDL_GetTicks()) + instance_offset_ms) % cycle_duration_ms\n                    : 0;\n                if (phase_ms >= idle_hold_ms && action_duration_ms > 0) {\n                    const std::uint64_t action_elapsed_ms = phase_ms - idle_hold_ms;\n                    const int action_index = std::min(\n                        action_count - 1,\n                        static_cast<int>(action_elapsed_ms / static_cast<std::uint64_t>(duration_ms)));\n                    frame_index = action_start + action_index;\n                }\n            }\n        } else {\n            // Legacy behaviour: every multi-frame building keeps looping exactly\n            // as before unless its data explicitly opts into ambient_once.\n            frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);\n        }\n\n        const float frame_w = source_width / static_cast<float>(frame_count);\n        const float frame_h = source_height;\n        const SDL_FRect src_rect = { frame_index * frame_w, 0.0F, frame_w, frame_h };\n        SDL_RenderTexture(renderer, texture, &src_rect, &geometry.sprite_bounds);\n    } else {''',
)

print("CH_RUNTIME_ANIM_PATCH_OK")
