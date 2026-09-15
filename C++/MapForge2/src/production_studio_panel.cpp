#include "production_studio_panel.h"

#include "src/ch_core/contracts.h"

#include <QDirIterator>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSaveFile>
#include <QTabWidget>
#include <QVBoxLayout>

#include <algorithm>

namespace ch::studio {
namespace {

constexpr auto kStudioProjectContract = "CH_STUDIO_PROJECT_V1";
constexpr int kPreviewMaxEdge = 420;
constexpr int kLibraryPreviewLimit = 500;

QLabel* makeWrappedLabel(const QString& text, QWidget* parent) {
    auto* label = new QLabel(text, parent);
    label->setWordWrap(true);
    label->setTextInteractionFlags(Qt::TextSelectableByMouse);
    return label;
}

QWidget* makeInfoPage(const QString& title, const QString& body, QWidget* parent) {
    auto* page = new QWidget(parent);
    auto* layout = new QVBoxLayout(page);

    auto* heading = new QLabel(title, page);
    QFont font = heading->font();
    font.setBold(true);
    font.setPointSize(font.pointSize() + 1);
    heading->setFont(font);

    layout->addWidget(heading);
    layout->addWidget(makeWrappedLabel(body, page));
    layout->addStretch(1);
    return page;
}

QString canonicalCameraSummary() {
    return QString(
        "Grid contract: %1\n"
        "Tile: %2 × %3 px (2:1)\n"
        "World rotation: %4°\n"
        "Isometric inclination: %5°\n"
        "Projection: fixed orthographic isometric\n"
        "Policy: project camera is authoritative; assets adapt to the project, not the reverse.")
        .arg(ch::contracts::kGridContract)
        .arg(ch::contracts::kTileWidth)
        .arg(ch::contracts::kTileHeight)
        .arg(ch::contracts::kHorizontalWorldRotationDeg, 0, 'f', 3)
        .arg(ch::contracts::kIsometricInclinationDeg, 0, 'f', 3);
}

} // namespace

ProductionStudioPanel::ProductionStudioPanel(QWidget* parent)
    : QWidget(parent), tabs_(new QTabWidget(this)) {
    auto* root = new QVBoxLayout(this);
    root->setContentsMargins(0, 0, 0, 0);

    auto* intro = makeWrappedLabel(
        "Production Workbench V1 — non-destructive foundation. Existing Map Forge / Studio systems remain intact. "
        "This layer starts turning the editor into a repeatable 2D/isometric asset-production environment.",
        this);
    root->addWidget(intro);
    root->addWidget(tabs_, 1);

    tabs_->addTab(buildProjectPage(), "Project");
    tabs_->addTab(buildArtPage(), "Art");
    tabs_->addTab(buildMasksPage(), "Masks");
    tabs_->addTab(buildAssemblyPage(), "Assembly");
    tabs_->addTab(buildAnimationPage(), "Animation");
    tabs_->addTab(buildLightingPage(), "Lighting");
    tabs_->addTab(buildCameraPage(), "Camera");
    tabs_->addTab(buildLibraryPage(), "Library");
    tabs_->addTab(buildValidationPage(), "Validation");
    tabs_->addTab(buildExportPage(), "Export");

    refreshProjectSummary();
    refreshAssetPreview();
    validateCurrentAsset();
}

QWidget* ProductionStudioPanel::buildProjectPage() {
    auto* page = new QWidget(tabs_);
    auto* layout = new QVBoxLayout(page);

    layout->addWidget(makeWrappedLabel(
        "A production project freezes the visual world before individual assets are authored. "
        "City Horizon currently inherits the already-homologated CH_GRID_V1 projection instead of inventing a second camera.",
        page));

    auto* form = new QFormLayout();
    project_id_ = new QLineEdit("city_horizon", page);
    project_name_ = new QLineEdit("City Horizon", page);
    form->addRow("Project ID", project_id_);
    form->addRow("Display name", project_name_);
    layout->addLayout(form);

    project_summary_ = makeWrappedLabel({}, page);
    layout->addWidget(project_summary_);

    auto* buttons = new QHBoxLayout();
    auto* load = new QPushButton("Load Profile…", page);
    auto* save = new QPushButton("Save Profile…", page);
    buttons->addWidget(load);
    buttons->addWidget(save);
    buttons->addStretch(1);
    layout->addLayout(buttons);

    connect(project_id_, &QLineEdit::textChanged, this, [this]() { refreshProjectSummary(); });
    connect(project_name_, &QLineEdit::textChanged, this, [this]() { refreshProjectSummary(); });
    connect(load, &QPushButton::clicked, this, [this]() {
        const QString path = QFileDialog::getOpenFileName(this, "Load Studio production profile", {}, "Studio Project (*.json);;All files (*.*)");
        if (path.isEmpty()) return;
        QString error;
        if (!loadProjectProfile(path, &error)) {
            if (validation_report_ != nullptr) validation_report_->setPlainText("PROFILE ERROR\n" + error);
            return;
        }
        refreshProjectSummary();
        if (validation_report_ != nullptr) validation_report_->setPlainText("PROFILE OK\nLoaded: " + path);
    });
    connect(save, &QPushButton::clicked, this, [this]() {
        const QString suggested = project_id_ != nullptr && !project_id_->text().trimmed().isEmpty()
            ? project_id_->text().trimmed() + ".studio.json"
            : QString("city_horizon.studio.json");
        const QString path = QFileDialog::getSaveFileName(this, "Save Studio production profile", suggested, "Studio Project (*.json);;All files (*.*)");
        if (path.isEmpty()) return;
        QString error;
        if (!saveProjectProfile(path, &error)) {
            if (validation_report_ != nullptr) validation_report_->setPlainText("PROFILE ERROR\n" + error);
            return;
        }
        if (validation_report_ != nullptr) validation_report_->setPlainText("PROFILE SAVED\n" + path);
    });

    layout->addStretch(1);
    return page;
}

QWidget* ProductionStudioPanel::buildArtPage() {
    auto* page = new QWidget(tabs_);
    auto* layout = new QVBoxLayout(page);

    layout->addWidget(makeWrappedLabel(
        "Start from existing material instead of a blank canvas: generated image, own render, own drawing, or licensed source. "
        "V1 only inspects the source; it never overwrites it.",
        page));

    auto* choose = new QPushButton("Choose Base Asset…", page);
    layout->addWidget(choose);
    connect(choose, &QPushButton::clicked, this, [this]() { chooseBaseAsset(); });

    asset_preview_ = new QLabel(page);
    asset_preview_->setMinimumSize(240, 240);
    asset_preview_->setAlignment(Qt::AlignCenter);
    asset_preview_->setStyleSheet("QLabel { background: #172025; border: 1px solid #46565d; padding: 8px; }");
    layout->addWidget(asset_preview_, 1);

    asset_metadata_ = makeWrappedLabel({}, page);
    layout->addWidget(asset_metadata_);
    return page;
}

QWidget* ProductionStudioPanel::buildMasksPage() {
    return makeInfoPage(
        "Masks & Materials",
        "Preserve the already-frozen CH_MASK_V1 model. Structural geometry stays untouched while named mask regions control wall, roof, trim, clothing, terrain materials and future overlays.\n\n"
        "Production direction: base RGBA remains immutable; masks and recipes are separate; alpha/anchor/footprint/collision are not changed by recolor. A later workbench phase will add paint/selection tools that author these masks visually without weakening the contract.",
        tabs_);
}

QWidget* ProductionStudioPanel::buildAssemblyPage() {
    return makeInfoPage(
        "2D Modular Assembly",
        "This is the future '2D puzzle' layer: one approved structural base plus compatible pieces such as roof, door, window, awning, sign, chimney and decoration. Pieces will attach through named sockets instead of freehand placement.\n\n"
        "The goal is multiplication without perspective drift: structure first, interchangeable pieces second, mask/material variants third. V1 records the production sector without changing existing building definitions.",
        tabs_);
}

QWidget* ProductionStudioPanel::buildAnimationPage() {
    return makeInfoPage(
        "Animation",
        "Reuse CH_ANIMATED_PROP_V1 and the existing separation between simulation, animation phase and rendering. The production tool will eventually offer typed presets for rotation, oscillation, path, state and atlas-based animation rather than a generic animation editor.\n\n"
        "Characters can later gain directional frame inspection, stride calibration, appearance masks and anchor previews. No existing animation contract is replaced here.",
        tabs_);
}

QWidget* ProductionStudioPanel::buildLightingPage() {
    return makeInfoPage(
        "Lighting & Art Finish",
        "Lighting is a project-level discipline, not something every asset invents. This sector will hold fixed light direction, shadow policy, contrast range and atmosphere presets.\n\n"
        "A later raster-finish stage can simplify gradients, reinforce readable edges, reduce noisy detail and preview the asset at actual in-game scale. The source image must remain recoverable at all times.",
        tabs_);
}

QWidget* ProductionStudioPanel::buildCameraPage() {
    auto* page = new QWidget(tabs_);
    auto* layout = new QVBoxLayout(page);
    layout->addWidget(makeWrappedLabel(
        "Camera is intentionally locked to the canonical game contract for City Horizon. This prevents a visually attractive asset from silently introducing a second projection.",
        page));
    layout->addWidget(makeWrappedLabel(canonicalCameraSummary(), page));
    layout->addStretch(1);
    return page;
}

QWidget* ProductionStudioPanel::buildLibraryPage() {
    auto* page = new QWidget(tabs_);
    auto* layout = new QVBoxLayout(page);
    layout->addWidget(makeWrappedLabel(
        "Index the asset archive without moving, renaming or modifying files. This is the first step toward salvaging old generations into coherent sellable packs.",
        page));

    auto* index = new QPushButton("Index Asset Folder…", page);
    layout->addWidget(index);
    connect(index, &QPushButton::clicked, this, [this]() { indexLibraryFolder(); });

    library_summary_ = makeWrappedLabel("No folder indexed.", page);
    layout->addWidget(library_summary_);

    library_list_ = new QListWidget(page);
    layout->addWidget(library_list_, 1);
    connect(library_list_, &QListWidget::itemDoubleClicked, this, [this](QListWidgetItem* item) {
        if (item == nullptr) return;
        const QString path = item->data(Qt::UserRole).toString();
        if (path.isEmpty()) return;
        current_asset_path_ = path;
        refreshAssetPreview();
        validateCurrentAsset();
        tabs_->setCurrentIndex(1);
    });
    return page;
}

QWidget* ProductionStudioPanel::buildValidationPage() {
    auto* page = new QWidget(tabs_);
    auto* layout = new QVBoxLayout(page);
    layout->addWidget(makeWrappedLabel(
        "Validation V1 is deliberately modest: file readability, image decode, dimensions, alpha availability and canonical project identity. It does not pretend to certify perspective, footprint or artistic quality yet.",
        page));

    auto* run = new QPushButton("Validate Current Asset", page);
    layout->addWidget(run);
    connect(run, &QPushButton::clicked, this, [this]() { validateCurrentAsset(); });

    validation_report_ = new QPlainTextEdit(page);
    validation_report_->setReadOnly(true);
    layout->addWidget(validation_report_, 1);
    return page;
}

QWidget* ProductionStudioPanel::buildExportPage() {
    return makeInfoPage(
        "Export",
        "Production export is intentionally gated in V1. The workbench can save its project profile, but it does not yet rewrite assets, generate packs or mutate canonical game data.\n\n"
        "This protects the existing City Horizon pipeline while we add deterministic stages one by one. Final export will eventually include PNG/RGBA, masks, metadata, thumbnails and CH_CONTENT_PACK_V1-compatible definitions.",
        tabs_);
}

void ProductionStudioPanel::chooseBaseAsset() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "Choose base asset",
        current_asset_path_.isEmpty() ? QString() : QFileInfo(current_asset_path_).absolutePath(),
        "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)");
    if (path.isEmpty()) return;

    current_asset_path_ = path;
    refreshAssetPreview();
    validateCurrentAsset();
}

