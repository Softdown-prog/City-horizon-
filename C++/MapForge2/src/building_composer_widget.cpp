#include "building_composer_widget.h"
#include "building_export_pipeline.h"
#include "building_roof_editor_renderer.h"

#include "src/ch_core/contracts.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDir>
#include <QFile>
#include <QFileDialog>
#include <QFont>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QLabel>
#include <QPainter>
#include <QPixmap>
#include <QPolygonF>
#include <QPushButton>
#include <QSignalBlocker>
#include <QSlider>
#include <QSpinBox>
#include <QVBoxLayout>

#include <algorithm>
#include <array>

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

struct PreviewPoint {
    float x = 0.0F;
    float y = 0.0F;
};

PreviewPoint rotatePreviewPoint(const PreviewPoint point, const BuildingView view) {
    switch (view) {
        case BuildingView::East: return {-point.y, point.x};
        case BuildingView::North: return {-point.x, -point.y};
        case BuildingView::West: return {point.y, -point.x};
        case BuildingView::South: return point;
    }
    return point;
}

QPointF projectPreviewPoint(const PreviewPoint point, const BuildingView view, const QSize canvas) {
    const PreviewPoint rotated = rotatePreviewPoint(point, view);
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    return {
        static_cast<float>(canvas.width()) * 0.5F + (rotated.x - rotated.y) * half_tile_w,
        static_cast<float>(canvas.height()) - 42.0F + (rotated.x + rotated.y) * half_tile_h,
    };
}

QPolygonF previewQuad(const float x0, const float y0, const float x1, const float y1,
                      const BuildingView view, const QSize canvas) {
    return {
        projectPreviewPoint({x0, y0}, view, canvas),
        projectPreviewPoint({x1, y0}, view, canvas),
        projectPreviewPoint({x1, y1}, view, canvas),
        projectPreviewPoint({x0, y1}, view, canvas),
    };
}

void drawTerrainGrid(QPainter& painter, const BuildingView view, const QSize canvas) {
    painter.fillRect(QRect(QPoint(0, 0), canvas), QColor("#172025"));
    painter.setRenderHint(QPainter::Antialiasing, true);

    for (int y = -4; y <= 4; ++y) {
        for (int x = -4; x <= 4; ++x) {
            const bool alternate = ((x + y) & 1) != 0;
            const QColor grass = alternate ? QColor("#78995f") : QColor("#73945b");
            const QPolygonF tile = previewQuad(static_cast<float>(x), static_cast<float>(y),
                                               static_cast<float>(x + 1), static_cast<float>(y + 1),
                                               view, canvas);
            painter.setPen(QPen(QColor(73, 101, 64, 68), 0.55));
            painter.setBrush(grass);
            painter.drawPolygon(tile);
        }
    }
}

