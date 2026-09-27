# Park fences — runtime

O City Park possui uma única rede lógica de cercas, mas pode apresentar mais de um estilo visual. Cercas não são `BuildingDefinition` comuns: vivem nas bordas/vértices do grid e usam `FenceManager` + `FencePlacementController` para manter conexão automática no estilo clássico de tycoon.

Na aba **PARK**, o jogador pode escolher atualmente:

- **Grade Classica do Parque** — `park_fence_classic_iron_v1`;
- **Grade de Ferro e Pedra** — `park_iron_fence_01`;
- **Portao Aberto do Parque** — ferramenta de portão compatível com os dois estilos.

A topologia lógica resolve automaticamente `end`, `straight`, `corner`, `tee` e `cross` conforme os vizinhos mudam. O preview usa a mesma topologia virtual antes do commit. O estilo visual é armazenado por segmento; portanto, cercas clássicas e cercas de ferro/pedra podem coexistir na mesma cidade sem trocar a aparência umas das outras.

## Portão aberto

A aba **PARK** oferece uma única ferramenta **Portao Aberto do Parque**. O jogador seleciona a ferramenta e clica sobre um trecho existente de qualquer estilo de cerca. O portão pertence ao segmento, não ao poste: visualmente o trecho abre no centro e, para navegação, aquela borda deixa de bloquear a passagem.

Cercas fechadas bloqueiam a travessia dos visitantes entre dois tiles. O wrapper `ParkFencePedestrianNavigationNetwork` mantém a topologia normal de ruas dos pedestres e apenas veta a travessia quando existe um segmento fechado naquela borda. Segmentos marcados como `open_gate` permanecem atravessáveis.

## Save / load

O estado runtime é compartilhado por `park_fence_runtime.h`. A rede é persistida junto ao mesmo slot da cidade por `ParkFenceSaveManager`, em um sidecar determinístico `<save>.park_fences`.

O formato atual é `CH_PARK_FENCE_V2`. Ele persiste:

- vértices da rede;
- orientação de fallback;
- estilo visual de cada segmento;
- segmentos de portão aberto.

Sidecars `CH_PARK_FENCE_V1` continuam válidos e são carregados como **Grade Classica do Parque**, preservando compatibilidade com cidades anteriores. Se o sidecar não existir, a cidade carrega normalmente com uma rede de cercas vazia.

## Apresentação runtime

O renderer runtime continua vetorial/procedural em SDL, agora com duas linguagens visuais selecionáveis por segmento. A Grade Clássica preserva o visual verde-escuro existente. A Grade de Ferro e Pedra usa metal carvão, barras verticais mais densas, postes mais robustos e mureta baixa de pedra, seguindo a família procedural promovida.

O card da Grade Clássica usa:

`assets/ui/thumbnails/buildings/park_fence_classic_iron_v1.png`

O card da Grade de Ferro e Pedra usa diretamente o módulo promovido:

`assets/city_park/fences/park_iron_fence_01/park_iron_fence_01_segment_east.png`

## Família procedural promovida: `park_iron_fence_01`

A referência visual aprovada foi reconstruída deterministicamente no Visitor Forge 2D pelo contrato `CH_2D_FENCE_SCENERY_V1` e está promovida para a biblioteca do jogo em:

`assets/city_park/fences/park_iron_fence_01/`

Arquivos runtime:

- `park_iron_fence_01_segment_east.png`
- `park_iron_fence_01_segment_south.png`
- `park_iron_fence_01_gate_east.png`
- `park_iron_fence_01_gate_south.png`
- `park_iron_fence_01_post.png`
- `park_iron_fence_01.json`

Os módulos usam canvas RGBA 192×128, anchor `[96,64]` e `CH_CAMERA_V1` (tile 128×64, yaw 45°, elevação 30°). NORTH/WEST reutilizam as mesmas arestas físicas a partir do endpoint oposto; cantos, tees e crosses continuam sendo compostos pela topologia existente, com um único poste no vértice compartilhado.

A fonte canônica continua em `tools/visitor_forge_2d/examples/park_iron_fence_01.json`. O manifesto promovido registra hashes dos PNGs e `runtimePromotion: true`.

A integração atual usa o PNG promovido no catálogo/preview e reproduz sua linguagem no renderer vetorial da cerca. A troca futura do desenho vetorial do mundo pelos próprios módulos PNG de alta fidelidade pode ser feita sem alterar `FenceManager`, navegação ou o contrato de estilos por segmento.
