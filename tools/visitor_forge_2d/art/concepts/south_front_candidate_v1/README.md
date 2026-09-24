# SOUTH frontal — candidato de revisão V1

Este estudo usa o mesmo visitante como referência e corrige somente a
orientação visual SOUTH. Não substitui `frames_preview/`, não altera EAST,
NORTH ou WEST e ainda não é arte aprovada.

- `south_front_master.png`: fonte RGBA de 512×512, derivada de uma revisão
  visual frontal e normalizada no canvas do Visitor Forge. Editar este master
  para qualquer retoque durável de rosto, cor ou juntas.
- `south_idle.png`, `south_walk_a.png`, `south_walk_b.png`: três frames
  exportados pelo rig de recorte 2D, em 128×128, com pés na linha 115 e
  anchor `[64,116]`. Caminhada curta; cada pose dura 220 ms.
- `south_old_vs_front_three_poses.png`: três frames existentes à esquerda,
  três candidatos frontais à direita, em escala nativa sobre fundo neutro.
- `south_old_vs_front_map_56px.png`: esquerda original, direita candidato,
  mesma captura de MapForge, mesmo ponto dos pés e corpo exibido a 56 px.

Para reconstruir os três frames após retocar o master:

```bash
ch-visitor-forge-2d build-concept-rig \
  --master tools/visitor_forge_2d/art/concepts/south_front_candidate_v1/south_front_master.png \
  --direction south \
  --asset-root out/visitor_forge_2d/south_front/parts \
  --definition-output out/visitor_forge_2d/south_front/definition.json

ch-visitor-forge-2d prototype \
  --definition out/visitor_forge_2d/south_front/definition.json \
  --pose tools/visitor_forge_2d/poses/concept/south_idle.json \
  --pose tools/visitor_forge_2d/poses/concept/south_walk_a.json \
  --pose tools/visitor_forge_2d/poses/concept/south_walk_b.json \
  --asset-root out/visitor_forge_2d/south_front/parts \
  --output out/visitor_forge_2d/south_front/frames
```

A opção local `CH_VISITOR_FORGE_PREVIEW=ON` inclui este estudo como quinta
aparência F8, depois da prévia atual do Visitor Forge. Para realmente ver
SOUTH andando, marque início com F3 e destino numa rua ao longo de +Y com
F4; F6 envia o visitante pelo caminho. F7 sempre usa seis tiles ao longo
de +X e portanto mostra EAST. A trajetória SOUTH aparece diagonal na tela
isométrica; a correção aqui é a direção **do corpo**, não a projeção do mapa.

**Gate visual:** comparar rosto, cabelo, calça e sapatos com o visitante
aprovado; observar juntas, transparência, contato dos pés e mudança de
direção durante a caminhada. Este candidato pode precisar de retoque e não
deve substituir o SOUTH original sem aprovação visual.
