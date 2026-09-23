#include <QAction>
#include <QApplication>
#include <QCheckBox>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QDoubleSpinBox>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QImage>
#include <QLabel>
#include <QMainWindow>
#include <QMenuBar>
#include <QPainter>
#include <QPushButton>
#include <QSpinBox>
#include <QStatusBar>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

#include <algorithm>

namespace {

struct LaunchOptions {
    QString base_path;
    QString overlay_path;
    QString direction;
    QString asset_name;
    int base_frames = 1;
    int base_duration_ms = 125;
    int overlay_frames = 1;
    int overlay_duration_ms = 125;
    double anchor_x = 0.5;
    double anchor_y = 0.82;
};

struct AlphaStats {
    qint64 opaque = 0;
    qint64 semi_transparent = 0;
    qint64 transparent = 0;
    qint64 edge_fringe = 0;
    QRect opaque_bounds;
};

AlphaStats analyzeAlpha(const QImage& image, const QRect& source) {
    AlphaStats stats;
    if (image.isNull() || source.isEmpty()) return stats;

    const QRect clipped = source.intersected(image.rect());
    int min_x = clipped.right();
    int min_y = clipped.bottom();
    int max_x = clipped.left() - 1;
    int max_y = clipped.top() - 1;

    const auto alphaAt = [&image](int x, int y) {
        if (x < 0 || y < 0 || x >= image.width() || y >= image.height()) return 0;
        return qAlpha(image.pixel(x, y));
    };

    for (int y = clipped.top(); y <= clipped.bottom(); ++y) {
        for (int x = clipped.left(); x <= clipped.right(); ++x) {
            const int alpha = alphaAt(x, y);
            if (alpha == 0) {
                ++stats.transparent;
                continue;
            }

            min_x = std::min(min_x, x);
            min_y = std::min(min_y, y);
            max_x = std::max(max_x, x);
            max_y = std::max(max_y, y);

            if (alpha == 255) {
                ++stats.opaque;
                continue;
            }

            ++stats.semi_transparent;
            bool touches_transparent = false;
            for (int oy = -1; oy <= 1 && !touches_transparent; ++oy) {
                for (int ox = -1; ox <= 1; ++ox) {
                    if (ox == 0 && oy == 0) continue;
                    if (alphaAt(x + ox, y + oy) == 0) {
                        touches_transparent = true;
                        break;
                    }
                }
            }
            if (touches_transparent) ++stats.edge_fringe;
        }
    }

    if (max_x >= min_x && max_y >= min_y) {
        stats.opaque_bounds = QRect(QPoint(min_x, min_y), QPoint(max_x, max_y));
    }
    return stats;
}

class SpriteCanvas final : public QWidget {
public:
    explicit SpriteCanvas(QWidget* parent = nullptr) : QWidget(parent) {
        setMinimumSize(560, 520);
    }

    void setBaseImage(const QImage& image) { base_ = image.convertToFormat(QImage::Format_ARGB32); update(); }
    void setOverlayImage(const QImage& image) { overlay_ = image.convertToFormat(QImage::Format_ARGB32); update(); }
    void clearOverlay() { overlay_ = QImage(); overlay_frame_index_ = 0; update(); }
    void setBaseFrameCount(int count) {
        base_frame_count_ = std::max(1, count);
        base_frame_index_ = std::min(base_frame_index_, base_frame_count_ - 1);
        update();
    }
    void setOverlayFrameCount(int count) {
        overlay_frame_count_ = std::max(1, count);
        overlay_frame_index_ = std::min(overlay_frame_index_, overlay_frame_count_ - 1);
        update();
    }
    void setBaseFrameIndex(int index) {
        base_frame_index_ = std::clamp(index, 0, std::max(0, base_frame_count_ - 1));
        update();
    }
    void setOverlayFrameIndex(int index) {
        overlay_frame_index_ = std::clamp(index, 0, std::max(0, overlay_frame_count_ - 1));
        update();
    }
    void setAnchor(QPointF anchor) { anchor_ = anchor; update(); }
    void setShowBounds(bool value) { show_bounds_ = value; update(); }
    void setShowCheckerboard(bool value) { show_checkerboard_ = value; update(); }
    void setShowOverlay(bool value) { show_overlay_ = value; update(); }

