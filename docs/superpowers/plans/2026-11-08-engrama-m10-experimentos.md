# Engrama M10 — Experimentos de ML: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** pôr a plataforma do M1/M2 à prova com quatro experimentos de ML. Cada um é só um módulo (ou dois) e uma receita, e todos são comparados com a criatura padrão no laboratório:
- **CTRNN** no lugar da SNN (`temporal.ctrnn`);
- **modelo de mundo com curiosidade intrínseca** (`world.model` + `policy.curious`);
- **Thompson sampling** no lugar do Q-learning (`policy.thompson`);
- **inferência ativa** no lugar do Q-learning (`policy.aif`).

A receita `default-v1` e tudo o que ela produz ficam byte a byte iguais ao M9.

**Arquitetura:**
- Módulos novos em `engrama/modules/temporal/ctrnn.py`, `engrama/modules/world/model.py` (família nova `world`), `engrama/modules/policy/{curious,thompson,aif}.py`. São registrados em `REGISTRY` e plugados só por receita. Eles se falam só por canais: o único canal novo é `world.error`.
- O `policy.curious` é subclasse do `QLearningPolicy`; o `policy.thompson` e o `policy.aif` reusam o `state_index` dele (mesma família). Nenhum arquivo existente de módulo é editado.
- Uma suíte nova no lab (`engrama/lab/suite.py`, `engrama/lab/expmetrics.py`, subcomando `suite`) roda receitas × perfis × sementes com várias vidas e compara cada experimento com o padrão. `sim`, `compare`, `report`, `replay`, `runtime.py`, `metrics.py` e `explog.py` não mudam.
- Um relatório (`docs/superpowers/reports/2026-11-08-m10-experimentos.md`) registra a comparação.
- No app, só o `--recipe` passa a aceitar nome; a interface não muda.