void ProductionStudioPanel::indexLibraryFolder() {
    const QString path = QFileDialog::getExistingDirectory(this, "Index asset folder", current_library_path_);
    if (path.isEmpty()) return;

    current_library_path_ = path;
    library_list_->clear();

    const QStringList filters = {"*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"};
    QDirIterator iterator(path, filters, QDir::Files | QDir::Readable, QDirIterator::Subdirectories);

    int total = 0;
    int shown = 0;
    while (iterator.hasNext()) {
        const QString filePath = iterator.next();
        ++total;
        if (shown >= kLibraryPreviewLimit) continue;

        const QFileInfo info(filePath);
        auto* item = new QListWidgetItem(QDir(path).relativeFilePath(filePath), library_list_);
        item->setData(Qt::UserRole, filePath);
        item->setToolTip(QString("%1\n%2 bytes").arg(filePath).arg(info.size()));
        ++shown;
    }

    library_summary_->setText(
        QString("Indexed read-only: %1 image file(s). Showing %2.\nSource: %3")
            .arg(total)
            .arg(shown)
            .arg(path));
}

void ProductionStudioPanel::validateCurrentAsset() {
    if (validation_report_ == nullptr) return;

    QStringList lines;
    lines << QString("Contract: %1").arg(kStudioProjectContract);
    lines << QString("Grid: %1 / %2x%3 / 2:1")
                 .arg(ch::contracts::kGridContract)
                 .arg(ch::contracts::kTileWidth)
                 .arg(ch::contracts::kTileHeight);

    if (project_id_ == nullptr || project_id_->text().trimmed().isEmpty()) {
        lines << "ERROR: Project ID is empty.";
    } else {
        lines << "OK: Project identity is present.";
    }

    if (current_asset_path_.isEmpty()) {
        lines << "INFO: No base asset selected yet.";
        validation_report_->setPlainText(lines.join('\n'));
        return;
    }

    const QFileInfo info(current_asset_path_);
    if (!info.exists() || !info.isFile()) {
        lines << "ERROR: Asset file does not exist.";
        validation_report_->setPlainText(lines.join('\n'));
        return;
    }
    if (!info.isReadable()) {
        lines << "ERROR: Asset file is not readable.";
        validation_report_->setPlainText(lines.join('\n'));
        return;
    }

    QImage image(current_asset_path_);
    if (image.isNull()) {
        lines << "ERROR: Qt could not decode the image.";
        validation_report_->setPlainText(lines.join('\n'));
        return;
    }

    lines << QString("OK: Decoded %1 × %2 pixels.").arg(image.width()).arg(image.height());
    lines << QString("%1: Alpha channel %2.")
                 .arg(image.hasAlphaChannel() ? "OK" : "WARNING")
                 .arg(image.hasAlphaChannel() ? "is available" : "is not available");

    const QString suffix = info.suffix().toLower();
    if (suffix == "png") {
        lines << "OK: PNG source is suitable for the RGBA production pipeline.";
    } else {
        lines << QString("WARNING: Source is .%1; final game assets should normally be PNG RGBA.").arg(suffix);
    }

    lines << "INFO: Perspective/scale/anchor/footprint validation is intentionally not claimed by V1.";
    validation_report_->setPlainText(lines.join('\n'));
}

