# Asset PNG Tool

Ferramenta local em Python para preparar assets 2D de city builder.

## Requisitos

- Python com `Pillow` e `PySide6`.
- Neste computador, o PySide6 6.11.2 já está disponível.

## Abrir a interface PySide6

No PowerShell, dentro desta pasta:

```powershell
python .\asset_png_tool.py
```

1. Clique em **Abrir imagem**. A interface foi construída com **PySide6**.
2. Ajuste tolerância, suavização e redução de halo usando a prévia.
3. Preencha identificação, categoria, grade, âncora e tags.
4. Clique em **Exportar PNG + JSON** e escolha a pasta de destino.

## O que é exportado

- `id-do-asset.png`: PNG RGBA com fundo transparente.
- `id-do-asset.json`: classificação do asset, tamanho, grade, âncora, tags e parâmetros de tratamento.

## Processamento em lote

```powershell
python .\asset_png_tool.py --batch "C:\imagem.jpg" --out "C:\assets-prontos" --id "cafe_moderno_01"
```

## Ajustes recomendados

- **Tolerância de fundo:** aumente somente se restarem partes do checkerboard; reduza se o tratamento invadir paredes/toldos claros.
- **Suavização:** 1–3 px normalmente mantém bordas naturais.
- **Redução de halo:** 1 px é o ponto de partida seguro para imagens JPEG com checkerboard.
- **Recortar área transparente:** use apenas quando o pipeline do jogo não depender de uma tela/canvas padronizado.
