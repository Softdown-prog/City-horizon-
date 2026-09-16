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
#include <QSlider>
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
            break;
        case 2:
            spec.wall_color = QColor("#d8b88a");
            spec.roof_color = QColor("#7f5a45");
            spec.trim_color = QColor("#f1dfbf");
            spec.glass_color = QColor("#82b7c7");
            spec.door_color = QColor("#5c3d2e");
            break;
        default:
            spec.wall_color = QColor("#d8c3a5");
            spec.roof_color = QColor("#a94e3f");
            spec.trim_color = QColor("#f2eadf");
            spec.glass_color = QColor("#78b9d1");
            spec.door_color = QColor("#6d4c41");
            break;
    }
}

} // namespace

BuildingComposerWidget::BuildingComposerWidget(QWidget* parent)
    : QWidget(parent) {
    auto* root = new QVBoxLayout(this);

    auto* intro = new QLabel(
        "Building / Asset Composer — PILOT\n"
        "Parametric geometry is the editable source; PNG RGBA remains the runtime output. "
        "The four views are generated from one structural definition so rotation never invents a different building.",
        this);
    intro->setWordWrap(true);
    root->addWidget(intro);

    auto* form = new QFormLayout();

    footprint_combo_ = new QComboBox(this);
    footprint_combo_->addItems({"1×1", "2×1", "2×2", "3×2"});
    footprint_combo_->setCurrentIndex(1);
    form->addRow("Footprint", footprint_combo_);

    roof_combo_ = new QComboBox(this);
    roof_combo_->addItems({"Gable", "Pyramid", "Flat"});
    form->addRow("Roof", roof_combo_);

    palette_combo_ = new QComboBox(this);
    palette_combo_->addItems({"Warm residential", "Cool modern", "Earth / rural"});
    form->addRow("Material preset", palette_combo_);

    wall_height_slider_ = new QSlider(Qt::Horizontal, this);
    wall_height_slider_->setRange(48, 132);
    wall_height_slider_->setValue(spec_.wall_height_px);
    wall_height_slider_->setSingleStep(4);
    form->addRow("Wall height", wall_height_slider_);

    root->addLayout(form);

    auto* flags = new QHBoxLayout();
    windows_check_ = new QCheckBox("Windows", this);
    windows_check_->setChecked(true);
    door_check_ = new QCheckBox("South door", this);
    door_check_->setChecked(true);
    shadow_check_ = new QCheckBox("Contact shadow", this);
    shadow_check_->setChecked(true);
    flags->addWidget(windows_check_);
    flags->addWidget(door_check_);
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
    connect(palette_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int) { changed(); });
    connect(wall_height_slider_, &QSlider::valueChanged, this, [changed](int) { changed(); });
    connect(windows_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(door_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(shadow_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
    connect(export_button, &QPushButton::clicked, this, [this]() { exportAsset(); });

    refreshSpecFromControls();
    refreshPreview();
}

void BuildingComposerWidget::refreshSpecFromControls() {
    const int footprint = footprint_combo_ != nullptr ? footprint_combo_->currentIndex() : 1;
    switch (footprint) {
        case 0: spec_.footprint_width_tiles = 1; spec_.footprint_depth_tiles = 1; break;
        case 2: spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 2; break;
        case 3: spec_.footprint_width_tiles = 3; spec_.footprint_depth_tiles = 2; break;
        default: spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 1; break;
    }

    const int roof = roof_combo_ != nullptr ? roof_combo_->currentIndex() : 0;
    spec_.roof_style = roof == 1 ? BuildingRoofStyle::Pyramid
        : (roof == 2 ? BuildingRoofStyle::Flat : BuildingRoofStyle::Gable);
    spec_.wall_height_px = wall_height_slider_ != nullptr ? wall_height_slider_->value() : 82;
    spec_.roof_height_px = spec_.roof_style == BuildingRoofStyle::Flat ? 10 : 34;
    spec_.windows = windows_check_ == nullptr || windows_check_->isChecked();
    spec_.south_door = door_check_ == nullptr || door_check_->isChecked();
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

    summary_->setText(
        QString("CH_BUILDING_COMPOSER_V0 / PILOT — %1×%2 tile footprint, %3 roof, %4 px walls. "
                "Logical entrance stays on the south façade; the four views share one geometry and one palette. Runtime target: PNG RGBA bitmap.")
            .arg(spec_.footprint_width_tiles)
            .arg(spec_.footprint_depth_tiles)
            .arg(BuildingComposer::roofName(spec_.roof_style))
            .arg(spec_.wall_height_px));
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
    manifest_file.write(QJsonDocument(BuildingComposer::manifest(spec_, frame)).toJson(QJsonDocument::Indented));
    manifest_file.close();

    summary_->setText("EXPORTED: " + path + " + " + manifest_path);
}

} // namespace ch::studio
