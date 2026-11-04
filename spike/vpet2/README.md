# spike/vpet2 — sprites V-Pet coesos (M11, protótipo, rodada 2)

Estilo de referência: sprites de V-Pet (contorno escuro de 1 px, rampa curta, olhos grandes). **Todo desenho é
original**; nenhuma forma, nome ou visual de personagem existente.

Folhas de revisão (em `art-review/`, fora do git):

    SDL_VIDEODRIVER=dummy ./.venv/bin/python -m spike.vpet2.sheets /home/alex/Documentos/codes/engrama/art-review

`lineages.png` (16 sementes × ovo + 5 estágios), `families.png` (8 famílias × os 3 subplanos + 1 extra, adulto),
`silhouettes.png` (mesmo recorte no estágio final, só a silhueta, sem acessórios), `personality.png` (traços
extremos e cada ramo), `anims.png` (todas as `ANIMS`). Imagens do README do produto:
`python -m spike.vpet2.showcase docs/images`.

Custo medido (adulto/final, 400 sprites): mediana ~5,5 ms, p95 ~8 ms, pior ~11 ms (finais densos de dragão
quadrúpede). Determinístico.

## Coesão (mantida da rodada 1)

- **Família fixa pela vida toda** (`family_of(seed)`) e agora também um **subplano fixo** (`genes["plan"]`, 0..2).
- Mesmos genes, paleta, marcações e estilo de olho em todos os estágios; o estágio só muda proporções e o tamanho
  dos traços (`GROW`: 0,42 → 1,15) e o preenchimento do canvas (0,74 → 1,0), então cada estágio cresce do anterior.

## Famílias e subplanos (esqueleto próprio por plano)

| família | plano 0 | plano 1 | plano 2 |
|---|---|---|---|
| dragão | quadrúpede 3/4: tronco horizontal, pescoço, focinho, cauda grossa, asas de membrana com dedos (adulto+) | bípede pesado de frente: quadril largo, focinho, cauda, asas grandes | serpente/wyrm: corpo em S saindo de uma espiral, bigodes, crista nas costas, bracinhos |
| fera | quadrúpede 3/4 ágil, cauda para cima | sentado: ancas largas, patas dianteiras retas (sociável acena com uma), cauda em volta | bípede (urso/coelho), orelhas grandes |
| ave | empoleirada 3/4: corpo inclinado, bico de acento, cauda longa, pernas finas, asas sobem no perfeito | coruja: disco facial, tufos, asas laterais, garras | em voo: asas abertas em leque, cauda em leque, sem pernas |
| inseto | besouro de frente: carapaça em domo (acento) com costura, cabeça baixa, chifre, 6 patas | louva-a-deus/formiga: abdômen grande atrás, tórax fino, braços-lâmina | mariposa: corpo segmentado, dois pares de asas grandes com ocelos |
| planta | bulbo andante: pera, folhas no topo, raízes, mãos-folha | flor: rosto num anel de pétalas sobre um caule, braços-folha, base de raízes | cacto: coluna alta, braços dobrados, espinhos, flor no topo |
| espírito | lençol: domo + barra ondulada, bracinhos, flutua | chama: gota coroada de línguas de fogo, cauda de fumaça | encapuzado: manto com barra recortada, rosto na sombra com olhos acesos, mãos soltas, cajado com orbe |
| aquático | água-viva: sino, saia recortada, tentáculos | peixe 3/4: nadadeira bifurcada, dorsal, peitoral | anfíbio de pé: brânquias/nadadeiras na cabeça, cauda com nadadeira |
| máquina | bípede de caixas com tela no rosto | tanque: esteiras com rodas, casco, cabeça-TV, canhão (adulto+), braços (perfeito+) | drone: núcleo redondo, rotor, braços com garra, propulsor, anel |

Planos 3/4 são desenhados virados para a esquerda e espelhados pelo gene `side`.
Genes por família (`f1`..`f4`): tipo de chifre/orelha/crista/antena, ponta de cauda, juba, material da carapaça
etc. Genes comuns: marcação (listras, pintas, máscara, boné, meias) e seu material, boca, barriga, proporções.

## Olhos e rostos

Estilos (`face.py`): `gem` (oval escuro com brilhos), `sclera` (branco + pupila), `slit` (íris de acento com pupila
em fenda), `beady` (pontinho), `compound` (grande, facetado), `glow` (claro, sem pupila), `visor` (faixa escura
com duas fendas acesas), `sleepy` (pálpebra). Cada família tem sua lista e a semente escolhe:
dragão slit/gem, fera gem/slit/sclera, ave beady/gem/sclera, inseto compound/beady, planta gem/sleepy/beady,
espírito glow/gem (encapuzado sempre glow), aquático glow/gem/beady conforme o plano, máquina visor/glow/gem.
Bocas por família: presa/sorriso, boca de gato, bico (sem boca), mandíbulas, "o", boca larga, grade de alto-falante.
Persona: independência → sobrancelha brava; paciência → pálpebra; curiosidade → olho mais alto;
sociabilidade → sorriso. Ramos de negligência só deixam os olhos vermelhos (paleta intocada).

