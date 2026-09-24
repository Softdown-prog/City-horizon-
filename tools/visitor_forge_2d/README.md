# CH Visitor Forge 2D

Ferramenta dedicada para gerar visitantes 2D estilizados para o City Horizon.

## Objetivo

O Visitor Forge 2D existe para produzir personagens pequenos, legíveis e consistentes para o mapa isométrico do jogo sem depender de um render 3D realista como arte final.

O alvo visual é um visitante com linguagem de tycoon clássico: silhueta clara, cabeça um pouco maior, braços e pernas legíveis, mãos e pés simplificados, roupa com massas limpas e boa leitura em tamanho pequeno.

A ferramenta deve priorizar **estilo, legibilidade, consistência e animação curta** em vez de anatomia realista.

## Decisão de pipeline

O MPFB/Blender pode continuar sendo usado como apoio para anatomia, pose, rig e referência, mas **não é a fonte visual final obrigatória** dos sprites do Visitor Forge 2D.

Pipeline pretendido:

```text
CharacterDefinition
  -> BodyParts 2D
  -> Pose / Joint transforms
  -> Layer Composer
  -> Shading/lighting 2D simplificado
  -> Downscale controlado
  -> Anchor
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
  definitions/
  poses/
```

`core/` contém somente mecanismos genéricos: canvas, layers, joints, transforms, composição, paleta, downscale e export.

`character/` contém apenas regras do personagem/visitante e o gate da V1.

Pastas de arte (`assets/`) só serão criadas quando existirem peças visuais reais. Não adicionar diretórios vazios ou placeholders sem uso.

## Escopo V1

A V1 deve provar apenas um visitante masculino em SOUTH com três poses:

- `south_idle`
- `south_walk_a`
- `south_walk_b`

A V1 usa um rig 2D de recortes simples:

- pelvis / spine / neck / head;
- shoulder / elbow / wrist por braço;
- hip / knee / ankle por perna;
- partes visuais separadas para cabeça, cabelo, tronco, braços, mãos, pernas e sapatos.

Regras da V1:

- composição por camadas 2D;
- caminhada curta e conservadora;
- pouco balanço de braço;
- sem deslocamento vertical artificial do corpo;
- anchor dos pés idêntico entre os três frames;
- PNG RGBA transparente e full-color;
- render interno em resolução maior e downscale final controlado;
- preview em escala real de gameplay;
- não integrar ao runtime antes de aprovação visual.

## Direção visual

Evitar:

- humano realista miniaturizado;
- textura fotográfica;
- roupa com microdetalhes que somem no gameplay;
- mãos com dedos individualizados;
- braços/pernas finos demais;
- iluminação dramática ou excessivamente 3D;
- animação com passos largos ou muito movimento de braços.

Preferir:

- formas simples e contínuas;
- cabeça mais legível;
- braços/pernas ligeiramente mais grossos;
- mãos e pés simplificados;
- cores limpas e separadas;
- contraste suficiente para leitura no mapa;
- sombra e volume 2D discretos;
- visual original do City Horizon inspirado pela legibilidade dos tycoons clássicos, sem copiar personagens específicos.

## Canvas V1

A composição acontece em `512x512` e o primeiro gate exporta em `128x128`.

O downscale usa Lanczos com tratamento de alpha premultiplicado quando suportado pelo Pillow. Isso é parte do contrato para reduzir halo/fringe nas bordas.

O anchor da definição inicial é `[64, 116]` no canvas final de gameplay e pertence ao personagem, não à pose.

## CLI

Instalação local de desenvolvimento:

```bash
python -m pip install -e tools/visitor_forge_2d
```

Validar apenas contratos/poses, sem precisar das imagens das partes:

```bash
ch-visitor-forge-2d validate \
  --definition tools/visitor_forge_2d/definitions/visitor_male_01.south.json \
  --pose tools/visitor_forge_2d/poses/south_idle.json \
  --pose tools/visitor_forge_2d/poses/south_walk_a.json \
  --pose tools/visitor_forge_2d/poses/south_walk_b.json
```

Quando as peças 2D existirem, o mesmo core poderá renderizar:

```bash
ch-visitor-forge-2d render \
  --definition tools/visitor_forge_2d/definitions/visitor_male_01.south.json \
  --pose tools/visitor_forge_2d/poses/south_idle.json \
  --pose tools/visitor_forge_2d/poses/south_walk_a.json \
  --pose tools/visitor_forge_2d/poses/south_walk_b.json \
  --asset-root tools/visitor_forge_2d/assets \
  --output out/visitor_forge_2d/visitor_male_01
```

## Metadata de saída

Cada frame exportado inclui PNG e JSON com, no mínimo:

- `characterId`
- `direction`
- `pose`
- `canvasSize`
- `workingCanvasSize`
- `anchor`
- `frameDurationMs`
- `transparent`
- `colorMode`
- `downscaleFilter`
- `forgeContractVersion`

A engine continua consumindo apenas PNG RGBA + metadata; ela não deve depender de como o personagem foi produzido.

## Gate de qualidade

Antes de qualquer expansão para EAST/WEST/NORTH ou visitantes femininos, o primeiro conjunto SOUTH deve ser validado em três níveis:

1. visual grande para inspecionar as formas;
2. visual no tamanho real de gameplay;
3. comparação dentro do mapa, sobre calçada/rua e próximo a construções.

Se o personagem só ficar bonito ampliado, a V1 ainda não está aprovada.

## Integração futura

O Sprite Workshop existente pode ser usado depois para validar alpha, halo, bounds, anchor e animação.

O núcleo genérico também poderá ser reaproveitado no futuro por funcionários, vendedores, mascotes, pequenos animais, placas animadas e outros assets 2D em camadas.

## Status

**Estado atual:** núcleo procedural 2D V0.1 implementado; definição/skeleton SOUTH e poses V1 registradas. Ainda não há arte final das partes 2D.

**Próxima tarefa:** criar as primeiras partes visuais estilizadas de `visitor_male_01` diretamente em 2D, renderizar `south_idle`, `south_walk_a` e `south_walk_b`, e avaliar o resultado em tamanho real de gameplay antes de expandir o sistema.
