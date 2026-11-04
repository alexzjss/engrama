# Engrama M14: Arte com animação de membros e poses, plano de implementação

**Objetivo:** a criatura se mexer por partes (pernas, braços, cauda, asas, nadadeiras), e não só como um bloco que balança. Cada plano de corpo ganha poses próprias para as animações do app, e o desenho em repouso não muda.

**Roadmap:** `docs/superpowers/specs/2026-11-04-engrama-m12-m15-roadmap.md` (seção M14). Parte de `main` com o M12 mergeado (famílias já em `engrama/app/art/vpet/families/`).

**Execução:** orquestração pelo Opus; subagentes Sonnet (motor de pose, poses por família) e Haiku (marcação mecânica, testes, docs), em worktrees no scratchpad da sessão, partindo da branch `m14`. Um PR no fim. **Sem** linhas de coautoria de IA.

**Ponto de decisão humano:** antes do PR, o usuário aprova as folhas de revisão (PNG/GIF) geradas na T5.

## Estado atual (base técnica)

- Uma criatura é uma lista de `Part` (`E` elipse, `C` cápsula/corrente, `P` polígono, `R` retângulo) montada pelo `Builder` em `core.py`.
- `render(b, N, ...)` rasteriza uma vez, e `gen.sprite()` devolve `Sprite(body, face, n, family, plan)`.
- `anim.frame_arrays(sp, anim)` gera os quadros só com carimbo de rosto mais transformações do sprite inteiro (`dy`, `sq`, `lean`, `lie`, `tint`...). Não há membro que se mexa.
- `sprites.frames()` guarda os quadros num LRU por (semente, cor, estágio, animação, linhagem).
- Partes têm `name` (`"leg"`, `"arm"`, `"tail"`, `"wing"`, `"paw"`, `"foot"`, `"hand"`...), mas o uso é irregular e não há junta (pivô).
- `sym=True` cria a cópia espelhada com o **mesmo** nome; não se sabe qual é o lado.
- Gabarito de pixels do M12: `tests/fixtures/m12_sprite_hashes.json`.

## Desenho

1. **Papel e junta por parte.** `Part` ganha dois campos opcionais com padrão `None`:
   - `role`: `leg`, `arm`, `tail`, `wing`, `fin`, `ear`, `antenna`;
   - `pivot`: `(x, y)` no espaço de desenho.
   `Builder._add` marca `side = +1` na original e `-1` na cópia espelhada. `flip()` espelha também o pivô. Partes sem `role` nunca se mexem.
2. **Pose.** Um dicionário `{role: {"rot": graus, "dx": px, "dy": px, "alt": bool}}`. Com `alt`, o lado `-1` recebe a fase oposta (pernas alternadas). A transformação gira e desloca a geometria da parte em torno do `pivot`, antes de rasterizar:
   - `E`: centro e `rot`;
   - `C` e `P`: pontos;
   - `R`: só translação.
   Função pura `posed(builder, pose) -> Builder`, sem mutar o original.
3. **Quadros.**
   - `frame_arrays` passa a aceitar, por animação e por plano de corpo, uma lista de poses (`POSES[family][plan][anim]`, com fallback por família e depois genérico).
   - Cada quadro renderiza o builder com a pose e depois aplica o carimbo de rosto e as transformações de sempre. As transformações de corpo inteiro continuam, combinadas.
   - Para isso, `gen.sprite()` guarda o builder e os parâmetros de render no `Sprite` (campo novo `_build`, fora da comparação).
4. **Rosto fixo.** O rosto continua posicionado pelo render em repouso. Partes da cabeça não têm `role` neste marco (sem cabeça que balança: evita desalinhar olhos e boca).
5. **Repouso intocado.** Pose vazia = bytes idênticos ao render atual. O primeiro quadro de `idle`, todos os quadros de animações sem pose e o ovo continuam batendo com o gabarito do M12.
6. **Orçamento.**
   - Quadros com pose custam um render cada. Medir o custo de gerar todas as animações de um estágio e manter `test_sprite_cost_is_small` e `test_draw_budget`.
   - Se o custo passar, gerar só as animações pedidas (já é lazy por animação) e reduzir quadros, nunca piorar o FPS.
   - O bench do app não pode subir RSS nem CPU de forma relevante (comparar com o M12).

