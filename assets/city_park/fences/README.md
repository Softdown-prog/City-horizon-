# Park fences — runtime

A família `park_fence_classic_iron_v1` é a primeira cerca jogável do City Park.

Ela não é uma `BuildingDefinition` comum: cercas vivem nas bordas/vértices do grid e usam `FenceManager` + `FencePlacementController` para manter conexão automática no estilo clássico de tycoon. O jogador seleciona **Grade Clássica do Parque** na aba **PARK** e arrasta entre vértices do mapa.

A topologia lógica resolve automaticamente `end`, `straight`, `corner`, `tee` e `cross` conforme os vizinhos mudam. O preview usa a mesma topologia virtual antes do commit. O protótipo de portão aberto continua suportado pelo `FenceManager`, mas ainda não tem um card separado no catálogo do jogador.

A apresentação runtime atual é vetorial/procedural em SDL e usa a mesma linguagem verde-escura do conceito aprovado. O renderer de revisão do MapForge2 continua sendo a fonte para os PNGs autorais de alta fidelidade (`C++/MapForge2/src/park_fence_renderer.*`); esses PNGs não são necessários para o primeiro encaixe jogável e não devem ser gerados por build/Action apenas para abrir o catálogo.

Thumbnail do catálogo: `assets/ui/thumbnails/buildings/park_fence_classic_iron_v1.png`.

Pendências fora deste encaixe inicial: serialização das cercas no save, ferramenta dedicada de portão aberto e integração de barreira com navegação de visitantes.
