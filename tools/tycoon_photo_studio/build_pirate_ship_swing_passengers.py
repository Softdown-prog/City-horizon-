#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

import build_pirate_ship_four_directions as current
import build_coaster_car_flame_passenger_overlay_v1_guarded as coaster_passengers

base = current.base

ANIMATION_CONTRACT = "CH_PIRATE_SHIP_SWING_PASSENGER_V1"
PASSENGER_CONTRACT = "CH_PIRATE_SHIP_PASSENGER_OVERLAY_V1"
COLOR_MASK_CONTRACT = "CH_RIDE_COLOR_MASK_V1"
FRAME_COUNT = 12
FPS = 8
AMPLITUDE_DEGREES = 35.0
CAPACITY = 24

# Frozen from the human-approved Viking V15 swing review. Do not retime this
# cycle without another visual approval pass.
APPROVED_SWING_ANGLES = [
    0.0, 17.5, 30.310889, 35.0, 30.310889, 17.5,
    0.0, -17.5, -30.310889, -35.0, -30.310889, -17.5,
]

JACKET_COLORS = coaster_passengers.JACKET_COLORS
PANTS_COLORS = coaster_passengers.PANTS_COLORS
SKIN = coaster_passengers.SKIN
HAIR = coaster_passengers.HAIR
SHOES = coaster_passengers.SHOES


def angles() -> list[float]:
    return list(APPROVED_SWING_ANGLES)


def _material(name, rgba):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    return base.bs.make_material(name, list(rgba), 0.76, 0.0)


def _sphere(name, location, radius, material, parent):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    obj["ch.semanticRole"] = "pirate_ship.passenger"
    obj["passengerOverlayContract"] = PASSENGER_CONTRACT
    return obj


def _limb(name, a, b, radius, material, parent):
    return base.cylinder_between(name, a, b, radius, material, parent, verts=10, bevel=.018)


def _preserve_reparent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def _moving_name(name: str) -> bool:
    prefixes = (
        "DominantPassengerShip", "PortSheer_", "PortRub_", "StarboardSheer_", "StarboardRub_",
        "BowCrest", "BowGoldCap", "SternCrest", "SternGoldCap", "Seat_", "SeatBack_", "SeatCap_",
        "NearPendulum_", "FarPendulum_", "CentralRoundPendulumMast", "CentralPivotCollar", "CentralShipMount",
        "PortHullInset", "StarboardHullInset", "BowColorInset", "SternColorInset", "BowYellowCrown", "SternYellowCrown",
        "PortSheerLamp_", "StarboardSheerLamp_"
    )
    return name.startswith(prefixes)


def _primary_mask_name(name: str) -> bool:
    # Primary Color = the fixed A-frame supports/"muletas" and their pivot hardware.
    prefixes = (
        "NearSide_", "FarSide_", "TransversePivotAxle",
        "NearBearingHousing", "NearBearingHub",
        "FarBearingHousing", "FarBearingHub", "PivotColorCap_",
    )
    return name.startswith(prefixes)


def _secondary_mask_name(name: str) -> bool:
    # Secondary Color = the boat itself. Pendulum arms and passengers are excluded.
    prefixes = (
        "DominantPassengerShip", "PortSheer_", "PortRub_", "StarboardSheer_", "StarboardRub_",
        "BowCrest", "BowGoldCap", "SternCrest", "SternGoldCap",
        "Seat_", "SeatBack_", "SeatCap_",
        "PortHullInset", "StarboardHullInset",
        "BowColorInset", "SternColorInset", "BowYellowCrown", "SternYellowCrown",
        "PortSheerLamp_", "StarboardSheerLamp_",
    )
    return name.startswith(prefixes)


def _tag_color_masks():
    counts = {"primary": 0, "secondary": 0}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if _primary_mask_name(obj.name):
            obj["ch.colorMask"] = "primary"
            counts["primary"] += 1
        elif _secondary_mask_name(obj.name):
            obj["ch.colorMask"] = "secondary"
            counts["secondary"] += 1
    if counts["primary"] == 0 or counts["secondary"] == 0:
        raise RuntimeError(f"CH_PIRATE_COLOR_MASK_EMPTY:{counts}")
    return counts


def _make_swing_pivot(root, c):
    pz = float(c["dimensions"]["pivotZ"])
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, pz))
    pivot = bpy.context.object
    pivot.name = "SwingPivot"
    pivot.parent = root
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "approved_viking_v15"
    pivot["frameCount"] = FRAME_COUNT
    pivot["fps"] = FPS
    pivot["amplitudeDegrees"] = AMPLITUDE_DEGREES
    pivot["approvedAnglesDegrees"] = json.dumps(APPROVED_SWING_ANGLES)

    for obj in list(bpy.context.scene.objects):
        if obj == pivot or obj == root:
            continue
        if _moving_name(obj.name):
            _preserve_reparent(obj, pivot)
    return pivot