    const QImage& baseImage() const { return base_; }
    const QImage& overlayImage() const { return overlay_; }
    int baseFrameCount() const { return base_frame_count_; }
    int overlayFrameCount() const { return overlay_frame_count_; }
    int baseFrameIndex() const { return base_frame_index_; }
    int overlayFrameIndex() const { return overlay_frame_index_; }

    QRect baseFrameRect() const {
        return frameRect(base_, base_frame_count_, base_frame_index_);
    }

    QRect overlayFrameRect() const {
        return frameRect(overlay_, overlay_frame_count_, overlay_frame_index_);
    }

protected:
    void paintEvent(QPaintEvent*) override {
        QPainter painter(this);
        painter.setRenderHint(QPainter::SmoothPixmapTransform, false);

        if (show_checkerboard_) {
            constexpr int cell = 16;
            const QColor a(54, 59, 67);
            const QColor b(76, 82, 92);
            for (int y = 0; y < height(); y += cell) {
                for (int x = 0; x < width(); x += cell) {
                    painter.fillRect(QRect(x, y, cell, cell), ((x / cell) + (y / cell)) % 2 == 0 ? a : b);
                }
            }
        } else {
            painter.fillRect(rect(), QColor(41, 45, 52));
        }

        const QRect source = baseFrameRect();
        if (base_.isNull() || source.isEmpty()) {
            painter.setPen(Qt::white);
            painter.drawText(rect(), Qt::AlignCenter, QStringLiteral("Open a PNG to inspect it"));
            return;
        }

        QRectF available = QRectF(rect()).adjusted(28.0, 28.0, -28.0, -28.0);
        QSizeF target_size = QSizeF(source.size());
        target_size.scale(available.size(), Qt::KeepAspectRatio);
        const QRectF target(available.center().x() - target_size.width() / 2.0,
                            available.center().y() - target_size.height() / 2.0,
                            target_size.width(), target_size.height());

        painter.drawImage(target, base_, source);
        if (show_overlay_ && !overlay_.isNull()) {
            const QRect overlay_source = overlayFrameRect();
            if (!overlay_source.isEmpty()) painter.drawImage(target, overlay_, overlay_source);
        }

        if (show_bounds_) {
            const AlphaStats stats = analyzeAlpha(base_, source);
            if (!stats.opaque_bounds.isEmpty()) {
                const double sx = target.width() / source.width();
                const double sy = target.height() / source.height();
                const QRect local = stats.opaque_bounds.translated(-source.topLeft());
                const QRectF bounds(target.left() + local.left() * sx,
                                    target.top() + local.top() * sy,
                                    local.width() * sx,
                                    local.height() * sy);
                QPen pen(QColor(255, 196, 64));
                pen.setWidth(2);
                painter.setPen(pen);
                painter.setBrush(Qt::NoBrush);
                painter.drawRect(bounds);
            }
        }

        const QPointF anchor_point(target.left() + std::clamp(anchor_.x(), 0.0, 1.0) * target.width(),
                                   target.top() + std::clamp(anchor_.y(), 0.0, 1.0) * target.height());
        QPen anchor_pen(QColor(79, 214, 255));
        anchor_pen.setWidth(2);
        painter.setPen(anchor_pen);
        painter.drawLine(QPointF(anchor_point.x() - 10.0, anchor_point.y()), QPointF(anchor_point.x() + 10.0, anchor_point.y()));
        painter.drawLine(QPointF(anchor_point.x(), anchor_point.y() - 10.0), QPointF(anchor_point.x(), anchor_point.y() + 10.0));

        painter.setPen(QColor(230, 234, 239));
        painter.drawText(QRectF(12.0, 8.0, width() - 24.0, 24.0), Qt::AlignLeft | Qt::AlignVCenter,
                         QStringLiteral("Base %1/%2   Overlay %3/%4")
                             .arg(base_frame_index_ + 1).arg(base_frame_count_)
                             .arg(overlay_frame_index_ + 1).arg(overlay_frame_count_));
    }

private:
    static QRect frameRect(const QImage& image, int frame_count, int frame_index) {
        if (image.isNull()) return {};
        frame_count = std::max(1, frame_count);
        const int width = image.width() / frame_count;
        if (width <= 0) return {};
        frame_index = std::clamp(frame_index, 0, frame_count - 1);
        return QRect(frame_index * width, 0, width, image.height()).intersected(image.rect());
    }

