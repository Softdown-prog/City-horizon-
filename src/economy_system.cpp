#include "economy_system.h"

#include "population_system.h"
#include "vehicle_system.h"
#include "farming_system.h"

#include <algorithm>

CityEconomy::CityEconomy(const std::int64_t initial_funds)
    : funds_(initial_funds) {}

std::int64_t CityEconomy::funds() const {
    return funds_;
}

const MonthlyEconomySummary& CityEconomy::monthly_summary() const {
    return monthly_summary_;
}

const std::vector<EconomyTransaction>& CityEconomy::ledger() const {
    return ledger_;
}

bool CityEconomy::can_afford(const std::int64_t cost) const {
    return cost >= 0 && funds_ >= cost;
}

bool CityEconomy::try_spend(const std::int64_t cost) {
    if (!can_afford(cost)) {
        return false;
    }
    funds_ -= cost;
    return true;
}

bool CityEconomy::spend_for_building(const std::int64_t cost, const GameDate& date, const std::uint64_t building_instance_id) {
    if (!try_spend(cost)) {
        return false;
    }
    record(EconomyTransactionType::building_construction, -cost, date, building_instance_id);
    return true;
}

bool CityEconomy::spend_for_land(const std::int64_t cost, const GameDate& date, const std::uint32_t land_parcel_id) {
    if (!try_spend(cost)) {
        return false;
    }
    record(EconomyTransactionType::land_purchase, -cost, date, 0, land_parcel_id);
    return true;
}
void CityEconomy::earn_agricultural_sale(const std::int64_t amount, const GameDate& date) { if (amount <= 0) return; funds_ += amount; record(EconomyTransactionType::agricultural_sale, amount, date); }

void CityEconomy::restore_funds(const std::int64_t funds) {
    funds_ = funds;
    last_property_tax_year_ = 0;
    monthly_summary_ = {};
    ledger_.clear();
}

void CityEconomy::restore_last_property_tax_year(const int year) {
    last_property_tax_year_ = std::max(0, year);
}

int CityEconomy::last_property_tax_year() const {
    return last_property_tax_year_;
}

namespace {

[[nodiscard]] std::int64_t monthly_revenue_for(const BuildingDefinition& definition,
                                                const BuildingLevelDefinition& level_def,
                                                const PopulationSystem& population) {
    return level_def.tax_revenue_per_month *
        static_cast<std::int64_t>(CityEconomy::commercial_demand_percent(definition, population.current_population())) / 100;
}

[[nodiscard]] std::int64_t monthly_expense_for(const BuildingLevelDefinition& level_def) {
    return level_def.maintenance_per_month;
}

}  // namespace

std::uint32_t CityEconomy::commercial_demand_percent(const BuildingDefinition& definition,
                                                      const std::uint32_t current_population) {
    if (definition.required_population_for_full_revenue == 0) {
        return 100;
    }

    constexpr std::uint32_t kMinimumDemandPercent = 10;
    const std::uint64_t population_percent = static_cast<std::uint64_t>(current_population) * 100U /
        definition.required_population_for_full_revenue;
    return std::max(kMinimumDemandPercent, static_cast<std::uint32_t>(std::min<std::uint64_t>(100U, population_percent)));
}

void CityEconomy::rebuild_monthly_summary(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                          const PopulationSystem& population) {
    monthly_summary_ = {};
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const auto& level_def = instance.current_level_definition(*definition);
        monthly_summary_.revenue += monthly_revenue_for(*definition, level_def, population);
        monthly_summary_.expenses += monthly_expense_for(level_def);
    }
    monthly_summary_.balance = monthly_summary_.revenue - monthly_summary_.expenses;
}

