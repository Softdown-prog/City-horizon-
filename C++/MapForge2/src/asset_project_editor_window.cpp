#include "asset_project_editor_window.h"

#include <QAction>
#include <QCheckBox>
#include <QComboBox>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QInputDialog>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMenuBar>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPixmap>
#include <QPushButton>
#include <QScrollArea>
#include <QSpinBox>
#include <QSplitter>
#include <QTabWidget>
#include <QVBoxLayout>
#include <QWidget>

namespace ch::studio {
namespace {

constexpr const char* kDefaultStyle = "CH_TYCOON_MINIATURE_V1";

QString nextLayerId(const AssetDocument& document, const QString& prefix) {
    int index = 1;
    for (;;) {
        const QString candidate = QStringLiteral("%1_%2").arg(prefix).arg(index, 3, 10, QLatin1Char('0'));
        if (document.layer(candidate) == nullptr) {
            return candidate;
        }
        ++index;
    }
}

QLineEdit* makePathRow(QWidget* parent,
                       QFormLayout* form,
                       const QString& label,
                       const std::function<void()>& browse_action) {
    auto* row = new QWidget(parent);
    auto* layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);
    auto* edit = new QLineEdit(row);
    auto* browse = new QPushButton(QStringLiteral("Browse..."), row);
    layout->addWidget(edit, 1);
    layout->addWidget(browse);
    QObject::connect(browse, &QPushButton::clicked, row, browse_action);
    form->addRow(label, row);
    return edit;
}

} // namespace

AssetProjectEditorWindow::AssetProjectEditorWindow() {
    document_.newDocument(QStringLiteral("park.asset.new"), QStringLiteral("New Park Asset"), QSize(512, 512));
    document_.setCategory(QStringLiteral("scenery"));
    document_.setStylePreset(QStringLiteral(kDefaultStyle));
    buildUi();
    buildMenus();
    refreshUiFromDocument();
    resize(1380, 820);
}

