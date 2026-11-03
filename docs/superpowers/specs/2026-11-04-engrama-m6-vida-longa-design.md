# Engrama M6 — Vida longa: design

**Status:** proposta para aprovação · **Data:** 2026-11-04 · **Base:** branch `main` com M5 (PR #5). Fontes: spec v2 §10 (M6), spec v1 §5.9–5.10 e os designs M4/M5.

## 1. Intenção

A criatura passa a ter **uma vida inteira**: evolui por ramos que dependem de como foi cuidada, de quem ela se tornou e do que viu você fazer; adoece por descuido ou por azar; envelhece; e morre. Da morte nasce um **ovo novo**, que não é ela de volta, mas carrega um pouco da personalidade dela e 1–3 lembranças que aparecem como sonho ou déjà-vu. Um painel guarda a história das gerações.

O roadmap juntava vida longa e presença (overlay, necessidades digitais). **Por decisão do usuário, o M6 é só vida longa; presença vira o M7.**

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Escopo | **M6 = vida longa**, M7 = overlay e necessidades digitais. |
| Morte | **Existe de verdade**, por velhice ou por descuido. |
| Duração | **~2–3 meses** do ovo ao final com bom cuidado (os mínimos atuais somam ~74 dias, mantidos), mais **~1 mês** de final até a velhice levar. Vida total ~3–3,5 meses. |
| O que decide o ramo | **Cuidado, personalidade e também o que ela percebe** (interesses por categoria de app). |
| Nº de ramos | **4–5 por estágio** (criança, adulto, perfeito, final). |
| PC desligado | **Nunca morre offline.** O tempo desligado envelhece, mas não adoece nem mata. |
| Na tela | **Aviso antes e despedida**: doença grave ou velhice dão sinais claros por um tempo; se morrer, cena de despedida, uma fala final e o ovo novo. |
| Herança | **Viés de personalidade** e **memória ancestral**. A aparência do ovo novo é toda nova. |
| Visual por ramo | **Partes e paleta por ramo**, tudo procedural. |
| Doença | **Descuido e também resfriados aleatórios raros**; existe um **remédio** no menu. |
| Resfriado | **~1 por mês, curto** (algumas horas), nunca mata se for cuidado. |
| Gerações | **Painel com histórico.** |
| Memória da nova geração | **Começa do zero mais as lembranças ancestrais.** O banco antigo é **arquivado**, não apagado. |
| Testes | **Simulação no lab**: vidas inteiras com perfis de usuário, métricas de ramo e de causa de morte. |

## 3. Restrições que continuam

- O **kernel** continua determinístico (mesma semente → mesma vida) e não importa `mind`, `modules`, `lab` nem `services`.
- `EVENT_KINDS` **não muda** (dimensão de entrada da SNN). Nenhuma entrada lida por módulos existentes muda de forma.
- Saves antigos (M1–M5) **abrem** sem erro: os campos novos têm padrão.
- Orçamento: ≤150 MB RSS, ≤2% de um núcleo; a simulação de 30 dias continua < 2 min.
- PT/EN em toda fala e UI. Sem dígitos no modo normal da UI, como hoje.
- Tudo local; nenhuma rede.

## 4. Ciclo de vida

Estágios continuam `egg → baby → child → adult → perfect → final`. O M6 acrescenta:

- **Ramo por estágio.** Ao entrar em `child`, `adult`, `perfect` e `final`, o kernel escolhe um ramo (§5). A **linhagem** (lista de ramos) é guardada; `Genome.branch` passa a ser o ramo atual.
- **Velhice.** No `final`, depois de `FINAL_LIFESPAN_S = 30 dias` (tempo de vida, conta offline), a criatura entra em **velhice**: anda mais devagar, dorme mais, a fala fica mais calma, e um sinal discreto aparece no HUD. A morte por velhice acontece **só com o app aberto**, depois de pelo menos `OLD_AGE_WARN_S = 3 dias` de velhice **online**, num momento calmo (acordada, sem tela cheia, sem chat em andamento). Se o PC ficou desligado além do prazo, a velhice começa na volta e o aviso de 3 dias online ainda vale.
- **Evolução visível.** Uma animação de evolução (~3 s: piscar, brilho, troca de forma) e uma fala curta de "virei outra coisa".

## 5. Ramos

**Minha decisão (o builder pode ajustar nomes e pesos):**

Entradas, todas determinísticas:
- `care_quality` (já existe, EMA de 6 h) e também a **média de cuidado do estágio inteiro** (nova, `stage_care_mean`).
- **Traços** atuais (curiosidade, sociabilidade, paciência, independência, criatividade), que vivem na mente. O runtime/host os entrega ao kernel a cada tick por `Kernel.observe_traits(vec)`; o kernel guarda só o último valor (sem importar a mente).
- **Interesses**: tempo acumulado por **grupo de interesse** a partir dos eventos `app_focus` (só a categoria, que já chega ao kernel). Grupos em `vocab.INTEREST_GROUPS` mapeiam as categorias da percepção (PT: `jogo`, `musica`, `programacao`, …) e as do usuário simulado (EN: `game`, `editor`, …) para: `jogos`, `arte` (música, vídeo, desenho), `tecnologia` (programação, terminal), `social` (chat, navegador), `trabalho` (escritório). "privado" e vazio não contam.
- **Ramo anterior** (a linhagem limita e favorece opções).

Regra: cada ramo tem uma função de pontuação (soma ponderada das entradas acima, com pré-requisitos opcionais). Vence a maior; empates por hash da semente. **O ramo de descuido vence sempre que `stage_care_mean < 0.45`**, com uma exceção: quem veio de um ramo de descuido e teve cuidado bom no estágio (`≥ 0.7`) pode "se redimir" e sair dele.

Tabela inicial:

| Estágio | Ramos (PT / EN) | Ênfase |
|---|---|---|
| child | brincalhão / playful · curioso / curious · sonhador / dreamy · arisco / skittish | sociabilidade · curiosidade · criatividade+paciência · descuido |
| adult | companheiro / companion · explorador / explorer · artista / artist · técnico / tinkerer · sombrio / shadow | sociabilidade+cuidado · curiosidade+independência · criatividade ou interesse `arte` · interesse `tecnologia`/`trabalho` · descuido |
| perfect | guardião / guardian · sábio / sage · virtuoso / virtuoso · aventureiro / adventurer · rebelde / rebel | cuidado alto + linhagem social · paciência+curiosidade · linhagem artista+`arte` · interesse `jogos`+independência · descuido ou linhagem sombria |
| final | lendário / legendary · mestre / master · eco / echo · sombra / umbra | cuidado alto a vida toda · traço dominante muito alto · interesse dominante da vida · descuido |

O nome mostrado na UI é o do ramo atual (sem número).

## 6. Saúde e doença

`Health` (hoje um stub) vira:

- **Estado:** `healthy`, `sick`; `kind` = `neglect` ou `cold`; `severity` 0..1; `grave` quando `severity ≥ 0.8`; tempo grave acumulado online.
- **Descuido:** média das necessidades `> 70` por `NEGLECT_SICK_AFTER_S = 6 h` (online) → `sick/neglect` com severidade 0.3. A severidade sobe enquanto as necessidades ficam altas e desce com cuidado (média `< 40`); em 0 cura.
- **Resfriado:** risco por hora tal que dá **~1 por 30 dias** de tempo online, sorteado pelo `rng` do kernel (determinístico). Dura 3–8 h, severidade máxima 0.4, cura sozinho, nunca fica grave se as necessidades forem atendidas.
- **Remédio:** item novo no menu de comida (`remedio`, a partir de bebê). Cura um resfriado na hora e tira 0.5 de severidade de descuido; no máximo um a cada 6 h (depois disso não faz efeito e ela faz careta). Dar remédio a quem está saudável não faz nada.
- **Efeitos:** doente usa a animação `sick` (já existe), tira `play_alone`, `explore` e `show_something` das ações disponíveis, e a fala fica mais curta e abatida. Grave mostra um aviso claro no HUD (texto PT/EN, sem dígitos) e ela pede ajuda.
- **Morte por descuido:** grave por `GRAVE_DEATH_AFTER_S = 24 h` **online** → morte. Cuidar durante esse tempo tira do grave.
- **Offline:** `offline_catchup` envelhece e mexe nas necessidades (como hoje, teto 70), mas **não avança a saúde**: não adoece, não piora, não morre. Sai igual entrou.

A saúde vai para a mente pelo canal novo `body.health` (`[sick, severity]`), que nenhum módulo existente lê; a mudança de comportamento é pela lista de ações disponíveis. `Snapshot` ganha `sick`, `grave`, `old`, `branch`, `generation`.

## 7. Morte, despedida e renascimento

1. O kernel marca `dead` com a causa (`old_age` ou `neglect`) e para de agir.
2. **Despedida na tela:** a criatura deita, a cor esmaece; uma fala final curta (LLM se estiver pronto, com um prompt de despedida, senão um balbucio carinhoso); depois fica só o contorno, e um ovo novo aparece. A cena dura ~10 s e pode ser pulada com clique depois da fala.
3. **Registro da geração** (novo arquivo `data/generations.json`, lista): número, linhagem, ramo final, nascimento e morte (datas do relógio de parede), duração em dias, causa, a semente do genoma (para redesenhar a miniatura) e as lembranças ancestrais escolhidas.
4. **Memória ancestral:** no momento da morte, o serviço de memória escolhe até 3 episódios mais marcantes (maior `importance`, desempate por valência absoluta e recência), sem fatos sobre o usuário e respeitando a lista de bloqueio. O resumo é guardado.
5. **Arquivo:** `memory.sqlite` vai para `data/generations/<n>/memory.sqlite` (o save também). Nada é apagado; "esquecer tudo" no F7 continua funcionando para a geração atual, e o painel de gerações tem "apagar arquivo desta geração".
6. **Renascimento:** semente nova derivada da antiga e do número da geração; genoma **todo novo** (sem herança visual, por decisão do usuário); módulos da mente **novos**; memória nova com as lembranças ancestrais gravadas como episódios `kind="ancestral"`. Configuração, permissões, lista de bloqueio, temas silenciados e categorias de app **continuam** (são escolhas do usuário, não da criatura).
7. **Viés de personalidade:** os traços iniciais do filho = `INITIAL_TRAITS + 0.25 × (traços finais do pai − INITIAL_TRAITS)`. Entram pelo `load_state_dict` do módulo de traços.
8. **Déjà-vu:** o recall pode trazer um episódio ancestral quando as palavras batem; a persona sabe que é "um sonho de antes de nascer" e fala disso assim. A iniciativa do M4 ganha um tipo raro `ancestral` (mesma cota).

## 8. Arte

- `Look` ganha `branch` e `lineage`. Cada ramo define **sobreposição de partes** (orelhas/chifres, cauda, olhos, padrão), **ajuste de paleta** (desvio de matiz/saturação, ex.: sombrio mais escuro, artista mais saturado) e **um acessório** procedural (ex.: antena, capa, coroa, fones). Tudo procedural, a partir do genoma.
- `adult`, `perfect` e `final` deixam de reusar a arte da criança: tamanhos maiores (ex.: 28, 32, 32 px de grade) e proporções próprias.
- Animações novas: `evolve` (transição), `old` (variação lenta do idle), `dead` (deitada esmaecendo). `sick` já existe.
- O cache de sprites continua por chave; trocar de ramo invalida só a entrada daquele ramo.

## 9. UI

- **HUD:** nome do ramo; sinal de doente/grave/velhice (texto e ícone, sem dígitos).
- **Menu de comida:** item remédio.
- **Painel de gerações (F10):** lista das vidas (miniatura, linhagem, duração em palavras — "uns três meses" —, causa em palavras), e por geração "apagar arquivo". Modo dev mostra os números.
- **Cena de evolução** e **cena de despedida** (§4, §7).

## 10. Lab

- `engrama.lab sim` passa a rodar **várias vidas** num run: quando a criatura morre, o runtime faz o renascimento igual ao app (sem serviços: memória ancestral fica vazia) e segue. Mesma semente → mesma sequência de gerações.
- Perfis: usar `attentive` (cuidadoso), `absent` e `gamer`, e criar `neglectful` (quase nunca alimenta nem dá carinho).
- Métricas novas no `report`: por geração, linhagem, duração, horas doente, resfriados, causa da morte; agregado de distribuição de ramos por perfil.
- Para vidas de meses, a simulação usa passos grandes como hoje; o critério é 200 dias simulados em < 8 min.

## 11. Critérios de aceite (testes)

- Determinismo: mesma semente e perfil → mesma linhagem, mesmas doenças, mesma data de morte.
- `attentive`: chega ao `final` em ~75–90 dias, morre de velhice entre ~105–125 dias, nunca morre de descuido.
- `neglectful`: adoece por descuido, fica grave e morre antes do `final`.
- Perfis diferentes dão linhagens diferentes (ao menos `attentive` × `neglectful` × `gamer` diferem no adulto); `gamer` puxa o ramo de interesse em jogos em pelo menos uma das sementes 1–3.
- Offline: um run com 60 dias offline seguidos não adoece nem mata; a velhice ainda espera os 3 dias online de aviso.
- Resfriados: em 120 dias online, entre 1 e 8.
- Remédio cura resfriado; cooldown respeitado.
- Renascimento: genoma novo, mente nova, traços com viés de 25%, memória nova com ≤3 episódios ancestrais, config/permissões/bloqueio mantidos, arquivo da geração anterior existe.
- Saves de M5 abrem; nenhum `EVENT_KINDS` mudou; arquitetura passa.
- Bench do app continua ≤150 MB e ≤2% de CPU.

## 12. Fica para depois

- Overlay no desktop, notificações, necessidades digitais e comportamentos extras → **M7**.
- Herança de aparência e de gostos de comida (o usuário não quis agora; `Genome.inherit` fica sem uso).
- Modo de tempo acelerado dentro do app (o usuário preferiu testar no lab).
- Escolher o momento de chocar o ovo novo.
