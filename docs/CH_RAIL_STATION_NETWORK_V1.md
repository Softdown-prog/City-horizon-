# City Horizon — Rede de estações ferroviárias V1

As letras A/B identificavam apenas as pontas do antigo cenário de teste. **Não são tipos de estação**.

- Cada estação tem um `StationId` numérico, estável e não reutilizado, separado de seu nome visível.
- A estação é associada a um `RailPlacementPieceId` ativo; nomes podem ser alterados sem quebrar referências.
- Um `Service` registra uma lista ordenada de paradas (ex.: 1→2→3) e pode indicar repetição.
- Estações podem existir no meio de um trilho; não se obriga o jogador a terminar a linha ou criar um loop.
- `compile_station_network_route` reaproveita a compilação operacional existente, validando as paradas e recusando ordens que o percurso compilado não respeita.
- **Limite intencional:** a topologia atual ainda não resolve caminhos arbitrários entre estações por desvios. Este primeiro contrato não inventa conexão, não teletransporta trens, não inverte automaticamente uma locomotiva e não simula carga.
- Próxima integração: escolher explicitamente o trajeto por IDs de estações, reservar desvios, vincular `Service` aos trens, implementar logística/carga e persistir registro de estações. A lógica terminal A/B existente fica preservada enquanto isso.

Teste isolado: `c++ -std=c++20 -Isrc src/rail_station_network_test.cpp src/rail_system.cpp -o /tmp/rail_station_network_test && /tmp/rail_station_network_test` (requer toolchain C++20).
