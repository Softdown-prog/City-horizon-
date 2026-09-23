#pragma once

#include "asset_document.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonObject>
#include <QProcess>
#include <QString>
#include <QStringList>

namespace ch::studio {

inline QString spriteWorkshopResolvedPath(const QString& stored_path, const QString& document_path) {
    if (stored_path.isEmpty()) return {};
    const QFileInfo info(stored_path);
    if (info.isAbsolute()) return QDir::cleanPath(stored_path);
    if (document_path.isEmpty()) return QDir::cleanPath(stored_path);
    return QDir(QFileInfo(document_path).absolutePath()).absoluteFilePath(stored_path);
}

inline int spriteWorkshopDirectionIndex(const QString& direction) {
    if (direction == QStringLiteral("south")) return 0;
    if (direction == QStringLiteral("west")) return 1;
    if (direction == QStringLiteral("north")) return 2;
    if (direction == QStringLiteral("east")) return 3;
    return -1;
}

inline QJsonObject spriteWorkshopBaseAnimation(const QJsonObject& metadata, const QString& direction) {
    const QJsonObject per_direction = metadata.value(QStringLiteral("directionAnimations")).toObject();
    const QJsonObject directional = per_direction.value(direction).toObject();
    if (!directional.isEmpty()) return directional;
    return metadata.value(QStringLiteral("animation")).toObject();
}

inline QString spriteWorkshopOverlayPath(const QJsonObject& metadata, const QString& direction) {
    const QJsonObject activity = metadata.value(QStringLiteral("activityOverlay")).toObject();
    const QJsonObject sprites = activity.value(QStringLiteral("sprites")).toObject();
    QString stored = sprites.value(direction).toString();
    if (!stored.isEmpty()) return stored;
    const int index = spriteWorkshopDirectionIndex(direction);
    if (index >= 0) stored = sprites.value(QString::number(index)).toString();
    return stored;
}

inline bool launchSpriteWorkshop(const AssetDocument& document,
                                 const QString& document_path,
                                 const QString& direction,
                                 QString* reason = nullptr) {
    const QJsonObject metadata = document.metadata();
    const QJsonObject directions = metadata.value(QStringLiteral("directions")).toObject();
    const QString base_stored = directions.value(direction).toString();
    const QString base_path = spriteWorkshopResolvedPath(base_stored, document_path);
    if (base_path.isEmpty() || !QFileInfo::exists(base_path)) {
        if (reason) *reason = QStringLiteral("No readable %1 PNG is assigned to this asset.").arg(direction.toUpper());
        return false;
    }

    const QJsonObject base_animation = spriteWorkshopBaseAnimation(metadata, direction);
    const int base_frames = qMax(1, base_animation.value(QStringLiteral("frameCount")).toInt(1));
    const int base_duration = qMax(16, base_animation.value(QStringLiteral("frameDurationMs")).toInt(125));

    const QJsonObject activity = metadata.value(QStringLiteral("activityOverlay")).toObject();
    const QJsonObject overlay_animation = activity.value(QStringLiteral("animation")).toObject();
    const int overlay_frames = qMax(1, overlay_animation.value(QStringLiteral("frameCount")).toInt(1));
    const int overlay_duration = qMax(16, overlay_animation.value(QStringLiteral("frameDurationMs")).toInt(125));
    const QString overlay_path = spriteWorkshopResolvedPath(spriteWorkshopOverlayPath(metadata, direction), document_path);

    QStringList arguments;
    arguments << QStringLiteral("--base") << base_path
              << QStringLiteral("--base-frames") << QString::number(base_frames)
              << QStringLiteral("--base-duration") << QString::number(base_duration)
              << QStringLiteral("--anchor-x") << QString::number(document.anchorNormalized().x(), 'f', 6)
              << QStringLiteral("--anchor-y") << QString::number(document.anchorNormalized().y(), 'f', 6)
              << QStringLiteral("--direction") << direction.toUpper()
              << QStringLiteral("--asset") << document.displayName();

    if (!overlay_path.isEmpty() && QFileInfo::exists(overlay_path)) {
        arguments << QStringLiteral("--overlay") << overlay_path
                  << QStringLiteral("--overlay-frames") << QString::number(overlay_frames)
                  << QStringLiteral("--overlay-duration") << QString::number(overlay_duration);
    }

#ifdef Q_OS_WIN
    const QString executable_name = QStringLiteral("CityHorizonSpriteWorkshop.exe");
#else
    const QString executable_name = QStringLiteral("CityHorizonSpriteWorkshop");
#endif
    const QString beside_editor = QDir(QCoreApplication::applicationDirPath()).filePath(executable_name);
    const QString program = QFileInfo::exists(beside_editor) ? beside_editor : executable_name;

    if (!QProcess::startDetached(program, arguments)) {
        if (reason) {
            *reason = QStringLiteral("Could not start %1. Build/install the Sprite Workshop beside CityHorizonAssetEditor.")
                          .arg(executable_name);
        }
        return false;
    }

    if (reason) reason->clear();
    return true;
}

} // namespace ch::studio
