# Workers do Visitor Forge 2D

`run-workers` executa cinco tarefas pequenas sobre **uma receita existente**:

1. **Receita** — confere ID seguro, canvas, pivô e o contrato da câmera quando há cenário orgânico.
2. **Render** — chama o renderizador original de shape, árvore ou canteiro; não redesenha o asset.
3. **Alpha/pivô** — abre o PNG real, verifica RGBA, dimensões, pixels visíveis, limites de altura e metadados.
4. **Câmera** — exige a prancha isométrica `CH_CAMERA_V1` para cenário orgânico. Shape simples não recebe câmera inventada.
5. **Proveniência** — registra SHA-256 da receita e do PNG em `worker_report.json`.

Exemplo local:

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d run-workers \
  --recipe tools/visitor_forge_2d/examples/pine_small_v1.json \
  --output out/visitor_forge_2d/workers
```

A saída fica em `out/visitor_forge_2d/workers/pine_small_v1/`, separada por ID,
com PNG, review 1x/2x, prancha de câmera (quando aplicável), metadados e
`worker_report.json`. A conclusão é `review_ready`: métricas e CI não aprovam
arte nem promovem um PNG para `assets/`.

O workflow `Visitor Forge 2D Workers` usa uma matriz de seis receitas: quatro
pinheiros, canteiro e placa. Cada item roda em um worker paralelo do GitHub
Actions com artefato independente. Para ampliar a lista, inclua uma receita
versionada em `examples/` e seu nome na matriz; mantenha o gate visual em 1x
e na grade antes de qualquer integração no jogo.
O workflow antigo de pinheiros permanece disponível manualmente, sem duplicar
as renderizações em cada push.

São workers determinísticos da ferramenta, sem serviços de IA, credenciais ou
gerações de imagem externas. A decisão artística continua com a revisão humana.
