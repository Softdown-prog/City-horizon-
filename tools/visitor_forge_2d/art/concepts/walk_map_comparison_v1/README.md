# Retomada da caminhada — EAST no mapa

Esta revisão compara os dois pares EAST existentes no mesmo recorte real do
MapForge, no tamanho de exibição de 56 px, com anchor `[64,116]`, câmera
`CH_CAMERA_V1` e deslocamento simulado de 0,30 tile/s. O painel PNG expõe seis
instantes; o GIF mostra a alternância A/B com 220 ms (Structural Gait V2) e
270 ms (Full Pose EAST). É uma composição de revisão, **não uma captura da
animação rodando no jogo**.

- `east_steps_on_map_56px.png`: contato e silhueta em seis instantes.
- `east_steps_on_map_56px.gif`: duas caminhadas lado a lado.
- `review.json`: hash da captura, escala, velocidade, cadências e contrato.

A captura vem do artefato `MapForge-Ice-Cream-Inactive-vs-Active`, ID
`10781869942`, no [workflow 35934307091](https://github.com/Softdown-prog/City-horizon-/actions/runs/35934307091).
Extraia `mapforge_ice_cream_inactive_vs_active.png` e execute:

```bash
python tools/visitor_forge_2d/art/concepts/walk_map_comparison_v1/render_review.py \
  --capture CAMINHO/mapforge_ice_cream_inactive_vs_active.png \
  --output tools/visitor_forge_2d/art/concepts/walk_map_comparison_v1
```

## Diagnóstico visual

O par Full Pose EAST troca o pé à frente e balança os braços de maneira mais
legível sem redesenhar rosto e roupa. O V2 preserva a identidade do tronco,
mas os braços ficam praticamente parados e o desenho das pernas muda pouco
na escala do mapa. Em NORTH a diferença A/B também permanece muito pequena no
painel `../directional_gait_candidate_v2/four_direction_structural_gait_56px.png`.

O próximo gate é andar no executável: desenhar seis ruas retas em +X, usar
F7 com o Full Pose EAST; F8 permite alternar para V2 e comparar no mesmo
trajeto. Confirmar contato dos pés, transição idle/A/B e eventual deslizamento.
NORTH/WEST exigem poses completas próprias com braços e pernas coordenados;
não basta aumentar os deslocamentos do warp estrutural. SOUTH frontal e os
assets já aprovados não foram alterados. Nenhum frame desta revisão foi
promovido a `assets/`.