void AssetProjectEditorWindow::buildUi() {
    auto* splitter = new QSplitter(Qt::Horizontal, this);
    setCentralWidget(splitter);

    // Left: persistent layer/object structure.
    auto* left = new QWidget(splitter);
    auto* left_layout = new QVBoxLayout(left);
    auto* layer_title = new QLabel(QStringLiteral("Asset layers"), left);
    QFont title_font = layer_title->font();
    title_font.setBold(true);
    layer_title->setFont(title_font);
    layer_list_ = new QListWidget(left);
    auto* layer_buttons = new QHBoxLayout();
    auto* add_raster = new QPushButton(QStringLiteral("+ Raster"), left);
    auto* add_reference = new QPushButton(QStringLiteral("+ Reference"), left);
    auto* remove_layer = new QPushButton(QStringLiteral("Remove"), left);
    layer_buttons->addWidget(add_raster);
    layer_buttons->addWidget(add_reference);
    layer_buttons->addWidget(remove_layer);
    left_layout->addWidget(layer_title);
    left_layout->addWidget(layer_list_, 1);
    left_layout->addLayout(layer_buttons);
    left->setMinimumWidth(260);

    connect(add_raster, &QPushButton::clicked, this, [this]() { addRasterLayer(false); });
    connect(add_reference, &QPushButton::clicked, this, [this]() { addRasterLayer(true); });
    connect(remove_layer, &QPushButton::clicked, this, [this]() { removeSelectedLayer(); });
    connect(layer_list_, &QListWidget::currentRowChanged, this, [this](int) { refreshPreview(); });

    // Center: immediate visual proof at gameplay-oriented scale.
    auto* center = new QWidget(splitter);
    auto* center_layout = new QVBoxLayout(center);
    auto* preview_title = new QLabel(QStringLiteral("Canonical asset preview"), center);
    preview_title->setFont(title_font);
    preview_label_ = new QLabel(center);
    preview_label_->setAlignment(Qt::AlignCenter);
    preview_label_->setMinimumSize(480, 480);
    preview_label_->setStyleSheet(QStringLiteral("QLabel { background:#242424; border:1px solid #555; color:#bbb; }"));
    preview_info_label_ = new QLabel(center);
    preview_info_label_->setWordWrap(true);
    center_layout->addWidget(preview_title);
    center_layout->addWidget(preview_label_, 1);
    center_layout->addWidget(preview_info_label_);

    // Right: APE-like property pages.
    auto* right = new QWidget(splitter);
    auto* right_layout = new QVBoxLayout(right);
    auto* tabs = new QTabWidget(right);
    right_layout->addWidget(tabs, 1);
    right->setMinimumWidth(430);

    auto* general_tab = new QWidget(tabs);
    auto* general_form = new QFormLayout(general_tab);
    asset_id_edit_ = new QLineEdit(general_tab);
    asset_id_edit_->setReadOnly(true);
    display_name_edit_ = new QLineEdit(general_tab);
    category_combo_ = new QComboBox(general_tab);
    category_combo_->setEditable(true);
    category_combo_->addItems({QStringLiteral("building"), QStringLiteral("attraction"), QStringLiteral("service"),
                               QStringLiteral("scenery"), QStringLiteral("tree"), QStringLiteral("prop"),
                               QStringLiteral("path"), QStringLiteral("character"), QStringLiteral("ui")});
    canvas_width_spin_ = new QSpinBox(general_tab);
    canvas_height_spin_ = new QSpinBox(general_tab);
    canvas_width_spin_->setRange(32, 4096);
    canvas_height_spin_->setRange(32, 4096);
    camera_contract_edit_ = new QLineEdit(general_tab);
    style_preset_edit_ = new QLineEdit(general_tab);
    general_form->addRow(QStringLiteral("Asset ID"), asset_id_edit_);
    general_form->addRow(QStringLiteral("Display name"), display_name_edit_);
    general_form->addRow(QStringLiteral("Category"), category_combo_);
    general_form->addRow(QStringLiteral("Canvas width"), canvas_width_spin_);
    general_form->addRow(QStringLiteral("Canvas height"), canvas_height_spin_);
    general_form->addRow(QStringLiteral("Camera contract"), camera_contract_edit_);
    general_form->addRow(QStringLiteral("Style preset"), style_preset_edit_);
    auto* apply_general = new QPushButton(QStringLiteral("Apply general properties"), general_tab);
    general_form->addRow(apply_general);
    tabs->addTab(general_tab, QStringLiteral("General"));
    connect(apply_general, &QPushButton::clicked, this, [this]() { applyGeneralFields(); });

    auto* gameplay_tab = new QWidget(tabs);
    auto* gameplay_form = new QFormLayout(gameplay_tab);
    cost_spin_ = new QSpinBox(gameplay_tab);
    upkeep_spin_ = new QSpinBox(gameplay_tab);
    income_spin_ = new QSpinBox(gameplay_tab);
    footprint_width_spin_ = new QSpinBox(gameplay_tab);
    footprint_depth_spin_ = new QSpinBox(gameplay_tab);
    for (QSpinBox* spin : {cost_spin_, upkeep_spin_, income_spin_}) {
        spin->setRange(-1000000, 1000000);
    }
    footprint_width_spin_->setRange(1, 64);
    footprint_depth_spin_->setRange(1, 64);
    requires_path_check_ = new QCheckBox(QStringLiteral("Object requires a path connection"), gameplay_tab);
    tags_edit_ = new QLineEdit(gameplay_tab);
    tags_edit_->setPlaceholderText(QStringLiteral("food, family, decorative ..."));
    gameplay_form->addRow(QStringLiteral("Build cost"), cost_spin_);
    gameplay_form->addRow(QStringLiteral("Upkeep / cycle"), upkeep_spin_);
    gameplay_form->addRow(QStringLiteral("Income / cycle"), income_spin_);
    gameplay_form->addRow(QStringLiteral("Footprint width (tiles)"), footprint_width_spin_);
    gameplay_form->addRow(QStringLiteral("Footprint depth (tiles)"), footprint_depth_spin_);
    gameplay_form->addRow(requires_path_check_);
    gameplay_form->addRow(QStringLiteral("Tags"), tags_edit_);
    auto* apply_gameplay = new QPushButton(QStringLiteral("Apply gameplay properties"), gameplay_tab);
    gameplay_form->addRow(apply_gameplay);
    tabs->addTab(gameplay_tab, QStringLiteral("Gameplay"));
    connect(apply_gameplay, &QPushButton::clicked, this, [this]() { applyGameplayFields(); });

    auto* visuals_tab = new QWidget(tabs);
    auto* visuals_form = new QFormLayout(visuals_tab);
    south_path_edit_ = makePathRow(visuals_tab, visuals_form, QStringLiteral("South PNG"), [this]() {
        const QString path = chooseImageFile(QStringLiteral("Choose SOUTH sprite"));
        if (!path.isEmpty()) applyDirectionPath(QStringLiteral("south"), path);
    });
    east_path_edit_ = makePathRow(visuals_tab, visuals_form, QStringLiteral("East PNG"), [this]() {
        const QString path = chooseImageFile(QStringLiteral("Choose EAST sprite"));
        if (!path.isEmpty()) applyDirectionPath(QStringLiteral("east"), path);
    });
    west_path_edit_ = makePathRow(visuals_tab, visuals_form, QStringLiteral("West PNG"), [this]() {
        const QString path = chooseImageFile(QStringLiteral("Choose WEST sprite"));
        if (!path.isEmpty()) applyDirectionPath(QStringLiteral("west"), path);
    });
    north_path_edit_ = makePathRow(visuals_tab, visuals_form, QStringLiteral("North PNG"), [this]() {
        const QString path = chooseImageFile(QStringLiteral("Choose NORTH sprite"));
        if (!path.isEmpty()) applyDirectionPath(QStringLiteral("north"), path);
    });
    auto* refresh_preview = new QPushButton(QStringLiteral("Refresh preview"), visuals_tab);
    visuals_form->addRow(refresh_preview);
    tabs->addTab(visuals_tab, QStringLiteral("4 Directions"));
    connect(refresh_preview, &QPushButton::clicked, this, [this]() { refreshPreview(); });

    auto* metadata_tab = new QWidget(tabs);
    auto* metadata_layout = new QVBoxLayout(metadata_tab);
    metadata_edit_ = new QPlainTextEdit(metadata_tab);
    metadata_edit_->setPlaceholderText(QStringLiteral("Advanced object metadata as JSON"));
    auto* apply_metadata = new QPushButton(QStringLiteral("Apply metadata JSON"), metadata_tab);
    metadata_layout->addWidget(metadata_edit_, 1);
    metadata_layout->addWidget(apply_metadata);
    tabs->addTab(metadata_tab, QStringLiteral("Advanced"));
    connect(apply_metadata, &QPushButton::clicked, this, [this]() { applyRawMetadata(); });

    status_label_ = new QLabel(right);
    status_label_->setWordWrap(true);
    right_layout->addWidget(status_label_);

    splitter->addWidget(left);
    splitter->addWidget(center);
    splitter->addWidget(right);
    splitter->setStretchFactor(0, 0);
    splitter->setStretchFactor(1, 1);
    splitter->setStretchFactor(2, 0);
}

