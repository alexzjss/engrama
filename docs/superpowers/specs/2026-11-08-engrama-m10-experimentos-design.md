# Engrama M10 — Experimentos de ML: design

**Status:** proposta para aprovação · **Data:** 2026-11-08 · **Base:** branch `m9` (PR #10). Fontes: arquitetura v2 §1 ("nada pode quebrar a criatura"), §4 (contrato de módulo, canais, receitas, famílias), §6 (laboratório) e §10 item 7 ("Experimentos: cada um vira apenas um módulo e uma receita"), o plano v2 (M1+M2: plataforma, sombra, replay, `compare`), a nota R21 do M2 (o que a SNN comprova), o M6 (várias vidas, causas de morte) e as medições da máquina de referência (§10).

O item 7 da arquitetura lista cinco experimentos. Embeddings já entraram no M9. O M10 faz os outros quatro: **CTRNN**, **modelo de mundo com curiosidade intrínseca**, **Thompson sampling** e **inferência ativa**.

## 1. Intenção

A plataforma do M1/M2 foi feita para que trocar a ideia de ML fosse trocar uma receita. Até agora só a SNN e o Q-learning tabular foram plugados. No M10 a plataforma é posta à prova com quatro ideias diferentes, cada uma como **módulo novo mais receita nova**, e com uma comparação reprodutível contra a criatura padrão:

- **CTRNN** (`temporal.ctrnn`): uma rede recorrente de tempo contínuo, com constantes de tempo de um minuto a um dia, no lugar da SNN. Escreve os mesmos canais `temporal.*` e tem a mesma leitura preditiva, então só a dinâmica muda.
- **Modelo de mundo com curiosidade** (`world.model` + `policy.curious`): um modelo direto pequeno prevê o que acontece depois de cada ação. O erro dessa previsão vira um bônus de recompensa intrínseca para um Q-learning.
- **Thompson sampling** (`policy.thompson`): um Q-learning bayesiano. Cada valor tem média e incerteza, e a proposta é uma amostra da crença. Assim a criatura explora o que ainda não conhece, não ao acaso.
- **Inferência ativa** (`policy.aif`): para cada ação, a política calcula a energia livre esperada. Ela combina o quanto o resultado previsto se afasta do que a criatura prefere (as preferências são priors sobre resultados) com o quanto a ação ensinaria sobre o mundo.

A criatura padrão **não muda**. `default-v1` continua byte a byte igual. Os experimentos vivem no laboratório: uma suíte nova roda as receitas com as mesmas sementes e perfis, e um relatório diz o que cada uma muda e o que não muda.

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Escopo | **[usuário]** M10 = os quatro experimentos da arquitetura v2 §10 item 7, menos embeddings (feitos no M9): CTRNN, modelo de mundo com curiosidade intrínseca, Thompson sampling e inferência ativa. Cada um é só um módulo (ou dois) e uma receita |
| Criatura padrão | **[usuário]** não muda: `recipes/default-v1.toml`, os módulos que ela usa e a saída do lab para ela ficam idênticos ao M9 (arquitetura v2 §1: "nada pode quebrar a criatura"). Um teste de gabarito guarda isso |
| Como escolher um experimento no app | **[pendente — recomendação: só no laboratório e na linha de comando.]** `python -m engrama --recipe <nome ou caminho>` já cria uma criatura nova com a receita, numa pasta de dados nova. A receita fica gravada no save e segue a criatura e as gerações dela. Nada muda na interface: nem menu, nem F-tecla, nem texto novo. **Alternativas:** (b) no modo dev (F12), o painel Gerações (F10) deixa escolher a receita da **próxima** vida; (c) a cada vida nova, uma tela pergunta qual mente ela terá, também no modo normal. A (c) foi descartada na recomendação porque os experimentos não estão validados para uso diário; a (b) custa painel, i18n e testes de UI, e pode ficar para quando algum experimento valer a pena |
| Canal novo `world.error` | **[pendente — recomendação: sim, só esse.]** `CHANNELS` ganha `world.error[1]` (0..1), o erro de previsão do modelo de mundo, como já previa a arquitetura v2 §4.4. Nenhum canal existente muda, e a receita padrão não o escreve, então a saída dela não muda. **Alternativa:** manter `CHANNELS` congelado e juntar o modelo de mundo e a curiosidade num módulo só (`policy.curious` com o modelo dentro). Perde-se a separação "modelo de mundo × aprendiz", e outro módulo não pode mais usar o erro |
| Promover um experimento a padrão | **[pendente — recomendação: não no M10.]** O M10 só mede. Trocar o padrão quebraria a regra do byte a byte e as criaturas que já existem; se o relatório mostrar ganho, a promoção vira uma decisão de um marco seguinte |
| Forma das comparações | **[pendente — recomendação: cada receita é a `default-v1` com uma troca só.]** Os casos: SNN → CTRNN; Q-learning → Q curioso (+ modelo de mundo); Q-learning → Thompson; Q-learning → inferência ativa. A utilidade, o PAD, os traços e as preferências ficam iguais, e assim a diferença medida é de uma peça. Uma receita exploratória `aif-solo-v1` (inferência ativa sem a utilidade) entra só como linha extra do relatório, fora da aceitação |

Continuam valendo, por decisão do usuário em marcos anteriores:
- PAD, Q-learning tabular contextual, SNN, deriva de traços e preferências como mente padrão (v1/M2);
- kernel determinístico; a mente só escolhe e o kernel executa e valida; política segura quando nada propõe (M1);
- várias vidas, doença e morte (M6), que viram métrica de sobrevivência no M10;
- ≤150 MB e ≤2% de CPU médio (M3, M8); local, offline, só numpy; PT/EN; sem números no modo normal; commits sem atribuição a IA.

## 3. Objetivos

1. **Quatro experimentos como módulos registrados.**
   - `temporal.ctrnn` (`engrama/modules/temporal/ctrnn.py`). Rede de `CTRNN_HIDDEN` unidades `tanh`, com constantes de tempo distribuídas em escala log de `CTRNN_TAU_MIN_BINS` a `CTRNN_TAU_MAX_BINS` (de 1 minuto a 1 dia), recorrência esparsa fixa com raio espectral `CTRNN_SPECTRAL_RADIUS` e integração de Euler em `CTRNN_SUBSTEPS` subpassos por bin.
     - Mesma entrada da SNN: tipos de evento do bin, as quatro metades da fase da hora e `user_active`.
     - Mesmos bins de `SNN_BIN_S`, invariantes ao `dt`.
     - Mesma leitura preditiva: LMS normalizado sobre traços centrados mais um viés, com as constantes `SNN_PRED_LR`, `SNN_BIAS_LR`, `SNN_SURPRISE_EMA`, `SNN_FAMILIARITY_BINS` e `SNN_FMEAN_RATE`.
     - Escreve `temporal.surprise`, `temporal.familiarity` e `temporal.expectation`.
     - Parâmetro `readout_hidden=False` para a ablação só com viés, como na SNN.
     - Os pesos recorrentes são fixos (um reservatório de tempo contínuo); só a leitura aprende.
   - `world.model` (`engrama/modules/world/model.py`, família nova `world`). Modelo direto linear, treinado online por LMS normalizado.
     - Entrada: o contexto (`world.hour`, `world.user_active`, `body.asleep`, `affect.pad`, `drives` e um viés) mais a ação em one-hot.
     - Saída prevista: os tipos de evento da transição (sigmoide) e a variação das necessidades por hora, cortada em ±1.
     - O erro quadrático médio da última transição, cortado em [0, 1], é escrito em `world.error`.
   - `policy.curious` (`engrama/modules/policy/curious.py`). Subclasse do `QLearningPolicy`, com a mesma tabela, o mesmo contexto, os mesmos `alpha` e `gamma` e a mesma proposta. A recompensa vira `reward_combine(rewards) + CUR_BETA · bônus`, e o bônus sai de `world.error` em um de dois modos (parâmetro `bonus`):
     - `"surprise"`: o erro acima da média móvel dele;
     - `"progress"`: o progresso de aprendizado por ação, ou seja, a queda do erro daquela ação.
   - `policy.thompson` (`engrama/modules/policy/thompson.py`). Q-learning bayesiano simplificado.
     - A média `μ[s,a]` é atualizada por TD, como no `QLearningPolicy`.
     - A incerteza é `sd[s,a] = sqrt(s2 / (1 + n[s,a]))`, com `n` = visitas que esquecem com meia-vida `TS_N_HALF_LIFE_DAYS` e `s2` = variância móvel do erro de TD, com piso `TS_NOISE_FLOOR²` e valor inicial `TS_SIGMA0²`.
     - A proposta é `μ + sd·z`, com `z ~ N(0, 1)` tirado do RNG do módulo, uma amostra por ação a cada decisão.
   - `policy.aif` (`engrama/modules/policy/aif.py`). Inferência ativa discreta mínima.
     - O contexto é o mesmo do Q-learning (32 estados, observados). Os resultados são os sete sinais de `REWARD_KEYS` como fatores binários, com contagens Beta por (contexto, ação, fator), que esquecem em direção ao prior com meia-vida `AIF_COUNT_HALF_LIFE_DAYS`.
     - Preferências como priors: o log da preferência de cada sinal é `AIF_PREF_SCALE · REWARD_WEIGHTS[k]`; a preferência por resposta do usuário escala com a sociabilidade.
     - `G(a) = Σ_k −E_q[ln p̃_k(o)] − AIF_NOVELTY_WEIGHT · Σ_k ganho de informação dos parâmetros_k`, e a proposta é `−G(a)`.
     - Horizonte de um passo; não usa RNG.
2. **Receitas.** Em `recipes/`, cada uma com nome e versão 1:
   - `ctrnn-v1` (SNN → CTRNN);
   - `shadow-ctrnn-v1` (padrão + CTRNN em sombra; ao vivo, idêntica ao padrão);
   - `curious-v1` (+ `world.model`; Q-learning → `policy.curious` com `bonus="surprise"`);
   - `curious-lp-v1` (o mesmo com `bonus="progress"`);
   - `thompson-v1` (Q-learning → Thompson);
   - `aif-v1` (Q-learning → inferência ativa);
   - `lab-shadow-all-v1` (padrão ao vivo + CTRNN, Thompson, inferência ativa e modelo de mundo em sombra: a mesma vida para todos e o pior caso de custo);
   - `aif-solo-v1` (exploratória, ver §2).
3. **Suíte de comparação no laboratório.** `python -m engrama.lab suite` roda receitas × perfis × sementes, com renascimento (várias vidas), e devolve JSON e uma tabela Markdown.
   - O padrão é a linha de base; cada experimento aparece com a diferença para ela e se o sinal da diferença foi o mesmo em todas as sementes.
   - Perfis: `attentive`, `absent`, `neglectful` (sobrevivência) e `routine`, o usuário periódico roteirizado do teste R21 do M2, que serve para medir a previsão.
   - Pode rodar em paralelo (`--jobs`), com resultado idêntico ao sequencial.
4. **Métricas para comparar.** São as do `compute_metrics` de hoje (bem-estar, entropia, taxas de resposta e de ignorado, PAD, vidas) mais:
   - satisfação das necessidades (1 − média das necessidades no tempo);
   - retorno extrínseco por dia (a mesma regra de crédito do aprendiz);
   - novidade por dia;
   - entropia das decisões e taxa de troca de ação;
   - Brier da previsão de `temporal.expectation` no próximo bin, ao vivo e de cada sombra;
   - erro médio de `world.error`;
   - sobrevivência: dias de vida, vidas terminadas e mortes por causa;
   - custo em ms por módulo, à parte, porque depende do relógio e não é determinístico;
   - métricas próprias dos módulos, por um método opcional `lab_metrics()` (por exemplo a fração do retorno que veio do bônus, a incerteza média do Thompson e a fração de `G` que veio da novidade).
   - A saída de `engrama.lab sim` e `compare` **não muda**: as métricas novas só existem na `suite`.
5. **Relatório.** `docs/superpowers/reports/2026-11-08-m10-experimentos.md` (mais o JSON da corrida), com a tabela da suíte, o que cada experimento muda, o que não muda e o que fica em aberto, no tom da nota R21 do M2: nada de "melhor" sem o mesmo sinal em todas as sementes.
6. **Saves.** Todo módulo novo grava `version` no `state_dict`. `{}` carrega como estado inicial; uma versão maior que a conhecida é recusada com `ValueError`. Salvar e carregar no meio de uma corrida continua bit a bit igual para cada receita nova. No renascimento os módulos novos recomeçam do zero, como o Q-learning.
7. **App.** O `--recipe` também aceita um nome de `recipes/` (`--recipe thompson-v1`).
   - A receita só vale para uma criatura nova. Numa pasta com save, o save manda (como hoje) e uma linha de log avisa da diferença.
   - A Visão da Mente (F2) mostra os módulos novos e as visualizações deles sem código de UI novo, porque usa o `viz()`.
8. **README** PT/EN: o que é cada experimento, como rodar a suíte, como criar uma criatura com uma receita experimental, e que o padrão não mudou.

## 4. Não objetivos

- Mudar a criatura padrão, os módulos dela ou a ordem dos RNGs dela.
- Interface para escolher experimento (fica a recomendação da §2).
- `torch`, `onnxruntime` ou qualquer dependência nova: só numpy.
- Aprender os pesos recorrentes da CTRNN (BPTT, FORCE). No M10 ela é um reservatório com leitura aprendida.
- Modelo de mundo profundo, RNN, ensemble ou dinâmica no espaço latente.
- Inferência ativa com estados ocultos (POMDP), inferência variacional de estados, horizonte maior que um passo, árvore de políticas ou aprendizado das preferências.
- Thompson com posterior Normal-Gamma completo por par ou com bootstrap de redes.
- Árbitro novo (bandit, subsunção, votação), que é outro experimento da arquitetura §4.2.
- Avaliação fora da política (IPS) válida para o Thompson: a probabilidade gravada é a do árbitro, dada a amostra, e não a da política marginal (§11).
- Ligar os experimentos ao LLM, à memória ou à percepção.

## 5. Anti-objetivos (falha mesmo que "funcione")

- Qualquer diferença na saída de `engrama.lab sim` com `default-v1` ou `minimal-v1`, no comportamento do app com a receita padrão ou nos saves que ele grava.
- Um módulo novo que use `np.random` global, a hora do relógio ou `time` para decidir (só o `self.rng` que a receita dá).
- Um módulo em sombra que mude a vida ao vivo (ação, RNG, canal sem prefixo `shadow/`).
- Uma receita experimental que pare a criatura (nenhuma ação, exceção fora do módulo, `NaN` num canal).
- Afrouxar ≤150 MB / ≤2% de CPU, ou um módulo novo que passe do orçamento de ms.
- Um relatório que declare um experimento melhor sem o mesmo sinal em todas as sementes, ou que esconda uma métrica pior.
- Um save de um experimento que não continue igual depois de carregar.
- Mudar `ACTIONS`, `EVENT_KINDS`, `REWARD_KEYS`, `NEED_KEYS`, `FOOD_IDS`, `TRAIT_KEYS`, `DIGITAL_IDS`, `VARIANTS`, `DISPLAY_MODES`, ou qualquer canal existente.

## 6. Restrições

Todas as restrições globais dos marcos anteriores continuam valendo:
- kernel determinístico; a saída do lab para `default-v1` fica igual à do M9 (gabarito `tests/fixtures/m6_sim_1d_seed1_attentive.json` e um gabarito novo de várias vidas gravado com o código do M9);
- regras de importação de `tests/test_architecture.py`. Os módulos importam só `engrama.mind`, `engrama.vocab`, `engrama.balance` e a própria família: `policy.curious`, `policy.thompson` e `policy.aif` podem reusar `engrama.modules.policy.qlearning`, mas `policy.curious` **não** importa `engrama.modules.world` e só conversa com o modelo de mundo pelo canal `world.error`;
- ≤150 MB RSS e ≤2% de CPU médio, sem mudar os limites dos testes;
- PT/EN em todo texto novo; sem números no modo normal (o M10 não tem texto novo de UI);
- local e offline; dependências: pygame-ce, numpy, psutil; commits sem atribuição a IA.

Além disso:
- **Determinismo.** Mesma receita, semente, perfil e `dt`: mesma saída da suíte, exceto `module_ms`. Isso vale com `--jobs 1` ou `--jobs N`. Os módulos novos sorteiam só com `self.rng`. A inferência ativa, a CTRNN depois de criada e o modelo de mundo não sorteiam nada.
- **Sombra não vaza.** Uma sombra escreve só em `shadow/<nome>/...` e usa o próprio RNG, que fica depois do árbitro na ordem de `spawn`. `shadow-ctrnn-v1` e `lab-shadow-all-v1` têm as mesmas ações ao vivo que `default-v1` com a mesma semente.
- **Crédito de recompensa.** As experiências de `dt == 0`, que movem `user_response`/`ignored` para o pedido de atenção que abriu a janela (`AskCredit`), são tratadas à parte em cada aprendiz novo (§8, item 1 da §11).
- **Orçamento por módulo.** No lab com `dt = 60`, cada módulo novo fica com `mean_ms ≤ EXP_BUDGET_MS`. `budget_ms` é o padrão (5 ms), salvo a CTRNN (`CTRNN_BUDGET_MS`).
- **Saves versionados por módulo** (§3, item 6). `SAVE_VERSION` da persistência não muda.
- **A suíte não muda o runtime.** Ela roda `Runtime.run(dt, dt, user)` tick a tick e lê o quadro-negro e os módulos entre os ticks, sem tocar em `runtime.py`, `metrics.py` nem `explog.py`.

## 7. Critérios de aceitação

Testes headless, com relógio simulado e `dt = 60`, salvo indicação:

1. **Padrão intocado.**
   - `engrama.lab sim` com `default-v1`, 1 dia, semente 1, `attentive` é igual ao gabarito do M6.
   - Com `default-v1`, 7 dias, semente 2, `neglectful` (morte e renascimento), é igual ao gabarito novo gravado com o código do M9.
   - Os arquivos `default-v1.toml` e `minimal-v1.toml` têm o mesmo SHA-256 do M9, e as entradas antigas de `REGISTRY` não mudam.
   - `CHANNELS` é o do M9 mais `world.error` (se aceito).
   - `Config().recipe == "default-v1"`.
2. **Cada receita nova roda.** Três dias com `attentive` e cinco com `neglectful` (com renascimento), sem módulo desabilitado, sem exceção, sem `NaN` e com a criatura sempre agindo.
3. **Determinismo.**
   - Duas corridas iguais dão a mesma saída da suíte (sem `module_ms`), e `--jobs 2` dá a mesma saída que `--jobs 1`.
   - Para cada receita nova, salvar no meio de uma corrida, carregar e continuar dá o mesmo log que a corrida sem parar.
4. **Sombra.** `shadow-ctrnn-v1` e `lab-shadow-all-v1` escolhem as mesmas ações que `default-v1` (mesma semente e perfil, 2 dias), e a sombra da CTRNN tem Brier próprio na suíte.
5. **Cada mecanismo faz o que diz** (evidência do mecanismo, não de que é melhor):
   - **CTRNN:** no usuário `routine`, sementes 1, 2 e 3, o Brier da CTRNN não é pior que o da ablação só com viés. O ganho relativo é registrado no relatório, sem limiar exigido. A surpresa de um evento raro é maior que a de um comum, e o modelo é invariante ao `dt` (bins).
   - **Modelo de mundo:** num mundo roteirizado estacionário o erro cai (a média do último quarto fica abaixo da do primeiro).
   - **Curiosidade:** num roteiro sintético em que só a ação X tem resultado imprevisível, sem recompensa extrínseca, `Q[s, X]` passa as outras ações. Ao mesmo tempo, o bônus de uma transição é creditado à ação dela, não à seguinte. No modo `"progress"`, o bônus de uma ação cujo erro parou de cair volta a zero.
   - **Thompson:** `sd` cai com as visitas e volta a subir com o esquecimento. Num bandit sintético de dois braços, a fração de escolhas do melhor braço passa de 0,9. Com `sd → 0`, a proposta é a média (Q-learning).
   - **Inferência ativa:** com contagens que mostram o resultado preferido para a ação A, A tem o menor `G`. Com contagens iguais, a ação menos visitada tem o menor `G` (novidade). Sem preferência e sem novidade, `G` é igual para todas. Não usa RNG (mesmas propostas com qualquer `self.rng`).
6. **Orçamento.**
   - `tools/bench.py --recipe <receita> --seconds 30` (headless) para cada receita nova e `--app --recipe lab-shadow-all-v1 --seconds 30` ficam em ≤150 MB e ≤2% de CPU.
   - `mean_ms ≤ EXP_BUDGET_MS` para cada módulo novo no lab.
   - Os dois testes de orçamento do M3/M7 continuam verdes sem mudança.
7. **Suíte.**
   - `python -m engrama.lab suite` com uma configuração pequena gera o JSON e a tabela.
   - As métricas de base da linha `default-v1`/`attentive`/semente 1/1 dia são iguais à saída de `sim`.
   - `vs_baseline` e `consistent_sign` estão certos num exemplo conhecido.
8. **Saves.** `state_dict` de cada módulo novo tem `version`. `load_state_dict({})` deixa o estado inicial; uma versão maior levanta `ValueError`. O estado passa pela persistência real (`.npz` + `.json`) sem perda.
9. **App.**
   - `python -m engrama --recipe thompson-v1 --no-llm --frames 120 --data-dir <tmp>` sai com 0, e o save gravado tem a receita `thompson-v1`.
   - Rodar de novo na mesma pasta com `--recipe default-v1` mantém a `thompson-v1` e registra o aviso.
   - A Visão da Mente monta as visualizações dos módulos novos sem exceção.
10. **Arquitetura e vocabulário:** `test_architecture` verde, com a família `world`; as tuplas do vocabulário não mudam.
11. **Relatório** presente, com a tabela gerada pela suíte (padrão: 3 sementes × `attentive`/`absent`/`neglectful` × 7 dias, mais `routine` × 4 dias) e os comandos para reproduzir.

## 8. O que fica com o builder

- A inicialização exata da CTRNN: máscara esparsa, escala para o raio espectral (por potência ou autovalores na criação) e ganho de entrada.
- O formato das visualizações (`viz()`) de cada módulo novo, dentro dos tipos existentes (`series`, `heatmap`, `bars`, `table`).
- Os textos de `reason` das propostas (em PT, como os do `policy.utility` e do `policy.qlearning`), não vazios e curtos.
- O formato da tabela Markdown da suíte e do relatório.
- A calibração, na Tarefa 6, dos valores do bloco `# Task M10` e dos pesos das receitas experimentais, dentro das faixas dadas no plano, registrada no relatório.
- Como a suíte divide as corridas entre processos (o resultado não pode depender disso).

## 9. Decisões minhas (para o usuário conferir)

- **Uma troca por receita**, do jeito que a §2 recomenda, e o resto da mente igual ao padrão. O peso de `policy.curious` e de `policy.thompson` no árbitro é o do Q-learning (0,6). O de `policy.aif` parte de 0,6 e pode ser calibrado entre 0,2 e 1,0 na Tarefa 6, porque a escala de `−G` (nats) não é a de `Q`.
- **O árbitro não muda.** O Thompson propõe amostras e o árbitro softmax continua por cima, com a mesma temperatura. Isso mantém a comparação limpa e o contrato intacto. O preço é que a probabilidade gravada é condicional à amostra (§11).
- **CTRNN com a mesma leitura e os mesmos bins da SNN.** Assim a comparação mede a dinâmica (disparos com STDP × contínua com várias escalas de tempo), não a leitura. O tamanho é fixo (`CTRNN_HIDDEN`), sem crescer por estágio: custo constante e previsível.
- **Curiosidade com crédito atrasado de um tick.** O modelo de mundo aprende a transição `e_t` e escreve o erro dela no `step` do mesmo tick, que acontece depois de todos os `learn`. Por isso o `policy.curious` guarda a transição e só a completa no `learn` seguinte, quando `world.error` dela já está em `exp.channels`. Experiências de `dt == 0` são aplicadas na hora, sem bônus. Isso mantém os módulos separados (só pelo canal) sem mudar o runtime.
- **Bônus "surpresa acima do normal" como padrão** (`curious-v1`) e "progresso de aprendizado" como variante (`curious-lp-v1`). A surpresa é a forma clássica (estilo ICM) e é sensível a ruído irredutível (o problema da "TV com chiado"); o progresso resiste a isso, mas é um sinal mais fraco. O relatório compara os dois.
- **Inferência ativa mínima e honesta.** Contexto observado (sem estados ocultos), horizonte de 1 passo, resultados = sinais de recompensa do kernel, preferências = `REWARD_WEIGHTS` em nats. A parte pragmática fica `−Σ q ln p̃`, porque com estados observados risco + ambiguidade se reduzem à entropia cruzada com as preferências. A parte epistêmica é o ganho de informação dos parâmetros Beta, na aproximação usada no pymdp (`½(1/α_o − 1/α_0)`). Com isso ela fica parecida com um bandit bayesiano com bônus de informação, e o relatório diz isso.
- **Crédito do pedido de atenção na inferência ativa.** Numa linha de `ask_attention`, os fatores `user_response`/`ignored` só são atualizados pela experiência de crédito (ou pela própria linha, se a janela fechou nela); as outras ações contam esses fatores como 0. Assim cada janela de pedido conta uma vez.
- **Métricas novas só na `suite`.** `compute_metrics` não muda, para a saída de `sim` continuar igual ao gabarito. As métricas da suíte saem de uma sonda que lê o quadro-negro tick a tick e do `lab_metrics()` opcional (duck typing, fora do contrato `Module`).
- **Usuário `routine` no laboratório.** A suíte ganha uma cópia exata do `_RoutineUser` do teste R21 do M2, para a previsão da CTRNN ser comparada com o número que já existe para a SNN. `PROFILES` não muda.
- **`--recipe` aceita nome.** É uma conveniência: `thompson-v1` resolve para `recipes/thompson-v1.toml`, e um caminho continua funcionando. Não há texto novo na UI.
- **Constantes** num bloco `# Task M10` de `engrama/balance.py`. As antigas não mudam.
- **Relatório em `docs/superpowers/reports/`**, em PT, com o JSON ao lado para reproduzir.
- **Versão 0.10.0.**

## 10. Medições na máquina de referência

Máquina: CachyOS, AMD Ryzen 5 7520U (4 núcleos / 8 threads), 7,2 GB de RAM; código do `m9` (`bf3d7f1`); `SDL_VIDEODRIVER=dummy`.

| Medida | Valor |
|---|---|
| `engrama.lab sim`, `default-v1`, 1 dia, `attentive`, `dt=60` | 2,1 s de parede (processo inteiro); 1,39 s só a simulação, ≈0,97 ms por tick |
| `engrama.lab sim`, `minimal-v1`, 1 dia | 0,8 s |
| `engrama.lab sim`, `default-v1`, 7 dias, `absent` | 11,1 s |
| `engrama.lab sim`, `default-v1`, 10 dias, `neglectful` | 15,2 s; morte por negligência no dia 5,0 e renascimento (2 gerações) |
| `mean_ms` por módulo, `default-v1`, 1 dia, `dt=60` | `temporal.snn` 0,65; `affect.pad` 0,03; `drives.needs` 0,016; os outros < 0,01 |
| RSS do processo do lab (1 dia) | ≈42 MB |
| Brier no usuário `routine` (teste R21), semente 1, 4 dias | SNN 0,00528; ablação só com viés 0,00551 (ganho de 4,2%); ≈5 s por corrida |

Consequências:
- A suíte padrão do relatório (8 receitas × 3 sementes × 3 perfis × 7 dias, mais `routine` × 4 dias) custa em torno de 8 × 3 × (3 × 11 + 5) s ≈ 15 min em sequência, e ≈4–5 min com `--jobs 4`. Os testes automáticos usam uma suíte pequena (1 dia, 1 semente, 2 receitas).
- O orçamento sobra: a mente padrão inteira custa menos de 1 ms por tick no lab, e no app roda a 1 Hz. Os módulos novos são pequenos (a CTRNN tem 64 × 64 pesos e 4 subpassos por bin; o modelo de mundo, 16 × 22; as tabelas do Thompson e da inferência ativa, menos de 4 mil números cada). O pior caso medido vai ser o da `lab-shadow-all-v1`.
- O ganho da SNN sobre a ablação (≈4% na semente 1) é a referência com que a CTRNN vai ser comparada no mesmo usuário e nas mesmas sementes.

## 11. Revisão — pontos de risco

1. **Crédito da curiosidade.** Se o bônus for creditado à ação seguinte, a curiosidade vira ruído. O atraso de um tick (§9) e o teste sintético do critério 5 cobrem isso. Um renascimento ou um `load` no meio precisam levar a transição guardada junto (`state_dict`).
2. **"TV com chiado".** Eventos do usuário simulado são aleatórios (Poisson) e nenhuma ação os explica. No modo `"surprise"` a criatura pode ficar presa ao que é só ruído. O modo `"progress"` e a entropia das decisões no relatório mostram se isso acontece.
3. **Escala do `−G`.** Nats contra valores de `Q` no mesmo árbitro: a inferência ativa pode dominar ou sumir. A calibração do peso fica na Tarefa 6, dentro de uma faixa, registrada no relatório.
4. **Probabilidade gravada no Thompson.** A probabilidade gravada é a do árbitro dada a amostra, não a marginal da política. O IPS (`lab/ope.py`) sobre logs do Thompson fica enviesado, e o relatório não usa IPS para ele.
5. **`dt` do modelo de mundo.** As variações por hora são invariantes ao `dt`, mas a chance de um evento por transição depende do tamanho do tick (60 s no lab, 1 s no app). O modelo foi pensado para o lab. Se no futuro a escolha (b) ou (c) da §2 levar o experimento ao app, o erro muda de escala (anotado no README).
6. **Estabilidade da CTRNN.** Com constante de tempo mínima de 1 bin e 4 subpassos, o Euler é estável (passo de 0,25 τ). O raio espectral < 1 evita explosão. Um teste de 30 dias sem `NaN` e com estados limitados cobre isso.
7. **Poucas sementes.** Com 3 sementes não há significância estatística. O relatório usa "mesmo sinal em todas as sementes" como critério mínimo e diz isso.
8. **Comparação que parece da peça, mas é da receita.** No M2 (R21), `minimal` × `default` era diferença de receita. Aqui, cada receita troca uma peça só, mas a peça nova muda o PAD (CTRNN) ou as ações (políticas), e isso muda os traços e as preferências pela vida afora. O relatório separa os efeitos diretos (Brier, erro, incerteza) dos indiretos (bem-estar, entropia, sobrevivência).
