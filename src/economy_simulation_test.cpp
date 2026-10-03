#include "economy_system.h"

#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) std::cerr << "FAILED: " << description << '\n';
    return condition;
}

bool contains_transaction(const CityEconomy& economy, const EconomyTransactionType type) {
    for (const EconomyTransaction& transaction : economy.ledger()) {
        if (transaction.type == type) return true;
    }
    return false;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) return 1;

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "runtime catalog loads economic building data")) return 1;

    const BuildingDefinition* bakery = catalog.find("bakery_01");
    const BuildingDefinition* coffee = catalog.find("coffee_shop_01");
    if (!require(bakery != nullptr, "bakery definition exists") ||
        !require(coffee != nullptr, "coffee shop definition exists")) return 1;

    if (!require(bakery->build_cost == 2'500 && bakery->default_service_price.minor_units == 3 &&
                     bakery->base_service_customers_per_month == 120 &&
                     bakery->service_population_for_full_demand == 60,
                 "bakery economy comes from current JSON") ||
        !require(coffee->default_service_price.minor_units == 300 &&
                     coffee->default_service_price.units_per_dollar == 100 &&
                     coffee->minimum_service_price.minor_units == 50 &&
                     coffee->maximum_service_price.minor_units == 2000,
                 "coffee shop keeps cent-based CH_SERVICE_PRICE_V1 pricing")) return 1;

    BuildingInstance bakery_instance;
    bakery_instance.definition_id = bakery->id;
    bakery_instance.service_price = bakery->default_service_price;
    const ServicePricingEstimate bakery_default = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 2;
    const ServicePricingEstimate bakery_discount = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 5;
    const ServicePricingEstimate bakery_expensive = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 3;
    const ServicePricingEstimate bakery_half_population = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 30);

    if (!require(bakery_default.price_demand_percent == 100 && bakery_default.customers_per_month == 120 &&
                     bakery_default.revenue_per_month == 360,
                 "default bakery price produces reference demand and revenue") ||
        !require(bakery_discount.price_demand_percent == 120 && bakery_discount.customers_per_month == 144 &&
                     bakery_discount.revenue_per_month == 288,
                 "bakery discount increases customers while lowering revenue per customer") ||
        !require(bakery_expensive.price_demand_percent == 36 && bakery_expensive.customers_per_month == 43 &&
                     bakery_expensive.revenue_per_month == 215,
                 "high bakery price reduces demand") ||
        !require(bakery_half_population.population_demand_percent == 50 &&
                     bakery_half_population.customers_per_month == 60 && bakery_half_population.revenue_per_month == 180,
                 "service demand is capped by local population")) return 1;

    BuildingDefinition demand_fixture = *bakery;
    demand_fixture.required_population_for_full_revenue = 20;
    if (!require(CityEconomy::commercial_demand_percent(demand_fixture, 0) == 10,
                 "commercial demand has a ten-percent floor") ||
        !require(CityEconomy::commercial_demand_percent(demand_fixture, 5) == 25,
                 "commercial demand scales at low population") ||
        !require(CityEconomy::commercial_demand_percent(demand_fixture, 10) == 50,
                 "commercial demand scales at half population") ||
        !require(CityEconomy::commercial_demand_percent(demand_fixture, 20) == 100 &&
                     CityEconomy::commercial_demand_percent(demand_fixture, 21) == 100,
                 "commercial demand clamps at full population")) return 1;

    CityEconomy economy;
    if (!require(economy.funds() == 50'000, "economy starts with 50000") ||
        !require(economy.spend_for_building(bakery->build_cost, {1, 1, 1}, 1),
                 "runtime bakery construction is affordable") ||
        !require(economy.funds() == 47'500, "construction deducts its exact cost") ||
        !require(!economy.spend_for_building(50'000, {1, 1, 1}, 2),
                 "construction cannot create negative funds") ||
        !require(contains_transaction(economy, EconomyTransactionType::building_construction),
                 "ledger records construction")) return 1;

    SimulationClock clock(1.0);
    if (!require(clock.advance_seconds(0.9).days_advanced == 0,
                 "clock does not advance below one configured game day") ||
        !require(clock.advance_seconds(0.1).days_advanced == 1 && clock.date().day == 2,
                 "clock advances deterministically")) return 1;
    clock.set_speed(SimulationSpeed::paused);
    if (!require(clock.advance_seconds(100.0).days_advanced == 0 && clock.date().day == 2,
                 "pause freezes simulated time")) return 1;
    clock.set_speed(SimulationSpeed::speed2);
    if (!require(clock.advance_seconds(1.0).days_advanced == 4,
                 "speed 2 advances four game days per configured second")) return 1;
    clock.set_speed(SimulationSpeed::speed3);
    if (!require(clock.advance_seconds(1.0).days_advanced == 12,
                 "speed 3 advances twelve game days per configured second")) return 1;

    std::cout << "economy and simulation tests passed\n";
    return 0;
}
