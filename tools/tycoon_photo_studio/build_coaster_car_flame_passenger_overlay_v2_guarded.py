"""Depth-correct final bake for the approved Flame coaster passengers.

V2 intentionally reuses every authored mesh, palette, seat slot, camera rule and pose
transform from CH_COASTER_PASSENGER_OVERLAY_V1.  The only behavioral change is the
final output: each pose emits both a passenger-only RGBA overlay and an occupied
car+passenger composite rendered together in Blender so the car body/restraints
occlude riders correctly.
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_coaster_car_flame_passenger_overlay_v1_guarded as v1


def _occupied_frame_name(base_file: str) -> str:
    return f"occupied_{base_file}"


def _write_v2_manifest(output: Path, slots: list[dict], pose_manifest: dict) -> None:
    v1._write_manifest(output, slots, pose_manifest, stage="final")
    path = output / "passenger_overlay_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["renderContract"] = "CH_COASTER_PASSENGER_OCCLUSION_V2"
    payload["runtimeCompositePolicy"] = "use_blender_occupied_composite"
    payload["passengerOverlayPurpose"] = "future_dynamic_occupancy_reuse"
    for frame in payload["frames"]:
        frame["occupiedCompositeFile"] = _occupied_frame_name(frame["baseCarFile"])
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = v1.parse_args()
    if args.stage != "final":
        # Proxy/preflight remain byte-for-byte on the reviewed V1 path.
        v1.main()
        return

    if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
        raise ValueError("The final passenger overlay bake requires the reviewed proxy SHA-256")

    studio = v1.bs.load_json(args.studio_preset)
    profile = v1.scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    v1.shape.load_contract()
    v1.bs.clear_scene()
    scene = v1.bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    car_meshes = v1.atlas.build_generic_car()
    passenger_meshes, markers, slots = v1.add_passengers()
    authored = car_meshes + passenger_meshes
    root = v1.bs.create_asset_root(authored + markers)
    root["assetId"] = v1.ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["trackContract"] = v1.TRACK_CONTRACT
    root["carContract"] = v1.CAR_CONTRACT
    root["passengerOverlayContract"] = v1.PASSENGER_CONTRACT
    root["passengerOcclusionContract"] = "CH_COASTER_PASSENGER_OCCLUSION_V2"
    root["rideCapacityPerCar"] = v1.CAPACITY
    root["styleId"] = v1.STYLE_ID
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    base_matrices = v1.atlas.capture_base_matrices(authored)
    v1.atlas.apply_pose(authored, base_matrices, v1.PROXY_HEADING_DEG, v1.PROXY_PITCH_DEG)
    v1.bs.calibrate_ortho_scale(scene, authored, safety_margin=0.34)
    bpy.context.view_layer.update()

    pose_manifest = v1.atlas.build_pose_manifest()
    if pose_manifest["totalFrames"] != 40:
        raise RuntimeError(
            f"CH_COASTER_PASSENGER_POSE_COUNT_MISMATCH: expected 40, got {pose_manifest['totalFrames']}"
        )

    _write_v2_manifest(output, slots, pose_manifest)
    (output / "studio_metadata.json").write_text(json.dumps({
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": v1.ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": "final",
        "runtimeRepresentation": "2D_RGBA_pre_rendered_passenger_overlay_plus_depth_correct_composite",
        "poseContract": v1.CAR_CONTRACT,
        "passengerOverlayContract": v1.PASSENGER_CONTRACT,
        "passengerOcclusionContract": "CH_COASTER_PASSENGER_OCCLUSION_V2",
        "capacityPerCar": v1.CAPACITY,
        "frameCount": pose_manifest["totalFrames"],
        "occupiedCompositeFrameCount": pose_manifest["totalFrames"],
        "reviewPose": {"headingDegrees": v1.PROXY_HEADING_DEG, "pitchDegrees": v1.PROXY_PITCH_DEG},
    }, indent=2), encoding="utf-8")

    report = v1.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=v1.FOOTPRINT,
        profile=profile,
        asset_id=v1.ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    v1.scene_gate.require_pass(report)

    (output / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": v1.ASSET_ID,
        "reviewed": True,
        "proxySha256": args.approval_proxy_sha,
        "reviewedVisualSource": "V1 proxy; V2 changes final occlusion composition only",
    }, indent=2), encoding="utf-8")

    for pose in pose_manifest["frames"]:
        heading = float(pose["headingDegrees"])
        pitch = float(pose["pitchDegrees"])
        v1.atlas.apply_pose(authored, base_matrices, heading, pitch)
        direction = f"h{pose['headingIndex']:02d}_pitch_{pitch:+.0f}"

        # Runtime source: render car and riders together so Blender resolves depth.
        v1._set_visibility(car_meshes, True)
        v1._set_visibility(passenger_meshes, True)
        v1._render(
            scene,
            authored,
            profile,
            output,
            _occupied_frame_name(pose["file"]),
            direction,
        )

        # Preserve a transparent passenger-only layer for future dynamic occupancy.
        v1._set_visibility(car_meshes, False)
        v1._set_visibility(passenger_meshes, True)
        v1._render(
            scene,
            passenger_meshes,
            profile,
            output,
            v1._overlay_frame_name(pose["file"]),
            direction,
        )

    v1._set_visibility(car_meshes, True)


if __name__ == "__main__":
    main()
