# Engrama M3 — Corpo e voz: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** transformar a plataforma headless v2 no MVP do usuário: uma criatura visual numa janela pygame, que conversa em PT/EN pelo Ollama gerenciado, mostra a SNN e o resto da mente na Visão da Mente, e descansa manual e automaticamente.

**Arquitetura:**
- Um **host** (`engrama/app/host.py`) é a raiz de composição. Ele roda o `Runtime` v2 numa thread de simulação única e escritora, a 1 Hz em tempo real. Recebe eventos da UI por fila, publica um `Snapshot` imutável e salva periodicamente.
- A UI (`engrama/app/ui`, `art`, `audio`, `i18n`) só lê snapshots e publica eventos.
- A linguagem e a memória são serviços (`engrama/services/language`, `engrama/services/memory`), portados do branch `m1-m2` e adaptados. O LLM nunca escolhe ações.

**Stack:** Python 3.13, pygame-ce 2.5, numpy e psutil. Só stdlib para HTTP (urllib), threads e SQLite. Ollama 0.40 em `E:\Ollama`, modelo padrão `qwen3:1.7b`.

**Spec:** `docs/superpowers/specs/2026-10-31-engrama-arquitetura-v2.md`, §5, §7, §8, §9 e §10 (M3). As decisões de UI, fala e LLM do v1 continuam valendo onde a v2 não diz o contrário: `git show m1-m2:docs/superpowers/specs/2026-10-31-engrama-design.md`, §3, §5.7, §5.10, §5.11 e §9.

## Restrições globais

- **Leveza:** núcleo (kernel + mente + UI, sem LLM carregado) com ≤ 150 MB de RAM e ≤ 2% de CPU médio. Janela a ≤ 20 FPS com foco, 5 FPS sem foco e 2 FPS em descanso.
- **LLM sob demanda:** o LLM só fica carregado durante e logo após a conversa. `keep_alive` padrão = 600 s; depois disso, descarrega.
- **Nada no C:**
  - O Ollama é iniciado pelo próprio Engrama com `E:\Ollama\ollama.exe serve`, com `USERPROFILE`, `HOME` = `E:\Ollama\home` e `OLLAMA_MODELS` = `E:\Ollama\models` (os caminhos vêm de `Config`). O app de bandeja não é usado.
  - Dados do app ficam em `Config.data_dir`; testes, em `<repo>/.pytest_tmp`.
- **Local e offline:** HTTP só para `Config.ollama_url` (localhost).
- **Dependências:** pygame-ce, numpy e psutil. Nada mais no núcleo.
- **Regra de dependência:** a regra atual continua. Além dela:
  - `engrama/app/{ui,art,audio,i18n}/**` e `engrama/app/snapshot.py` importam só `engrama.app`, `engrama.vocab`, `engrama.balance`, stdlib, numpy e pygame;
  - `engrama/services/**` nunca importa `engrama.mind`, `engrama.modules`, `engrama.kernel`, `engrama.lab` nem `engrama.app`;
  - `kernel` e `mind` nunca importam `engrama.app`.
  
  Só `engrama/app/host.py` e `engrama/__main__.py` ligam tudo.
- **Persona:**
  - Nunca números crus: todo dígito sai do prompt de sistema e da resposta.
  - Nunca fala de assistente.
  - Sem emojis.
  - A fala cresce com o estágio (`SPEECH` do v1: egg 0 palavras, baby 6, child 12, adult 30, perfect/final 40).
  - Responde no idioma da mensagem (PT/EN).
- **Fallback sem LLM:** com o LLM offline ou carregando, a conversa vira balbucio e a criatura segue viva.
- **Commits:** sem `Co-Authored-By` e sem qualquer atribuição a IA ou Claude.
- **UI no modo normal:** nenhum número de necessidade visível. Números só no modo dev e na Visão da Mente.
- **Testes de UI:** headless, com `SDL_VIDEODRIVER=dummy` e `SDL_AUDIODRIVER=dummy` definidos em `tests/conftest.py`.

## Foco de revisão

