#include "economy_system.h"

#include "population_system.h"
#include "vehicle_system.h"
#include "farming_system.h"

#include <algorithm>
#include <string_view>
#include <unordered_set>

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

constexpr std::string_view kParkTicketBoothId = "park_ticket_booth_01";
constexpr int kParkTicketBoothLinkRangeTiles = 1;

[[nodiscard]] bool is_park_ticket_booth(const BuildingDefinition& definition) {
    return definition.id == kParkTicketBoothId;
}

[[nodiscard]] bool is_ticketed_park_attraction(const BuildingDefinition& definition) {
    return !is_park_ticket_booth(definition) && definition.category == "service" &&
        definition.default_service_price > 0 &&
        definition.texture_path.find("assets/city_park/") != std::string::npos;
}

[[nodiscard]] int footprint_axis_gap(const int a_start, const int a_size,
                                     const int b_start, const int b_size) {
    const int a_end = a_start + a_size;
    const int b_end = b_start + b_size;
    if (a_end <= b_start) return b_start - a_end;
    if (b_end <= a_start) return a_start - b_end;
    return 0;
}

[[nodiscard]] int footprint_gap(const BuildingInstance& a, const BuildingDefinition& a_definition,
                                const BuildingInstance& b, const BuildingDefinition& b_definition) {
    const BuildingFootprint a_footprint = rotated_footprint(a_definition, a.rotation);
    const BuildingFootprint b_footprint = rotated_footprint(b_definition, b.rotation);
    return footprint_axis_gap(a.tile_x, a_footprint.width, b.tile_x, b_footprint.width) +
           footprint_axis_gap(a.tile_y, a_footprint.height, b.tile_y, b_footprint.height);
}

struct ParkTicketTarget {
    const BuildingInstance* instance = nullptr;
    const BuildingDefinition* definition = nullptr;
    int distance = 0;
};

[[nodiscard]] ParkTicketTarget nearest_ticketed_park_attraction(const BuildingInstance& booth,
                                                                 const BuildingDefinition& booth_definition,
                                                                 const BuildingManager& buildings,
                                                                 const BuildingCatalog& catalog) {
    ParkTicketTarget best;
    bool found = false;
    for (const BuildingInstance& candidate : buildings.instances()) {
        if (candidate.instance_id == booth.instance_id) continue;
        const BuildingDefinition* candidate_definition = catalog.find(candidate.definition_id);
        if (candidate_definition == nullptr || !is_ticketed_park_attraction(*candidate_definition)) continue;

        const int distance = footprint_gap(booth, booth_definition, candidate, *candidate_definition);
        if (distance > kParkTicketBoothLinkRangeTiles) continue;
        if (!found || distance < best.distance ||
            (distance == best.distance && candidate.instance_id < best.instance->instance_id)) {
            best = {&candidate, candidate_definition, distance};
            found = true;
        }
    }
    return best;
}

// A park ticket booth is the authoritative price control for the nearest
// ticketed City Park attraction. The visual footprint is used for proximity so
// the booth can sit beside the ride entrance/stairs even when a large sprite
// uses a smaller physical occupancy footprint. One empty tile of separation is
// tolerated. If multiple booths resolve to the same ride, the earliest placed
// booth is authoritative and later booths mirror that ride price.
void synchronize_park_ticket_booth_prices(BuildingManager& buildings, const BuildingCatalog& catalog) {
    std::unordered_set<std::uint64_t> claimed_attractions;
    for (const BuildingInstance& booth_snapshot : buildings.instances()) {
        const BuildingDefinition* booth_definition = catalog.find(booth_snapshot.definition_id);
        if (booth_definition == nullptr || !is_park_ticket_booth(*booth_definition)) continue;

        const ParkTicketTarget target = nearest_ticketed_park_attraction(
            booth_snapshot, *booth_definition, buildings, catalog);
        if (target.instance == nullptr || target.definition == nullptr) continue;

        const BuildingInstance* current_target = buildings.find_by_id(target.instance->instance_id);
        if (current_target == nullptr) continue;
        if (claimed_attractions.contains(target.instance->instance_id)) {
            (void)buildings.set_service_price(
                booth_snapshot.instance_id, *booth_definition, current_target->service_price);
            continue;
        }
        claimed_attractions.insert(target.instance->instance_id);

        const std::int64_t desired_price = booth_snapshot.service_price > 0
            ? static_cast<std::int64_t>(booth_snapshot.service_price)
            : static_cast<std::int64_t>(current_target->service_price);
        if (desired_price <= 0) continue;

        (void)buildings.set_service_price(
            target.instance->instance_id, *target.definition, desired_price);
        current_target = buildings.find_by_id(target.instance->instance_id);
        if (current_target != nullptr) {
            (void)buildings.set_service_price(
                booth_snapshot.instance_id, *booth_definition, current_target->service_price);
        }
    }
}