def _build_actor(parent, slot: int, x: float, y: float, cz: float, hw: float, mats: dict):
    tag = f"CHR_PiratePassenger_{slot:02d}"
    jacket = mats[f"jacket_{slot % len(JACKET_COLORS)}"]
    pants = mats[f"pants_{slot % len(PANTS_COLORS)}"]
    skin, hair, shoes = mats["skin"], mats["hair"], mats["shoes"]

    # Author riders in world/AssetRoot space and only then preserve-reparent them
    # to SwingPivot. Parenting at creation time added pivotZ twice and produced
    # the floating overlay seen in review.
    created = []
    pelvis = Vector((x - .04, y, cz + .90))
    chest = Vector((x + .01, y, cz + 1.28))
    head = Vector((x + .05, y, cz + 1.62))

    torso = base.box(f"{tag}_Torso", tuple(chest), (.28, .34, .40), jacket, None, .055)
    torso.rotation_euler[1] = math.radians(4.0)
    created.append(torso)
    created.append(_sphere(f"{tag}_Head", tuple(head), .125, skin, None))
    created.append(_sphere(f"{tag}_Hair", (head.x - .01, head.y, head.z + .055), .130, hair, None))

    for side in (-1, 1):
        sy = y + side * .13
        shoulder = (chest.x, sy, chest.z + .08)
        elbow = (chest.x + .12, sy, chest.z - .08)
        hand = (chest.x + .19, sy, chest.z - .19)
        created.append(_limb(f"{tag}_UpperArm_{side:+d}", shoulder, elbow, .043, jacket, None))
        created.append(_limb(f"{tag}_ForeArm_{side:+d}", elbow, hand, .036, jacket, None))
        created.append(_sphere(f"{tag}_Hand_{side:+d}", hand, .040, skin, None))

    for side in (-1, 1):
        sy = y + side * .085
        hip = (pelvis.x, sy, pelvis.z)
        knee = (pelvis.x + .22, sy, pelvis.z - .08)
        ankle = (pelvis.x + .25, sy, cz + .50)
        toe = (pelvis.x + .34, sy, cz + .48)
        created.append(_limb(f"{tag}_Thigh_{side:+d}", hip, knee, .052, pants, None))
        created.append(_limb(f"{tag}_Shin_{side:+d}", knee, ankle, .045, pants, None))
        created.append(_limb(f"{tag}_Shoe_{side:+d}", ankle, toe, .048, shoes, None))

    marker = bpy.data.objects.new(f"{tag}_SeatMarker", None)
    bpy.context.scene.collection.objects.link(marker)
    marker.location = tuple(pelvis)
    marker["seatSlot"] = slot
    marker["occupantType"] = "CHActor"
    marker["paletteIndex"] = slot % len(JACKET_COLORS)

    for obj in created:
        _preserve_reparent(obj, parent)
    _preserve_reparent(marker, parent)
    return marker


def _add_passengers(pivot, c):
    d = c["dimensions"]
    cz = float(d["shipCenterZ"])
    hw = float(d["shipHalfWidth"])
    xs = [-7.0,-5.7,-4.4,-3.1,-1.9,-.85,.85,1.9,3.1,4.4,5.7,7.0]
    bank_y = hw * .43

    mats = {
        "skin": _material("PiratePassengerSkin", SKIN),
        "hair": _material("PiratePassengerHair", HAIR),
        "shoes": _material("PiratePassengerShoes", SHOES),
    }
    for i, rgba in enumerate(JACKET_COLORS):
        mats[f"jacket_{i}"] = _material(f"PiratePassengerJacket{i}", rgba)
    for i, rgba in enumerate(PANTS_COLORS):
        mats[f"pants_{i}"] = _material(f"PiratePassengerPants{i}", rgba)

    slots = []
    slot = 0
    for row, x in enumerate(xs):
        for side in (-1, 1):
            y = side * bank_y
            marker = _build_actor(pivot, slot, x, y, cz, hw, mats)
            slots.append({
                "slotId": slot,
                "row": row,
                "bank": "near" if side < 0 else "far",
                "localPosition": [round(x, 4), round(y, 4), round(cz + .90, 4)],
                "paletteIndex": slot % len(JACKET_COLORS),
            })
            slot += 1
    if slot != CAPACITY:
        raise RuntimeError(f"CH_PIRATE_PASSENGER_CAPACITY_MISMATCH:{slot}!={CAPACITY}")
    return slots