1. **Ollama ausente, parado ou sem o modelo.** O app abre, a criatura vive, a conversa vira balbucio e a UI mostra o estado claramente ("Ollama não encontrado" / "baixando modelo"). Nunca há exceção na thread da UI. Teste em T3 e T10.
2. **Fechar a janela no meio de uma resposta do LLM ou de um save.** O processo termina em ≤ 3 s, threads daemon, com o save final gravado e íntegro. Teste em T5.
3. **Mensagem vazia, só espaços, com emoji ou com mais de 500 caracteres.** A vazia é ignorada; as outras são truncadas em `MAX_INPUT = 500`. Nada quebra e o balão mostra texto limpo. Teste em T3 e T7.
4. **Salto grande de tempo real** (notebook suspenso, debugger parado). O `SimClock` limita o dt por tick a 5 s × escala. Ausência entre sessões entra só uma vez, por `offline_catchup` no carregamento. Teste em T5.
5. **`VizSpec` de tipo desconhecido, dados vazios ou com NaN/inf.** A Visão da Mente desenha um placeholder com o título e segue desenhando o resto. Teste em T8.

---

## Mapa de arquivos

```
engrama/__main__.py                     python -m engrama → app.host.main()
engrama/app/__init__.py
engrama/app/snapshot.py                 Snapshot, Viz, ProposalView, ModuleView (dados imutáveis)
engrama/app/host.py                     Host: thread de simulação, filas, snapshot, save, descanso, main()
engrama/app/rest.py                     RestPolicy (gatilhos automáticos de descanso)
engrama/app/i18n/{__init__.py,pt.json,en.json}   portado de m1-m2:engrama/i18n
engrama/app/art/sprites.py              portado de m1-m2:engrama/art/sprites.py (recebe Look, não Genome)
engrama/app/audio/growl.py              portado de m1-m2:engrama/audio/growl.py
engrama/app/ui/{window,scene,hud,chat,menus,mind_view,viz_draw}.py
engrama/services/language/{client,server,lang,persona,service}.py   portado de m1-m2:engrama/language
engrama/services/memory/store.py        portado de m1-m2:engrama/memory/store.py
engrama/mind/scheduler.py               + set_rest()
engrama/kernel/kernel.py                + egg_clicks
engrama/lab/runtime.py                  + last_proposals, last_choice
tests/app/, tests/services/language/, tests/services/memory/, tests/test_m3_acceptance.py
```

Ondas: **A**: T1, T2, T4, T5 (paralelas, em worktrees) · **B**: T3, T6 · **C**: T7, T8, T9 · **D**: T10.

---

### Tarefa 1: Regra de dependência do app, i18n, sprites e grunhidos

**Arquivos:**
- Criar: `engrama/app/__init__.py`, `engrama/app/i18n/*`, `engrama/app/art/{__init__,sprites}.py`, `engrama/app/audio/{__init__,growl}.py`.
- Modificar: `tests/test_architecture.py`, `tests/conftest.py`.
- Testes: `tests/app/test_i18n.py`, `tests/app/test_sprites_audio.py` (portados de `m1-m2:tests/test_i18n.py` e `m1-m2:tests/art/test_sprites_audio.py`).

**Interfaces:**
- Produz:
  - `engrama.app.i18n`: `t(key: str, **fmt) -> str`, `set_lang(lang)`, `get_lang()`, `system_lang()`.
  - `engrama.app.art.sprites`: `Look` (dataclass congelada com `seed, body, eyes, ears, tail, pattern, palette, voice_pitch`) e `Look.from_dict(d: dict) -> Look`, que aceita o dict de `Genome` do kernel (`Kernel.state_dict()["genome"]`).
  - `engrama.app.art.sprites`: `frames(look, stage, anim) -> list[pygame.Surface]` e `make_egg_crack(look, level) -> Surface`, com `ANIMS` e `SIZES` iguais aos do v1.
  - `engrama.app.audio.growl`: `Growler` (`growl(pitch, kind)`, `set_muted(bool)`), com `KINDS = ("happy","ask","bleh","hatch","evolve","talk")`.

- [ ] **Passo 1:** amplie `tests/test_architecture.py` com as três regras novas da seção Restrições globais. Cubra cada uma com um teste em árvore temporária, no padrão `_tree` existente:
  - `test_app_ui_cannot_import_kernel`
  - `test_services_cannot_import_mind`
  - `test_host_may_import_everything`
