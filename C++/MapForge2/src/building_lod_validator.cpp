#include "building_lod_validator.h"

#include "building_facade_renderer.h"

#include <QFont>
#include <QPainter>
#include <QStringList>

#include <algorithm>
#include <array>

namespace ch::studio {
namespace {

struct LodProfile {
    const char* id;
    const char* label;
    float scale;
    int min_width;
    int min_height;
    int min_alpha_pixels;
    int min_luminance_range;
};

constexpr std::array<LodProfile, 3> kProfiles = {{
    {"distant", "Distant", 0.35F, 24, 24, 220, 18},
    {"medium", "Medium", 0.60F, 40, 40, 650, 22},
    {"close", "Close", 1.00F, 64, 64, 1500, 26},
}};

QRect alphaBounds(const QImage& image, const int threshold = 16) {
    int min_x = image.width(), min_y = image.height(), max_x = -1, max_y = -1;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            if (qAlpha(image.pixel(x, y)) <= threshold) continue;
            min_x = std::min(min_x, x); min_y = std::min(min_y, y);
            max_x = std::max(max_x, x); max_y = std::max(max_y, y);
        }
    }
    return max_x >= min_x && max_y >= min_y
        ? QRect(QPoint(min_x, min_y), QPoint(max_x, max_y))
        : QRect();
}

BuildingLodLevelValidation evaluate(const QImage& image, const LodProfile& profile) {
    BuildingLodLevelValidation level;
    level.id = QString::fromLatin1(profile.id);
    level.label = QString::fromLatin1(profile.label);
    level.scale = profile.scale;

    const QRect bounds = alphaBounds(image);
    level.visible_width_px = bounds.width();
    level.visible_height_px = bounds.height();

    int min_luma = 255;
    int max_luma = 0;
    int alpha_pixels = 0;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QRgb pixel = image.pixel(x, y);
            if (qAlpha(pixel) <= 32) continue;
            ++alpha_pixels;
            const int luma = (qRed(pixel) * 54 + qGreen(pixel) * 183 + qBlue(pixel) * 19) / 256;
            min_luma = std::min(min_luma, luma);
            max_luma = std::max(max_luma, luma);
        }
    }
    level.visible_alpha_pixels = alpha_pixels;
    level.luminance_range = alpha_pixels > 0 ? max_luma - min_luma : 0;

    QStringList failures;
    if (level.visible_width_px < profile.min_width) failures << QStringLiteral("silhouette too narrow");
    if (level.visible_height_px < profile.min_height) failures << QStringLiteral("silhouette too short");
    if (level.visible_alpha_pixels < profile.min_alpha_pixels) failures << QStringLiteral("too little visible area");
    if (level.luminance_range < profile.min_luminance_range) failures << QStringLiteral("insufficient visual contrast");

    level.valid = failures.isEmpty();
    level.reason = level.valid ? QStringLiteral("pass") : failures.join(QStringLiteral(", "));
    return level;
}

QImage scaledBuilding(const BuildingComposerSpec& spec, const LodProfile& profile) {
    const QSize source_size(420, 420);
    const QImage source = BuildingFacadeRenderer::renderView(spec, BuildingView::South, source_size);
    const QSize target(std::max(1, static_cast<int>(source.width() * profile.scale)),
                       std::max(1, static_cast<int>(source.height() * profile.scale)));
    return source.scaled(target, Qt::KeepAspectRatio, Qt::SmoothTransformation);
}

void drawLevelCard(QPainter& painter, const QRect& rect, const BuildingComposerSpec& spec,
                   const LodProfile& profile, const BuildingLodLevelValidation& validation) {
    painter.save();
    painter.fillRect(rect, QColor("#20292d"));
    painter.setPen(QPen(QColor("#435158"), 1.0));
    painter.drawRect(rect.adjusted(0, 0, -1, -1));

    QFont title(QStringLiteral("Arial"));
    title.setBold(true);
    title.setPointSize(10);
    painter.setFont(title);
    painter.setPen(validation.valid ? QColor("#cfe5c8") : QColor("#efb5a9"));
    painter.drawText(QRect(rect.left() + 10, rect.top() + 8, rect.width() - 20, 24),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("%1 — %2% — %3")
                        .arg(validation.label)
                        .arg(static_cast<int>(profile.scale * 100.0F))
                        .arg(validation.valid ? QStringLiteral("PASS") : QStringLiteral("FAIL")));

    const QImage building = scaledBuilding(spec, profile);
    const QRect target(rect.left() + 10, rect.top() + 40, rect.width() - 20, rect.height() - 108);
    painter.drawImage(QRect(target.center().x() - building.width() / 2,
                            target.center().y() - building.height() / 2,
                            building.width(), building.height()), building);

    QFont info(QStringLiteral("Arial"));
    info.setPointSize(8);
    painter.setFont(info);
    painter.setPen(QColor("#c0cbd0"));
    painter.drawText(QRect(rect.left() + 10, rect.bottom() - 62, rect.width() - 20, 22),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("silhouette %1×%2 px | visible %3 px | contrast %4")
                        .arg(validation.visible_width_px).arg(validation.visible_height_px)
                        .arg(validation.visible_alpha_pixels).arg(validation.luminance_range));
    painter.setPen(validation.valid ? QColor("#9fb0b7") : QColor("#efb5a9"));
    painter.drawText(QRect(rect.left() + 10, rect.bottom() - 40, rect.width() - 20, 30),
                     Qt::AlignLeft | Qt::AlignTop | Qt::TextWordWrap, validation.reason);
    painter.restore();
}

} // namespace

