#include "terrain_semantics.h"
#include "semantic_contracts.h"
#include <cctype>
#include <optional>

namespace ch {
namespace {
std::optional<std::string> string_field(std::string_view object, std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\"";
    const auto key_pos = object.find(needle);
    if (key_pos == std::string_view::npos) return std::nullopt;
    const auto colon = object.find(':', key_pos + needle.size());
    if (colon == std::string_view::npos) return std::nullopt;
    const auto begin = object.find('"', colon + 1);
    if (begin == std::string_view::npos) return std::nullopt;
    const auto end = object.find('"', begin + 1);
    if (end == std::string_view::npos) return std::nullopt;
    return std::string(object.substr(begin + 1, end - begin - 1));
}
std::optional<bool> bool_field(std::string_view object, std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\"";
    const auto key_pos = object.find(needle);
    if (key_pos == std::string_view::npos) return std::nullopt;
    const auto colon = object.find(':', key_pos + needle.size());
    if (colon == std::string_view::npos) return std::nullopt;
    std::size_t pos = colon + 1;
    while (pos < object.size() && std::isspace(static_cast<unsigned char>(object[pos]))) ++pos;
    if (object.substr(pos, 4) == "true") return true;
    if (object.substr(pos, 5) == "false") return false;
    return std::nullopt;
}
bool allowed_surface(std::string_view value) {
    return value == "sidewalk" || value == "plaza" || value == "industrial_floor" ||
           value == "grass" || value == "soil" || value == "road" || value == "water" ||
           value == "restricted_area";
}
}

TerrainSemanticCatalog::TerrainSemanticCatalog(std::string json) {
    if (json.empty()) { error_ = "empty terrain catalog"; return; }
    const auto definitions_key = json.find("\"definitions\"");
    const auto start = json.find('[', definitions_key);
    if (definitions_key == std::string::npos || start == std::string::npos) { error_ = "missing definitions array"; return; }
    std::size_t pos = start + 1;
    while (true) {
        const auto begin = json.find('{', pos);
        if (begin == std::string::npos) break;
        int depth = 0; std::size_t end = begin;
        for (; end < json.size(); ++end) { if (json[end] == '{') ++depth; else if (json[end] == '}' && --depth == 0) break; }
        if (end == json.size()) { error_ = "unterminated definition"; definitions_.clear(); return; }
        const std::string_view obj(json.data() + begin, end - begin + 1);
        const auto contract = string_field(obj, "contract");
        const auto id = string_field(obj, "id");
        const auto material = string_field(obj, "visualMaterial");
        const auto surface = string_field(obj, "surface");
        const auto pedestrian = bool_field(obj, "pedestrianWalkable");
        const auto vehicle = bool_field(obj, "vehicleDriveable");
        const auto buildable = bool_field(obj, "buildable");
        const auto farmable = bool_field(obj, "farmable");
        if (!contract || *contract != kTerrainSemanticsContract || !id || id->empty() || !material || material->empty() ||
            !surface || !allowed_surface(*surface) || !pedestrian || !vehicle || !buildable || !farmable || definitions_.contains(*id)) {
            error_ = "invalid CH_TERRAIN_SEMANTICS_V1 definition"; definitions_.clear(); return;
        }
        definitions_.emplace(*id, TerrainSemanticDefinition{*id, *material, *surface, *pedestrian, *vehicle, *buildable, *farmable});
        pos = end + 1;
    }
    if (definitions_.empty()) { error_ = "empty definitions array"; return; }
    valid_ = true;
}

const TerrainSemanticDefinition* TerrainSemanticCatalog::find(std::string_view id) const {
    const auto it = definitions_.find(std::string(id));
    return it == definitions_.end() ? nullptr : &it->second;
}
} // namespace ch
