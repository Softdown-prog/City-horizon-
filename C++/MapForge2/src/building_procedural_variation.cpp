#include "building_procedural_variation.h"

#include <QJsonArray>

#include <algorithm>
#include <cmath>
#include <random>
#include <vector>

namespace ch::studio {
namespace {

float randomUnit(std::mt19937& rng) {
    return std::uniform_real_distribution<float>(0.0F, 1.0F)(rng);
}

float randomSigned(std::mt19937& rng) {
    return randomUnit(rng) * 2.0F - 1.0F;
}

QColor variedColor(const QColor& source, std::mt19937& rng, const float strength) {
    const QColor hsl = source.toHsl();
    const int source_hue = hsl.hslHue();
    const int hue = source_hue >= 0
        ? (source_hue + static_cast<int>(std::round(randomSigned(rng) * 10.0F * strength)) + 360) % 360
        : 0;
    const int saturation = std::clamp(hsl.hslSaturation() + static_cast<int>(std::round(randomSigned(rng) * 22.0F * strength)), 0, 255);
    const int lightness = std::clamp(hsl.lightness() + static_cast<int>(std::round(randomSigned(rng) * 18.0F * strength)), 0, 255);
    QColor result;
    result.setHsl(hue, source_hue >= 0 ? saturation : 0, lightness, source.alpha());
    return result.toRgb();
}

template <typename T>
T choose(std::mt19937& rng, const std::vector<T>& values, const T fallback) {
    if (values.empty()) return fallback;
    std::uniform_int_distribution<int> distribution(0, static_cast<int>(values.size()) - 1);
    return values[distribution(rng)];
}

bool isAccessModule(const BuildingFacadeModuleKind kind) {
    return kind == BuildingFacadeModuleKind::Door ||
           kind == BuildingFacadeModuleKind::DoubleDoor ||
           kind == BuildingFacadeModuleKind::GarageDoor;
}

bool isDecorativeOptionalModule(const BuildingFacadeModuleKind kind) {
    return kind == BuildingFacadeModuleKind::Planter ||
           kind == BuildingFacadeModuleKind::Hvac ||
           kind == BuildingFacadeModuleKind::Sign;
}

std::vector<BuildingWallMaterial> wallMaterialsFor(const BuildingTypology typology) {
    switch (typology) {
        case BuildingTypology::SmallHouse:
        case BuildingTypology::SuburbanHouse:
        case BuildingTypology::LowRiseResidential:
            return {BuildingWallMaterial::Plaster, BuildingWallMaterial::Brick, BuildingWallMaterial::Timber};
        case BuildingTypology::Cafeteria:
        case BuildingTypology::CornerShop:
        case BuildingTypology::Market:
            return {BuildingWallMaterial::Plaster, BuildingWallMaterial::Brick, BuildingWallMaterial::Concrete};
        case BuildingTypology::Warehouse:
            return {BuildingWallMaterial::MetalPanel, BuildingWallMaterial::Concrete, BuildingWallMaterial::Brick};
        case BuildingTypology::SmallTownHall:
        case BuildingTypology::School:
            return {BuildingWallMaterial::Brick, BuildingWallMaterial::Stone, BuildingWallMaterial::Plaster};
        case BuildingTypology::LowRiseOffice:
            return {BuildingWallMaterial::Concrete, BuildingWallMaterial::Brick, BuildingWallMaterial::Glass};
        case BuildingTypology::Custom:
            return {};
    }
    return {};
}

std::vector<BuildingRoofMaterial> roofMaterialsFor(const BuildingTypology typology) {
    switch (typology) {
        case BuildingTypology::SmallHouse:
        case BuildingTypology::SuburbanHouse:
        case BuildingTypology::SmallTownHall:
        case BuildingTypology::School:
            return {BuildingRoofMaterial::CeramicTile, BuildingRoofMaterial::AsphaltShingle};
        case BuildingTypology::Cafeteria:
        case BuildingTypology::CornerShop:
        case BuildingTypology::Market:
        case BuildingTypology::Warehouse:
        case BuildingTypology::LowRiseOffice:
            return {BuildingRoofMaterial::MetalSeam, BuildingRoofMaterial::Solid};
        case BuildingTypology::LowRiseResidential:
            return {BuildingRoofMaterial::AsphaltShingle, BuildingRoofMaterial::Solid, BuildingRoofMaterial::MetalSeam};
        case BuildingTypology::Custom:
            return {};
    }
    return {};
}

std::vector<BuildingRoofStyle> roofStylesFor(const BuildingTypology typology) {
    switch (typology) {
        case BuildingTypology::SmallHouse:
        case BuildingTypology::SuburbanHouse:
            return {BuildingRoofStyle::Gable, BuildingRoofStyle::Hip};
        case BuildingTypology::Cafeteria:
        case BuildingTypology::CornerShop:
        case BuildingTypology::Market:
        case BuildingTypology::LowRiseOffice:
            return {BuildingRoofStyle::Flat, BuildingRoofStyle::Shed};
        case BuildingTypology::Warehouse:
            return {BuildingRoofStyle::Shed, BuildingRoofStyle::Gable, BuildingRoofStyle::Flat};
        case BuildingTypology::SmallTownHall:
        case BuildingTypology::School:
            return {BuildingRoofStyle::Gable, BuildingRoofStyle::Hip};
        case BuildingTypology::LowRiseResidential:
            return {BuildingRoofStyle::Flat, BuildingRoofStyle::Hip};
        case BuildingTypology::Custom:
            return {};
    }
    return {};
}

} // namespace

BuildingComposerSpec BuildingProceduralVariation::generate(const BuildingComposerSpec& base) {
    BuildingComposerSpec result = base;
    if (!base.procedural_variation_enabled) return result;

    const int seed = std::max(0, base.procedural_variation_seed);
    std::seed_seq seed_sequence{
        seed,
        static_cast<int>(base.building_typology) * 977,
        base.footprint_width_tiles * 131,
        base.footprint_depth_tiles * 211,
        base.floor_count * 307,
    };
    std::mt19937 rng(seed_sequence);
    const float strength = std::clamp(base.procedural_variation_strength, 0.0F, 1.0F);

    if (base.procedural_vary_palette) {
        result.wall_color = variedColor(base.wall_color, rng, strength);
        result.roof_color = variedColor(base.roof_color, rng, strength * 0.85F);
        result.trim_color = variedColor(base.trim_color, rng, strength * 0.45F);
        result.door_color = variedColor(base.door_color, rng, strength * 0.70F);
        result.accent_color = variedColor(base.accent_color, rng, strength);
    }

    if (base.procedural_vary_materials && strength > 0.05F) {
        if (randomUnit(rng) < 0.35F + strength * 0.45F)
            result.wall_material = choose(rng, wallMaterialsFor(base.building_typology), base.wall_material);
        if (randomUnit(rng) < 0.30F + strength * 0.40F)
            result.roof_material = choose(rng, roofMaterialsFor(base.building_typology), base.roof_material);
        result.material_strength = std::clamp(base.material_strength + randomSigned(rng) * 0.10F * strength, 0.15F, 0.78F);
        result.material_variation = std::clamp(base.material_variation + randomSigned(rng) * 0.14F * strength, 0.08F, 0.72F);
        result.material_contrast = std::clamp(base.material_contrast + randomSigned(rng) * 0.10F * strength, 0.18F, 0.72F);
        result.material_seed = seed * 17 + 31;
    }

    if (base.procedural_vary_roof && strength > 0.05F) {
        if (randomUnit(rng) < 0.22F + strength * 0.42F)
            result.roof_style = choose(rng, roofStylesFor(base.building_typology), base.roof_style);
        result.roof_pitch_degrees = std::clamp(base.roof_pitch_degrees + randomSigned(rng) * 5.0F * strength, 12.0F, 60.0F);
        result.roof_overhang = std::clamp(base.roof_overhang + randomSigned(rng) * 0.025F * strength, 0.0F, 0.24F);
        if (result.roof_style == BuildingRoofStyle::Flat)
            result.roof_height_px = 10;
    }

    if (base.procedural_vary_modules) {
        for (auto& module : result.facade_modules) {
            if (!module.enabled) continue;
            const bool required_access = module.floor_index == 0 &&
                                         module.edge == base.road_socket_edge &&
                                         isAccessModule(module.kind);
            if (required_access) continue;

            module.width = std::clamp(module.width + randomSigned(rng) * 0.055F * strength, 0.06F, 0.90F);
            module.position = std::clamp(module.position + randomSigned(rng) * 0.045F * strength,
                                         module.width * 0.5F,
                                         1.0F - module.width * 0.5F);
            if (isDecorativeOptionalModule(module.kind) && randomUnit(rng) < 0.14F * strength)
                module.enabled = false;
        }

        if (!base.facade_editor_enabled) {
            if (randomUnit(rng) < 0.45F * strength)
                result.window_pattern = static_cast<BuildingWindowPattern>(std::uniform_int_distribution<int>(0, 2)(rng));
            if (base.roof_chimney && randomUnit(rng) < 0.16F * strength)
                result.roof_chimney = false;
        }
    }

    // Geometry and access safety invariants. These assignments are intentional:
    // procedural siblings must remain placement-compatible with their authored base.
    result.footprint_shape = base.footprint_shape;
    result.footprint_width_tiles = base.footprint_width_tiles;
    result.footprint_depth_tiles = base.footprint_depth_tiles;
    result.footprint_cutout_width_tiles = base.footprint_cutout_width_tiles;
    result.footprint_cutout_depth_tiles = base.footprint_cutout_depth_tiles;
    result.footprint_annex_depth_tiles = base.footprint_annex_depth_tiles;
    result.footprint_annex_offset_tiles = base.footprint_annex_offset_tiles;
    result.footprint_setback_front_tiles = base.footprint_setback_front_tiles;
    result.footprint_setback_back_tiles = base.footprint_setback_back_tiles;
    result.footprint_setback_left_tiles = base.footprint_setback_left_tiles;
    result.footprint_setback_right_tiles = base.footprint_setback_right_tiles;
    result.floor_count = base.floor_count;
    result.floor_height_px = base.floor_height_px;
    result.road_socket_enabled = base.road_socket_enabled;
    result.road_socket_edge = base.road_socket_edge;
    result.road_socket_type = base.road_socket_type;
    result.road_socket_position = base.road_socket_position;
    result.road_socket_width_tiles = base.road_socket_width_tiles;
    result.sidewalk_enabled = base.sidewalk_enabled;
    result.sidewalk_depth_tiles = base.sidewalk_depth_tiles;
    result.sidewalk_lateral_margin_tiles = base.sidewalk_lateral_margin_tiles;
    result.procedural_variation_applied = true;
    return result;
}

QJsonObject BuildingProceduralVariation::manifest(const BuildingComposerSpec& spec) {
    return QJsonObject{
        {"version", QStringLiteral("controlled_procedural_variation_1")},
        {"enabled", spec.procedural_variation_enabled},
        {"applied", spec.procedural_variation_applied},
        {"seed", std::max(0, spec.procedural_variation_seed)},
        {"strength", static_cast<double>(std::clamp(spec.procedural_variation_strength, 0.0F, 1.0F))},
        {"varyPalette", spec.procedural_vary_palette},
        {"varyMaterials", spec.procedural_vary_materials},
        {"varyRoof", spec.procedural_vary_roof},
        {"varyModules", spec.procedural_vary_modules},
        {"preservesFootprint", true},
        {"preservesFloorCount", true},
        {"preservesRoadSocket", true},
        {"preservesRequiredGroundAccess", true},
        {"deterministic", true},
        {"visualPreset", BuildingComposer::visualPresetId(spec.visual_preset)},
        {"typology", BuildingComposer::typologyId(spec.building_typology)},
    };
}

} // namespace ch::studio
