from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match for {old[:60]!r}, found {count}")
    write(path, text.replace(old, new, 1))


def insert_before_once(path: str, marker: str, addition: str) -> None:
    text = read(path)
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one insertion marker {marker[:60]!r}, found {count}")
    write(path, text.replace(marker, addition + marker, 1))


def insert_after_once(path: str, marker: str, addition: str) -> None:
    text = read(path)
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one insertion marker {marker[:60]!r}, found {count}")
    write(path, text.replace(marker, marker + addition, 1))


def insert_after_struct(path: str, struct_name: str, addition: str) -> None:
    text = read(path)
    start_marker = f"struct {struct_name} {{"
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{path}: struct {struct_name} not found")
    end = text.find("\n};", start)
    if end < 0:
        raise SystemExit(f"{path}: struct {struct_name} end not found")
    end += len("\n};")
    text = text[:end] + addition + text[end:]
    write(path, text)


# ---------------------------------------------------------------------------
# building_system.h — data contract and per-instance color state.
# ---------------------------------------------------------------------------
insert_after_struct(
    "src/building_system.h",
    "BuildingAnimationDefinition",
    '''

// CH_COLOR_MASK_V1 runtime contract. A is object coverage while R/G identify
// independently recolorable wall and roof regions.
struct BuildingColorTint {
    std::uint8_t r = 255;
    std::uint8_t g = 255;
    std::uint8_t b = 255;
};

struct BuildingColorMaskDefinition {
    bool enabled = false;
    std::array<std::string, 4> sprite_paths;
};''',
)

insert_after_once(
    "src/building_system.h",
    "    std::optional<BuildingAnimationDefinition> animation;\n",
    "    std::optional<BuildingColorMaskDefinition> color_mask;\n",
)
insert_after_once(
    "src/building_system.h",
    "    [[nodiscard]] const std::string& texture_path_for(BuildingRotation rotation, int level = 1) const;\n",
    "    [[nodiscard]] const std::string& color_mask_path_for(BuildingRotation rotation) const;\n"
    "    [[nodiscard]] bool supports_color_mask(BuildingRotation rotation) const;\n",
)
insert_after_once(
    "src/building_system.h",
    "    std::int64_t service_price = 0;\n",
    '''

    // Two instances of the same definition may carry different player colors.
    // False means render the approved source PNG with no recolor pass.
    bool color_customized = false;
    BuildingColorTint wall_tint{};
    BuildingColorTint roof_tint{};''',
)
insert_before_once(
    "src/building_system.h",
    "    std::size_t set_operational_by_definition(std::string_view definition_id, bool operational);\n",
    "    [[nodiscard]] bool set_color_customization(std::uint64_t instance_id, BuildingColorTint wall, BuildingColorTint roof);\n"
    "    [[nodiscard]] bool clear_color_customization(std::uint64_t instance_id);\n",
)

