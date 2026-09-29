# CH MapForge Video Validation

Este é o caminho operacional do CH Video Lab enquanto a integração direta com o executável `city_builder` permanece separada do V1.

## Fluxo

```text
job CH_VIDEO_SCENARIO_V1
        ↓
GitHub Actions (Windows)
        ↓
MapForge2CLI / MAPFORGE_CAPTURE_REQUEST_V1
        ↓
requests JSON resolvidos por frame
        ↓
PNGs determinísticos do renderer
        ↓
CH Video Lab
        ↓
GIF + contact sheet + MP4/WebM + relatórios JSON
        ↓
artifact CH-MapForge-Video-Validation
```

O workflow é `.github/workflows/ch-mapforge-video-capture.yml`.

Ele é pesado porque instala Qt, compila o capturador e codifica mídia. Por isso o gatilho de push é deliberadamente restrito a:

```text
tools/animation_preview/mapforge_jobs/*.json
```

Um commit comum de código ou assets não deve disparar esse workflow.

## Criando um teste

Crie um JSON em `tools/animation_preview/mapforge_jobs/` com contrato `CH_VIDEO_SCENARIO_V1`.

Além dos campos normais do cenário, o workflow usa:

```json
{
  "mapforgeCandidateFile": "assets/tree/park_tree_angico_final_v1.png",
  "mapforgeBaseRequestFile": "C++/MapForge2/examples/map_capture/capture_request.json"
}
```

O workflow substitui `renderer.command`, `renderer.cwd`, `baseRequestFile` e `outputDir` por caminhos absolutos do runner. Assim o job continua portátil no repositório.

## Evidência

O MP4/GIF é somente revisão. A evidência autoritativa continua sendo:

- o job JSON original;
- cada request JSON resolvido por frame;
- os PNGs renderizados pelo MapForge;
- os hashes registrados por `scenario_report.json` e pelo relatório do encoder.

Isso permite reproduzir o vídeo sem depender de captura de desktop ou vídeo generativo.

## Estado da integração com o jogo real

O objetivo final continua sendo usar o mesmo CH Video Lab para cenários do runtime completo (veículos, visitantes, clima, atrações, trens e ações de gameplay).

Essa ponte não faz parte do V1 operacional enquanto o target raiz `city_builder` apresentar regressões de compilação independentes da ferramenta de vídeo. O Video Lab não deve contornar esses erros criando uma segunda cópia do jogo. Quando o runtime voltar a compilar, a extensão correta será expor um modo determinístico de frame/action capture no executável canônico e reutilizar os mesmos writers de GIF/MP4/WebM.
