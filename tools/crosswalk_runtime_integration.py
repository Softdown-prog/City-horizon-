from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old!r}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/building_system.h",
    "    [[nodiscard]] bool restore_ticket_link(std::uint64_t booth_instance_id, std::uint64_t attraction_instance_id);\n",
    "    [[nodiscard]] bool restore_ticket_link(std::uint64_t booth_instance_id, std::uint64_t attraction_instance_id);\n    void unlink_ticket_booth(std::uint64_t booth_instance_id);\n",
)

replace_once(
    "src/economy_system.h",
    "    building_construction,\n    land_purchase,\n",
    "    building_construction,\n    building_upgrade,\n    land_purchase,\n",
)
replace_once(
    "src/economy_system.h",
    "    [[nodiscard]] bool spend_for_building(std::int64_t cost, const GameDate& date, std::uint64_t building_instance_id);\n",
    "    [[nodiscard]] bool spend_for_building(std::int64_t cost, const GameDate& date, std::uint64_t building_instance_id);\n    [[nodiscard]] bool spend_for_upgrade(std::int64_t cost, const GameDate& date, std::uint64_t building_instance_id);\n",
)

replace_once(
    "src/economy_system.cpp",
    """bool CityEconomy::spend_for_land(const std::int64_t cost, const GameDate& date, const std::uint32_t land_parcel_id) {
""",
    """bool CityEconomy::spend_for_upgrade(const std::int64_t cost, const GameDate& date,
                                           const std::uint64_t building_instance_id) {
    if (!try_spend(cost)) {
        return false;
    }
    record(EconomyTransactionType::building_upgrade, -cost, date, building_instance_id);
    return true;
}

bool CityEconomy::spend_for_land(const std::int64_t cost, const GameDate& date, const std::uint32_t land_parcel_id) {
""",
)
replace_once(
    "src/economy_system.cpp",
    "        case EconomyTransactionType::building_construction: return \"BUILD\";\n",
    "        case EconomyTransactionType::building_construction: return \"BUILD\";\n        case EconomyTransactionType::building_upgrade: return \"UPGRADE\";\n",
)

print("focused build contract repair applied")
