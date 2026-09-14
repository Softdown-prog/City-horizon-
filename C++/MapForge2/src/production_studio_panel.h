#pragma once

#include <QDir>
#include <QFile>
#include <QFont>
#include <QPixmap>
#include <QWidget>

class QLabel;
class QLineEdit;
class QListWidget;
class QPlainTextEdit;
class QTabWidget;

namespace ch::studio {

class ProductionStudioPanel final : public QWidget {
public:
    explicit ProductionStudioPanel(QWidget* parent = nullptr);

private:
    QWidget* buildProjectPage();
    QWidget* buildArtPage();
    QWidget* buildMasksPage();
    QWidget* buildAssemblyPage();
    QWidget* buildAnimationPage();
    QWidget* buildLightingPage();
    QWidget* buildCameraPage();
    QWidget* buildLibraryPage();
    QWidget* buildValidationPage();
    QWidget* buildExportPage();

    void chooseBaseAsset();
    void indexLibraryFolder();
    void validateCurrentAsset();
    void refreshAssetPreview();
    void refreshProjectSummary();
    bool loadProjectProfile(const QString& path, QString* error = nullptr);
    bool saveProjectProfile(const QString& path, QString* error = nullptr) const;

    QString current_asset_path_;
    QString current_library_path_;

    QTabWidget* tabs_ = nullptr;
    QLineEdit* project_id_ = nullptr;
    QLineEdit* project_name_ = nullptr;
    QLabel* project_summary_ = nullptr;
    QLabel* asset_preview_ = nullptr;
    QLabel* asset_metadata_ = nullptr;
    QLabel* library_summary_ = nullptr;
    QListWidget* library_list_ = nullptr;
    QPlainTextEdit* validation_report_ = nullptr;
};

} // namespace ch::studio
