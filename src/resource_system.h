#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct AgriculturalResourceDefinition {
    std::string id;
    std::string display_name;
    std::string storage_class;
    int base_sell_price = 0;
    std::string icon_path;
};

class AgriculturalResourceCatalog {
public:
    bool load_from_directory(const std::filesystem::path& directory);
    [[nodiscard]] const AgriculturalResourceDefinition* find(std::string_view id) const;
    [[nodiscard]] const std::vector<AgriculturalResourceDefinition>& definitions() const;
private:
    std::vector<AgriculturalResourceDefinition> definitions_;
};
