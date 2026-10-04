from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "tools/runtime_promotion_requests/carousel_city_horizon_v1.request.json"
SOURCE_ROOT = ROOT / "out/carousel_city_horizon_promotion"
DEST = ROOT / "assets/city_park/carousel"
DEFINITION = ROOT / "assets/definitions/carousel_city_horizon_01.json"
DIRECTIONS = ["south", "east", "west", "north"]
FRAME_COUNT = 48
FRAME_DURATION_MS = 100
SOURCE_SIZE = 384
RUNTIME_SIZE = 256
ASSET_ID = "attraction.park_carousel_city_horizon.01"
SOURCE_ASSET_ID = "park_carousel_city_horizon_01"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_manifest(name: str, contract: str) -> Path:
    matches = []
    for path in SOURCE_ROOT.rglob(name):
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("contract") == contract and payload.get("assetId") == SOURCE_ASSET_ID:
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {contract} manifest, found {len(matches)}: {matches}")
    return matches[0]


def require_frames(directory: Path) -> list[Path]:
    frames = sorted(directory.glob("frame_*.png"))
    if len(frames) != FRAME_COUNT:
        raise RuntimeError(f"Expected {FRAME_COUNT} frames in {directory}, got {len(frames)}")
    expected = [f"frame_{i:03d}.png" for i in range(FRAME_COUNT)]
    actual = [p.name for p in frames]
    if actual != expected:
        raise RuntimeError(f"Frame sequence is not contiguous in {directory}")
    return frames


def alpha_bounds(image: Image.Image) -> list[int]:
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    return list(bbox) if bbox else [0, 0, 0, 0]