void drawStreetContext(QPainter& painter, const BuildingComposerSpec& spec,
                       const BuildingView view, const QSize canvas) {
    drawTerrainGrid(painter, view, canvas);

    const float half_w = static_cast<float>(std::max(1, spec.footprint_width_tiles)) * 0.5F;
    const float half_d = static_cast<float>(std::max(1, spec.footprint_depth_tiles)) * 0.5F;
    const float sidewalk_margin = std::clamp(spec.sidewalk_lateral_margin_tiles, 0.0F, 2.0F);
    const float sidewalk_depth = std::clamp(spec.sidewalk_depth_tiles, 0.0F, 1.0F);
    const float street_half_width = std::max(half_w + sidewalk_margin, 1.65F);

    // Logical south remains the authored frontage in this preview. The actual
    // road socket edge is exported as logical metadata and rotates with placement.
    const float sidewalk_y0 = half_d;
    const float sidewalk_y1 = half_d + (spec.sidewalk_enabled ? sidewalk_depth : 0.0F);
    if (spec.sidewalk_enabled && sidewalk_depth > 0.001F) {
        const QPolygonF sidewalk = previewQuad(-street_half_width, sidewalk_y0,
                                               street_half_width, sidewalk_y1,
                                               view, canvas);
        painter.setPen(QPen(QColor("#77766f"), 0.85));
        painter.setBrush(QColor("#b7b3aa"));
        painter.drawPolygon(sidewalk);

        painter.setPen(QPen(QColor(133, 131, 124, 150), 0.55));
        for (float x = -street_half_width + 0.45F; x < street_half_width; x += 0.45F) {
            painter.drawLine(projectPreviewPoint({x, sidewalk_y0}, view, canvas),
                             projectPreviewPoint({x, sidewalk_y1}, view, canvas));
        }
    }

    if (spec.road_socket_enabled) {
        const float road_y0 = sidewalk_y1;
        const float road_y1 = sidewalk_y1 + 0.82F;
        const QPolygonF road = previewQuad(-street_half_width - 0.25F, road_y0,
                                           street_half_width + 0.25F, road_y1,
                                           view, canvas);
        painter.setPen(QPen(QColor("#343a3d"), 1.0));
        painter.setBrush(QColor("#4a5052"));
        painter.drawPolygon(road);

        painter.setPen(QPen(QColor("#d0cbc0"), 1.0));
        painter.drawLine(projectPreviewPoint({-street_half_width, road_y0}, view, canvas),
                         projectPreviewPoint({street_half_width, road_y0}, view, canvas));

        const float lane_y = road_y0 + (road_y1 - road_y0) * 0.54F;
        painter.setPen(QPen(QColor(211, 198, 143, 178), 0.9, Qt::DashLine));
        painter.drawLine(projectPreviewPoint({-street_half_width + 0.25F, lane_y}, view, canvas),
                         projectPreviewPoint({street_half_width - 0.25F, lane_y}, view, canvas));
    }

    painter.setPen(QPen(QColor(238, 227, 199, 150), 0.65));
    painter.drawLine(projectPreviewPoint({-half_w, half_d}, view, canvas),
                     projectPreviewPoint({half_w, half_d}, view, canvas));
}

QImage renderEnvironmentReviewSheet(const BuildingComposerSpec& spec, const QSize cell) {
    constexpr int kHeader = 34;
    constexpr std::array<BuildingView, 4> views = {
        BuildingView::South, BuildingView::East, BuildingView::West, BuildingView::North,
    };

    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));
    QPainter painter(&sheet);
    painter.setRenderHint(QPainter::Antialiasing, true);
    QFont font(QStringLiteral("Arial"));
    font.setBold(true);
    font.setPointSize(9);
    painter.setFont(font);

    for (int i = 0; i < static_cast<int>(views.size()); ++i) {
        const int left = i * cell.width();
        painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter,
                         BuildingComposer::viewName(views[i]));

        QImage context(cell, QImage::Format_ARGB32_Premultiplied);
        context.fill(Qt::transparent);
        QPainter context_painter(&context);
        drawStreetContext(context_painter, spec, views[i], cell);
        context_painter.end();
        painter.drawImage(QPoint(left, kHeader), context);
        painter.drawImage(QPoint(left, kHeader),
                          BuildingRoofEditorRenderer::renderView(spec, views[i], cell));

        if (i > 0) {
            painter.setPen(QPen(QColor(58, 71, 76), 1.0));
            painter.drawLine(left, 0, left, sheet.height());
        }
    }
    painter.end();
    return sheet;
}

} // namespace

