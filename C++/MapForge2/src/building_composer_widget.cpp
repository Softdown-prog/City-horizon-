#include "building_composer_widget.h"

#include <QCheckBox>
#include <QComboBox>
#include <QFile>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QLabel>
#include <QPixmap>
#include <QPushButton>
#include <QSignalBlocker>
#include <QSlider>
#include <QSpinBox>
#include <QVBoxLayout>

namespace ch::studio {
namespace {

void applyPalette(BuildingComposerSpec& spec, const int index) {
    switch (index) {
        case 1:
            spec.wall_color = QColor("#d9d7cf");
            spec.roof_color = QColor("#4d5961");
            spec.trim_color = QColor("#f7f7f3");
            spec.glass_color = QColor("#7cb5c9");
            spec.door_color = QColor("#3f4b52");
            spec.accent_color = QColor("#2f7f91");
            break;
        case 2:
            spec.wall_color = QColor("#d8b88a");
            spec.roof_color = QColor("#7f5a45");
            spec.trim_color = QColor("#f1dfbf");
            spec.glass_color = QColor("#82b7c7");
            spec.door_color = QColor("#5c3d2e");
            spec.accent_color = QColor("#b46d37");
            break;
        default:
            spec.wall_color = QColor("#d8c3a5");
            spec.roof_color = QColor("#a94e3f");
            spec.trim_color = QColor("#f2eadf");
            spec.glass_color = QColor("#78b9d1");
            spec.door_color = QColor("#6d4c41");
            spec.accent_color = QColor("#d79b38");
            break;
    }
}

} // namespace

BuildingComposerWidget::BuildingComposerWidget(QWidget* parent)
    : QWidget(parent),
      spec_(BuildingComposer::presetSpec(BuildingVisualPreset::CityHorizonClassicTycoon)) {
    auto* root = new QVBoxLayout(this);

    auto* intro = new QLabel(
        "Building / Asset Composer — PILOT\n"
        "City Horizon Classic Tycoon remains the visual baseline. The roof editor now controls roof profile, pitch, overhang, fascia and ridge weight from one parametric definition.",
        this);
    intro->setWordWrap(true);
    root->addWidget(intro);

    auto* form = new QFormLayout();

    auto* visual_preset_label = new QLabel(BuildingComposer::visualPresetName(spec_.visual_preset), this);
    form->addRow("Visual preset", visual_preset_label);

    auto* module_library_label = new QLabel(QStringLiteral("architectural_modules_1"), this);
    form->addRow("Module library", module_library_label);

    footprint_combo_ = new QComboBox(this);
    footprint_combo_->addItems({"1×1", "2×1", "2×2", "3×2"});
    footprint_combo_->setCurrentIndex(1);
    form->addRow("Footprint", footprint_combo_);

    roof_combo_ = new QComboBox(this);
    roof_combo_->addItems({"Gable", "Hip", "Pyramid", "Flat", "Shed", "Mansard"});
    form->addRow("Roof profile", roof_combo_);

    roof_pitch_slider_ = new QSlider(Qt::Horizontal, this);
    roof_pitch_slider_->setRange(12, 60);
    roof_pitch_slider_->setValue(static_cast<int>(spec_.roof_pitch_degrees));
    roof_pitch_slider_->setSingleStep(1);
    form->addRow("Roof pitch (deg)", roof_pitch_slider_);

    roof_overhang_slider_ = new QSlider(Qt::Horizontal, this);
    roof_overhang_slider_->setRange(0, 24);
    roof_overhang_slider_->setValue(static_cast<int>(spec_.roof_overhang * 100.0F));
    roof_overhang_slider_->setSingleStep(1);
    form->addRow("Roof overhang", roof_overhang_slider_);

    roof_fascia_slider_ = new QSlider(Qt::Horizontal, this);
    roof_fascia_slider_->setRange(1, 60);
    roof_fascia_slider_->setValue(static_cast<int>(spec_.roof_fascia_thickness_px * 10.0F));
    roof_fascia_slider_->setSingleStep(2);
    form->addRow("Fascia thickness", roof_fascia_slider_);

    roof_ridge_slider_ = new QSlider(Qt::Horizontal, this);
    roof_ridge_slider_->setRange(50, 180);
    roof_ridge_slider_->setValue(static_cast<int>(spec_.roof_ridge_scale * 100.0F));
    roof_ridge_slider_->setSingleStep(5);
    form->addRow("Ridge weight", roof_ridge_slider_);

    palette_combo_ = new QComboBox(this);
    palette_combo_->addItems({"Warm residential", "Cool modern", "Earth / rural"});
    form->addRow("Color palette", palette_combo_);

    detail_preset_combo_ = new QComboBox(this);
    detail_preset_combo_->addItems({"Residence", "Small shop", "Utility / depot"});
    form->addRow("Detail preset", detail_preset_combo_);

    wall_material_combo_ = new QComboBox(this);
    wall_material_combo_->addItems({
        "Plaster", "Brick", "Concrete", "Timber",
        "Stone", "Metal panel", "Glass", "Solid"
    });
    form->addRow("Wall material", wall_material_combo_);

    roof_material_combo_ = new QComboBox(this);
    roof_material_combo_->addItems({"Ceramic tile", "Metal seam", "Asphalt shingle", "Solid"});
    form->addRow("Roof material", roof_material_combo_);

    material_scale_combo_ = new QComboBox(this);
    material_scale_combo_->addItems({"Fine", "Medium", "Coarse"});
    material_scale_combo_->setCurrentIndex(1);
    form->addRow("Texture scale", material_scale_combo_);

    material_strength_slider_ = new QSlider(Qt::Horizontal, this);
    material_strength_slider_->setRange(0, 100);
    material_strength_slider_->setValue(static_cast<int>(spec_.material_strength * 100.0F));
    material_strength_slider_->setSingleStep(5);
    form->addRow("Material intensity", material_strength_slider_);

    material_variation_slider_ = new QSlider(Qt::Horizontal, this);
    material_variation_slider_->setRange(0, 100);
    material_variation_slider_->setValue(static_cast<int>(spec_.material_variation * 100.0F));
    material_variation_slider_->setSingleStep(5);
    form->addRow("Tone variation", material_variation_slider_);

    material_contrast_slider_ = new QSlider(Qt::Horizontal, this);
    material_contrast_slider_->setRange(0, 100);
    material_contrast_slider_->setValue(static_cast<int>(spec_.material_contrast * 100.0F));
    material_contrast_slider_->setSingleStep(5);
    form->addRow("Material contrast", material_contrast_slider_);

    material_seed_spin_ = new QSpinBox(this);
    material_seed_spin_->setRange(0, 9999);
    material_seed_spin_->setValue(spec_.material_seed);
    form->addRow("Material seed", material_seed_spin_);

    door_position_combo_ = new QComboBox(this);
    door_position_combo_->addItems({"Left", "Center", "Right"});
    door_position_combo_->setCurrentIndex(1);
    form->addRow("Entrance socket", door_position_combo_);

    window_pattern_combo_ = new QComboBox(this);
    window_pattern_combo_->addItems({"Single", "Pair", "Strip"});
    window_pattern_combo_->setCurrentIndex(1);
    form->addRow("Window layout", window_pattern_combo_);

    wall_height_slider_ = new QSlider(Qt::Horizontal, this);
    wall_height_slider_->setRange(48, 132);
    wall_height_slider_->setValue(spec_.wall_height_px);
    wall_height_slider_->setSingleStep(4);
    form->addRow("Wall height", wall_height_slider_);

    roof_height_slider_ = new QSlider(Qt::Horizontal, this);
    roof_height_slider_->setRange(10, 64);
    roof_height_slider_->setValue(spec_.roof_height_px);
    roof_height_slider_->setSingleStep(2);
    form->addRow("Roof base height", roof_height_slider_);

    root->addLayout(form);

    auto* roof_flags = new QHBoxLayout();
    roof_fascia_check_ = new QCheckBox("Fascia", this);
    roof_fascia_check_->setChecked(spec_.roof_fascia_enabled);
    roof_ridge_check_ = new QCheckBox("Ridge / hip cap", this);
    roof_ridge_check_->setChecked(spec_.roof_ridge_enabled);
    roof_flags->addWidget(roof_fascia_check_);
    roof_flags->addWidget(roof_ridge_check_);
    roof_flags->addStretch(1);
    root->addLayout(roof_flags);

    auto* flags = new QHBoxLayout();
    windows_check_ = new QCheckBox("Window module", this);
    windows_check_->setChecked(true);
    door_check_ = new QCheckBox("Door module", this);
    door_check_->setChecked(true);
    awning_check_ = new QCheckBox("Awning module", this);
    sign_check_ = new QCheckBox("Sign module", this);
    chimney_check_ = new QCheckBox("Chimney module", this);
    shadow_check_ = new QCheckBox("Contact shadow", this);
    shadow_check_->setChecked(true);
    flags->addWidget(windows_check_);
    flags->addWidget(door_check_);
    flags->addWidget(awning_check_);
    flags->addWidget(sign_check_);
    flags->addWidget(chimney_check_);
    flags->addWidget(shadow_check_);
    flags->addStretch(1);
    root->addLayout(flags);

    preview_ = new QLabel(this);
    preview_->setAlignment(Qt::AlignCenter);
    preview_->setMinimumHeight(230);
    preview_->setStyleSheet("QLabel { background: #172025; border: 1px solid #46565d; padding: 6px; }");
    root->addWidget(preview_, 1);

    summary_ = new QLabel(this);
    summary_->setWordWrap(true);
    root->addWidget(summary_);

    auto* buttons = new QHBoxLayout();
    auto* export_button = new QPushButton("Export 4-view PNG + Manifest…", this);
    buttons->addWidget(export_button);
    buttons->addStretch(1);
    root->addLayout(buttons);

    const auto changed = [this]() {
        refreshSpecFromControls();
        refreshPreview();
    };
    connect(footprint_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(roof_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(roof_pitch_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(roof_overhang_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(roof_fascia_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(roof_ridge_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(roof_fascia_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(roof_ridge_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(palette_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(detail_preset_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this](int index) {
        applyDetailPreset(index);
        refreshSpecFromControls();
        refreshPreview();
    });
    connect(wall_material_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(roof_material_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(material_scale_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(material_strength_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(material_variation_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(material_contrast_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(material_seed_spin_, qOverload<int>(&QSpinBox::valueChanged), this, [changed](int) { changed(); });
    connect(door_position_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(window_pattern_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(wall_height_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(roof_height_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(windows_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(door_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(awning_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(sign_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(chimney_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(shadow_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(export_button, &QPushButton::clicked, this, [this]() { exportAsset(); });

    applyDetailPreset(0);
    refreshSpecFromControls();
    refreshPreview();
}

void BuildingComposerWidget::applyDetailPreset(const int index) {
    if (door_check_ == nullptr) return;

    const QSignalBlocker door_blocker(door_check_);
    const QSignalBlocker windows_blocker(windows_check_);
    const QSignalBlocker awning_blocker(awning_check_);
    const QSignalBlocker sign_blocker(sign_check_);
    const QSignalBlocker chimney_blocker(chimney_check_);
    const QSignalBlocker door_position_blocker(door_position_combo_);
    const QSignalBlocker window_pattern_blocker(window_pattern_combo_);
    const QSignalBlocker wall_material_blocker(wall_material_combo_);
    const QSignalBlocker roof_material_blocker(roof_material_combo_);

    switch (index) {
        case 1:
            door_check_->setChecked(true);
            windows_check_->setChecked(true);
            awning_check_->setChecked(true);
            sign_check_->setChecked(true);
            chimney_check_->setChecked(false);
            door_position_combo_->setCurrentIndex(0);
            window_pattern_combo_->setCurrentIndex(2);
            wall_material_combo_->setCurrentIndex(2);
            roof_material_combo_->setCurrentIndex(1);
            break;
        case 2:
            door_check_->setChecked(true);
            windows_check_->setChecked(true);
            awning_check_->setChecked(false);
            sign_check_->setChecked(false);
            chimney_check_->setChecked(false);
            door_position_combo_->setCurrentIndex(2);
            window_pattern_combo_->setCurrentIndex(0);
            wall_material_combo_->setCurrentIndex(3);
            roof_material_combo_->setCurrentIndex(1);
            break;
        default:
            door_check_->setChecked(true);
            windows_check_->setChecked(true);
            awning_check_->setChecked(false);
            sign_check_->setChecked(false);
            chimney_check_->setChecked(true);
            door_position_combo_->setCurrentIndex(1);
            window_pattern_combo_->setCurrentIndex(1);
            wall_material_combo_->setCurrentIndex(0);
            roof_material_combo_->setCurrentIndex(0);
            break;
    }
}

void BuildingComposerWidget::refreshSpecFromControls() {
    spec_.visual_preset = BuildingVisualPreset::CityHorizonClassicTycoon;
    spec_.window_module = BuildingWindowModule::ClassicFramed;
    spec_.door_module = BuildingDoorModule::ClassicWood;
    spec_.awning_module = BuildingAwningModule::CanvasCanopy;
    spec_.sign_module = BuildingSignModule::FacadePlaque;
    spec_.chimney_module = BuildingChimneyModule::MasonryCap;

    const int footprint = footprint_combo_ != nullptr ? footprint_combo_->currentIndex() : 1;
    switch (footprint) {
        case 0: spec_.footprint_width_tiles = 1; spec_.footprint_depth_tiles = 1; break;
        case 2: spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 2; break;
        case 3: spec_.footprint_width_tiles = 3; spec_.footprint_depth_tiles = 2; break;
        default: spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 1; break;
    }

    switch (roof_combo_ != nullptr ? roof_combo_->currentIndex() : 0) {
        case 1: spec_.roof_style = BuildingRoofStyle::Hip; break;
        case 2: spec_.roof_style = BuildingRoofStyle::Pyramid; break;
        case 3: spec_.roof_style = BuildingRoofStyle::Flat; break;
        case 4: spec_.roof_style = BuildingRoofStyle::Shed; break;
        case 5: spec_.roof_style = BuildingRoofStyle::Mansard; break;
        default: spec_.roof_style = BuildingRoofStyle::Gable; break;
    }

    spec_.wall_height_px = wall_height_slider_ != nullptr ? wall_height_slider_->value() : 82;
    spec_.roof_height_px = roof_height_slider_ != nullptr ? roof_height_slider_->value() : 34;
    spec_.roof_pitch_degrees = roof_pitch_slider_ != nullptr ? static_cast<float>(roof_pitch_slider_->value()) : 35.0F;
    spec_.roof_overhang = roof_overhang_slider_ != nullptr
        ? static_cast<float>(roof_overhang_slider_->value()) / 100.0F : 0.10F;
    spec_.roof_fascia_thickness_px = roof_fascia_slider_ != nullptr
        ? static_cast<float>(roof_fascia_slider_->value()) / 10.0F : 2.8F;
    spec_.roof_ridge_scale = roof_ridge_slider_ != nullptr
        ? static_cast<float>(roof_ridge_slider_->value()) / 100.0F : 1.0F;
    spec_.roof_fascia_enabled = roof_fascia_check_ == nullptr || roof_fascia_check_->isChecked();
    spec_.roof_ridge_enabled = roof_ridge_check_ == nullptr || roof_ridge_check_->isChecked();
    if (spec_.roof_style == BuildingRoofStyle::Flat) spec_.roof_height_px = 10;

    const int door_position = door_position_combo_ != nullptr ? door_position_combo_->currentIndex() : 1;
    spec_.door_position = door_position == 0 ? BuildingDoorPosition::Left
        : (door_position == 2 ? BuildingDoorPosition::Right : BuildingDoorPosition::Center);

    const int window_pattern = window_pattern_combo_ != nullptr ? window_pattern_combo_->currentIndex() : 1;
    spec_.window_pattern = window_pattern == 0 ? BuildingWindowPattern::Single
        : (window_pattern == 2 ? BuildingWindowPattern::Strip : BuildingWindowPattern::Pair);

    const int wall_material = wall_material_combo_ != nullptr ? wall_material_combo_->currentIndex() : 0;
    switch (wall_material) {
        case 1: spec_.wall_material = BuildingWallMaterial::Brick; break;
        case 2: spec_.wall_material = BuildingWallMaterial::Concrete; break;
        case 3: spec_.wall_material = BuildingWallMaterial::Timber; break;
        case 4: spec_.wall_material = BuildingWallMaterial::Stone; break;
        case 5: spec_.wall_material = BuildingWallMaterial::MetalPanel; break;
        case 6: spec_.wall_material = BuildingWallMaterial::Glass; break;
        case 7: spec_.wall_material = BuildingWallMaterial::Solid; break;
        default: spec_.wall_material = BuildingWallMaterial::Plaster; break;
    }

    const int roof_material = roof_material_combo_ != nullptr ? roof_material_combo_->currentIndex() : 0;
    switch (roof_material) {
        case 1: spec_.roof_material = BuildingRoofMaterial::MetalSeam; break;
        case 2: spec_.roof_material = BuildingRoofMaterial::AsphaltShingle; break;
        case 3: spec_.roof_material = BuildingRoofMaterial::Solid; break;
        default: spec_.roof_material = BuildingRoofMaterial::CeramicTile; break;
    }

    const int texture_scale = material_scale_combo_ != nullptr ? material_scale_combo_->currentIndex() : 1;
    spec_.material_scale = texture_scale == 0 ? 0.72F : (texture_scale == 2 ? 1.45F : 1.0F);
    spec_.material_strength = material_strength_slider_ != nullptr
        ? static_cast<float>(material_strength_slider_->value()) / 100.0F : 0.45F;
    spec_.material_variation = material_variation_slider_ != nullptr
        ? static_cast<float>(material_variation_slider_->value()) / 100.0F : 0.35F;
    spec_.material_contrast = material_contrast_slider_ != nullptr
        ? static_cast<float>(material_contrast_slider_->value()) / 100.0F : 0.45F;
    spec_.material_seed = material_seed_spin_ != nullptr ? material_seed_spin_->value() : 17;

    spec_.windows = windows_check_ == nullptr || windows_check_->isChecked();
    spec_.south_door = door_check_ == nullptr || door_check_->isChecked();
    spec_.south_awning = awning_check_ != nullptr && awning_check_->isChecked();
    spec_.south_sign = sign_check_ != nullptr && sign_check_->isChecked();
    spec_.roof_chimney = chimney_check_ != nullptr && chimney_check_->isChecked();
    spec_.cast_shadow = shadow_check_ == nullptr || shadow_check_->isChecked();
    applyPalette(spec_, palette_combo_ != nullptr ? palette_combo_->currentIndex() : 0);
}

void BuildingComposerWidget::refreshPreview() {
    if (preview_ == nullptr || summary_ == nullptr) return;

    const QImage image = BuildingComposer::renderReviewSheet(spec_, QSize(300, 250));
    const QPixmap pixmap = QPixmap::fromImage(image);
    preview_->setPixmap(pixmap.scaled(
        qMax(240, preview_->width() - 12),
        qMax(190, preview_->height() - 12),
        Qt::KeepAspectRatio,
        Qt::SmoothTransformation));

    QStringList modules;
    if (spec_.windows) modules << BuildingComposer::windowModuleId(spec_.window_module);
    if (spec_.south_door) modules << BuildingComposer::doorModuleId(spec_.door_module);
    if (spec_.south_awning) modules << BuildingComposer::awningModuleId(spec_.awning_module);
    if (spec_.south_sign) modules << BuildingComposer::signModuleId(spec_.sign_module);
    if (spec_.roof_chimney) modules << BuildingComposer::chimneyModuleId(spec_.chimney_module);
    const QString module_text = modules.isEmpty() ? QStringLiteral("none") : modules.join(", ");

    summary_->setText(
        QString("%1 — %2×%3, %4 roof. Pitch %5°, overhang %6, fascia %7px, ridge %8x. "
                "Walls: %9. Roof material: %10. Material %11% / variation %12% / contrast %13%. Modules: %14.")
            .arg(BuildingComposer::visualPresetName(spec_.visual_preset))
            .arg(spec_.footprint_width_tiles)
            .arg(spec_.footprint_depth_tiles)
            .arg(BuildingComposer::roofName(spec_.roof_style))
            .arg(spec_.roof_pitch_degrees, 0, 'f', 0)
            .arg(spec_.roof_overhang, 0, 'f', 2)
            .arg(spec_.roof_fascia_thickness_px, 0, 'f', 1)
            .arg(spec_.roof_ridge_scale, 0, 'f', 2)
            .arg(BuildingComposer::wallMaterialName(spec_.wall_material))
            .arg(BuildingComposer::roofMaterialName(spec_.roof_material))
            .arg(static_cast<int>(spec_.material_strength * 100.0F))
            .arg(static_cast<int>(spec_.material_variation * 100.0F))
            .arg(static_cast<int>(spec_.material_contrast * 100.0F))
            .arg(module_text));
}

void BuildingComposerWidget::exportAsset() {
    const QString path = QFileDialog::getSaveFileName(
        this,
        "Export Building Composer sprite sheet",
        "building_composer_4view.png",
        "PNG image (*.png)");
    if (path.isEmpty()) return;

    const QSize frame(320, 280);
    const QImage sheet = BuildingComposer::renderSpriteSheet(spec_, frame);
    if (!sheet.save(path, "PNG")) {
        summary_->setText("EXPORT ERROR: Could not write PNG.");
        return;
    }

    QString manifest_path = path;
    if (manifest_path.endsWith(".png", Qt::CaseInsensitive)) manifest_path.chop(4);
    manifest_path += ".json";

    QFile manifest_file(manifest_path);
    if (!manifest_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        summary_->setText("PNG exported, but manifest could not be written: " + manifest_path);
        return;
    }

    QJsonObject manifest = BuildingComposer::manifest(spec_, frame);
    manifest.insert(QStringLiteral("architecturalModules"), BuildingComposer::architecturalModules(spec_));
    manifest_file.write(QJsonDocument(manifest).toJson(QJsonDocument::Indented));
    manifest_file.close();

    summary_->setText("EXPORTED: " + path + " + " + manifest_path +
                      " / roof editor parameters and reusable module IDs recorded");
}

} // namespace ch::studio