**Stack:** Python 3.13, numpy, stdlib (`multiprocessing`, `tomllib`, `hashlib`), pygame-ce 2.5 e psutil. Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-08-engrama-m10-experimentos-design.md`. As seções 2, 3, 5, 6, 7 e 9 são requisito; a §10 dá os tempos medidos e a §11 os riscos. Contexto: arquitetura v2 (§4 contrato e famílias, §6 laboratório), plano v2 (sombra, replay, `compare`) e a nota R21 do M2.

**Antes de começar:** o usuário respondeu as decisões da spec §2 (2026-11-03) e aceitou todas as recomendações. Este plano segue essas decisões:
- só lab/CLI (`--recipe` na linha de comando, em pasta de dados nova), sem UI;
- `world.error` entra em `CHANNELS` (único canal novo);
- nenhuma promoção a padrão no M10;
- uma troca por receita, e `aif-solo-v1` só como linha extra do relatório, fora da aceitação.

## Restrições globais

- Branch `m10`. Cada agente começa com `git reset --hard m10` no seu worktree.
- **Padrão intocado:**
  - `recipes/default-v1.toml`, `recipes/minimal-v1.toml`, `engrama/kernel/**`, `engrama/lab/{runtime,metrics,explog,replay,ope,simuser}.py`, `engrama/mind/{scheduler,arbiter,recipe,helpers}.py` e os módulos existentes (`engrama/modules/{affect,drives,prefs,traits}/**`, `temporal/snn.py`, `policy/{utility,qlearning}.py`) **não são editados**;
  - em `engrama/mind/contracts.py` só entra a linha de `world.error` em `CHANNELS`, e em `engrama/mind/registry.py` só entram linhas novas;
  - se um teste provar bug num desses arquivos, reportar, não corrigir.
- **Gabaritos:**
  - `tests/fixtures/m6_sim_1d_seed1_attentive.json` (já existe);
  - `tests/fixtures/m9_sim_7d_seed2_neglectful.json`, gravado na T0 com o código do M9 **antes de qualquer outra mudança**;
  - os dois são comparados com a saída de `engrama.lab sim` com `default-v1` em todas as ondas.
- **Não mudam:** `ACTIONS`, `EVENT_KINDS`, `REWARD_KEYS`, `NEED_KEYS`, `FOOD_IDS`, `TRAIT_KEYS`, `DIGITAL_IDS`, `VARIANTS`, `DISPLAY_MODES`, os canais existentes e `SAVE_VERSION`. `CHANNELS` ganha só `world.error`.
- **Determinismo:**
  - módulos novos sorteiam só com `self.rng`; nada de `np.random.*` global, `random`, `time` ou relógio de parede para decidir;
  - o `policy.thompson` tira, a cada `propose`, sempre `len(ACTIONS)` normais, para o consumo do RNG não depender das ações disponíveis;
  - a CTRNN só sorteia na criação; o modelo de mundo, o Q curioso e a inferência ativa não sorteiam.
- **Crédito de recompensa:** as experiências de `dt == 0` (crédito do `AskCredit`) têm tratamento próprio em cada aprendiz novo, descrito na tarefa dele.
- **Camadas** (`tests/test_architecture.py`, sem mudança de regra):
  - módulos importam só `engrama.mind`, `engrama.vocab`, `engrama.balance` e a própria família;
  - `policy/{curious,thompson,aif}.py` podem importar `engrama.modules.policy.qlearning`;
  - `policy/curious.py` **não** importa `engrama.modules.world`.
- **Saves:**
  - todo módulo novo grava `"version": M10_STATE_VERSION` no `state_dict`;
  - `load_state_dict({})` mantém o estado inicial;
  - uma versão maior levanta `ValueError`;
  - arrays como `np.ndarray`, porque a persistência separa em `.npz`.
- **Constantes** num bloco `# Task M10` no fim de `engrama/balance.py`:

  | Constante | Valor | Uso |
  |---|---|---|
  | `M10_STATE_VERSION` | 1 | versão do `state_dict` dos módulos novos |
  | `EXP_BUDGET_MS` | 2.0 | `mean_ms` máximo de um módulo novo no lab (`dt = 60`) |
  | `CTRNN_HIDDEN` | 64 | unidades |
  | `CTRNN_TAU_MIN_BINS` | 1.0 | menor constante de tempo (bins de `SNN_BIN_S`) |
  | `CTRNN_TAU_MAX_BINS` | 1440.0 | maior constante de tempo (1 dia) |
  | `CTRNN_SUBSTEPS` | 4 | passos de Euler por bin |
  | `CTRNN_SPECTRAL_RADIUS` | 0.9 | raio espectral da recorrência |
  | `CTRNN_P_REC` | 0.2 | densidade da recorrência |
  | `CTRNN_W_IN` | 1.0 | escala dos pesos de entrada |
  | `CTRNN_BUDGET_MS` | 5.0 | `budget_ms` da CTRNN |
  | `WM_LR` | 0.05 | LMS normalizado do modelo de mundo |
  | `WM_ERR_EMA` | 0.99 | média móvel do erro (visualização e `lab_metrics`) |
  | `CUR_BETA` | 0.3 | peso do bônus intrínseco |
  | `CUR_BASELINE_EMA` | 0.99 | média do erro no modo `"surprise"` |
  | `CUR_LP_FAST` | 0.9 | média rápida por ação no modo `"progress"` |
  | `CUR_LP_SLOW` | 0.99 | média lenta por ação no modo `"progress"` |
  | `TS_SIGMA0` | 0.5 | desvio inicial do Thompson |
  | `TS_NOISE_FLOOR` | 0.05 | piso do desvio do erro de TD |
  | `TS_TD_VAR_EMA` | 0.99 | média móvel da variância do erro de TD |
  | `TS_N_HALF_LIFE_DAYS` | 7.0 | esquecimento das visitas |
  | `AIF_PRIOR` | 1.0 | contagem Beta inicial por resultado |
  | `AIF_PREF_SCALE` | 2.0 | nats por unidade de `REWARD_WEIGHTS` |
  | `AIF_NOVELTY_WEIGHT` | 1.0 | peso do ganho de informação |
  | `AIF_SOCIAL_GAIN` | 1.0 | sociabilidade na preferência por resposta |
  | `AIF_COUNT_HALF_LIFE_DAYS` | 7.0 | esquecimento das contagens em direção ao prior |
  | `SUITE_DAYS` | 7.0 | dias por corrida da suíte padrão |
  | `SUITE_ROUTINE_DAYS` | 4.0 | dias do perfil `routine` (como no teste R21) |
  | `SUITE_SEEDS` | (1, 2, 3) | sementes da suíte padrão |
  | `SUITE_PROFILES` | ("attentive", "absent", "neglectful", "routine") | perfis da suíte padrão |

  A T6 pode calibrar, registrando no relatório, **só** dentro destas faixas:
  - `CUR_BETA` 0,1–1,0;
  - `TS_SIGMA0` 0,2–1,0;
  - `AIF_PREF_SCALE` 1,0–4,0;
  - `AIF_NOVELTY_WEIGHT` 0,25–2,0;
  - peso de `policy.aif` nas receitas 0,2–1,0.

  Nada mais muda de valor depois da T0.
- **Orçamento:**
  - ≤150 MB RSS e ≤2% de CPU em `test_core_budget` e `test_overlay_bench_within_budget`, **sem mudar os limites dos testes**;
  - cada módulo novo com `mean_ms ≤ EXP_BUDGET_MS` no lab;
  - bench headless de cada receita nova ≤150 MB / ≤2%.
- **Lab:**
  - a suíte nunca edita o runtime: ela repete o corpo de `Runtime.run` tick a tick (`user.events` → `tick` → sonda → renascimento se morto);
  - a linha de base dela tem que bater com `sim`;
  - `module_ms` é o único campo não determinístico e fica fora das comparações de igualdade.
- Sem texto novo de UI no M10 (decisão recomendada).
- Commits sem `Co-Authored-By` e sem atribuição a IA. A mensagem exata está em cada tarefa. Não fazer push.
- Python: `.venv/bin/python` do worktree (no Windows, `.venv\Scripts\python.exe`). Testes com `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`. Os testes gravam em `.pytest_tmp`. **Nunca rode dois pytest ao mesmo tempo.**
- Máquina de referência: CachyOS, Ryzen 5 7520U, 7,2 GB. `default-v1` custa ≈1,6 s por dia simulado com `dt = 60` (spec §10).

## Foco de revisão

1. **Padrão byte a byte:**
   - os dois gabaritos de `sim` passam em todas as ondas;
   - SHA-256 de `default-v1.toml` e `minimal-v1.toml` iguais;
   - nenhuma linha removida ou mudada em `contracts.py` e `registry.py`. (T0, todas)
2. **Crédito da curiosidade:**
   - o bônus de uma transição vai para a ação dela (atraso de um tick, transição guardada salva no `state_dict`);
   - `dt == 0` é aplicado na hora, sem bônus;
   - com `beta = 0`, o resultado é o Q-learning atrasado de uma transição. (T2)
3. **Disciplina de RNG e sombra:**
   - só `self.rng`;
   - consumo fixo no Thompson;
   - `shadow-ctrnn-v1` e `lab-shadow-all-v1` com as mesmas ações ao vivo do padrão. (T1, T3, T6, T7)
4. **Matemática da inferência ativa:**
   - sinal de `G`: a proposta é `−G`;
   - preferências em log normalizado;
   - novidade `½(1/α_o − 1/α_0)` ponderada por `q(o)`;
   - a janela de pedido conta uma vez. (T4)
5. **Saves:** salvar, carregar e continuar dá um log idêntico para cada receita nova; `version`; `{}`. (T1–T4, T7)
6. **Suíte:**
   - mesma saída com `--jobs 1` e `--jobs N`;
   - linha de base == `sim`;
   - Brier sem a transição de renascimento;
   - `consistent_sign` pareado por semente. (T5)
7. **Relatório honesto:**
   - nada de "melhor" sem o mesmo sinal em todas as sementes;
   - efeitos diretos e indiretos separados;
   - IPS não usado para o Thompson. (T6)

---

## Mapa de arquivos

```
engrama/balance.py                         bloco # Task M10 (constantes)
engrama/mind/contracts.py                  CHANNELS += world.error (única linha nova)
engrama/mind/registry.py                   temporal.ctrnn, world.model, policy.curious, policy.thompson, policy.aif
engrama/modules/temporal/ctrnn.py          TemporalCTRNN
engrama/modules/world/__init__.py          (vazio; família nova)
engrama/modules/world/model.py             WorldModel, features, targets
engrama/modules/policy/curious.py          CuriousQPolicy (subclasse de QLearningPolicy)
engrama/modules/policy/thompson.py         ThompsonPolicy
engrama/modules/policy/aif.py              ActiveInferencePolicy, outcome_vector, log_pref, efe
engrama/lab/expmetrics.py                  Probe, experiment_metrics
engrama/lab/suite.py                       RoutineUser, RunSpec, run_one, run_suite, summarize, to_markdown, PRESETS
engrama/lab/cli.py                         subcomando suite
engrama/app/host.py                        main(): --recipe aceita nome; aviso quando o save manda
tools/bench.py                             --app repassa --recipe
recipes/ctrnn-v1.toml, recipes/shadow-ctrnn-v1.toml, recipes/curious-v1.toml, recipes/curious-lp-v1.toml,
recipes/thompson-v1.toml, recipes/aif-v1.toml, recipes/aif-solo-v1.toml, recipes/lab-shadow-all-v1.toml
tests/fixtures/m9_sim_7d_seed2_neglectful.json   gabarito gravado com o código do M9
tests/modules/contract_kit.py              verificações comuns de módulo/receita experimental
tests/modules/test_contract_kit.py, tests/test_m10_guard.py
tests/modules/test_ctrnn.py, tests/modules/test_world_model.py, tests/modules/test_curious.py,
tests/modules/test_thompson.py, tests/modules/test_aif.py
tests/lab/test_suite.py, tests/lab/test_expmetrics.py
tests/test_m10_acceptance.py
docs/superpowers/reports/2026-11-08-m10-experimentos.md, docs/superpowers/reports/2026-11-08-m10-experimentos.json
README.md, pyproject.toml
```

## Ondas e modelos

| Onda | Tarefas | Modelo |
|---|---|---|
| 0 | T0 | haiku |
| A | T1, T2, T4, T5 (sonnet) e T3 (haiku), paralelas; dependem de T0 | sonnet / haiku |
| B | T6; depende de T1–T5 | sonnet |
| C | T7; depende de T6 | sonnet |

Na Onda A os arquivos não se cruzam:
- T1: `temporal/ctrnn.py`, `recipes/ctrnn-v1.toml`, `recipes/shadow-ctrnn-v1.toml`, `tests/modules/test_ctrnn.py`;
- T2: `modules/world/**`, `policy/curious.py`, `recipes/curious-v1.toml`, `recipes/curious-lp-v1.toml`, `tests/modules/test_world_model.py`, `tests/modules/test_curious.py`;
- T3: `policy/thompson.py`, `recipes/thompson-v1.toml`, `tests/modules/test_thompson.py`;
- T4: `policy/aif.py`, `recipes/aif-v1.toml`, `tests/modules/test_aif.py`;
- T5: `lab/suite.py`, `lab/expmetrics.py`, `lab/cli.py`, `tests/lab/test_suite.py`, `tests/lab/test_expmetrics.py`.

`balance.py`, `contracts.py`, `registry.py` e `contract_kit.py` são só da T0. Se uma tarefa da Onda A precisar mudar um deles, ela reporta ao controlador em vez de editar. A T6 é a única que mexe em valores do bloco `# Task M10` (dentro das faixas) e em pesos das receitas experimentais. A T7 é a única que mexe em `host.py`, `tools/bench.py`, README e `pyproject.toml`.

---

### Tarefa 0: gabarito do M9, constantes, canal `world.error`, registro e kit de teste — onda 0 (haiku)

Afetada pelas decisões "criatura padrão" e "canal novo `world.error`" (spec §2).

**Arquivos:**
- Criar: `tests/fixtures/m9_sim_7d_seed2_neglectful.json`, `tests/modules/contract_kit.py`, `tests/modules/test_contract_kit.py`, `tests/test_m10_guard.py`.
- Modificar: `engrama/balance.py` (bloco `# Task M10`), `engrama/mind/contracts.py` (uma linha), `engrama/mind/registry.py` (cinco linhas).

**Interfaces:**
- Produz:
  ```python
  # contracts.py — acrescentar ao fim da tupla de CHANNELS:
  Channel("world.error", 1, 0, 1, "forward-model prediction error of the last transition")
  # registry.py — acrescentar ao REGISTRY:
  "temporal.ctrnn": "engrama.modules.temporal.ctrnn:TemporalCTRNN",
  "world.model": "engrama.modules.world.model:WorldModel",
  "policy.curious": "engrama.modules.policy.curious:CuriousQPolicy",
  "policy.thompson": "engrama.modules.policy.thompson:ThompsonPolicy",
  "policy.aif": "engrama.modules.policy.aif:ActiveInferencePolicy",
  # tests/modules/contract_kit.py
  RECIPES: Path                                        # <repo>/recipes
  def recipe(name_or_path) -> Recipe                    # "ctrnn-v1" -> recipes/ctrnn-v1.toml
  def actions(rt, seconds, dt=60.0) -> list[str]        # o mesmo _actions de tests/lab/test_runtime.py
  def run_clean(rec, days, profile="attentive", seed=1, dt=60.0) -> Runtime
      # com renascimento (corpo de Runtime.run); falha se: módulo desabilitado (status().error), ação fora de ACTIONS,
      # canal não finito no quadro-negro, tick sem ação
  def assert_save_load_identical(rec, tmp_path, before_s, after_s, profile="attentive", seed=1)
      # como test_default_recipe_save_load_continue_identical: ações e kernel.state_dict()["needs"] iguais
  def assert_same_live_actions(rec_a, rec_b, days=2.0, seed=1, profile="attentive")
  def assert_state_roundtrip(module, tmp_path)
      # save_run/load_run reais com {"m": module.state_dict()}; carrega num módulo novo (mesmo tipo/params);
      # state_dict() igual (arrays com np.array_equal); "version" == M10_STATE_VERSION;
      # load_state_dict({}) não muda o estado inicial; {"version": M10_STATE_VERSION + 1} -> ValueError
  def assert_no_global_rng(monkeypatch, rec, seconds=3600.0)
      # monkeypatch: np.random.{random,rand,randn,normal,uniform,choice,integers,standard_normal,seed} e random.*
      # levantam AssertionError depois de Runtime(...) construído; roda `seconds` sem erro
  def mean_ms(rt, name) -> float
  ```
  - As linhas novas de `REGISTRY` apontam para arquivos que só existem depois da Onda A. Até lá, `build` levanta `ModuleUnavailable` (o import é preguiçoso).
  - O gabarito novo é gerado **com o código do M9, antes de qualquer outra mudança**: `python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --seed 2 --profile neglectful > tests/fixtures/m9_sim_7d_seed2_neglectful.json`. Ele tem que conter pelo menos uma morte e um renascimento; se não tiver, troque a semente e registre no commit.

- [x] **Passo 1:** com o código do M9 intacto, gere e commite o gabarito novo. Anote o SHA-256 atual de `recipes/default-v1.toml` e `recipes/minimal-v1.toml`.
- [x] **Passo 2:** escreva os testes:
  - `tests/test_m10_guard.py`:
    - `test_default_lab_matches_m6_fixture` (a mesma comparação do `test_lab_identical_to_m8`);
    - `test_default_multilife_matches_m9_fixture` (`slow`; 7 dias, semente 2, `neglectful`; `lives.generations_finished ≥ 1`);
    - `test_default_and_minimal_recipes_unchanged` (SHA-256 gravados no teste);
    - `test_old_registry_entries_unchanged` (as sete entradas do M9, iguais);
    - `test_channels_are_m9_plus_world_error` (os 14 canais do M9 na mesma ordem, com os mesmos `dim`, `lo` e `hi`, mais `world.error[1]` em 0..1 no fim);
    - `test_config_recipe_default`;
    - `test_m10_constants` (valores da tabela);
  - `tests/modules/test_contract_kit.py`, que exercita o kit com módulos que já existem:
    - `run_clean(recipe("default-v1"), 0.5)`;
    - `assert_save_load_identical(recipe("minimal-v1"), ...)`;
    - `assert_same_live_actions` entre `minimal-v1` e `minimal-v1` com uma sombra `policy.qlearning` escrita em `tmp_path`;
    - `assert_state_roundtrip` com um módulo falso de teste que grava `version`;
    - `assert_no_global_rng` com `minimal-v1`;
    - `test_kit_detects_global_rng` (um módulo falso que chama `np.random.random()` faz o kit falhar);
    - `test_new_types_registered_lazily` (os cinco nomes estão no `REGISTRY`; `build` não quebra o import do `registry`).
- [x] **Passo 3:** rode os testes. Esperado: FAIL nos novos (os gabaritos já passam).
- [x] **Passo 4:** implemente.
- [x] **Passo 5:** rode `-m pytest -q tests/test_m10_guard.py tests/modules tests/mind tests/lab tests/test_architecture.py`. Esperado: PASS.
- [x] **Passo 6:** commit `feat(m10): M9 lab golden, constants, world.error channel, registry and module test kit`.

---

### Tarefa 1: CTRNN temporal — onda A (sonnet)

Afetada pela decisão "forma das comparações" (spec §2).

**Arquivos:**
- Criar: `engrama/modules/temporal/ctrnn.py`, `recipes/ctrnn-v1.toml`, `recipes/shadow-ctrnn-v1.toml`, `tests/modules/test_ctrnn.py`.

**Interfaces:**
- Consome: constantes `CTRNN_*`, `SNN_BIN_S`, `SNN_MAX_BINS_PER_STEP`, `SNN_PRED_LR`, `SNN_BIAS_LR`, `SNN_SURPRISE_EMA`, `SNN_FAMILIARITY_BINS`, `SNN_FMEAN_RATE`, `M10_STATE_VERSION`, `EXP_BUDGET_MS` (T0); `contract_kit` (T0).
- Produz:
  ```python
  class TemporalCTRNN(Module):
      reads = ("world.hour", "world.user_active")
      writes = ("temporal.surprise", "temporal.familiarity", "temporal.expectation")
      rate_hz = 1.0
      budget_ms = B.CTRNN_BUDGET_MS
      # params: n_hidden (CTRNN_HIDDEN), readout_hidden (True), tau_min/tau_max (bins), spectral_radius
      def step(self, bb, dt) -> None
      def state_dict(self) -> dict
      def load_state_dict(self, d: dict) -> None
      def viz(self) -> list[VizSpec]
      def lab_metrics(self) -> dict          # {"ctrnn_h_abs_mean": ..., "ctrnn_surprise_mean": ...}
  ```
  - **Entrada:** igual à da SNN (`_encode` da `snn.py`, reimplementado aqui sem importar nada privado dela): um por tipo de `EVENT_KINDS` presente no bin, as quatro metades de `world.hour`, `world.user_active`. `n_in = len(EVENT_KINDS) + 5`.
  - **Bins:** os mesmos da SNN. `dt` se acumula; cada evento vai para o bin do seu timestamp; no máximo `SNN_MAX_BINS_PER_STEP` bins por `step`; entre bins as saídas ficam como estão. O builder copia a lógica do `TemporalSNN.step` e mantém a mesma semântica.
  - **Criação** (o único uso do `self.rng`):
    - `tau = np.geomspace(tau_min, tau_max, n)`;
    - `U ~ N(0, CTRNN_W_IN / sqrt(n_in))`;
    - máscara recorrente com densidade `CTRNN_P_REC` e diagonal zero;
    - `W ~ N(0, 1) · máscara`, reescalado para raio espectral `spectral_radius` (`np.linalg.eigvals` uma vez);
    - `b ~ N(0, 0,1)`; `h = 0`.
  - **Por bin**, na mesma ordem do `TemporalSNN._advance`:
    1. `err = ev − pred`; `raw = mean(|err|)`;
    2. `w_pred += SNN_PRED_LR / (1 + f·f) · outer(err, f)`; `bias += SNN_BIAS_LR · err`;
    3. `surprise_ema` e `surprise_long` como na SNN;
    4. `CTRNN_SUBSTEPS` passos de Euler, `h += (1/S) / tau · (−h + W·tanh(h) + U·x + b)`;
    5. `trace = tanh(h)`; `fmean += SNN_FMEAN_RATE · (trace − fmean)`; `f = trace − fmean` (ou zeros com `readout_hidden=False`); `pred = sigmoid(w_pred·f + bias)`.
  - Escreve os três canais a cada `step`, como a SNN.
  - `state_dict`: `version`, `h`, `tau`, `W`, `U`, `b`, `w_pred`, `bias`, `feat`, `fmean`, `pred`, `surprise_ema`, `surprise_long`, `raw_surprise`, `bin_start`, `pending`, `series`.
  - `viz()`:
    - `series` "surprise / familiarity" (como a SNN);
    - `bars` "atividade por escala de tempo": média de `|tanh(h)|` em 4 faixas de `tau`;
    - `heatmap` dos pesos de leitura.
  - `recipes/ctrnn-v1.toml`: cópia de `default-v1` com `type = "temporal.ctrnn"` no lugar de `temporal.snn` (mesma posição na lista, para os RNGs dos outros módulos não mudarem), `name = "ctrnn-v1"`, `version = 1`.
  - `recipes/shadow-ctrnn-v1.toml`: cópia de `default-v1` mais `[[shadow]] type = "temporal.ctrnn"`, `name = "shadow-ctrnn-v1"`.

- [ ] **Passo 1:** escreva os testes:
  - `test_writes_temporal_channels_in_range`;
  - `test_dt_invariant` (mesmos eventos com `dt = 1` e `dt = 60`: as mesmas saídas nas fronteiras de bin, como o teste equivalente da SNN);
  - `test_rare_event_more_surprising` (um evento raro dá mais surpresa que um comum depois de habituar);
  - `test_readout_hidden_false_is_bias_only` (`w_pred` não muda);
  - `test_spectral_radius_at_creation` (≈`CTRNN_SPECTRAL_RADIUS`, tolerância 1e-6);
  - `test_stable_thirty_days` (`slow`: `ctrnn-v1`, 30 dias, `attentive`; `|h| ≤ 10`, tudo finito);
  - `test_no_worse_than_bias_only_on_routine` (`slow`, sementes 1, 2, 3: o `_brier` do teste R21 do M2 adaptado para trocar a SNN pela CTRNN; `ganho = (abl − full)/abl ≥ 0` em cada semente; imprime os ganhos, que vão para o relatório);
  - pelo `contract_kit`:
    - `run_clean(ctrnn-v1, 3, "attentive")` e `run_clean(ctrnn-v1, 5, "neglectful")` (`slow`);
    - `assert_save_load_identical(ctrnn-v1, ...)`;
    - `assert_state_roundtrip`;
    - `assert_no_global_rng`;
    - `mean_ms ≤ EXP_BUDGET_MS`;
  - `test_shadow_ctrnn_live_identical_to_default` (`assert_same_live_actions`).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/modules/test_ctrnn.py tests/modules/test_snn.py tests/test_m10_guard.py tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m10): CTRNN temporal module and recipes`.

---

### Tarefa 2: modelo de mundo e Q-learning curioso — onda A (sonnet)

Afetada pelas decisões "canal novo `world.error`" e "forma das comparações" (spec §2).

**Arquivos:**
- Criar: `engrama/modules/world/__init__.py`, `engrama/modules/world/model.py`, `engrama/modules/policy/curious.py`, `recipes/curious-v1.toml`, `recipes/curious-lp-v1.toml`, `tests/modules/test_world_model.py`, `tests/modules/test_curious.py`.

**Interfaces:**
- Consome: `world.error` em `CHANNELS`, constantes `WM_*`, `CUR_*`, `M10_STATE_VERSION`, `EXP_BUDGET_MS`, `contract_kit` (T0); `QLearningPolicy`, `state_index` (M2).
- Produz:
  ```python
  # engrama/modules/world/model.py
  CONTEXT = ("world.hour", "world.user_active", "body.asleep", "affect.pad", "drives")   # 2+1+1+3+6 = 13
  N_IN = 13 + 1 + len(ACTIONS)            # contexto, viés, ação one-hot = 22
  N_OUT = len(EVENT_KINDS) + len(NEED_KEYS)   # 16
  def features(ch: dict[str, np.ndarray], action: str) -> np.ndarray      # canal ausente = zeros
  def targets(exp: Experience) -> np.ndarray
      # tipos de evento em exp.events (0/1) + clip((next body.needs − body.needs) / (dt / HOUR), −1, 1)
  class WorldModel(Module):
      reads = CONTEXT + ("body.needs",)
      writes = ("world.error",)
      rate_hz = 1.0
      W: np.ndarray                       # (N_OUT, N_IN), zeros
      last_error: float                   # 0.0 antes do primeiro learn
      def predict(self, x) -> np.ndarray  # sigmoide nos 10 primeiros, identidade nos 6 últimos
      def learn(self, exp) -> None        # ignora dt <= 0 e ação fora de ACTIONS
      def step(self, bb, dt) -> None      # bb.write("world.error", [last_error])
      def lab_metrics(self) -> dict       # {"world_error_mean", "world_error_ema"}
  # engrama/modules/policy/curious.py
  class CuriousQPolicy(QLearningPolicy):
      reads = QLearningPolicy.reads + ("world.error",)
      # params: beta (CUR_BETA), bonus ("surprise" | "progress"), error_channel ("world.error"), alpha, gamma
      def learn(self, exp) -> None
      def lab_metrics(self) -> dict       # {"bonus_mean", "bonus_share"}
  ```
  - `WorldModel.learn`:
    - `x = features(exp.channels, exp.action)`, `y = targets(exp)`, `p = predict(x)`;
    - `err = clip(mean((y − p)²), 0, 1)`;
    - `W += WM_LR · outer(y − p, x) / (1 + x·x)` (para as saídas sigmoide, o gradiente da entropia cruzada tem a mesma forma);
    - `last_error = err`; atualiza a média móvel `WM_ERR_EMA` e as somas para `lab_metrics`.
  - **Ordem no runtime** (não muda): `learn(e_t)` de todos → `step` de todos → snapshot. Portanto `world.error` no snapshot do tick `t` é o erro de `e_t`, e chega ao `policy.curious` como `e_{t+1}.channels["world.error"]`.
  - `CuriousQPolicy.learn(exp)`:
    1. ação fora de `ACTIONS` → ignora; `s, a, s2 = state_index(...)`; `r = reward_combine(exp.rewards)`;
    2. `exp.dt <= 0` (crédito de pedido): atualização TD do `QLearningPolicy` na hora, com `r`, sem bônus; fim;
    3. se há transição guardada `(s0, a0, s20, r0)`: `err = exp.channels.get(error_channel)` (ausente → bônus 0); `b = bonus(a0, err)`; TD em `(s0, a0, s20)` com `r0 + beta·b`; soma estatísticas;
    4. guarda `(s, a, s2, r)`.
  - Bônus `"surprise"`: `b = clip(err − baseline, 0, 1)`, depois `baseline += (1 − CUR_BASELINE_EMA)·(err − baseline)`. `baseline` começa em 0.
  - Bônus `"progress"`: `fast[a0]` e `slow[a0]` com `CUR_LP_FAST` e `CUR_LP_SLOW`, atualizados primeiro; `b = clip(slow[a0] − fast[a0], 0, 1)`.
  - `propose`: herdado, com `reason` "aprendi + curiosidade: {b}/{act}".
  - `state_dict`: o do pai mais `version`, `held` (ou `None`), `baseline`, `fast`, `slow` e as somas. `load_state_dict({})` mantém o estado inicial.
  - `bonus_share = beta·Σb / (Σ|r_ext| + beta·Σb)` (0 se tudo for 0).
  - `viz()`: `WorldModel`, `series` do erro e da média; `CuriousQPolicy`, o `heatmap` de Q do pai mais `series` do bônus.
  - Receitas:
    - `curious-v1`: cópia de `default-v1`, `policy.qlearning` trocado por `type = "policy.curious"`, `weight = 0.6`, `bonus = "surprise"` (mesma posição) e `[[module]] type = "world.model"` **no fim** da lista viva. Assim os RNGs dos módulos anteriores não mudam; o do árbitro muda, porque há um módulo vivo a mais, e isso fica anotado num comentário da receita.
    - `curious-lp-v1`: o mesmo com `bonus = "progress"`.

- [ ] **Passo 1:** escreva os testes:
  - `test_world_model.py`:
    - `test_features_targets_shapes_and_missing_channels`;
    - `test_targets_need_rate_dt_invariant` (mesma taxa por hora com `dt = 60` e `dt = 1`);
    - `test_error_drops_in_stationary_world` (experiências sintéticas: a ação `play_alone` sempre traz `pet`, as outras nada; a média do último quarto fica abaixo de metade da do primeiro);
    - `test_ignores_credit_experiences`;
    - `test_world_error_written_after_learn` (`Runtime` real com `curious-v1`, 30 ticks: `bb.read("world.error")[0] == módulo.last_error`);
    - `test_world_model_no_rng`;
  - `test_curious.py`:
    - `test_beta_zero_is_q_learning_lagged_by_one` (para as mesmas transições `e_0..e_N`, Q do curioso com `beta = 0` == Q do `QLearningPolicy` depois de `e_0..e_{N−1}`, com `np.array_equal`);
    - `test_bonus_credited_to_transition_action` (pipeline sintético que imita a ordem do runtime: `wm.learn(e_t)`, `cur.learn(e_t)`, `wm.step(bb)`, `e_{t+1}.channels = bb.snapshot()`; só a ação X tem eventos aleatórios, com RNG do teste, e recompensa extrínseca 0; depois de 400 transições, `Q[s, X] > max` das outras);
    - `test_credit_experience_applied_immediately_without_bonus`;
    - `test_progress_bonus_returns_to_zero_when_error_flat`;
    - `test_no_world_channel_means_no_bonus`;
    - `test_held_transition_survives_save_load`;
  - pelo `contract_kit`, para `curious-v1` e `curious-lp-v1`:
    - `run_clean` (3 dias `attentive`; 5 dias `neglectful` `slow`);
    - `assert_save_load_identical`;
    - `assert_state_roundtrip` (os dois módulos);
    - `assert_no_global_rng`;
    - `mean_ms ≤ EXP_BUDGET_MS` (os dois módulos).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/modules/test_world_model.py tests/modules/test_curious.py tests/modules/test_qlearning.py tests/test_m10_guard.py tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m10): world model and curiosity-driven Q-learning`.

---

### Tarefa 3: Thompson sampling — onda A (haiku)

Afetada pela decisão "forma das comparações" (spec §2).

**Arquivos:**
- Criar: `engrama/modules/policy/thompson.py`, `recipes/thompson-v1.toml`, `tests/modules/test_thompson.py`.

**Interfaces:**
- Consome: constantes `TS_*`, `QL_ALPHA`, `QL_GAMMA`, `M10_STATE_VERSION`, `EXP_BUDGET_MS`, `contract_kit` (T0); `state_index`, `context`, `N_STATES` (M2).
- Produz:
  ```python
  class ThompsonPolicy(Module):
      reads = ("world.hour", "world.user_active", "affect.pad")
      writes = ()
      rate_hz = 1.0
      # params: alpha (QL_ALPHA), gamma (QL_GAMMA), sigma0 (TS_SIGMA0), half_life_days (TS_N_HALF_LIFE_DAYS)
      mu: np.ndarray            # (N_STATES, len(ACTIONS)), zeros
      n: np.ndarray             # (N_STATES, len(ACTIONS)) float, zeros
      td_var: float             # começa em sigma0**2
      def sd(self) -> np.ndarray          # sqrt(max(TS_NOISE_FLOOR**2, td_var) / (1 + n))
      def learn(self, exp) -> None
      def propose(self, bb) -> list[Proposal]
      def lab_metrics(self) -> dict       # {"sd_mean", "explore_rate"}
  ```
  - `learn`:
    - ação fora de `ACTIONS` → ignora;
    - `td = r + gamma·mu[s2].max() − mu[s, a]`; `mu[s, a] += alpha·td` (a mesma conta do `QLearningPolicy`);
    - com `exp.dt > 0`: `n *= 0.5 ** (exp.dt / (half_life_days · 86400))`;
    - `n[s, a] += 1`; `td_var += (1 − TS_TD_VAR_EMA)·(td² − td_var)`.
  - `propose`:
    - `z = self.rng.standard_normal(len(ACTIONS))` **sempre**, mesmo com poucas ações disponíveis;
    - para cada ação disponível, `score = mu[s, i] + sd[s, i]·z[i]`; `reason` "amostrei: {b}/{act}";
    - `explore_rate` conta as decisões em que o argmax da amostra difere do argmax de `mu` entre as disponíveis.
  - `state_dict`: `version`, `mu`, `n`, `td_var` e os contadores de `lab_metrics`.
  - `viz()`: `heatmap` de `mu` e `heatmap` de `sd`.
  - `recipes/thompson-v1.toml`: cópia de `default-v1` com `type = "policy.thompson"`, `weight = 0.6` no lugar de `policy.qlearning` (mesma posição), `name = "thompson-v1"`.

- [x] **Passo 1:** escreva os testes:
  - `test_mu_matches_qlearning` (mesmas transições → `mu == QLearningPolicy.Q`);
  - `test_sd_shrinks_with_visits_and_regrows_with_forgetting`;
  - `test_two_armed_bandit_prefers_best` (contexto fixo, `gamma = 0`, braço A recompensa 1 com p = 0,7, braço B com p = 0,3, RNG do teste; laço `propose` → argmax → `learn`, 500 passos; fração de A nos últimos 200 > 0,9);
  - `test_zero_sd_equals_mean`;
  - `test_rng_draws_fixed_per_propose` (o estado do `self.rng` avança igual com 2 e com 8 ações disponíveis);
  - `test_deterministic_given_rng_state`;
  - pelo `contract_kit` com `thompson-v1`:
    - `run_clean` (3 dias `attentive`; 5 dias `neglectful` `slow`);
    - `assert_save_load_identical` (o RNG do módulo vai no save do runtime);
    - `assert_state_roundtrip`;
    - `assert_no_global_rng`;
    - `mean_ms ≤ EXP_BUDGET_MS`.
- [x] **Passo 2:** rode os testes. Esperado: FAIL.
- [x] **Passo 3:** implemente.
- [x] **Passo 4:** rode `-m pytest -q tests/modules/test_thompson.py tests/test_m10_guard.py tests/test_architecture.py`. Esperado: PASS.
- [x] **Passo 5:** commit `feat(m10): Thompson sampling policy`.

---

### Tarefa 4: inferência ativa — onda A (sonnet)

Afetada pelas decisões "forma das comparações" e pela §9 da spec (inferência ativa mínima, crédito do pedido).

**Arquivos:**
- Criar: `engrama/modules/policy/aif.py`, `recipes/aif-v1.toml`, `tests/modules/test_aif.py`.

**Interfaces:**
- Consome: constantes `AIF_*`, `REWARD_WEIGHTS`, `M10_STATE_VERSION`, `EXP_BUDGET_MS`, `contract_kit` (T0); `state_index`, `N_STATES` (M2); `ASK_ACTION`, `ASK_WINDOW_KEYS` (`contracts`); `read_traits` (`helpers`).
- Produz:
  ```python
  FACTORS = REWARD_KEYS                    # 7 fatores binários
  def outcome_vector(rewards: dict[str, float]) -> np.ndarray      # bool (7,): valor > 0 para todas as chaves
  def log_pref(traits: dict[str, float], scale: float = B.AIF_PREF_SCALE) -> np.ndarray
      # (7, 2): C_k = scale · REWARD_WEIGHTS[k]; user_response · (1 + AIF_SOCIAL_GAIN · (sociabilidade − 0.5));
      # [k, 1] = C_k − logaddexp(C_k, 0); [k, 0] = −logaddexp(C_k, 0)
  def efe(counts: np.ndarray, lnp: np.ndarray, eta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]
      # counts (A, 7, 2) de um contexto → (G, pragmatic, novelty), cada um (A,)
      # q = counts / counts.sum(-1); pragmatic = Σ_k −Σ_o q·lnp
      # novelty = Σ_k Σ_o q · 0.5 · (1/counts − 1/counts.sum(-1)); G = pragmatic − eta · novelty
  class ActiveInferencePolicy(Module):
      reads = ("world.hour", "world.user_active", "affect.pad", "traits")
      writes = ()
      rate_hz = 1.0
      # params: pref_scale (AIF_PREF_SCALE), novelty_weight (AIF_NOVELTY_WEIGHT), half_life_days (AIF_COUNT_HALF_LIFE_DAYS)
      counts: np.ndarray                   # (N_STATES, len(ACTIONS), 7, 2), AIF_PRIOR
      def learn(self, exp) -> None
      def propose(self, bb) -> list[Proposal]           # score = −G(a)
      def lab_metrics(self) -> dict        # {"novelty_share", "g_spread_mean", "pragmatic_mean"}
  ```
  - `learn`:
    - ação fora de `ACTIONS` → ignora;
    - com `exp.dt > 0`: `counts = AIF_PRIOR + (counts − AIF_PRIOR) · 0.5 ** (exp.dt / (half_life_days · 86400))`;
    - `o = outcome_vector(exp.rewards)`. Fatores atualizados (`counts[s, a, k, o_k] += 1`):
      - `exp.dt <= 0` (crédito): só os de `ASK_WINDOW_KEYS` com valor > 0, com `o_k = 1`;
      - `exp.action == ASK_ACTION`: todos, menos os de `ASK_WINDOW_KEYS` que não vieram > 0 nesta linha (o fechamento da janela chega pelo crédito);
      - outras ações: todos.
  - `propose`:
    - `s = state_index(bb.snapshot())`, `lnp = log_pref(read_traits(bb), pref_scale)`, `efe(counts[s], lnp, novelty_weight)`;
    - uma proposta por ação disponível com `score = −G[i]`;
    - `reason` pelo termo dominante: "prefere {chave mais provável e preferida}" ou "curiosa sobre {ação}".
  - Não usa o `self.rng`.
  - `state_dict`: `version`, `counts` e os contadores de `lab_metrics`.
  - `viz()`: `bars` de `−G` por ação na última decisão e `table` com `pragmatic` e `novelty` por ação.
  - `recipes/aif-v1.toml`: cópia de `default-v1` com `type = "policy.aif"`, `weight = 0.6` no lugar de `policy.qlearning` (mesma posição), `name = "aif-v1"`. O peso pode ser calibrado na T6.

- [ ] **Passo 1:** escreva os testes:
  - `test_outcome_vector` (`need_pain` > 0 → 1; `msg_valence` negativo → 0);
  - `test_log_pref_normalized_and_signed` (`exp` das duas colunas soma 1; `need_relief` prefere 1; `need_pain` e `ignored` preferem 0; a preferência por resposta cresce com a sociabilidade);
  - `test_preferred_outcome_action_has_lowest_G`;
  - `test_novelty_prefers_unvisited` (preferências planas, `pref_scale = 0`: a ação com menos contagens tem o menor `G`);
  - `test_no_pref_no_novelty_equal_G`;
  - `test_ask_window_counted_once` (linha de `ask_attention` sem resposta, depois a experiência de crédito `dt = 0` com `user_response = 1`: `counts[s, ask, user_response]` ganha exatamente +1 em `o = 1` e nada em `o = 0`; idem para `ignored`);
  - `test_counts_decay_toward_prior`;
  - `test_no_rng_use` (propostas iguais com dois `self.rng` diferentes);
  - `test_efe_matches_hand_computed` (um caso pequeno feito à mão);
  - pelo `contract_kit` com `aif-v1`:
    - `run_clean` (3 dias `attentive`; 5 dias `neglectful` `slow`);
    - `assert_save_load_identical`;
    - `assert_state_roundtrip`;
    - `assert_no_global_rng`;
    - `mean_ms ≤ EXP_BUDGET_MS`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/modules/test_aif.py tests/test_m10_guard.py tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m10): active inference policy`.

---

### Tarefa 5: suíte de experimentos e métricas de comparação — onda A (sonnet)

Afetada pela decisão "forma das comparações" (spec §2).

**Arquivos:**
- Criar: `engrama/lab/expmetrics.py`, `engrama/lab/suite.py`, `tests/lab/test_expmetrics.py`, `tests/lab/test_suite.py`.
- Modificar: `engrama/lab/cli.py` (só o subcomando novo `suite`; os outros não mudam).

**Interfaces:**
- Consome: constantes `SUITE_*` (T0); `Runtime`, `runtime._Collector`, `compute_metrics`, `SimUser`, `PROFILES`, `credit_rows` (M1–M6). Os testes usam só `default-v1`, `minimal-v1` e módulos falsos registrados no teste, porque as receitas da Onda A podem ainda não existir.
- Produz:
  ```python
  # engrama/lab/expmetrics.py
  class Probe:
      def __init__(self, start_t: float, days: float) -> None
      def after_tick(self, rt: Runtime, reborn: bool) -> None
          # Brier: para cada canal do quadro-negro cujo nome termina em "temporal.expectation" (vivo e shadow/*):
          #   mean((expectation do tick anterior − eventos deste tick)²), só com t ≥ start_t + days/2 e
          #   nunca no tick de um renascimento; satisfação: 1 − mean(body.needs); "world.error" (vivo e shadow/*)
      def before_rebirth(self, rt: Runtime) -> None   # junta lab_metrics() dos módulos da vida que acabou
      def result(self, rt: Runtime) -> dict
          # {"pred_brier": {canal: v}, "need_satisfaction", "world_error_mean": {canal: v},
          #  "lab_metrics": {módulo: {k: média ponderada pelos ticks de cada vida}}}
  def experiment_metrics(rows: list[TickRow], days: float) -> dict
      # {"return_per_day": Σ credit_rows / days, "novelty_per_day", "decision_entropy" (linhas decided),
      #  "switch_rate" (decided consecutivas com ação diferente)}
  # engrama/lab/suite.py
  class RoutineUser                        # cópia exata de _RoutineUser (tests/test_m2_acceptance.py), com state_dict()
  @dataclass(frozen=True)
  class RunSpec:
      recipe: Path; profile: str; seed: int; days: float; dt: float = 60.0
  PRESETS: dict[str, dict]                 # "m10": recipes (8, spec §3 item 2, menos lab-shadow-all), SUITE_PROFILES,
                                           #        SUITE_SEEDS, SUITE_DAYS, SUITE_ROUTINE_DAYS
  def specs_from(preset_or_args) -> list[RunSpec]       # "routine" usa SUITE_ROUTINE_DAYS
  def run_one(spec: RunSpec) -> dict
      # {"recipe": nome, "profile", "seed", "days", "metrics": {...compute_metrics(rows, lives), ...experiment_metrics,
      #   ...Probe.result}, "module_ms": {nome: mean_ms}}
  def run_suite(specs: list[RunSpec], jobs: int = 1) -> list[dict]
      # jobs > 1: multiprocessing com contexto "spawn"; saída ordenada por (recipe, profile, seed), igual a jobs = 1
  def summarize(runs: list[dict], baseline: str = "default-v1") -> dict
      # {"by_recipe": {recipe: {profile: {métrica: {"mean", "sd", "n", "values"}}}},
      #  "vs_baseline": {recipe: {profile: {métrica: {"diff": média das diferenças pareadas por semente,
      #                                               "consistent_sign": todas > 0 ou todas < 0}}}}}
      # métricas: escalares numéricos, achatados com "/" ("lives/life_days_mean", "pred_brier/temporal.expectation")
  MD_METRICS: tuple[str, ...]              # wellbeing, need_satisfaction, return_per_day, behavior_entropy, decision_entropy,
                                           # answered_rate, ignored_rate, novelty_per_day, pred_brier/temporal.expectation,
                                           # world_error_mean/world.error, lives/life_days_mean, lives/generations_finished
  def to_markdown(summary: dict, metrics=MD_METRICS) -> str      # uma tabela por perfil; "±" e marca de sinal consistente
  ```
  - `run_one` repete **exatamente** o `run_days` (mesmo `Runtime(recipe, seed, _Collector())` e mesmo `SimUser(PROFILES[p], default_rng([seed, 1]))`; `RoutineUser(dt)` no perfil `routine`). O laço é o corpo de `Runtime.run`: `rt.user = user`; enquanto `t < fim`: `step = min(dt, fim − t)`; `evs = user.events(t, step, rt.creature())`; `rt.tick(step, evs)`; `probe.after_tick`; se `rt.kernel.dead`: `probe.before_rebirth(rt)`; `rt.lives.append(rt.rebirth())`. Vidas = `rt.lives + [rt.life_summary()]`.
  - Os módulos sem `lab_metrics` são ignorados (duck typing, `getattr`).
  - CLI: `python -m engrama.lab suite [--preset m10] [--recipes P ...] [--profiles ...] [--seeds ...] [--days N] [--routine-days N] [--dt 60] [--jobs N] [--baseline default-v1] [--out x.json] [--md x.md]`. Sem `--out`, imprime o JSON (`runs` + `summary`); com `--md`, grava a tabela.

- [ ] **Passo 1:** escreva os testes:
  - `test_expmetrics.py`:
    - `test_brier_known_sequence` (quadro-negro falso com expectativa e eventos conhecidos);
    - `test_brier_skips_rebirth_tick_and_first_half`;
    - `test_brier_includes_shadow_channels` (`minimal-v1` mais uma sombra `temporal.snn` escrita em `tmp_path`: existe a chave `shadow/<nome>/temporal.expectation`);
    - `test_need_satisfaction_and_world_error`;
    - `test_return_per_day_uses_credit_rows`;
    - `test_decision_entropy_and_switch_rate`;
    - `test_lab_metrics_weighted_over_lives` (módulo falso registrado com `lab_metrics`);
  - `test_suite.py`:
    - `test_baseline_matches_sim` (`run_one(default-v1, attentive, 1, 1 dia)["metrics"]` contém exatamente o gabarito `m6_sim_1d_seed1_attentive.json` nas chaves dele);
    - `test_routine_user_matches_m2_copy` (mesmos eventos que o `_RoutineUser` dos testes do M2 por 2 dias);
    - `test_jobs_do_not_change_results` (`slow`: 2 receitas × 2 sementes × 1 dia, `jobs = 1` e `jobs = 2`; iguais sem `module_ms`);
    - `test_deterministic_rerun`;
    - `test_summarize_paired_diff_and_consistent_sign` (corridas falsas com valores conhecidos);
    - `test_markdown_has_one_table_per_profile`;
    - `test_cli_suite_small` (`--recipes default-v1 minimal-v1 --profiles attentive --seeds 1 --days 0.5 --out --md`);
    - `test_sim_and_compare_output_unchanged` (o gabarito do M6 continua igual por `cli.main(["sim", ...])`).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/lab tests/test_m10_guard.py tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m10): lab experiment suite and comparison metrics`.

---

### Tarefa 6: relatório de comparação — onda B (sonnet; depende de T1–T5)

Afetada pelas decisões "forma das comparações" e "promover um experimento a padrão" (spec §2).

**Arquivos:**
- Criar: `recipes/lab-shadow-all-v1.toml`, `recipes/aif-solo-v1.toml`, `docs/superpowers/reports/2026-11-08-m10-experimentos.md`, `docs/superpowers/reports/2026-11-08-m10-experimentos.json`.
- Modificar (só se a calibração do Passo 3 pedir, dentro das faixas das Restrições globais): o bloco `# Task M10` de `engrama/balance.py` e os pesos em `recipes/{curious,curious-lp,thompson,aif,aif-solo}-v1.toml`.

**Interfaces:**
- Consome: tudo da Onda A.
- Produz:
  - `lab-shadow-all-v1`: `default-v1` ao vivo mais `[[shadow]]` `temporal.ctrnn`, `policy.thompson`, `policy.aif` e `world.model`. O `policy.curious` fica de fora, porque em sombra ele não vê o `world.error` de outra sombra.
  - `aif-solo-v1`: `default-v1` sem `policy.utility` e com `policy.aif` no lugar de `policy.qlearning` (linha exploratória, spec §2).
  - O relatório, em PT, com estas seções:
    1. **Como reproduzir:** comandos exatos, commit e máquina.
    2. **Tabela da suíte:** `to_markdown`, uma tabela por perfil, média ± dp das 3 sementes, diferença para o padrão e marca de sinal consistente.
    3. **Efeitos diretos** por experimento:
       - Brier da CTRNN contra a SNN e contra a ablação só com viés, ao vivo e em sombra na mesma vida;
       - erro do modelo de mundo e `bonus_share`;
       - `sd_mean` e `explore_rate` do Thompson;
       - `novelty_share` e `g_spread_mean` da inferência ativa.
    4. **Efeitos indiretos** (bem-estar, satisfação, retorno, entropia, respostas, sobrevivência no `neglectful`), com a ressalva da spec §11, item 8.
    5. **Custo:** bench headless de cada receita nova e da `lab-shadow-all-v1` (RSS, CPU, `modules_mean_ms`).
    6. **Calibrações feitas**, com o valor anterior, o novo e o motivo, ou "nenhuma".
    7. **O que não se conclui:** 3 sementes, usuário simulado ≠ real, IPS não vale para o Thompson, recomendação sobre promoção (spec §2).
  - Regra de escrita: só se diz que um experimento "melhora" ou "piora" uma métrica com o mesmo sinal nas 3 sementes. Senão, "sem efeito consistente".

- [ ] **Passo 1:** crie as duas receitas e confira `assert_same_live_actions(default-v1, lab-shadow-all-v1)` e `run_clean(aif-solo-v1, 3)` à mão (os testes entram na T7).
- [ ] **Passo 2:** rode `python -m engrama.lab suite --preset m10 --jobs 4 --out docs/superpowers/reports/2026-11-08-m10-experimentos.json --md <tmp>/tabela.md` e anote o tempo de parede.
- [ ] **Passo 3:** calibração, só se um experimento ficar degenerado no `attentive`:
  - degenerado = módulo desabilitado, uma ação com mais de 60% do tempo, ou `wellbeing` abaixo de metade do padrão;
  - ajuste só dentro das faixas, rode a suíte de novo e registre antes/depois;
  - nunca mexa em constantes ou módulos do padrão.
- [ ] **Passo 4:** rode `tools/bench.py --recipe recipes/<r>.toml --seconds 30` para cada receita nova e para a `lab-shadow-all-v1`. Esperado: ≤150 MB, ≤2% e `modules_mean_ms` de cada módulo novo ≤ `EXP_BUDGET_MS`.
- [ ] **Passo 5:** escreva o relatório.
- [ ] **Passo 6:** rode `-m pytest -q tests/test_m10_guard.py tests/modules tests/lab`. Esperado: PASS (a calibração não quebra os testes da Onda A).
- [ ] **Passo 7:** commit `docs(m10): lab comparison report of the ML experiments`.

---

### Tarefa 7: wiring, acceptance and README — onda C (sonnet)

Afetada pela decisão "como escolher um experimento no app" (spec §2).

**Arquivos:**
- Modificar: `engrama/app/host.py` (só `main()` e a construção do `Host`, para o aviso), `tools/bench.py` (`--app` repassa `--recipe`), `README.md` (PT e EN), `pyproject.toml` (versão `0.10.0`).
- Criar: `tests/test_m10_acceptance.py` (marcado `slow` onde roda subprocesso, bench ou vários dias).

**Interfaces:**
- Consome: tudo acima.
- Produz:
  - `main()`: `--recipe X`. Se `X` existe como caminho, usa o caminho; senão, `recipes/X.toml` (com ou sem `.toml`). Inexistente: mensagem de erro PT/EN em `stderr` e saída 2, antes de abrir a janela.
  - `Host._load_or_create`: quando há save e o nome da receita do save difere do da receita pedida, registra uma linha de `logging` (nunca na UI) e segue com a do save, como hoje.
  - `tools/bench.py --app --recipe R`: repassa `--recipe R` ao `python -m engrama`. Sem `--recipe`, o comando é o de hoje.

- [ ] **Passo 1:** escreva `tests/test_m10_acceptance.py`, cobrindo a spec §7:
  - `test_default_untouched` (critério 1: os dois gabaritos, SHA-256 das receitas, `REGISTRY` antigo, `CHANNELS`, `Config().recipe`);
  - `test_every_new_recipe_runs_clean` (critério 2; parametrizado nas 8 receitas novas; `attentive` 3 dias e `neglectful` 5 dias `slow`);
  - `test_suite_deterministic_and_jobs_invariant` (critério 3);
  - `test_every_new_recipe_save_load_identical` (critério 3, parametrizado);
  - `test_shadows_keep_live_identical` (critério 4: `shadow-ctrnn-v1` e `lab-shadow-all-v1` contra `default-v1`; a suíte devolve Brier da sombra);
  - `test_mechanisms` (critério 5: versões curtas, com os módulos reais, dos quatro casos centrais da Onda A: o erro do modelo de mundo cai, o bônus vai para a ação certa, o bandit de dois braços prefere o melhor e o resultado preferido tem o menor `G`);
  - `test_ctrnn_routine_no_worse` (critério 5, `slow`, sementes 1–3);
  - `test_budget_headless_each_recipe` (critério 6, `slow`, 30 s cada no bench headless);
  - `test_budget_app_shadow_all` (critério 6, `slow`: `tools/bench.py --app --recipe lab-shadow-all-v1 --seconds 30` ≤150 MB e ≤2% com a mesma tolerância de máquina carregada do `test_core_budget`);
  - `test_new_modules_mean_ms` (critério 6);
  - `test_suite_cli_small` (critério 7);
  - `test_state_versions` (critério 8, os cinco tipos);
  - `test_app_new_creature_with_recipe_name` (critério 9: `python -m engrama --recipe thompson-v1 --no-llm --frames 120 --data-dir <tmp>` sai com 0; `meta.json` do save tem `recipe.name == "thompson-v1"`);
  - `test_app_existing_save_keeps_recipe` (critério 9: a mesma pasta com `--recipe default-v1` continua `thompson-v1` e registra o aviso);
  - `test_unknown_recipe_name_exits_2`;
  - `test_mind_view_collects_new_viz` (critério 9: `Host` com `lab-shadow-all-v1` e `want_viz`; `snapshot().viz` tem entradas para os módulos novos, sem exceção);
  - `test_architecture_and_vocab_frozen` (critério 10);
  - `test_report_present` (critério 11: o relatório e o JSON existem; o JSON tem as 8 receitas e os 4 perfis);
  - `test_smoke_frames` (`python -m engrama --frames 120 --no-llm --data-dir <tmp>` sai com 0, receita padrão).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente a ligação (`main`, aviso, bench).
- [ ] **Passo 4:** rode `-m pytest -q tests/test_m10_acceptance.py` e depois `-m pytest -q`, a suíte inteira. Esperado: tudo PASS, incluindo os dois testes de orçamento do M3/M7, sem mudança nos limites.
- [ ] **Passo 5:** rode `tools/bench.py --app --seconds 60` e `--overlay --seconds 30` (receita padrão). Esperado: ≤150 MB e ≤2%, iguais ao M9 dentro do ruído. Anote no PR.
- [ ] **Passo 6:** atualize o README em PT e EN:
  - seção nova "Experimentos de ML (M10)" / "ML experiments (M10)":
    - os quatro experimentos em uma linha cada;
    - a tabela de receitas, com a troca que cada uma faz;
    - que o padrão não mudou;
    - o resumo de uma linha do relatório, com link;
  - "Laboratório": o subcomando `suite` (exemplo pequeno e o `--preset m10` com o tempo medido);
  - "Receitas" e "O app": `--recipe` aceita nome; a receita só vale para uma criatura nova (pasta de dados nova), segue as gerações e é ignorada quando já há save;
  - "Escrever um módulo": o `lab_metrics()` opcional e o `version` no `state_dict`.
- [ ] **Passo 7:** versão `0.10.0` em `pyproject.toml`.
- [ ] **Passo 8:** commit `feat(m10): experiment recipes in the app, M10 acceptance and README`.
- [ ] **Passo 9:** o controlador mostra ao usuário a tabela do relatório e as decisões abertas (a recomendação de não promover). Nenhum smoke manual é exigido, porque a UI não muda. Opcional: `python -m engrama --recipe curious-v1 --dev --time-scale 60 --data-dir <pasta nova>`, abrir a Visão da Mente (F2) e conferir que os módulos novos aparecem.
