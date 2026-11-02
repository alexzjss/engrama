# Engrama M6 — Vida longa: plano de implementação

> **Para agentes:** use superpowers:subagent-driven-development ou superpowers:executing-plans. Passos com `- [ ]`.

**Objetivo:** ramos evolutivos, doença, velhice, morte com despedida, renascimento com herança de personalidade e memória ancestral, painel de gerações e vidas múltiplas no lab.

**Arquitetura:** o kernel ganha saúde, velhice, morte, interesses e escolha de ramo (puro, determinístico). O `Runtime` (lab) sabe renascer: cria kernel e mente novos, aplica o viés de traços. O host faz o resto do renascimento (arquivo da memória, lembranças ancestrais, registro de gerações, fala de despedida). Arte e UI leem só o `Snapshot`.

**Stack:** Python 3.13 (venv `E:/Documentos/GitHub/digimon/.venv/Scripts/python.exe`), numpy, pygame-ce, sqlite3, stdlib.

**Spec:** `docs/superpowers/specs/2026-11-04-engrama-m6-vida-longa-design.md`

## Restrições globais

- Branch `m6`. Cada agente começa com `git reset --hard m6`.
- Commits sem `Co-Authored-By` e sem atribuição de IA. Mensagem exata dada em cada tarefa.
- Kernel determinístico; não importa `mind`, `modules`, `lab`, `services`. `tests/test_architecture.py` passa.
- `EVENT_KINDS` e `FOOD_IDS` **não mudam**. O remédio **não** é uma comida de `FOOD_IDS` (mudaria o estado do módulo de preferências): é o evento `food` com `{"food": "remedio"}`, tratado à parte no kernel e ignorado por `FoodPrefs` (já ignora ids fora de `FOOD_IDS`).
- Saves de M5 abrem: todo campo novo de `state_dict` tem padrão em `from_state_dict`/`from_dict`.
- PT/EN em toda string nova; UI sem dígitos no modo normal (modo dev pode mostrar).
- Nunca rodar dois pytest ao mesmo tempo (`.pytest_tmp` compartilhado). Use sempre o Python do venv.
- Orçamento do app: ≤150 MB RSS, ≤2% CPU (`tests/test_m3_acceptance.py::test_core_budget`).

## Foco de revisão

1. Save de M5 carregado no M6: criatura no meio de um estágio, sem `lineage`/`health` novos → abre, ramo atual `"base"` até a próxima evolução, nada quebra. (T2)
2. PC desligado por meses: `offline_catchup` com 90 dias não muda saúde nem mata; velhice só depois de 3 dias online. (T2)
3. Morte durante o chat ou com tela cheia: a morte por velhice espera momento calmo; por descuido não espera, mas a cena só começa quando a tela cheia acaba. (T2/T7)
4. App fechado no meio da despedida: na próxima abertura, o renascimento acontece direto (estado `dead` salvo → renasce ao carregar). (T7)
5. Remédio spam: cooldown de 6 h; remédio em ovo ou em criatura saudável não faz nada. (T2)

---

### Tarefa 0: vocabulário e constantes (haiku)

**Arquivos:** `engrama/vocab.py`, `engrama/balance.py`, `tests/test_vocab_m6.py`

Acrescentar exatamente:

`vocab.py`
```python
MEDICINE_ID = "remedio"
BRANCH_STAGES = ("child", "adult", "perfect", "final")
BRANCHES = {
    "child": ("brincalhao", "curioso", "sonhador", "arisco"),
    "adult": ("companheiro", "explorador", "artista", "tecnico", "sombrio"),
    "perfect": ("guardiao", "sabio", "virtuoso", "aventureiro", "rebelde"),
    "final": ("lendario", "mestre", "eco", "sombra"),
}
NEGLECT_BRANCHES = frozenset({"arisco", "sombrio", "rebelde", "sombra"})
INTEREST_KEYS = ("jogos", "arte", "tecnologia", "social", "trabalho")
INTEREST_GROUPS = {   # app category (perception PT or sim-user EN) -> interest
    "jogo": "jogos", "game": "jogos",
    "musica": "arte", "video": "arte", "desenho": "arte", "music": "arte",
    "programacao": "tecnologia", "terminal": "tecnologia", "editor": "tecnologia",
    "chat": "social", "navegador": "social", "browser": "social",
    "escritorio": "trabalho", "office": "trabalho",
}
DEATH_CAUSES = ("old_age", "neglect")
```

