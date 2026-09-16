#pragma once

#include "building_composer.h"

#include <QWidget>

class QCheckBox;
class QComboBox;
class QLabel;
class QSlider;

namespace ch::studio {

class BuildingComposerWidget final : public QWidget {
public:
    explicit BuildingComposerWidget(QWidget* parent = nullptr);

private:
    void refreshSpecFromControls();
    void refreshPreview();
    void exportAsset();

    BuildingComposerSpec spec_;

    QComboBox* footprint_combo_ = nullptr;
    QComboBox* roof_combo_ = nullptr;
    QComboBox* palette_combo_ = nullptr;
    QSlider* wall_height_slider_ = nullptr;
    QCheckBox* windows_check_ = nullptr;
    QCheckBox* door_check_ = nullptr;
    QCheckBox* shadow_check_ = nullptr;
    QLabel* preview_ = nullptr;
    QLabel* summary_ = nullptr;
};

} // namespace ch::studio
