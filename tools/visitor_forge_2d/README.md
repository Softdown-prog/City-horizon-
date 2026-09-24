# CH Visitor Forge 2D

Ferramenta dedicada para gerar visitantes 2D estilizados para o City Horizon.

## Objetivo

O Visitor Forge 2D existe para produzir personagens pequenos, legíveis e consistentes para o mapa isométrico do jogo sem depender de um render 3D realista como arte final.

O alvo visual é uma linguagem própria de city builder/tycoon: silhueta clara, cabeça mais legível, braços e pernas com espessura suficiente, mãos e pés simplificados, roupa com massas limpas e detalhes que sobrevivam ao tamanho real de gameplay.

A ferramenta deve priorizar **estilo, legibilidade, consistência e animação curta** em vez de anatomia realista.

## Decisão de pipeline

O MPFB/Blender pode continuar sendo usado como apoio para anatomia, pose, rig e referência, mas **não é a fonte visual final obrigatória** dos sprites do Visitor Forge 2D.

Pipeline atual:

```text
Procedural 2D Art Generator
  -> neutral RGBA body parts
  -> palette tint
  -> 2D joints / pose transforms
  -> layer composer
  -> simplified painted shading
  -> alpha-safe downscale
  -> anchor
  -> PNG RGBA + metadata
```

## Arquitetura

O núcleo foi separado do módulo de personagem para que a ferramenta possa crescer além de visitantes:

```text
tools/visitor_forge_2d/
  README.md
  pyproject.toml
  docs/
    ARCHITECTURE.md
  src/
    visitor_forge_2d/
      core/
      character/
        procedural_art.py
  definitions/
  poses/
  tests/
```

`core/` contém mecanismos genéricos: canvas, layers, joints, transforms, composição, paleta, downscale e export.

`character/` contém as regras específicas de personagem e o gerador visual atual.

A pasta de assets gerados não é tratada como fonte canônica: as peças V1 são determinísticas e podem ser reconstruídas pelo próprio Visitor Forge. Isso evita acumular PNGs duplicados no repositório enquanto o estilo ainda está em gate visual.

## Escopo V1

A V1 deve provar apenas um visitante masculino em SOUTH com três poses:

- `south_idle`
- `south_walk_a`
- `south_walk_b`

O rig 2D usa:

- pelvis / spine / neck / head;
- shoulder / elbow / wrist por braço;
- hip / knee / ankle por perna;
- cabeça, cabelo, tronco, braços, mãos, pernas e sapatos como partes independentes;
- sombra de contato separada e fixa no chão.

Regras:

- composição por camadas 2D;
- SOUTH em leitura leve de 3/4, não frontal chapada;
- caminhada curta e conservadora;
- pouco balanço de braço;
- sem bob vertical artificial;
- anchor dos pés idêntico entre frames;
- PNG RGBA full-color;
- render interno em 512x512 e saída inicial em 128x128;
- downscale Lanczos com alpha premultiplicado quando suportado pelo Pillow;
- não promover ao runtime antes de aprovação visual.

## Gerador visual procedural V1

`character/procedural_art.py` gera as peças-base diretamente em 2D. Ele não usa malha 3D, fotografia ou textura de roupa realista.

Contrato visual atual:

`CH_VISITOR_FORGE_2D_TYCOON_V1`

O gerador trabalha com máscaras vetoriais/rasterizadas pelo Pillow e aplica iluminação 2D ampla, bordas suaves, pequenos detalhes de rosto/roupa e shading neutro. As peças são criadas em tons neutros e recebem a paleta depois, no compositor.

Isso permite trocar pele, cabelo, camisa, calça e sapatos sem redesenhar a silhueta ou a animação.

## Direção visual

Evitar:

- humano realista miniaturizado;
- textura fotográfica;
- roupa com microdetalhe que desaparece no gameplay;
- dedos individualizados;
- braços/pernas finos demais;
- aparência de boneco feito de cilindros;
- iluminação dramática ou excessivamente 3D;
- passos largos ou movimentos exagerados.

Preferir:

- formas contínuas e levemente caricatas;
- cabeça legível;
- membros com boa leitura;
- mãos/pés simplificados;
- rosto econômico;
- cores limpas e separadas;
- volume 2D amplo e discreto;
- pequena sombra de contato;
- identidade original do City Horizon, inspirada pela legibilidade dos tycoons clássicos sem copiar personagens específicos.

## CLI

Instalação local de desenvolvimento:

```bash
python -m pip install -e tools/visitor_forge_2d
```

Validar contratos/poses:

```bash
ch-visitor-forge-2d validate \
  --definition tools/visitor_forge_2d/definitions/visitor_male_01.south.json \
  --pose tools/visitor_forge_2d/poses/south_idle.json \
  --pose tools/visitor_forge_2d/poses/south_walk_a.json \
  --pose tools/visitor_forge_2d/poses/south_walk_b.json
```

Gerar somente as partes 2D:

```bash
ch-visitor-forge-2d build-assets \
  --asset-root out/visitor_forge_2d/assets
```

Gerar partes + três frames + strips de comparação em uma única chamada:

```bash
ch-visitor-forge-2d prototype \
  --definition tools/visitor_forge_2d/definitions/visitor_male_01.south.json \
  --pose tools/visitor_forge_2d/poses/south_idle.json \
  --pose tools/visitor_forge_2d/poses/south_walk_a.json \
  --pose tools/visitor_forge_2d/poses/south_walk_b.json \
  --asset-root out/visitor_forge_2d/assets \
  --output out/visitor_forge_2d/visitor_male_01
```

O comando `prototype` produz também:

- `visitor_male_01_south_review_strip.png`;
- `visitor_male_01_south_gameplay_strip.png`.

Esses strips existem para comparar as três poses sem precisar integrar nada ao jogo.

## Metadata de saída

Cada frame exportado inclui PNG e JSON com, no mínimo:

- `characterId`;
- `direction`;
- `pose`;
- `canvasSize`;
- `workingCanvasSize`;
- `anchor`;
- `frameDurationMs`;
- `transparent`;
- `colorMode`;
- `downscaleFilter`;
- `forgeContractVersion`.

A engine continua consumindo apenas PNG RGBA + metadata; ela não deve depender de como o personagem foi produzido.

## Gate de qualidade

Antes de qualquer expansão para EAST/WEST/NORTH ou visitantes femininos, o conjunto SOUTH deve ser validado em três níveis:

1. visual grande para inspecionar forma e juntas;
2. visual em 128x128/tamanho real de gameplay;
3. comparação dentro do mapa sobre calçada/rua e próximo a construções.

Se o personagem só ficar bom ampliado, a V1 ainda não está aprovada.

## Integração futura

O Sprite Workshop existente pode ser usado depois para validar alpha, halo, bounds, anchor e animação.

O núcleo genérico também poderá ser reaproveitado por funcionários, vendedores, mascotes, pequenos animais, placas animadas e outros assets 2D em camadas.

## Status

**Estado atual:** núcleo procedural V0.1 + primeiro gerador visual SOUTH implementados. A ferramenta já consegue construir as próprias partes 2D, compor `idle`, `walk A`, `walk B` e produzir strips de revisão. Ainda é um gate artístico; nada foi promovido ao runtime.

**Próxima tarefa:** executar e revisar o primeiro strip produzido pelo pipeline real, ajustar proporções/silhueta/3/4 até o visitante chegar ao padrão visual desejado e somente depois congelar o estilo V1.
