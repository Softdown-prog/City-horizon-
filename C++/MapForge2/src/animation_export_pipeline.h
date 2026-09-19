#pragma once

#include "animation_core.h"

#include <QString>
#include <QStringList>

namespace ch::studio {

struct AnimationExportResult {
    bool success = false;
    QString reason;
    QString output_directory;
    QStringList files;
};

class AnimationExportPipeline final {
public:
    static constexpr const char* kVersion = "animation_export_4";

    static AnimationExportResult exportClip(const AnimatedAssetSpec& asset,
                                            const QString& clip_id,
                                            const QString& output_directory);
};

} // namespace ch::studio