# ---------------------------------------------------------------------------
# building_system.cpp — parser, directional path lookup and state mutation.
# ---------------------------------------------------------------------------
insert_before_once(
    "src/building_system.cpp",
    "    if (const auto serialized_access_points = json_array_objects(json, \"accessPoints\")) {\n",
    '''    if (const auto serialized_mask = json_object(json, "colorMask")) {
        const bool enabled = json_bool(*serialized_mask, "enabled").value_or(false);
        if (enabled) {
            if (json_string(*serialized_mask, "contract").value_or("") != "CH_COLOR_MASK_V1") return std::nullopt;
            const auto channels = json_object(*serialized_mask, "channels");
            const auto mask_sprites = json_object(*serialized_mask, "sprites");
            if (!channels || !mask_sprites || json_string(*channels, "R").value_or("") != "wall" ||
                json_string(*channels, "G").value_or("") != "roof") {
                return std::nullopt;
            }
            BuildingColorMaskDefinition mask;
            mask.enabled = true;
            for (std::size_t index = 0; index < mask.sprite_paths.size(); ++index) {
                mask.sprite_paths[index] = json_string(*mask_sprites, std::to_string(index)).value_or("");
                if (definition.available_rotations[index] && mask.sprite_paths[index].empty()) return std::nullopt;
            }
            definition.color_mask = mask;
        }
    }

''',
)
insert_before_once(
    "src/building_system.cpp",
    "float BuildingDefinition::anchor_x_for(const BuildingRotation rotation, const int level) const {\n",
    '''const std::string& BuildingDefinition::color_mask_path_for(const BuildingRotation rotation) const {
    static const std::string empty;
    if (!supports_color_mask(rotation)) return empty;
    return color_mask->sprite_paths[static_cast<std::size_t>(rotation)];
}

bool BuildingDefinition::supports_color_mask(const BuildingRotation rotation) const {
    return color_mask.has_value() && color_mask->enabled && supports_rotation(rotation) &&
           !color_mask->sprite_paths[static_cast<std::size_t>(rotation)].empty();
}

''',
)
insert_before_once(
    "src/building_system.cpp",
    "std::size_t BuildingManager::set_operational_by_definition(const std::string_view definition_id, const bool operational) {\n",
    '''bool BuildingManager::set_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall,
                                              const BuildingColorTint roof) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->wall_tint = wall;
    found->roof_tint = roof;
    found->color_customized = true;
    return true;
}

bool BuildingManager::clear_color_customization(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->color_customized = false;
    found->wall_tint = {};
    found->roof_tint = {};
    return true;
}

''',
)

# ---------------------------------------------------------------------------
# main.cpp — extract R/G channels once and render them as color overlays.
# ---------------------------------------------------------------------------
insert_before_once(
    "src/main.cpp",
    "    [[nodiscard]] const TextureAsset* find(const std::filesystem::path& path) const {\n",
    '''    [[nodiscard]] const TextureAsset* load_mask_channel(SDL_Renderer* renderer, const std::filesystem::path& path,
                                                        const char channel) {
        if (channel != 'R' && channel != 'G') return nullptr;
        const std::string key = path.generic_string() + "#CH_COLOR_MASK_" + channel;
        if (const auto existing = textures_.find(key); existing != textures_.end()) return &existing->second;

        SDL_Surface* source = SDL_LoadPNG(path.string().c_str());
        if (source == nullptr) {
            std::cerr << "Color mask could not be loaded: " << path << "\\nSDL error: " << SDL_GetError() << '\\n';
            return nullptr;
        }
        SDL_Surface* extracted = SDL_CreateSurface(source->w, source->h, SDL_PIXELFORMAT_RGBA32);
        if (extracted == nullptr) {
            SDL_DestroySurface(source);
            return nullptr;
        }
        for (int y = 0; y < source->h; ++y) {
            for (int x = 0; x < source->w; ++x) {
                Uint8 r = 0, g = 0, b = 0, a = 0;
                if (!SDL_ReadSurfacePixel(source, x, y, &r, &g, &b, &a)) continue;
                const Uint8 coverage = channel == 'R' ? r : g;
                const Uint8 mask_alpha = static_cast<Uint8>((static_cast<unsigned>(coverage) * static_cast<unsigned>(a)) / 255U);
                (void)SDL_WriteSurfacePixel(extracted, x, y, 255, 255, 255, mask_alpha);
            }
        }
        SDL_DestroySurface(source);

        TextureAsset asset;
        asset.texture = SDL_CreateTextureFromSurface(renderer, extracted);
        asset.source_width = static_cast<float>(extracted->w);
        asset.source_height = static_cast<float>(extracted->h);
        SDL_DestroySurface(extracted);
        if (asset.texture == nullptr) return nullptr;
        SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
        return &textures_.emplace(key, asset).first->second;
    }

    [[nodiscard]] const TextureAsset* find_mask_channel(const std::filesystem::path& path, const char channel) const {
        const std::string key = path.generic_string() + "#CH_COLOR_MASK_" + channel;
        const auto found = textures_.find(key);
        return found == textures_.end() ? nullptr : &found->second;
    }

''',
)