## Restrições globais

- Só `engrama/app/art/**`, testes de arte, `spike/vpet2/**` (showcase e folhas), `docs/images/**`, README.
- Nada de `kernel`, `mind`, `modules`, `services`, `lab`, receitas, saves. `ANIMS` e os nomes de animação não mudam. Nenhum campo novo no genoma (`look`): tudo sai da semente e da linhagem, como no M11.
- Determinismo: as poses não sorteiam; se precisarem de variação, usar o `rng(seed, tag)` de `genes.py`.
- Gabarito:
  - os hashes de **repouso** (quadro 0 de `idle`, `evolve`, `dead`, ovo e as animações sem pose) não mudam;
  - os hashes que mudam de propósito são regenerados **uma vez**, na T6, depois da aprovação do usuário, com `ENGRAMA_REGEN_GOLDEN=1`, e o diff do JSON é listado no PR.

## Tarefas

Ordem: **T1 → T2 → {T3a, T3b em paralelo} → T4 → T5 (aprovação) → T6**.

### T1: Motor de pose (Sonnet)

- [ ] `Part.role`, `Part.pivot`, `Part.side`; `Builder` propaga o lado em `sym` e espelha o pivô em `flip()`.
- [ ] `core.posed(builder, pose)` e transformação por tipo de parte (testes unitários com builders pequenos: rotação de 90° de uma cápsula em torno do pivô, `alt` invertendo o lado, `R` só desloca).
- [ ] `Sprite` guarda o necessário para re-renderizar (builder, `N`, `FILL`, paleta, `n_base`); `frame_arrays` aceita poses; sem poses definidas, saída idêntica (gabarito do M12 passa inteiro).
- [ ] Commit `feat(m14): pose engine (part roles, pivots, posed render)`.

### T2: Marcação de papéis e juntas (Haiku, revisão do orquestrador)

- [ ] Nos helpers de `families/common.py` (`leg`, `upright`, `quad`) e em cada família, passar `role` e `pivot` para pernas, braços, caudas, asas, nadadeiras, orelhas e antenas. O pivô é o ponto de encaixe no corpo: primeiro ponto da cápsula, ou topo da elipse do membro.
- [ ] **Só** adicionar argumentos; nenhuma coordenada muda. O gabarito do M12 passa inteiro (o papel não afeta o render em repouso).
- [ ] Script no scratchpad lista, para cada uma das 24 combinações família × plano, as partes com papel por estágio. Anexar a tabela no relatório.
- [ ] Commit `feat(m14): roles and pivots on limbs of every family`.

### T3a: Poses de quatro famílias (Sonnet): dragão, fera, ave, inseto
### T3b: Poses de quatro famílias (Sonnet): planta, espírito, aquático, máquina

Cada uma num worktree próprio, editando só os módulos das suas famílias e um `poses/<familia>.py` por família (arquivos disjuntos).
- [ ] Para cada plano de corpo, poses de:
  - `walk`: 4 quadros, pernas alternadas, braços em contrafase; serpente, peixe e água-viva ondulam a cauda ou os tentáculos; ave em voo e mariposa batem asa; tanque e bulbo, que não têm perna, mexem antena, folha ou esteira;
  - `idle`: 2 quadros, cauda ou orelha sutil, 1 px;
  - `eat`: braço ou pata leva à boca quando houver braço;
  - `happy`: braços ou asas para cima;
  - `sleep`: membros recolhidos;
  - `sad`: orelhas e cauda caídas;
  - `jump` e `dance`: membros abertos e alternados.
  `sick`, `old`, `evolve` e `dead` ficam sem pose (repouso), salvo cauda caída em `old`.
