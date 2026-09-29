# CH Animation Preview / CH Video Lab

Ferramenta genérica de revisão visual para animações e testes do City Horizon.

Ela existe para permitir que agentes e workflows produzam sequências determinísticas de PNGs e artefatos de revisão (GIF, MP4 ou WebM) sem depender de screen scraping do desktop.

Os PNGs continuam sendo a evidência visual autoritativa de cada frame. GIF e vídeo são artefatos de revisão/validação; nunca substituem atlas, sprites, overlays ou metadata usados pelo runtime.

## Contratos

- `CH_ANIMATION_PREVIEW_V1` — PNGs -> GIF + contact sheet.
- `CH_VIDEO_PREVIEW_V1` — PNGs -> MP4/WebM + relatório `ffprobe`.
- `CH_FRAME_CAPTURE_SEQUENCE_V1` — orquestra um renderer autoritativo para produzir os PNGs e, opcionalmente, GIF/vídeo.

## Dependências

GIF:
- Python 3;
- Pillow.

Vídeo:
- Python 3;
- Pillow;
- `ffmpeg`;
- `ffprobe`.

O writer de vídeo nunca captura a tela diretamente. Ele recebe frames PNG já renderizados pelo MapForge, runtime, Blender ou outro produtor determinístico.

## 1. Montar GIF a partir de PNGs

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

A ferramenta usa uma paleta compartilhada entre os frames para reduzir cintilação de cores e produz também um JSON com hashes dos PNGs/GIF.

## 2. Montar MP4 ou WebM a partir de PNGs

Crie `video_preview_manifest.json`:

```json
{
  "contract": "CH_VIDEO_PREVIEW_V1",
  "id": "runtime.train.validation",
  "reviewOnly": true,
  "frameDir": "frames",
  "pattern": "frame_*.png",
  "fps": 30,
  "pingPong": false,
  "background": [24, 30, 36],
  "output": "train_validation.mp4"
}
```

Execute:

```bash
python tools/animation_preview/make_video.py --manifest CAMINHO/video_preview_manifest.json
```

Ou processe todos os manifests:

```bash
python tools/animation_preview/make_video.py --discover-root out
```

Saídas suportadas:

- `.mp4` — H.264 (`libx264`), `yuv420p`, indicado para revisão geral;
- `.webm` — VP9 (`libvpx-vp9`), `yuv420p`.

Regras V1:

- FPS permitido: 1–120;
- todos os frames precisam ter a mesma dimensão;
- alpha é composto sobre `background`;
- dimensões ímpares recebem padding de no máximo 1 px para compatibilidade com `yuv420p`;
- o frame não é reescalado;
- áudio ainda não é multiplexado nesta etapa;
- o relatório `<video>.<ext>.json` registra hash, FPS, duração, tamanho e metadata do `ffprobe`.

## 3. Capturar frames e gerar GIF + vídeo numa receita

`capture_sequence.py` aceita uma receita `CH_FRAME_CAPTURE_SEQUENCE_V1`. O comando pode apontar para MapForge, um executável do jogo com modo de captura, Blender ou outro renderer determinístico.

Placeholders:

- `{index}`
- `{index03}`
- `{output}`

Exemplo:

```json
{
  "contract": "CH_FRAME_CAPTURE_SEQUENCE_V1",
  "id": "runtime.train.validation",
  "reviewOnly": true,
  "frameCount": 120,
  "outputDir": "out/train_validation",
  "capture": {
    "cwd": "../../..",
    "command": [
      "CityHorizon.exe",
      "--validation-scene", "train",
      "--capture-frame", "{index}",
      "--output", "{output}"
    ]
  },
  "gif": {
    "durationMs": 80,
    "loop": 0,
    "pingPong": false,
    "background": [24, 30, 36],
    "output": "train_validation.gif",
    "contactSheet": "train_validation_contact_sheet.png"
  },
  "video": {
    "fps": 30,
    "pingPong": false,
    "background": [24, 30, 36],
    "output": "train_validation.mp4"
  }
}
```

Execute:

```bash
python tools/animation_preview/capture_sequence.py --recipe CAMINHO/capture_recipe.json
```

O diretório de saída terá, quando configurado:

```text
out/train_validation/
  frames/
    frame_000.png
    frame_001.png
    ...
  animation_preview_manifest.json
  train_validation.gif
  train_validation.json
  train_validation_contact_sheet.png
  video_preview_manifest.json
  train_validation.mp4
  train_validation.mp4.json
  capture_report.json
```

Compatibilidade:

- receitas antigas sem bloco `video` continuam gerando GIF como antes;
- use `"gif": false` para uma captura somente de vídeo;
- use `"video": false` ou omita `video` para não exigir FFmpeg.

## Fontes suportadas

O contrato de captura é propositalmente neutro. Pode ser usado para:

- caminhada de visitantes/personagens;
- trem/veículos em movimento;
- giro de roda-gigante;
- balanço de Barca Viking;
- overlays de luz, fumaça, vapor e clima;
- sequências produzidas pelo CH Blender;
- capturas determinísticas do MapForge/runtime quando o renderer expõe um comando por frame.

## Direção do CH Video Lab

A etapa atual resolve a camada de mídia: frames determinísticos -> GIF/MP4/WebM + relatórios.

A próxima camada deve ser o executor de cenários de validação no runtime/MapForge, para que uma receita de alto nível possa:

1. carregar um mapa de teste;
2. executar ações determinísticas;
3. posicionar câmera;
4. avançar a simulação por ticks;
5. exportar cada frame diretamente;
6. gerar o vídeo e o relatório de validação.

A IA pode escrever/orquestrar a receita, mas o vídeo de validação deve mostrar o renderer real do jogo. Não usar vídeo generativo para provar comportamento do runtime.

## Regras

- fontes PNG permanecem autoritativas;
- GIF/MP4/WebM são artefatos de revisão;
- manter câmera, asset root e iluminação do pipeline de origem;
- não usar screen scraping quando o renderer consegue exportar PNG diretamente;
- captura de revisão pode usar frames/ângulos temporários sem congelar FPS ou frame count do runtime;
- geração de vídeo não deve alterar assets de produção.
