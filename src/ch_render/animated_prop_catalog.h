#ifndef CITY_HORIZON_CH_RENDER_ANIMATED_PROP_CATALOG_H
#define CITY_HORIZON_CH_RENDER_ANIMATED_PROP_CATALOG_H

#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>
#include <cstdint>
#include <optional>

namespace ch {

enum class AnimationDriver {
    Time,
    Rotation,
    Oscillate,
    Path,
    State,
    Distance
};

enum class VisualPresentation {
    TransformRotation,
    AtlasPhase
};

struct AnimatedPropLayerDef {
    std::string id;
    std::string sprite_path;
    AnimationDriver driver = AnimationDriver::Rotation;
    VisualPresentation presentation = VisualPresentation::TransformRotation;
    float mount_point_x = 0.0F; // Asset-local coordinate on base
    float mount_point_y = 0.0F;
    float pivot_x = 0.0F;       // Layer-local coordinate on sprite
    float pivot_y = 0.0F;
    int render_order = 1;
};

struct AnimatedPropDefinition {
    std::string contract = "CH_ANIMATED_PROP_V1";
    std::string id;
    std::string base_static_path;
    float base_width = 0.0F;
    float base_height = 0.0F;
    std::vector<AnimatedPropLayerDef> layers;
};

class AnimatedPropCatalog {
public:
    AnimatedPropCatalog() = default;

    bool load_manifest(const std::filesystem::path& manifest_path);
    bool load_directory(const std::filesystem::path& directory_path);

    [[nodiscard]] const AnimatedPropDefinition* find_prop(const std::string& prop_id) const;

    void clear() { catalog_.clear(); }

private:
    std::unordered_map<std::string, AnimatedPropDefinition> catalog_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_RENDER_ANIMATED_PROP_CATALOG_H
