# spike/vpet2 — sprites V-Pet coesos (M11, protótipo)

Estilo de referência: sprites de V-Pet (contorno escuro de 1 px, rampa curta, olhos grandes). **Todo desenho é
original**; nenhuma forma, nome ou visual de personagem existente.

Rodar as folhas de revisão (saem em `art-review/`, não versionado):

    SDL_VIDEODRIVER=dummy ./.venv/bin/python -m spike.vpet2.sheets /home/alex/Documentos/codes/engrama/art-review

`lineages.png` (16 sementes × ovo + 5 estágios), `families.png` (8 famílias × 4 sementes, adulto),
`personality.png` (mesma semente com traços extremos e cada ramo), `anims.png` (todas as `ANIMS`).
Custo medido: ~3,5 ms por sprite (48 px final ~4,6 ms), determinístico.

## Como a coesão funciona

- **Família fixa pela vida toda**, `family_of(seed)` (sha256 da semente): `draco` (dragão), `fera`, `ave`,
  `inseto`, `planta`, `espirito`, `aquatico`, `maquina`.
- **Um esqueleto só** (`families.skeleton`): cabeça, corpo, pernas, braços, em coordenadas de projeto (x centrado,
  chão em y=0). O estágio só muda proporções: bebê = cabeça enorme + pés; criança ganha braços/pernas; adulto,
  perfeito e final alongam corpo e membros e encolhem a cabeça relativa. O render encaixa no canvas com
  preenchimento crescente (0,74 → 1,0), então cada estágio é maior que o anterior.
- **Traços da família crescem** com `GROW[t]` (0,42 → 1,15): chifres, orelhas, cristas, caudas, nadadeiras,
  asas (dragão a partir do adulto, ave abre as asas no perfeito, inseto ganha asas no perfeito).
- **Genes da semente iguais em todos os estágios**: tipo de chifre/orelha/crista (`f1`), variante de corpo
  (`f2`), cauda (`f3`), material dos chifres/marca da testa (`f4`), estilo de olho, marcação (listras, pintas,
  máscara, boné, meias), material da marcação, boca, barriga, lado da cauda, proporções finas (`hy`, `bodyk`,
  `limbk`).

### Famílias (plano de corpo)

| família | silhueta | genes `f1`/`f2`/`f3` |
|---|---|---|
| dragão | corpo largo com quadril, focinho saliente, cauda grossa | chifres (cone, curvo, dois pares, crista) / asas de membrana ou espinhos nas costas / ponta da cauda (pá, chama, espinhos) |
| fera | cabeça larga, focinho + nariz, cauda com tufo | orelhas (pontuda, redonda, longa, caída) / juba no perfeito / cauda (tufo, fina, cheia) |
| ave | corpo grande, cabeça afundada, bico de acento, pernas finas | crista (três penas, pluma, leque, coroa) / — / leque da cauda; asas dobradas → abertas |
| inseto | corpo estreito, antenas, par de patas extra | antenas (bola, enrolada, plumosa, chicote) / besouro (carapaça + chifre), mariposa (gola + asas com olho), louva-deus (lâminas) |
| planta | bulbo em pera, sem pescoço, raízes | broto, botão em haste, coroa de folhas, flor (anel de pétalas a partir do adulto) |
| espírito | sem pernas, flutua sobre cauda de fumaça | chama, chifrinhos, auréola, capuz; orbes no perfeito, cauda dupla no final |
| aquático | cabeça bem larga, quadril, cauda com nadadeira | nadadeira-orelha, brânquias, isca luminosa, nadadeira dorsal |
| máquina | cabeça e corpo em caixa, tela clara no rosto | antena simples/dupla, parafusos, aleta; ombreiras no perfeito, propulsores no final |

## Personalidade e ramo

Persona 0..1 nas chaves de `vocab.TRAIT_KEYS`. Bebê usa o **temperamento** (derivado da semente). Do filhote em
diante usa a **persona vivida** = temperamento + empurrões dos ramos da linhagem (`genes.BRANCH_PUSH`, espelha os
pesos de `kernel/branches.py`), ou os traços reais se forem passados (`traits=`).

| traço alto | efeito |
|---|---|
| curiosidade | cabeça maior, olhos mais altos, orelhas/antenas maiores |
| sociabilidade | braços abertos/levantados, sorriso, corpo um pouco mais largo, cor mais quente (temperamento) |
| paciência | corpo largo, pernas curtas, base aberta, olhos semicerrados ("calm"), braços descansando |
| independência | corpo magro, pernas longas, chifres/cauda/espinhos maiores, olhos "sharp", presa, cor mais fria e saturada |
| criatividade | traços ornamentais maiores (cristas), acento mais afastado no círculo de cor |

