# Park fences — runtime

A família `park_fence_classic_iron_v1` é a primeira cerca jogável do City Park.

Ela não é uma `BuildingDefinition` comum: cercas vivem nas bordas/vértices do grid e usam `FenceManager` + `FencePlacementController` para manter conexão automática no estilo clássico de tycoon. O jogador seleciona **Grade Clássica do Parque** na aba **PARK** e arrasta entre vértices do mapa.

A topologia lógica resolve automaticamente `end`, `straight`, `corner`, `tee` e `cross` conforme os vizinhos mudam. O preview usa a mesma topologia virtual antes do commit.

## Portão aberto

A aba **PARK** também oferece **Portão Aberto do Parque**. O jogador seleciona a ferramenta e clica sobre um trecho existente de cerca. O portão pertence ao segmento, não ao poste: visualmente o trecho abre no centro e, para navegação, aquela borda deixa de bloquear a passagem.

Cercas fechadas bloqueiam a travessia dos visitantes entre dois tiles. O wrapper `ParkFencePedestrianNavigationNetwork` mantém a topologia normal de ruas dos pedestres e apenas veta a travessia quando existe um segmento fechado naquela borda. Segmentos marcados como `open_gate` permanecem atravessáveis.

## Save / load

O estado runtime é compartilhado por `park_fence_runtime.h`. A rede é persistida junto ao mesmo slot da cidade por `ParkFenceSaveManager`, em um sidecar determinístico `<save>.park_fences`. Saves antigos continuam válidos: se o sidecar não existir, a cidade carrega normalmente com uma rede de cercas vazia.

São persistidos os vértices da rede, a orientação de fallback e todos os segmentos de portão aberto. Ao carregar, as conexões `end/straight/corner/tee/cross` são reconstruídas automaticamente pelo `FenceManager`.

## Apresentação

A apresentação runtime atual é vetorial/procedural em SDL e usa a mesma linguagem verde-escura do conceito aprovado. O renderer de revisão do MapForge2 continua sendo a fonte para os PNGs autorais de alta fidelidade (`C++/MapForge2/src/park_fence_renderer.*`); esses PNGs não precisam ser gerados por build/Action para usar a cerca no jogo.

Thumbnail do catálogo: `assets/ui/thumbnails/buildings/park_fence_classic_iron_v1.png`.