- [ ] **Passo 2:** defina `os.environ.setdefault("SDL_VIDEODRIVER", "dummy")` e o mesmo para `SDL_AUDIODRIVER` no topo de `tests/conftest.py`.
- [ ] **Passo 3:** porte i18n, sprites e growl. Troque `genome` por `Look`, troque `engrama.i18n` por `engrama.app.i18n` e porte os testes do v1, ajustando os imports.
- [ ] **Passo 4:** adicione às tabelas `pt.json` e `en.json` as chaves usadas pelas tarefas 6–9:
  - `ui.chat.placeholder`, `ui.rest.on`, `ui.rest.off`, `ui.mind.title`
  - `ui.menu.food`, `ui.menu.models`, `ui.menu.settings`
  - `ui.ollama.missing`, `ui.ollama.pulling`, `ui.ollama.loading`
  - `ui.lang`, `ui.mute`, `ui.dev`
  
  Escreva o teste `test_pt_en_have_same_keys`.
- [ ] **Passo 5:** rode `python -m pytest -q tests/app tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 6:** commit `feat(m3): app layer rules, i18n, procedural sprites and growls`.

### Tarefa 2: Cliente e servidor do Ollama e detecção de idioma

**Arquivos:**
- Criar: `engrama/services/language/{__init__,client,server,lang}.py`.
- Testes: `tests/services/language/test_client.py`, portado de `m1-m2:tests/language/test_client.py`, e `test_server.py`, `test_lang.py`.

**Interfaces:**
- Consome: `engrama.config.Config` (`ollama_exe`, `ollama_home`, `ollama_models`, `ollama_url`).
- Produz:
  - `OllamaClient(cfg, http_json=..., http_stream=...)`, com `tags() -> set[str] | None`, `pull(name, on_progress)`, `warm(model)`, `unload(model)` e `chat(model, messages, num_predict, temperature) -> str`.
  - As exceções `LLMOffline` e `LLMTimeout`.
  - `strip_think(text)`.
  - `OllamaServer(cfg, popen=..., ping=...)`, com `available()`, `running()`, `start() -> bool`, `stop()` e a propriedade `started_by_us`.
  - `detect_lang(text, default="pt") -> str`.

- [ ] **Passo 1:** porte client, server e lang com os testes do v1, ajustando os imports.
- [ ] **Passo 2:** adicione `Config.model: str = "qwen3:1.7b"`, `Config.keep_alive_s: float = 600.0` e `Config.recommended_models = ("qwen3:1.7b", "qwen3:0.6b", "gemma3:1b", "llama3.2:1b")`. Adicione o teste em `tests/test_config.py` de que um config antigo sem esses campos carrega com os padrões.
- [ ] **Passo 3:** escreva o teste `test_server_env_points_to_drive_e`. O `popen` falso recebe `env["OLLAMA_MODELS"] == str(cfg.ollama_models)` e `env["USERPROFILE"] == env["HOME"] == str(cfg.ollama_home)`, além de `creationflags` com `CREATE_NO_WINDOW`.
- [ ] **Passo 4:** escreva os testes `test_stop_only_kills_what_we_started` e `test_missing_exe_is_unavailable_not_error`. Com `ollama_exe` inexistente, `available()` é False e `start()` retorna False sem exceção.
- [ ] **Passo 5:** escreva o teste `test_detect_lang` com 6 frases PT e 6 EN, inclusive sem acento ("vc quer comer?", "do u wanna play"), e uma mensagem só de emoji, que cai no `default`.
- [ ] **Passo 6:** rode `python -m pytest -q tests/services/language tests/test_config.py`. Esperado: PASS.
- [ ] **Passo 7:** commit `feat(m3): managed Ollama client/server and language detection`.

### Tarefa 3: Persona por estágio e serviço de linguagem

**Arquivos:**
- Criar: `engrama/services/language/persona.py`, portado de `m1-m2:engrama/language/persona.py`; `engrama/services/language/service.py`, que substitui `m1-m2:.../worker.py`.
- Testes: `tests/services/language/test_persona.py`, `test_service.py`.

**Interfaces:**
- Consome: T2 e T4 (`MemoryStore.recent`, `WorkingMemory`). Serviços não importam `engrama.app`, então:
  - os textos da persona (balbucio, dica "cérebro carregando", adjetivos e humor), que no v1 vinham de `engrama.i18n`, ficam em tabelas PT/EN dentro de `persona.py`;
  - os nomes de comida chegam por `food_name: Callable[[str, str], str]` (id, idioma → nome), injetado pelo host.
- Produz:
  - `persona.SPEECH`, `persona.build_messages(state: PersonaState, history, user_text, lang) -> list[dict]`, `persona.clean_reply(text, max_words) -> str | None`, `persona.babble(user_text, stage, lang, rng, key=None) -> str` e `persona.valence(text, lang) -> float`, com valor em [-1, 1] e léxico pequeno PT/EN.
  - `PersonaState`: dataclass com `stage: str`, `needs_top: list[str]`, `traits: dict[str, float]`, `mood: str` (rótulo PAD do `affect.pad`: `pad_label`), `curious: bool` (surpresa acima do limiar), `favorites: list[str]`, `disliked: list[str]` e `memories: list[str]`.
  - `LanguageService(client, server, cfg, memory, working, get_state: Callable[[], PersonaState], food_name)`, com:
    - `request(text)`;
    - `replies: queue.Queue[Reply]`, onde `Reply(text, lang, source)` e `source ∈ {"llm","babble"}`;
    - a propriedade `status ∈ {"missing","offline","loading","ready","pulling"}`;
    - `warm()`, `unload()`, `tick(now)`, que descarrega após `keep_alive_s` sem conversa;
    - `pull(name, on_progress)` e `shutdown()`.
  - A fila interna é de prioridade: chat 0 > comentário 1 > reflexão 2 > fatos 3. Jobs de prioridade ≥ 1 só rodam com status `ready` e com `idle()` verdadeiro, sendo `idle` um callable injetado.

- [ ] **Passo 1:** porte a persona. Os traços viram adjetivos por uma tabela local `TRAIT_ADJ[lang][trait][low|high]`, com limiar 35/65 em escala 0–100. A `life.traits` do v1 não é portada. O humor vem de `PersonaState.mood`, mapeado para palavras PT/EN.
- [ ] **Passo 2:** escreva o teste `test_prompt_has_no_digits_and_no_assistant_talk`. Com qualquer `PersonaState` (inclusive memórias com números), o prompt de sistema não contém `\d`, e `clean_reply("Como posso ajudar? 42 😀", 12)` devolve None ou texto sem dígitos, sem emoji e sem frase de assistente.
- [ ] **Passo 3:** escreva o teste `test_reply_length_grows_with_stage`. `clean_reply` corta em `SPEECH[stage][0]` palavras, e o estágio egg sempre balbucia.
- [ ] **Passo 4:** escreva os testes do `LanguageService` com `OllamaClient` falso e `server` falso:
  - `test_offline_babbles_and_retries_after_cooldown`: com `OFFLINE_COOLDOWN = 30`, uma requisição com LLM offline devolve `source="babble"` em ≤ 1 s.
  - `test_loading_babbles_with_hint`.
  - `test_ready_replies_in_message_language`: o system prompt termina com "Responda em português." ou "Reply in English.", conforme `detect_lang`.
  - `test_input_truncated_to_500`.
  - `test_empty_input_ignored`.
  - `test_missing_server_status`: `server.available()` False dá status `missing`, e o chat balbucia.
  - `test_unload_after_keep_alive`: `tick(t0 + 601)` chama `client.unload` uma vez.
  - `test_background_jobs_wait_for_idle`.
- [ ] **Passo 5:** cada resposta `llm` ou `babble` é registrada em `WorkingMemory` (papéis user/assistant). Cada conversa vira episódio em `MemoryStore.add_episode("chat", resumo_sem_digitos, valence)`.
- [ ] **Passo 6:** rode `python -m pytest -q tests/services/language`. Esperado: PASS.
- [ ] **Passo 7:** commit `feat(m3): stage persona and prioritized language service`.

### Tarefa 4: Memória (episódica, com esquecimento, e de trabalho)

**Arquivos:**
- Criar: `engrama/services/memory/{__init__,store}.py`, portado de `m1-m2:engrama/memory/store.py`.
- Teste: `tests/services/memory/test_store.py`, portado.

**Interfaces:**
- Produz: `MemoryStore(db_path, now_fn)` com `add_episode`, `upsert_fact`, `facts`, `bump_topic`, `top_topics`, `retrieve(words, k)`, `recent(n)`, `forget(now)` e `close()`, e `WorkingMemory(maxlen=12)` com `add`, `messages` e `clear`. As constantes são as do v1: `FORGET_AGE = 3 dias`, `FORGET_BELOW = 0.3` e `RECENCY_TAU = 7 dias`.

- [ ] **Passo 1:** porte o código e os testes. Adicione o teste `test_store_is_thread_confined`: o store abre a conexão na thread que o usa. A conexão usa `check_same_thread=False`, com um `threading.Lock` em volta de cada operação. O teste chama `add_episode` de 4 threads ao mesmo tempo, 50 vezes cada, e verifica 200 episódios gravados sem exceção.
- [ ] **Passo 2:** rode `python -m pytest -q tests/services/memory`. Esperado: PASS.
- [ ] **Passo 3:** commit `feat(m3): episodic and working memory store`.

### Tarefa 5: Host, snapshot e descanso

**Arquivos:**
- Criar: `engrama/app/snapshot.py`, `engrama/app/rest.py`, `engrama/app/host.py`.
- Modificar:
  - `engrama/mind/scheduler.py`: `set_rest(on: bool)`; em descanso, todos os módulos rodam com `rate_factor = B.MODULE_MIN_RATE_FACTOR`, e o fator anterior volta ao sair.
  - `engrama/kernel/kernel.py`: a propriedade `egg_clicks`.
  - `engrama/lab/runtime.py`: as propriedades `last_proposals -> tuple[list[Proposal], list[Proposal]]` (live, shadow da última decisão) e `last_choice -> str`.
  - `engrama/balance.py`: um bloco `# Task M3-5` com `HOST_TICK_S = 1.0`, `AUTOSAVE_S = 300.0`, `REST_RAM_FREE_MB = 1000`, `REST_IDLE_S = 1800.0` e `SURPRISE_CURIOUS = 0.5`.