    QImage base_;
    QImage overlay_;
    int base_frame_count_ = 1;
    int overlay_frame_count_ = 1;
    int base_frame_index_ = 0;
    int overlay_frame_index_ = 0;
    QPointF anchor_{0.5, 0.82};
    bool show_bounds_ = true;
    bool show_checkerboard_ = true;
    bool show_overlay_ = true;
};

class SpriteWorkshopWindow final : public QMainWindow {
public:
    explicit SpriteWorkshopWindow(const LaunchOptions& options) {
        setWindowTitle(QStringLiteral("City Horizon Sprite Workshop"));
        resize(1160, 760);

        auto* root = new QWidget(this);
        auto* root_layout = new QHBoxLayout(root);
        canvas_ = new SpriteCanvas(root);
        root_layout->addWidget(canvas_, 1);

        auto* panel = new QWidget(root);
        panel->setMinimumWidth(360);
        auto* panel_layout = new QVBoxLayout(panel);

        auto* title = new QLabel(QStringLiteral("Sprite Workshop V1.1"), panel);
        QFont title_font = title->font();
        title_font.setPointSize(title_font.pointSize() + 2);
        title_font.setBold(true);
        title->setFont(title_font);
        panel_layout->addWidget(title);

        context_label_ = new QLabel(panel);
        context_label_->setWordWrap(true);
        panel_layout->addWidget(context_label_);

        auto* open_base = new QPushButton(QStringLiteral("Open base PNG..."), panel);
        auto* open_overlay = new QPushButton(QStringLiteral("Open activity overlay..."), panel);
        auto* clear_overlay = new QPushButton(QStringLiteral("Clear overlay"), panel);
        panel_layout->addWidget(open_base);
        panel_layout->addWidget(open_overlay);
        panel_layout->addWidget(clear_overlay);

        auto* form = new QFormLayout();
        base_frame_count_ = new QSpinBox(panel);
        base_frame_count_->setRange(1, 128);
        base_frame_index_ = new QSpinBox(panel);
        base_frame_index_->setRange(1, 1);
        base_duration_ms_ = new QSpinBox(panel);
        base_duration_ms_->setRange(16, 5000);
        base_duration_ms_->setSuffix(QStringLiteral(" ms"));

        overlay_frame_count_ = new QSpinBox(panel);
        overlay_frame_count_->setRange(1, 128);
        overlay_frame_index_ = new QSpinBox(panel);
        overlay_frame_index_->setRange(1, 1);
        overlay_duration_ms_ = new QSpinBox(panel);
        overlay_duration_ms_->setRange(16, 5000);
        overlay_duration_ms_->setSuffix(QStringLiteral(" ms"));

        anchor_x_ = new QDoubleSpinBox(panel);
        anchor_y_ = new QDoubleSpinBox(panel);
        for (QDoubleSpinBox* spin : {anchor_x_, anchor_y_}) {
            spin->setRange(0.0, 1.0);
            spin->setSingleStep(0.01);
            spin->setDecimals(3);
        }

        form->addRow(QStringLiteral("Base frames"), base_frame_count_);
        form->addRow(QStringLiteral("Base current frame"), base_frame_index_);
        form->addRow(QStringLiteral("Base frame duration"), base_duration_ms_);
        form->addRow(QStringLiteral("Overlay frames"), overlay_frame_count_);
        form->addRow(QStringLiteral("Overlay current frame"), overlay_frame_index_);
        form->addRow(QStringLiteral("Overlay frame duration"), overlay_duration_ms_);
        form->addRow(QStringLiteral("Anchor X"), anchor_x_);
        form->addRow(QStringLiteral("Anchor Y"), anchor_y_);
        panel_layout->addLayout(form);

        play_ = new QPushButton(QStringLiteral("Play animation"), panel);
        play_->setCheckable(true);
        panel_layout->addWidget(play_);

        checkerboard_ = new QCheckBox(QStringLiteral("Checkerboard transparency"), panel);
        bounds_ = new QCheckBox(QStringLiteral("Show opaque bounds"), panel);
        show_overlay_ = new QCheckBox(QStringLiteral("Composite activity overlay"), panel);
        checkerboard_->setChecked(true);
        bounds_->setChecked(true);
        show_overlay_->setChecked(true);
        panel_layout->addWidget(checkerboard_);
        panel_layout->addWidget(bounds_);
        panel_layout->addWidget(show_overlay_);

        diagnostics_ = new QLabel(panel);
        diagnostics_->setWordWrap(true);
        diagnostics_->setTextInteractionFlags(Qt::TextSelectableByMouse);
        diagnostics_->setMinimumHeight(170);
        diagnostics_->setStyleSheet(QStringLiteral("QLabel { background: #20242b; border: 1px solid #3b424d; padding: 8px; }"));
        panel_layout->addWidget(diagnostics_);

        auto* export_frame = new QPushButton(QStringLiteral("Export current composite..."), panel);
        panel_layout->addWidget(export_frame);
        panel_layout->addStretch(1);

        root_layout->addWidget(panel);
        setCentralWidget(root);

        connect(&base_timer_, &QTimer::timeout, this, [this]() {
            const int next = (canvas_->baseFrameIndex() + 1) % canvas_->baseFrameCount();
            canvas_->setBaseFrameIndex(next);
            base_frame_index_->setValue(next + 1);
            refreshDiagnostics();
        });
        connect(&overlay_timer_, &QTimer::timeout, this, [this]() {
            const int next = (canvas_->overlayFrameIndex() + 1) % canvas_->overlayFrameCount();
            canvas_->setOverlayFrameIndex(next);
            overlay_frame_index_->setValue(next + 1);
            refreshDiagnostics();
        });

        connect(open_base, &QPushButton::clicked, this, [this]() { openBaseDialog(); });
        connect(open_overlay, &QPushButton::clicked, this, [this]() { openOverlayDialog(); });
        connect(clear_overlay, &QPushButton::clicked, this, [this]() {
            canvas_->clearOverlay();
            overlay_path_.clear();
            refreshDiagnostics();
        });
        connect(base_frame_count_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setBaseFrameCount(value);
            base_frame_index_->setRange(1, value);
            base_frame_index_->setValue(std::min(base_frame_index_->value(), value));
            syncTimers();
            refreshDiagnostics();
        });
        connect(overlay_frame_count_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setOverlayFrameCount(value);
            overlay_frame_index_->setRange(1, value);
            overlay_frame_index_->setValue(std::min(overlay_frame_index_->value(), value));
            syncTimers();
            refreshDiagnostics();
        });
        connect(base_frame_index_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setBaseFrameIndex(value - 1);
            refreshDiagnostics();
        });
        connect(overlay_frame_index_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setOverlayFrameIndex(value - 1);
            refreshDiagnostics();
        });
        connect(base_duration_ms_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int) { syncTimers(); });
        connect(overlay_duration_ms_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int) { syncTimers(); });
        connect(anchor_x_, qOverload<double>(&QDoubleSpinBox::valueChanged), this, [this](double) { refreshAnchor(); });
        connect(anchor_y_, qOverload<double>(&QDoubleSpinBox::valueChanged), this, [this](double) { refreshAnchor(); });
        connect(checkerboard_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowCheckerboard(value); });
        connect(bounds_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowBounds(value); });
        connect(show_overlay_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowOverlay(value); });
        connect(play_, &QPushButton::toggled, this, [this](bool playing) {
            play_->setText(playing ? QStringLiteral("Pause animation") : QStringLiteral("Play animation"));
            syncTimers();
        });
        connect(export_frame, &QPushButton::clicked, this, [this]() { exportCurrentComposite(); });

        auto* file_menu = menuBar()->addMenu(QStringLiteral("&File"));
        auto* open_base_action = file_menu->addAction(QStringLiteral("Open &base PNG..."));
        auto* open_overlay_action = file_menu->addAction(QStringLiteral("Open &activity overlay..."));
        file_menu->addSeparator();
        auto* export_action = file_menu->addAction(QStringLiteral("&Export current composite..."));
        connect(open_base_action, &QAction::triggered, this, [this]() { openBaseDialog(); });
        connect(open_overlay_action, &QAction::triggered, this, [this]() { openOverlayDialog(); });
        connect(export_action, &QAction::triggered, this, [this]() { exportCurrentComposite(); });

        applyLaunchOptions(options);
    }

