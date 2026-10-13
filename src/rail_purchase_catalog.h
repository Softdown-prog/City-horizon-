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

inline constexpr std::int64_t kTurntablePurchaseCost = 4200;
inline constexpr std::int64_t kLocomotivePurchaseCost = 9500;
inline constexpr std::int64_t kCoachPurchaseCost = 1800;

inline constexpr std::array<Item, 10> items{{
    {"rail_track_straight", "Trilho reto", "TRILHOS", 125, "125 POR UNIDADE DE COMPRIMENTO | SEM PACOTE MINIMO | ARRASTE LIVRE", false},
    {"rail_track_curve", "Trilho curvo", "TRILHOS", 150, "150 POR UNIDADE DE COMPRIMENTO | COBRANCA PELO TRACADO REAL", false},
    {"rail_track_turnout", "Desvio ferroviario", "TRILHOS", 169, "135% DO COMPRIMENTO REAL | VALOR BASE ARREDONDADO", false},
    {"rail_track_crossing", "Cruzamento", "TRILHOS", 150, "120% DO COMPRIMENTO REAL | COBRANCA POR PECA LOGICA", false},
    {"rail_terminal_station_01", "Estacao ferroviaria", "ESTACAO", 7500, "5X3 | MANUTENCAO 125/MES | CATALOGO DE CONSTRUCAO", true},
    {"rail_turntable_7m2_01", "Plataforma giratoria", "INFRAESTRUTURA", kTurntablePurchaseCost, "CLIQUE E ESCOLHA TRILHO RETO >= 8M | REEMBOLSO 65%", true},
    {"steam_train_locomotive_01", "Locomotiva a vapor", "VEICULOS", kLocomotivePurchaseCost, "1 POR LINHA | EXIGE ESTAÇÕES A/B E LINHA VALIDADA", true},
    {"steam_train_coach_01", "Vagao de passageiros", "VEICULOS", kCoachPurchaseCost, "PRECO POR UNIDADE | MAXIMO 7 | REQUER LOCOMOTIVA", true},
    {"steam_train_locomotive_02", "Locomotiva - linha 2", "FROTA LINHA 2", kLocomotivePurchaseCost, "SEGUNDA LINHA | EXIGE A1/B1 + A2/B2 EM VIAS SEPARADAS", true},
    {"steam_train_coach_02", "Vagao - linha 2", "FROTA LINHA 2", kCoachPurchaseCost, "1 POR VEZ | ATE 7 | EXIGE LOCOMOTIVA DA LINHA 2", true},
}};

inline constexpr std::int64_t locomotive_monthly_maintenance = 160;
inline constexpr std::int64_t coach_monthly_maintenance = 35;
inline constexpr std::int64_t turntable_monthly_maintenance = 60;
}  // namespace ch::rail_catalog