- Testes: `tests/app/test_host.py`, `tests/app/test_rest.py`, `tests/mind/test_scheduler_rest.py`.

**Interfaces:**
- Produz:
  - `Snapshot` (dataclass congelada): `t`, `wall`, `stage`, `action`, `asleep`, `egg_clicks`, `needs: dict[str,float]`, `pad: tuple[float,float,float]`, `pad_label: str`, `traits: dict`, `food_liking: dict`, `surprise: float`, `familiarity: float`, `look: dict` (dict do genoma), `proposals: tuple[ProposalView,...]`, `shadow_proposals`, `winner: str`, `modules: tuple[ModuleView,...]`, `viz: dict[str, tuple[Viz,...]]`, `recipe_name: str`, `recipe_version: int`, `resting: bool` e `rest_reason: str`.
  - `Viz(kind, title, data)`, `ProposalView(action, score, reason, source)` e `ModuleView(name, type, reads, writes, shadow, mean_ms, rate_factor, disabled)`. Todos são cópias, sem referência a arrays vivos.
  - `RestPolicy(now_fn, ram_free_mb_fn)`, com `update(fullscreen: bool, last_input_wall: float) -> str | None` (devolve o motivo do descanso automático ou None) e `manual: bool`.
  - `Host(cfg, data_dir, recipe_path, seed=None, clock=None)`, com:
    - `start()`, `stop(timeout=3.0)`;
    - `post(kind: str, data: dict | None = None)`, thread-safe, que vira `Obs` com o `t` da simulação no próximo tick;
    - `snapshot() -> Snapshot`, a última publicada, sem trava longa;
    - `set_rest(on: bool)`;
    - os callbacks `on_rest_change`, `on_event` (hatch, evolve, action_change), consumidos pela UI.
  - `to_viz(spec: VizSpec) -> Viz`: converte e copia os dados (arrays viram listas). É usado pelo host e pelos testes da T8.
  - `surprise` e `familiarity` vêm dos canais `temporal.*` quando a receita tem SNN, e são 0.0 quando não tem.
  - `main()`: cria a janela da T6 e liga o serviço da T3. É escrito em T10; aqui é só um stub que levanta `NotImplementedError`.

