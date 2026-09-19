#pragma once

#include "building_asset_catalog.h"

#include <QDialog>
#include <QVector>

class QComboBox;
class QLabel;
class QLineEdit;
class QListWidget;
class QPushButton;

namespace ch::studio {

class BuildingAssetBrowserDialog final : public QDialog {
public:
    explicit BuildingAssetBrowserDialog(QWidget* parent = nullptr);

    void setLibraryRoot(const QString& root);
    QString libraryRoot() const { return library_root_; }
    bool selectedSpec(BuildingComposerSpec* spec) const;
    QString selectedManifestPath() const;

private:
    void chooseRoot();
    void rescan();
    void rebuildFilters();
    void refreshList();
    void refreshSelection();

    QString library_root_;
    QVector<BuildingAssetRecord> records_;
    QVector<int> visible_indices_;

    QLineEdit* search_edit_ = nullptr;
    QComboBox* typology_filter_ = nullptr;
    QComboBox* footprint_filter_ = nullptr;
    QComboBox* floors_filter_ = nullptr;
    QComboBox* status_filter_ = nullptr;
    QListWidget* asset_list_ = nullptr;
    QLabel* thumbnail_ = nullptr;
    QLabel* details_ = nullptr;
    QLabel* root_label_ = nullptr;
    QPushButton* open_button_ = nullptr;
};

} // namespace ch::studio
