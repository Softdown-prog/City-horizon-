from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "tools/ch_blender/runtime_integrations/building.ice_cream_shop.01.json"
STATIC_SOURCE_ROOT = ROOT / "out/ice_runtime/static"
STATIC_FINAL_ROOT = ROOT / "out/ice_runtime/static_final"
ACTIVITY_SOURCE_ROOT = ROOT / "out/ice_runtime/activity"


def load_contract() -> dict:
    cfg = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert cfg["contract"] == "CH_RUNTIME_BUILDING_INTEGRATION_V1"
    assert cfg["assetId"] == "building.ice_cream_shop.01"
    assert cfg["activityOverlay"]["contract"] == "CH_BUILDING_ACTIVITY_OVERLAY_V1"
    assert cfg["activityOverlay"]["frameCount"] == 8
    assert cfg["activityOverlay"]["layout"] == "horizontal"
    assert cfg["resourceInputs"] == []
    return cfg


def align_activity_frame(image: Image.Image, static_meta: dict, activity_meta: dict) -> Image.Image:
    static_ground = static_meta["directions"][0]["groundOriginSourcePx"]
    activity_ground = activity_meta["groundOriginSourcePx"]
    static_ortho = float(static_meta["orthoScaleCalibrated"])
    activity_ortho = float(activity_meta["calibratedOrthoScale"])
    scale = activity_ortho / static_ortho
    inv = 1.0 / scale
    affine = (
        inv,
        0.0,
        float(activity_ground["x"]) - float(static_ground["x"]) * inv,
        0.0,
        inv,
        float(activity_ground["y"]) - float(static_ground["y"]) * inv,
    )
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        affine,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def package_runtime(cfg: dict) -> None:
    asset_id = cfg["assetId"]
    stem = cfg["fileStem"]
    dst = ROOT / cfg["destination"]
    dst.mkdir(parents=True, exist_ok=True)

    static_source = STATIC_SOURCE_ROOT / cfg["static"]["sourceDir"]
    activity_source = ACTIVITY_SOURCE_ROOT / cfg["activityOverlay"]["sourceDir"]
    static_meta = json.loads((static_source / "studio_metadata.json").read_text(encoding="utf-8"))
    activity_meta = json.loads((activity_source / "activity_overlay_metadata.json").read_text(encoding="utf-8"))

    assert static_meta["sourceObject"] == asset_id
    assert activity_meta["assetId"] == asset_id
    assert activity_meta["activityContract"] == "CH_BUILDING_ACTIVITY_OVERLAY_V1"
    assert activity_meta["frameCount"] == cfg["activityOverlay"]["frameCount"]
    assert activity_meta["layout"] == "horizontal"
    assert activity_meta["playback"] == "loop"

    frame_size = tuple(map(int, static_meta["finalResolution"]))
    if tuple(map(int, activity_meta["finalResolution"])) != frame_size:
        raise RuntimeError("Static and activity final resolutions disagree")

    directions = ("south", "east", "west", "north")
    runtime_order = ("south", "west", "north", "east")
    static_files: dict[str, str] = {}
    mask_files: dict[str, str] = {}
    for direction in directions:
        color_src = STATIC_FINAL_ROOT / f"{asset_id}_{direction}.png"
        mask_src = STATIC_FINAL_ROOT / f"{asset_id}_{direction}_mask.png"
        if not color_src.is_file() or not mask_src.is_file():
            raise RuntimeError(f"Missing postprocessed {direction} output")
        color_dst = dst / f"{stem}_{direction}.png"
        mask_dst = dst / f"{stem}_{direction}_mask.png"
        shutil.copy2(color_src, color_dst)
        shutil.copy2(mask_src, mask_dst)
        static_files[direction] = color_dst.name
        mask_files[direction] = mask_dst.name

    for suffix in ("_4view.png", "_mask_4view.png", "_mask_review.png"):
        source = STATIC_FINAL_ROOT / f"{asset_id}{suffix}"
        if source.is_file():
            shutil.copy2(source, dst / f"{stem}{suffix}")

    activity_by_direction = {item["id"]: item for item in activity_meta["directions"]}
    activity_files: dict[str, str] = {}
    for direction in directions:
        frames: list[Image.Image] = []
        for frame in activity_by_direction[direction]["frames"]:
            source_path = activity_source / frame["source"]
            image = Image.open(source_path).convert("RGBA")
            aligned = align_activity_frame(image, static_meta, activity_meta)
            small = aligned.resize(frame_size, Image.Resampling.LANCZOS)
            if small.getchannel("A").getbbox() is None:
                raise RuntimeError(f"Empty activity frame: {source_path}")
            frames.append(small)
        sheet = Image.new("RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            sheet.alpha_composite(frame, (index * frame_size[0], 0))
        sheet_path = dst / f"{stem}_activity_{direction}.png"
        sheet.save(sheet_path)
        activity_files[direction] = sheet_path.name

    static_ground = static_meta["directions"][0]["groundOriginSourcePx"]
    source_w, source_h = map(float, static_meta["renderResolution"])
    anchor_x = float(static_ground["x"]) / source_w
    anchor_y = float(static_ground["y"]) / source_h
    anchors = {str(index): {"x": anchor_x, "y": anchor_y} for index in range(4)}
    sprites = {
        str(index): f"assets/buildings/ice_cream_shop/{static_files[direction]}"
        for index, direction in enumerate(runtime_order)
    }
    masks = {
        str(index): f"assets/buildings/ice_cream_shop/{mask_files[direction]}"
        for index, direction in enumerate(runtime_order)
    }
    activity_sprites = {
        str(index): f"assets/buildings/ice_cream_shop/{activity_files[direction]}"
        for index, direction in enumerate(runtime_order)
    }

    definition = {
        "id": cfg["definitionId"],
        "name": cfg["displayName"],
        "category": "commercial",
        "texture": sprites["0"],
        "sprites": sprites,
        "spriteAnchors": anchors,
        "rotatable": True,
        "requiresRoadAccess": True,
        "roadAccessMode": "front_edge",
        "frontEdge": "south",
        "footprint": {"width": 2, "height": 2},
        "buildCost": 0,
        "maintenancePerMonth": 0,
        "taxRevenuePerMonth": 0,
        "propertyTaxPerYear": 0,
        "requiredPopulationForFullRevenue": 0,
        "powerConsumption": 0,
        "artScale": 1.0,
        "playerBuildable": True,
        "productionStatus": "runtime_buildable",
        "resourceInputs": [],
        "colorMask": {
            "contract": "CH_COLOR_MASK_V1",
            "enabled": True,
            "channels": {"R": "wall", "G": "roof"},
            "alpha": "coverage",
            "sprites": masks,
        },
        "activityOverlay": {
            "contract": "CH_BUILDING_ACTIVITY_OVERLAY_V1",
            "enabled": True,
            "sprites": activity_sprites,
            "animation": {
                "frameCount": int(activity_meta["frameCount"]),
                "frameDurationMs": int(round(1000.0 / float(activity_meta["fps"]))),
                "layout": "horizontal",
                "playback": "loop",
                "idleFrame": 0,
                "actionStartFrame": 0,
                "actionFrameCount": int(activity_meta["frameCount"]),
            },
        },
    }
    definition_path = ROOT / cfg["definitionPath"]
    if definition_path.is_file():
        # Keep gameplay and economy fields authored after the original art import.
        current = json.loads(definition_path.read_text(encoding="utf-8"))
        for key in ("texture", "sprites", "colorMask", "activityOverlay"):
            current[key] = definition[key]
        definition = current
    definition_path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")

    package = {
        "contract": "CH_RUNTIME_BUILDING_V1",
        "assetId": asset_id,
        "displayName": cfg["displayName"],
        "visualContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "format": "PNG_RGBA",
        "frameSize": list(frame_size),
        "transparentBackground": True,
        "directionOrder": list(directions),
        "footprint": static_meta["footprint"],
        "approvedForRuntime": True,
        "sourceCommit": cfg["static"]["sourceCommit"],
        "sourceWorkflowRun": cfg["static"]["sourceWorkflowRun"],
        "sourceArtifactId": cfg["static"]["sourceArtifactId"],
        "approvedProxySha256": cfg["static"]["approvedProxySha256"],
        "colorMask": {
            "contract": "CH_COLOR_MASK_V1",
            "enabled": True,
            "channels": {"R": "wall", "G": "roof"},
            "alpha": "coverage",
            "runtimeTintingImplemented": True,
        },
        "activityOverlay": {
            "contract": "CH_BUILDING_ACTIVITY_OVERLAY_V1",
            "frameCount": int(activity_meta["frameCount"]),
            "frameDurationMs": int(round(1000.0 / float(activity_meta["fps"]))),
            "layout": "horizontal",
            "playback": "loop",
            "sourceCommit": cfg["activityOverlay"]["sourceCommit"],
            "sourceWorkflowRun": cfg["activityOverlay"]["sourceWorkflowRun"],
            "sourceArtifactId": cfg["activityOverlay"]["sourceArtifactId"],
            "approvedProxySha256": cfg["activityOverlay"]["approvedProxySha256"],
            "sprites": activity_files,
        },
    }
    package["sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dst.glob("*.png"))
    }
    (dst / f"{stem}.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")


def patch_runtime() -> None:
    path = ROOT / "src/main.cpp"
    text = path.read_text(encoding="utf-8")

    helper_anchor = "void render_anchor_cross(SDL_Renderer* renderer, const SDL_FPoint point, const float radius,"
    if "void render_building_activity_overlay(" not in text:
        helper = r'''
void render_building_activity_overlay(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                      const BuildingInstance& instance, const BuildingRotation visual_rotation,
                                      const TextureCache& textures, const std::filesystem::path& asset_root,
                                      const Camera& camera, const float viewport_width, const float viewport_height) {
    if (!instance.activity_active() || !definition.activity_overlay || !definition.activity_overlay->enabled) return;
    const std::size_t rotation_index = static_cast<std::size_t>(visual_rotation);
    if (rotation_index >= definition.activity_overlay->sprite_paths.size()) return;
    const std::string& relative_path = definition.activity_overlay->sprite_paths[rotation_index];
    if (relative_path.empty()) return;
    const TextureAsset* texture = textures.find(asset_root / relative_path);
    if (texture == nullptr || texture->texture == nullptr) return;

    const BuildingAnimationDefinition* animation = definition.activity_overlay->animation
        ? &*definition.activity_overlay->animation : nullptr;
    const int frame_count = animation == nullptr ? 1 : std::max(1, animation->frame_count);
    const int frame_duration_ms = animation == nullptr ? 1 : std::max(1, animation->frame_duration_ms);
    int frame_index = 0;
    if (frame_count > 1) {
        const Uint64 elapsed_ms = SDL_GetTicks();
        if (animation->playback == "ambient_once") {
            frame_index = std::min(frame_count - 1, static_cast<int>(elapsed_ms / static_cast<Uint64>(frame_duration_ms)));
        } else {
            frame_index = static_cast<int>((elapsed_ms / static_cast<Uint64>(frame_duration_ms)) % static_cast<Uint64>(frame_count));
        }
    }

    const float frame_width = texture->source_width / static_cast<float>(frame_count);
    const float frame_height = texture->source_height;
    const SDL_FRect source = {frame_width * static_cast<float>(frame_index), 0.0F, frame_width, frame_height};
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    const CameraWorldPoint ground = building_visual_ground_world(instance, footprint, camera.rotation);
    const SDL_FPoint anchor = world_to_screen(ground.x, ground.y, camera, viewport_width, viewport_height);
    const float scale = definition.art_scale * camera.zoom;
    const SDL_FRect destination = {
        anchor.x - frame_width * scale * definition.anchor_x_for(visual_rotation, instance.current_level),
        anchor.y - frame_height * scale * definition.anchor_y_for(visual_rotation, instance.current_level),
        frame_width * scale,
        frame_height * scale,
    };
    SDL_RenderTexture(renderer, texture->texture, &source, &destination);
}

'''
        if helper_anchor not in text:
            raise RuntimeError("render helper insertion anchor not found")
        text = text.replace(helper_anchor, helper + helper_anchor, 1)

    load_anchor = """                    if (lvl.level == 1 && definition.supports_color_mask(logical_rotation)) {
                        const auto mask_path = asset_root / definition.color_mask_path_for(logical_rotation);
                        (void)textures.load_mask_channel(renderer, mask_path, 'R');
                        (void)textures.load_mask_channel(renderer, mask_path, 'G');
                    }
"""
    if "definition.activity_overlay->sprite_paths[rotation]" not in text:
        replacement = load_anchor + """                    if (lvl.level == 1 && definition.activity_overlay && definition.activity_overlay->enabled) {
                        const std::string& overlay_path = definition.activity_overlay->sprite_paths[rotation];
                        if (!overlay_path.empty()) {
                            (void)textures.load(renderer, asset_root / overlay_path);
                        }
                    }
"""
        if load_anchor not in text:
            raise RuntimeError("activity texture load anchor not found")
        text = text.replace(load_anchor, replacement, 1)

    if "render_building_activity_overlay(renderer, *definition, *draw.building" not in text:
        world_start = text.index("void render_world_entities(")
        mobile_anchor = """            }
            continue;
        }
        const MobileEntityRenderData& entity = *draw.mobile_entity;
"""
        pos = text.find(mobile_anchor, world_start)
        if pos < 0:
            raise RuntimeError("world render insertion anchor not found")
        replacement = """                render_building_activity_overlay(renderer, *definition, *draw.building, visual_rotation,
                                                 textures, root, camera, viewport_width, viewport_height);
""" + mobile_anchor
        text = text[:pos] + replacement + text[pos + len(mobile_anchor):]

    if "case SDL_SCANCODE_F8:" not in text:
        f10_anchor = "                    case SDL_SCANCODE_F10: {"
        f8_case = """                    case SDL_SCANCODE_F8: {
                        if (!selected_instance_id) {
                            status = "ACTIVITY TEST: SELECT A BUILDING FIRST";
                            break;
                        }
                        const BuildingInstance* selected = buildings.find_by_id(*selected_instance_id);
                        const BuildingDefinition* definition = selected == nullptr ? nullptr : catalog.find(selected->definition_id);
                        if (selected == nullptr || definition == nullptr || !definition->activity_overlay || !definition->activity_overlay->enabled) {
                            status = "ACTIVITY TEST: SELECT A BUILDING WITH OVERLAY";
                            break;
                        }
                        const bool was_active = selected->activity_active();
                        if (was_active) {
                            while (true) {
                                const BuildingInstance* current = buildings.find_by_id(*selected_instance_id);
                                if (current == nullptr || !current->activity_active()) break;
                                (void)buildings.end_activity(*selected_instance_id);
                            }
                        } else {
                            (void)buildings.begin_activity(*selected_instance_id);
                        }
                        status = std::string("ICE CREAM ACTIVITY TEST: ") + (was_active ? "OFF" : "ON");
                        break;
                    }
"""
        if f10_anchor not in text:
            raise RuntimeError("F8 insertion anchor not found")
        text = text.replace(f10_anchor, f8_case + f10_anchor, 1)

    path.write_text(text, encoding="utf-8")


def sanity_check(cfg: dict) -> None:
    definition = json.loads((ROOT / cfg["definitionPath"]).read_text(encoding="utf-8"))
    assert definition["resourceInputs"] == []
    assert definition["activityOverlay"]["contract"] == "CH_BUILDING_ACTIVITY_OVERLAY_V1"
    assert definition["activityOverlay"]["animation"]["frameCount"] == 8
    assert definition["activityOverlay"]["animation"]["frameDurationMs"] == 250
    for path in definition["sprites"].values():
        image = Image.open(ROOT / path)
        assert image.mode == "RGBA" and image.size == (320, 288)
    for path in definition["activityOverlay"]["sprites"].values():
        image = Image.open(ROOT / path)
        assert image.mode == "RGBA" and image.size == (320 * 8, 288)


if __name__ == "__main__":
    config = load_contract()
    package_runtime(config)
    patch_runtime()
    sanity_check(config)
    print("Ice cream runtime integration staged successfully")
