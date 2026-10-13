#pragma once

#include <array>
#include <cstdint>

// CH_RAIL_PURCHASE_CATALOG_V1
// Currency values are game credits, not real-world prices.
// Track quotes are computed separately by RailConstructionEconomy.
namespace ch::rail_catalog {
struct Item {
    const char* id;
    const char* name;
    const char* category;
    std::int64_t cost;
    const char* note;
    bool purchase_implemented;
};

inline constexpr std::array<Item, 8> items{{
    {"rail_track_straight", "Trilho reto (4 un.)", "TRILHOS", 500, "BASE: 125 / UNIDADE | CUSTO FINAL POR COMPRIMENTO", false},
    {"rail_track_curve", "Trilho curvo (referencia 4 un.)", "TRILHOS", 600, "120% DO COMPRIMENTO | VALOR DE REFERENCIA", false},
    {"rail_track_turnout", "Desvio ferroviario (referencia 4 un.)", "TRILHOS", 675, "135% DO COMPRIMENTO | VALOR DE REFERENCIA", false},
    {"rail_track_crossing", "Cruzamento (referencia 4 un.)", "TRILHOS", 600, "120% DO COMPRIMENTO | VALOR DE REFERENCIA", false},
    {"rail_terminal_station_01", "Estacao ferroviaria", "ESTACAO", 7500, "5X3 | MANUTENCAO 125/MES | CATALOGO DE CONSTRUCAO", true},
    {"rail_turntable_7m2_01", "Plataforma giratoria", "INFRAESTRUTURA", 4200, "PRECO PLANEJADO | COMPRA AINDA NAO INTEGRADA", false},
    {"steam_train_locomotive_01", "Locomotiva a vapor", "VEICULOS", 9500, "PRECO PLANEJADO | COMPRA AINDA NAO INTEGRADA", false},
    {"steam_train_coach_01", "Vagao de passageiros", "VEICULOS", 1800, "PRECO POR VAGAO | COMPRA AINDA NAO INTEGRADA", false},
}};

inline constexpr std::int64_t locomotive_monthly_maintenance = 160;
inline constexpr std::int64_t coach_monthly_maintenance = 35;
inline constexpr std::int64_t turntable_monthly_maintenance = 60;
}  // namespace ch::rail_catalog
