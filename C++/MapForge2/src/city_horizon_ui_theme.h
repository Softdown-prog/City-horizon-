#pragma once

#include <QColor>
#include <QFont>
#include <QRectF>
#include <QString>

namespace ch::ui {

struct Theme final {
    static QColor backdrop() { return QColor(4, 14, 20, 178); }
    static QColor panel() { return QColor(15, 33, 45, 247); }
    static QColor panelRaised() { return QColor(20, 44, 59, 252); }
    static QColor border() { return QColor(70, 119, 145); }
    static QColor borderSoft() { return QColor(42, 78, 98); }
    static QColor accent() { return QColor(91, 188, 211); }
    static QColor accentHover() { return QColor(117, 211, 230); }
    static QColor textPrimary() { return QColor(238, 246, 249); }
    static QColor textSecondary() { return QColor(158, 186, 199); }
    static QColor disabledFill() { return QColor(31, 43, 50); }
    static QColor disabledText() { return QColor(105, 121, 129); }
    static QColor shadow() { return QColor(0, 0, 0, 95); }

    static QFont titleFont() {
        QFont font(QStringLiteral("Segoe UI"));
        font.setPixelSize(29);
        font.setWeight(QFont::DemiBold);
        return font;
    }

    static QFont sectionFont() {
        QFont font(QStringLiteral("Segoe UI"));
        font.setPixelSize(16);
        font.setWeight(QFont::DemiBold);
        return font;
    }

    static QFont bodyFont() {
        QFont font(QStringLiteral("Segoe UI"));
        font.setPixelSize(14);
        return font;
    }
};

struct PauseLayout final {
    QRectF panel;
    QRectF titleArea;
    QRectF buttonsArea;
    qreal buttonHeight = 52.0;
    qreal buttonGap = 10.0;

    static PauseLayout forViewport(const QSizeF viewport) {
        constexpr qreal kMaxWidth = 520.0;
        constexpr qreal kMaxHeight = 570.0;
        constexpr qreal kMargin = 28.0;

        const qreal width = qMin(kMaxWidth, qMax(360.0, viewport.width() - kMargin * 2.0));
        const qreal height = qMin(kMaxHeight, qMax(500.0, viewport.height() - kMargin * 2.0));
        const qreal x = (viewport.width() - width) * 0.5;
        const qreal y = (viewport.height() - height) * 0.5;

        PauseLayout layout;
        layout.panel = QRectF(x, y, width, height);
        layout.titleArea = QRectF(x + 34.0, y + 28.0, width - 68.0, 76.0);
        layout.buttonsArea = QRectF(x + 34.0, y + 126.0, width - 68.0, height - 160.0);
        return layout;
    }
};

}  // namespace ch::ui
