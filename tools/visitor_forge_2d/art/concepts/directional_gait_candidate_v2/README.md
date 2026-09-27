# Caminhada estrutural EAST / NORTH / WEST — candidato V2

Este estudo preserva o candidato V1 e troca somente a forma de descrever o movimento.
Em vez de fornecer um deslocamento livre para cada pé, `recipe.json` declara uma
cadeia explícita `hip -> knee -> ankle` para cada perna e pose.

Contrato: `CH_VISITOR_STRUCTURAL_GAIT_V1`.

O renderer:

- mantém as linhas 0..279 do master 512x512 literalmente intactas;
- interpola a deformação da perna entre quadril, joelho e tornozelo;
- limita deslocamento de quadril, joelho e tornozelo;
- rejeita mudanças excessivas no comprimento aparente de coxa/canela;
- executa `CH_VISITOR_IDENTITY_LOCK_V1` depois do downscale;
- mantém anchor `[64, 116]` como referência da revisão;
- não promove nenhum PNG ao runtime.

Gerar a revisão:

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d render-directional-gait \
  --tool-root tools/visitor_forge_2d \
  --recipe tools/visitor_forge_2d/art/concepts/directional_gait_candidate_v2/recipe.json \
  --output out/visitor_forge_2d/directional_gait_v2_review
```

A saída deve incluir `east/north/west_walk_a.png`, `*_walk_b.png`,
`four_direction_structural_gait_56px.png` e `review_metrics.json`.

O workflow `.github/workflows/visitor-forge-structural-gait.yml` executa somente
os testes focados deste estudo, renderiza o mesmo painel e publica a pasta de
revisão como artifact. Ele não compila o City Horizon nem promove sprites.

## Gate visual obrigatório

Passar nos limites estruturais e no Identity Lock significa apenas que o frame
não quebrou as invariantes mecânicas. Antes de substituir qualquer preview V1,
inspecionar o painel em 56 px e caminhar no motor, conferindo abertura de perna,
contato do pé, ausência de arrasto, joelho natural e transição idle/A/B.

Se o V2 ainda parecer rígido ou anatômicamente errado, ajustar primeiro os alvos
de joelho/tornozelo da receita. Não aumentar os limites do validador apenas para
forçar um frame a passar.
