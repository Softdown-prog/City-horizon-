# CH Actor — fonte original validada

Esta pasta preserva o HTML original do CH Actor fornecido pelo autor do projeto e permite executá-lo diretamente no GitHub Actions.

## Fonte congelada

- `ch_actor_lab_original.html`
- contrato exportado: `CH_ACTOR_CONTRACT_V1`
- câmera: `CH_CAMERA_V1` ortográfica 45°/30°
- frame padrão: `48x64`
- ground anchor: `[24,60]`
- caminhada: `8` frames por direção
- leg swing: `0.32 rad`
- arm swing: `0.18 rad`
- vertical bounce: `0.004`
- ordem das linhas: `S / E / W / N`

Não alterar esta fonte ao criar roupas/personagens. Novas aparências devem ser implementadas como skins/costumes sobre o ator validado.

## Executar no GitHub

Workflow: `.github/workflows/ch-actor-original-html-export.yml`

No GitHub:

1. Abra **Actions**.
2. Escolha **CH Actor Original HTML Export**.
3. Clique em **Run workflow** e selecione a branch `feature/ch-character-studio-art-v0`.
4. Ao terminar, baixe o artifact `CH-Actor-Original-HTML-<run id>`.

O workflow abre o HTML original em Chromium headless com Playwright e usa os próprios botões de exportação da página.

## Saídas do artifact

- `ch_actor_48x64_8f.png` — spritesheet RGBA real gerada pelo HTML.
- `ch_actor_48x64_8f_manifest.json` — manifesto exportado pela página.
- `ch_actor_lab_page.png` — captura da ferramenta executando no navegador.
- `execution_report.json` — validação automática dos valores congelados.

O workflow falha se resolução, número de frames, câmera, anchor ou parâmetros validados da caminhada forem alterados.