QJsonObject BuildingLodLevelValidation::toJson() const {
    return QJsonObject{
        {"id", id}, {"label", label}, {"scale", static_cast<double>(scale)}, {"valid", valid},
        {"visibleWidthPx", visible_width_px}, {"visibleHeightPx", visible_height_px},
        {"visibleAlphaPixels", visible_alpha_pixels}, {"luminanceRange", luminance_range},
        {"reason", reason},
    };
}

QString BuildingLodValidation::summary() const {
    return valid
        ? QStringLiteral("PASS — distant, medium and close gameplay scales remain legible")
        : QStringLiteral("FAIL — distant=%1 medium=%2 close=%3")
            .arg(distant.valid ? QStringLiteral("ok") : distant.reason)
            .arg(medium.valid ? QStringLiteral("ok") : medium.reason)
            .arg(close.valid ? QStringLiteral("ok") : close.reason);
}

QJsonObject BuildingLodValidation::toJson() const {
    return QJsonObject{
        {"version", QStringLiteral("building_lod_gate_1")},
        {"valid", valid},
        {"distant", distant.toJson()},
        {"medium", medium.toJson()},
        {"close", close.toJson()},
        {"summary", summary()},
    };
}

BuildingLodValidation BuildingLodValidator::validate(const BuildingComposerSpec& spec) {
    BuildingLodValidation result;
    result.distant = evaluate(scaledBuilding(spec, kProfiles[0]), kProfiles[0]);
    result.medium = evaluate(scaledBuilding(spec, kProfiles[1]), kProfiles[1]);
    result.close = evaluate(scaledBuilding(spec, kProfiles[2]), kProfiles[2]);
    result.valid = result.distant.valid && result.medium.valid && result.close.valid;
    return result;
}

QImage BuildingLodValidator::renderReviewSheet(const BuildingComposerSpec& spec, const QSize canvas) {
    QImage sheet(canvas, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));
    QPainter painter(&sheet);
    painter.setRenderHint(QPainter::Antialiasing, true);

    QFont header(QStringLiteral("Arial"));
    header.setBold(true);
    header.setPointSize(11);
    painter.setFont(header);
    painter.setPen(QColor("#e7ecee"));
    painter.drawText(QRect(14, 8, canvas.width() - 28, 28), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("BUILDING LOD / GAMEPLAY SCALE GATE"));
    painter.setPen(QColor("#aebbc0"));
    header.setBold(false);
    header.setPointSize(8);
    painter.setFont(header);
    painter.drawText(QRect(14, 34, canvas.width() - 28, 20), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("Distant 35% / Medium 60% / Close 100% — preview only; production sprite remains unchanged"));

    const BuildingLodValidation validation = validate(spec);
    const int margin = 12;
    const int gap = 10;
    const int top = 62;
    const int card_width = (canvas.width() - margin * 2 - gap * 2) / 3;
    const int card_height = canvas.height() - top - margin;
    drawLevelCard(painter, QRect(margin, top, card_width, card_height), spec, kProfiles[0], validation.distant);
    drawLevelCard(painter, QRect(margin + card_width + gap, top, card_width, card_height), spec, kProfiles[1], validation.medium);
    drawLevelCard(painter, QRect(margin + (card_width + gap) * 2, top, card_width, card_height), spec, kProfiles[2], validation.close);
    painter.end();
    return sheet;
}

QJsonObject BuildingLodValidator::manifest(const BuildingComposerSpec& spec) {
    QJsonArray levels;
    for (const auto& profile : kProfiles) {
        levels.append(QJsonObject{
            {"id", QString::fromLatin1(profile.id)}, {"scale", static_cast<double>(profile.scale)},
            {"minimumVisibleWidthPx", profile.min_width}, {"minimumVisibleHeightPx", profile.min_height},
            {"minimumVisibleAlphaPixels", profile.min_alpha_pixels},
            {"minimumLuminanceRange", profile.min_luminance_range},
        });
    }
    return QJsonObject{
        {"version", QStringLiteral("building_lod_gate_1")},
        {"blockingProductionExport", true},
        {"sourceView", QStringLiteral("south")},
        {"levels", levels},
        {"validation", validate(spec).toJson()},
        {"purpose", QStringLiteral("ensure building silhouette and material/facade contrast remain readable at gameplay zoom scales")},
    };
}

} // namespace ch::studio