def _assert_passenger_binding(c):
    cz = float(c["dimensions"]["shipCenterZ"])
    passengers = [
        o for o in bpy.context.scene.objects
        if o.type == "MESH" and o.name.startswith("CHR_PiratePassenger_")
    ]
    if not passengers:
        raise RuntimeError("CH_PIRATE_PASSENGER_OVERLAY_EMPTY")
    world_z = []
    for obj in passengers:
        for corner in obj.bound_box:
            world_z.append((obj.matrix_world @ Vector(corner)).z)
    zmin, zmax = min(world_z), max(world_z)
    if zmin < cz + .20 or zmax > cz + 2.40:
        raise RuntimeError(
            f"CH_PIRATE_PASSENGER_BINDING_OUT_OF_BOAT:z={zmin:.3f}..{zmax:.3f}:shipCenterZ={cz:.3f}"
        )
    return {"status": "ok", "worldZMin": round(zmin, 4), "worldZMax": round(zmax, 4)}


def _set_passenger_only(only: bool):
    states = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        is_passenger = obj.name.startswith("CHR_PiratePassenger_")
        states.append((obj, obj.hide_render))
        if only:
            obj.hide_render = not is_passenger
    return states


def _restore_visibility(states):
    for obj, hidden in states:
        obj.hide_render = hidden


def _mask_material():
    mat = bpy.data.materials.get("CH_ColorMaskWhite")
    if mat is not None:
        return mat
    mat = bpy.data.materials.new("CH_ColorMaskWhite")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emission.inputs["Strength"].default_value = 1.0
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def render_color_mask(scene, output_path: Path, slot: str):
    pred = _primary_mask_name if slot == "primary" else _secondary_mask_name
    states = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        states.append((obj, obj.hide_render))
        obj.hide_render = not pred(obj.name)
    old_override = bpy.context.view_layer.material_override
    old_path = scene.render.filepath
    bpy.context.view_layer.material_override = _mask_material()
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    scene.render.filepath = old_path
    bpy.context.view_layer.material_override = old_override
    _restore_visibility(states)


