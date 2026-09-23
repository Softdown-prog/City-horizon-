#include <QApplication>
#include <QCheckBox>
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
    void clearOverlay() { overlay_ = QImage(); update(); }
    void setFrameCount(int count) { frame_count_ = std::max(1, count); frame_index_ %= frame_count_; update(); }
    void setFrameIndex(int index) { frame_index_ = std::clamp(index, 0, std::max(0, frame_count_ - 1)); update(); }
    void setAnchor(QPointF anchor) { anchor_ = anchor; update(); }
    void setShowBounds(bool value) { show_bounds_ = value; update(); }
    void setShowCheckerboard(bool value) { show_checkerboard_ = value; update(); }
    void setShowOverlay(bool value) { show_overlay_ = value; update(); }

    const QImage& baseImage() const { return base_; }
    const QImage& overlayImage() const { return overlay_; }
    int frameCount() const { return frame_count_; }
    int frameIndex() const { return frame_index_; }

    QRect baseFrameRect() const {
        if (base_.isNull()) return {};
        const int width = base_.width() / std::max(1, frame_count_);
        if (width <= 0) return {};
        return QRect(frame_index_ * width, 0, width, base_.height()).intersected(base_.rect());
    }

    QRect overlayFrameRect() const {
        if (overlay_.isNull()) return {};
        if (overlay_.width() % std::max(1, frame_count_) != 0) return overlay_.rect();
        const int width = overlay_.width() / std::max(1, frame_count_);
        return QRect(frame_index_ * width, 0, width, overlay_.height()).intersected(overlay_.rect());
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
                QRect local = stats.opaque_bounds.translated(-source.topLeft());
                QRectF bounds(target.left() + local.left() * sx,
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
                         QStringLiteral("Frame %1 / %2").arg(frame_index_ + 1).arg(frame_count_));
    }

private:
    QImage base_;
    QImage overlay_;
    int frame_count_ = 1;
    int frame_index_ = 0;
    QPointF anchor_{0.5, 0.82};
    bool show_bounds_ = true;
    bool show_checkerboard_ = true;
    bool show_overlay_ = true;
};

