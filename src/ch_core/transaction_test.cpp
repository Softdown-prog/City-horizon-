#include "src/ch_core/transaction_manager.h"
#include <iostream>
#include <cassert>

void test_transaction_manager_basic() {
    ch::TransactionManager tm(10);
    assert(!tm.can_undo());
    assert(!tm.can_redo());

    ch::CommandRecord cmd1;
    cmd1.description = "Paint Grass Tile";
    cmd1.action_type = ch::TransactionActionType::paint_terrain;
    ch::TerrainStateSnapshot s1{5, 5, "sand", "grass"};
    cmd1.payloads.push_back(s1);

    tm.record_command(cmd1);

    assert(tm.can_undo());
    assert(!tm.can_redo());
    assert(tm.undo_stack_size() == 1);

    auto undo_cmd = tm.undo();
    assert(undo_cmd.has_value());
    assert(undo_cmd->description == "Paint Grass Tile");
    assert(!tm.can_undo());
    assert(tm.can_redo());

    auto redo_cmd = tm.redo();
    assert(redo_cmd.has_value());
    assert(redo_cmd->description == "Paint Grass Tile");
    assert(tm.can_undo());
    assert(!tm.can_redo());

    std::cout << "[PASS] test_transaction_manager_basic\n";
}

void test_transaction_manager_batch() {
    ch::TransactionManager tm(10);

    tm.begin_transaction("Batch Paint Coastline");
    assert(tm.is_in_batch());

    ch::CommandRecord cmd1;
    cmd1.description = "Tile 1";
    cmd1.payloads.push_back(ch::TerrainStateSnapshot{1, 1, "water", "sand"});
    tm.record_command(cmd1);

    ch::CommandRecord cmd2;
    cmd2.description = "Tile 2";
    cmd2.payloads.push_back(ch::TerrainStateSnapshot{1, 2, "water", "sand"});
    tm.record_command(cmd2);

    tm.commit_transaction();
    assert(!tm.is_in_batch());
    assert(tm.can_undo());
    assert(tm.undo_stack_size() == 1);

    auto undo_cmd = tm.undo();
    assert(undo_cmd.has_value());
    assert(undo_cmd->payloads.size() == 2);
    assert(undo_cmd->description == "Batch Paint Coastline");

    std::cout << "[PASS] test_transaction_manager_batch\n";
}

int main() {
    std::cout << "Running ch_core transaction manager tests...\n";
    test_transaction_manager_basic();
    test_transaction_manager_batch();
    std::cout << "All transaction manager tests passed successfully!\n";
    return 0;
}