[[nodiscard]] std::int64_t monthly_tax_revenue_for(const BuildingDefinition& definition,
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

std::uint32_t CityEconomy::service_price_demand_percent(const BuildingDefinition& definition,
                                                         const std::int64_t service_price) {
    if (definition.default_service_price <= 0 || service_price <= 0) return 0;
    const std::int64_t minimum = definition.minimum_service_price;
    const std::int64_t maximum = definition.maximum_service_price;
    const std::int64_t price = std::clamp(service_price, minimum, maximum);
    const std::int64_t reference = definition.default_service_price;
    const std::int64_t units_per_dollar = std::max<std::int64_t>(1, definition.default_service_price.units_per_dollar);
    if (price <= reference) {
        // The original curve awards +20 demand points per $1 discount. Scale
        // the price delta back to dollars so cent-based products keep the same
        // elasticity instead of treating a 25-cent change like $25.
        const std::int64_t bonus = (reference - price) * 20 / units_per_dollar;
        return static_cast<std::uint32_t>(std::clamp<std::int64_t>(100 + bonus, 0, 160));
    }

    // Above the reference price demand follows an inverse-square curve. The
    // ratio is unitless, so it works identically for dollars and cents.
    const std::uint64_t numerator = static_cast<std::uint64_t>(reference) *
                                    static_cast<std::uint64_t>(reference) * 100U;
    const std::uint64_t denominator = static_cast<std::uint64_t>(price) *
                                      static_cast<std::uint64_t>(price);
    return std::max<std::uint32_t>(5U, static_cast<std::uint32_t>(numerator / denominator));
}

ServicePricingEstimate CityEconomy::service_pricing_estimate(const BuildingDefinition& definition,
                                                              const BuildingInstance& instance,
                                                              const std::uint32_t current_population,
                                                              const FarmingSystem* farming) {
    ServicePricingEstimate estimate;
    if (definition.default_service_price <= 0) {
        return estimate;
    }

    const std::int64_t minimum = definition.minimum_service_price;
    const std::int64_t maximum = definition.maximum_service_price;
    const std::int64_t requested_price = instance.service_price > 0
        ? static_cast<std::int64_t>(instance.service_price)
        : static_cast<std::int64_t>(definition.default_service_price);
    const std::int64_t price = std::clamp(requested_price, minimum, maximum);
    estimate.price_demand_percent = service_price_demand_percent(definition, price);

    // A shop may expose its player-controlled price before customer-volume
    // balancing is configured. In that state the UI still shows price demand,
    // while customer count and revenue remain zero rather than inventing data.
    if (definition.base_service_customers_per_month == 0 ||
        definition.service_population_for_full_demand == 0) {
        return estimate;
    }

    estimate.population_demand_percent = static_cast<std::uint32_t>(std::min<std::uint64_t>(
        100U, static_cast<std::uint64_t>(current_population) * 100U /
                  definition.service_population_for_full_demand));
    estimate.customers_before_supply = static_cast<std::uint32_t>(
        static_cast<std::uint64_t>(definition.base_service_customers_per_month) *
        estimate.price_demand_percent * estimate.population_demand_percent / 10'000U);
    // Commerce demand is intentionally independent from farming stock. Crops are
    // an agricultural production-and-sale loop, not ingredients required by shops.
    estimate.supply_percent = 100;
    estimate.customers_per_month = estimate.customers_before_supply;
    const std::int64_t units_per_dollar = std::max<std::int64_t>(1, definition.default_service_price.units_per_dollar);
    estimate.revenue_per_month = static_cast<std::int64_t>(estimate.customers_per_month) * price / units_per_dollar;
    (void)farming;
    return estimate;
}

void CityEconomy::rebuild_monthly_summary(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                          const PopulationSystem& population, const FarmingSystem* farming) {
    // Pricing is normally a pure economy read. Park booths are the exception:
    // changing a booth price in the existing building panel must immediately
    // update the nearby ride before the summary is recomputed.
    synchronize_park_ticket_booth_prices(const_cast<BuildingManager&>(buildings), catalog);
    monthly_summary_ = {};
    (void)farming;
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const auto& level_def = instance.current_level_definition(*definition);
        monthly_summary_.revenue += monthly_tax_revenue_for(*definition, level_def, population);
        if (!is_park_ticket_booth(*definition)) {
            const ServicePricingEstimate service = service_pricing_estimate(
                *definition, instance, population.current_population());
            monthly_summary_.revenue += service.revenue_per_month;
        }
        monthly_summary_.expenses += monthly_expense_for(level_def);
    }
    monthly_summary_.balance = monthly_summary_.revenue - monthly_summary_.expenses;
}

void CityEconomy::on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                  const PopulationSystem& population, const GameDate& closing_date,
                                  const ServiceVehicleCatalog* vehicle_catalog, const ServiceVehicleManager* vehicles, FarmingSystem* farming) {
    synchronize_park_ticket_booth_prices(const_cast<BuildingManager&>(buildings), catalog);
    monthly_summary_ = {};
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const auto& level_def = instance.current_level_definition(*definition);
        const std::int64_t tax_revenue = monthly_tax_revenue_for(*definition, level_def, population);
        ServicePricingEstimate service;
        if (!is_park_ticket_booth(*definition)) {
            service = service_pricing_estimate(
                *definition, instance, population.current_population(), farming);
        }
        monthly_summary_.revenue += tax_revenue + service.revenue_per_month;
        const std::int64_t expense = monthly_expense_for(level_def);
        monthly_summary_.expenses += expense;
        if (tax_revenue != 0) {
            record(EconomyTransactionType::tax_revenue, tax_revenue, closing_date, instance.instance_id);
        }
        if (service.revenue_per_month != 0) {
            record(EconomyTransactionType::service_revenue, service.revenue_per_month, closing_date, instance.instance_id);
        }
        if (expense != 0) {
            record(EconomyTransactionType::maintenance, -expense, closing_date, instance.instance_id);
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
        case EconomyTransactionType::service_revenue: return "SERVICE SALES";
        case EconomyTransactionType::property_tax: return "IPTU";
        case EconomyTransactionType::maintenance: return "MAINTENANCE";
        case EconomyTransactionType::agricultural_sale: return "AGRICULTURAL SALE";
        case EconomyTransactionType::local_supply_bonus: return "LOCAL SUPPLY BONUS";
        case EconomyTransactionType::monthly_closure: return "MONTH CLOSE";
    }
    return "UNKNOWN";
}
