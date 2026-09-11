# City Builder SDL3

Protótipo inicial em C++20 e SDL3 para validar o contrato entre o mapa isométrico e os assets de edifícios pintados.

## Contrato de câmera

A imagem da cafeteria já contém luz, perspectiva e orientação. Portanto, ela é um **sprite isométrico pré-renderizado**, não um modelo que a câmera deve rotacionar. O mapa usa projeção 2:1:

```text
screenX = centroX + panX + (tileX - tileY) * tileWidth/2 * zoom
screenY = centroY + panY + (tileX + tileY) * tileHeight/2 * zoom
```

O asset é colocado pelo centro inferior (`anchor = 0.5, 1.0`) no vértice frontal-inferior de seu footprint. Isso mantém o ângulo estabelecido pela referência em todos os prédios do catálogo.

O terreno usa `assets/terrain/grass_isometric_01.png` como tile 1×1. Seus limites opacos são alinhados aos quatro vértices do mesmo grid 2:1, sem aplicar rotação à textura.

## Executar

Pré-requisitos: CMake 3.24+, compilador C++20 e acesso à internet na primeira configuração para baixar SDL 3.4.0 diretamente do repositório oficial do SDL.

```powershell
cmake -S . -B build
cmake --build build --config Debug
.\build\Debug\city_builder.exe
```

Controles: `WASD`/setas movem o mapa, roda do mouse aplica zoom, `R` restaura a câmera e `Esc` fecha.
