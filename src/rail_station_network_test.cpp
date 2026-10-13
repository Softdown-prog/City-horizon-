#include "rail_station_network.h"
#include <cassert>
#include <string>
int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0,0,0},0);
    assert(root);
    auto a = graph.append_straight(*root, 8.0f);
    assert(a);
    auto b = graph.append_straight(a->node, 8.0f);
    assert(b);
    auto c = graph.append_straight(b->node, 8.0f);
    assert(c);
    ch::rail_network::StationRegistry stations;
    auto id1 = stations.add(graph, a->edge);
    auto id2 = stations.add(graph, b->edge, "Carga");
    auto id3 = stations.add(graph, c->edge);
    assert(id1 && id2 && id3 && *id1 != *id2 && *id2 != *id3);
    assert(stations.find(*id1)->name == "Estação 1");
    assert(stations.rename(*id2, "Terminal Norte"));
    assert(stations.find(*id2)->name == "Terminal Norte");
    assert(!stations.add(graph, b->edge));
    assert(stations.validate_service(graph, {1, {*id1,*id2,*id3}, false}));
    assert(stations.validate_service(graph, {2, {*id1,*id2,*id1}, false}));
    assert(!stations.validate_service(graph, {3, {*id1,*id2,*id2}, false}));
    assert(!stations.validate_service(graph, {4, {*id1,999}, false}));
    assert(stations.erase(*id2));
    assert(!stations.validate_service(graph, {1, {*id1,*id2,*id3}, false}));
    auto replacement = stations.add(graph, b->edge);
    assert(replacement && *replacement > *id3);
    return 0;
}