void AssetProjectEditorWindow::buildMenus() {
    auto* file_menu = menuBar()->addMenu(QStringLiteral("&File"));
    auto* new_action = file_menu->addAction(QStringLiteral("&New asset..."));
    auto* open_action = file_menu->addAction(QStringLiteral("&Open .chasset..."));
    file_menu->addSeparator();
    auto* save_action = file_menu->addAction(QStringLiteral("&Save"));
    auto* save_as_action = file_menu->addAction(QStringLiteral("Save &As..."));
    file_menu->addSeparator();
    auto* validate_action = file_menu->addAction(QStringLiteral("&Validate document"));

    auto* edit_menu = menuBar()->addMenu(QStringLiteral("&Edit"));
    auto* undo_action = edit_menu->addAction(QStringLiteral("&Undo"));
    auto* redo_action = edit_menu->addAction(QStringLiteral("&Redo"));

    connect(new_action, &QAction::triggered, this, [this]() { newAsset(); });
    connect(open_action, &QAction::triggered, this, [this]() { openAsset(); });
    connect(save_action, &QAction::triggered, this, [this]() { saveAsset(false); });
    connect(save_as_action, &QAction::triggered, this, [this]() { saveAsset(true); });
    connect(validate_action, &QAction::triggered, this, [this]() {
        QString reason;
        if (document_.validate(&reason)) {
            QMessageBox::information(this, QStringLiteral("Validation"), QStringLiteral("CH_ASSET_DOCUMENT_V1: PASS"));
        } else {
            QMessageBox::warning(this, QStringLiteral("Validation failed"), reason);
        }
    });
    connect(undo_action, &QAction::triggered, this, [this]() { undo(); });
    connect(redo_action, &QAction::triggered, this, [this]() { redo(); });
}