- [ ] Amplitudes pequenas: rotações de 10° a 25°, deslocamentos de 1 a 2 px no tamanho final. Pixel art lê melhor com pouco movimento.
- [ ] Folha de revisão por família (`python -m spike.vpet2.sheets` estendido para animações; GIF por animação) em `art-review/m14/`, que é ignorado pelo git.
- [ ] Gabarito de repouso passa; os hashes de animação mudam (esperado). **Não** regenerar o JSON ainda.

### T4: Limpeza do dragão quadrúpede adulto e orçamento (Sonnet)

- [ ] Reduzir partes do dragão quadrúpede no estágio `adult` (limitação conhecida): menos espinhos e menos camadas de asa, mantendo a identidade. Isto muda o repouso desse plano de propósito. Listar os hashes afetados.
- [ ] Medir:
  - custo de `creature_frames` por animação e de todas as animações de um estágio (antes e depois);
  - `test_sprite_cost_is_small` e `test_draw_budget`;
  - bench do app (`tools/bench.py --app --seconds 30`) contra o número do M12.
  Ajustar quadros ou cache se passar.
- [ ] Testes novos (`tests/app/test_poses_m14.py`):
  - todas as 24 combinações têm ao menos um papel animado em `walk` (ou fallback documentado);
  - quadros de `walk` diferem entre si;
  - o rosto não se move entre quadros sem `dy`;
  - nenhum pixel sai do canvas;
  - o contorno continua fechado (sem buraco no contorno após girar membro).

### T5: Revisão do usuário (orquestrador)

- [ ] Gerar uma folha por família com todas as animações (GIFs e uma grade PNG) e o dragão quadrúpede antes e depois. Enviar ao usuário pela conversa.
- [ ] Coletar ajustes e voltar para T3a/T3b/T4 até aprovar.

### T6: Gabarito, showcase, docs e PR (Haiku + orquestrador)

- [ ] Regenerar `tests/fixtures/m12_sprite_hashes.json` com `ENGRAMA_REGEN_GOLDEN=1`; conferir que só mudaram animações com pose e o dragão quadrúpede adulto (script de diff do JSON).
- [ ] `SDL_VIDEODRIVER=dummy python -m spike.vpet2.showcase`: atualizar `docs/images/anims.png` e adicionar um GIF curto de `walk` no README.
- [ ] README PT/EN:
  - seção Arte: membros animados;
  - limitações: tirar "sem animação de membros" e "dragão carregado", se resolvidos;
  - linha M14 no roadmap.
- [ ] `version = "0.14.0"` (ou o próximo, conforme a ordem de merge com o M13).
- [ ] `ruff check .`, suíte e CI verdes; push; PR com antes e depois.

## Aceite do M14

1. As 24 combinações família × plano têm `walk` com membros em movimento (ou fallback justificado), e as demais animações com pose onde fizer sentido.
2. Repouso idêntico ao M12, salvo o dragão quadrúpede adulto (mudança listada).
3. Custos de sprite e de desenho dentro dos orçamentos; bench do app sem regressão relevante.
4. Folhas aprovadas pelo usuário.

## Riscos

| Risco | Mitigação |
|---|---|
| Girar membro abre buraco no contorno ou cria pixel solto | Teste de contorno fechado; cleanup do `render` já roda depois; amplitudes pequenas |
| Partes sobrepostas (perna atrás do corpo) aparecem na frente ao girar | `z` da parte não muda; pivô no encaixe; revisar nas folhas |
| Custo de render por quadro estoura o orçamento | Medir na T4; reduzir quadros; cache já é por animação |
| Marcação de papel muda pixels sem querer | T2 só adiciona argumentos; gabarito do M12 é o juiz |
| Conflito com M13 no README | M13 e M14 só tocam seções diferentes; quem mergear depois faz rebase |