# Scope the preload insertion to the building-catalog preload block.
main_text = read("src/main.cpp")
preload_start = main_text.find("    for (const BuildingDefinition& definition : catalog.definitions()) {")
preload_end = main_text.find("    show_loading(0.58F, \"CARREGANDO CATALOGO E CONSTRUCOES\");", preload_start)
if preload_start < 0 or preload_end < 0:
    raise SystemExit("src/main.cpp: building preload block not found")
preload_block = main_text[preload_start:preload_end]
preload_line = "                    (void)textures.load(renderer, asset_root / definition.texture_path_for(logical_rotation, lvl.level));\n"
if preload_block.count(preload_line) != 1:
    raise SystemExit(f"src/main.cpp: expected one building preload line, found {preload_block.count(preload_line)}")
preload_block = preload_block.replace(
    preload_line,
    preload_line
    + "                    if (lvl.level == 1 && definition.supports_color_mask(logical_rotation)) {\n"
    + "                        const auto mask_path = asset_root / definition.color_mask_path_for(logical_rotation);\n"
    + "                        (void)textures.load_mask_channel(renderer, mask_path, 'R');\n"
    + "                        (void)textures.load_mask_channel(renderer, mask_path, 'G');\n"
    + "                    }\n",
    1,
)
main_text = main_text[:preload_start] + preload_block + main_text[preload_end:]
write("src/main.cpp", main_text)

insert_after_once(
    "src/main.cpp",
    "                render_building(renderer, *definition, *draw.building, visual_rotation, *texture, camera, viewport_width, viewport_height, SDL_ALPHA_OPAQUE, r, g, b);\n",
    '''
                // CH_COLOR_MASK_V1 is opt-in. The approved source sprite stays
                // untouched until this concrete instance has player colors.
                if (draw.building->color_customized && definition->supports_color_mask(visual_rotation)) {
                    constexpr Uint8 kTintOverlayAlpha = 184;
                    const auto mask_path = root / definition->color_mask_path_for(visual_rotation);
                    if (const TextureAsset* wall = textures.find_mask_channel(mask_path, 'R')) {
                        render_building(renderer, *definition, *draw.building, visual_rotation, *wall, camera,
                                        viewport_width, viewport_height, kTintOverlayAlpha,
                                        draw.building->wall_tint.r, draw.building->wall_tint.g, draw.building->wall_tint.b);
                    }
                    if (const TextureAsset* roof = textures.find_mask_channel(mask_path, 'G')) {
                        render_building(renderer, *definition, *draw.building, visual_rotation, *roof, camera,
                                        viewport_width, viewport_height, kTintOverlayAlpha,
                                        draw.building->roof_tint.r, draw.building->roof_tint.g, draw.building->roof_tint.b);
                    }
                }
''',
)

# ---------------------------------------------------------------------------
# save_manager.cpp — preserve the already-added servicePrice and add optional
# per-instance wall/roof tints. Old saves remain valid because the fields are
# optional; save version 9 remains unchanged.
# ---------------------------------------------------------------------------
insert_after_once(
    "src/save_manager.cpp",
    "        const auto service_price = json_number<std::int64_t>(building, \"servicePrice\");\n",
    '''        const auto wall_tint_r = json_number<int>(building, "wallTintR");
        const auto wall_tint_g = json_number<int>(building, "wallTintG");
        const auto wall_tint_b = json_number<int>(building, "wallTintB");
        const auto roof_tint_r = json_number<int>(building, "roofTintR");
        const auto roof_tint_g = json_number<int>(building, "roofTintG");
        const auto roof_tint_b = json_number<int>(building, "roofTintB");
''',
)
insert_after_once(
    "src/save_manager.cpp",
    "        saved.service_price = (*version >= 9 && service_price.has_value()) ? std::max<std::int64_t>(0, *service_price) : 0;\n",
    '''        const bool has_any_tint = wall_tint_r || wall_tint_g || wall_tint_b || roof_tint_r || roof_tint_g || roof_tint_b;
        if (has_any_tint) {
            if (!wall_tint_r || !wall_tint_g || !wall_tint_b || !roof_tint_r || !roof_tint_g || !roof_tint_b ||
                *wall_tint_r < 0 || *wall_tint_r > 255 || *wall_tint_g < 0 || *wall_tint_g > 255 ||
                *wall_tint_b < 0 || *wall_tint_b > 255 || *roof_tint_r < 0 || *roof_tint_r > 255 ||
                *roof_tint_g < 0 || *roof_tint_g > 255 || *roof_tint_b < 0 || *roof_tint_b > 255) {
                error = "building color customization is invalid";
                return false;
            }
            saved.color_customized = true;
            saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),
                               static_cast<std::uint8_t>(*wall_tint_b)};
            saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),
                               static_cast<std::uint8_t>(*roof_tint_b)};
        }
''',
)