void AssetProjectEditorWindow::newAsset() {
    bool ok = false;
    const QString id = QInputDialog::getText(this, QStringLiteral("New asset"),
                                             QStringLiteral("Persistent asset ID:"), QLineEdit::Normal,
                                             QStringLiteral("park.scenery.new_asset"), &ok).trimmed();
    if (!ok || id.isEmpty()) return;
    const QString display = QInputDialog::getText(this, QStringLiteral("New asset"),
                                                  QStringLiteral("Display name:"), QLineEdit::Normal,
                                                  QStringLiteral("New Park Asset"), &ok).trimmed();
    if (!ok || display.isEmpty()) return;

    document_.newDocument(id, display, QSize(512, 512));
    document_.setCategory(QStringLiteral("scenery"));
    document_.setStylePreset(QStringLiteral(kDefaultStyle));
    history_.clear();
    current_path_.clear();
    refreshUiFromDocument();
    setStatus(QStringLiteral("New asset created. Save it as .chasset when ready."));
}

void AssetProjectEditorWindow::openAsset() {
    const QString path = QFileDialog::getOpenFileName(this, QStringLiteral("Open City Horizon asset"), QString(),
                                                      QStringLiteral("City Horizon Asset (*.chasset);;All files (*.*)"));
    if (path.isEmpty()) return;
    AssetDocument loaded;
    QString reason;
    if (!AssetDocument::load(path, &loaded, &reason)) {
        QMessageBox::critical(this, QStringLiteral("Open failed"), reason);
        return;
    }
    document_ = loaded;
    history_.clear();
    current_path_ = path;
    refreshUiFromDocument();
    setStatus(QStringLiteral("Opened %1").arg(QFileInfo(path).fileName()));
}

bool AssetProjectEditorWindow::saveAsset(bool save_as) {
    QString path = current_path_;
    if (save_as || path.isEmpty()) {
        path = QFileDialog::getSaveFileName(this, QStringLiteral("Save City Horizon asset"),
                                            path.isEmpty() ? document_.assetId() + QStringLiteral(".chasset") : path,
                                            QStringLiteral("City Horizon Asset (*.chasset)"));
        if (path.isEmpty()) return false;
    }
    if (!path.endsWith(QStringLiteral(".chasset"), Qt::CaseInsensitive)) {
        path += QStringLiteral(".chasset");
    }
    QString reason;
    if (!document_.save(path, &reason)) {
        QMessageBox::critical(this, QStringLiteral("Save failed"), reason);
        return false;
    }
    current_path_ = path;
    updateWindowTitle();
    setStatus(QStringLiteral("Saved %1").arg(QFileInfo(path).fileName()));
    return true;
}

void AssetProjectEditorWindow::refreshUiFromDocument() {
    refreshing_ = true;
    asset_id_edit_->setText(document_.assetId());
    display_name_edit_->setText(document_.displayName());
    category_combo_->setCurrentText(document_.category());
    canvas_width_spin_->setValue(document_.canvasSize().width());
    canvas_height_spin_->setValue(document_.canvasSize().height());
    camera_contract_edit_->setText(document_.cameraContract());
    style_preset_edit_->setText(document_.stylePreset());

    const QJsonObject metadata = document_.metadata();
    const QJsonObject gameplay = metadata.value(QStringLiteral("gameplay")).toObject();
    cost_spin_->setValue(gameplay.value(QStringLiteral("cost")).toInt(0));
    upkeep_spin_->setValue(gameplay.value(QStringLiteral("upkeep")).toInt(0));
    income_spin_->setValue(gameplay.value(QStringLiteral("income")).toInt(0));
    footprint_width_spin_->setValue(gameplay.value(QStringLiteral("footprintWidthTiles")).toInt(1));
    footprint_depth_spin_->setValue(gameplay.value(QStringLiteral("footprintDepthTiles")).toInt(1));
    requires_path_check_->setChecked(gameplay.value(QStringLiteral("requiresPath")).toBool(false));
    tags_edit_->setText(gameplay.value(QStringLiteral("tags")).toString());

    south_path_edit_->setText(directionPath(QStringLiteral("south")));
    east_path_edit_->setText(directionPath(QStringLiteral("east")));
    west_path_edit_->setText(directionPath(QStringLiteral("west")));
    north_path_edit_->setText(directionPath(QStringLiteral("north")));
    refreshing_ = false;

    refreshLayerList();
    refreshRawMetadata();
    refreshPreview();
    updateWindowTitle();
}

void AssetProjectEditorWindow::refreshLayerList() {
    layer_list_->clear();
    for (const AssetLayer& layer : document_.layers()) {
        layer_list_->addItem(QStringLiteral("%1  [%2]").arg(layer.name, assetLayerTypeId(layer.type)));
    }
}

