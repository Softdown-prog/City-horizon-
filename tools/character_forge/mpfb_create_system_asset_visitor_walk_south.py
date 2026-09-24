"""Render the approved MPFB/MakeHuman visitor at compact gameplay scale.

Gate: SOUTH only.
Outputs one idle frame plus two conservative walk frames. The approved visual
identity is reused unchanged: male phenotype, system-asset outfit, hair, eyes,
shoes, City Horizon matte pass, canonical SOUTH camera and lighting.

Animation rules:
- two-frame walk (A/B)
- short stride
- minimal arm swing
- no root translation / no vertical bob
- 128x128 transparent gameplay frames
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mpfb_create_basic_human as base  # noqa: E402
import mpfb_create_system_asset_visitor as visitor  # noqa: E402


FRAME_RESOLUTION = 128
GAMEPLAY_ORTHO_SCALE = 5.6


def make_walk_pose(phase: int) -> dict:
    """Small, mirrored FK walk pose around the approved neutral idle.

    phase +1 = left leg forward/right leg back.
    phase -1 = mirror.
    No pelvis/root translation is used, which prevents sprite bobbing.
    """
    deg = math.radians
    stride = 11.0 * phase
    arm = 5.0 * phase

    # Start from the exact approved idle arm posture.
    idle = base.make_neutral_idle_pose()
    rotations = dict(idle["bone_rotations"])

    # Legs: intentionally conservative. X is the forward/back axis on the
    # default_no_toes MakeHuman FK rig. A small knee flex softens the trailing
    # leg without creating an exaggerated RPG stride.
    rotations.update(
        {
            "upperleg01.L": [deg(-stride), 0.0, 0.0],
            "upperleg01.R": [deg(stride), 0.0, 0.0],
            "lowerleg01.L": [deg(7.0 if phase < 0 else 3.0), 0.0, 0.0],
            "lowerleg01.R": [deg(7.0 if phase > 0 else 3.0), 0.0, 0.0],
            # Arms swing opposite the legs, only five degrees.
            "upperarm01.L": [deg(arm), 0.0, deg(-22.0)],
            "upperarm01.R": [deg(-arm), 0.0, deg(22.0)],
            "lowerarm01.L": [deg(-6.0), 0.0, 0.0],
            "lowerarm01.R": [deg(-6.0), 0.0, 0.0],
        }
    )

    return {
        "skeleton_type": "default_no_toes",
        "bone_rotations": rotations,
        "bone_rotation_modes": {name: "XYZ" for name in rotations},
        "bone_translations": {},
        "has_ik_bones": False,
        "original_spine_length": 0.0,
        "original_shoulder_width": 0.0,
    }


def render_frame(scene: bpy.types.Scene, camera: bpy.types.Object, output: Path) -> None:
    scene.render.resolution_x = FRAME_RESOLUTION
    scene.render.resolution_y = FRAME_RESOLUTION
    scene.render.resolution_percentage = 100
    camera.data.ortho_scale = GAMEPLAY_ORTHO_SCALE
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


def build_character():
    extension_module = base.find_mpfb_extension_module()
    base.ensure_mpfb_enabled(extension_module)
    base.clear_scene_objects()

    HumanService = base.import_symbol(extension_module, "services.humanservice", "HumanService")
    TargetService = base.import_symbol(extension_module, "services.targetservice", "TargetService")
    RigService = base.import_symbol(extension_module, "services.rigservice", "RigService")
    AssetService = base.import_symbol(extension_module, "services.assetservice", "AssetService")
    HumanObjectProperties = base.import_symbol(
        extension_module, "entities.objectproperties", "HumanObjectProperties"
    )

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_Approved_Base_01"
    for key, value in base.MALE_PHENOTYPE.items():
        HumanObjectProperties.set_value(key, value, entity_reference=human)
    TargetService.reapply_macro_details(human)
    bpy.context.view_layer.update()

    phenotype = {
        key: HumanObjectProperties.get_value(key, entity_reference=human)
        for key in base.MALE_PHENOTYPE
    }

    rig = HumanService.add_builtin_rig(human, "default_no_toes")
    assets = visitor.add_system_assets(HumanService, AssetService, human)
    visitor.set_skin_material(human)
    bpy.context.view_layer.update()

    camera = base.setup_camera_and_light(human)
    scene = bpy.context.scene
    visitor.configure_render(scene)
    return extension_module, human, rig, RigService, assets, phenotype, camera, scene


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    output_value = argv[0] if argv else os.environ.get(
        "CH_AGENT_OUTPUT_DIR",
        "out/ch_blender_agent/character.forge.mpfb.visitor.walk.south.manual",
    )
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    (
        extension_module,
        human,
        rig,
        RigService,
        assets,
        phenotype,
        camera,
        scene,
    ) = build_character()

    frames = [
        ("idle", base.make_neutral_idle_pose()),
        ("walk_a", make_walk_pose(+1)),
        ("walk_b", make_walk_pose(-1)),
    ]

    outputs = {}
    for frame_name, pose in frames:
        base.apply_idle_pose(RigService, rig, pose)
        bpy.context.view_layer.update()
        path = output_dir / f"visitor_male_south_{frame_name}.png"
        render_frame(scene, camera, path)
        outputs[frame_name] = path.name

    report = {
        "contract": "CH_CHARACTER_FORGE_VISITOR_SOUTH_WALK_V1",
        "status": "ok",
        "approvedBase": "visitor_male_system_assets",
        "direction": "south",
        "visualIdentityChanged": False,
        "phenotypeApplied": phenotype,
        "rig": "default_no_toes",
        "assets": assets,
        "gameplayFrame": {
            "resolution": [FRAME_RESOLUTION, FRAME_RESOLUTION],
            "orthoScale": GAMEPLAY_ORTHO_SCALE,
            "transparent": True,
            "scalePolicy": "same approved camera framing, half-resolution compact gameplay canvas",
        },
        "animation": {
            "idleFrames": 1,
            "walkFrames": 2,
            "recommendedFrameDurationMs": 220,
            "loop": "A-B-A-B",
            "strideDegrees": 11.0,
            "armSwingDegrees": 5.0,
            "rootTranslation": [0.0, 0.0, 0.0],
            "verticalBob": False,
        },
        "outputs": outputs,
        "runtimePromotion": False,
        "nextGate": "validate SOUTH size and walk silhouette before EAST/WEST/NORTH",
    }
    report_path = output_dir / "visitor_male_south_walk.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
