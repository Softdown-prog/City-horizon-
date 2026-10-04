from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_ROOT = ROOT / "out" / "classic_steel_body_promotion"
REQUEST_PATH = ROOT / "tools" / "runtime_promotion_requests" / "classic_steel_body_v1.request.json"
ASSET_DIR = ROOT / "assets" / "coasters" / "skins" / "classic_steel_01" / "body"
MANIFEST_PATH = ASSET_DIR / "track_body_runtime.json"
RENDERER_PATH = ROOT / "src" / "coaster_sdl_renderer.h"

DIRECTIONS = ("south", "east", "west", "north")
EXPECTED_ASSET_ID = "coaster.track_skin.classic_steel_01.body"
EXPECTED_CONTRACT = "CH_COASTER_TRACK_BODY_BAKE_V1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"guarded replacement failed for {path}: expected 1 occurrence, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def locate_final_root() -> Path:
    candidates = []
    for report_path in DOWNLOAD_ROOT.rglob("final_bake_report.json"):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if report.get("contract") == EXPECTED_CONTRACT and report.get("assetId") == EXPECTED_ASSET_ID:
            candidates.append(report_path.parent)
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Classic Steel final root, found {len(candidates)}")
    return candidates[0]


def validate_and_promote(final_root: Path, request: dict) -> dict:
    report = json.loads((final_root / "final_bake_report.json").read_text(encoding="utf-8"))
    metadata = json.loads((final_root / "studio_metadata.json").read_text(encoding="utf-8"))
    approval = json.loads((final_root / "proxy_approval.json").read_text(encoding="utf-8"))

    if report.get("contract") != EXPECTED_CONTRACT or report.get("status") != "ok":
        raise RuntimeError("final bake report is not an approved CH_COASTER_TRACK_BODY_BAKE_V1")
    if report.get("assetId") != EXPECTED_ASSET_ID:
        raise RuntimeError("wrong assetId in final bake")
    if report.get("geometryAuthority") != "CH_COASTER_TRACK_GEOMETRY_V1":
        raise RuntimeError("track-body bake attempted to replace geometry authority")
    if report.get("runtimeRepresentation") != "2D_RGBA_track_body_skin":
        raise RuntimeError("unexpected runtime representation")
    if report.get("directionOrder") != list(DIRECTIONS):
        raise RuntimeError("unexpected direction order")

    expected_proxy = request["approvedProxySha256"]
    expected_source = request["sourceFingerprint"]
    if report.get("approvedProxySha256") != expected_proxy:
        raise RuntimeError("final report proxy approval does not match request")
    if approval.get("proxySha256") != expected_proxy or approval.get("reviewed") is not True:
        raise RuntimeError("proxy approval record does not match request")
    if metadata.get("sourceFingerprint") != expected_source:
        raise RuntimeError("source fingerprint does not match reviewed proxy")

    records = {entry["id"]: entry for entry in report.get("directions", [])}
    if set(records) != set(DIRECTIONS):
        raise RuntimeError("final bake is missing one or more directions")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    promoted = []
    expected_hashes = request["directionSha256"]
    for direction in DIRECTIONS:
        src = final_root / "runtime" / f"track_body_{direction}.png"
        if not src.is_file():
            raise RuntimeError(f"missing final render: {src}")
        actual = sha256(src)
        report_hash = records[direction].get("sha256")
        if actual != report_hash or actual != expected_hashes[direction]:
            raise RuntimeError(f"hash mismatch for {direction}: {actual}")
        dst = ASSET_DIR / src.name
        shutil.copy2(src, dst)
        promoted.append({
            "direction": direction,
            "path": dst.relative_to(ROOT).as_posix(),
            "sha256": actual,
            "bytes": dst.stat().st_size,
        })

    manifest = {
        "contract": "CH_COASTER_TRACK_BODY_RUNTIME_V1",
        "assetId": EXPECTED_ASSET_ID,
        "skinId": "classic_steel_01",
        "geometryAuthority": "CH_COASTER_TRACK_GEOMETRY_V1",
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "runtimeRepresentation": "2D_RGBA_track_body_skin",
        "bakeRun": request["bakeRun"],
        "artifact": request["artifact"],
        "approvedProxySha256": expected_proxy,
        "sourceFingerprint": expected_source,
        "resolutionPx": [256, 256],
        "groundOriginPx": [128.00006103515625, 203.8922233581543],
        "groundAnchorNormalized": [0.5000002384185791, 0.7964539974927902],
        "projectedTileWidthPx": 297.43548583984375,
        "canonicalTileWidthPx": 128,
        "spriteScaleAtZoom1": 0.43034542310436524,
        "moduleLengthMeters": 3.0,
        "directions": promoted,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def patch_renderer() -> None:
    text = RENDERER_PATH.read_text(encoding="utf-8")
    if "render_coaster_track_body_skin" in text:
        return

    marker = "[[nodiscard]] inline int coaster_overlay_module_row(const CoasterSkinOverlayModule module) noexcept {\n"
    if marker not in text:
        raise RuntimeError("Classic Steel body insertion marker missing from renderer")

    body_code = r'''struct CoasterTrackBodyDraw {
    SDL_Texture* texture = nullptr;
    SDL_FRect destination{};
    float depth_key = 0.0F;
};

[[nodiscard]] inline SDL_Texture* coaster_track_body_texture(
    SDL_Renderer* renderer,
    const CoasterTrackSkin& skin,
    const int direction_index) {
    if (renderer == nullptr || !skin.body_sprite_enabled ||
        direction_index < 0 || direction_index >= static_cast<int>(skin.body_sprite_paths.size())) {
        return nullptr;
    }
    const std::string path{skin.body_sprite_paths[static_cast<std::size_t>(direction_index)]};
    if (path.empty()) return nullptr;

    static std::unordered_map<SDL_Renderer*, std::unordered_map<std::string, SDL_Texture*>> cache;
    auto& renderer_cache = cache[renderer];
    if (const auto found = renderer_cache.find(path); found != renderer_cache.end()) {
        return found->second;
    }

    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface == nullptr) {
        renderer_cache.emplace(path, nullptr);
        return nullptr;  // Procedural track remains visible as the fallback.
    }
    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_DestroySurface(surface);
    if (texture != nullptr) {
        SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);
    }
    renderer_cache.emplace(path, texture);
    return texture;
}

inline void append_coaster_track_body_draw(
    std::vector<CoasterTrackBodyDraw>& draws,
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const std::size_t frame_index,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    if (frame_index >= geometry.frames.size()) return;
    const int direction_index = coaster_overlay_direction_column(geometry, frame_index, camera);
    SDL_Texture* texture = coaster_track_body_texture(renderer, skin, direction_index);
    if (texture == nullptr) return;

    const auto& frame = geometry.frames[frame_index];
    const WorldPoint3 anchor_world = coaster_meters_to_world(
        frame.center.x,
        frame.center.y,
        frame.center.z - skin.body_ground_below_center_m);
    const ScreenPoint anchor = world_to_screen_point(
        anchor_world, camera, viewport_width, viewport_height);
    const float sprite_scale = std::max(
        0.0F, skin.body_sprite_scale_at_zoom1 * std::max(0.0F, camera.zoom));
    const float width = static_cast<float>(skin.body_sprite_width_px) * sprite_scale;
    const float height = static_cast<float>(skin.body_sprite_height_px) * sprite_scale;
    if (!(width > 0.0F) || !(height > 0.0F)) return;

    CoasterTrackBodyDraw draw;
    draw.texture = texture;
    draw.destination = {
        anchor.x - width * skin.body_sprite_anchor_x,
        anchor.y - height * skin.body_sprite_anchor_y,
        width,
        height,
    };
    draw.depth_key = camera_depth_key(anchor_world.x, anchor_world.y, camera);
    draws.push_back(draw);
}

inline void render_coaster_track_body_skin(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    if (renderer == nullptr || !skin.body_sprite_enabled || geometry.frames.empty() ||
        !(skin.body_sprite_spacing_m > 0.0) || !(geometry.route_length_m > 0.0)) {
        return;
    }

    std::vector<CoasterTrackBodyDraw> draws;
    const std::size_t estimated = static_cast<std::size_t>(
        std::ceil(geometry.route_length_m / skin.body_sprite_spacing_m)) + 1U;
    draws.reserve(estimated);

    std::size_t cursor = 0U;
    std::size_t last_index = geometry.frames.size();
    const double end_distance = geometry.closed
        ? std::max(0.0, geometry.route_length_m - skin.body_sprite_spacing_m * 0.25)
        : geometry.route_length_m;
    for (double target = 0.0; target <= end_distance + 1.0e-6;
         target += skin.body_sprite_spacing_m) {
        while (cursor + 1U < geometry.frames.size() &&
               std::abs(geometry.frames[cursor + 1U].distance_m - target) <=
               std::abs(geometry.frames[cursor].distance_m - target)) {
            ++cursor;
        }
        if (cursor == last_index) continue;
        append_coaster_track_body_draw(
            draws, renderer, geometry, cursor, camera,
            viewport_width, viewport_height, skin);
        last_index = cursor;
    }

    std::stable_sort(draws.begin(), draws.end(), [](const auto& left, const auto& right) {
        return left.depth_key < right.depth_key;
    });
    for (const auto& draw : draws) {
        SDL_SetTextureColorMod(draw.texture, 255, 255, 255);
        SDL_SetTextureAlphaMod(draw.texture, SDL_ALPHA_OPAQUE);
        SDL_RenderTexture(renderer, draw.texture, nullptr, &draw.destination);
    }
}

'''
    text = text.replace(marker, body_code + marker, 1)

    old_call = """    render_coaster_track_overlay_modules(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
}"""
    new_call = """    // Full Blender body is presentation-only. The procedural geometry above
    // remains authoritative and doubles as the safe fallback when a PNG is absent.
    render_coaster_track_body_skin(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
    render_coaster_track_overlay_modules(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
}"""
    if text.count(old_call) != 1:
        raise RuntimeError("Classic Steel body render-call marker missing or ambiguous")
    text = text.replace(old_call, new_call, 1)
    RENDERER_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    if request.get("contract") != "CH_RUNTIME_PROMOTION_REQUEST_V1":
        raise RuntimeError("invalid promotion request contract")
    final_root = locate_final_root()
    manifest = validate_and_promote(final_root, request)
    patch_renderer()
    print(json.dumps({"status": "ok", "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
