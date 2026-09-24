# City Horizon — Tile Pipeline

Esta pasta é a entrada canônica para agentes que trabalham com **tiles de chão/caminhos**. Não é necessário vasculhar todas as ferramentas do repositório antes de produzir um tile.

## Contrato do jogo

Para caminhos atômicos atuais:

- PNG RGBA
- 128 x 64 px
- losango isométrico 2:1
- alpha fora do losango
- sem halo, borda decorativa, bevel, pixels pretos/coloridos ou resíduos da imagem-fonte
- interior da textura deve permanecer visualmente estável
- conexões N/E/S/W usam família de 16 máscaras

A autoridade geométrica é `assets/terrain/ground_tile_contract.json`, perfil `atomic-path`.

## Pipeline oficial

1. **Fonte artística** — começar por uma textura/imagem visualmente boa. Não usar procedural para inventar a arte do material por padrão.
2. **Normalização** — produzir o losango 128x64 RGBA.
3. **Limpeza de borda** — preencher RGB transparente antes de copiar amostras para a borda, remover bevel/rim e contaminação somente no perímetro. Nunca espalhar correção para o centro.
4. **Seam** — igualar apenas amostras que realmente se encontram nas bordas opostas. Não difundir cores da borda para o interior.
5. **Autotile** — gerar as 16 máscaras N/E/S/W a partir do tile-base limpo.
6. **Gates** — validar contrato geométrico, pixels escuros indevidos e as 16 máscaras, inclusive pares de bordas com conectores compatíveis.
7. **Preview visual** — verificar reta, curva, cruzamento, repetição e tile isolado. Gate técnico aprovado NÃO equivale a aprovação artística.
8. **Runtime** — publicar PNGs apenas após aprovação do preview visual. Os workflows de geração armazenam candidatos como artefatos e nunca fazem commit dos tiles.

## Problemas já aprendidos

### Linhas verdes entre tiles
Não esconder aumentando o sprite. Verificar alpha, diamond mask, alinhamento 128x64 e igualdade das bordas que se encontram.

### Mancha radial / efeito de estrela
Foi causado por correções de borda difundidas para o interior. É proibido usar centre-pull ou harmonização que pinte vários pixels em direção ao centro.

### Pontas pretas/vermelhas/coloridas
São contaminação da fonte ou de amostragem de borda. A limpeza deve detectar outliers somente na faixa externa e substituí-los por textura válida encontrada mais para dentro da mesma região.
Em especial, copiar RGB de pixels transparentes pretos e só depois tornar a borda opaca cria pontos pretos mesmo quando a fonte parecia correta.

### Emendas entre máscaras
O erro da borda de um tile isolado não comprova continuidade da família. Comparar todas as duplas de lados que podem encostar com o mesmo estado de conexão e rejeitar diferença de cor excessiva. Em cada par, comparar RGB apenas onde os dois pixels são opacos: o contorno rasterizado pode deslocar um pixel entre lados opostos.

### Repetição artificial
Não resolver deformando o tile. Preservar a textura-base; variantes artísticas podem ser adicionadas depois.

## Ferramentas canônicas atuais

As implementações históricas ainda podem estar em `tools/` por compatibilidade com workflows existentes. Antes de mover código, atualizar todos os imports/workflows no mesmo commit para não quebrar CI.

- `tools/ground_tile_worker.py` — preparação, limpeza, seam e preview repetido.
- `tools/tile_geometry.py` — máscara de losango compartilhada por normalização, worker, geradores e gate.
- `tools/normalize_atomic_path_tile.py` — normalização do caminho atômico.
- `tools/generate_sand_paths.py` — gerador da família de areia; serve como referência para materiais futuros.
- `tools/validate_ground_tiles.py` — gate do contrato geométrico.
- `tools/validate_path_tiles.py` — gate das 16 máscaras, pixels escuros e emendas compatíveis.
- `tools/extract_ground_tile_sheet.py` — extração de sheets de terreno.
- `assets/terrain/ground_tile_contract.json` — contrato canônico.

## Regra para agentes

Ao receber tarefa de tile, **ler este README primeiro**. Não criar outro normalizador, seam fixer ou gerador específico antes de verificar se o worker existente cobre o caso. Se surgir um defeito recorrente, corrigir a ferramenta reutilizável e documentar a causa aqui.

Não alterar Blender/building pipeline para corrigir tiles. Tiles e buildings são domínios separados.

## Estrutura alvo

```text
tools/
  tiles/       # pipeline de tiles
  buildings/   # pipeline de buildings
  audio/       # pipeline de áudio
  sprites/     # pipeline de sprites/personagens
```

A migração física dos scripts existentes deve ser incremental: documentação/entrada primeiro, depois mover scripts por domínio atualizando imports e workflows juntos. Isso evita quebrar Actions que já estão em produção.
