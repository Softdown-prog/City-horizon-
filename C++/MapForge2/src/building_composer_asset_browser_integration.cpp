#include "building_composer_widget.h"
#include "building_asset_browser_dialog.h"

#include <QCheckBox>
#include <QComboBox>
#include <QLabel>
#include <QSignalBlocker>
#include <QSlider>
#include <QSpinBox>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

int typologyIndex(BuildingTypology value) {
    switch (value) {
        case BuildingTypology::SmallHouse: return 1;
        case BuildingTypology::SuburbanHouse: return 2;
        case BuildingTypology::Cafeteria: return 3;
        case BuildingTypology::CornerShop: return 4;
        case BuildingTypology::Market: return 5;
        case BuildingTypology::Warehouse: return 6;
        case BuildingTypology::SmallTownHall: return 7;
        case BuildingTypology::School: return 8;
        case BuildingTypology::LowRiseResidential: return 9;
        case BuildingTypology::LowRiseOffice: return 10;
        case BuildingTypology::Custom: return 0;
    }
    return 0;
}

int footprintShapeIndex(BuildingFootprintShape value) {
    switch (value) {
        case BuildingFootprintShape::LShape: return 1;
        case BuildingFootprintShape::Courtyard: return 2;
        case BuildingFootprintShape::Annex: return 3;
        case BuildingFootprintShape::Rectangle: return 0;
    }
    return 0;
}

int roofIndex(BuildingRoofStyle value) {
    switch (value) {
        case BuildingRoofStyle::Gable: return 0;
        case BuildingRoofStyle::Hip: return 1;
        case BuildingRoofStyle::Pyramid: return 2;
        case BuildingRoofStyle::Flat: return 3;
        case BuildingRoofStyle::Shed: return 4;
        case BuildingRoofStyle::Mansard: return 5;
    }
    return 0;
}

int wallMaterialIndex(BuildingWallMaterial value) {
    switch (value) {
        case BuildingWallMaterial::Plaster: return 0;
        case BuildingWallMaterial::Brick: return 1;
        case BuildingWallMaterial::Concrete: return 2;
        case BuildingWallMaterial::Timber: return 3;
        case BuildingWallMaterial::Stone: return 4;
        case BuildingWallMaterial::MetalPanel: return 5;
        case BuildingWallMaterial::Glass: return 6;
        case BuildingWallMaterial::Solid: return 7;
    }
    return 0;
}

int roofMaterialIndex(BuildingRoofMaterial value) {
    switch (value) {
        case BuildingRoofMaterial::CeramicTile: return 0;
        case BuildingRoofMaterial::MetalSeam: return 1;
        case BuildingRoofMaterial::AsphaltShingle: return 2;
        case BuildingRoofMaterial::Solid: return 3;
    }
    return 0;
}

int doorPositionIndex(BuildingDoorPosition value) {
    switch (value) {
        case BuildingDoorPosition::Left: return 0;
        case BuildingDoorPosition::Center: return 1;
        case BuildingDoorPosition::Right: return 2;
    }
    return 1;
}

int windowPatternIndex(BuildingWindowPattern value) {
    switch (value) {
        case BuildingWindowPattern::Single: return 0;
        case BuildingWindowPattern::Pair: return 1;
        case BuildingWindowPattern::Strip: return 2;
    }
    return 1;
}

int materialScaleIndex(float scale) {
    if (scale < 0.86F) return 0;
    if (scale > 1.20F) return 2;
    return 1;
}

int quickFootprintIndex(const BuildingComposerSpec& spec) {
    if (spec.footprint_shape != BuildingFootprintShape::Rectangle) return 4;
    if (spec.footprint_width_tiles == 1 && spec.footprint_depth_tiles == 1) return 0;
    if (spec.footprint_width_tiles == 2 && spec.footprint_depth_tiles == 1) return 1;
    if (spec.footprint_width_tiles == 2 && spec.footprint_depth_tiles == 2) return 2;
    if (spec.footprint_width_tiles == 3 && spec.footprint_depth_tiles == 2) return 3;
    return 4;
}

} // namespace

