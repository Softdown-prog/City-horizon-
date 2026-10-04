#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"patch anchor missing in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def promote_sprites(repo: Path, artifact: Path) -> None:
    runtime_dir = repo / "assets/rail/classic/turnouts"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    jobs = {
        "switch_left": artifact / "rail.classic.v7.01.switch_left.final",
        "switch_right": artifact / "rail.classic.v7.02.switch_right.final",
    }
    directions = ("south", "east", "north", "west")
    promoted: dict[str, dict[str, str]] = {}
    for kind, folder in jobs.items():
        files: dict[str, str] = {}
        for direction in directions:
            source = folder / f"transport.rail_track.classic.{kind}.01_{direction}_source.png"
            if not source.is_file():
                raise SystemExit(f"missing approved bake: {source}")
            target_name = f"transport.rail_track.classic.{kind}.01_{direction}.png"
            target = runtime_dir / target_name
            image = Image.open(source).convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
            image.save(target, optimize=True)
            files[direction] = target_name
        promoted[kind] = files

    manifest = {
        "contract": "CH_RAIL_RUNTIME_SPRITES_V1",
        "sourceArtifact": {
            "workflowRun": 37166371198,
            "artifactId": 11288884463,
            "sha256": "0d476f867fcf2b438f521981ed2deda11c5b8414d6f8dda5630db8e44029db18",
        },
        "cameraContract": "CH_CAMERA_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "runtimeResolution": [512, 512],
        "spriteAnchorPixels": [256.0, 380.0],
        "projectedFootprintWidthPixels": 435.36,
        "footprintTiles": [1, 1],
        "geometry": {
            "throughSpanTiles": 1.0,
            "divergingRadiusTiles": 0.5,
            "divergingAngleDegrees": 90.0,
            "ports": ["entry", "through_exit", "side_exit"],
        },
        "assets": {
            "switch_left": {
                "assetId": "transport.rail_track.classic.switch_left.01",
                "state": "approved_frozen_promoted_runtime",
                "files": promoted["switch_left"],
            },
            "switch_right": {
                "assetId": "transport.rail_track.classic.switch_right.01",
                "state": "approved_frozen_promoted_runtime",
                "files": promoted["switch_right"],
            },
        },
        "fallback": "procedural_renderer_when_sprite_unavailable",
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def patch_path_builder(repo: Path) -> None:
    path = repo / "src/rail_path_builder.h"
    marker = "    // Canonical turnout/points primitive. The through route remains straight,\n"
    block = r'''    // Approved City Horizon 1x1 modular turnout primitive. The piece enters at
    // one tile boundary, crosses the tile on the through route, and exposes a
    // perpendicular side port through a 90-degree half-tile-radius branch. This
    // mirrors CITY_HORIZON_RAIL_TRACK_V1 instead of stretching the art to a
    // shallow procedural turnout.
    [[nodiscard]] static RailTurnoutBuildResult modular_turnout(
        const RailWorldPoint3& start,
        const float start_heading_radians,
        const RailTurnDirection direction,
        const float tile_span = 1.0F,
        const int subdivisions = 48,
        const RailProfile& profile = {}) {
        if (!std::isfinite(tile_span) || tile_span <= 0.0F) {
            return {{RailValidationError::invalid_profile, "rail modular turnout has invalid tile span"}, {}, {}, 0.0F};
        }

        RailProfile modular_profile = profile;
        const float radius = tile_span * 0.5F;
        // This fixed tycoon module is intentionally tighter than free-form
        // curves. Relax only its local structural validation profile.
        modular_profile.min_turn_radius = std::min(modular_profile.min_turn_radius, radius * 0.90F);

        const RailPathBuildResult branch = quarter_curve(
            start, start_heading_radians, radius, direction,
            subdivisions, modular_profile);
        if (!branch) return {branch.validation, {}, {}, 0.0F};

        const RailPathBuildResult through = straight(
            start, start_heading_radians, tile_span,
            std::max(modular_profile.min_subdivisions, subdivisions), modular_profile);
        if (!through) return {through.validation, {}, {}, 0.0F};

        const RailBuildResult through_mesh = RailMeshBuilder::build(through.segment, modular_profile);
        const RailBuildResult branch_mesh = RailMeshBuilder::build(branch.segment, modular_profile);
        if (!through_mesh.ok()) return {through_mesh.validation, {}, {}, 0.0F};
        if (!branch_mesh.ok()) return {branch_mesh.validation, {}, {}, 0.0F};

        constexpr float kHalfPi = 1.57079632679489661923F;
        RailTurnoutBuildResult result;
        result.through = through.segment;
        result.diverging = branch.segment;
        result.diverging_exit_heading_radians = start_heading_radians +
            (direction == RailTurnDirection::left ? kHalfPi : -kHalfPi);
        result.validation = {};
        return result;
    }

'''
    replace_once(path, marker, block + marker)


def patch_graph(repo: Path) -> None:
    path = repo / "src/rail_placement_graph.h"
    marker = "    // At-grade diamond crossing. The primary route continues from `from`; the\n"
    block = r'''    [[nodiscard]] std::optional<RailPlacementTurnoutResult> append_modular_turnout(
        const RailPlacementNodeId from,
        const RailTurnDirection direction,
        const float tile_span = 1.0F,
        const int subdivisions = 48) {
        const RailPlacementNode* source = node(from);
        if (source == nullptr) return std::nullopt;

        const RailTurnoutBuildResult authored = RailPathBuilder::modular_turnout(
            source->position, source->heading_radians, direction,
            tile_span, subdivisions, profile_);
        if (!authored.ok() ||
            !mesh_safe_for_kind(authored.through, RailPlacementEdgeKind::turnout_through) ||
            !mesh_safe_for_kind(authored.diverging, RailPlacementEdgeKind::turnout_diverging)) {
            return std::nullopt;
        }
        if (nodes_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementNodeId>::max()) - 2U ||
            edges_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementEdgeId>::max()) - 2U) {
            return std::nullopt;
        }

        const RailPlacementCheckpoint before = checkpoint();
        const auto through_node = add_root(authored.through.end, source->heading_radians);
        const auto diverging_node = add_root(authored.diverging.end, authored.diverging_exit_heading_radians);
        if (!through_node || !diverging_node) {
            const bool rolled_back = rollback(before);
            (void)rolled_back;
            return std::nullopt;
        }

        const RailPlacementEdgeId through_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        const RailPlacementPieceId piece_group = static_cast<RailPlacementPieceId>(through_edge);
        edges_.push_back({through_edge, from, *through_node, RailPlacementEdgeKind::turnout_through, authored.through, piece_group, true});
        const RailPlacementEdgeId diverging_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({diverging_edge, from, *diverging_node, RailPlacementEdgeKind::turnout_diverging, authored.diverging, piece_group, true});
        return RailPlacementTurnoutResult{*through_node, *diverging_node, through_edge, diverging_edge};
    }

'''
    replace_once(path, marker, block + marker)
    replace_once(path, "!mesh_safe(edge_value.segment)) {", "!mesh_safe_for_kind(edge_value.segment, edge_value.kind)) {")
    old = r'''    [[nodiscard]] bool mesh_safe(const RailSplineSegment& segment) const {
        const RailBuildResult built = RailMeshBuilder::build(segment, profile_);
        if (!built.ok()) return false;
        return RailMeshBuilder::validate_mesh(built.geometry.ballast, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.sleepers, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.left_rail, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.right_rail, profile_).ok();
    }
'''
    new = r'''    [[nodiscard]] static bool mesh_safe_with_profile(const RailSplineSegment& segment,
                                                     const RailProfile& validation_profile) {
        const RailBuildResult built = RailMeshBuilder::build(segment, validation_profile);
        if (!built.ok()) return false;
        return RailMeshBuilder::validate_mesh(built.geometry.ballast, validation_profile).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.sleepers, validation_profile).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.left_rail, validation_profile).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.right_rail, validation_profile).ok();
    }

    [[nodiscard]] bool mesh_safe_for_kind(const RailSplineSegment& segment,
                                          const RailPlacementEdgeKind kind) const {
        if (kind == RailPlacementEdgeKind::turnout_diverging) {
            RailProfile modular_profile = profile_;
            modular_profile.min_turn_radius = std::min(modular_profile.min_turn_radius, 0.45F);
            return mesh_safe_with_profile(segment, modular_profile);
        }
        return mesh_safe_with_profile(segment, profile_);
    }

    [[nodiscard]] bool mesh_safe(const RailSplineSegment& segment) const {
        return mesh_safe_with_profile(segment, profile_);
    }
'''
    replace_once(path, old, new)


def patch_controller(repo: Path) -> None:
    path = repo / "src/rail_placement_controller.h"
    replace_once(
        path,
        "    explicit RailPlacementController(RailPlacementGraph& graph) : graph_(graph) {}\n",
        "    explicit RailPlacementController(RailPlacementGraph& graph, const bool modular_turnouts = false)\n"
        "        : graph_(graph), modular_turnouts_(modular_turnouts) {}\n",
    )
    replace_once(
        path,
        "            const auto result = graph_.append_quarter_curve(source_, metric_world, direction);\n",
        "            if (modular_turnouts_ && metric_world < 1.35F) break;\n"
        "            const auto result = graph_.append_quarter_curve(source_, metric_world, direction);\n",
    )
    old = r'''            constexpr float kTurnoutAngleRadians = 0.2617993877991494F; // 15 degrees
            const RailTurnDirection direction = mode_ == RailPlacementMode::turnout_left
                ? RailTurnDirection::left : RailTurnDirection::right;
            const auto result = graph_.append_turnout(
                source_, metric_world, kTurnoutAngleRadians, direction);
'''
    new = r'''            constexpr float kTurnoutAngleRadians = 0.2617993877991494F; // generic 15-degree turnout
            const RailTurnDirection direction = mode_ == RailPlacementMode::turnout_left
                ? RailTurnDirection::left : RailTurnDirection::right;
            const auto result = modular_turnouts_
                ? graph_.append_modular_turnout(source_, direction)
                : graph_.append_turnout(source_, metric_world, kTurnoutAngleRadians, direction);
'''
    replace_once(path, old, new)
    replace_once(path, "    bool active_ = false;\n", "    bool modular_turnouts_ = false;\n    bool active_ = false;\n")


def patch_runtime_bridge(repo: Path) -> None:
    path = repo / "src/rail_runtime_bridge.h"
    replace_once(
        path,
        "    RuntimeState()\n        : graph_(profile_), controller_(graph_), drag_(controller_), input_(drag_) {\n",
        "    RuntimeState()\n        : graph_(profile_), controller_(graph_, true), drag_(controller_), input_(drag_) {\n",
    )
    text = path.read_text(encoding="utf-8")
    render_start = text.index("    void render(SDL_Renderer* renderer,\n")
    render_end = text.index("\nprivate:\n", render_start)
    new_render = r'''    void render(SDL_Renderer* renderer,
                const CameraState& camera,
                const float viewport_width,
                const float viewport_height,
                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture) const {
        if (renderer == nullptr || graph_.edges().empty()) return;

        ProceduralRailRenderer::Palette committed_palette{};
        ProceduralRailRenderer::Palette hover_palette{};
        hover_palette.ballast = SDL_Color{111, 121, 129, 235};
        hover_palette.sleepers = SDL_Color{144, 111, 72, 255};
        hover_palette.rails = SDL_Color{237, 218, 128, 255};
        ProceduralRailRenderer::Palette valid_preview_palette{};
        valid_preview_palette.ballast = SDL_Color{124, 111, 74, 220};
        valid_preview_palette.sleepers = SDL_Color{125, 83, 42, 235};
        valid_preview_palette.rails = SDL_Color{219, 193, 95, 255};
        ProceduralRailRenderer::Palette invalid_preview_palette{};
        invalid_preview_palette.ballast = SDL_Color{129, 58, 54, 210};
        invalid_preview_palette.sleepers = SDL_Color{142, 58, 45, 235};
        invalid_preview_palette.rails = SDL_Color{232, 91, 76, 255};

        constexpr float kHalfPi = 1.57079632679489661923F;
        constexpr float kTwoPi = 6.28318530717958647692F;
        constexpr float kSpriteCanvasPixels = 512.0F;
        constexpr float kSpriteAnchorX = 256.0F;
        constexpr float kSpriteAnchorY = 380.0F;
        constexpr float kProjectedFootprintWidth = 435.36F;

        const auto diverging_edge_for = [&](const RailPlacementPieceId group) -> const RailPlacementEdge* {
            for (const RailPlacementEdge& candidate : graph_.edges()) {
                if (candidate.active && candidate.piece_group == group &&
                    candidate.kind == RailPlacementEdgeKind::turnout_diverging) {
                    return &candidate;
                }
            }
            return nullptr;
        };

        const auto render_turnout_sprite = [&](const RailPlacementEdge& through,
                                               const bool staged,
                                               const bool hovered) -> bool {
            const RailPlacementEdge* branch = diverging_edge_for(through.piece_group);
            if (branch == nullptr || !find_texture) return false;

            const float tx = through.segment.end.x - through.segment.start.x;
            const float ty = through.segment.end.y - through.segment.start.y;
            const float branch_x = branch->segment.end.x - branch->segment.start.x;
            const float branch_y = branch->segment.end.y - branch->segment.start.y;
            const float heading = std::atan2(ty, tx);
            int logical_turn = static_cast<int>(std::lround(heading / kHalfPi));
            const float snapped_heading = static_cast<float>(logical_turn) * kHalfPi;
            if (std::abs(std::remainder(heading - snapped_heading, kTwoPi)) > 0.03F) return false;
            logical_turn = ((logical_turn % 4) + 4) % 4;

            const float cross = tx * branch_y - ty * branch_x;
            const bool left = cross > 0.0F;
            const int visual_turn = (logical_turn - static_cast<int>(camera.rotation) + 4) % 4;
            const char* direction = visual_turn == 0 ? "south" :
                                    visual_turn == 1 ? "east" :
                                    visual_turn == 2 ? "north" : "west";
            const std::string kind = left ? "switch_left" : "switch_right";
            const std::filesystem::path sprite_path =
                std::filesystem::path("assets/rail/classic/turnouts") /
                ("transport.rail_track.classic." + kind + ".01_" + direction + ".png");
            const TextureAsset* sprite = find_texture(sprite_path);
            if (sprite == nullptr || sprite->texture == nullptr) return false;

            const RailWorldPoint3 center{
                (through.segment.start.x + through.segment.end.x) * 0.5F,
                (through.segment.start.y + through.segment.end.y) * 0.5F,
                (through.segment.start.z + through.segment.end.z) * 0.5F,
            };
            const ScreenPoint screen = world_to_screen_point(
                center.x, center.y, center.z, camera, viewport_width, viewport_height);
            const float scale = (static_cast<float>(contracts::kTileWidth) * camera.zoom) /
                                kProjectedFootprintWidth;
            const SDL_FRect destination{
                screen.x - kSpriteAnchorX * scale,
                screen.y - kSpriteAnchorY * scale,
                kSpriteCanvasPixels * scale,
                kSpriteCanvasPixels * scale,
            };

            Uint8 red = 255, green = 255, blue = 255, alpha = 255;
            if (staged) {
                if (preview_valid_) {
                    red = 244; green = 220; blue = 145; alpha = 224;
                } else {
                    red = 255; green = 112; blue = 102; alpha = 216;
                }
            } else if (hovered) {
                red = 255; green = 226; blue = 126;
            }
            (void)SDL_SetTextureColorMod(sprite->texture, red, green, blue);
            (void)SDL_SetTextureAlphaMod(sprite->texture, alpha);
            const bool rendered = SDL_RenderTexture(renderer, sprite->texture, nullptr, &destination);
            (void)SDL_SetTextureColorMod(sprite->texture, 255, 255, 255);
            (void)SDL_SetTextureAlphaMod(sprite->texture, 255);
            return rendered;
        };

        std::unordered_set<RailPlacementPieceId> sprite_backed_turnouts;
        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (!edge.active) continue;
            const bool staged = gesture_active_ &&
                static_cast<std::size_t>(edge.id) >= gesture_checkpoint_.edge_count;
            const bool hovered = !staged && hovered_piece_.has_value() &&
                edge.piece_group == *hovered_piece_;

            if (edge.kind == RailPlacementEdgeKind::turnout_through) {
                if (render_turnout_sprite(edge, staged, hovered)) {
                    sprite_backed_turnouts.insert(edge.piece_group);
                    continue;
                }
            }
            if (sprite_backed_turnouts.contains(edge.piece_group)) continue;

            const ProceduralRailRenderer::Palette& palette = staged
                ? (preview_valid_ ? valid_preview_palette : invalid_preview_palette)
                : (hovered ? hover_palette : committed_palette);
            RailProfile render_profile = profile_;
            if (edge.kind == RailPlacementEdgeKind::turnout_through ||
                edge.kind == RailPlacementEdgeKind::turnout_diverging) {
                render_profile.min_turn_radius = std::min(render_profile.min_turn_radius, 0.45F);
            }
            (void)ProceduralRailRenderer::render_segment(
                renderer, edge.segment, render_profile, camera,
                viewport_width, viewport_height, palette);
        }
    }
'''
    text = text[:render_start] + new_render + text[render_end:]

    validation_anchor = """            const RailPlacementEdge& edge = graph_.edges()[edge_index];\n            if (!edge.active) continue;\n            const RailSplineSegment& segment = edge.segment;\n"""
    validation_replacement = """            const RailPlacementEdge& edge = graph_.edges()[edge_index];\n            if (!edge.active) continue;\n            if (edge.kind == RailPlacementEdgeKind::turnout_through) {\n                const float dx = edge.segment.end.x - edge.segment.start.x;\n                const float dy = edge.segment.end.y - edge.segment.start.y;\n                constexpr float kTurnoutQuarterTurn = 1.57079632679489661923F;\n                constexpr float kTurnoutFullTurn = 6.28318530717958647692F;\n                const float heading = std::atan2(dy, dx);\n                const float snapped = std::round(heading / kTurnoutQuarterTurn) * kTurnoutQuarterTurn;\n                if (std::abs(std::remainder(heading - snapped, kTurnoutFullTurn)) > 0.03F) {\n                    if (error) *error = \"RAIL TURNOUT REQUIRES CARDINAL 90 DEG HEADING\";\n                    return false;\n                }\n            }\n            const RailSplineSegment& segment = edge.segment;\n"""
    if validation_anchor not in text:
        raise SystemExit("runtime staged validation anchor missing")
    text = text.replace(validation_anchor, validation_replacement, 1)

    old_wrapper = """inline void render(SDL_Renderer* renderer,\n                   const CameraState& camera,\n                   const float viewport_width,\n                   const float viewport_height) {\n    (void)kRailPersistenceRuntimeRegistered;\n    state().render(renderer, camera, viewport_width, viewport_height);\n}\n"""
    new_wrapper = """inline void render(SDL_Renderer* renderer,\n                   const CameraState& camera,\n                   const float viewport_width,\n                   const float viewport_height,\n                   const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture) {\n    (void)kRailPersistenceRuntimeRegistered;\n    state().render(renderer, camera, viewport_width, viewport_height, find_texture);\n}\n"""
    if old_wrapper not in text:
        raise SystemExit("rail runtime render wrapper anchor missing")
    text = text.replace(old_wrapper, new_wrapper, 1)
    text = text.replace(
        "        rail_runtime::render(renderer, camera, viewport_width, viewport_height);\n",
        "        rail_runtime::render(renderer, camera, viewport_width, viewport_height, find_texture);\n",
        1,
    )
    text = text.replace(
        "// append the procedural railway immediately above roads and below sidewalks.\n",
        "// append the hybrid railway immediately above roads and below sidewalks.\n"
        "// Approved turnout modules use CH Blender sprites; unfinished modules stay procedural.\n",
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    artifact = Path(args.artifact_dir).resolve()

    promote_sprites(repo, artifact)
    patch_path_builder(repo)
    patch_graph(repo)
    patch_controller(repo)
    patch_runtime_bridge(repo)

    runtime_dir = repo / "assets/rail/classic/turnouts"
    pngs = sorted(runtime_dir.glob("*.png"))
    if len(pngs) != 8:
        raise SystemExit(f"expected 8 promoted turnout PNGs, found {len(pngs)}")
    json.loads((runtime_dir / "manifest.json").read_text(encoding="utf-8"))
    print("approved turnout runtime promotion prepared")
    for path in pngs:
        print(path.relative_to(repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
