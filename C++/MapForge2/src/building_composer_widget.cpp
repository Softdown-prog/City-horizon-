#include "building_composer_widget.h"
#include "building_export_pipeline.h"
#include "building_facade_renderer.h"
#include "building_footprint_model.h"
#include "building_roof_editor_renderer.h"

#include "src/ch_core/contracts.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDir>
#include <QFileDialog>
#include <QFont>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
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
            spec.wall_color = QColor("#d9d7cf"); spec.roof_color = QColor("#4d5961");
            spec.trim_color = QColor("#f7f7f3"); spec.glass_color = QColor("#7cb5c9");
            spec.door_color = QColor("#3f4b52"); spec.accent_color = QColor("#2f7f91");
            break;
        case 2:
            spec.wall_color = QColor("#d8b88a"); spec.roof_color = QColor("#7f5a45");
            spec.trim_color = QColor("#f1dfbf"); spec.glass_color = QColor("#82b7c7");
            spec.door_color = QColor("#5c3d2e"); spec.accent_color = QColor("#b46d37");
            break;
        default:
            spec.wall_color = QColor("#d8c3a5"); spec.roof_color = QColor("#a94e3f");
            spec.trim_color = QColor("#f2eadf"); spec.glass_color = QColor("#78b9d1");
            spec.door_color = QColor("#6d4c41"); spec.accent_color = QColor("#d79b38");
            break;
    }
}

BuildingStreetEdge edgeFromIndex(const int index) {
    switch (index) {
        case 1: return BuildingStreetEdge::East;
        case 2: return BuildingStreetEdge::North;
        case 3: return BuildingStreetEdge::West;
        default: return BuildingStreetEdge::South;
    }
}

BuildingTypology typologyFromIndex(const int index) {
    switch (index) {
        case 1: return BuildingTypology::SmallHouse;
        case 2: return BuildingTypology::SuburbanHouse;
        case 3: return BuildingTypology::Cafeteria;
        case 4: return BuildingTypology::CornerShop;
        case 5: return BuildingTypology::Market;
        case 6: return BuildingTypology::Warehouse;
        case 7: return BuildingTypology::SmallTownHall;
        case 8: return BuildingTypology::School;
        case 9: return BuildingTypology::LowRiseResidential;
        case 10: return BuildingTypology::LowRiseOffice;
        default: return BuildingTypology::Custom;
    }
}

BuildingFootprintShape footprintShapeFromIndex(const int index) {
    switch (index) {
        case 1: return BuildingFootprintShape::LShape;
        case 2: return BuildingFootprintShape::Courtyard;
        case 3: return BuildingFootprintShape::Annex;
        default: return BuildingFootprintShape::Rectangle;
    }
}

BuildingFacadeModuleKind moduleKindFromIndex(const int index) {
    switch (index) {
        case 1: return BuildingFacadeModuleKind::Door;
        case 2: return BuildingFacadeModuleKind::Storefront;
        case 3: return BuildingFacadeModuleKind::Sign;
        case 4: return BuildingFacadeModuleKind::Awning;
        case 5: return BuildingFacadeModuleKind::DoubleDoor;
        case 6: return BuildingFacadeModuleKind::GarageDoor;
        case 7: return BuildingFacadeModuleKind::Balcony;
        case 8: return BuildingFacadeModuleKind::Marquee;
        case 9: return BuildingFacadeModuleKind::Hvac;
        case 10: return BuildingFacadeModuleKind::Planter;
        default: return BuildingFacadeModuleKind::Window;
    }
}

struct PreviewPoint { float x = 0.0F; float y = 0.0F; };

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
    return {
        static_cast<float>(canvas.width()) * 0.5F + (rotated.x - rotated.y) * ch::contracts::kTileWidth * 0.5F,
        static_cast<float>(canvas.height()) - 42.0F + (rotated.x + rotated.y) * ch::contracts::kTileHeight * 0.5F,
    };
}

QPolygonF previewQuad(const float x0, const float y0, const float x1, const float y1,
                      const BuildingView view, const QSize canvas) {
    return {projectPreviewPoint({x0, y0}, view, canvas), projectPreviewPoint({x1, y0}, view, canvas),
            projectPreviewPoint({x1, y1}, view, canvas), projectPreviewPoint({x0, y1}, view, canvas)};
}

void drawTerrainGrid(QPainter& painter, const BuildingView view, const QSize canvas) {
    painter.fillRect(QRect(QPoint(0, 0), canvas), QColor("#172025"));
    painter.setRenderHint(QPainter::Antialiasing, true);
    for (int y = -4; y <= 4; ++y) {
        for (int x = -4; x <= 4; ++x) {
            painter.setPen(QPen(QColor(73, 101, 64, 68), 0.55));
            painter.setBrush(((x + y) & 1) ? QColor("#78995f") : QColor("#73945b"));
            painter.drawPolygon(previewQuad(static_cast<float>(x), static_cast<float>(y),
                                            static_cast<float>(x + 1), static_cast<float>(y + 1), view, canvas));
        }
    }
}

void drawFootprintMask(QPainter& painter, const BuildingComposerSpec& spec,
                       const BuildingView view, const QSize canvas) {
    const BuildingFootprintMask mask = BuildingFootprintModel::mask(spec);
    const float origin_x = -static_cast<float>(mask.width) * 0.5F;
    const float origin_y = -static_cast<float>(mask.depth) * 0.5F;
    painter.save();
    painter.setPen(QPen(QColor(239, 219, 164, 190), 1.05));
    painter.setBrush(QColor(217, 176, 92, 46));
    for (const QPoint& cell : mask.occupied_cells) {
        const float x0 = origin_x + static_cast<float>(cell.x());
        const float y0 = origin_y + static_cast<float>(cell.y());
        painter.drawPolygon(previewQuad(x0, y0, x0 + 1.0F, y0 + 1.0F, view, canvas));
    }
    painter.restore();
}