class SpriteWorkshopWindow final : public QMainWindow {
public:
    SpriteWorkshopWindow() {
        setWindowTitle(QStringLiteral("City Horizon Sprite Workshop"));
        resize(1120, 720);

        auto* root = new QWidget(this);
        auto* root_layout = new QHBoxLayout(root);
        canvas_ = new SpriteCanvas(root);
        root_layout->addWidget(canvas_, 1);

        auto* panel = new QWidget(root);
        panel->setMinimumWidth(330);
        auto* panel_layout = new QVBoxLayout(panel);

        auto* title = new QLabel(QStringLiteral("Sprite Workshop V1"), panel);
        QFont title_font = title->font();
        title_font.setPointSize(title_font.pointSize() + 2);
        title_font.setBold(true);
        title->setFont(title_font);
        panel_layout->addWidget(title);

        auto* open_base = new QPushButton(QStringLiteral("Open base PNG..."), panel);
        auto* open_overlay = new QPushButton(QStringLiteral("Open activity overlay..."), panel);
        auto* clear_overlay = new QPushButton(QStringLiteral("Clear overlay"), panel);
        panel_layout->addWidget(open_base);
        panel_layout->addWidget(open_overlay);
        panel_layout->addWidget(clear_overlay);

        auto* form = new QFormLayout();
        frame_count_ = new QSpinBox(panel);
        frame_count_->setRange(1, 128);
        frame_count_->setValue(1);
        frame_index_ = new QSpinBox(panel);
        frame_index_->setRange(1, 1);
        frame_index_->setValue(1);
        duration_ms_ = new QSpinBox(panel);
        duration_ms_->setRange(16, 5000);
        duration_ms_->setValue(125);
        duration_ms_->setSuffix(QStringLiteral(" ms"));
        anchor_x_ = new QDoubleSpinBox(panel);
        anchor_y_ = new QDoubleSpinBox(panel);
        for (QDoubleSpinBox* spin : {anchor_x_, anchor_y_}) {
            spin->setRange(0.0, 1.0);
            spin->setSingleStep(0.01);
            spin->setDecimals(3);
        }
        anchor_x_->setValue(0.5);
        anchor_y_->setValue(0.82);
        form->addRow(QStringLiteral("Frames (horizontal)"), frame_count_);
        form->addRow(QStringLiteral("Current frame"), frame_index_);
        form->addRow(QStringLiteral("Frame duration"), duration_ms_);
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
        diagnostics_->setMinimumHeight(150);
        diagnostics_->setStyleSheet(QStringLiteral("QLabel { background: #20242b; border: 1px solid #3b424d; padding: 8px; }"));
        panel_layout->addWidget(diagnostics_);

        auto* export_frame = new QPushButton(QStringLiteral("Export current frame..."), panel);
        panel_layout->addWidget(export_frame);
        panel_layout->addStretch(1);

        root_layout->addWidget(panel);
        setCentralWidget(root);

        timer_.setInterval(duration_ms_->value());
        connect(&timer_, &QTimer::timeout, this, [this]() {
            const int next = (canvas_->frameIndex() + 1) % canvas_->frameCount();
            canvas_->setFrameIndex(next);
            frame_index_->setValue(next + 1);
            refreshDiagnostics();
        });

        connect(open_base, &QPushButton::clicked, this, [this]() { openBase(); });
        connect(open_overlay, &QPushButton::clicked, this, [this]() { openOverlay(); });
        connect(clear_overlay, &QPushButton::clicked, this, [this]() {
            canvas_->clearOverlay();
            overlay_path_.clear();
            refreshDiagnostics();
        });
        connect(frame_count_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setFrameCount(value);
            frame_index_->setRange(1, value);
            frame_index_->setValue(std::min(frame_index_->value(), value));
            refreshDiagnostics();
        });
        connect(frame_index_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
            canvas_->setFrameIndex(value - 1);
            refreshDiagnostics();
        });
        connect(duration_ms_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) { timer_.setInterval(value); });
        connect(anchor_x_, qOverload<double>(&QDoubleSpinBox::valueChanged), this, [this](double) { refreshAnchor(); });
        connect(anchor_y_, qOverload<double>(&QDoubleSpinBox::valueChanged), this, [this](double) { refreshAnchor(); });
        connect(checkerboard_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowCheckerboard(value); });
        connect(bounds_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowBounds(value); });
        connect(show_overlay_, &QCheckBox::toggled, canvas_, [this](bool value) { canvas_->setShowOverlay(value); });
        connect(play_, &QPushButton::toggled, this, [this](bool playing) {
            play_->setText(playing ? QStringLiteral("Pause animation") : QStringLiteral("Play animation"));
            if (playing) timer_.start(); else timer_.stop();
        });
        connect(export_frame, &QPushButton::clicked, this, [this]() { exportCurrentFrame(); });

        auto* file_menu = menuBar()->addMenu(QStringLiteral("&File"));
        auto* open_base_action = file_menu->addAction(QStringLiteral("Open &base PNG..."));
        auto* open_overlay_action = file_menu->addAction(QStringLiteral("Open &activity overlay..."));
        file_menu->addSeparator();
        auto* export_action = file_menu->addAction(QStringLiteral("&Export current frame..."));
        connect(open_base_action, &QAction::triggered, this, [this]() { openBase(); });
        connect(open_overlay_action, &QAction::triggered, this, [this]() { openOverlay(); });
        connect(export_action, &QAction::triggered, this, [this]() { exportCurrentFrame(); });

        refreshDiagnostics();
    }