Ramo do estágio atual → acessório (por cima do corpo, não muda o encaixe): brincalhão bochechas, curioso pinta na
testa, sonhador estrela, companheiro cachecol, explorador óculos, artista boina, técnico fone, guardião ombreira +
emblema, sábio capa + gema, virtuoso laço, aventureiro bandana + alça, rebelde braceletes com tachas, lendário coroa +
emblema, mestre capa + cinto, eco anel, sombra chamas escuras. Ramos de negligência (arisco, sombrio, rebelde,
sombra) dão **olhos vermelhos**. Ramos anteriores não deixam acessório, só a persona acumulada.

## Paleta

- 3 tons de corpo (luz → amarelo, sombra → violeta, com deslocamento de matiz), barriga = tons claros do mesmo
  matiz, marcação = tons escuros do mesmo matiz, **1 acento** (complementar, triádico ou split, pela semente),
  contorno quente fixo `(46, 26, 22)`. Extras fixos e pequenos: osso (chifres/garras), vidro (tela, asas de
  inseto, óculos) e ouro (só emblemas/coroas).
- Matiz base = `Genome.palette[1]` (o mesmo que a herança preserva), puxado para a família (planta → verde,
  aquático → azul-ciano, máquina/espírito dessaturados) e empurrado pelo temperamento. Constante a vida inteira.

## Pipeline de render (`core.render`)

Partes vetoriais (elipse, cápsula afunilada em cadeia, polígono, retângulo arredondado) → máscara por pixel com
normal analítica → tom por luz fixa de cima-esquerda (realce / base / sombra); partes planas usam aro
inferior-direito. Sombra de contato sob partes da frente; "patches" recolorem partes já desenhadas sem mudar o
tom. Limpeza: remove pixels órfãos e lascas de 1 px (exceto pontas marcadas `keep`), tapa furos de 1 px, reverte
realces/sombras isolados. Linha interna seletiva (mais clara que o contorno) entre partes de materiais
diferentes; contorno externo de 4 vizinhos. Simetria espelhada exata quando o corpo está centrado. Rosto (olhos e
boca) é carimbado por quadro, igual ao M6.

## O que falta / limitações conhecidas

- O ovo ainda é o do M6 (cor do genoma, sem o puxão da família): o ovo de uma planta pode sair amarelo.
- Asas abertas da ave e a carapaça do inseto ainda são as partes mais "ruidosas"; inseto adulto é o mais
  carregado. Nadadeira-leque do aquático lê como estrela em algumas sementes.
- Só vista frontal; poses (sentado, de lado) não implementadas. Sem animação de membros (só transformações do
  sprite inteiro, como no M6).
- Acessórios são pequenos no adulto; alguns (cachecol, pinta) somem em 40 px.
- Não há testes ainda; as heurísticas de encaixe com acessório alto (coroa) encolhem um pouco o corpo.

## Integração em `engrama/app/art`

1. Mover `core/face/genes/families/gen` para `engrama/app/art/vpet/` (substituindo `archetypes.py`/`plan.py`),
   manter `anim.py` do M6 (o protótipo já reusa as transformações dele).
2. `sprites.frames(look, stage, anim)` continua a API pública: `vpet.creature_frames(look, stage, anim, branch,
   lineage)` passa a chamar `gen.sprite(look.seed, stage, lineage=known_lineage(lineage)+(branch,),
   hue_rgb=look.palette[1])`. `Look`, `look_of`, `ANIMS`, `SIZES`, `make_egg_crack`, `food_icon` e
   `contact_sheet` não mudam.
3. **Saves**: nada novo no `Genome`. Família, genes, temperamento e paleta saem da semente; a persona vivida sai
   da linhagem já salva. `Look` continua lendo dicts antigos. Chave de cache = (seed, palette[1], stage, anim,
   ramo do estágio, linhagem) — igual à atual.
4. Opcional: passar os traços reais (`snapshot.traits`) congelados no momento da evolução — exigiria guardar um
   vetor por estágio; por isso o padrão é derivar da linhagem.
5. Testes a portar/criar: tamanhos, determinismo, família constante entre estágios, olhos visíveis em todo
   `idle`, área do final > adulto, ramo desconhecido → base, custo ≤10 ms, LRU limitado.