`balance.py` (comentário `# M6`)
```python
FINAL_LIFESPAN_S = 30 * 24 * HOUR
OLD_AGE_WARN_S = 3 * 24 * HOUR
NEGLECT_NEED_MEAN = 70.0
NEGLECT_SICK_AFTER_S = 6 * HOUR
CARE_RECOVER_NEED_MEAN = 40.0
SICK_SEVERITY_START = 0.3
SICK_SEVERITY_UP_PER_H = 0.03
SICK_SEVERITY_DOWN_PER_H = 0.05
GRAVE_SEVERITY = 0.8
GRAVE_DEATH_AFTER_S = 24 * HOUR
COLD_PER_ONLINE_H = 1.0 / (30 * 24)
COLD_MIN_S, COLD_MAX_S = 3 * HOUR, 8 * HOUR
COLD_MAX_SEVERITY = 0.4
MEDICINE_COOLDOWN_S = 6 * HOUR
MEDICINE_NEGLECT_RELIEF = 0.5
NEGLECT_BRANCH_CARE = 0.45
REDEEM_CARE = 0.7
TRAIT_INHERIT = 0.25
ANCESTRAL_MAX = 3
FAREWELL_S = 10.0
```

- [ ] Teste: `test_branches_shape` (4 estágios, 4–5 ramos cada, um ramo de descuido por estágio, ids sem acento), `test_interest_groups_values_in_keys`, `test_medicine_not_a_food` (`MEDICINE_ID not in FOOD_IDS`).
- [ ] `-m pytest -q tests/test_vocab_m6.py tests/test_architecture.py` passa.
- [ ] Commit `feat(m6): vocabulary and balance for long life`.

---

### Tarefa 1: escolha de ramo (puro) — onda A

**Arquivos:** criar `engrama/kernel/branches.py`, `tests/kernel/test_branches.py`

**Produz:**
```python
@dataclass(frozen=True)
class BranchContext:
    stage: str                      # stage being entered (in BRANCH_STAGES)
    care_now: float                 # StageMachine.care_quality
    stage_care_mean: float          # mean care over the stage just finished
    life_care_mean: float           # mean care over the whole life
    traits: tuple[float, ...]       # TRAIT_KEYS order, 0..1 (default INITIAL_TRAITS/100)
    interests: dict[str, float]     # INTEREST_KEYS -> share of perceived app time, sums to 1 or all 0
    lineage: tuple[str, ...]        # branches already taken, oldest first
def pick_branch(ctx: BranchContext, seed: int) -> str
def branch_name(branch: str, lang: str) -> str          # PT/EN display name, "base" -> stage-neutral name
BRANCH_NAMES: dict[str, tuple[str, str]]                # id -> (pt, en), all ids of vocab.BRANCHES
def derive_seed(seed: int, generation: int) -> int       # sha256-based, 31-bit, deterministic
```

Regras (spec §5): pontuação por ramo = soma ponderada de traços/interesses/cuidado/linhagem; vence a maior; empate desfeito por `hash` estável de `(seed, stage, branch)` (use sha256, não `hash()`). Ramo de descuido do estágio vence se `stage_care_mean < NEGLECT_BRANCH_CARE`, exceto redenção: último da linhagem em `NEGLECT_BRANCHES` e `stage_care_mean >= REDEEM_CARE` → o descuido é excluído. Ramos de descuido só ganham assim (pontuação normal −∞). Pesos são decisão do implementador, com as ênfases da tabela da spec; documente-os numa tabela no topo do arquivo.

- [ ] Testes:
  - `test_neglect_wins_when_care_low` (cada estágio)
  - `test_redemption_leaves_neglect`
  - `test_social_child_is_playful` (sociabilidade alta, resto médio → `brincalhao`)
  - `test_art_interest_pulls_artist` (adulto, interesses `arte=0.8` → `artista`)
  - `test_tech_interest_pulls_tinkerer`
  - `test_games_interest_pulls_adventurer` (perfeito)
  - `test_legendary_needs_life_care` (final, `life_care_mean ≥ 0.85`)
  - `test_deterministic_and_seed_breaks_ties`
  - `test_every_branch_reachable` (para cada ramo existe um contexto que o escolhe)
  - `test_names_pt_en_complete`
  - `test_derive_seed_stable` (valor fixo para `(1, 2)`).
