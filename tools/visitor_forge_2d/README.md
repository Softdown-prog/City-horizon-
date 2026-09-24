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
  -> Pose
  -> Layer Composer
  -> Shading/lighting 2D simplificado
  -> Downscale controlado
  -> Anchor
  -> PNG RGBA + metadata
```

## Escopo V1

A V1 deve provar apenas um visitante masculino em SOUTH com três poses:

- `south_idle`
- `south_walk_a`
- `south_walk_b`

Regras da V1:

- composição por camadas 2D;
- partes mínimas: cabeça, cabelo, tronco/roupa, braço esquerdo, braço direito, perna esquerda, perna direita e sapatos;
- caminhada curta e conservadora;
- pouco balanço de braço;
- sem deslocamento vertical artificial do corpo;
- anchor dos pés idêntico entre os três frames;
- PNG RGBA transparente;
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

## Estrutura planejada

```text
tools/visitor_forge_2d/
  README.md
  src/
  assets/
    body/
    heads/
    hair/
    clothes/
    legs/
    shoes/
  definitions/
  poses/
  previews/
  output/
```

Essas subpastas devem ser criadas apenas quando tiverem conteúdo real; não adicionar diretórios vazios ou placeholders desnecessários.

## Metadata de saída

Cada visitante aprovado deverá exportar PNGs e um JSON com, no mínimo:

- `characterId`
- `direction`
- `pose`
- `canvasSize`
- `anchor`
- `frameDurationMs`
- `transparent`
- `forgeContractVersion`

Exemplo futuro:

```json
{
  "characterId": "visitor_male_01",
  "direction": "south",
  "canvasSize": [128, 128],
  "anchor": [64, 112],
  "frameDurationMs": 220,
  "transparent": true,
  "forgeContractVersion": "CH_VISITOR_FORGE_2D_V1"
}
```

## Gate de qualidade

Antes de qualquer expansão para EAST/WEST/NORTH ou visitantes femininos, o primeiro conjunto SOUTH deve ser validado em três níveis:

1. visual grande para inspecionar as formas;
2. visual no tamanho real de gameplay;
3. comparação dentro do mapa, sobre calçada/rua e próximo a construções.

Se o personagem só ficar bonito ampliado, a V1 ainda não está aprovada.

## Integração futura

O Sprite Workshop existente pode ser usado depois para validar alpha, halo, bounds, anchor e animação. A engine deve continuar consumindo apenas PNG RGBA + metadata, sem depender de como o personagem foi produzido.

## Status

**Estado atual:** estrutura inicial/documentação criada. Implementação ainda não iniciada.

**Próxima tarefa:** criar o primeiro protótipo independente do `CH Visitor Forge 2D`, gerando somente `south_idle`, `south_walk_a` e `south_walk_b` para um visitante masculino estilizado.