#pragma once

#include "animation_core.h"

#include <QImage>
#include <QJsonObject>
#include <QString>

namespace ch::studio {

class AnimationVisualSourceRenderer final {
public:
    static constexpr const char* kVersion = "animation_visual_sources_1";

    static bool validateSource(const AnimatedAssetSpec& asset,
                               const AnimationNodeSpec& node,
                               QString* reason = nullptr);

    static QImage renderSource(const AnimatedAssetSpec& asset,
                               const AnimationNodeSpec& node,
                               QString* reason = nullptr);

    static QJsonObject manifest(const AnimationNodeSpec& node);
};

} // namespace ch::studio
