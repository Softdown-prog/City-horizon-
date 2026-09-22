#pragma once

#include "building_system.h"
#include "simulation_clock.h"

#include <cstddef>
#include <cstdint>
#include <vector>

class PopulationSystem;
class ServiceVehicleCatalog;
class ServiceVehicleManager;
class FarmingSystem;

enum class EconomyTransactionType : std::uint8_t {
    building_construction,
    land_purchase,
    tax_revenue,
    service_revenue,
    property_tax,
    maintenance,
    agricultural_sale,
    local_supply_bonus,
    monthly_closure,
};

struct EconomyTransaction {
    EconomyTransactionType type = EconomyTransactionType::monthly_closure;
    std::int64_t amount = 0;
    GameDate date;
    std::uint64_t building_instance_id = 0;
    std::uint32_t land_parcel_id = 0;
};

struct MonthlyEconomySummary {
    std::int64_t revenue = 0;
    std::int64_t expenses = 0;
    std::int64_t balance = 0;
};

struct ServicePricingEstimate {
    std::uint32_t price_demand_percent = 0;
    std::uint32_t population_demand_percent = 0;
    std::uint32_t customers_per_month = 0;
    std::int64_t revenue_per_month = 0;
};

class CityEconomy {
public:
    explicit CityEconomy(std::int64_t initial_funds = 50'000);

    [[nodiscard]] std::int64_t funds() const;
    [[nodiscard]] const MonthlyEconomySummary& monthly_summary() const;
    [[nodiscard]] const std::vector<EconomyTransaction>& ledger() const;

    [[nodiscard]] bool can_afford(std::int64_t cost) const;
    [[nodiscard]] bool try_spend(std::int64_t cost);
    [[nodiscard]] bool spend_for_building(std::int64_t cost, const GameDate& date, std::uint64_t building_instance_id);
    [[nodiscard]] bool spend_for_land(std::int64_t cost, const GameDate& date, std::uint32_t land_parcel_id);
    void earn_agricultural_sale(std::int64_t amount, const GameDate& date);
    void restore_funds(std::int64_t funds);
    void restore_last_property_tax_year(int year);
    [[nodiscard]] int last_property_tax_year() const;
    void rebuild_monthly_summary(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                 const PopulationSystem& population);
    // Invoked once per calendar close, never polled from the frame loop.
    void on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                         const PopulationSystem& population, const GameDate& closing_date,
                         const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                         const ServiceVehicleManager* vehicles = nullptr, FarmingSystem* farming = nullptr);
    // Compatibility entry point for existing callers/tests.
    void process_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                       const PopulationSystem& population, const GameDate& closing_date,
                       const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                       const ServiceVehicleManager* vehicles = nullptr, FarmingSystem* farming = nullptr);

    // Returns the population-demand revenue percentage for a definition at the
    // supplied population. Definitions without a requirement keep full revenue.
    [[nodiscard]] static std::uint32_t commercial_demand_percent(const BuildingDefinition& definition,
                                                                  std::uint32_t current_population);
    // Price elasticity for player-controlled shops. Default price is the 100% reference;
    // lowering price attracts more customers while higher prices progressively reduce demand.
    [[nodiscard]] static std::uint32_t service_price_demand_percent(const BuildingDefinition& definition,
                                                                     std::int64_t service_price);
    [[nodiscard]] static ServicePricingEstimate service_pricing_estimate(const BuildingDefinition& definition,
                                                                          const BuildingInstance& instance,
                                                                          std::uint32_t current_population);

private:
    void record(EconomyTransactionType type, std::int64_t amount, const GameDate& date,
                std::uint64_t building_instance_id = 0, std::uint32_t land_parcel_id = 0);

    static constexpr std::size_t kMaxLedgerEntries = 100;
    std::int64_t funds_ = 50'000;
    // The fiscal closure marker prevents a save/load from charging January's
    // property tax twice for the same game year.
    int last_property_tax_year_ = 0;
    MonthlyEconomySummary monthly_summary_;
    std::vector<EconomyTransaction> ledger_;
};

[[nodiscard]] const char* economy_transaction_label(EconomyTransactionType type);