def build_strip(frames: Iterable[Path], destination: Path, *, mask: bool) -> list[int]:
    frame_paths = list(frames)
    first_bounds: list[int] | None = None
    strip = Image.new("RGBA", (RUNTIME_SIZE * FRAME_COUNT, RUNTIME_SIZE), (0, 0, 0, 0))
    for index, path in enumerate(frame_paths):
        with Image.open(path) as source:
            rgba = source.convert("RGBA")
            if rgba.size != (SOURCE_SIZE, SOURCE_SIZE):
                raise RuntimeError(f"Unexpected source frame size {rgba.size} in {path}")
            resized = rgba.resize(
                (RUNTIME_SIZE, RUNTIME_SIZE),
                Image.Resampling.NEAREST if mask else Image.Resampling.LANCZOS,
            )
            if first_bounds is None:
                first_bounds = alpha_bounds(resized)
            strip.paste(resized, (index * RUNTIME_SIZE, 0))

    destination.parent.mkdir(parents=True, exist_ok=True)
    if mask:
        # Binary/near-binary color masks compress extremely well as indexed PNG and must stay lossless.
        encoded = strip.quantize(colors=4, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    else:
        # City Horizon runtime sprites are deliberately compact; indexed PNG preserves alpha and the stylized palette.
        encoded = strip.quantize(colors=192, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    encoded.save(destination, "PNG", optimize=True)
    return first_bounds or [0, 0, 0, 0]


def main() -> None:
    request = load_json(REQUEST)
    animation_manifest_path = find_manifest("animation_manifest.json", "CH_CAROUSEL_ANIMATION_FRAMES_V1")
    mask_manifest_path = find_manifest("primary_mask_manifest.json", "CH_COLOR_MASK_ANIMATION_FRAMES_V1")
    animation = load_json(animation_manifest_path)
    masks = load_json(mask_manifest_path)

    if animation.get("status") != "ok" or masks.get("status") != "ok":
        raise RuntimeError("CH Blender manifests are not marked ok")
    if animation.get("directions") != DIRECTIONS or masks.get("directions") != DIRECTIONS:
        raise RuntimeError("Direction contract mismatch")
    if animation.get("frameCount") != FRAME_COUNT or masks.get("frameCount") != FRAME_COUNT:
        raise RuntimeError("Frame count contract mismatch")
    if animation.get("frameDurationMs") != FRAME_DURATION_MS or masks.get("frameDurationMs") != FRAME_DURATION_MS:
        raise RuntimeError("Frame duration contract mismatch")
    if masks.get("channel") != "primary" or masks.get("encoding") != "white_on_black":
        raise RuntimeError("Primary color-mask contract mismatch")

    animation_root = animation_manifest_path.parent / "frames"
    mask_root = mask_manifest_path.parent / "masks" / "primary"
    DEST.mkdir(parents=True, exist_ok=True)

    runtime_directions: dict[str, dict] = {}
    runtime_masks: dict[str, dict] = {}
    frame_order = list(range(FRAME_COUNT))

    for direction in DIRECTIONS:
        source_frames = require_frames(animation_root / direction)
        source_masks = require_frames(mask_root / direction)

        sprite_name = f"{ASSET_ID}_{direction}_animation.png"
        mask_name = f"{ASSET_ID}_{direction}_primary_mask.png"
        sprite_path = DEST / sprite_name
        mask_path = DEST / mask_name

        bounds = build_strip(source_frames, sprite_path, mask=False)
        mask_bounds = build_strip(source_masks, mask_path, mask=True)
        if bounds != mask_bounds:
            # Mask may cover fewer interior pixels, but its transparent canvas/anchor must still be compatible.
            mask_bounds = bounds

        runtime_directions[direction] = {
            "sheet": sprite_name,
            "rows": 1,
            "columns": FRAME_COUNT,
            "frameOrder": frame_order,
            "frameResolution": [RUNTIME_SIZE, RUNTIME_SIZE],
            "firstFrameAlphaBounds": bounds,
            "sha256": sha256(sprite_path),
        }
        runtime_masks[direction] = {
            "sheet": mask_name,
            "rows": 1,
            "columns": FRAME_COUNT,
            "frameOrder": frame_order,
            "frameResolution": [RUNTIME_SIZE, RUNTIME_SIZE],
            "encoding": "white_on_black",
            "sha256": sha256(mask_path),
        }

    source_anim_copy = DEST / "source_animation_manifest.json"
    source_mask_copy = DEST / "source_primary_mask_manifest.json"
    source_anim_copy.write_text(json.dumps(animation, indent=2) + "\n", encoding="utf-8")
    source_mask_copy.write_text(json.dumps(masks, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "contract": "CH_ANIMATED_SPRITE_BAKE_V1",
        "assetId": ASSET_ID,
        "sourceAssetId": SOURCE_ASSET_ID,
        "assetType": "animated_attraction",
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "transparentCanvas": True,
        "backgroundIncluded": False,
        "directionOrder": DIRECTIONS,
        "frameStart": 0,
        "frameEnd": FRAME_COUNT - 1,
        "frameCount": FRAME_COUNT,
        "frameDurationMs": FRAME_DURATION_MS,
        "fps": 1000 // FRAME_DURATION_MS,
        "looping": True,
        "rotationDegreesPerLoop": animation.get("rotationDegreesPerLoop", 360.0),
        "horseBobAmplitude": animation.get("horseBobAmplitude", 0.14),
        "horseBobCyclesPerLoop": animation.get("horseBobCyclesPerLoop", 2.0),
        "sourceFrameResolution": [SOURCE_SIZE, SOURCE_SIZE],
        "frameResolution": [RUNTIME_SIZE, RUNTIME_SIZE],
        "pivot": {"x": 128, "y": 175},
        "footprint": {"width": 4, "height": 4, "anchor": [2.0, 2.0]},
        "directions": runtime_directions,
        "colorMasks": {
            "primary": {
                "semantic": masks.get("semantic"),
                "targetPanels": masks.get("targetPanels", []),
                "encoding": "white_on_black",
                "directions": runtime_masks,
            }
        },
        "source": {
            "repository": request["sourceRepository"],
            "runId": request["sourceRunId"],
            "artifactId": request["sourceArtifactId"],
            "artifactName": request["sourceArtifactName"],
            "headSha": request["sourceHeadSha"],
            "animationManifestSha256": sha256(animation_manifest_path),
            "primaryMaskManifestSha256": sha256(mask_manifest_path),
        },
        "productionStatus": "runtime_promoted_from_validated_ch_blender_batch_003",
    }
    runtime_manifest = DEST / f"{ASSET_ID}_runtime_manifest.json"
    runtime_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    sprite = lambda d: f"assets/city_park/carousel/{ASSET_ID}_{d}_animation.png"
    color_mask = lambda d: f"assets/city_park/carousel/{ASSET_ID}_{d}_primary_mask.png"
    definition = {
        "id": "carousel_city_horizon_01",
        "name": "Carrossel",
        "category": "city_park",
        "texture": sprite("south"),
        "sprites": {"0": sprite("south"), "1": sprite("west"), "2": sprite("north"), "3": sprite("east")},
        "spriteAnchors": {
            "0": {"x": 0.5, "y": 0.68359375},
            "1": {"x": 0.5, "y": 0.68359375},
            "2": {"x": 0.5, "y": 0.68359375},
            "3": {"x": 0.5, "y": 0.68359375},
        },
        "colorMasks": {
            "primary": {
                "semantic": masks.get("semantic"),
                "encoding": "white_on_black",
                "sprites": {"0": color_mask("south"), "1": color_mask("west"), "2": color_mask("north"), "3": color_mask("east")},
            }
        },
        "rotatable": True,
        "requiresRoadAccess": False,
        "requiresRoadOrPathAccess": False,
        "requiresTicketBooth": True,
        "grassOnly": True,
        "roadAccessMode": "any_perimeter",
        "accessPoints": [{"x": 2, "y": 4, "facing": "south"}],
        "footprint": {"width": 4, "height": 4},
        "occupancyFootprint": {"width": 4, "height": 4, "offsetX": 0, "offsetY": 0},
        "buildCost": 15000,
        "maintenancePerMonth": 0,
        "taxRevenuePerMonth": 0,
        "powerConsumption": 0,
        "serviceName": "Ingresso do carrossel",
        "defaultServicePrice": 5,
        "minimumServicePrice": 1,
        "maximumServicePrice": 30,
        "baseServiceCustomersPerMonth": 75,
        "servicePopulationForFullDemand": 50,
        "needsEffect": {"fun": 55},
        "artScale": 1.0,
        "animation": {"layout": "horizontal", "frameCount": FRAME_COUNT, "frameDurationMs": FRAME_DURATION_MS, "playback": "activity_loop"},
        "playerBuildable": True,
        "balanceStatus": "provisional",
        "productionStatus": "runtime_256_promoted",
        "renderClass": "attraction_256",
        "runtimeManifest": f"assets/city_park/carousel/{ASSET_ID}_runtime_manifest.json",
        "sourceChBlenderRunId": request["sourceRunId"],
        "sourceChBlenderHeadSha": request["sourceHeadSha"],
    }
    DEFINITION.parent.mkdir(parents=True, exist_ok=True)
    DEFINITION.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Promoted {ASSET_ID}: {len(DIRECTIONS)} directions x {FRAME_COUNT} frames + primary color masks")
    print(f"Runtime manifest: {runtime_manifest.relative_to(ROOT)}")
    print(f"Definition: {DEFINITION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
