# Caminhada EAST / NORTH / WEST — prévia V1

O mesmo visitante mantém os idles existentes de EAST, NORTH e WEST e o SOUTH
frontal aprovado em `../south_front_candidate_v1/`. Os seis PNGs daqui são
somente `walk_a` e `walk_b` das três vistas restantes. O catálogo F8 da prévia
usa esses PNGs; o catálogo normal e `frames_preview/` continuam intactos.

O recorte 2D não contém a parte escondida atrás das calças laterais: girar
as pernas em juntas separadas revelava uma borda reta. A receita de
`recipe.json` deforma suavemente apenas a parte inferior dos masters RGBA
originais de 512×512, com deslocamento distinto para os dois pés. Cabeça,
camisa, luz e sombra de contato ficam fixas. O render usa a mesma redução RGBA
com alfa pré-multiplicado do Visitor Forge e exporta 128×128 com anchor
`[64, 116]` e cadência de 220 ms por pose.

Regenerar e revisar:

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d render-directional-gait \
  --tool-root tools/visitor_forge_2d \
  --recipe tools/visitor_forge_2d/art/concepts/directional_gait_candidate_v1/recipe.json \
  --output out/visitor_forge_2d/directional_gait_review
```

O comando produz seis PNGs, `four_direction_gait_56px.png` e
`review_metrics.json`. O painel inclui as quatro direções em 56 px de altura
do corpo, com as colunas idle / A / B. Comparado com as versões anteriores,
as novas silhuetas mudam aproximadamente 9–11% em relação ao idle, e os três
frames de cada direção mantêm o pixel de pé mais baixo na linha 115.

**Gate pendente:** observar as quatro direções andando no motor, incluindo
transição entre parado e caminhada, contato do pé, direção do corpo na rota e
eventual deslizamento à velocidade escolhida. Os deslocamentos são passos
curtos: diferenças medidas e painel estático não garantem naturalidade em
movimento. Não promover esta prévia a `assets/` antes desse teste.
