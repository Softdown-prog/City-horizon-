#include "animation_visual_source_renderer.h"

namespace ch::studio {

QImage AnimationVisualSourceRenderer::renderSource(const AnimatedAssetSpec& asset,
                                                   const AnimationNodeSpec& node,
                                                   QString* reason) {
    return renderSource(asset, node, node.visual_variant, reason);
}

} // namespace ch::studio