void drawStreetContext(QPainter& painter, const BuildingComposerSpec& spec,
                       const BuildingView view, const QSize canvas) {
    drawTerrainGrid(painter, view, canvas);
    drawFootprintMask(painter, spec, view, canvas);
    const float half_w = static_cast<float>(std::max(1, spec.footprint_width_tiles)) * 0.5F;
    const float half_d = static_cast<float>(std::max(1, spec.footprint_depth_tiles)) * 0.5F;
    const float sidewalk_margin = std::clamp(spec.sidewalk_lateral_margin_tiles, 0.0F, 2.0F);
    const float sidewalk_depth = std::clamp(spec.sidewalk_depth_tiles, 0.0F, 1.0F);
    const float street_half_width = std::max(half_w + sidewalk_margin, 1.65F);
    const float sidewalk_y0 = half_d;
    const float sidewalk_y1 = half_d + (spec.sidewalk_enabled ? sidewalk_depth : 0.0F);
    if (spec.sidewalk_enabled && sidewalk_depth > 0.001F) {
        painter.setPen(QPen(QColor("#77766f"), 0.85)); painter.setBrush(QColor("#b7b3aa"));
        painter.drawPolygon(previewQuad(-street_half_width, sidewalk_y0, street_half_width, sidewalk_y1, view, canvas));
        painter.setPen(QPen(QColor(133, 131, 124, 150), 0.55));
        for (float x = -street_half_width + 0.45F; x < street_half_width; x += 0.45F)
            painter.drawLine(projectPreviewPoint({x, sidewalk_y0}, view, canvas),
                             projectPreviewPoint({x, sidewalk_y1}, view, canvas));
    }
    if (spec.road_socket_enabled) {
        const float road_y0 = sidewalk_y1, road_y1 = sidewalk_y1 + 0.82F;
        painter.setPen(QPen(QColor("#343a3d"), 1.0)); painter.setBrush(QColor("#4a5052"));
        painter.drawPolygon(previewQuad(-street_half_width - 0.25F, road_y0,
                                        street_half_width + 0.25F, road_y1, view, canvas));
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
    constexpr std::array<BuildingView, 4> views = {BuildingView::South, BuildingView::East, BuildingView::West, BuildingView::North};
    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));
    QPainter painter(&sheet);
    QFont font(QStringLiteral("Arial")); font.setBold(true); font.setPointSize(9); painter.setFont(font);
    for (int i = 0; i < static_cast<int>(views.size()); ++i) {
        const int left = i * cell.width();
        painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter, BuildingComposer::viewName(views[i]));
        QImage context(cell, QImage::Format_ARGB32_Premultiplied); context.fill(Qt::transparent);
        QPainter cp(&context); drawStreetContext(cp, spec, views[i], cell); cp.end();
        painter.drawImage(QPoint(left, kHeader), context);
        painter.drawImage(QPoint(left, kHeader), BuildingFacadeRenderer::renderView(spec, views[i], cell));
        if (i > 0) { painter.setPen(QPen(QColor(58, 71, 76), 1.0)); painter.drawLine(left, 0, left, sheet.height()); }
    }
    painter.end();
    return sheet;
}

} // namespace

