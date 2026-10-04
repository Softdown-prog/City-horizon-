from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_ROOT = ROOT / "out" / "classic_steel_overlay_promotion"
ASSET_DIR = ROOT / "assets" / "coasters" / "skins" / "classic_steel_01"
ATLAS_PATH = ASSET_DIR / "track_skin_atlas.png"
MANIFEST_PATH = ASSET_DIR / "track_skin_atlas_runtime.json"

MODULES = ("joint_plate", "chain_lift", "brake_fin")
DIRECTIONS = ("south", "east", "west", "north")
CELL_W = 96
CELL_H = 72
ATLAS_W = CELL_W * len(DIRECTIONS)
ATLAS_H = CELL_H * len(MODULES)


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"guarded replacement failed for {path}: expected 1 occurrence, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def locate_final_root() -> Path:
    candidates = list(DOWNLOAD_ROOT.rglob("runtime_modules"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one runtime_modules directory, found {len(candidates)}")
    return candidates[0].parent


def build_atlas(final_root: Path) -> dict:
    modules_dir = final_root / "runtime_modules"
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))
    records = []
    for row, module in enumerate(MODULES):
        for col, direction in enumerate(DIRECTIONS):
            src_path = modules_dir / f"{module}_{direction}.png"
            if not src_path.is_file():
                raise RuntimeError(f"missing approved module render: {src_path}")
            image = Image.open(src_path).convert("RGBA")
            bbox = image.getchannel("A").getbbox()
            if bbox is None:
                raise RuntimeError(f"empty alpha in {src_path}")
            crop = image.crop(bbox)
            max_w = CELL_W - 8
            max_h = CELL_H - 10
            scale = min(max_w / crop.width, max_h / crop.height)
            resized = crop.resize(
                (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
                Image.Resampling.LANCZOS,
            )
            cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
            px = (CELL_W - resized.width) // 2
            py = (CELL_H - resized.height) // 2
            cell.alpha_composite(resized, (px, py))
            atlas.alpha_composite(cell, (col * CELL_W, row * CELL_H))
            records.append({
                "module": module,
                "direction": direction,
                "sourceRect": [col * CELL_W, row * CELL_H, CELL_W, CELL_H],
                "anchorPx": [CELL_W // 2, CELL_H // 2],
            })

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    atlas.save(ATLAS_PATH, optimize=True)
    atlas_sha = hashlib.sha256(ATLAS_PATH.read_bytes()).hexdigest()

    approval = json.loads((final_root / "proxy_approval.json").read_text(encoding="utf-8"))
    metadata = json.loads((final_root / "studio_metadata.json").read_text(encoding="utf-8"))
    manifest = {
        "contract": "CH_COASTER_TRACK_SKIN_ATLAS_V1",
        "assetId": "coaster.track_skin.classic_steel_01.modules",
        "skinId": "classic_steel_01",
        "geometryAuthority": "CH_COASTER_TRACK_GEOMETRY_V1",
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "runtimeRepresentation": "2D_RGBA_overlay_atlas",
        "atlas": {
            "path": "assets/coasters/skins/classic_steel_01/track_skin_atlas.png",
            "width": ATLAS_W,
            "height": ATLAS_H,
            "sha256": atlas_sha,
            "cellWidth": CELL_W,
            "cellHeight": CELL_H,
        },
        "approvedProxySha256": approval.get("proxySha256"),
        "sourceFingerprint": metadata.get("sourceFingerprint"),
        "bakeRun": 37177174997,
        "directions": list(DIRECTIONS),
        "modules": records,
        "placement": {
            "joint_plate": "repeat_on_free_or_station_track",
            "chain_lift": "drive_mode_lift_only",
            "brake_fin": "drive_mode_brake_only",
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def patch_skin_contract() -> None:
    path = ROOT / "src" / "coaster_track_skin.h"
    replace_once(path, "    bool overlay_atlas_enabled = false;", """    // Blender-baked visual modules layered over the procedural rail geometry.
    int overlay_cell_width_px = 96;
    int overlay_cell_height_px = 72;
    float overlay_sprite_scale = 0.56F;
    double joint_plate_spacing_m = 6.0;
    double chain_lift_spacing_m = 1.35;
    double brake_fin_spacing_m = 1.55;
    bool overlay_atlas_enabled = true;""")


def patch_geometry_contract() -> None:
    path = ROOT / "src" / "coaster_track_geometry.h"
    replace_once(
        path,
        "    double roll_degrees = 0.0;\n};",
        "    double roll_degrees = 0.0;\n    DriveMode drive_mode = DriveMode::Free;\n};",
    )
    replace_once(
        path,
        "            sample->roll_degrees,\n        });",
        "            sample->roll_degrees,\n            sample->drive_mode,\n        });",
    )


def patch_renderer() -> None:
    path = ROOT / "src" / "coaster_sdl_renderer.h"
    replace_once(
        path,
        "#include <functional>\n#include <vector>",
        "#include <functional>\n#include <string>\n#include <unordered_map>\n#include <vector>",
    )

    marker = "// Hybrid track renderer. The procedural geometry underneath is the only source\n"
    overlay_code = r'''enum class CoasterSkinOverlayModule : std::uint8_t {
    joint_plate = 0,
    chain_lift = 1,
    brake_fin = 2,
};

struct CoasterSkinOverlayDraw {
    SDL_FRect source{};
    SDL_FRect destination{};
    float depth_key = 0.0F;
};

[[nodiscard]] inline SDL_Texture* coaster_skin_overlay_texture(
    SDL_Renderer* renderer,
    const CoasterTrackSkin& skin) {
    if (renderer == nullptr || !skin.overlay_atlas_enabled || skin.overlay_atlas_path.empty()) {
        return nullptr;
    }
    static std::unordered_map<SDL_Renderer*, SDL_Texture*> cache;
    if (const auto found = cache.find(renderer); found != cache.end()) return found->second;

    const std::string path{skin.overlay_atlas_path};
    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface == nullptr) return nullptr;  // Vector skin remains the safe fallback.
    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_DestroySurface(surface);
    if (texture == nullptr) return nullptr;
    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);
    cache.emplace(renderer, texture);
    return texture;
}

[[nodiscard]] inline int coaster_overlay_direction_column(
    const CoasterTrackGeometry& geometry,
    const std::size_t index,
    const CameraState& camera) noexcept {
    if (geometry.frames.size() < 2U) return 0;
    const std::size_t count = geometry.frames.size();
    const std::size_t prev = index == 0U ? (geometry.closed ? count - 1U : 0U) : index - 1U;
    const std::size_t next = index + 1U < count ? index + 1U : (geometry.closed ? 0U : count - 1U);
    const auto& a = geometry.frames[prev].center;
    const auto& b = geometry.frames[next].center;
    const double angle = std::atan2(b.y - a.y, b.x - a.x);
    constexpr double kHalfPi = 1.57079632679489661923;
    int quarter_turns = static_cast<int>(std::lround(angle / kHalfPi));
    quarter_turns = (quarter_turns % 4 + 4) % 4;
    const int camera_turns = static_cast<int>(camera.rotation) & 3;
    const int visual_turns = (quarter_turns - camera_turns + 4) % 4;
    // Atlas order follows CH Blender DIRECTIONS: SOUTH, EAST, WEST, NORTH.
    switch (visual_turns) {
        case 0: return 0;
        case 1: return 1;
        case 2: return 3;
        default: return 2;
    }
}

[[nodiscard]] inline int coaster_overlay_module_row(const CoasterSkinOverlayModule module) noexcept {
    return static_cast<int>(module);
}

inline void append_coaster_overlay_draw(
    std::vector<CoasterSkinOverlayDraw>& draws,
    const CoasterTrackGeometry& geometry,
    const std::size_t frame_index,
    const CoasterSkinOverlayModule module,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    const auto& frame = geometry.frames[frame_index];
    const WorldPoint3 world = coaster_track_world_point(frame.center);
    const ScreenPoint anchor = world_to_screen_point(
        world, camera, viewport_width, viewport_height);
    const int column = coaster_overlay_direction_column(geometry, frame_index, camera);
    const int row = coaster_overlay_module_row(module);
    const float sprite_scale = std::max(0.05F, skin.overlay_sprite_scale * std::max(0.0F, camera.zoom));
    const float width = static_cast<float>(skin.overlay_cell_width_px) * sprite_scale;
    const float height = static_cast<float>(skin.overlay_cell_height_px) * sprite_scale;

    CoasterSkinOverlayDraw draw;
    draw.source = {
        static_cast<float>(column * skin.overlay_cell_width_px),
        static_cast<float>(row * skin.overlay_cell_height_px),
        static_cast<float>(skin.overlay_cell_width_px),
        static_cast<float>(skin.overlay_cell_height_px),
    };
    draw.destination = {
        anchor.x - width * 0.5F,
        anchor.y - height * 0.5F,
        width,
        height,
    };
    draw.depth_key = camera_depth_key(world.x, world.y, camera);
    draws.push_back(draw);
}

inline void render_coaster_track_overlay_modules(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    SDL_Texture* atlas = coaster_skin_overlay_texture(renderer, skin);
    if (atlas == nullptr || geometry.frames.empty()) return;

    std::vector<CoasterSkinOverlayDraw> draws;
    draws.reserve(geometry.frames.size() / 8U + 32U);
    double last_joint = -1.0e9;
    double last_lift = -1.0e9;
    double last_brake = -1.0e9;

    for (std::size_t i = 0; i < geometry.frames.size(); ++i) {
        const auto& frame = geometry.frames[i];
        if (frame.drive_mode == DriveMode::Lift) {
            if (frame.distance_m - last_lift >= skin.chain_lift_spacing_m) {
                append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::chain_lift,
                                            camera, viewport_width, viewport_height, skin);
                last_lift = frame.distance_m;
            }
            continue;
        }
        if (frame.drive_mode == DriveMode::Brake) {
            if (frame.distance_m - last_brake >= skin.brake_fin_spacing_m) {
                append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::brake_fin,
                                            camera, viewport_width, viewport_height, skin);
                last_brake = frame.distance_m;
            }
            continue;
        }
        if (frame.distance_m - last_joint >= skin.joint_plate_spacing_m) {
            append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::joint_plate,
                                        camera, viewport_width, viewport_height, skin);
            last_joint = frame.distance_m;
        }
    }

    std::stable_sort(draws.begin(), draws.end(), [](const auto& left, const auto& right) {
        return left.depth_key < right.depth_key;
    });
    SDL_SetTextureColorMod(atlas, 255, 255, 255);
    SDL_SetTextureAlphaMod(atlas, SDL_ALPHA_OPAQUE);
    for (const auto& draw : draws) {
        SDL_RenderTexture(renderer, atlas, &draw.source, &draw.destination);
    }
}

'''
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        raise RuntimeError("renderer insertion marker missing")
    if "render_coaster_track_overlay_modules" in text:
        raise RuntimeError("overlay renderer already present")
    text = text.replace(marker, overlay_code + marker, 1)

    tail = """    SDL_RenderGeometry(
        renderer,
        nullptr,
        vertices.data(),
        static_cast<int>(vertices.size()),
        indices.data(),
        static_cast<int>(indices.size()));
}"""
    replacement = """    SDL_RenderGeometry(
        renderer,
        nullptr,
        vertices.data(),
        static_cast<int>(vertices.size()),
        indices.data(),
        static_cast<int>(indices.size()));
    render_coaster_track_overlay_modules(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
}"""
    if text.count(tail) != 1:
        raise RuntimeError(f"renderer tail guard expected 1, got {text.count(tail)}")
    path.write_text(text.replace(tail, replacement, 1), encoding="utf-8")


def main() -> None:
    final_root = locate_final_root()
    manifest = build_atlas(final_root)
    patch_skin_contract()
    patch_geometry_contract()
    patch_renderer()
    print(json.dumps({
        "status": "ok",
        "contract": "CH_COASTER_TRACK_SKIN_ATLAS_V1",
        "atlas": str(ATLAS_PATH.relative_to(ROOT)),
        "sha256": manifest["atlas"]["sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