- [ ] `-m pytest -q tests/kernel/test_branches.py tests/test_architecture.py`.
- [ ] Commit `feat(m6): branch choice from care, traits and interests`.

---

### Tarefa 3: arte por ramo e estágios altos — onda A

**Arquivos:** `engrama/app/art/sprites.py`, `tests/app/test_sprites_m6.py` (e ajustar `tests/app/test_sprites*.py` existentes só se a mudança de tamanho exigir)

**Produz:**
- `Look` ganha `branch: str = "base"` e `lineage: tuple[str, ...] = ()`, lidos de `d.get("branch")`/`d.get("lineage")` com tolerância (como os outros campos).
- `SIZES = {"egg": 16, "baby": 16, "child": 24, "adult": 28, "perfect": 32, "final": 32}`.
- Arte própria para `adult`, `perfect`, `final` (proporções diferentes da criança, corpo mais alto, membros), ainda a partir do genoma.
- Por ramo (todos os ids de `vocab.BRANCHES`): sobreposição de partes (orelhas/chifres, cauda, olhos, padrão), ajuste de paleta (matiz/saturação/valor; ramos de descuido mais escuros e dessaturados) e um acessório desenhado proceduralmente. O acessório do ramo do estágio anterior pode permanecer menor (linhagem), decisão do implementador.
- `ANIMS` ganha `"evolve"` (4 frames: brilho crescente), `"old"` (idle mais lento e encurvado) e `"dead"` (deitada, 2 frames esmaecendo). A chave de cache inclui `branch`.
- Ramo desconhecido (save futuro) → desenha como `"base"`, sem erro.

- [ ] Testes:
  - `test_each_branch_draws` (todo ramo × estágio correspondente × todas as ANIMS → 2–4 superfícies do tamanho certo)
  - `test_branches_differ` (pixels de dois ramos do mesmo estágio e genoma diferem)
  - `test_neglect_branch_darker` (média de valor HSV do sombrio < companheiro)
  - `test_unknown_branch_falls_back`
  - `test_look_from_old_dict` (sem `branch`)
  - `test_cache_key_has_branch`.
- [ ] `-m pytest -q tests/app tests/test_architecture.py`.
- [ ] Commit `feat(m6): branch art and real adult, perfect and final sprites`.

---

### Tarefa 4: memória ancestral, arquivo e gerações (serviços) — onda A

**Arquivos:** `engrama/services/memory/store.py`, `engrama/services/memory/recall.py`, `engrama/services/language/{persona,initiative,service}.py`, criar `engrama/services/generations.py`; testes `tests/services/memory/test_ancestral.py`, `tests/services/test_generations.py`, casos novos em `tests/services/language/test_initiative.py`

**Produz:**
- `MemoryStore.ancestral_candidates(k: int = ANCESTRAL_MAX) -> list[str]`: resumos dos episódios mais marcantes (maior `importance`, desempate `abs(valence)`, depois mais recente), excluindo `kind` em `("ancestral", "arquivo")`, sem dígitos, e nada que a blocklist de tópicos bloqueie.
- `MemoryStore.archive_to(path: Path) -> None`: cópia consistente do banco (API `sqlite3.backup`) para `path` (cria pastas).
- `MemoryStore.new_generation(ancestral: list[str]) -> None`: apaga episódios, fatos, tópicos, opiniões, reflexões e links da geração; **mantém** `blocklist` (incluindo `perceived`) e `app_categories`; grava cada resumo como episódio `kind="ancestral"`, `importance=0.6`.
- Recall: episódios `ancestral` podem aparecer quando as palavras batem; `RecallContext` marca-os (`ancestral=True` ou lista separada); o persona os apresenta como "um sonho de antes de nascer" (PT/EN).
- `persona.FAREWELL_PROMPT` (pt/en) e `persona.build_farewell_messages(...)`; `LanguageService.farewell(cause: str, on_text: Callable[[str], None])`: job de prioridade chat; LLM pronto → fala curta de despedida; senão, balbucio carinhoso; nunca levanta exceção; ovo/bebê → balbucio.
- `InitiativePolicy`: tipo raro `"ancestral"` (mesma cota do M4), só se houver episódio ancestral e estágio ≥ criança.
- `engrama/services/generations.py`:
  ```python
  @dataclass(frozen=True)
  class GenerationRecord:
      n: int; lineage: tuple[str, ...]; seed: int; born_wall: float; died_wall: float
      days: float; cause: str; ancestral: tuple[str, ...]
  def load_generations(path: Path) -> list[GenerationRecord]     # missing/corrupt file -> []
  def append_generation(path: Path, rec: GenerationRecord) -> None   # atomic write
  def delete_generation_archive(data_dir: Path, n: int) -> None      # removes data/generations/<n>/, keeps record
  ```

