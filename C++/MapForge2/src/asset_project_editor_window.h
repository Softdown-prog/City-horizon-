#pragma once

#include "asset_document.h"
#include "asset_history.h"

#include <QFont>
#include <QMainWindow>

#include <functional>

class QCheckBox;
class QComboBox;
class QLabel;
class QLineEdit;
class QListWidget;
class QPlainTextEdit;
class QSpinBox;
class QTabWidget;

namespace ch::studio {

class AssetProjectEditorWindow final : public QMainWindow {
public:
    AssetProjectEditorWindow();

private:
    void buildUi();
    void buildMenus();
    void newAsset();
    void openAsset();
    bool saveAsset(bool save_as);
    void refreshUiFromDocument();
    void refreshLayerList();
    void refreshPreview();
    void refreshRawMetadata();
    void applyGeneralFields();
    void applyGameplayFields();
    void applyDirectionPath(const QString& direction, const QString& path);
    void applyRawMetadata();
    void addRasterLayer(bool reference_layer);
    void removeSelectedLayer();
    void undo();
    void redo();
    QString chooseImageFile(const QString& title) const;
    QString storedPathForFile(const QString& absolute_path) const;
    QString resolvedPath(const QString& stored_path) const;
    QString directionPath(const QString& direction) const;
    void setStatus(const QString& text);
    void updateWindowTitle();

    AssetDocument document_;
    AssetHistory history_;
    QString current_path_;
    bool refreshing_ = false;

    QLineEdit* asset_id_edit_ = nullptr;
    QLineEdit* display_name_edit_ = nullptr;
    QComboBox* category_combo_ = nullptr;
    QSpinBox* canvas_width_spin_ = nullptr;
    QSpinBox* canvas_height_spin_ = nullptr;
    QLineEdit* camera_contract_edit_ = nullptr;
    QLineEdit* style_preset_edit_ = nullptr;

    QSpinBox* cost_spin_ = nullptr;
    QSpinBox* upkeep_spin_ = nullptr;
    QSpinBox* income_spin_ = nullptr;
    QSpinBox* footprint_width_spin_ = nullptr;
    QSpinBox* footprint_depth_spin_ = nullptr;
    QCheckBox* requires_path_check_ = nullptr;
    QLineEdit* tags_edit_ = nullptr;

    QLineEdit* south_path_edit_ = nullptr;
    QLineEdit* east_path_edit_ = nullptr;
    QLineEdit* west_path_edit_ = nullptr;
    QLineEdit* north_path_edit_ = nullptr;

    QListWidget* layer_list_ = nullptr;
    QLabel* preview_label_ = nullptr;
    QLabel* preview_info_label_ = nullptr;
    QPlainTextEdit* metadata_edit_ = nullptr;
    QLabel* status_label_ = nullptr;
};

} // namespace ch::studio