void AssetProjectEditorWindow::refreshPreview() {
    QString candidate;
    const int row = layer_list_->currentRow();
    if (row >= 0 && row < document_.layers().size()) {
        candidate = document_.layers().at(row).source_path;
    }
    if (candidate.isEmpty()) {
        for (const QString& dir : {QStringLiteral("south"), QStringLiteral("east"), QStringLiteral("west"), QStringLiteral("north")}) {
            candidate = directionPath(dir);
            if (!candidate.isEmpty()) break;
        }
    }

    const QString resolved = resolvedPath(candidate);
    QPixmap pixmap;
    if (!resolved.isEmpty()) pixmap.load(resolved);
    if (pixmap.isNull()) {
        preview_label_->setPixmap(QPixmap());
        preview_label_->setText(QStringLiteral("No preview image yet\n\nAssign a SOUTH/EAST/WEST/NORTH PNG\nor add a raster/reference layer."));
        preview_info_label_->setText(QStringLiteral("The editor stores deterministic asset data even before final art exists."));
        return;
    }

    preview_label_->setText(QString());
    preview_label_->setPixmap(pixmap.scaled(preview_label_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation));
    preview_info_label_->setText(QStringLiteral("%1 × %2 px — %3").arg(pixmap.width()).arg(pixmap.height()).arg(candidate));
}

void AssetProjectEditorWindow::refreshRawMetadata() {
    metadata_edit_->setPlainText(QString::fromUtf8(QJsonDocument(document_.metadata()).toJson(QJsonDocument::Indented)));
}

void AssetProjectEditorWindow::applyGeneralFields() {
    if (refreshing_) return;
    AssetEditTransaction transaction(document_, history_, QStringLiteral("Edit general asset properties"));
    document_.setDisplayName(display_name_edit_->text().trimmed());
    document_.setCategory(category_combo_->currentText().trimmed());
    document_.setCanvasSize(QSize(canvas_width_spin_->value(), canvas_height_spin_->value()));
    document_.setCameraContract(camera_contract_edit_->text().trimmed());
    document_.setStylePreset(style_preset_edit_->text().trimmed());
    if (!transaction.commit()) {
        setStatus(QStringLiteral("No general property changes to commit."));
    } else {
        setStatus(QStringLiteral("General properties updated."));
    }
    refreshUiFromDocument();
}

void AssetProjectEditorWindow::applyGameplayFields() {
    AssetEditTransaction transaction(document_, history_, QStringLiteral("Edit gameplay properties"));
    QJsonObject metadata = document_.metadata();
    QJsonObject gameplay = metadata.value(QStringLiteral("gameplay")).toObject();
    gameplay.insert(QStringLiteral("cost"), cost_spin_->value());
    gameplay.insert(QStringLiteral("upkeep"), upkeep_spin_->value());
    gameplay.insert(QStringLiteral("income"), income_spin_->value());
    gameplay.insert(QStringLiteral("footprintWidthTiles"), footprint_width_spin_->value());
    gameplay.insert(QStringLiteral("footprintDepthTiles"), footprint_depth_spin_->value());
    gameplay.insert(QStringLiteral("requiresPath"), requires_path_check_->isChecked());
    gameplay.insert(QStringLiteral("tags"), tags_edit_->text().trimmed());
    metadata.insert(QStringLiteral("gameplay"), gameplay);
    document_.setMetadata(metadata);
    transaction.commit();
    refreshRawMetadata();
    setStatus(QStringLiteral("Gameplay properties updated."));
}

void AssetProjectEditorWindow::applyDirectionPath(const QString& direction, const QString& path) {
    AssetEditTransaction transaction(document_, history_, QStringLiteral("Assign %1 sprite").arg(direction.toUpper()));
    QJsonObject metadata = document_.metadata();
    QJsonObject directions = metadata.value(QStringLiteral("directions")).toObject();
    directions.insert(direction, storedPathForFile(path));
    metadata.insert(QStringLiteral("directions"), directions);
    document_.setMetadata(metadata);
    transaction.commit();
    refreshUiFromDocument();
    setStatus(QStringLiteral("%1 sprite assigned.").arg(direction.toUpper()));
}