save_text = read("src/save_manager.cpp")
loop_start_marker = "    for (std::size_t index = 0; index < buildings.instances().size(); ++index) {\n"
loop_end_marker = "    output << \"  ],\\n  \\\"roads\\\": [\\n\";\n"
loop_start = save_text.find(loop_start_marker)
loop_end = save_text.find(loop_end_marker, loop_start)
if loop_start < 0 or loop_end < 0:
    raise SystemExit("src/save_manager.cpp: building save loop not found")
new_loop = '''    for (std::size_t index = 0; index < buildings.instances().size(); ++index) {
        const BuildingInstance& building = buildings.instances()[index];
        output << "    { \\\"instanceId\\\": " << building.instance_id << ", \\\"definitionId\\\": \\\"" << escape_json(building.definition_id)
               << "\\\", \\\"tileX\\\": " << building.tile_x << ", \\\"tileY\\\": " << building.tile_y
               << ", \\\"rotation\\\": " << static_cast<int>(building.rotation)
               << ", \\\"level\\\": " << building.current_level
               << ", \\\"servicePrice\\\": " << building.service_price;
        if (building.color_customized) {
            output << ", \\\"wallTintR\\\": " << static_cast<int>(building.wall_tint.r)
                   << ", \\\"wallTintG\\\": " << static_cast<int>(building.wall_tint.g)
                   << ", \\\"wallTintB\\\": " << static_cast<int>(building.wall_tint.b)
                   << ", \\\"roofTintR\\\": " << static_cast<int>(building.roof_tint.r)
                   << ", \\\"roofTintG\\\": " << static_cast<int>(building.roof_tint.g)
                   << ", \\\"roofTintB\\\": " << static_cast<int>(building.roof_tint.b);
        }
        output << " }" << (index + 1U == buildings.instances().size() ? "\\n" : ",\\n");
    }
'''
save_text = save_text[:loop_start] + new_loop + save_text[loop_end:]
write("src/save_manager.cpp", save_text)

# Runtime manifest becomes truthful only in the commit that contains the engine support.
manifest = Path("assets/buildings/bakery/bakery.json")
manifest_text = manifest.read_text(encoding="utf-8")
if '"runtimeTintingImplemented": false' not in manifest_text:
    raise SystemExit("bakery manifest: expected runtimeTintingImplemented false")
manifest.write_text(manifest_text.replace('"runtimeTintingImplemented": false', '"runtimeTintingImplemented": true', 1), encoding="utf-8")

# Lightweight contract checks. Do not trigger a full local rebuild from this migration.
definition = Path("assets/definitions/bakery_01.json").read_text(encoding="utf-8")
assert "CH_COLOR_MASK_V1" in definition
assert '"R": "wall"' in definition and '"G": "roof"' in definition
assert "bakery_south_mask.png" in definition and "bakery_north_mask.png" in definition
assert "service_price" in read("src/building_system.h")
assert "color_customized" in read("src/building_system.h")
assert "servicePrice" in read("src/save_manager.cpp") and "wallTintR" in read("src/save_manager.cpp")
print("CH_COLOR_MASK_V1 runtime migration prepared successfully")
