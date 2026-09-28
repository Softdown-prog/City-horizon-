# Agua continua do City Horizon

Esta pasta contem as superficies aprovadas de agua rasa e profunda. Os PNGs `*_world.png` sao as bases periodicas de 256x256 amostradas em coordenadas do mundo; cada periodo equivale a quatro tiles por eixo. Os bakes isolados 128x64 nao devem ser repetidos como superficie final.

Para cada profundidade, `*_glint_overlay.png` preserva a fonte do brilho translucido original aprovado. `*_glint_indices.png` codifica o alpha original nos seis bits superiores e uma fase local nos dois bits inferiores. `*_glint_cycle_atlas.png` guarda 16 quadros RGBA de 256x256, com 1 px de margem periodica por lado. O atlas ja incorpora o brilho e seu deslocamento suave, alem de um ciclo discreto de quatro paletas de intensidade (variacao maxima de 3/255 no alpha). Desenhe apenas o atlas sobre a base, sem somar o overlay original uma segunda vez. As bases nao mudam de cor durante a animacao.

`water_surfaces.json` registra caminhos, paletas, ordem dos quadros e tempo de 125 ms por quadro (2 segundos por volta). Para um quadro de indice `i` em ordem de linha, seu retangulo util comeca em `((i % 4) * 258 + 1, (i // 4) * 258 + 1)` e mede 256x256. Amostre o quadro no espaco do mundo e limite o desenho aos tiles semanticamente definidos como agua; a rotacao de camera altera apenas as coordenadas de amostragem.

Fonte reproduzivel: receitas `water_surface_*_01.json` -> bake CH Blender -> `export_water_tiles.py` -> `prepare_water_world_preview.py` -> `promote_water_surface.py`. A ultima etapa recebe a pasta `out/water/continuous` aprovada e grava esta pasta:

```bash
python tools/tycoon_photo_studio/promote_water_surface.py \
  --continuous out/water/continuous --output assets/terrain/water
```

Promocao visual: artefato `City-Horizon-Water-3D-to-2D-PNGs` do workflow `Tycoon Water Surface Bake`, run 36481392330. Os arquivos estao prontos para consumo pelo renderer; conectar e conferir no mapa sera uma etapa posterior. O atlas RGBA permite animacao sem depender de suporte a texturas indexadas em cada backend SDL. A costa continua independente desta superficie.
