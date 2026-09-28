# Autor de arte determinístico do Forge 2D

O comando `author-art` cria uma **receita nova** a partir de uma intenção curta,
renderiza o PNG no Forge existente e produz um relatório com as decisões.
Ele usa presets versionados e regras explícitas. Não executa um modelo de IA,
não aprende sozinho com imagens e não aprova a estética. Outro agente pode
operá-lo sem ter que adivinhar caminhos de arquivo ou parâmetros da câmera.

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d author-art \
  --id park_tree_early_autumn_study \
  --prompt 'árvore folhosa de outono, copa arredondada e densa' \
  --output out/visitor_forge_2d/author
```

Para reproduzir uma especificação sem ambiguidades, use um brief JSON:

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d author-art \
  --brief tools/visitor_forge_2d/examples/briefs/park_tree_early_autumn.json \
  --output out/visitor_forge_2d/author
```

O `CH_2D_ART_BRIEF_V1` aceita `id` seguro e `subject`. Campos específicos:

| Família | Receita de referência | Controles do autor |
| --- | --- | --- |
| `broadleaf` | `park_tree_broadleaf_early_autumn_v1.json` | `season`: `early_autumn`/`summer`; `silhouette`: `rounded`/`wide`/`tall`; `density`: `sparse`/`balanced`/`dense`; `seed` |
| `conifer` | `pine_small_v1.json` e variantes | `silhouette`: `rounded`/`wide`/`tall`; `density`; `seed` |
| `flower_bed` | `flower_bed_01.json` | `seed` |
| `sign` | `park_wayfinding_sign.json` | `seed` |
| `custom` | `template`: nome de outro JSON sob `examples/` | `seed`; `recipeUpdates` para parâmetros existentes |

O prompt curto reconhece o tema (árvore folhosa, pinheiro, canteiro, placa),
outono, copa arredondada/larga/alta e densidade rala/densa em português ou
inglês. Ele **não interpreta todas as palavras livres**. Use os campos JSON
para decisões precisas. `custom` permite que outro agente versiona uma nova
golden recipe e entregue edições explícitas como:

```json
{
  "contract": "CH_2D_ART_BRIEF_V1",
  "id": "my_tree_study",
  "subject": "custom",
  "template": "park_tree_broadleaf_early_autumn_v1.json",
  "recipeUpdates": {"broadleafStructure": {"masses": 52}}
}
```

`recipeUpdates` rejeita novos campos e protege
`contract`, `id`, `camera`, `rotation`, `canvas`, `anchor` e `finishRecipe`.
Caso a ferramenta não tenha uma primitive para a forma pedida, o agente deve
criar essa primitive e sua receita no módulo correto antes de usá-la.
Água/tiles conectados e construções com fonte Blender continuam em seus
pipelines canônicos; o router não inventa uma receita inadequada.

O resultado fica em `out/.../<id>/`: `authored_recipe.json`, PNG, prancha 1x/2x,
prancha da câmera (quando aplicável), `worker_report.json` e
`art_author_report.json`. Este último registra template, seed, interpretação
e uma crítica **mecânica** (por exemplo, falha de continuidade entre linhas
da copa). `review_ready` significa que o PNG está pronto para um artista
inspecionar no mapa em 1x; `artApproved` e `runtimePromotion` continuam falsos.

## Estudo da árvore outonal

`park_tree_broadleaf_early_autumn_v1.json` usa `broadleafStructure.layout =
"continuous"`. O renderer distribui grupos sobre uma copa única e pinta cada
grupo com luz local, sombra inferior e variação de oliva, amarelo e âmbar.
Isso evita que as quatro faixas da receita `organic_02` sejam fundidas em
prateleiras planas. As receitas antigas continuam usando seu desenho anterior.
A candidata deve ser comparada em 1x e na grade antes de qualquer promoção.
