#pragma once

#include "building_composer.h"

#include <QWidget>

class QCheckBox;
class QComboBox;
class QLabel;
class QListWidget;
class QSlider;
class QSpinBox;

namespace ch::studio {

class BuildingComposerWidget final : public QWidget {
public:
    explicit BuildingComposerWidget(QWidget* parent = nullptr);

private:
    void refreshSpecFromControls();
    void refreshPreview();
    void refreshFacadeModuleList();
    void addFacadeModule();
    void removeSelectedFacadeModule();
    void clearSelectedFacade();
    void applyBuildingTypologyPreset(int index);
    void applyDetailPreset(int index);
    void exportAsset();

    BuildingComposerSpec spec_;

    QComboBox* typology_combo_ = nullptr;
    QComboBox* footprint_combo_ = nullptr;
    QComboBox* roof_combo_ = nullptr;
    QComboBox* palette_combo_ = nullptr;
    QComboBox* detail_preset_combo_ = nullptr;
    QComboBox* door_position_combo_ = nullptr;
    QComboBox* window_pattern_combo_ = nullptr;
    QComboBox* wall_material_combo_ = nullptr;
    QComboBox* roof_material_combo_ = nullptr;
    QComboBox* material_scale_combo_ = nullptr;
    QComboBox* facade_edge_combo_ = nullptr;
    QComboBox* facade_module_combo_ = nullptr;

    QSlider* wall_height_slider_ = nullptr;
    QSlider* roof_height_slider_ = nullptr;
    QSlider* roof_pitch_slider_ = nullptr;
    QSlider* roof_overhang_slider_ = nullptr;
    QSlider* roof_fascia_slider_ = nullptr;
    QSlider* roof_ridge_slider_ = nullptr;
    QSlider* material_strength_slider_ = nullptr;
    QSlider* material_variation_slider_ = nullptr;
    QSlider* material_contrast_slider_ = nullptr;
    QSlider* facade_position_slider_ = nullptr;
    QSlider* facade_width_slider_ = nullptr;

    QSpinBox* material_seed_spin_ = nullptr;
    QSpinBox* floor_count_spin_ = nullptr;
    QSpinBox* floor_height_spin_ = nullptr;
    QSpinBox* facade_floor_spin_ = nullptr;

    QCheckBox* windows_check_ = nullptr;
    QCheckBox* door_check_ = nullptr;
    QCheckBox* awning_check_ = nullptr;
    QCheckBox* sign_check_ = nullptr;
    QCheckBox* chimney_check_ = nullptr;
    QCheckBox* shadow_check_ = nullptr;
    QCheckBox* roof_fascia_check_ = nullptr;
    QCheckBox* roof_ridge_check_ = nullptr;
    QCheckBox* context_preview_check_ = nullptr;
    QCheckBox* facade_editor_check_ = nullptr;
    QCheckBox* floor_bands_check_ = nullptr;

    QListWidget* facade_module_list_ = nullptr;
    QLabel* preview_ = nullptr;
    QLabel* summary_ = nullptr;
};

} // namespace ch::studio