void AssetProjectEditorWindow::applyRawMetadata() {
    QJsonParseError error;
    const QJsonDocument parsed = QJsonDocument::fromJson(metadata_edit_->toPlainText().toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !parsed.isObject()) {
        QMessageBox::warning(this, QStringLiteral("Invalid metadata JSON"), error.errorString());
        return;
    }
    AssetEditTransaction transaction(document_, history_, QStringLiteral("Edit advanced metadata"));
    document_.setMetadata(parsed.object());
    transaction.commit();
    refreshUiFromDocument();
    setStatus(QStringLiteral("Advanced metadata updated."));
}

void AssetProjectEditorWindow::addRasterLayer(bool reference_layer) {
    const QString path = chooseImageFile(reference_layer ? QStringLiteral("Choose reference image") : QStringLiteral("Choose raster image"));
    if (path.isEmpty()) return;

    AssetLayer layer;
    layer.id = nextLayerId(document_, reference_layer ? QStringLiteral("reference") : QStringLiteral("raster"));
    layer.name = QFileInfo(path).completeBaseName();
    layer.type = reference_layer ? AssetLayerType::Reference : AssetLayerType::Raster;
    layer.source_path = storedPathForFile(path);

    QString reason;
    AssetEditTransaction transaction(document_, history_, reference_layer ? QStringLiteral("Add reference layer") : QStringLiteral("Add raster layer"));
    if (!document_.addLayer(layer, -1, &reason)) {
        transaction.rollback();
        QMessageBox::warning(this, QStringLiteral("Layer rejected"), reason);
        return;
    }
    transaction.commit();
    refreshUiFromDocument();
    layer_list_->setCurrentRow(document_.layers().size() - 1);
    setStatus(QStringLiteral("Layer added: %1").arg(layer.name));
}

void AssetProjectEditorWindow::removeSelectedLayer() {
    const int row = layer_list_->currentRow();
    if (row < 0 || row >= document_.layers().size()) return;
    const QString id = document_.layers().at(row).id;
    QString reason;
    AssetEditTransaction transaction(document_, history_, QStringLiteral("Remove asset layer"));
    if (!document_.removeLayer(id, &reason)) {
        transaction.rollback();
        QMessageBox::warning(this, QStringLiteral("Remove failed"), reason);
        return;
    }
    transaction.commit();
    refreshUiFromDocument();
    setStatus(QStringLiteral("Layer removed."));
}

void AssetProjectEditorWindow::undo() {
    QString label;
    if (history_.undo(document_, &label)) {
        refreshUiFromDocument();
        setStatus(QStringLiteral("Undo: %1").arg(label));
    } else {
        setStatus(QStringLiteral("Nothing to undo."));
    }
}

void AssetProjectEditorWindow::redo() {
    QString label;
    if (history_.redo(document_, &label)) {
        refreshUiFromDocument();
        setStatus(QStringLiteral("Redo: %1").arg(label));
    } else {
        setStatus(QStringLiteral("Nothing to redo."));
    }
}

QString AssetProjectEditorWindow::chooseImageFile(const QString& title) const {
    return QFileDialog::getOpenFileName(const_cast<AssetProjectEditorWindow*>(this), title, QString(),
                                        QStringLiteral("Images (*.png *.jpg *.jpeg *.webp);;All files (*.*)"));
}

QString AssetProjectEditorWindow::storedPathForFile(const QString& absolute_path) const {
    if (absolute_path.isEmpty()) return {};
    if (current_path_.isEmpty()) return QDir::cleanPath(absolute_path);
    const QDir doc_dir(QFileInfo(current_path_).absolutePath());
    return doc_dir.relativeFilePath(absolute_path);
}

QString AssetProjectEditorWindow::resolvedPath(const QString& stored_path) const {
    if (stored_path.isEmpty()) return {};
    const QFileInfo info(stored_path);
    if (info.isAbsolute()) return QDir::cleanPath(stored_path);
    if (current_path_.isEmpty()) return QDir::cleanPath(stored_path);
    return QDir(QFileInfo(current_path_).absolutePath()).absoluteFilePath(stored_path);
}

QString AssetProjectEditorWindow::directionPath(const QString& direction) const {
    return document_.metadata().value(QStringLiteral("directions")).toObject().value(direction).toString();
}

void AssetProjectEditorWindow::setStatus(const QString& text) {
    status_label_->setText(text);
}

void AssetProjectEditorWindow::updateWindowTitle() {
    const QString file = current_path_.isEmpty() ? QStringLiteral("unsaved") : QFileInfo(current_path_).fileName();
    setWindowTitle(QStringLiteral("City Horizon Asset Editor — %1 — %2").arg(document_.displayName(), file));
}

} // namespace ch::studio