- [ ] **Passo 1:** escreva os testes do scheduler:
  - `test_rest_slows_all_modules_and_restores`;
  - `test_rest_is_saved`, que verifica que o estado de descanso entra no `state_dict` do scheduler.
- [ ] **Passo 2:** escreva os testes do host com relógio falso, `Host(..., clock=FakeClock)` e o método `host.pump(n)`, que roda n ticks na thread chamadora só para teste:
  - `test_post_reaches_kernel_once`: um `pet` postado entra em exatamente um tick.
  - `test_snapshot_is_immutable_copy`: mudar o `needs` do snapshot não afeta o kernel, e arrays não são compartilhados.
  - `test_egg_hatches_after_clicks`: postar `B.EGG_HATCH_CLICKS` cliques muda `stage` de egg para baby e dispara `on_event("hatch")`.
  - `test_autosave_and_resume`: depois de `AUTOSAVE_S` existe save; um novo `Host` carrega e continua com o mesmo `stage` e o mesmo `seed`.
  - `test_offline_catchup_once`: `host.json` guarda o `wall` do save. Ao carregar com wall +2 h, `kernel.offline_catchup` é chamado uma vez com 7200 s, limitado por `OFFLINE_NEED_CAP` no kernel.
  - `test_wall_jump_is_capped`: um salto de relógio de 3600 s num tick avança a simulação ≤ 5 s.
  - `test_stop_saves_and_joins_within_3s`, inclusive com um `post` em andamento.
  - `test_new_creature_gets_random_seed_saved`.