BuildingComposerWidget::BuildingComposerWidget(QWidget* parent)
    : QWidget(parent),
      spec_(BuildingComposer::presetSpec(BuildingVisualPreset::CityHorizonClassicTycoon)) {
    auto* root = new QVBoxLayout(this);

    auto* intro = new QLabel(
        "Building / Asset Composer — PILOT / Windows PC\n"
        "City Horizon Classic Tycoon remains the visual baseline. Preview context can show terrain, integrated sidewalk and street frontage without contaminating exported building sprites.",
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
    roof_fascia_slider_->setRange(5, 60);
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
    context_preview_check_ = new QCheckBox("Terrain + sidewalk + road preview", this);
    context_preview_check_->setChecked(true);
    context_preview_check_->setToolTip(
        "Preview-only environment context. Exported building PNGs remain transparent.");
    flags->addWidget(windows_check_);
    flags->addWidget(door_check_);
    flags->addWidget(awning_check_);
    flags->addWidget(sign_check_);
    flags->addWidget(chimney_check_);
    flags->addWidget(shadow_check_);
    flags->addWidget(context_preview_check_);
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
    auto* export_button = new QPushButton("Auto Export Validated Package…", this);
    export_button->setToolTip(
        "Exports individual RGBA views, 4-view sheet, review, thumbnail, manifest and validation report. Invalid footprint/halo blocks production output.");
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
    connect(context_preview_check_, &QCheckBox::toggled, this, [changed](bool) { changed(); });
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

    const bool context_enabled = context_preview_check_ != nullptr && context_preview_check_->isChecked();
    const QImage image = context_enabled
        ? renderEnvironmentReviewSheet(spec_, QSize(300, 250))
        : BuildingRoofEditorRenderer::renderReviewSheet(spec_, QSize(300, 250));
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
    const QSize export_frame = BuildingExportPipeline::recommendedFrame(spec_);

    summary_->setText(
        QString("%1 — %2×%3, %4 roof. Pitch %5°, overhang %6, fascia %7px, ridge %8x. "
                "Walls: %9. Roof material: %10. Material %11% / variation %12% / contrast %13%. "
                "Modules: %14. Preview context: %15. Auto-export frame: %16×%17.")
            .arg(BuildingComposer::visualPresetName(spec_.visual_preset))
            .arg(spec_.footprint_width_tiles)
            .arg(spec_.footprint_depth_tiles)
            .arg(BuildingRoofEditorRenderer::roofProfileName(spec_.roof_style))
            .arg(spec_.roof_pitch_degrees, 0, 'f', 0)
            .arg(spec_.roof_overhang, 0, 'f', 2)
            .arg(spec_.roof_fascia_thickness_px, 0, 'f', 1)
            .arg(spec_.roof_ridge_scale, 0, 'f', 2)
            .arg(BuildingComposer::wallMaterialName(spec_.wall_material))
            .arg(BuildingComposer::roofMaterialName(spec_.roof_material))
            .arg(static_cast<int>(spec_.material_strength * 100.0F))
            .arg(static_cast<int>(spec_.material_variation * 100.0F))
            .arg(static_cast<int>(spec_.material_contrast * 100.0F))
            .arg(module_text)
            .arg(context_enabled ? QStringLiteral("terrain + integrated sidewalk + road frontage")
                                 : QStringLiteral("asset only"))
            .arg(export_frame.width())
            .arg(export_frame.height()));
}

void BuildingComposerWidget::exportAsset() {
    const QString output_dir = QFileDialog::getExistingDirectory(
        this,
        "Auto Export Validated Building Package",
        QString());
    if (output_dir.isEmpty()) return;

    QString stem;
    QString error;
    BuildingExportValidation validation;
    const bool exported = BuildingExportPipeline::exportPackage(
        spec_, output_dir, &stem, &validation, &error);

    const QString validation_path = QDir(output_dir).filePath(stem + QStringLiteral("_validation.json"));
    if (!exported) {
        summary_->setText(
            QStringLiteral("EXPORT BLOCKED: %1. Validation report: %2")
                .arg(error, validation_path));
        return;
    }

    summary_->setText(
        QStringLiteral("AUTO EXPORTED: %1/%2_* — %3. Package includes SOUTH/EAST/WEST/NORTH RGBA PNGs, 4-view sheet, review sheet, thumbnail, manifest and validation report. Environment preview remains excluded.")
            .arg(output_dir, stem, validation.summary()));
}

} // namespace ch::studio
