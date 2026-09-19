#pragma once

#include "animation_core.h"

#include <QImage>
#include <QSize>

namespace ch::studio {

class AnimationPreviewRenderer final {
public:
    static QImage renderFrame(const AnimatedAssetSpec& asset, const AnimationClip& clip,
                              int frame_index);
    static QImage renderSpriteSheet(const AnimatedAssetSpec& asset, const AnimationClip& clip,
                                    int columns = 0);
    static QImage renderPreviewSheet(const AnimatedAssetSpec& asset, const AnimationClip& clip,
                                     QSize canvas = QSize(960, 640));
};

} // namespace ch::studio