BuildingComposerWidget::BuildingComposerWidget(QWidget* parent)
    : QWidget(parent), spec_(BuildingComposer::presetSpec(BuildingVisualPreset::CityHorizonClassicTycoon)) {
    auto* root = new QVBoxLayout(this);
    auto* intro = new QLabel(
        "Building / Asset Composer — Windows PC\n"
        "Typology presets remain editable. Flexible footprint authoring adds rectangle, L, courtyard and annex placement masks with setbacks.", this);
    intro->setWordWrap(true); root->addWidget(intro);

    auto* form = new QFormLayout();
    form->addRow("Visual preset", new QLabel(BuildingComposer::visualPresetName(spec_.visual_preset), this));
    form->addRow("Module library", new QLabel(QStringLiteral("architectural_modules_2 / facade_editor_2 / flexible_footprint_1"), this));

    typology_combo_ = new QComboBox(this);
    typology_combo_->addItems({"Custom", "Small house", "Suburban house", "Cafeteria", "Corner shop", "Market", "Warehouse", "Small town hall", "School", "Low-rise residential", "Low-rise office"});
    form->addRow("Building typology", typology_combo_);

    footprint_combo_ = new QComboBox(this); footprint_combo_->addItems({"1×1", "2×1", "2×2", "3×2", "Custom"}); footprint_combo_->setCurrentIndex(1);
    form->addRow("Footprint quick size", footprint_combo_);
    footprint_shape_combo_ = new QComboBox(this); footprint_shape_combo_->addItems({"Rectangle", "L shape", "Courtyard", "Annex / stepped"});
    form->addRow("Footprint shape", footprint_shape_combo_);
    footprint_width_spin_ = new QSpinBox(this); footprint_width_spin_->setRange(1, 8); footprint_width_spin_->setValue(2); form->addRow("Footprint width", footprint_width_spin_);
    footprint_depth_spin_ = new QSpinBox(this); footprint_depth_spin_->setRange(1, 8); footprint_depth_spin_->setValue(1); form->addRow("Footprint depth", footprint_depth_spin_);
    footprint_cutout_width_spin_ = new QSpinBox(this); footprint_cutout_width_spin_->setRange(1, 6); footprint_cutout_width_spin_->setValue(1); form->addRow("Cutout width", footprint_cutout_width_spin_);
    footprint_cutout_depth_spin_ = new QSpinBox(this); footprint_cutout_depth_spin_->setRange(1, 6); footprint_cutout_depth_spin_->setValue(1); form->addRow("Cutout depth", footprint_cutout_depth_spin_);
    footprint_annex_depth_spin_ = new QSpinBox(this); footprint_annex_depth_spin_->setRange(1, 8); footprint_annex_depth_spin_->setValue(1); form->addRow("Annex depth", footprint_annex_depth_spin_);
    footprint_annex_offset_spin_ = new QSpinBox(this); footprint_annex_offset_spin_->setRange(0, 7); footprint_annex_offset_spin_->setValue(0); form->addRow("Annex offset", footprint_annex_offset_spin_);
    footprint_setback_front_spin_ = new QSpinBox(this); footprint_setback_front_spin_->setRange(0, 20); footprint_setback_front_spin_->setSuffix(" ×0.1 tile"); form->addRow("Front setback", footprint_setback_front_spin_);
    footprint_setback_back_spin_ = new QSpinBox(this); footprint_setback_back_spin_->setRange(0, 20); footprint_setback_back_spin_->setSuffix(" ×0.1 tile"); form->addRow("Back setback", footprint_setback_back_spin_);
    footprint_setback_left_spin_ = new QSpinBox(this); footprint_setback_left_spin_->setRange(0, 20); footprint_setback_left_spin_->setSuffix(" ×0.1 tile"); form->addRow("Left setback", footprint_setback_left_spin_);
    footprint_setback_right_spin_ = new QSpinBox(this); footprint_setback_right_spin_->setRange(0, 20); footprint_setback_right_spin_->setSuffix(" ×0.1 tile"); form->addRow("Right setback", footprint_setback_right_spin_);

    floor_count_spin_ = new QSpinBox(this); floor_count_spin_->setRange(1, 8); floor_count_spin_->setValue(1);
    form->addRow("Floors", floor_count_spin_);
    floor_height_spin_ = new QSpinBox(this); floor_height_spin_->setRange(36, 132); floor_height_spin_->setValue(82); floor_height_spin_->setSuffix(" px");
    form->addRow("Floor height", floor_height_spin_);
    floor_bands_check_ = new QCheckBox("Show floor bands", this); floor_bands_check_->setChecked(true);
    form->addRow("Floor articulation", floor_bands_check_);

    roof_combo_ = new QComboBox(this); roof_combo_->addItems({"Gable", "Hip", "Pyramid", "Flat", "Shed", "Mansard"});
    form->addRow("Roof profile", roof_combo_);
    roof_pitch_slider_ = new QSlider(Qt::Horizontal, this); roof_pitch_slider_->setRange(12, 60); roof_pitch_slider_->setValue(35); form->addRow("Roof pitch (deg)", roof_pitch_slider_);
    roof_overhang_slider_ = new QSlider(Qt::Horizontal, this); roof_overhang_slider_->setRange(0, 24); roof_overhang_slider_->setValue(10); form->addRow("Roof overhang", roof_overhang_slider_);
    roof_fascia_slider_ = new QSlider(Qt::Horizontal, this); roof_fascia_slider_->setRange(5, 60); roof_fascia_slider_->setValue(28); form->addRow("Fascia thickness", roof_fascia_slider_);
    roof_ridge_slider_ = new QSlider(Qt::Horizontal, this); roof_ridge_slider_->setRange(50, 180); roof_ridge_slider_->setValue(100); form->addRow("Ridge weight", roof_ridge_slider_);

    palette_combo_ = new QComboBox(this); palette_combo_->addItems({"Warm residential", "Cool modern", "Earth / rural"}); form->addRow("Color palette", palette_combo_);
    detail_preset_combo_ = new QComboBox(this); detail_preset_combo_->addItems({"Residence", "Small shop", "Utility / depot"}); form->addRow("Detail preset", detail_preset_combo_);
    wall_material_combo_ = new QComboBox(this); wall_material_combo_->addItems({"Plaster", "Brick", "Concrete", "Timber", "Stone", "Metal panel", "Glass", "Solid"}); form->addRow("Wall material", wall_material_combo_);
    roof_material_combo_ = new QComboBox(this); roof_material_combo_->addItems({"Ceramic tile", "Metal seam", "Asphalt shingle", "Solid"}); form->addRow("Roof material", roof_material_combo_);
    material_scale_combo_ = new QComboBox(this); material_scale_combo_->addItems({"Fine", "Medium", "Coarse"}); material_scale_combo_->setCurrentIndex(1); form->addRow("Texture scale", material_scale_combo_);
    material_strength_slider_ = new QSlider(Qt::Horizontal, this); material_strength_slider_->setRange(0, 100); material_strength_slider_->setValue(45); form->addRow("Material intensity", material_strength_slider_);
    material_variation_slider_ = new QSlider(Qt::Horizontal, this); material_variation_slider_->setRange(0, 100); material_variation_slider_->setValue(35); form->addRow("Tone variation", material_variation_slider_);
    material_contrast_slider_ = new QSlider(Qt::Horizontal, this); material_contrast_slider_->setRange(0, 100); material_contrast_slider_->setValue(45); form->addRow("Material contrast", material_contrast_slider_);
    material_seed_spin_ = new QSpinBox(this); material_seed_spin_->setRange(0, 9999); material_seed_spin_->setValue(17); form->addRow("Material seed", material_seed_spin_);
    door_position_combo_ = new QComboBox(this); door_position_combo_->addItems({"Left", "Center", "Right"}); door_position_combo_->setCurrentIndex(1); form->addRow("Legacy entrance socket", door_position_combo_);
    window_pattern_combo_ = new QComboBox(this); window_pattern_combo_->addItems({"Single", "Pair", "Strip"}); window_pattern_combo_->setCurrentIndex(1); form->addRow("Legacy window layout", window_pattern_combo_);
    roof_height_slider_ = new QSlider(Qt::Horizontal, this); roof_height_slider_->setRange(10, 64); roof_height_slider_->setValue(34); form->addRow("Roof base height", roof_height_slider_);
    root->addLayout(form);

    auto* facade_form = new QFormLayout();
    facade_editor_check_ = new QCheckBox("Use manual facade modules", this);
    facade_form->addRow("Facade editor", facade_editor_check_);
    facade_edge_combo_ = new QComboBox(this); facade_edge_combo_->addItems({"South", "East", "North", "West"}); facade_form->addRow("Facade", facade_edge_combo_);
    facade_floor_spin_ = new QSpinBox(this); facade_floor_spin_->setRange(1, 1); facade_floor_spin_->setValue(1); facade_form->addRow("Floor", facade_floor_spin_);
    facade_module_combo_ = new QComboBox(this);
    facade_module_combo_->addItems({"Window", "Door", "Storefront", "Sign", "Awning", "Double door", "Garage door", "Balcony", "Marquee", "Air conditioner", "Planter"});
    facade_form->addRow("Module", facade_module_combo_);
    facade_position_slider_ = new QSlider(Qt::Horizontal, this); facade_position_slider_->setRange(5, 95); facade_position_slider_->setValue(50); facade_form->addRow("Position", facade_position_slider_);
    facade_width_slider_ = new QSlider(Qt::Horizontal, this); facade_width_slider_->setRange(6, 90); facade_width_slider_->setValue(22); facade_form->addRow("Width", facade_width_slider_);
    root->addLayout(facade_form);

    auto* facade_buttons = new QHBoxLayout();
    auto* add_module = new QPushButton("Add module", this);
    auto* remove_module = new QPushButton("Remove selected", this);
    auto* clear_facade = new QPushButton("Clear selected facade", this);
    facade_buttons->addWidget(add_module); facade_buttons->addWidget(remove_module); facade_buttons->addWidget(clear_facade); facade_buttons->addStretch(1);
    root->addLayout(facade_buttons);
    facade_module_list_ = new QListWidget(this); facade_module_list_->setMaximumHeight(120); root->addWidget(facade_module_list_);

    auto* roof_flags = new QHBoxLayout();
    roof_fascia_check_ = new QCheckBox("Fascia", this); roof_fascia_check_->setChecked(true);
    roof_ridge_check_ = new QCheckBox("Ridge / hip cap", this); roof_ridge_check_->setChecked(true);
    roof_flags->addWidget(roof_fascia_check_); roof_flags->addWidget(roof_ridge_check_); roof_flags->addStretch(1); root->addLayout(roof_flags);

    auto* flags = new QHBoxLayout();
    windows_check_ = new QCheckBox("Legacy windows", this); windows_check_->setChecked(true);
    door_check_ = new QCheckBox("Legacy door", this); door_check_->setChecked(true);
    awning_check_ = new QCheckBox("Legacy awning", this); sign_check_ = new QCheckBox("Legacy sign", this);
    chimney_check_ = new QCheckBox("Chimney", this); shadow_check_ = new QCheckBox("Contact shadow", this); shadow_check_->setChecked(true);
    context_preview_check_ = new QCheckBox("Terrain + sidewalk + road preview", this); context_preview_check_->setChecked(true);
    for (QCheckBox* check : {windows_check_, door_check_, awning_check_, sign_check_, chimney_check_, shadow_check_, context_preview_check_}) flags->addWidget(check);
    flags->addStretch(1); root->addLayout(flags);

    preview_ = new QLabel(this); preview_->setAlignment(Qt::AlignCenter); preview_->setMinimumHeight(230);
    preview_->setStyleSheet("QLabel { background: #172025; border: 1px solid #46565d; padding: 6px; }"); root->addWidget(preview_, 1);
    summary_ = new QLabel(this); summary_->setWordWrap(true); root->addWidget(summary_);

    auto* buttons = new QHBoxLayout();
    auto* export_button = new QPushButton("Auto Export Validated Package…", this);
    buttons->addWidget(export_button); buttons->addStretch(1); root->addLayout(buttons);

    const auto changed = [this]() { refreshSpecFromControls(); refreshPreview(); };
    connect(typology_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this](int index){
        applyBuildingTypologyPreset(index); refreshSpecFromControls(); refreshFacadeModuleList(); refreshPreview();
    });
    connect(footprint_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(footprint_shape_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    for (QSpinBox* spin : {footprint_width_spin_, footprint_depth_spin_, footprint_cutout_width_spin_, footprint_cutout_depth_spin_,
                           footprint_annex_depth_spin_, footprint_annex_offset_spin_, footprint_setback_front_spin_, footprint_setback_back_spin_,
                           footprint_setback_left_spin_, footprint_setback_right_spin_})
        connect(spin, qOverload<int>(&QSpinBox::valueChanged), this, [changed](int){ changed(); });
    connect(floor_count_spin_, qOverload<int>(&QSpinBox::valueChanged), this, [this, changed](int value){ facade_floor_spin_->setMaximum(value); changed(); });
    connect(floor_height_spin_, qOverload<int>(&QSpinBox::valueChanged), this, [changed](int){ changed(); });
    connect(floor_bands_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(facade_editor_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(roof_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(roof_pitch_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(roof_overhang_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(roof_fascia_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(roof_ridge_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(roof_fascia_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(roof_ridge_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(palette_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(detail_preset_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this](int index){ applyDetailPreset(index); refreshSpecFromControls(); refreshPreview(); });
    connect(wall_material_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(roof_material_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(material_scale_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(material_strength_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(material_variation_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(material_contrast_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(material_seed_spin_, qOverload<int>(&QSpinBox::valueChanged), this, [changed](int){ changed(); });
    connect(door_position_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(window_pattern_combo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [changed](int){ changed(); });
    connect(roof_height_slider_, &QSlider::valueChanged, this, [changed](int){ changed(); });
    connect(windows_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(door_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(awning_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(sign_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(chimney_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(shadow_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(context_preview_check_, &QCheckBox::toggled, this, [changed](bool){ changed(); });
    connect(add_module, &QPushButton::clicked, this, [this](){ addFacadeModule(); });
    connect(remove_module, &QPushButton::clicked, this, [this](){ removeSelectedFacadeModule(); });
    connect(clear_facade, &QPushButton::clicked, this, [this](){ clearSelectedFacade(); });
    connect(export_button, &QPushButton::clicked, this, [this](){ exportAsset(); });

    applyDetailPreset(0); refreshSpecFromControls(); refreshFacadeModuleList(); refreshPreview();
}

void BuildingComposerWidget::applyBuildingTypologyPreset(const int index) {
    if (index <= 0) return;

    const QSignalBlocker b1(footprint_combo_), b2(floor_count_spin_), b3(floor_height_spin_), b4(floor_bands_check_),
                         b5(roof_combo_), b6(roof_pitch_slider_), b7(roof_overhang_slider_), b8(palette_combo_),
                         b9(detail_preset_combo_), b10(wall_material_combo_), b11(roof_material_combo_), b12(material_scale_combo_),
                         b13(material_strength_slider_), b14(material_variation_slider_), b15(material_contrast_slider_),
                         b16(facade_editor_check_), b17(windows_check_), b18(door_check_), b19(awning_check_),
                         b20(sign_check_), b21(chimney_check_), b22(roof_height_slider_), b23(footprint_shape_combo_);

    auto module = [this](BuildingFacadeModuleKind kind, BuildingStreetEdge edge, int floor,
                         float position, float width) {
        spec_.facade_modules.push_back({kind, edge, floor, position, width, true});
    };
    auto windows = [&module](BuildingStreetEdge edge, int floor) {
        module(BuildingFacadeModuleKind::Window, edge, floor, 0.25F, 0.18F);
        module(BuildingFacadeModuleKind::Window, edge, floor, 0.75F, 0.18F);
    };
    auto base = [this](int footprint, int floors, int floor_h, int roof, int pitch,
                       int palette, int detail, int wall_material, int roof_material) {
        footprint_combo_->setCurrentIndex(footprint);
        footprint_shape_combo_->setCurrentIndex(0);
        floor_count_spin_->setValue(floors);
        floor_height_spin_->setValue(floor_h);
        floor_bands_check_->setChecked(floors > 1);
        roof_combo_->setCurrentIndex(roof);
        roof_pitch_slider_->setValue(pitch);
        roof_overhang_slider_->setValue(10);
        palette_combo_->setCurrentIndex(palette);
        detail_preset_combo_->setCurrentIndex(detail);
        wall_material_combo_->setCurrentIndex(wall_material);
        roof_material_combo_->setCurrentIndex(roof_material);
        material_scale_combo_->setCurrentIndex(1);
        material_strength_slider_->setValue(45);
        material_variation_slider_->setValue(35);
        material_contrast_slider_->setValue(45);
        facade_editor_check_->setChecked(true);
        windows_check_->setChecked(false);
        door_check_->setChecked(false);
        awning_check_->setChecked(false);
        sign_check_->setChecked(false);
        chimney_check_->setChecked(false);
        facade_floor_spin_->setMaximum(floors);
        spec_.facade_modules.clear();
    };

    switch (index) {
        case 1:
            base(0, 1, 78, 0, 38, 0, 0, 0, 0); chimney_check_->setChecked(true);
            module(BuildingFacadeModuleKind::Door, BuildingStreetEdge::South, 0, 0.50F, 0.20F);
            module(BuildingFacadeModuleKind::Window, BuildingStreetEdge::South, 0, 0.20F, 0.18F);
            module(BuildingFacadeModuleKind::Window, BuildingStreetEdge::South, 0, 0.80F, 0.18F);
            module(BuildingFacadeModuleKind::Planter, BuildingStreetEdge::South, 0, 0.20F, 0.20F); break;
        case 2:
            base(1, 2, 72, 1, 32, 0, 0, 0, 0); chimney_check_->setChecked(true);
            module(BuildingFacadeModuleKind::Door, BuildingStreetEdge::South, 0, 0.20F, 0.16F);
            module(BuildingFacadeModuleKind::GarageDoor, BuildingStreetEdge::South, 0, 0.70F, 0.36F);
            windows(BuildingStreetEdge::South, 1); module(BuildingFacadeModuleKind::Balcony, BuildingStreetEdge::South, 1, 0.50F, 0.34F);
            windows(BuildingStreetEdge::East, 1); break;
        case 3:
            base(1, 1, 78, 3, 18, 1, 1, 2, 1); roof_height_slider_->setValue(10);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::South, 0, 0.32F, 0.42F);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.76F, 0.20F);
            module(BuildingFacadeModuleKind::Marquee, BuildingStreetEdge::South, 0, 0.50F, 0.82F);
            module(BuildingFacadeModuleKind::Sign, BuildingStreetEdge::South, 0, 0.50F, 0.44F);
            module(BuildingFacadeModuleKind::Planter, BuildingStreetEdge::South, 0, 0.10F, 0.16F);
            module(BuildingFacadeModuleKind::Planter, BuildingStreetEdge::South, 0, 0.90F, 0.16F); break;
        case 4:
            base(2, 2, 68, 3, 18, 0, 1, 1, 1); roof_height_slider_->setValue(10);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::South, 0, 0.38F, 0.48F);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.78F, 0.18F);
            module(BuildingFacadeModuleKind::Sign, BuildingStreetEdge::South, 0, 0.48F, 0.40F);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::East, 0, 0.50F, 0.56F);
            windows(BuildingStreetEdge::South, 1); windows(BuildingStreetEdge::East, 1); break;
        case 5:
            base(3, 1, 88, 3, 15, 1, 1, 2, 1); roof_height_slider_->setValue(10);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::South, 0, 0.28F, 0.42F);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.62F, 0.18F);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::South, 0, 0.84F, 0.20F);
            module(BuildingFacadeModuleKind::Marquee, BuildingStreetEdge::South, 0, 0.52F, 0.86F);
            module(BuildingFacadeModuleKind::Sign, BuildingStreetEdge::South, 0, 0.50F, 0.36F);
            module(BuildingFacadeModuleKind::Hvac, BuildingStreetEdge::East, 0, 0.72F, 0.20F); break;
        case 6:
            base(3, 1, 104, 4, 24, 1, 2, 5, 1);
            module(BuildingFacadeModuleKind::GarageDoor, BuildingStreetEdge::South, 0, 0.46F, 0.56F);
            module(BuildingFacadeModuleKind::Door, BuildingStreetEdge::South, 0, 0.87F, 0.12F);
            module(BuildingFacadeModuleKind::Sign, BuildingStreetEdge::South, 0, 0.50F, 0.30F);
            module(BuildingFacadeModuleKind::Hvac, BuildingStreetEdge::East, 0, 0.60F, 0.22F); break;
        case 7:
            base(3, 2, 76, 1, 34, 0, 0, 4, 0);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.50F, 0.20F);
            windows(BuildingStreetEdge::South, 0); windows(BuildingStreetEdge::South, 1); windows(BuildingStreetEdge::East, 0); windows(BuildingStreetEdge::East, 1);
            module(BuildingFacadeModuleKind::Marquee, BuildingStreetEdge::South, 0, 0.50F, 0.34F);
            module(BuildingFacadeModuleKind::Planter, BuildingStreetEdge::South, 0, 0.18F, 0.18F);
            module(BuildingFacadeModuleKind::Planter, BuildingStreetEdge::South, 0, 0.82F, 0.18F); break;
        case 8:
            base(3, 2, 72, 0, 26, 0, 0, 1, 0);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.50F, 0.22F);
            module(BuildingFacadeModuleKind::Marquee, BuildingStreetEdge::South, 0, 0.50F, 0.34F);
            for (float p : {0.14F, 0.32F, 0.68F, 0.86F}) module(BuildingFacadeModuleKind::Window, BuildingStreetEdge::South, 0, p, 0.12F);
            for (float p : {0.14F, 0.32F, 0.50F, 0.68F, 0.86F}) module(BuildingFacadeModuleKind::Window, BuildingStreetEdge::South, 1, p, 0.12F);
            windows(BuildingStreetEdge::East, 0); windows(BuildingStreetEdge::East, 1); break;
        case 9:
            base(2, 4, 62, 3, 15, 0, 0, 0, 2); roof_height_slider_->setValue(10);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.50F, 0.18F); windows(BuildingStreetEdge::South, 0);
            for (int floor = 1; floor < 4; ++floor) { windows(BuildingStreetEdge::South, floor); module(BuildingFacadeModuleKind::Balcony, BuildingStreetEdge::South, floor, 0.50F, 0.34F); windows(BuildingStreetEdge::East, floor); }
            break;
        case 10:
            base(2, 4, 64, 3, 15, 1, 1, 2, 1); roof_height_slider_->setValue(10);
            module(BuildingFacadeModuleKind::Storefront, BuildingStreetEdge::South, 0, 0.32F, 0.38F);
            module(BuildingFacadeModuleKind::DoubleDoor, BuildingStreetEdge::South, 0, 0.72F, 0.20F);
            module(BuildingFacadeModuleKind::Marquee, BuildingStreetEdge::South, 0, 0.52F, 0.72F);
            for (int floor = 1; floor < 4; ++floor) { windows(BuildingStreetEdge::South, floor); windows(BuildingStreetEdge::East, floor); }
            module(BuildingFacadeModuleKind::Hvac, BuildingStreetEdge::East, 3, 0.82F, 0.16F); break;
        default: break;
    }
}

void BuildingComposerWidget::applyDetailPreset(const int index) {
    if (!door_check_) return;
    const QSignalBlocker a(door_check_), b(windows_check_), c(awning_check_), d(sign_check_), e(chimney_check_),
                         f(door_position_combo_), g(window_pattern_combo_), h(wall_material_combo_), i(roof_material_combo_);
    if (index == 1) {
        door_check_->setChecked(true); windows_check_->setChecked(true); awning_check_->setChecked(true); sign_check_->setChecked(true); chimney_check_->setChecked(false);
        door_position_combo_->setCurrentIndex(0); window_pattern_combo_->setCurrentIndex(2); wall_material_combo_->setCurrentIndex(2); roof_material_combo_->setCurrentIndex(1);
    } else if (index == 2) {
        door_check_->setChecked(true); windows_check_->setChecked(true); awning_check_->setChecked(false); sign_check_->setChecked(false); chimney_check_->setChecked(false);
        door_position_combo_->setCurrentIndex(2); window_pattern_combo_->setCurrentIndex(0); wall_material_combo_->setCurrentIndex(3); roof_material_combo_->setCurrentIndex(1);
    } else {
        door_check_->setChecked(true); windows_check_->setChecked(true); awning_check_->setChecked(false); sign_check_->setChecked(false); chimney_check_->setChecked(true);
        door_position_combo_->setCurrentIndex(1); window_pattern_combo_->setCurrentIndex(1); wall_material_combo_->setCurrentIndex(0); roof_material_combo_->setCurrentIndex(0);
    }
}

void BuildingComposerWidget::refreshSpecFromControls() {
    spec_.visual_preset = BuildingVisualPreset::CityHorizonClassicTycoon;
    spec_.building_typology = typologyFromIndex(typology_combo_ ? typology_combo_->currentIndex() : 0);
    spec_.footprint_shape = footprintShapeFromIndex(footprint_shape_combo_ ? footprint_shape_combo_->currentIndex() : 0);
    const int footprint = footprint_combo_ ? footprint_combo_->currentIndex() : 1;
    if (footprint == 0) { spec_.footprint_width_tiles = 1; spec_.footprint_depth_tiles = 1; }
    else if (footprint == 1) { spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 1; }
    else if (footprint == 2) { spec_.footprint_width_tiles = 2; spec_.footprint_depth_tiles = 2; }
    else if (footprint == 3) { spec_.footprint_width_tiles = 3; spec_.footprint_depth_tiles = 2; }
    else { spec_.footprint_width_tiles = footprint_width_spin_ ? footprint_width_spin_->value() : 2; spec_.footprint_depth_tiles = footprint_depth_spin_ ? footprint_depth_spin_->value() : 1; }
    spec_.footprint_cutout_width_tiles = footprint_cutout_width_spin_ ? footprint_cutout_width_spin_->value() : 1;
    spec_.footprint_cutout_depth_tiles = footprint_cutout_depth_spin_ ? footprint_cutout_depth_spin_->value() : 1;
    spec_.footprint_annex_depth_tiles = footprint_annex_depth_spin_ ? footprint_annex_depth_spin_->value() : 1;
    spec_.footprint_annex_offset_tiles = footprint_annex_offset_spin_ ? footprint_annex_offset_spin_->value() : 0;
    spec_.footprint_setback_front_tiles = footprint_setback_front_spin_ ? footprint_setback_front_spin_->value() / 10.0F : 0.0F;
    spec_.footprint_setback_back_tiles = footprint_setback_back_spin_ ? footprint_setback_back_spin_->value() / 10.0F : 0.0F;
    spec_.footprint_setback_left_tiles = footprint_setback_left_spin_ ? footprint_setback_left_spin_->value() / 10.0F : 0.0F;
    spec_.footprint_setback_right_tiles = footprint_setback_right_spin_ ? footprint_setback_right_spin_->value() / 10.0F : 0.0F;

    spec_.floor_count = floor_count_spin_ ? floor_count_spin_->value() : 1;
    spec_.floor_height_px = floor_height_spin_ ? floor_height_spin_->value() : 82;
    spec_.wall_height_px = spec_.floor_height_px;
    spec_.floor_bands_enabled = !floor_bands_check_ || floor_bands_check_->isChecked();
    spec_.facade_editor_enabled = facade_editor_check_ && facade_editor_check_->isChecked();

    switch (roof_combo_ ? roof_combo_->currentIndex() : 0) {
        case 1: spec_.roof_style = BuildingRoofStyle::Hip; break; case 2: spec_.roof_style = BuildingRoofStyle::Pyramid; break;
        case 3: spec_.roof_style = BuildingRoofStyle::Flat; break; case 4: spec_.roof_style = BuildingRoofStyle::Shed; break;
        case 5: spec_.roof_style = BuildingRoofStyle::Mansard; break; default: spec_.roof_style = BuildingRoofStyle::Gable; break;
    }
    spec_.roof_height_px = roof_height_slider_ ? roof_height_slider_->value() : 34;
    spec_.roof_pitch_degrees = roof_pitch_slider_ ? static_cast<float>(roof_pitch_slider_->value()) : 35.0F;
    spec_.roof_overhang = roof_overhang_slider_ ? roof_overhang_slider_->value() / 100.0F : 0.10F;
    spec_.roof_fascia_thickness_px = roof_fascia_slider_ ? roof_fascia_slider_->value() / 10.0F : 2.8F;
    spec_.roof_ridge_scale = roof_ridge_slider_ ? roof_ridge_slider_->value() / 100.0F : 1.0F;
    spec_.roof_fascia_enabled = !roof_fascia_check_ || roof_fascia_check_->isChecked();
    spec_.roof_ridge_enabled = !roof_ridge_check_ || roof_ridge_check_->isChecked();
    if (spec_.roof_style == BuildingRoofStyle::Flat) spec_.roof_height_px = 10;

    const int door_position = door_position_combo_ ? door_position_combo_->currentIndex() : 1;
    spec_.door_position = door_position == 0 ? BuildingDoorPosition::Left : door_position == 2 ? BuildingDoorPosition::Right : BuildingDoorPosition::Center;
    const int window_pattern = window_pattern_combo_ ? window_pattern_combo_->currentIndex() : 1;
    spec_.window_pattern = window_pattern == 0 ? BuildingWindowPattern::Single : window_pattern == 2 ? BuildingWindowPattern::Strip : BuildingWindowPattern::Pair;

    const int wall_material = wall_material_combo_ ? wall_material_combo_->currentIndex() : 0;
    switch (wall_material) {
        case 1: spec_.wall_material = BuildingWallMaterial::Brick; break; case 2: spec_.wall_material = BuildingWallMaterial::Concrete; break;
        case 3: spec_.wall_material = BuildingWallMaterial::Timber; break; case 4: spec_.wall_material = BuildingWallMaterial::Stone; break;
        case 5: spec_.wall_material = BuildingWallMaterial::MetalPanel; break; case 6: spec_.wall_material = BuildingWallMaterial::Glass; break;
        case 7: spec_.wall_material = BuildingWallMaterial::Solid; break; default: spec_.wall_material = BuildingWallMaterial::Plaster; break;
    }
    const int roof_material = roof_material_combo_ ? roof_material_combo_->currentIndex() : 0;
    switch (roof_material) {
        case 1: spec_.roof_material = BuildingRoofMaterial::MetalSeam; break; case 2: spec_.roof_material = BuildingRoofMaterial::AsphaltShingle; break;
        case 3: spec_.roof_material = BuildingRoofMaterial::Solid; break; default: spec_.roof_material = BuildingRoofMaterial::CeramicTile; break;
    }
    const int texture_scale = material_scale_combo_ ? material_scale_combo_->currentIndex() : 1;
    spec_.material_scale = texture_scale == 0 ? 0.72F : texture_scale == 2 ? 1.45F : 1.0F;
    spec_.material_strength = material_strength_slider_ ? material_strength_slider_->value() / 100.0F : 0.45F;
    spec_.material_variation = material_variation_slider_ ? material_variation_slider_->value() / 100.0F : 0.35F;
    spec_.material_contrast = material_contrast_slider_ ? material_contrast_slider_->value() / 100.0F : 0.45F;
    spec_.material_seed = material_seed_spin_ ? material_seed_spin_->value() : 17;
    spec_.windows = !windows_check_ || windows_check_->isChecked(); spec_.south_door = !door_check_ || door_check_->isChecked();
    spec_.south_awning = awning_check_ && awning_check_->isChecked(); spec_.south_sign = sign_check_ && sign_check_->isChecked();
    spec_.roof_chimney = chimney_check_ && chimney_check_->isChecked(); spec_.cast_shadow = !shadow_check_ || shadow_check_->isChecked();
    applyPalette(spec_, palette_combo_ ? palette_combo_->currentIndex() : 0);
}

void BuildingComposerWidget::addFacadeModule() {
    refreshSpecFromControls();
    BuildingFacadeModulePlacement module;
    module.edge = edgeFromIndex(facade_edge_combo_ ? facade_edge_combo_->currentIndex() : 0);
    module.kind = moduleKindFromIndex(facade_module_combo_ ? facade_module_combo_->currentIndex() : 0);
    module.floor_index = std::clamp((facade_floor_spin_ ? facade_floor_spin_->value() : 1) - 1, 0, spec_.floor_count - 1);
    module.position = facade_position_slider_ ? facade_position_slider_->value() / 100.0F : 0.50F;
    module.width = facade_width_slider_ ? facade_width_slider_->value() / 100.0F : 0.22F;
    spec_.facade_modules.push_back(module);
    if (facade_editor_check_) facade_editor_check_->setChecked(true);
    spec_.facade_editor_enabled = true;
    refreshFacadeModuleList(); refreshPreview();
}

void BuildingComposerWidget::removeSelectedFacadeModule() {
    if (!facade_module_list_) return;
    const int row = facade_module_list_->currentRow();
    if (row < 0 || row >= static_cast<int>(spec_.facade_modules.size())) return;
    spec_.facade_modules.erase(spec_.facade_modules.begin() + row);
    refreshFacadeModuleList(); refreshPreview();
}

void BuildingComposerWidget::clearSelectedFacade() {
    const BuildingStreetEdge edge = edgeFromIndex(facade_edge_combo_ ? facade_edge_combo_->currentIndex() : 0);
    spec_.facade_modules.erase(std::remove_if(spec_.facade_modules.begin(), spec_.facade_modules.end(),
        [edge](const BuildingFacadeModulePlacement& module){ return module.edge == edge; }), spec_.facade_modules.end());
    refreshFacadeModuleList(); refreshPreview();
}

void BuildingComposerWidget::refreshFacadeModuleList() {
    if (!facade_module_list_) return;
    facade_module_list_->clear();
    for (const auto& module : spec_.facade_modules) {
        facade_module_list_->addItem(QStringLiteral("%1 / F%2 / %3 / pos %4% / width %5%")
            .arg(BuildingComposer::streetEdgeName(module.edge).toUpper())
            .arg(module.floor_index + 1)
            .arg(BuildingComposer::facadeModuleKindName(module.kind))
            .arg(static_cast<int>(module.position * 100.0F))
            .arg(static_cast<int>(module.width * 100.0F)));
    }
}

void BuildingComposerWidget::refreshPreview() {
    if (!preview_ || !summary_) return;
    const bool context_enabled = context_preview_check_ && context_preview_check_->isChecked();
    const QImage image = context_enabled ? renderEnvironmentReviewSheet(spec_, QSize(300, 250))
                                         : BuildingFacadeRenderer::renderReviewSheet(spec_, QSize(300, 250));
    preview_->setPixmap(QPixmap::fromImage(image).scaled(qMax(240, preview_->width() - 12), qMax(190, preview_->height() - 12),
                                                      Qt::KeepAspectRatio, Qt::SmoothTransformation));
    const QSize export_frame = BuildingExportPipeline::recommendedFrame(spec_);
    const BuildingFootprintMask footprint = BuildingFootprintModel::mask(spec_);
    QString footprint_reason; const bool footprint_valid = BuildingFootprintModel::isValid(spec_, &footprint_reason);
    summary_->setText(QStringLiteral("%1 / %2 — footprint %3 %4×%5 (%6 occupied cells, %7). %8 floor(s) × %9px = %10px wall height. %11 roof. Facade editor: %12 (%13 modules). Preview: %14. Auto-export frame: %15×%16.")
        .arg(BuildingComposer::visualPresetName(spec_.visual_preset))
        .arg(BuildingComposer::typologyName(spec_.building_typology))
        .arg(BuildingFootprintModel::shapeName(spec_.footprint_shape))
        .arg(spec_.footprint_width_tiles).arg(spec_.footprint_depth_tiles)
        .arg(footprint.occupiedCount())
        .arg(footprint_valid ? QStringLiteral("valid") : footprint_reason)
        .arg(spec_.floor_count).arg(spec_.floor_height_px).arg(BuildingComposer::effectiveWallHeightPx(spec_))
        .arg(BuildingRoofEditorRenderer::roofProfileName(spec_.roof_style))
        .arg(spec_.facade_editor_enabled ? QStringLiteral("manual") : QStringLiteral("legacy automatic"))
        .arg(spec_.facade_modules.size())
        .arg(context_enabled ? QStringLiteral("terrain + sidewalk + road + footprint mask") : QStringLiteral("asset only"))
        .arg(export_frame.width()).arg(export_frame.height()));
}

void BuildingComposerWidget::exportAsset() {
    const QString output_dir = QFileDialog::getExistingDirectory(this, "Auto Export Validated Building Package", QString());
    if (output_dir.isEmpty()) return;
    QString stem, error; BuildingExportValidation validation;
    const bool exported = BuildingExportPipeline::exportPackage(spec_, output_dir, &stem, &validation, &error);
    const QString validation_path = QDir(output_dir).filePath(stem + QStringLiteral("_validation.json"));
    if (!exported) {
        summary_->setText(QStringLiteral("EXPORT BLOCKED: %1. Validation report: %2").arg(error, validation_path)); return;
    }
    summary_->setText(QStringLiteral("AUTO EXPORTED: %1/%2_* — %3. Flexible footprint mask, typology origin and facade/floor contract recorded in manifest.")
        .arg(output_dir, stem, validation.summary()));
}

} // namespace ch::studio
