"""Proxy render must leave the authored scene exactly as it found it."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


class ProxyStateTests(unittest.TestCase):
    def test_restores_render_settings_and_visibility_on_failure(self):
        visible = types.SimpleNamespace(type="MESH", name="Visible", hide_render=False)
        hidden = types.SimpleNamespace(type="MESH", name="Hidden", hide_render=True)
        ground = types.SimpleNamespace(hide_render=True)
        settings = types.SimpleNamespace(color_mode="RGB", file_format="OPEN_EXR")
        render = types.SimpleNamespace(engine="CYCLES", resolution_x=640, resolution_y=480,
                                       resolution_percentage=75, filepath="original.exr",
                                       film_transparent=False, image_settings=settings)
        scene = types.SimpleNamespace(render=render, cycles=types.SimpleNamespace(samples=32))

        bpy = types.ModuleType("bpy")
        bpy.data = types.SimpleNamespace(objects={"ShadowReceiverPlane": ground})

        bpy.ops = types.SimpleNamespace(render=types.SimpleNamespace(render=lambda **_: (_ for _ in ()).throw(RuntimeError("simulated render failure"))))
        extras = types.ModuleType("bpy_extras")
        object_utils = types.ModuleType("bpy_extras.object_utils")
        object_utils.world_to_camera_view = lambda *_: None
        mathutils = types.ModuleType("mathutils")
        mathutils.Vector = object
        with patch.dict(sys.modules, {"bpy": bpy, "bpy_extras": extras,
                                      "bpy_extras.object_utils": object_utils, "mathutils": mathutils}):
            spec = importlib.util.spec_from_file_location("ch_scene_gate_proxy_test", ROOT / "tools/ch_blender/scene_gate.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(RuntimeError, "simulated render failure"):
                    module.render_proxy(scene=scene, authored=[visible, hidden],
                                        output_path=str(Path(tmp) / "proxy.png"))

        self.assertEqual((render.engine, render.resolution_x, render.resolution_y,
                          render.resolution_percentage, render.filepath),
                         ("CYCLES", 640, 480, 75, "original.exr"))
        self.assertEqual((render.film_transparent, settings.color_mode, settings.file_format,
                          scene.cycles.samples), (False, "RGB", "OPEN_EXR", 32))
        self.assertFalse(visible.hide_render)
        self.assertTrue(hidden.hide_render)
        self.assertTrue(ground.hide_render)


if __name__ == "__main__":
    unittest.main()
