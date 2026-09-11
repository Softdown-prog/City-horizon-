#include "building_system.h"
#include "economy_system.h"
#include "land_system.h"
#include "road_system.h"

#include <cstdint>
#include <iostream>
#include <string>

namespace {

bool require(const bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
    }
    return condition;
}

bool has_land_purchase(const CityEconomy& economy, const std::uint32_t parcel_id, const std::int64_t amount) {
    for (const EconomyTransaction& transaction : economy.ledger()) {
        if (transaction.type == EconomyTransactionType::land_purchase &&
            transaction.land_parcel_id == parcel_id && transaction.amount == amount) {
            return true;
        }
    }
    return false;
}

}  // namespace

int main(const int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: land_system_test <building-definition-directory>\n";
        return 2;
    }

    BuildingCatalog catalog;
    if (!catalog.load_from_directory(argv[1])) {
        std::cerr << "FAILED: catalog could not load\n";
        return 1;
    }
    const BuildingDefinition* cafe = catalog.find("cafe_01");
    const BuildingDefinition* house = catalog.find("house_suburban_01");
    if (!require(cafe != nullptr, "cafe definition exists") || !require(house != nullptr, "house definition exists")) {
        return 1;
    }

    LandManager lands(-24, 23);
    const LandParcel* initial = lands.parcel_at(0, 0);
    const LandParcel* east = lands.parcel_at(16, 0);
    const LandParcel* diagonal = lands.parcel_at(16, 16);
    if (!require(initial != nullptr && initial->owned &&
                 static_cast<std::int64_t>(initial->width) * initial->height >= 1'024,
                 "initial central parcel owns at least 1024 tiles") ||
        !require(lands.is_tile_owned(0, 0), "tile in initial parcel is owned") ||
        !require(!lands.is_tile_owned(16, 0), "tile outside initial parcel is not owned") ||
        !require(east != nullptr && !east->owned && east->purchase_cost == 5'000, "orthogonal neighboring parcel costs 5000") ||
        !require(diagonal != nullptr && !lands.can_purchase_parcel(diagonal->id), "diagonal parcel cannot be bought initially")) {
        return 1;
    }

    BuildingManager buildings(-24, 23);
    RoadManager roads(-24, 23);
    const bool building_allowed_on_owned_land = lands.is_area_owned(0, 0, cafe->footprint_width, cafe->footprint_height) &&
        buildings.validate(*cafe, 0, 0) == PlacementFailure::none;
    const bool road_allowed_on_owned_land = lands.is_tile_owned(0, 0) &&
        roads.validate_placement(0, 0, buildings) == RoadPlacementFailure::none;
    const bool building_allowed_on_unowned_land = lands.is_area_owned(16, 0, cafe->footprint_width, cafe->footprint_height) &&
        buildings.validate(*cafe, 16, 0) == PlacementFailure::none;
    const bool road_allowed_on_unowned_land = lands.is_tile_owned(16, 0) &&
        roads.validate_placement(16, 0, buildings) == RoadPlacementFailure::none;
    const bool house_allowed_on_owned_land = lands.is_area_owned(4, 4, house->footprint_width, house->footprint_height) &&
        buildings.validate(*house, 4, 4, BuildingRotation::r180) == PlacementFailure::none;
    const bool house_allowed_on_unowned_land = lands.is_area_owned(16, 4, house->footprint_width, house->footprint_height) &&
        buildings.validate(*house, 16, 4, BuildingRotation::r90) == PlacementFailure::none;
    if (!require(building_allowed_on_owned_land, "building placement is valid on the initial owned land") ||
        !require(road_allowed_on_owned_land, "road placement is valid on the initial owned land") ||
        !require(!building_allowed_on_unowned_land, "building placement is rejected on unowned land") ||
        !require(!road_allowed_on_unowned_land, "road placement is rejected on unowned land") ||
        !require(house_allowed_on_owned_land, "house placement is valid on owned land") ||
        !require(!house_allowed_on_unowned_land, "house placement is rejected on unowned land") ||
        !require(!lands.is_area_owned(15, 0, cafe->footprint_width, cafe->footprint_height),
                 "building footprint crossing into an unowned parcel is rejected")) {
        return 1;
    }

    CityEconomy economy;
    const GameDate date{1, 1, 1};
    if (!require(lands.can_purchase_parcel(east->id), "adjacent parcel is purchasable") ||
        !require(lands.purchase_parcel(east->id, economy, date), "adjacent purchase succeeds") ||
        !require(lands.is_tile_owned(16, 0), "purchased tile becomes owned") ||
        !require(economy.funds() == 45'000, "land cost is deducted exactly") ||
        !require(has_land_purchase(economy, east->id, -5'000), "ledger records land purchase") ||
        !require(!lands.purchase_parcel(east->id, economy, date), "same parcel cannot be purchased twice")) {
        return 1;
    }

    const bool building_allowed_after_purchase = lands.is_area_owned(16, 0, cafe->footprint_width, cafe->footprint_height) &&
        buildings.validate(*cafe, 16, 0) == PlacementFailure::none;
    const bool road_allowed_after_purchase = lands.is_tile_owned(16, 0) &&
        roads.validate_placement(16, 0, buildings) == RoadPlacementFailure::none;
    const bool house_allowed_after_purchase = lands.is_area_owned(16, 4, house->footprint_width, house->footprint_height) &&
        buildings.validate(*house, 16, 4, BuildingRotation::r90) == PlacementFailure::none;
    if (!require(building_allowed_after_purchase, "building placement becomes valid after purchase") ||
        !require(road_allowed_after_purchase, "road placement becomes valid after purchase")) {
        return 1;
    }
    if (!require(house_allowed_after_purchase, "house placement becomes valid after purchase")) {
        return 1;
    }

    LandManager poor_lands(-24, 23);
    const LandParcel* poor_target = poor_lands.parcel_at(16, 0);
    CityEconomy poor_economy(4'999);
    if (!require(poor_target != nullptr && !poor_lands.purchase_parcel(poor_target->id, poor_economy, date),
                 "insufficient funds reject land purchase") ||
        !require(poor_economy.funds() == 4'999, "failed purchase does not change funds") ||
        !require(poor_lands.owned_parcel_count() == 1, "failed purchase does not grant land")) {
        return 1;
    }

    std::cout << "land system tests passed\n";
    return 0;
}