- [ ] Testes:
  - `test_candidates_top_importance`
  - `test_candidates_skip_digits_and_blocked`
  - `test_archive_copy_opens`
  - `test_new_generation_keeps_blocklist_and_categories`
  - `test_new_generation_wipes_user_facts`
  - `test_ancestral_recalled_on_match`
  - `test_farewell_offline_babbles_never_raises`
  - `test_initiative_ancestral_rare_and_quota`
  - `test_generations_roundtrip_and_corrupt`
  - `test_delete_archive_keeps_record`.
- [ ] `-m pytest -q tests/services tests/test_architecture.py`.
- [ ] Commit `feat(m6): ancestral memory, generation archive and farewell`.

---

### Tarefa 2: kernel — saúde, velhice, morte, interesses, ramos — onda B (depende de T0, T1)

**Arquivos:** `engrama/kernel/{lifecycle,kernel,genome,actions}.py`, testes `tests/kernel/test_health.py`, `tests/kernel/test_life_m6.py`

**Consome:** `pick_branch`, `BranchContext`, `derive_seed` (T1); constantes (T0).

**Produz:**
- `StageMachine`: `stage_care_sum`, `stage_care_t`, `life_care_sum`, `life_care_t` (médias por estágio e vida), `final_age` (tempo no final), `old: bool`, `old_online_s: float`. `update(...)` devolve o estágio novo como hoje.
- `Health`: `sick: bool`, `kind: str` (`""`, `"neglect"`, `"cold"`), `severity: float`, `neglect_s: float` (tempo acumulado com média > 70), `grave_s: float`, `cold_left_s: float`, `last_medicine_t: float = -inf`. `update(dt, needs_mean, rng, online: bool)`; `give_medicine(t) -> bool`. Regras da spec §6, todas só com `online=True`.
- `Kernel`:
  - `__init__(seed, now=0.0, generation: int = 1)`; atributos `generation`, `lineage: tuple[str, ...]`, `dead: bool`, `death_cause: str`, `interest_s: dict[str, float]`, `_traits: tuple`.
  - `observe_traits(vec: Sequence[float]) -> None`.
  - Em `step`: `app_focus` acumula `dt` no grupo de `INTEREST_GROUPS` da categoria atual (`world.last_app`); `food` com `MEDICINE_ID` chama `give_medicine` (ovo não); evolução para estágio em `BRANCH_STAGES` chama `pick_branch` e faz `genome = dataclasses.replace(genome, branch=...)`, acrescenta à `lineage`; velhice/morte conforme spec §4/§6; com `dead`, `step` só avança o tempo (necessidades congeladas, sem ações: `available_actions()` → `()` e `execute` devolve `("idle", True)`).
  - Morte por velhice só em momento calmo: acordada, sem tela cheia, sem `message` nos últimos 5 min.
  - `offline_catchup` não chama `health.update` e não mata; avança `final_age` (a velhice pode começar, mas `old_online_s` só conta online).
  - `available_actions()`: doente tira `play_alone`, `explore`, `show_something`.
  - Canal novo `body.health = [sick, severity, old]`. Confirme que `state_index`/`context` do Q-learning e o SNN não mudam com um canal a mais (leem canais por nome); se mudarem, não acrescente o canal e explique no relatório.
  - `state_dict`/`from_state_dict` com todos os campos novos e padrões para saves antigos (`generation=1`, `lineage=()`, `dead=False`, saúde saudável).
