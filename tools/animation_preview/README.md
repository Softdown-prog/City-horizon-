# CH Animation Preview

Ferramenta genérica de revisão visual para animações do City Horizon.

Ela existe para permitir que agentes e workflows produzam uma sequência determinística de PNGs e um GIF de revisão sem precisar integrar a animação ao runtime para cada ajuste visual.

## O que já existia

O projeto já possui capturas estáticas determinísticas, por exemplo o `MapForge2MapCapture`, e o Visitor Forge já produz frames/strips de caminhada. Esses caminhos continuam válidos. Esta pasta adiciona a etapa genérica que faltava para transformar uma sequência em GIF e, quando necessário, orquestrar capturas sequenciais.

GIF é somente artefato de revisão. O jogo continua consumindo PNG/overlays/metadata próprios; nunca usar o GIF como asset de runtime.

## 1. Montar GIF a partir de PNGs já renderizados

Crie `animation_preview_manifest.json` ao lado dos frames:

```json
{
  "contract": "CH_ANIMATION_PREVIEW_V1",
  "id": "attraction.example.swing_review",
  "reviewOnly": true,
  "frameDir": "frames",
  "pattern": "frame_*.png",
  "durationMs": 90,
  "loop": 0,
  "pingPong": false,
  "background": [24, 30, 36],
  "output": "animation_preview.gif",
  "contactSheet": "animation_preview_contact_sheet.png"
}
```

Execute:

```bash
python tools/animation_preview/make_gif.py --manifest CAMINHO/animation_preview_manifest.json
```

Para processar todos os manifests dentro de um artifact/output:

```bash
python tools/animation_preview/make_gif.py --discover-root out
```

A ferramenta usa uma paleta compartilhada entre os frames para reduzir cintilação de cores no GIF e produz também um JSON com hashes dos PNGs/GIF.

## 2. Capturar frames sequencialmente

`capture_sequence.py` aceita uma receita `CH_FRAME_CAPTURE_SEQUENCE_V1`. O comando pode apontar para MapForge, um executável do jogo com modo de captura, Blender ou outro renderer determinístico. Os placeholders disponíveis são `{index}`, `{index03}` e `{output}`.

Exemplo:

```json
{
  "contract": "CH_FRAME_CAPTURE_SEQUENCE_V1",
  "id": "example.walk_review",
  "reviewOnly": true,
  "frameCount": 8,
  "outputDir": "out/example_walk",
  "capture": {
    "cwd": "../../..",
    "command": [
      "python",
      "tools/example_renderer.py",
      "--frame", "{index}",
      "--output", "{output}"
    ]
  },
  "gif": {
    "durationMs": 100,
    "loop": 0,
    "pingPong": false,
    "background": [24, 30, 36],
    "output": "walk_preview.gif",
    "contactSheet": "walk_contact_sheet.png"
  }
}
```

Execute:

```bash
python tools/animation_preview/capture_sequence.py --recipe CAMINHO/capture_recipe.json
```

## Fontes suportadas

O contrato é propositalmente neutro. Pode ser usado para:

- caminhada de visitantes/personagens do Visitor Forge;
- giro de roda-gigante;
- balanço de Barca Viking;
- overlays de luzes;
- sequências produzidas pelo CH Blender;
- capturas determinísticas do MapForge/runtime quando o renderer expõe um comando por frame.

## Regras

- fontes PNG permanecem autoritativas;
- GIF nunca substitui atlas/sprites/overlays de runtime;
- captura de revisão pode usar frames/ângulos temporários sem congelar FPS, arco ou frame count do runtime;
- manter câmera, asset root e iluminação do pipeline de origem;
- não usar screen scraping do desktop quando o renderer consegue exportar PNG diretamente;
- GIF com transparência usa fundo de revisão, evitando halos e limitações da transparência indexada do formato GIF.
