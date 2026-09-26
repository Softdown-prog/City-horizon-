"""Guarded CH Blender authoring for tactile gameplay selection-card chrome.

The building thumbnails stay unchanged. This asset only supplies the 3D-looking
selection boxes behind catalog items. Quality flow is mandatory:
    preflight -> SOUTH proxy showcase -> human review -> final state textures
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
for path in (HERE, CH_BLENDER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402


STATE_ORDER = ("normal", "hover", "selected", "disabled")


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--style-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def material(name: str, spec: dict):
    return bs.make_material(
        name,
        spec["rgba"],
        float(spec.get("roughness", 0.72)),
        float(spec.get("metallic", 0.0)),
    )


def local_box(parent, name: str, location, dimensions, mat, bevel: float, role: str):
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(float(v) for v in dimensions)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    obj.parent = parent
    obj.location = tuple(float(v) for v in location)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name="UiChromeBevel", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    scene_gate.tag(obj, role)
    return obj


def build_card(parent, state_id: str, card_cfg: dict, state_cfg: dict):
    width = float(card_cfg["width"])
    height = float(card_cfg["height"])
    depth = float(card_cfg["depth"])
    inset = float(card_cfg["inset"])
    rail = float(card_cfg["rail"])
    bevel = float(card_cfg["bevel"])

    mats = {
        key: material(f"{state_id}_{key}", state_cfg[key])
        for key in ("shadow", "base", "surface", "accent", "shade")
    }

    authored = []
    authored.append(local_box(
        parent,
        f"{state_id}_Shadow",
        (0.08, -0.08, -depth * 0.72),
        (width + 0.10, height + 0.10, depth * 0.42),
        mats["shadow"],
        bevel * 1.10,
        f"ui.selection_card.{state_id}.shadow",
    ))
    authored.append(local_box(
        parent,
        f"{state_id}_Base",
        (0.0, 0.0, 0.0),
        (width, height, depth),
        mats["base"],
        bevel,
        f"ui.selection_card.{state_id}.base",
    ))
    authored.append(local_box(
        parent,
        f"{state_id}_Surface",
        (0.0, 0.0, depth * 0.72),
        (width - inset * 2.0, height - inset * 2.0, depth * 0.34),
        mats["surface"],
        bevel * 0.72,
        f"ui.selection_card.{state_id}.surface",
    ))

    z_rail = depth * 1.03
    rail_long = width - inset * 2.4
    rail_short = height - inset * 2.4
    authored.append(local_box(
        parent,
        f"{state_id}_TopHighlight",
        (0.0, height * 0.5 - inset * 0.62, z_rail),
        (rail_long, rail, depth * 0.18),
        mats["accent"],
        rail * 0.45,
        f"ui.selection_card.{state_id}.highlight",
    ))
    authored.append(local_box(
        parent,
        f"{state_id}_LeftHighlight",
        (-width * 0.5 + inset * 0.62, 0.0, z_rail),
        (rail, rail_short, depth * 0.18),
        mats["accent"],
        rail * 0.45,
        f"ui.selection_card.{state_id}.highlight",
    ))
    authored.append(local_box(
        parent,
        f"{state_id}_BottomShade",
        (0.0, -height * 0.5 + inset * 0.62, z_rail * 0.96),
        (rail_long, rail, depth * 0.16),
        mats["shade"],
        rail * 0.45,
        f"ui.selection_card.{state_id}.shade",
    ))
    authored.append(local_box(
        parent,
        f"{state_id}_RightShade",
        (width * 0.5 - inset * 0.62, 0.0, z_rail * 0.96),
        (rail, rail_short, depth * 0.16),
        mats["shade"],
        rail * 0.45,
        f"ui.selection_card.{state_id}.shade",
    ))

    if state_id == "selected":
        authored.append(local_box(
            parent,
            "selected_OuterAccent",
            (0.0, 0.0, depth * 0.45),
            (width + 0.11, height + 0.11, depth * 0.12),
            mats["accent"],
            bevel * 1.18,
            "ui.selection_card.selected.outer_accent",
        ))
        # Keep the actual face above the outer selected frame.
        authored[-1].location.z = -depth * 0.20

    return authored


def render_final_states(scene, cfg: dict, groups: dict, state_objects: dict, out: Path):
    resolution = cfg.get("finalResolution", [512, 144])
    scene.render.resolution_x = int(resolution[0])
    scene.render.resolution_y = int(resolution[1])
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.camera.data.ortho_scale = float(cfg.get("finalOrthoScale", 1.55))

    original_locations = {state: groups[state].location.copy() for state in STATE_ORDER}
    try:
        for state in STATE_ORDER:
            for objects in state_objects.values():
                for obj in objects:
                    obj.hide_render = True
            for obj in state_objects[state]:
                obj.hide_render = False
            groups[state].location = (0.0, 0.0, 0.0)
            bpy.context.view_layer.update()
            scene.render.filepath = str(out / f"selection_card_{state}.png")
            bpy.ops.render.render(write_still=True)
            groups[state].location = original_locations[state]
    finally:
        for state, location in original_locations.items():
            groups[state].location = location
        for objects in state_objects.values():
            for obj in objects:
                obj.hide_render = False
        bpy.context.view_layer.update()


def main():
    args = parse_args()
    cfg = load_json(args.style_config)
    if cfg.get("contract") != "CH_UI_SELECTION_CARD_STYLE_V1":
        raise RuntimeError("Expected CH_UI_SELECTION_CARD_STYLE_V1 style config")

    studio = load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_resolution = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_resolution, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.camera.data.ortho_scale = float(cfg.get("proxyOrthoScale", 6.8))

    root = bpy.data.objects.new("AssetRoot", None)
    bpy.context.collection.objects.link(root)
    root.location = tuple(float(v) for v in studio["camera"]["target"])
    root.rotation_euler = scene.camera.rotation_euler.copy()
    root["assetId"] = cfg["assetId"]
    root["assetType"] = "ui.selection_card_set"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_ui_chrome"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    spacing = float(cfg["card"].get("showcaseSpacing", 1.50))
    offsets = {
        "normal": (0.0, spacing * 1.5, 0.0),
        "hover": (0.0, spacing * 0.5, 0.0),
        "selected": (0.0, -spacing * 0.5, 0.0),
        "disabled": (0.0, -spacing * 1.5, 0.0),
    }

    groups = {}
    state_objects = {}
    authored = []
    for state in STATE_ORDER:
        group = bpy.data.objects.new(f"CardState_{state}", None)
        bpy.context.collection.objects.link(group)
        group.parent = root
        group.location = offsets[state]
        groups[state] = group
        objects = build_card(group, state, cfg["card"], cfg["states"][state])
        state_objects[state] = objects
        authored.extend(objects)

    bpy.context.view_layer.update()
    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=cfg["footprint"],
        profile=profile,
        asset_id=cfg["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        print(f"[CH_GATE] UI selection-card preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=cfg["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        print(f"[CH_GATE] UI selection-card proxy ready: {proxy['sha256']}")
        return

    if not args.approval_proxy_sha:
        raise RuntimeError("Final stage requires --approval-proxy-sha")

    approval = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": cfg["assetId"],
        "reviewed": True,
        "proxySha256": args.approval_proxy_sha,
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval, indent=2), encoding="utf-8")
    metadata = {
        "contract": "CH_UI_SELECTION_CARD_FINAL_V1",
        "assetId": cfg["assetId"],
        "studio": studio.get("id"),
        "camera": studio.get("camera", {}).get("contract"),
        "visualContract": studio.get("visualContract"),
        "states": list(STATE_ORDER),
        "finalResolution": cfg.get("finalResolution", [512, 144]),
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    render_final_states(scene, cfg, groups, state_objects, out)
    print(f"[CH_GATE] UI selection-card final textures ready in {out}")


if __name__ == "__main__":
    main()