- [ ] **Passo 3:** escreva os testes do descanso:
  - `test_fullscreen_triggers_rest`;
  - `test_low_ram_triggers_rest` (RAM livre < 1000 MB);
  - `test_long_idle_triggers_rest` (≥ 1800 s);
  - `test_manual_overrides`;
  - `test_rest_exit_when_trigger_clears`.
  
  O host em descanso chama `scheduler.set_rest(True)` e publica `resting=True` com `rest_reason`.
- [ ] **Passo 4:** implemente. Detalhes:
  - A simulação roda numa `threading.Thread(daemon=True)`, com tick de `HOST_TICK_S` real vezes `cfg.time_scale`, pelo `SimClock`.
  - O log de experiência fica em `data_dir/explog.sqlite`.
  - O save fica em `data_dir/save` (`Runtime.save`/`Runtime.load`) e `data_dir/host.json` (`{"wall": ..., "seed": ...}`).
  - O snapshot é trocado por atribuição de referência; ler e trocar é atômico no CPython.
  - `viz()` dos módulos é chamado no máximo 1×/s e só se `want_viz` estiver ligado (a UI liga quando a Visão da Mente abre).
- [ ] **Passo 5:** rode `python -m pytest -q tests/app tests/mind tests/lab`. Esperado: PASS.
- [ ] **Passo 6:** commit `feat(m3): live host, immutable snapshot and rest mode`.

### Tarefa 6: Janela terrário, cena, HUD e comida

**Arquivos:**
- Criar: `engrama/app/ui/{__init__,window,scene,hud,menus}.py`.
- Teste: `tests/app/test_window.py`.

**Interfaces:**
- Consome: `Snapshot` (T5), sprites e growl (T1) e i18n (T1).
- Produz:
  - `Window(get_snapshot: Callable[[], Snapshot], post: Callable[[str, dict|None], None], language=None, size=(640, 480))`, com `run()` (laço até fechar), `frame(now) -> None` (um quadro, usado em testes), `target_fps -> int`, `open_panel(name)` e `close_panel()`.
  - `Scene.draw(surface, snap, now)`: cenário pixel simples e a criatura animada conforme `snap.action` (idle, wander → walk, sleep, play_alone → happy, ask_attention → happy com balão "!", hide → corpo parcial, eat após `food`). O ovo racha conforme `egg_clicks`.
  - `Hud.draw(surface, snap)`: ícones de humor e necessidade sem números (≤ 3 ícones das necessidades > 0.6) e um indicador de descanso.
  - O menu de comida lista `FOOD_IDS` com nome i18n.

- [ ] **Passo 1:** escreva os testes:
  - `test_frame_renders_headless`: 30 quadros com um snapshot de cada estágio egg/baby/child e de cada ação de `ACTIONS`, sem exceção.
  - `test_click_on_creature_posts_click_or_pet`: ovo → `click`; criatura → `pet`.
  - `test_food_menu_posts_food_event`: escolher "peixe" posta `("food", {"food": "peixe"})`.
  - `test_fps_policy`: 20 com foco, 5 sem foco, 2 com `snap.resting`.
  - `test_no_digits_rendered_in_normal_mode`: o texto desenhado no HUD passa por um hook de captura, e nenhum texto contém dígitos.
  - `test_growl_on_hatch_and_ask`, com Growler falso.
- [ ] **Passo 2:** implemente. Teclas:
  - **F2:** Visão da Mente.
  - **F3:** descanso manual.
  - **F4:** menu de comida.
  - **F5:** modelos.
  - **F6:** configurações.
  - **F12:** modo dev (números visíveis e escala de tempo).
  - **Esc:** fecha painel.
  
  O fundo é desenhado numa superfície de baixa resolução, escalada por inteiro.
