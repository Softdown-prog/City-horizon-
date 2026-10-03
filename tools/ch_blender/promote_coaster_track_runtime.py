#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runtime_path = ROOT / 'src/main_runtime_impl.cpp'
ci_path = ROOT / '.github/workflows/ch-coaster-runtime-check.yml'

runtime = runtime_path.read_text(encoding='utf-8')
old_render = '''        const std::vector<MobileEntityRenderData> mobile_entities = mobile_render_entities();
        const ch::coaster::TrainStepResult coaster_train = coaster_preview_enabled && coaster_runtime.ready()
            ? coaster_runtime.snapshot(static_cast<int>(camera_rotation_turns(camera.rotation)))
            : ch::coaster::TrainStepResult{};
        render_world_entities(renderer, buildings, catalog, lands, mobile_entities,
'''
new_render = '''        const std::vector<MobileEntityRenderData> mobile_entities = mobile_render_entities();
        const ch::coaster::TrainStepResult coaster_train = coaster_preview_enabled && coaster_runtime.ready()
            ? coaster_runtime.snapshot(static_cast<int>(camera_rotation_turns(camera.rotation)))
            : ch::coaster::TrainStepResult{};
        if (coaster_preview_enabled && coaster_runtime.ready()) {
            const ch::CameraState coaster_camera{
                camera.pan_x, camera.pan_y, camera.zoom,
                static_cast<ch::CameraRotation>(camera.rotation)};
            ch::coaster::render_coaster_track(
                renderer, coaster_runtime.track_geometry(), coaster_camera,
                static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        }
        render_world_entities(renderer, buildings, catalog, lands, mobile_entities,
'''
if runtime.count(old_render) != 1:
    raise SystemExit(f'expected exactly one runtime render marker, found {runtime.count(old_render)}')
runtime = runtime.replace(old_render, new_render, 1)
runtime = runtime.replace(
    '// CH_COASTER_RENDER_LINK_V1: until the track construction system owns a\n'
    '    // production centerline, P toggles a deterministic render-validation loop.\n'
    '    // The train still uses the real articulated runtime, pose atlas and world\n'
    '    // entity depth queue; only the temporary route source is developer-only.\n',
    '// CH_COASTER_RENDER_LINK_V3: until the track construction system owns a\n'
    '    // production centerline, P toggles a deterministic render-validation loop.\n'
    '    // Track and train now share the real coaster runtime route, native\n'
    '    // CH_COASTER_TRACK_GEOMETRY_V1 geometry, camera, and articulated cars.\n'
    '    // Only the temporary preview route source remains developer-only.\n',
    1,
)
runtime_path.write_text(runtime, encoding='utf-8')

ci = ci_path.read_text(encoding='utf-8')
old_guard = '''              'runtime update': 'coaster_runtime.update',
              'camera-aware snapshot': 'coaster_runtime.snapshot',
              'preview toggle': 'SDL_SCANCODE_P',
'''
new_guard = '''              'runtime update': 'coaster_runtime.update',
              'camera-aware snapshot': 'coaster_runtime.snapshot',
              'owned track geometry': 'coaster_runtime.track_geometry()',
              'native track renderer': 'render_coaster_track(',
              'preview toggle': 'SDL_SCANCODE_P',
'''
if ci.count(old_guard) != 1:
    raise SystemExit(f'expected exactly one runtime CI marker, found {ci.count(old_guard)}')
ci = ci.replace(old_guard, new_guard, 1)
ci = ci.replace("print('CH_COASTER_RENDER_LINK_V2 integration: OK')",
                "print('CH_COASTER_RENDER_LINK_V3 track + train integration: OK')", 1)
ci_path.write_text(ci, encoding='utf-8')

print('CH_COASTER_RENDER_LINK_V3 promotion patch: OK')