- [ ] Testes:
  - `test_neglect_makes_sick_after_6h`
  - `test_care_heals`
  - `test_grave_then_death_24h_online`
  - `test_cold_rate_about_monthly` (120 dias, sementes 1–3, entre 1 e 8 resfriados)
  - `test_cold_never_grave_when_cared`
  - `test_medicine_cures_cold_and_cooldown`
  - `test_medicine_egg_or_healthy_noop`
  - `test_offline_never_sick_or_dead` (90 dias)
  - `test_old_age_after_final_lifespan_and_3_online_days`
  - `test_old_age_waits_calm_moment`
  - `test_branch_on_each_evolution` (linhagem com 4 ramos ao chegar ao final)
  - `test_interest_from_app_focus` (eventos `app_focus` com `game` → `jogos`)
  - `test_dead_kernel_is_inert`
  - `test_m5_save_loads` (dict sem campos novos)
  - `test_deterministic_life` (mesma semente → mesmo estado após 10 dias com eventos).
- [ ] `-m pytest -q tests/kernel tests/test_architecture.py` e `-m pytest -q -m "not slow"`.
- [ ] Commit `feat(m6): health, old age, death and branching in the kernel`.

---

### Tarefa 6: UI de vida longa — onda B (depende de T3)

**Arquivos:** `engrama/app/snapshot.py`, `engrama/app/ui/{hud,scene,menus,window,__init__}.py`, criar `engrama/app/ui/generations.py`, `engrama/app/i18n/{pt,en}.json`, testes `tests/app/test_life_ui.py`, `tests/app/test_generations_panel.py`

**Produz:**
- `Snapshot` ganha (com padrão): `branch: str = "base"`, `branch_name: str = ""`, `lineage: tuple = ()`, `generation: int = 1`, `sick: bool = False`, `sick_kind: str = ""`, `grave: bool = False`, `old: bool = False`, `dead: bool = False`, `death_cause: str = ""`, `evolved_at: float = -inf` (wall time da última evolução).
- HUD: nome do ramo; sinais de doente, grave (texto de aviso pedindo ajuda) e velhice; tudo PT/EN, sem dígitos.
- Cena: `sick` → anim `sick`; `old` → `old`; evolução → `evolve` por ~3 s após `evolved_at`; `dead` → cena de despedida (deitada, esmaecer, depois contorno) e `window.farewell_text` (string, pode ser vazia) mostrado no balão. Clique depois do texto chama `window.on_farewell_skip` (callable ou None).
- Menu de comida: entrada extra "remédio" ao fim da lista (não está em `FOOD_IDS`; envia `post("food", {"food": MEDICINE_ID})`); oculta para ovo.
- `GenerationsPanel` (F10, `KEY_PANELS`): lista via `window.generations_provider` (duck-typed: `records() -> list` de objetos com os campos de `GenerationRecord`, `delete_archive(n)`); miniatura desenhada com `frames(Look.from_dict({"seed": rec.seed, "branch": rec.lineage[-1] if rec.lineage else "base"}), "final" ou último estágio, "idle")[0]`; duração em palavras (dias→"alguns dias", "umas semanas", "uns dois meses", "uns três meses", "mais de três meses"); causa em palavras; Delete apaga o arquivo da geração selecionada (com confirmação de segunda tecla). Modo dev mostra números.
- i18n: chaves `ui.life.*`, `ui.gen.*`, `branch.<id>` (PT/EN) em sincronia, sem dígitos.
- [ ] Testes:
  - `test_hud_shows_branch_and_signs`
  - `test_grave_warning_text`
  - `test_evolve_anim_window`
  - `test_dead_scene_and_skip`
  - `test_medicine_menu_posts_and_hidden_for_egg`
  - `test_generations_panel_lists_and_deletes`
  - `test_panel_no_digits_normal_mode`
  - `test_i18n_pt_en_in_sync`.
- [ ] `-m pytest -q tests/app tests/test_architecture.py`.
- [ ] Commit `feat(m6): life signs, medicine, evolution and farewell scenes, generations panel`.

---

### Tarefa 5: Runtime renasce e lab com várias vidas — onda C (depende de T2)

**Arquivos:** `engrama/lab/{runtime,simuser,metrics,cli}.py`, testes `tests/lab/test_rebirth.py`, `tests/lab/test_life_metrics.py`