void BuildingComposerWidget::applySpecToControls(const BuildingComposerSpec& loaded) {
    spec_ = loaded;

    const QSignalBlocker b1(typology_combo_), b2(footprint_combo_), b3(footprint_shape_combo_),
        b4(footprint_width_spin_), b5(footprint_depth_spin_), b6(footprint_cutout_width_spin_),
        b7(footprint_cutout_depth_spin_), b8(footprint_annex_depth_spin_), b9(footprint_annex_offset_spin_),
        b10(footprint_setback_front_spin_), b11(footprint_setback_back_spin_), b12(footprint_setback_left_spin_),
        b13(footprint_setback_right_spin_), b14(floor_count_spin_), b15(floor_height_spin_),
        b16(floor_bands_check_), b17(roof_combo_), b18(roof_pitch_slider_), b19(roof_overhang_slider_),
        b20(roof_fascia_slider_), b21(roof_ridge_slider_), b22(roof_fascia_check_), b23(roof_ridge_check_),
        b24(wall_material_combo_), b25(roof_material_combo_), b26(material_scale_combo_),
        b27(material_strength_slider_), b28(material_variation_slider_), b29(material_contrast_slider_),
        b30(material_seed_spin_), b31(door_position_combo_), b32(window_pattern_combo_),
        b33(roof_height_slider_), b34(windows_check_), b35(door_check_), b36(awning_check_),
        b37(sign_check_), b38(chimney_check_), b39(shadow_check_), b40(facade_editor_check_),
        b41(procedural_variation_check_), b42(procedural_variation_seed_spin_),
        b43(procedural_variation_strength_slider_), b44(procedural_vary_palette_check_),
        b45(procedural_vary_materials_check_), b46(procedural_vary_roof_check_),
        b47(procedural_vary_modules_check_);

    typology_combo_->setCurrentIndex(typologyIndex(loaded.building_typology));
    footprint_combo_->setCurrentIndex(quickFootprintIndex(loaded));
    footprint_shape_combo_->setCurrentIndex(footprintShapeIndex(loaded.footprint_shape));
    footprint_width_spin_->setValue(loaded.footprint_width_tiles);
    footprint_depth_spin_->setValue(loaded.footprint_depth_tiles);
    footprint_cutout_width_spin_->setValue(loaded.footprint_cutout_width_tiles);
    footprint_cutout_depth_spin_->setValue(loaded.footprint_cutout_depth_tiles);
    footprint_annex_depth_spin_->setValue(loaded.footprint_annex_depth_tiles);
    footprint_annex_offset_spin_->setValue(loaded.footprint_annex_offset_tiles);
    footprint_setback_front_spin_->setValue(static_cast<int>(std::round(loaded.footprint_setback_front_tiles * 10.0F)));
    footprint_setback_back_spin_->setValue(static_cast<int>(std::round(loaded.footprint_setback_back_tiles * 10.0F)));
    footprint_setback_left_spin_->setValue(static_cast<int>(std::round(loaded.footprint_setback_left_tiles * 10.0F)));
    footprint_setback_right_spin_->setValue(static_cast<int>(std::round(loaded.footprint_setback_right_tiles * 10.0F)));

    floor_count_spin_->setValue(loaded.floor_count);
    floor_height_spin_->setValue(loaded.floor_height_px);
    facade_floor_spin_->setMaximum(std::max(1, loaded.floor_count));
    floor_bands_check_->setChecked(loaded.floor_bands_enabled);
    roof_combo_->setCurrentIndex(roofIndex(loaded.roof_style));
    roof_pitch_slider_->setValue(static_cast<int>(std::round(loaded.roof_pitch_degrees)));
    roof_overhang_slider_->setValue(static_cast<int>(std::round(loaded.roof_overhang * 100.0F)));
    roof_fascia_slider_->setValue(static_cast<int>(std::round(loaded.roof_fascia_thickness_px * 10.0F)));
    roof_ridge_slider_->setValue(static_cast<int>(std::round(loaded.roof_ridge_scale * 100.0F)));
    roof_fascia_check_->setChecked(loaded.roof_fascia_enabled);
    roof_ridge_check_->setChecked(loaded.roof_ridge_enabled);
    roof_height_slider_->setValue(loaded.roof_height_px);

    wall_material_combo_->setCurrentIndex(wallMaterialIndex(loaded.wall_material));
    roof_material_combo_->setCurrentIndex(roofMaterialIndex(loaded.roof_material));
    material_scale_combo_->setCurrentIndex(materialScaleIndex(loaded.material_scale));
    material_strength_slider_->setValue(static_cast<int>(std::round(loaded.material_strength * 100.0F)));
    material_variation_slider_->setValue(static_cast<int>(std::round(loaded.material_variation * 100.0F)));
    material_contrast_slider_->setValue(static_cast<int>(std::round(loaded.material_contrast * 100.0F)));
    material_seed_spin_->setValue(loaded.material_seed);
    door_position_combo_->setCurrentIndex(doorPositionIndex(loaded.door_position));
    window_pattern_combo_->setCurrentIndex(windowPatternIndex(loaded.window_pattern));

    windows_check_->setChecked(loaded.windows);
    door_check_->setChecked(loaded.south_door);
    awning_check_->setChecked(loaded.south_awning);
    sign_check_->setChecked(loaded.south_sign);
    chimney_check_->setChecked(loaded.roof_chimney);
    shadow_check_->setChecked(loaded.cast_shadow);
    facade_editor_check_->setChecked(loaded.facade_editor_enabled);

    procedural_variation_check_->setChecked(loaded.procedural_variation_enabled);
    procedural_variation_seed_spin_->setValue(loaded.procedural_variation_seed);
    procedural_variation_strength_slider_->setValue(static_cast<int>(std::round(loaded.procedural_variation_strength * 100.0F)));
    procedural_vary_palette_check_->setChecked(loaded.procedural_vary_palette);
    procedural_vary_materials_check_->setChecked(loaded.procedural_vary_materials);
    procedural_vary_roof_check_->setChecked(loaded.procedural_vary_roof);
    procedural_vary_modules_check_->setChecked(loaded.procedural_vary_modules);

    refreshFacadeModuleList();
    refreshPreview();
}

void BuildingComposerWidget::openAssetBrowser() {
    BuildingAssetBrowserDialog browser(this);
    browser.setLibraryRoot(asset_library_root_);
    if (browser.exec() != QDialog::Accepted) {
        asset_library_root_ = browser.libraryRoot();
        return;
    }

    asset_library_root_ = browser.libraryRoot();
    BuildingComposerSpec loaded;
    if (!browser.selectedSpec(&loaded)) {
        if (summary_) summary_->setText(QStringLiteral("Asset selected, but this legacy package has no reopenable authoring snapshot."));
        return;
    }
    applySpecToControls(loaded);
    if (summary_) {
        summary_->setText(QStringLiteral("OPENED FROM ASSET BROWSER: %1 — editable and ready for normal validated re-export.")
            .arg(browser.selectedManifestPath()));
    }
}

} // namespace ch::studio