private:
    void applyLaunchOptions(const LaunchOptions& options) {
        asset_name_ = options.asset_name;
        direction_ = options.direction;
        context_label_->setText(asset_name_.isEmpty()
            ? (direction_.isEmpty() ? QStringLiteral("Manual inspection") : direction_)
            : QStringLiteral("%1 — %2").arg(asset_name_, direction_.isEmpty() ? QStringLiteral("sprite") : direction_));

        base_frame_count_->setValue(std::max(1, options.base_frames));
        base_duration_ms_->setValue(std::max(16, options.base_duration_ms));
        overlay_frame_count_->setValue(std::max(1, options.overlay_frames));
        overlay_duration_ms_->setValue(std::max(16, options.overlay_duration_ms));
        anchor_x_->setValue(std::clamp(options.anchor_x, 0.0, 1.0));
        anchor_y_->setValue(std::clamp(options.anchor_y, 0.0, 1.0));
        refreshAnchor();

        if (!options.base_path.isEmpty()) loadBase(options.base_path);
        if (!options.overlay_path.isEmpty()) loadOverlay(options.overlay_path);

        if (!asset_name_.isEmpty() || !direction_.isEmpty()) {
            setWindowTitle(QStringLiteral("City Horizon Sprite Workshop — %1%2")
                               .arg(asset_name_.isEmpty() ? QStringLiteral("Asset") : asset_name_)
                               .arg(direction_.isEmpty() ? QString() : QStringLiteral(" — %1").arg(direction_)));
        }
        refreshDiagnostics();
    }

    void openBaseDialog() {
        const QString path = QFileDialog::getOpenFileName(this, QStringLiteral("Open City Horizon PNG"), QString(),
                                                          QStringLiteral("PNG image (*.png);;Images (*.png *.bmp *.webp)"));
        if (!path.isEmpty()) loadBase(path);
    }

    void openOverlayDialog() {
        const QString path = QFileDialog::getOpenFileName(this, QStringLiteral("Open CH_BUILDING_ACTIVITY_OVERLAY_V1 PNG"), QString(),
                                                          QStringLiteral("PNG image (*.png)"));
        if (!path.isEmpty()) loadOverlay(path);
    }

    void loadBase(const QString& path) {
        QImage image(path);
        if (image.isNull()) {
            statusBar()->showMessage(QStringLiteral("Could not open base image."), 5000);
            return;
        }
        base_path_ = path;
        canvas_->setBaseImage(image);
        canvas_->setBaseFrameIndex(0);
        base_frame_index_->setValue(1);
        refreshDiagnostics();
        statusBar()->showMessage(QStringLiteral("Opened %1").arg(QFileInfo(path).fileName()), 5000);
    }

    void loadOverlay(const QString& path) {
        QImage image(path);
        if (image.isNull()) {
            statusBar()->showMessage(QStringLiteral("Could not open overlay."), 5000);
            return;
        }
        overlay_path_ = path;
        canvas_->setOverlayImage(image);
        canvas_->setOverlayFrameIndex(0);
        overlay_frame_index_->setValue(1);
        refreshDiagnostics();
        statusBar()->showMessage(QStringLiteral("Activity overlay loaded."), 5000);
    }

    void refreshAnchor() {
        canvas_->setAnchor(QPointF(anchor_x_->value(), anchor_y_->value()));
    }

    void syncTimers() {
        base_timer_.stop();
        overlay_timer_.stop();
        if (!play_->isChecked()) return;
        if (canvas_->baseFrameCount() > 1) base_timer_.start(base_duration_ms_->value());
        if (canvas_->overlayFrameCount() > 1 && !canvas_->overlayImage().isNull()) {
            overlay_timer_.start(overlay_duration_ms_->value());
        }
    }

    void refreshDiagnostics() {
        const QImage& base = canvas_->baseImage();
        if (base.isNull()) {
            diagnostics_->setText(QStringLiteral("No sprite loaded.\n\nOpen a PNG or launch this tool from CityHorizonAssetEditor."));
            return;
        }

        const int base_frames = canvas_->baseFrameCount();
        const bool base_divisible = base.width() % base_frames == 0;
        const QRect source = canvas_->baseFrameRect();
        const AlphaStats stats = analyzeAlpha(base, source);
        QString text = QStringLiteral("Base: %1 × %2 px\nBase frames: %3%4\nBase frame: %5 × %6 px\nOpaque: %7\nSemi-transparent: %8\nTransparent: %9\nEdge fringe: %10")
                           .arg(base.width()).arg(base.height()).arg(base_frames)
                           .arg(base_divisible ? QString() : QStringLiteral("  [WIDTH NOT DIVISIBLE]"))
                           .arg(source.width()).arg(source.height())
                           .arg(stats.opaque).arg(stats.semi_transparent).arg(stats.transparent).arg(stats.edge_fringe);

        if (!stats.opaque_bounds.isEmpty()) {
            const QRect local = stats.opaque_bounds.translated(-source.topLeft());
            text += QStringLiteral("\nOpaque bounds: x%1 y%2 %3×%4")
                        .arg(local.x()).arg(local.y()).arg(local.width()).arg(local.height());
        }

        const QImage& overlay = canvas_->overlayImage();
        if (!overlay.isNull()) {
            const int overlay_frames = canvas_->overlayFrameCount();
            const bool overlay_divisible = overlay.width() % overlay_frames == 0;
            const QRect overlay_frame = canvas_->overlayFrameRect();
            const bool geometry_match = overlay_frame.size() == source.size();
            text += QStringLiteral("\n\nActivity overlay: %1 × %2 px\nOverlay frames: %3%4\nOverlay frame: %5 × %6 px\nGeometry: %7")
                        .arg(overlay.width()).arg(overlay.height()).arg(overlay_frames)
                        .arg(overlay_divisible ? QString() : QStringLiteral("  [WIDTH NOT DIVISIBLE]"))
                        .arg(overlay_frame.width()).arg(overlay_frame.height())
                        .arg(geometry_match ? QStringLiteral("MATCH") : QStringLiteral("MISMATCH — fix before runtime"));
        }

        text += QStringLiteral("\n\nAnchor: %1, %2").arg(anchor_x_->value(), 0, 'f', 3).arg(anchor_y_->value(), 0, 'f', 3);
        if (stats.edge_fringe > 0) {
            text += QStringLiteral("\n\nFringe is diagnostic only; valid anti-aliasing can also create semi-transparent edge pixels.");
        }
        diagnostics_->setText(text);
    }

    void exportCurrentComposite() {
        const QImage& base = canvas_->baseImage();
        const QRect source = canvas_->baseFrameRect();
        if (base.isNull() || source.isEmpty()) return;

        const QString suggested = base_path_.isEmpty()
            ? QStringLiteral("sprite_composite.png")
            : QFileInfo(base_path_).completeBaseName() + QStringLiteral("_inspection.png");
        const QString path = QFileDialog::getSaveFileName(this, QStringLiteral("Export inspected composite"), suggested,
                                                          QStringLiteral("PNG image (*.png)"));
        if (path.isEmpty()) return;

        QImage output = base.copy(source).convertToFormat(QImage::Format_ARGB32);
        if (show_overlay_->isChecked() && !canvas_->overlayImage().isNull()) {
            const QRect overlay_source = canvas_->overlayFrameRect();
            const QImage overlay_frame = canvas_->overlayImage().copy(overlay_source);
            if (overlay_frame.size() == output.size()) {
                QPainter painter(&output);
                painter.drawImage(QPoint(0, 0), overlay_frame);
            }
        }
        if (!output.save(path, "PNG")) statusBar()->showMessage(QStringLiteral("Export failed."), 5000);
        else statusBar()->showMessage(QStringLiteral("Exported %1").arg(QFileInfo(path).fileName()), 5000);
    }

    SpriteCanvas* canvas_ = nullptr;
    QSpinBox* base_frame_count_ = nullptr;
    QSpinBox* base_frame_index_ = nullptr;
    QSpinBox* base_duration_ms_ = nullptr;
    QSpinBox* overlay_frame_count_ = nullptr;
    QSpinBox* overlay_frame_index_ = nullptr;
    QSpinBox* overlay_duration_ms_ = nullptr;
    QDoubleSpinBox* anchor_x_ = nullptr;
    QDoubleSpinBox* anchor_y_ = nullptr;
    QPushButton* play_ = nullptr;
    QCheckBox* checkerboard_ = nullptr;
    QCheckBox* bounds_ = nullptr;
    QCheckBox* show_overlay_ = nullptr;
    QLabel* context_label_ = nullptr;
    QLabel* diagnostics_ = nullptr;
    QTimer base_timer_;
    QTimer overlay_timer_;
    QString base_path_;
    QString overlay_path_;
    QString direction_;
    QString asset_name_;
};

