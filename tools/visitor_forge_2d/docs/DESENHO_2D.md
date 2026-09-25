# Desenho procedural 2D: peças pequenas e props

Este é o primeiro passo para criar arte 2D editável sem escrever código de
desenho a cada objeto. Leia `AGENTS.md` na raiz antes de trabalhar. O comando
`draw-recipe` recebe um JSON, renderiza cada camada em 4×, exporta PNG RGBA
com redução de alfa pré-multiplicado, metadados e um painel com escala 1×/2×.
O PNG é um **estudo**; conferir em tamanho real e no mapa antes de classificá-lo.

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d draw-recipe \
  --recipe tools/visitor_forge_2d/examples/park_wayfinding_sign.json \
  --output out/visitor_forge_2d/park_sign
```

Saídas: `park_wayfinding_sign_study.png`, `.json` de proveniência e
`park_wayfinding_sign_study_review.png` com o tamanho de jogo à esquerda.
Uma amostra desses dois PNGs também está em `examples/` para revisão sem
executar o comando. É um estudo, não um sprite classificado no jogo.
Abra a receita e troque `id`, `canvas`, `anchor`, camadas e cores para desenhar
outro objeto. Mantenha a receita no Git; arquivos em `out/` são descartáveis.

## Vocabulário da receita `CH_2D_SHAPE_RECIPE_V1`

```json
{
  "contract": "CH_2D_SHAPE_RECIPE_V1",
  "id": "my_prop_study",
  "canvas": [128, 128],
  "anchor": [64, 116],
  "layers": [{
    "name": "painted_panel",
    "fill": {"top": "#D7B075", "bottom": "#795A3B", "opacity": 1},
    "shapes": [{"type": "rounded_rect", "box": [15, 18, 102, 79], "radius": 4}],
    "shadow": {"offset": [2, 3], "blur": 2, "opacity": 0.4, "color": "#1E2630"}
  }]
}
```

Coordenadas de geometria e anchor estão **na escala do PNG final**, não nos
pixels de trabalho 4×. As camadas são desenhadas na ordem do JSON, da parte de
trás para a frente. `fill.top` é obrigatório; `bottom` iguala `top` por padrão;
cores têm formato `#RRGGBB`. Cada camada possui sua máscara e opcionalmente
sombra suave. `operation: "erase"` num shape corta somente a máscara da camada
atual, antes de aplicar material e sombra.

| Forma | Campos exigidos | Uso |
| --- | --- | --- |
| `polygon` | `points`: 3+ pares `[x,y]` | faces, setas, telhados simples |
| `ellipse` | `box`: `[x0,y0,x1,y1]` | copas, lâmpadas, sombras |
| `rounded_rect` | `box`, `radius` | placas, janelas, molduras |
| `line` | `points`: 2 pares, `width` | hastes, bordas |
| `quadratic` | `points`: 3 pares, `width` | cabos, ramos, curvas suaves |

Use o ponto de apoio real do objeto em `anchor`. Para direções de um objeto
isométrico, desenhe e revise receitas específicas mantendo a câmera e a luz
do projeto; esta ferramenta **não inventa a traseira ou gira a câmera** de
um desenho chapado. Não use a receita de props para substituir o pipeline de
tiles conectados, o Building Composer ou a renderização Blender quando essas
fontes já oferecem geometria/continuidade apropriada.

## Ferramentas seguintes que têm utilidade concreta

1. **Paletas compartilhadas e variantes com seed**: reutilizar materiais de
   uma família de props sem deriva de cores; tornar as variações repetíveis.
2. **Prévia sobre captura real de MapForge** e revisão de halo/anchor pelo
   Sprite Workshop existente: avaliar a leitura na rua e ao lado de prédios.
3. **Desenho de peças orgânicas com pincel/máscara e edição por camada**:
   cabelo, roupa e folhagem precisam de contornos que formas simples não dão.
4. **Linha do tempo de animação e comparação de poses**: reutilizar a mesma
   receita entre frames e flagrar deslizamento/juntas quando houver movimento.
5. **Validação de bordas para tiles conectados**: só junto ao pipeline de
   terreno atual, para detectar emendas antes de classificação.

Comece com um asset pequeno e um painel real antes de ampliar o vocabulário.
Comandos e métricas ajudam outro modelo a reproduzir o processo; não provam
que a arte ficou boa. Anote PNGs examinados, vista, escala e defeitos vistos.