void ProductionStudioPanel::refreshAssetPreview() {
    if (asset_preview_ == nullptr || asset_metadata_ == nullptr) return;

    if (current_asset_path_.isEmpty()) {
        asset_preview_->setText("No base asset selected");
        asset_preview_->setPixmap({});
        asset_metadata_->setText("The source asset remains untouched. Choose an image to inspect it in the production workbench.");
        return;
    }

    QImage image(current_asset_path_);
    const QFileInfo info(current_asset_path_);
    if (image.isNull()) {
        asset_preview_->setPixmap({});
        asset_preview_->setText("Unable to decode image");
        asset_metadata_->setText(current_asset_path_);
        return;
    }

    const QPixmap pixmap = QPixmap::fromImage(image).scaled(
        kPreviewMaxEdge,
        kPreviewMaxEdge,
        Qt::KeepAspectRatio,
        Qt::SmoothTransformation);
    asset_preview_->setText({});
    asset_preview_->setPixmap(pixmap);
    asset_metadata_->setText(
        QString("%1\n%2 × %3 px • %4 • %5 bytes")
            .arg(current_asset_path_)
            .arg(image.width())
            .arg(image.height())
            .arg(image.hasAlphaChannel() ? "alpha" : "opaque")
            .arg(info.size()));
}