- [ ] **Passo 3:** rode `python -m pytest -q tests/app`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(m3): terrarium window, animated creature, HUD and food`.

### Tarefa 7: Chat

**Arquivos:**
- Criar: `engrama/app/ui/chat.py`.
- Modificar: `engrama/app/ui/window.py`, que integra o chat.
- Teste: `tests/app/test_chat.py`.

**Interfaces:**
- Consome: `LanguageService.request`, `.replies` e `.status` (T3), e `persona.valence` (T3). A janela recebe `language` e `valence_fn` injetados.
- Produz: `ChatBox`, com campo de texto (Enter envia, Shift+Enter quebra linha), histórico curto e balão de fala sobre a criatura por `4 + 0.3 × palavras` segundos.

- [ ] **Passo 1:** escreva os testes:
  - `test_send_posts_message_event_with_valence`: "eu te amo" posta `("message", {"valence": v})` com v > 0, e "você é chato" com v < 0.
  - `test_reply_becomes_bubble`.
  - `test_babble_reply_also_bubbles`.
  - `test_long_and_emoji_input_safe`: 600 caracteres viram 500, e o emoji é removido do balão.
  - `test_empty_enter_does_nothing`.
  - `test_status_line_shows_ollama_missing`, que usa `ui.ollama.missing`.
  - `test_talk_growl_on_reply`.
- [ ] **Passo 2:** implemente. A entrada de texto usa `pygame.TEXTINPUT`/`TEXTEDITING`, para acentos PT. O chat nunca bloqueia: a janela só lê `replies.get_nowait()`.
- [ ] **Passo 3:** rode `python -m pytest -q tests/app`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(m3): chat box and speech bubbles`.

### Tarefa 8: Visão da Mente

**Arquivos:**
- Criar: `engrama/app/ui/{mind_view,viz_draw}.py`.
- Teste: `tests/app/test_mind_view.py`.

**Interfaces:**
- Consome: `Snapshot.viz`, `.proposals`, `.shadow_proposals`, `.winner`, `.modules` e `.recipe_*` (T5). Abrir a visão liga `host.want_viz`.
- Produz:
  - `draw_viz(surface, rect, viz: Viz) -> None`, com um renderizador por tipo:
    - `raster`: matriz de disparos, ou vetor 0/1 visto como uma linha que rola no tempo;
    - `heatmap`: normalizado por min/max finitos;
    - `series`: `{"names", "rows"}`;
    - `bars`: dict nome → valor;
    - `pad3d`: projeção P×A, com D como tamanho do ponto, e rótulo;
    - `table`: lista de linhas.
    
    Tipo desconhecido ou dado inválido viram placeholder com o título.
  - `MindView.draw(surface, snap)`:
    - **coluna fixa:** grafo da receita, com módulos em caixas, setas por canal (`writes` → `reads`) e sombras tracejadas;
    - **propostas do tick:** ação, pontuação e motivo, com a vencedora destacada;
    - **custo por módulo:** ms médio, com marca "rebaixado" quando `rate_factor < 1` e "desligado";
    - **módulos em sombra:** lado a lado com o ativo da mesma família;
    - **grade:** os `viz` de cada módulo.

- [ ] **Passo 1:** escreva os testes:
  - `test_every_default_recipe_viz_draws`: monte `Runtime` com `recipes/default-v1.toml`, rode 120 ticks e converta os `viz()` dos módulos em `Viz`. `draw_viz` não levanta exceção para nenhum deles.
  - `test_unknown_kind_and_nan_draw_placeholder`: `Viz("blob", ...)`, `Viz("heatmap", "x", [[nan, inf]])` e `Viz("bars", "y", {})`.
  - `test_snn_raster_changes_after_events`: postar 10 `pet` muda o raster renderizado (hash da superfície) em relação ao estado sem eventos.
  - `test_winner_highlighted_and_reason_shown`.
  - `test_demoted_module_marked`.
