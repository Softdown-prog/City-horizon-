#include "city_horizon_ui_theme.h"

#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QStringList>

#include <algorithm>

namespace {

using ch::ui::PauseLayout;
using ch::ui::Theme;

void drawBackground(QPainter& painter, const QSize& size) {
    painter.fillRect(QRect(QPoint(0, 0), size), QColor(76, 112, 78));

    // Lightweight stand-in for the running city.  The preview intentionally
    // contains no PNG artwork: it validates contrast, scale and composition.
    painter.setPen(QPen(QColor(103, 137, 93), 1.0));
    constexpr int step = 44;
    for (int x = -size.height(); x < size.width() + size.height(); x += step) {
        painter.drawLine(QPointF(x, 0), QPointF(x + size.height(), size.height()));
    }
    for (int x = 0; x < size.width() + size.height(); x += step) {
        painter.drawLine(QPointF(x, 0), QPointF(x - size.height(), size.height()));
    }

    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(74, 79, 83));
    painter.drawPolygon(QPolygonF{
        QPointF(0, size.height() * 0.64),
        QPointF(size.width() * 0.44, size.height() * 0.42),
        QPointF(size.width(), size.height() * 0.69),
        QPointF(size.width(), size.height() * 0.80),
        QPointF(size.width() * 0.44, size.height() * 0.53),
        QPointF(0, size.height() * 0.75),
    });

    painter.setBrush(QColor(195, 185, 151));
    painter.drawRect(QRectF(size.width() * 0.12, size.height() * 0.22, 170, 105));
    painter.setBrush(QColor(126, 77, 56));
    painter.drawPolygon(QPolygonF{
        QPointF(size.width() * 0.10, size.height() * 0.22),
        QPointF(size.width() * 0.205, size.height() * 0.14),
        QPointF(size.width() * 0.27, size.height() * 0.22),
        QPointF(size.width() * 0.205, size.height() * 0.30),
    });

    painter.setBrush(QColor(213, 206, 177));
    painter.drawRect(QRectF(size.width() * 0.70, size.height() * 0.24, 150, 94));
    painter.setBrush(QColor(102, 68, 53));
    painter.drawPolygon(QPolygonF{
        QPointF(size.width() * 0.68, size.height() * 0.24),
        QPointF(size.width() * 0.77, size.height() * 0.17),
        QPointF(size.width() * 0.84, size.height() * 0.24),
        QPointF(size.width() * 0.77, size.height() * 0.31),
    });
}

void drawButton(QPainter& painter, const QRectF& rect, const QString& label, const bool enabled,
                const bool primary) {
    QPainterPath path;
    path.addRoundedRect(rect, 8.0, 8.0);

    QColor fill = primary ? QColor(33, 101, 125) : Theme::panelRaised();
    QColor border = primary ? Theme::accent() : Theme::borderSoft();
    QColor text = Theme::textPrimary();
    if (!enabled) {
        fill = Theme::disabledFill();
        border = QColor(52, 66, 74);
        text = Theme::disabledText();
    }

    painter.fillPath(path, fill);
    painter.setPen(QPen(border, primary ? 1.8 : 1.2));
    painter.drawPath(path);

    if (primary && enabled) {
        const QRectF glow(rect.left() + 1.0, rect.top() + 1.0, rect.width() - 2.0, 2.0);
        painter.fillRect(glow, QColor(151, 229, 240, 95));
    }

    painter.setFont(Theme::sectionFont());
    painter.setPen(text);
    painter.drawText(rect, Qt::AlignCenter, label);
}

void drawPauseMenu(QPainter& painter, const QSize& size) {
    const QRectF viewport(QPointF(0, 0), QSizeF(size));
    painter.fillRect(viewport, Theme::backdrop());

    const PauseLayout layout = PauseLayout::forViewport(viewport.size());
    const QRectF shadowRect = layout.panel.translated(0.0, 10.0);
    QPainterPath shadowPath;
    shadowPath.addRoundedRect(shadowRect, 15.0, 15.0);
    painter.fillPath(shadowPath, Theme::shadow());

    QPainterPath panelPath;
    panelPath.addRoundedRect(layout.panel, 14.0, 14.0);
    painter.fillPath(panelPath, Theme::panel());
    painter.setPen(QPen(Theme::border(), 1.5));
    painter.drawPath(panelPath);

    const QRectF accentLine(layout.panel.left() + 2.0, layout.panel.top() + 2.0,
                            layout.panel.width() - 4.0, 3.0);
    painter.fillRect(accentLine, Theme::accent());

    painter.setFont(Theme::titleFont());
    painter.setPen(Theme::textPrimary());
    painter.drawText(layout.titleArea.adjusted(0.0, 0.0, 0.0, -20.0),
                     Qt::AlignHCenter | Qt::AlignVCenter, QStringLiteral("JOGO PAUSADO"));

    painter.setFont(Theme::bodyFont());
    painter.setPen(Theme::textSecondary());
    painter.drawText(layout.titleArea.adjusted(0.0, 38.0, 0.0, 0.0),
                     Qt::AlignHCenter | Qt::AlignVCenter,
                     QStringLiteral("City Horizon  •  sessão atual preservada"));

    const QStringList labels = {
        QStringLiteral("CONTINUAR"),
        QStringLiteral("SALVAR JOGO"),
        QStringLiteral("CARREGAR JOGO"),
        QStringLiteral("CONFIGURAÇÕES"),
        QStringLiteral("MENU PRINCIPAL"),
        QStringLiteral("SAIR DO JOGO"),
    };

    qreal y = layout.buttonsArea.top();
    for (int index = 0; index < labels.size(); ++index) {
        const QRectF button(layout.buttonsArea.left(), y, layout.buttonsArea.width(), layout.buttonHeight);
        const bool operational = index == 0;
        drawButton(painter, button, labels.at(index), operational, operational);
        y += layout.buttonHeight + layout.buttonGap;
    }

    painter.setFont(Theme::bodyFont());
    painter.setPen(Theme::textSecondary());
    const QRectF footer(layout.panel.left() + 30.0, layout.panel.bottom() - 33.0,
                        layout.panel.width() - 60.0, 18.0);
    painter.drawText(footer, Qt::AlignCenter, QStringLiteral("ESC  •  continuar"));
}

}  // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);

    const QSize size(1280, 720);
    QImage image(size, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::TextAntialiasing, true);
    drawBackground(painter, size);
    drawPauseMenu(painter, size);
    painter.end();

    const QString output = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QStringLiteral("city_horizon_pause_stage1.png");
    return image.save(output, "PNG") ? 0 : 2;
}
