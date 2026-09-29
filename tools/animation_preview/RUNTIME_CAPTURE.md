# CH Runtime Video Capture V1

Este documento cobre a ponte entre o runtime real do City Horizon e o CH Video Lab.

## Objetivo

O vídeo de validação deve mostrar frames realmente renderizados pelo `city_builder`. O runtime roda uma única sessão, avança com tempo fixo e grava PNGs antes de `SDL_RenderPresent`. Depois, o CH Video Lab monta GIF/MP4/WebM a partir desses PNGs.

Contratos:

- `CH_RUNTIME_FRAME_CAPTURE_V1` — relatório produzido pelo executável do jogo.
- `CH_RUNTIME_VIDEO_JOB_V1` — job Python que executa o runtime e monta os artefatos de revisão.

## Flags do runtime

```text
--validation-capture-dir DIR
--validation-frames N
--validation-fps FPS
--validation-hide-ui
--validation-show-ui
--validation-paused
--validation-weather sunny|overcast|rain|thunderstorm
```

Quando `--validation-capture-dir` não é informado, o jogo mantém o comportamento interativo normal.

No modo de captura:

- a janela SDL é criada oculta;
- VSync é desligado;
- teclado é neutralizado;
- mouse fica logicamente no centro para impedir edge-pan;
- `SDL_GetTicks` usa uma timeline determinística derivada de FPS/frame;
- por padrão a simulação é forçada para `speed1`;
- `--validation-paused` preserva captura pausada;
- o clima inicial pode ser escolhido;
- cada framebuffer é lido depois do render e antes do `SDL_RenderPresent`;
- os PNGs são `frame_000000.png`, `frame_000001.png`, etc.;
- ao completar N frames, o runtime escreve `runtime_capture_report.json` e encerra a sessão por evento SDL quit.

## Captura direta

Exemplo:

```powershell
build\Release\city_builder.exe `
  --validation-capture-dir out\runtime_frames `
  --validation-frames 150 `
  --validation-fps 30 `
  --validation-hide-ui `
  --validation-weather rain
```

Isso gera 5 segundos determinísticos de frames reais do jogo.

## Captura + MP4/GIF

Use `capture_runtime_video.py` com um job `CH_RUNTIME_VIDEO_JOB_V1`:

```json
{
  "contract": "CH_RUNTIME_VIDEO_JOB_V1",
  "id": "runtime.weather.rain_validation",
  "executable": "../../../build/Release/city_builder.exe",
  "cwd": "../../..",
  "outputDir": "../../../out/video_lab/runtime_weather_rain",
  "fps": 30,
  "frameCount": 150,
  "weather": "rain",
  "hideUi": true,
  "paused": false,
  "gif": {
    "enabled": true,
    "output": "runtime_weather_rain.gif"
  },
  "video": {
    "enabled": true,
    "output": "runtime_weather_rain.mp4"
  }
}
```

Execute:

```bash
python tools/animation_preview/capture_runtime_video.py --job tools/animation_preview/examples/runtime_weather_capture.json
```

O script valida `runtime_capture_report.json`, exige exatamente a quantidade pedida de PNGs e somente então chama os writers de GIF/vídeo.

## Evidência e limites do V1

A sequência PNG é a evidência visual autoritativa. O MP4/GIF é somente artefato de revisão.

V1 já resolve:

- captura real do renderer do jogo;
- timestep fixo;
- sessão única sem reiniciar o runtime a cada frame;
- clima selecionável;
- UI opcional;
- saída automática para o CH Video Lab.

Ainda não resolve ações semânticas de gameplay no meio da sessão, por exemplo “construa uma rua no segundo 2” ou “mande o trem sair da estação no segundo 5”. Essa é a próxima camada: um diretor de ações determinísticas aplicado sobre o estado real do runtime.