void CityEconomy::on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                  const PopulationSystem& population, const GameDate& closing_date,
                                  const ServiceVehicleCatalog* vehicle_catalog, const ServiceVehicleManager* vehicles, FarmingSystem* farming) {
    monthly_summary_ = {};
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const auto& level_def = instance.current_level_definition(*definition);
        const std::int64_t revenue = monthly_revenue_for(*definition, level_def, population);
        monthly_summary_.revenue += revenue;
        const std::int64_t expense = monthly_expense_for(level_def);
        monthly_summary_.expenses += expense;
        if (revenue != 0) {
            record(EconomyTransactionType::tax_revenue, revenue, closing_date, instance.instance_id);
        }
        if (expense != 0) {
            record(EconomyTransactionType::maintenance, -expense, closing_date, instance.instance_id);
        }
        if (farming != nullptr && !definition->resource_inputs.empty()) {
            bool supplied = true;
            for (const BuildingResourceInput& input : definition->resource_inputs) {
                if (farming->inventory_count(input.resource_id) < input.amount_per_month) { supplied = false; break; }
            }
            if (supplied) {
                std::int64_t bonus = 0;
                for (const BuildingResourceInput& input : definition->resource_inputs) { (void)farming->try_remove_resource(input.resource_id, input.amount_per_month); bonus += input.local_supply_bonus; }
                monthly_summary_.revenue += bonus;
                if (bonus != 0) record(EconomyTransactionType::local_supply_bonus, bonus, closing_date, instance.instance_id);
            }
        }
    }
    if (vehicle_catalog != nullptr && vehicles != nullptr) {
        for (const ServiceVehicleInstance& vehicle : vehicles->instances()) {
            const ServiceVehicleDefinition* definition = vehicle_catalog->find(vehicle.vehicle_id);
            if (vehicle.owned && definition != nullptr) monthly_summary_.expenses += definition->monthly_maintenance;
        }
    }
    if (closing_date.month == 1 && closing_date.year > last_property_tax_year_) {
        for (const BuildingInstance& instance : buildings.instances()) {
            const BuildingDefinition* definition = catalog.find(instance.definition_id);
            if (definition == nullptr || definition->property_tax_per_year == 0) {
                continue;
            }
            monthly_summary_.revenue += definition->property_tax_per_year;
            record(EconomyTransactionType::property_tax, definition->property_tax_per_year, closing_date, instance.instance_id);
        }
        last_property_tax_year_ = closing_date.year;
    }
    monthly_summary_.balance = monthly_summary_.revenue - monthly_summary_.expenses;
    funds_ += monthly_summary_.balance;
    record(EconomyTransactionType::monthly_closure, monthly_summary_.balance, closing_date);
}

void CityEconomy::process_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                const PopulationSystem& population, const GameDate& closing_date,
                                const ServiceVehicleCatalog* vehicle_catalog, const ServiceVehicleManager* vehicles, FarmingSystem* farming) {
    on_month_closed(buildings, catalog, population, closing_date, vehicle_catalog, vehicles, farming);
}

void CityEconomy::record(const EconomyTransactionType type, const std::int64_t amount, const GameDate& date,
                         const std::uint64_t building_instance_id, const std::uint32_t land_parcel_id) {
    if (ledger_.size() == kMaxLedgerEntries) {
        ledger_.erase(ledger_.begin());
    }
    ledger_.push_back({type, amount, date, building_instance_id, land_parcel_id});
}

const char* economy_transaction_label(const EconomyTransactionType type) {
    switch (type) {
        case EconomyTransactionType::building_construction: return "BUILD";
        case EconomyTransactionType::land_purchase: return "LAND PURCHASE";
        case EconomyTransactionType::tax_revenue: return "TAX";
        case EconomyTransactionType::property_tax: return "IPTU";
        case EconomyTransactionType::maintenance: return "MAINTENANCE";
        case EconomyTransactionType::agricultural_sale: return "AGRICULTURAL SALE";
        case EconomyTransactionType::local_supply_bonus: return "LOCAL SUPPLY BONUS";
        case EconomyTransactionType::monthly_closure: return "MONTH CLOSE";
    }
    return "UNKNOWN";
}
