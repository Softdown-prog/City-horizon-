#include "resource_system.h"

#include <cctype>
#include <fstream>
#include <optional>
#include <sstream>

namespace {
std::string read_file(const std::filesystem::path& path) { std::ifstream input(path); std::ostringstream output; output << input.rdbuf(); return output.str(); }
std::optional<std::size_t> value_position(const std::string& json, std::string_view key) { const auto found = json.find("\"" + std::string(key) + "\""); if (found == std::string::npos) return std::nullopt; const auto colon = json.find(':', found); if (colon == std::string::npos) return std::nullopt; auto position = colon + 1; while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) ++position; return position; }
std::optional<std::string> string_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position || *position >= json.size() || json[*position] != '\"') return std::nullopt; const auto end = json.find('\"', *position + 1); return end == std::string::npos ? std::nullopt : std::optional(json.substr(*position + 1, end - *position - 1)); }
std::optional<int> int_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position) return std::nullopt; try { return std::stoi(json.substr(*position)); } catch (...) { return std::nullopt; } }
}

bool AgriculturalResourceCatalog::load_from_directory(const std::filesystem::path& directory) {
    definitions_.clear(); std::error_code error;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(directory, error)) {
        if (error || !entry.is_regular_file() || entry.path().extension() != ".json") continue;
        const std::string json = read_file(entry.path()); AgriculturalResourceDefinition definition;
        definition.id = string_value(json, "id").value_or(""); definition.display_name = string_value(json, "displayName").value_or(definition.id);
        definition.storage_class = string_value(json, "storageClass").value_or(""); definition.base_sell_price = int_value(json, "baseSellPrice").value_or(0);
        definition.icon_path = string_value(json, "icon").value_or("");
        if (!definition.id.empty() && !definition.storage_class.empty() && definition.base_sell_price >= 0) definitions_.push_back(std::move(definition));
    }
    return !definitions_.empty();
}
const AgriculturalResourceDefinition* AgriculturalResourceCatalog::find(const std::string_view id) const { for (const auto& definition : definitions_) if (definition.id == id) return &definition; return nullptr; }
const std::vector<AgriculturalResourceDefinition>& AgriculturalResourceCatalog::definitions() const { return definitions_; }
