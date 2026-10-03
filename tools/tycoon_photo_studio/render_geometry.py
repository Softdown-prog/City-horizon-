"""Blender-independent framing math shared by bake, proxy and review tools."""
from __future__ import annotations

import hashlib
import json
import math


def source_resolution_for(final, minimum=(1024, 1024), supersample=4, cap=4096):
    """Use one integer scale on BOTH axes; independent power-of-two rounding stretches sprites."""
    width, height = map(int, final)
    if min(width, height) <= 0 or max(width, height) > cap:
        raise ValueError("Final resolution must be positive and fit the source resolution cap")
    scale = max(int(supersample), math.ceil(minimum[0] / width), math.ceil(minimum[1] / height))
    scale = min(scale, cap // max(width, height))
    if scale < 1 or width * scale < minimum[0] or height * scale < minimum[1]:
        raise ValueError("Source minimum and aspect ratio cannot both fit the resolution cap")
    return width * scale, height * scale


def ortho_spans(scale, resolution, sensor_fit="AUTO", pixel_aspect=(1.0, 1.0)):
    """Blender AUTO sensor fit uses the horizontal span for landscape frames."""
    aspect = resolution[0] * pixel_aspect[0] / (resolution[1] * pixel_aspect[1])
    horizontal = sensor_fit == "HORIZONTAL" or (sensor_fit == "AUTO" and aspect >= 1.0)
    return (scale, scale / aspect) if horizontal else (scale * aspect, scale)


def fit_ortho_scale(half_x, half_y, resolution, margin=0.12, sensor_fit="AUTO", pixel_aspect=(1.0, 1.0)):
    span_x, span_y = ortho_spans(1.0, resolution, sensor_fit, pixel_aspect)
    return max(2.0 * half_x / span_x, 2.0 * half_y / span_y) * (1.0 + margin)


def proxy_resolution_for(source, long_edge):
    """Preserve the bake camera aspect, including rectangular building frames."""
    width, height = map(int, source)
    long_edge = int(long_edge)
    if min(width, height, long_edge) <= 0:
        raise ValueError("Proxy/source resolutions must be positive")
    divisor = math.gcd(width, height)
    unit_x, unit_y = width // divisor, height // divisor
    scale = max(1, long_edge // max(unit_x, unit_y))
    return unit_x * scale, unit_y * scale


def require_same_aspect(source, final):
    if source[0] * final[1] != source[1] * final[0]:
        raise ValueError(f"CH_RENDER_ASPECT: source {tuple(source)} and final {tuple(final)} would stretch the asset")


def validate_studio_camera(studio):
    camera = studio.get("camera", {})
    if (camera.get("contract") != "CH_CAMERA_V1" or
            camera.get("projection") != "orthographic_dimetric_2_to_1" or
            not math.isclose(float(camera.get("yawDegrees", 0)), 45.0, abs_tol=0.001) or
            not math.isclose(float(camera.get("elevationDegrees", 0)), 30.0, abs_tol=0.001)):
        raise ValueError("CH_CAMERA_V1 requires orthographic 45 degree yaw / 30 degree elevation")


def studio_fingerprint(studio):
    """Identify actual lighting/color settings; identical preset IDs are not proof of equivalence."""
    render = studio.get("render", {})
    signature = {"world": studio.get("world"), "lights": studio.get("lights"),
                 "colorManagement": {key: render.get(key) for key in
                                     ("viewTransform", "look", "exposure", "gamma")}}
    return hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def scene_studio_state(scene):
    """Capture fixed studio data while allowing resolution and ortho framing changes."""
    background = scene.world.node_tree.nodes.get("Background") if scene.world and scene.world.use_nodes else None
    state = {"camera": [list(row) for row in scene.camera.matrix_world] if scene.camera else None,
             "lights": [{"name": obj.name, "matrix": [list(row) for row in obj.matrix_world],
                         "energy": obj.data.energy, "color": list(obj.data.color), "type": obj.data.type,
                         "size": getattr(obj.data, "size", None), "hidden": obj.hide_render}
                        for obj in scene.objects if obj.type == "LIGHT"],
             "worldColor": list(background.inputs["Color"].default_value) if background else None,
             "worldStrength": background.inputs["Strength"].default_value if background else None,
             "viewTransform": scene.view_settings.view_transform, "look": scene.view_settings.look,
             "exposure": scene.view_settings.exposure, "gamma": scene.view_settings.gamma}
    return json.dumps(state, sort_keys=True)