LaunchOptions parseLaunchOptions(QApplication& app) {
    QCommandLineParser parser;
    parser.setApplicationDescription(QStringLiteral("City Horizon raster QA and activity-overlay workshop"));
    parser.addHelpOption();

    const QCommandLineOption base_option(QStringLiteral("base"), QStringLiteral("Base sprite/spritesheet PNG."), QStringLiteral("path"));
    const QCommandLineOption overlay_option(QStringLiteral("overlay"), QStringLiteral("Activity overlay PNG."), QStringLiteral("path"));
    const QCommandLineOption base_frames_option(QStringLiteral("base-frames"), QStringLiteral("Horizontal base frame count."), QStringLiteral("count"), QStringLiteral("1"));
    const QCommandLineOption base_duration_option(QStringLiteral("base-duration"), QStringLiteral("Base frame duration in ms."), QStringLiteral("ms"), QStringLiteral("125"));
    const QCommandLineOption overlay_frames_option(QStringLiteral("overlay-frames"), QStringLiteral("Horizontal overlay frame count."), QStringLiteral("count"), QStringLiteral("1"));
    const QCommandLineOption overlay_duration_option(QStringLiteral("overlay-duration"), QStringLiteral("Overlay frame duration in ms."), QStringLiteral("ms"), QStringLiteral("125"));
    const QCommandLineOption anchor_x_option(QStringLiteral("anchor-x"), QStringLiteral("Normalized anchor X."), QStringLiteral("value"), QStringLiteral("0.5"));
    const QCommandLineOption anchor_y_option(QStringLiteral("anchor-y"), QStringLiteral("Normalized anchor Y."), QStringLiteral("value"), QStringLiteral("0.82"));
    const QCommandLineOption direction_option(QStringLiteral("direction"), QStringLiteral("Direction label."), QStringLiteral("name"));
    const QCommandLineOption asset_option(QStringLiteral("asset"), QStringLiteral("Asset display name."), QStringLiteral("name"));

    parser.addOptions({base_option, overlay_option, base_frames_option, base_duration_option,
                       overlay_frames_option, overlay_duration_option, anchor_x_option, anchor_y_option,
                       direction_option, asset_option});
    parser.process(app);

    LaunchOptions options;
    options.base_path = parser.value(base_option);
    options.overlay_path = parser.value(overlay_option);
    options.direction = parser.value(direction_option);
    options.asset_name = parser.value(asset_option);
    options.base_frames = std::max(1, parser.value(base_frames_option).toInt());
    options.base_duration_ms = std::max(16, parser.value(base_duration_option).toInt());
    options.overlay_frames = std::max(1, parser.value(overlay_frames_option).toInt());
    options.overlay_duration_ms = std::max(16, parser.value(overlay_duration_option).toInt());
    options.anchor_x = parser.value(anchor_x_option).toDouble();
    options.anchor_y = parser.value(anchor_y_option).toDouble();
    return options;
}

} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("City Horizon Sprite Workshop"));
    const LaunchOptions options = parseLaunchOptions(app);
    SpriteWorkshopWindow window(options);
    window.show();
    return app.exec();
}