def main():
    a = base.argv()
    c = base.load(a.recipe)
    studio = base.bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    base.bs.clear_scene()
    scene = base.bs.configure_scene(studio, tuple(map(int, studio["render"]["sourceResolution"])), str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    M = {k: base.material(v) for k, v in c["materials"].items()}
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.object
    root.name = "AssetRoot"
    root["assetId"] = base.ASSET
    root["cameraContract"] = "CH_CAMERA_V1"
    root["styleContract"] = c["styleContract"]
    root["footprint"] = "7x6"
    root["proceduralContract"] = base.CONTRACT
    root["animationContract"] = ANIMATION_CONTRACT
    root["passengerOverlayContract"] = PASSENGER_CONTRACT
    root["colorMaskContract"] = COLOR_MASK_CONTRACT
    root["rideCapacity"] = CAPACITY

    base.build(root, c, M)
    pivot = _make_swing_pivot(root, c)
    slots = _add_passengers(pivot, c)
    mask_counts = _tag_color_masks()
    overlay_validation = _assert_passenger_binding(c)

    recv = studio["shadowReceiver"]
    rm = base.bs.make_material("ShadowReceiver", recv["materialColor"], float(recv.get("roughness", 1)))
    ground = base.bs.add_box("ShadowReceiverPlane", recv["location"], [30, 21, float(recv["dimensions"][2])], rm, 0)
    authored = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != ground]

    base.bs.calibrate_ortho_scale(scene, authored, safety_margin=.16)
    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    metadata = {
        "contract": ANIMATION_CONTRACT,
        "assetId": base.ASSET,
        "cameraContract": "CH_CAMERA_V1",
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "anglesDegrees": APPROVED_SWING_ANGLES,
        "rotationAxis": "Y",
        "motion": "approved_viking_v15",
        "passengerOverlayContract": PASSENGER_CONTRACT,
        "passengerVisualRecipeSource": "CH_COASTER_PASSENGER_OVERLAY_V1 / approved Viking V15 CHActor recipe",
        "capacity": CAPACITY,
        "seatSlots": slots,
        "overlayValidation": overlay_validation,
        "colorMaskContract": COLOR_MASK_CONTRACT,
        "colorMasks": {
            "primary": "fixed A-frame supports / muletas",
            "secondary": "boat hull, seats and boat decoration",
            "taggedObjectCounts": mask_counts,
        },
        "sourceSwingApproval": {
            "commit": "a9f6e02b63a06462f10133b405ee85921f172e40",
            "reviewWorkflowRun": 36350851439,
            "frameCount": 12,
            "fps": 8,
            "amplitudeDegrees": 35.0,
            "approvedProxySha256": "c92f1feac2c816599edfac0bf00aa1a645389b7cca86f3350b6b73bd9d33e89b",
        },
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "passenger_overlay_manifest.json").write_text(json.dumps({
        "contract": PASSENGER_CONTRACT,
        "assetId": base.ASSET,
        "capacity": CAPACITY,
        "seatSlots": slots,
        "actorSource": "CHActor",
        "visualRecipeSource": "CH_COASTER_PASSENGER_OVERLAY_V1",
        "motionParent": "SwingPivot",
        "compositionMode": "depth_correct_blender_composite_plus_transparent_overlay",
        "frameCountPerDirection": FRAME_COUNT,
        "directions": [d["id"] for d in base.bs.DIRECTIONS],
        "validation": overlay_validation,
    }, indent=2), encoding="utf-8")
    (out / "color_mask_manifest.json").write_text(json.dumps({
        "contract": COLOR_MASK_CONTRACT,
        "assetId": base.ASSET,
        "primaryColor": {"target": "A-frame supports / muletas", "animated": False},
        "secondaryColor": {"target": "boat", "animated": True},
        "directions": [d["id"] for d in base.bs.DIRECTIONS],
        "frameCount": FRAME_COUNT,
    }, indent=2), encoding="utf-8")

    profile = base.scene_gate.load_profile(a.preflight_profile)
    pivot.rotation_euler[1] = 0.0
    pre = base.scene_gate.run_preflight(
        scene=scene, authored=authored, footprint=c["footprint"], profile=profile,
        asset_id=base.ASSET, report_path=out / "preflight_report.json"
    )
    base.scene_gate.require_pass(pre)

    frame_manifest = []
    cycle = angles()
    canonical_report = None
    for direction in base.bs.DIRECTIONS:
        did = direction["id"]
        base.bs.set_direction(root, direction)
        pivot.rotation_euler[1] = 0.0
        bpy.context.view_layer.update()
        render_color_mask(scene, out / f"mask_primary_{did}.png", "primary")
        for index, angle in enumerate(cycle):
            pivot.rotation_euler[1] = math.radians(angle)
            bpy.context.view_layer.update()
            occupied_name = f"swing_{did}_{index:02d}.png"
            report = base.scene_gate.render_proxy(
                scene=scene, authored=authored, output_path=out / occupied_name,
                profile=profile, asset_id=base.ASSET, direction=did
            )
            if did == "south" and index == 0:
                canonical_report = dict(report)
                (out / "proxy_south.png").write_bytes((out / occupied_name).read_bytes())

            states = _set_passenger_only(True)
            overlay_name = f"passengers_{did}_{index:02d}.png"
            base.scene_gate.render_proxy(
                scene=scene, authored=None, output_path=out / overlay_name,
                profile=profile, asset_id=base.ASSET, direction=did
            )
            _restore_visibility(states)

            secondary_mask = f"mask_secondary_{did}_{index:02d}.png"
            render_color_mask(scene, out / secondary_mask, "secondary")

            frame_manifest.append({
                "direction": did,
                "frameIndex": index,
                "angleDegrees": round(angle, 6),
                "occupiedFile": occupied_name,
                "passengerOverlayFile": overlay_name,
                "primaryMaskFile": f"mask_primary_{did}.png",
                "secondaryMaskFile": secondary_mask,
                "sha256": report["sha256"],
            })

    if canonical_report is None:
        raise RuntimeError("CH_PIRATE_SWING_CANONICAL_PROXY_MISSING")
    canonical_report["path"] = str(out / "proxy_south.png")
    (out / "proxy_report.json").write_text(json.dumps(canonical_report, indent=2), encoding="utf-8")
    (out / "swing_frames_manifest.json").write_text(json.dumps({
        "contract": ANIMATION_CONTRACT,
        "status": "ok",
        "frameCountPerDirection": FRAME_COUNT,
        "totalOccupiedFrames": FRAME_COUNT * 4,
        "totalPassengerOverlayFrames": FRAME_COUNT * 4,
        "fps": FPS,
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "anglesDegrees": cycle,
        "swingApproval": "Viking V15 / human reviewed",
        "directions": [d["id"] for d in base.bs.DIRECTIONS],
        "frames": frame_manifest,
    }, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    if a.save_blend:
        q = Path(a.save_blend).resolve()
        q.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(q))


if __name__ == "__main__":
    main()