void ProductionStudioPanel::refreshProjectSummary() {
    if (project_summary_ == nullptr) return;

    const QString id = project_id_ != nullptr ? project_id_->text().trimmed() : QString();
    const QString name = project_name_ != nullptr ? project_name_->text().trimmed() : QString();
    project_summary_->setText(
        QString("Contract: %1\nProject: %2 (%3)\n\n%4")
            .arg(kStudioProjectContract)
            .arg(name.isEmpty() ? QString("Unnamed") : name)
            .arg(id.isEmpty() ? QString("missing-id") : id)
            .arg(canonicalCameraSummary()));
}

bool ProductionStudioPanel::loadProjectProfile(const QString& path, QString* error) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        if (error != nullptr) *error = "Could not open profile for reading.";
        return false;
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        if (error != nullptr) *error = "Invalid project JSON: " + parseError.errorString();
        return false;
    }

    const QJsonObject root = document.object();
    if (root.value("contract").toString() != kStudioProjectContract) {
        if (error != nullptr) *error = QString("Unsupported project contract. Expected %1.").arg(kStudioProjectContract);
        return false;
    }
    if (root.value("gridContract").toString() != ch::contracts::kGridContract) {
        if (error != nullptr) *error = QString("Grid contract mismatch. City Horizon requires %1.").arg(ch::contracts::kGridContract);
        return false;
    }
    if (root.value("tileWidth").toInt() != ch::contracts::kTileWidth ||
        root.value("tileHeight").toInt() != ch::contracts::kTileHeight) {
        if (error != nullptr) *error = "Tile dimensions do not match the canonical City Horizon grid.";
        return false;
    }

    if (project_id_ != nullptr) project_id_->setText(root.value("projectId").toString());
    if (project_name_ != nullptr) project_name_->setText(root.value("displayName").toString());
    return true;
}