private:
    void openBase() {
        const QString path = QFileDialog::getOpenFileName(this, QStringLiteral("Open City Horizon PNG"), QString(),
                                                          QStringLiteral("PNG image (*.png);;Images (*.png *.bmp *.webp)"));
        if (path.isEmpty()) return;
        QImage image(path);
        if (image.isNull()) {
            statusBar()->showMessage(QStringLiteral("Could not open image."), 5000);
            return;
        }
        base_path_ = path;
        canvas_->setBaseImage(image);
        canvas_->setFrameIndex(0);
        frame_index_->setValue(1);
        refreshDiagnostics();
        statusBar()->showMessage(QStringLiteral("Opened %1").arg(QFileInfo(path).fileName()), 5000);
    }

    void openOverlay() {
        const QString path = QFileDialog::getOpenFileName(this, QStringLiteral("Open CH_BUILDING_ACTIVITY_OVERLAY_V1 PNG"), QString(),
                                                          QStringLiteral("PNG image (*.png)"));
        if (path.isEmpty()) return;
        QImage image(path);
        if (image.isNull()) {
            statusBar()->showMessage(QStringLiteral("Could not open overlay."), 5000);
            return;
        }
        overlay_path_ = path;
        canvas_->setOverlayImage(image);
        refreshDiagnostics();
        statusBar()->showMessage(QStringLiteral("Overlay loaded for composited inspection."), 5000);
    }

    void refreshAnchor() {
        canvas_->setAnchor(QPointF(anchor_x_->value(), anchor_y_->value()));
    }

    void refreshDiagnostics() {
        const QImage& base = canvas_->baseImage();
        if (base.isNull()) {
            diagnostics_->setText(QStringLiteral("No sprite loaded.\n\nOpen a PNG to inspect alpha, edge fringe, frame geometry and anchor alignment."));
            return;
        }

        const int frames = canvas_->frameCount();
        const bool divisible = base.width() % frames == 0;
        const QRect source = canvas_->baseFrameRect();
        const AlphaStats stats = analyzeAlpha(base, source);
        QString text = QStringLiteral("Base: %1 × %2 px\nFrames: %3%4\nCurrent frame: %5 × %6 px\nOpaque: %7\nSemi-transparent: %8\nTransparent: %9\nEdge fringe: %10")
                           .arg(base.width()).arg(base.height()).arg(frames)
                           .arg(divisible ? QString() : QStringLiteral("  [WIDTH NOT DIVISIBLE]"))
                           .arg(source.width()).arg(source.height())
                           .arg(stats.opaque).arg(stats.semi_transparent).arg(stats.transparent).arg(stats.edge_fringe);

        if (!stats.opaque_bounds.isEmpty()) {
            const QRect local = stats.opaque_bounds.translated(-source.topLeft());
            text += QStringLiteral("\nOpaque bounds: x%1 y%2 %3×%4")
                        .arg(local.x()).arg(local.y()).arg(local.width()).arg(local.height());
        }

        const QImage& overlay = canvas_->overlayImage();
        if (!overlay.isNull()) {
            const QRect overlay_frame = canvas_->overlayFrameRect();
            const bool geometry_match = overlay_frame.size() == source.size();
            text += QStringLiteral("\n\nActivity overlay: %1 × %2 px\nOverlay frame: %3 × %4 px\nGeometry: %5")
                        .arg(overlay.width()).arg(overlay.height())
                        .arg(overlay_frame.width()).arg(overlay_frame.height())
                        .arg(geometry_match ? QStringLiteral("MATCH") : QStringLiteral("MISMATCH — fix before runtime"));
        }

        if (stats.edge_fringe > 0) {
            text += QStringLiteral("\n\nNote: fringe count means semi-transparent edge pixels touching transparency. This is a diagnostic, not automatic proof of a bad halo; normal anti-aliasing can produce valid fringe.");
        }
        diagnostics_->setText(text);
    }

    void exportCurrentFrame() {
        const QImage& base = canvas_->baseImage();
        const QRect source = canvas_->baseFrameRect();
        if (base.isNull() || source.isEmpty()) return;

        const QString suggested = base_path_.isEmpty()
            ? QStringLiteral("sprite_frame_%1.png").arg(canvas_->frameIndex(), 2, 10, QLatin1Char('0'))
            : QFileInfo(base_path_).completeBaseName() + QStringLiteral("_frame_%1.png").arg(canvas_->frameIndex(), 2, 10, QLatin1Char('0'));
        const QString path = QFileDialog::getSaveFileName(this, QStringLiteral("Export inspected frame"), suggested,
                                                          QStringLiteral("PNG image (*.png)"));
        if (path.isEmpty()) return;

        QImage output = base.copy(source).convertToFormat(QImage::Format_ARGB32);
        if (show_overlay_->isChecked() && !canvas_->overlayImage().isNull()) {
            const QRect overlay_source = canvas_->overlayFrameRect();
            QImage overlay_frame = canvas_->overlayImage().copy(overlay_source);
            if (overlay_frame.size() == output.size()) {
                QPainter painter(&output);
                painter.drawImage(QPoint(0, 0), overlay_frame);
            }
        }
        if (!output.save(path, "PNG")) statusBar()->showMessage(QStringLiteral("Export failed."), 5000);
        else statusBar()->showMessage(QStringLiteral("Exported %1").arg(QFileInfo(path).fileName()), 5000);
    }

    SpriteCanvas* canvas_ = nullptr;
    QSpinBox* frame_count_ = nullptr;
    QSpinBox* frame_index_ = nullptr;
    QSpinBox* duration_ms_ = nullptr;
    QDoubleSpinBox* anchor_x_ = nullptr;
    QDoubleSpinBox* anchor_y_ = nullptr;
    QPushButton* play_ = nullptr;
    QCheckBox* checkerboard_ = nullptr;
    QCheckBox* bounds_ = nullptr;
    QCheckBox* show_overlay_ = nullptr;
    QLabel* diagnostics_ = nullptr;
    QTimer timer_;
    QString base_path_;
    QString overlay_path_;
};

} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("City Horizon Sprite Workshop"));
    SpriteWorkshopWindow window;
    window.show();
    return app.exec();
}