## Sombreamento

Luz fixa de cima-esquerda; normal analítica por parte (elipse, cápsula); tons realce/base/sombra com deslocamento
de matiz, mais um **brilho especular** (tom quase branco do material) no ponto de maior incidência das elipses
grandes. Partes planas (polígonos, retângulos) usam aro inferior-direito/superior-esquerdo. Sombra de contato sob
partes da frente. Linha interna seletiva (mais clara que o contorno) entre partes de materiais **ou nomes**
diferentes — é ela que separa asas, patas e cabeça do corpo da mesma cor.

## Persona e ramos

Persona 0..1 (`vocab.TRAIT_KEYS`): bebê usa o temperamento da semente; depois, temperamento + empurrões da
linhagem (`genes.BRANCH_PUSH`), ou traços reais (`traits=`). Efeitos: largura do corpo (paciência+, independência−),
comprimento de membros, tamanho dos traços, cabeça/orelhas (curiosidade), braços/asas abertos (sociabilidade). Sem
poses laterais por personalidade.

**Acessórios acumulam**: cada ramo da linhagem tem um encaixe (topo da cabeça, rosto, pescoço, peito, costas,
pulso). Do mais recente para o mais antigo, entra um por encaixe, no máximo 3; o mais recente em tamanho cheio,
os anteriores a 88%. Escala pela cabeça/corpo, não fixa em pixels.

| encaixe | ramos |
|---|---|
| topo | curioso (topete), sonhador (estrela), explorador (óculos), artista (boina), técnico (monóculo-visor com antena), virtuoso (laço), aventureiro (bandana), lendário (coroa) |
| rosto | brincalhão (bochechas), arisco (curativo) |
| pescoço | companheiro (cachecol) |
| peito | guardião (escudo + ombreiras), mestre (cinto, fivela, medalha) |
| costas | sombrio (capa rasgada), sábio (capa + gola), eco (anel), sombra (chamas escuras) |
| pulso | rebelde (braceletes com tachas; sem mãos → peito) |

## Paleta (regras inalteradas)

3 tons de corpo com deslocamento de matiz, barriga = tons claros do mesmo matiz, marcação = tons escuros, 1 acento,
contorno quente fixo `(46, 26, 22)`; extras fixos pequenos: osso, vidro, ouro, e o tom especular derivado.
Matiz base = `Genome.palette[1]`, puxado pela família e pelo temperamento.

## Ovo

`gen.egg(seed)`: 16 px, cor da família (mesma paleta da criatura) e um motivo pequeno: zigue-zague (dragão),
manchas (fera), pintinhas (ave), faixas (inseto), broto no topo (planta), chama (espírito), onda (aquático),
rebites + antena (máquina).

## Limitações conhecidas

- Dragão quadrúpede no adulto ainda fica carregado (asa + chifres + acessórios competem); a ave empoleirada com
  asas erguidas no final lê como "pente" em algumas sementes; louva-a-deus é o plano menos legível.
- Acessórios de costas (capa) em serpente e água-viva ficam estranhos; não há regra por plano para esconder um
  encaixe.
- Linhas internas por nome às vezes riscam o corpo em partes que deveriam fundir (ex.: barriga do wyrm).
- Custo: pior caso ~11 ms num final denso; com o LRU do app (desenho só na evolução) é aceitável, mas fica acima
  da meta de 10 ms. Caminhos: menos partes pequenas (juntar espinhos num polígono), cache de máscaras por estágio.
- Babies de planos diferentes da mesma família às vezes se parecem (bolha + traço da família).
- Sem testes ainda.

## Integração em `engrama/app/art`

1. Mover `core/face/genes/families/gen` para `engrama/app/art/vpet/` (substituindo `archetypes.py`/`plan.py`);
   `anim.py` do M6 continua (o protótipo já reusa as transformações).
2. `sprites.frames(look, stage, anim)` segue sendo a API pública: `vpet.creature_frames` chama
   `gen.sprite(look.seed, stage, lineage=known_lineage(lineage)+(branch,), hue_rgb=look.palette[1])`; o ovo passa a
   usar `gen.egg` (com o tremor/rachaduras do `make_egg_crack` por cima). `Look`, `look_of`, `ANIMS`, `SIZES`,
   `food_icon`, `contact_sheet` não mudam.
3. **Saves**: nada novo no `Genome`. Família, plano, genes, temperamento e paleta saem da semente; a persona
   vivida e os acessórios saem da linhagem já salva. Chave de cache = (seed, palette[1], stage, anim, linhagem).
4. Testes a criar: tamanhos; determinismo; família e plano constantes entre estágios; olhos visíveis em todo
   `idle`; área do final > adulto; ramo desconhecido → base; ≤3 acessórios; custo; LRU limitado.