**Produz:**
- `Runtime.tick`: depois de `scheduler.step`, passa `bb` `"traits"` (se houver) para `kernel.observe_traits`. Com `kernel.dead`, não decide nem aprende (só avança o kernel e o log, se houver).
- `Runtime.rebirth(now: float | None = None) -> dict`: devolve um resumo da vida que acabou (`generation`, `lineage`, `seed`, `days`, `cause`, `final_traits`); cria `Kernel(derive_seed(seed_atual, generation+1), now or k.t, generation+1)`; recria módulos e escalonador como no `__init__` (mesma receita, RNGs derivados da semente nova); aplica `TRAIT_INHERIT` no módulo que escreve `"traits"` via `load_state_dict({"traits": biased, "day": 0, "used": zeros})`; zera `_pending`, `_credit`. Mantém `user` e `log`. Save/load pós-renascimento continua bit-idêntico.
- `Runtime.run(..., rebirth: bool = True)`: se morrer, renasce na hora (lab) e guarda o resumo em `self.lives`.
- `PROFILES["neglectful"]`: quase nunca alimenta nem faz carinho (escolha valores que levem a descuido grave em semanas).
- `compute_metrics`/`report`: por geração: linhagem, dias, horas doente, resfriados, causa; agregados.
- CLI `sim` aceita `--days 200`; nada muda para runs curtos.
- [ ] Testes:
  - `test_rebirth_new_seed_and_mind` (Q zerado, traços com viés de 25%)
  - `test_rebirth_save_load_bit_identical`
  - `test_dead_runtime_does_not_learn`
  - `test_neglectful_dies_before_final` (slow)
  - `test_attentive_reaches_final_and_dies_old` (slow; final em 75–90 dias, morte por velhice 105–125)
  - `test_profiles_branch_differently` (slow)
  - `test_200_days_under_8_min` (slow)
  - `test_metrics_per_generation`.
- [ ] `-m pytest -q tests/lab tests/test_architecture.py` (inclui slow desta pasta) e `-m pytest -q -m "not slow"`.
- [ ] Commit `feat(m6): rebirth in the runtime and multi-life lab runs`.

---

### Tarefa 7: host, aceite, bench, README — onda D (depende de todas)

**Arquivos:** `engrama/app/host.py`, `tests/test_m6_acceptance.py`, `tools/bench.py` (só se precisar), `README.md`, `pyproject.toml`

- Snapshot: preencher os campos novos de T6 a partir do kernel; `branch_name` via `branch_name(branch, lang)`; `evolved_at` quando o estágio muda.
- Morte no host:
  1. Ao ver `kernel.dead` pela primeira vez: pede `language.farewell(cause, on_text)` e guarda o texto para `window.farewell_text`.
  2. Depois de `FAREWELL_S` de relógio de parede (ou `on_farewell_skip`), e fora de tela cheia: `ancestral = memory.ancestral_candidates()`; `memory.archive_to(data/generations/<n>/memory.sqlite)`; copia o save atual para `data/generations/<n>/save/`; `append_generation(data/generations.json, ...)`; `runtime.rebirth()`; `memory.new_generation(ancestral)`; limpa `WorkingMemory`; salva.
  3. Se o app abriu com o save já `dead`: renasce direto no início (sem cena), com os mesmos passos.
- `window.generations_provider` com `records()` e `delete_archive(n)`; `window.on_farewell_skip`.
- Config, permissões, blocklist e temas silenciados não mudam no renascimento.
- `tests/test_m6_acceptance.py` (slow, LLM falso): uma vida curta forçada (constantes monkeypatched) do ovo à morte por descuido no host → despedida, arquivo existe, registro gravado, ovo novo com geração 2, memória nova com ≤3 ancestrais e blocklist mantida; abrir com save `dead` renasce; save de M5 abre.
- README PT/EN: seção M6 (ramos, doença e remédio, velhice, morte e herança, F10). `pyproject.toml` → `0.6.0`.
- [ ] `-m pytest -q` completo passa; `tools/bench.py --app --seconds 60` ≤150 MB, ≤2%; `-m engrama --frames 120 --no-llm` sai com 0.
- [ ] Commit `feat(m6): host rebirth, generations, acceptance and docs`.

## Ondas

| Onda | Tarefas | Modelo |
|---|---|---|
| 0 | T0 | haiku |
| A | T1, T3, T4 | sonnet (paralelo) |
| B | T2, T6 | sonnet (paralelo) |
| C | T5 | sonnet |
| D | T7 | sonnet |
