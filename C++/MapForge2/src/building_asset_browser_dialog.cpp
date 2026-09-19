#include "building_asset_browser_dialog.h"

#include <QComboBox>
#include <QDialogButtonBox>
#include <QFileDialog>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPixmap>
#include <QPushButton>
#include <QSet>
#include <QVBoxLayout>

#include <algorithm>

namespace ch::studio {

BuildingAssetBrowserDialog::BuildingAssetBrowserDialog(QWidget* parent)
    : QDialog(parent) {
    setWindowTitle(QStringLiteral("Building Asset Browser"));
    resize(980, 620);

    auto* root_layout = new QVBoxLayout(this);

    auto* root_row = new QHBoxLayout();
    root_label_ = new QLabel(QStringLiteral("No asset library selected."), this);
    root_label_->setTextInteractionFlags(Qt::TextSelectableByMouse);
    auto* choose_button = new QPushButton(QStringLiteral("Choose library folder…"), this);
    auto* rescan_button = new QPushButton(QStringLiteral("Rescan"), this);
    root_row->addWidget(root_label_, 1);
    root_row->addWidget(choose_button);
    root_row->addWidget(rescan_button);
    root_layout->addLayout(root_row);

    auto* filter_row = new QHBoxLayout();
    search_edit_ = new QLineEdit(this);
    search_edit_->setPlaceholderText(QStringLiteral("Search stem or typology…"));
    typology_filter_ = new QComboBox(this);
    footprint_filter_ = new QComboBox(this);
    floors_filter_ = new QComboBox(this);
    status_filter_ = new QComboBox(this);
    status_filter_->addItems({QStringLiteral("All status"), QStringLiteral("Validated"), QStringLiteral("Invalid"), QStringLiteral("Reopenable"), QStringLiteral("Legacy browse-only")});
    filter_row->addWidget(search_edit_, 2);
    filter_row->addWidget(typology_filter_, 1);
    filter_row->addWidget(footprint_filter_, 1);
    filter_row->addWidget(floors_filter_, 1);
    filter_row->addWidget(status_filter_, 1);
    root_layout->addLayout(filter_row);

    auto* body = new QHBoxLayout();
    asset_list_ = new QListWidget(this);
    asset_list_->setMinimumWidth(430);
    asset_list_->setIconSize(QSize(96, 84));
    body->addWidget(asset_list_, 2);

    auto* detail_panel = new QVBoxLayout();
    thumbnail_ = new QLabel(this);
    thumbnail_->setAlignment(Qt::AlignCenter);
    thumbnail_->setMinimumSize(260, 220);
    thumbnail_->setStyleSheet(QStringLiteral("QLabel { background:#172025; border:1px solid #46565d; }"));
    details_ = new QLabel(this);
    details_->setWordWrap(true);
    details_->setTextInteractionFlags(Qt::TextSelectableByMouse);
    detail_panel->addWidget(thumbnail_, 1);
    detail_panel->addWidget(details_);
    body->addLayout(detail_panel, 1);
    root_layout->addLayout(body, 1);

    auto* buttons = new QDialogButtonBox(this);
    open_button_ = buttons->addButton(QStringLiteral("Open for editing"), QDialogButtonBox::AcceptRole);
    auto* close_button = buttons->addButton(QDialogButtonBox::Close);
    open_button_->setEnabled(false);
    root_layout->addWidget(buttons);

    connect(choose_button, &QPushButton::clicked, this, [this]() { chooseRoot(); });
    connect(rescan_button, &QPushButton::clicked, this, [this]() { rescan(); });
    connect(search_edit_, &QLineEdit::textChanged, this, [this]() { refreshList(); });
    connect(typology_filter_, &QComboBox::currentTextChanged, this, [this]() { refreshList(); });
    connect(footprint_filter_, &QComboBox::currentTextChanged, this, [this]() { refreshList(); });
    connect(floors_filter_, &QComboBox::currentTextChanged, this, [this]() { refreshList(); });
    connect(status_filter_, &QComboBox::currentTextChanged, this, [this]() { refreshList(); });
    connect(asset_list_, &QListWidget::currentRowChanged, this, [this](int) { refreshSelection(); });
    connect(asset_list_, &QListWidget::itemDoubleClicked, this, [this](QListWidgetItem*) {
        const int row = asset_list_->currentRow();
        if (row >= 0 && row < visible_indices_.size() && records_[visible_indices_[row]].can_reopen) accept();
    });
    connect(open_button_, &QPushButton::clicked, this, &QDialog::accept);
    connect(close_button, &QPushButton::clicked, this, &QDialog::reject);

    rebuildFilters();
}

void BuildingAssetBrowserDialog::setLibraryRoot(const QString& root) {
    library_root_ = root;
    root_label_->setText(root.isEmpty() ? QStringLiteral("No asset library selected.") : root);
    rescan();
}

void BuildingAssetBrowserDialog::chooseRoot() {
    const QString selected = QFileDialog::getExistingDirectory(this, QStringLiteral("Choose Building Asset Library"), library_root_);
    if (selected.isEmpty()) return;
    setLibraryRoot(selected);
}

void BuildingAssetBrowserDialog::rescan() {
    records_.clear();
    visible_indices_.clear();
    if (!library_root_.isEmpty()) {
        QString error;
        records_ = BuildingAssetCatalog::scan(library_root_, &error);
        if (!error.isEmpty()) details_->setText(error);
    }
    rebuildFilters();
    refreshList();
}

void BuildingAssetBrowserDialog::rebuildFilters() {
    const QString old_typology = typology_filter_ ? typology_filter_->currentText() : QString();
    const QString old_footprint = footprint_filter_ ? footprint_filter_->currentText() : QString();
    const QString old_floors = floors_filter_ ? floors_filter_->currentText() : QString();

    QSet<QString> typologies;
    QSet<QString> footprints;
    QSet<int> floors;
    for (const auto& record : records_) {
        typologies.insert(record.typology_name);
        footprints.insert(QStringLiteral("%1 %2×%3").arg(record.footprint_shape).arg(record.footprint_width).arg(record.footprint_depth));
        floors.insert(record.floor_count);
    }

    typology_filter_->blockSignals(true);
    footprint_filter_->blockSignals(true);
    floors_filter_->blockSignals(true);
    typology_filter_->clear(); footprint_filter_->clear(); floors_filter_->clear();
    typology_filter_->addItem(QStringLiteral("All typologies"));
    footprint_filter_->addItem(QStringLiteral("All footprints"));
    floors_filter_->addItem(QStringLiteral("All floors"));

    QStringList typology_values = typologies.values();
    QStringList footprint_values = footprints.values();
    std::sort(typology_values.begin(), typology_values.end());
    std::sort(footprint_values.begin(), footprint_values.end());
    for (const QString& value : typology_values) typology_filter_->addItem(value);
    for (const QString& value : footprint_values) footprint_filter_->addItem(value);
    QList<int> floor_values = floors.values();
    std::sort(floor_values.begin(), floor_values.end());
    for (int value : floor_values) floors_filter_->addItem(QStringLiteral("%1 floor(s)").arg(value), value);

    const int typology_index = typology_filter_->findText(old_typology);
    const int footprint_index = footprint_filter_->findText(old_footprint);
    const int floors_index = floors_filter_->findText(old_floors);
    if (typology_index >= 0) typology_filter_->setCurrentIndex(typology_index);
    if (footprint_index >= 0) footprint_filter_->setCurrentIndex(footprint_index);
    if (floors_index >= 0) floors_filter_->setCurrentIndex(floors_index);
    typology_filter_->blockSignals(false);
    footprint_filter_->blockSignals(false);
    floors_filter_->blockSignals(false);
}

void BuildingAssetBrowserDialog::refreshList() {
    asset_list_->clear();
    visible_indices_.clear();
    const QString needle = search_edit_->text().trimmed();
    const QString typology = typology_filter_->currentText();
    const QString footprint = footprint_filter_->currentText();
    const QVariant floor_data = floors_filter_->currentData();
    const QString status = status_filter_->currentText();

    for (int i = 0; i < records_.size(); ++i) {
        const BuildingAssetRecord& record = records_[i];
        if (!needle.isEmpty() && !record.stem.contains(needle, Qt::CaseInsensitive) &&
            !record.typology_name.contains(needle, Qt::CaseInsensitive)) continue;
        if (typology != QStringLiteral("All typologies") && record.typology_name != typology) continue;
        const QString record_footprint = QStringLiteral("%1 %2×%3").arg(record.footprint_shape).arg(record.footprint_width).arg(record.footprint_depth);
        if (footprint != QStringLiteral("All footprints") && record_footprint != footprint) continue;
        if (floor_data.isValid() && floor_data.toInt() > 0 && record.floor_count != floor_data.toInt()) continue;
        if (status == QStringLiteral("Validated") && !record.export_ready) continue;
        if (status == QStringLiteral("Invalid") && record.export_ready) continue;
        if (status == QStringLiteral("Reopenable") && !record.can_reopen) continue;
        if (status == QStringLiteral("Legacy browse-only") && record.can_reopen) continue;

        visible_indices_.push_back(i);
        const QString state = record.export_ready ? QStringLiteral("PASS") : QStringLiteral("FAIL");
        auto* item = new QListWidgetItem(QStringLiteral("%1  [%2]\n%3 — %4 %5×%6 — %7F")
            .arg(record.stem, state, record.typology_name, record.footprint_shape)
            .arg(record.footprint_width).arg(record.footprint_depth).arg(record.floor_count));
        if (QFileInfo::exists(record.thumbnail_path)) item->setIcon(QIcon(record.thumbnail_path));
        asset_list_->addItem(item);
    }

    if (asset_list_->count() > 0) asset_list_->setCurrentRow(0);
    else {
        thumbnail_->clear();
        details_->setText(QStringLiteral("No assets match the current filters. Indexed manifests: %1.").arg(records_.size()));
        open_button_->setEnabled(false);
    }
}

void BuildingAssetBrowserDialog::refreshSelection() {
    const int row = asset_list_->currentRow();
    if (row < 0 || row >= visible_indices_.size()) {
        open_button_->setEnabled(false);
        return;
    }
    const BuildingAssetRecord& record = records_[visible_indices_[row]];
    if (QFileInfo::exists(record.thumbnail_path)) {
        QPixmap pixmap(record.thumbnail_path);
        thumbnail_->setPixmap(pixmap.scaled(250, 210, Qt::KeepAspectRatio, Qt::SmoothTransformation));
    } else {
        thumbnail_->setText(QStringLiteral("No thumbnail"));
    }
    details_->setText(QStringLiteral(
        "%1\n\nTypology: %2\nFootprint: %3 %4×%5\nFloors: %6\nExport gate: %7\nLOD gate: %8\nUrban gate: %9\nAuthoring snapshot: %10\n\nManifest:\n%11")
        .arg(record.stem, record.typology_name, record.footprint_shape)
        .arg(record.footprint_width).arg(record.footprint_depth).arg(record.floor_count)
        .arg(record.export_ready ? QStringLiteral("PASS") : QStringLiteral("FAIL"))
        .arg(record.lod_valid ? QStringLiteral("PASS") : QStringLiteral("FAIL / unavailable"))
        .arg(record.urban_valid ? QStringLiteral("PASS") : QStringLiteral("FAIL / unavailable"))
        .arg(record.can_reopen ? QStringLiteral("reopenable") : QStringLiteral("legacy browse-only"))
        .arg(record.manifest_path));
    open_button_->setEnabled(record.can_reopen);
}

bool BuildingAssetBrowserDialog::selectedSpec(BuildingComposerSpec* spec) const {
    if (!spec) return false;
    const int row = asset_list_->currentRow();
    if (row < 0 || row >= visible_indices_.size()) return false;
    const BuildingAssetRecord& record = records_[visible_indices_[row]];
    if (!record.can_reopen) return false;
    *spec = record.authoring_spec;
    return true;
}

QString BuildingAssetBrowserDialog::selectedManifestPath() const {
    const int row = asset_list_->currentRow();
    if (row < 0 || row >= visible_indices_.size()) return {};
    return records_[visible_indices_[row]].manifest_path;
}

} // namespace ch::studio