- [ ] **Passo 2:** implemente com fonte pequena. Os números aparecem só aqui e no modo dev.
- [ ] **Passo 3:** rode `python -m pytest -q tests/app`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(m3): Mind View generated from module viz specs`.

### Tarefa 9: Menus de modelos e configurações

**Arquivos:**
- Modificar: `engrama/app/ui/menus.py`, `engrama/app/ui/window.py`.
- Teste: `tests/app/test_menus.py`.

**Interfaces:**
- Consome:
  - `LanguageService.pull` e `.status`, e `OllamaClient.tags` via serviço, pelo método `installed_models() -> set[str] | None` adicionado ao serviço;
  - `Config` e `Config.save`;
  - `i18n.set_lang`;
  - `Growler.set_muted`;
  - `Host.set_rest`.
- Produz: os painéis
  - **models:** lista `Config.recommended_models` marcando os instalados, tem campo livre para outro nome e botão baixar com barra de progresso, e salva `Config.model`;
  - **settings:** idioma da UI PT/EN, mudo, descanso manual e, no modo dev, a escala de tempo 1×/10×/60×.

- [ ] **Passo 1:** escreva os testes:
  - `test_select_model_saves_config`.
  - `test_pull_shows_progress_and_handles_failure`.
  - `test_ui_lang_switch_changes_strings`.
  - `test_mute_toggles_growler`.
  - `test_models_panel_when_ollama_missing`: mostra `ui.ollama.missing` e não tenta baixar.
- [ ] **Passo 2:** implemente.
- [ ] **Passo 3:** rode `python -m pytest -q tests/app`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(m3): model and settings menus`.

### Tarefa 10: Entrada do app, aceitação do M3, bench e README

**Arquivos:**
- Criar: `engrama/__main__.py`, `tests/test_m3_acceptance.py`.
- Modificar: `engrama/app/host.py` (`main()`), `tools/bench.py` (modo `--app`), `README.md` (PT e EN), `pyproject.toml` (versão `0.3.0` e script `engrama = "engrama.app.host:main"`).

**Interfaces:**
- Consome: tudo acima.
- `main(argv=None)`:
  1. carrega `Config` de `data_dir/config.json`;
  2. inicia o `OllamaServer` em segundo plano, sem bloquear a janela;
  3. cria `Host`, `MemoryStore`, `WorkingMemory`, `LanguageService` e `Window`;
  4. ao fechar, chama `window` → `host.stop()` → `language.shutdown()` → `server.stop()`, este só se `started_by_us`.
  
  As flags são `--data-dir`, `--recipe`, `--seed`, `--time-scale`, `--dev`, `--no-llm` e `--frames N` (encerra após N quadros, para smoke test).
- `PersonaState` é montado pelo host a partir do `Snapshot`:
  - `needs_top` são as necessidades > 0.6, ordenadas;
  - `mood` = `pad_label`;
  - `curious` = surprise > `SURPRISE_CURIOUS`;
  - `favorites` e `disliked` são o top 2 e o fundo 2 de `food_liking`, com sinal;
  - `memories` = `MemoryStore.recent(3)`.

- [ ] **Passo 1:** escreva `tests/test_m3_acceptance.py`, marcado `slow`, todo headless:
  - `test_open_hatch_and_live`: `main(["--frames", "300", "--no-llm", ...])` sai com código 0. Num `Host` com relógio rápido, `EGG_HATCH_CLICKS` cliques chocam o ovo, e a criatura troca de ação sozinha em 10 min simulados.
  - `test_chat_pt_and_en_in_character`: com o cliente falso devolvendo texto com dígitos e frase de assistente, as respostas aceitas não têm dígitos, emoji nem frase de assistente; o idioma do prompt segue a mensagem PT e depois EN.
  - `test_llm_offline_creature_keeps_living`: com o servidor ausente, o chat balbucia, os ticks continuam e as necessidades mudam.
  - `test_mind_view_shows_snn_reacting`: raster e surprise mudam depois de eventos.
  - `test_rest_mode_unloads_llm_and_drops_fps`: o descanso manual chama `language.unload()` e dá `target_fps == 2`; o descanso automático por `fullscreen_on` também.
  - `test_core_budget`: `tools/bench.py --app --seconds 60` (janela dummy, `--no-llm`) dá RSS de pico ≤ 150 MB e CPU médio ≤ 2%, com tolerância 1,5× registrada no relatório se a máquina estiver carregada.
- [ ] **Passo 2:** implemente `main()` e `--app` no bench.
- [ ] **Passo 3:** atualize o README em PT e EN:
  - como rodar `python -m engrama`;
  - pré-requisito: Ollama em `E:\Ollama`;
  - teclas F2–F6, F12 e Esc;
  - descanso;
  - Visão da Mente;
  - onde ficam os dados;
  - o que funciona sem o LLM.
- [ ] **Passo 4:** rode `python -m pytest -q`. Esperado: tudo PASS.
- [ ] **Passo 5:** faça o smoke manual (o controlador relata): `python -m engrama --frames 600`, com a janela visível e o Ollama em `E:`.
- [ ] **Passo 6:** commit `feat(m3): app entry point, M3 acceptance tests, app bench and README`.