bool ProductionStudioPanel::saveProjectProfile(const QString& path, QString* error) const {
    const QString id = project_id_ != nullptr ? project_id_->text().trimmed() : QString();
    if (id.isEmpty()) {
        if (error != nullptr) *error = "Project ID cannot be empty.";
        return false;
    }

    QJsonObject camera;
    camera.insert("projection", "orthographic_isometric");
    camera.insert("rotationDeg", ch::contracts::kHorizontalWorldRotationDeg);
    camera.insert("inclinationDeg", ch::contracts::kIsometricInclinationDeg);
    camera.insert("locked", true);

    QJsonObject production;
    production.insert("sourceAssetsImmutable", true);
    production.insert("maskContract", "CH_MASK_V1");
    production.insert("contentContract", "CH_CONTENT_PACK_V1");
    production.insert("animatedPropContract", "CH_ANIMATED_PROP_V1");

    QJsonObject root;
    root.insert("contract", kStudioProjectContract);
    root.insert("projectId", id);
    root.insert("displayName", project_name_ != nullptr ? project_name_->text().trimmed() : QString());
    root.insert("gridContract", ch::contracts::kGridContract);
    root.insert("tileWidth", ch::contracts::kTileWidth);
    root.insert("tileHeight", ch::contracts::kTileHeight);
    root.insert("diamondRatio", ch::contracts::kDiamondRatio);
    root.insert("camera", camera);
    root.insert("production", production);

    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (error != nullptr) *error = "Could not open profile for writing.";
        return false;
    }
    file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    if (!file.commit()) {
        if (error != nullptr) *error = "Could not atomically commit project profile.";
        return false;
    }
    return true;
}

} // namespace ch::studio
