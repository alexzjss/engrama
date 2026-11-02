# Engrama M5 — Percepção do PC: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** a criatura percebe o PC só com permissão:
- app em foco (categoria e tema);
- ociosidade do sistema;
- hora;
- tela cheia e PC pesado.

Ela fecha os olhos por atalho global, respeita uma lista de bloqueio, lê arquivos arrastados e transforma tudo em estímulo, memória e comentários raros.

**Arquitetura:**
- Um serviço novo, `engrama/services/perception`, roda numa thread daemon e lê o Windows por uma interface `Sources` injetável (`ctypes` e psutil no real, falsa nos testes).
- A cada leitura ele aplica nesta ordem: olhos fechados, permissões, lista de bloqueio, higienização.
- Só então publica eventos **já existentes** (`app_focus {category}`, `user_active`/`user_idle {source:"system"}`, `fullscreen_on/off`) por um `post` injetado pelo host.
- Processo e título nunca saem do serviço. O tema extraído do título vai para a memória do M4 (`source="percepcao"`).
- Olhos fechados e permissões ficam no `Config` e no host. O kernel só ganha a higienização de `last_app`.

**Stack:** Python 3.13, stdlib (`ctypes`, `threading`), psutil e pygame-ce. Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-03-engrama-m5-percepcao-design.md` (as seções 2, 3, 5, 6, 7 e 9 são requisito; a §9 vale onde detalha a §3). Contexto: os planos M3 e M4 (restrições globais) e o `CLAUDE.md`.

## Restrições globais

- **`EVENT_KINDS` não muda.** Kind novo muda as dimensões da SNN e quebra os saves.
- **Ordem obrigatória em toda leitura de fonte:**
  1. `eyes_closed()` → não lê nada;
  2. permissão da fonte desligada, ou `perception_asked` falso → não lê;
  3. bloqueio → evento `privado`;
  4. higienização → só categoria e tema saem.
- **Privacidade:**
  - nunca gravar em disco, explog, snapshot, prompt ou log de texto o título cru, o caminho completo de arquivo, o conteúdo de arquivo ou o nome de um processo bloqueado;
  - o kernel recebe só a categoria;
  - nada de rede além do LLM local.
- **Permissões no `Config`.** São as chaves existentes de `Config.permissions`:

  | Chave | Fonte |
  |---|---|
  | `process` | app/processo ativo |
  | `active_window` | título |
  | `idle` | ociosidade |
  | `time` | horário |
  | `system_load` | tela cheia e CPU/RAM |
  
  O padrão de **todas** passa a ser `False`. Campos novos: `perception_asked: bool = False`, `eyes_closed: bool = False`, `perception_interval_s: float = 30.0` (valores permitidos 15, 30 e 60), `perception_blocklist: list[str] = []` (entradas do usuário) e `eyes_hotkey: str = "ctrl+alt+e"`.
- **Constantes** num bloco `# Task M5` de `engrama/services/perception/__init__.py`:

  | Constante | Valor |
  |---|---|
  | `IDLE_AFTER_S` | 120 |
  | `FULLSCREEN_POLL_S` | 5 |
  | `HEAVY_CPU_PCT` | 85 |
  | `HEAVY_FOR_S` | 120 |
  | `PERCEIVED_AFFINITY_STEP` | 0.02 |
  | `PERCEIVED_AFFINITY_CAP` | 0.6 |
  | `ACTIVITY_EPISODE_EVERY_S` | 3 × 3600 |
  | `FILE_READ_CAP` | 8192 |
  | `PRIVATE` | `"privado"` |
- **Fora do Windows**, `Sources` real é um objeto nulo: toda leitura devolve None e nada quebra.
- **Robustez:** toda chamada a `Sources` fica em try/except. Uma exceção conta como leitura vazia e é registrada no log uma vez por fonte por minuto.
- **Importações:**
  - `engrama/services/**` não importa `mind`, `modules`, `kernel`, `lab` nem `app`; a percepção pode importar `engrama.services.memory`;
  - a UI não importa `services`;
  - só `host.py` liga tudo.
- **Orçamento:** núcleo com percepção (fontes falsas) ≤ 150 MB e ≤ 2% de CPU.
- **Sem números** no modo normal. PT/EN. Commits sem `Co-Authored-By` e sem atribuição a IA.
- Python em `E:/Documentos/GitHub/digimon/.venv/Scripts/python.exe`. Os testes gravam em `.pytest_tmp`. Nunca rode dois pytest ao mesmo tempo.

## Foco de revisão

1. **Processo que fecha no meio da leitura** (`psutil.NoSuchProcess`) ou janela sem título. Vira leitura vazia, sem evento falso. Teste em T2.
2. **Título com e-mail, caminho ou número** ("fatura_2026.pdf - joao@x.com") não vaza nada além de um tema seguro, ou nenhum. Teste em T3.
3. **Arquivo enorme, binário disfarçado de `.txt`, sem permissão de leitura do SO, ou atalho `.lnk`.** Respeita o teto, decodifica com `errors="replace"`, falha quieto e não segue o atalho. Teste em T6.
4. **Trocar uma permissão ou fechar os olhos no meio de um ciclo de amostragem.** A leitura seguinte já respeita a mudança, porque a verificação é por fonte e na hora da leitura. Teste em T2.
5. **Save antigo com `last_app` = nome de processo.** Ao carregar, vira categoria ou `""`. Teste em T1.

---

## Mapa de arquivos

```
engrama/config.py                          permissões padrão False + campos M5
engrama/kernel/sensors.py                  last_app = categoria; from_dict higieniza
engrama/app/ui/window.py                   para de postar app_focus; tecla F9 olhos; DROPFILE; F8 permissões
engrama/app/snapshot.py, host.py           Snapshot.eyes_closed; Host.set_eyes_closed; ligação no main()
engrama/app/rest.py                        gatilho heavy_pc
engrama/services/perception/__init__.py    constantes
engrama/services/perception/sources.py     Sources (protocolo), WinSources (ctypes+psutil), NullSources
engrama/services/perception/blocklist.py   Blocklist (fábrica + usuário), is_blocked(process, title)
engrama/services/perception/categories.py  APP_TABLE, Categorizer (tabela + cache + fila LLM)
engrama/services/perception/themes.py      extract_theme(process, title, category) -> str | None
engrama/services/perception/service.py     PerceptionService (thread, ordem de checagem, eventos, temas)
engrama/services/perception/hotkey.py      GlobalHotkey (RegisterHotKey + laço de mensagens)
engrama/services/perception/files.py       read_dropped(path) -> FileGlimpse
engrama/services/memory/store.py           app_categories; kind "perceived" no bloqueio; bump perceived
engrama/services/language/service.py       classify_app job; share_file()
engrama/services/language/initiative.py    tipo "activity", eyes_closed
engrama/app/ui/permissions.py              FirstUsePanel (modal), PermissionsPanel (F8)
engrama/app/ui/scene.py                    olhos fechados desenhados
tests/services/perception/*, tests/app/test_permissions_panel.py, tests/test_m5_acceptance.py
```

Ondas: **A**: T1, T2, T4, T6 (paralelas) · **B**: T3, T5 (paralelas) · **C**: T7.

---

### Tarefa 1: Config, higienização de eventos e olhos fechados no host

**Arquivos:**
- Modificar: `engrama/config.py`, `engrama/kernel/sensors.py`, `engrama/app/ui/window.py` (só deixar de postar `app_focus`), `engrama/app/snapshot.py`, `engrama/app/host.py` (`Host`, não o `main()`).
- Testes: `tests/test_config.py`, `tests/kernel/test_kernel.py` (acréscimos), `tests/app/test_host.py` (acréscimos).

**Interfaces:**
- Produz:
  - os campos de `Config` listados nas Restrições globais (um config antigo carrega com os padrões, e `permissions` antigos são **mantidos** se o config já existia);
  - `WorldState.apply("app_focus")` passa a gravar `last_app = category` (com `app` ausente cai para `""`);
  - `WorldState.from_dict` troca um `last_app` que não esteja em `seen_apps` por `""`;
  - `Snapshot.eyes_closed: bool = False`;
  - `Host.set_eyes_closed(on: bool)`, que vai para o snapshot no próximo tick e chama `on_eyes_change(on)` se esse callback existir;
  - `Host.eyes_closed -> bool`.
  - A janela mantém o foco só em `self.focused`, para o FPS, e não posta mais nada no foco.

- [ ] **Passo 1:** escreva os testes:
  - `test_config_m5_defaults_and_old_config`: um config novo tem todas as permissões False e `perception_asked` False. Um JSON antigo com `"permissions": {"idle": true}` carrega com `idle` True e os campos M5 padrão.
  - `test_last_app_is_category_only`: `ingest(Obs(t, "app_focus", {"app": "bank.exe", "category": "privado"}))` deixa `world.last_app == "privado"` e `"bank.exe"` fora de `state_dict()`.
  - `test_old_save_last_app_sanitized`: `from_dict({... "last_app": "steam.exe", "seen_apps": ["jogo"]})` dá `last_app == ""`.
  - `test_window_no_longer_posts_app_focus`: eventos `WINDOWFOCUSLOST`/`WINDOWFOCUSGAINED` não postam nada.
  - `test_eyes_closed_in_snapshot`: `host.set_eyes_closed(True)` e `pump(1)` dão `snapshot().eyes_closed is True`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/kernel tests/app tests/test_config.py tests/lab`. Esperado: PASS. O `simuser` continua postando `app_focus` com categoria.
- [ ] **Passo 5:** commit `feat(m5): perception config, category-only app events, eyes-closed state`.

### Tarefa 2: Serviço de percepção (fontes, ordem de checagem, bloqueio, eventos)

**Arquivos:**
- Criar: `engrama/services/perception/{__init__,sources,blocklist,service}.py` e `categories.py`. `categories.py` só tem `APP_TABLE` e `table_category()` nesta tarefa.
- Testes: `tests/services/perception/{__init__,test_service,test_blocklist}.py`.

**Interfaces:**
- Produz:
  - O protocolo `Sources`, com os métodos:
    - `foreground() -> tuple[str, str] | None`, que devolve (nome do processo em minúsculas, título);
    - `idle_seconds() -> float | None`;
    - `is_fullscreen() -> bool | None`;
    - `cpu_percent() -> float | None`.
  - `WinSources()`, com `ctypes`: `GetForegroundWindow`, `GetWindowTextW`, `GetWindowThreadProcessId` mais `psutil.Process(pid).name()`, `GetLastInputInfo` mais `GetTickCount64`, e o retângulo da janela contra `MonitorFromWindow`/`GetMonitorInfoW`, ignorando o desktop e o shell.
  - `NullSources()` e `make_sources()`, que dá `WinSources` no Windows e `NullSources` fora dele.
  - `Blocklist(user_entries: list[str])`, com `is_blocked(process: str, title: str) -> bool`:
    - substring sem caixa e sem acento;
    - padrões de fábrica `FACTORY` com bancos e afins (`"banco"`, `"bank"`, `"senha"`, `"password"`, `"keepass"`, `"bitwarden"`, `"1password"`, `"itau"`, `"bradesco"`, `"nubank"`, `"caixa"`, `"santander"`, `"paypal"`).
  - `table_category(process: str) -> str | None`, por `APP_TABLE: dict[str, str]`, com ~40 processos comuns nas categorias `navegador`, `programacao`, `jogo`, `musica`, `video`, `chat`, `escritorio`, `desenho` e `terminal`.
  - `PerceptionService(post, sources, get_config, eyes_closed, now_fn=time.time, on_theme=None, on_heavy=None, categorize=None)`:
    - `start()`, `stop()` (daemon, ≤ 0.5 s) e `tick(now)`, que faz um ciclo síncrono para testes;
    - `get_config()` devolve o `Config` atual, que é relido a cada leitura;
    - `categorize(process) -> str` é injetável; o padrão é `table_category(...) or "programa"`;
    - `on_theme(process, title, category)` é chamado só se `active_window` estiver permitida e o app não estiver bloqueado; quem implementa é a T3; o título nunca é guardado no objeto além da chamada;
    - `on_heavy(bool)` muda quando a CPU passa de `HEAVY_CPU_PCT` por `HEAVY_FOR_S`, e só com `system_load`.
  - Eventos postados:
    - `app_focus {"category": c}` só quando a categoria muda e `process` está permitida; um app bloqueado vira `{"category": PRIVATE}`;
    - `user_active` / `user_idle` com `{"source": "system"}` na transição em `IDLE_AFTER_S`, só com `idle`;
    - `fullscreen_on/off` na transição, checando a cada `FULLSCREEN_POLL_S`, só com `system_load`;
    - o ciclo principal segue `cfg.perception_interval_s`.

- [ ] **Passo 1:** escreva os testes, com `FakeSources`, que conta as chamadas por método e é roteirizável:
  - `test_nothing_read_before_first_use`: 10 min de `tick` com `perception_asked=False` deixam todos os contadores em 0 e nada é postado.
  - `test_only_permitted_sources_read`: só `idle` permitida dá `foreground` com 0 chamadas e `user_idle` postado depois de 120 s ocioso.
  - `test_eyes_closed_reads_nothing`: com tudo permitido e os olhos fechados, os contadores ficam em 0.
  - `test_permission_change_mid_cycle`: desligar `process` entre dois ticks deixa a leitura seguinte sem `foreground`.
  - `test_blocked_app_is_private`: com `("bradesco.exe", "Internet Banking")`, o evento é `{"category": "privado"}`, `on_theme` não é chamado, e o nome não aparece em nenhum `post` nem em `repr(service.__dict__)`.
  - `test_app_focus_only_on_category_change`.
  - `test_fullscreen_fast_poll`.
  - `test_heavy_pc_after_two_minutes`.
  - `test_source_errors_are_quiet`: uma fonte que levanta exceção (inclusive `psutil.NoSuchProcess`) não quebra nada e não posta evento falso.
  - `test_null_sources_off_windows`.
  - `test_blocklist_accents_case_user_entries`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m5): permission-gated perception service with blocklist`.

### Tarefa 3: Categorias pelo LLM, temas do título e memória percebida

**Arquivos:**
- Modificar:
  - `engrama/services/perception/categories.py`: `Categorizer`;
  - criar `engrama/services/perception/themes.py`;
  - `engrama/services/memory/store.py`: tabela `app_categories`, `bump_perceived`, `silence_theme`/`unsilence_theme`/`silenced_themes`, e a limpeza de `app_categories` em `forget_all_about_user`;
  - `engrama/services/language/service.py`: `classify_app(process) -> None`, que enfileira um job `P_FACTS`.
- Testes: `tests/services/perception/{test_categories,test_themes}.py` e `tests/services/memory/test_perceived.py`.

**Interfaces:**
- Consome: T2 (`table_category`, a assinatura de `on_theme`, `PRIVATE`, as constantes) e M4 (`bump_topic`, bloqueio, `add_episode`).
- Produz:
  - `Categorizer(memory, language=None)`, com `__call__(process) -> str`. A ordem é: tabela, cache (`app_categories`), e por fim `"programa"`. No último caso chama `language.classify_app(process)` uma vez por processo por sessão.
    - O job só roda com `ready` e `idle`, como a fila já garante.
    - Ele pede ao LLM só o nome do processo e uma categoria de uma lista fechada (as categorias de `APP_TABLE` mais `"programa"`). Uma resposta fora da lista é descartada.
    - O resultado é gravado com `source="llm"`. Uma correção do usuário (`set_app_category(process, cat, "user")`) prevalece.
    - A lista de bloqueio é checada antes, pelo chamador (T2), então um processo bloqueado nunca chega aqui.
  - `MemoryStore.app_category(process) -> str | None`, `set_app_category(process, category, source)`, `app_category_rows()` e `clear_app_categories()`.
  - `extract_theme(process, title, category) -> str | None`, um tema curto em minúsculas, sem dígitos, com até 4 palavras, ou None:
    - jogo: o título sem o sufixo de launcher;
    - música: o trecho antes de " - " em players conhecidos;
    - programação: "código <linguagem>" pela extensão no título (`.py` → "código python");
    - navegador e outros: None;
    - descarta qualquer coisa com `@`, `\`, `/`, `:` ou dígitos.
  - `MemoryStore.bump_perceived(theme, now) -> str`:
    - devolve `""` se o tema estiver silenciado (`blocklist kind="perceived"`, que **não** é liberado por menção nova);
    - soma `PERCEIVED_AFFINITY_STEP`, com afinidade limitada a `PERCEIVED_AFFINITY_CAP` (uma afinidade maior vinda do chat não é reduzida);
    - usa `source="percepcao"`;
    - grava no máximo um episódio `"atividade"` por tema a cada `ACTIVITY_EPISODE_EVERY_S`, com o texto "passou um tempo com <tema>", sem dígitos e ligado ao tópico.
  - `silence_theme(name)` (que o F7 chama ao apagar um tópico com `source="percepcao"`, junto com o `delete_topic` do M4), `unsilence_theme(name)` e `silenced_themes() -> list[str]`.
  - Um `on_theme` pronto para o host: `make_theme_sink(memory, now_fn) -> Callable[[str, str, str], None]`, que chama `extract_theme` e depois `bump_perceived`.

- [ ] **Passo 1:** escreva os testes:
  - `test_table_then_cache_then_llm_once`.
  - `test_llm_answer_outside_list_discarded`.
  - `test_user_correction_wins`.
  - `test_unknown_offline_stays_programa_and_client_not_called`.
  - `test_theme_extraction_cases`, com entradas e saídas exatas:
    - `("hollow_knight.exe", "Hollow Knight", "jogo")` → `"hollow knight"`;
    - `("code.exe", "main.py - engrama - Visual Studio Code", "programacao")` → `"código python"`;
    - `("chrome.exe", "Gmail - joao@x.com", "navegador")` → None;
    - `("spotify.exe", "Daft Punk - Around the World", "musica")` → `"daft punk"`;
    - `("x.exe", "fatura 2026.pdf", "programa")` → None.
  - `test_raw_title_never_stored`: depois do sink com "Hollow Knight - Steam 2026", nem "Steam" nem "2026" aparecem em nenhuma tabela do `memory.sqlite` (dump do texto completo do banco).
  - `test_perceived_affinity_capped_and_episode_throttled`.
  - `test_silenced_theme_never_returns`: depois de `delete_topic` mais `silence_theme`, 100 sinks não recriam o tema; `unsilence_theme` volta a permitir.
  - `test_forget_all_clears_app_categories`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m5): app categories, title themes and perceived memory`.

### Tarefa 4: Atalho global de olhos

**Arquivos:**
- Criar: `engrama/services/perception/hotkey.py`.
- Teste: `tests/services/perception/test_hotkey.py`.

**Interfaces:**
- Produz:
  - `parse_hotkey(spec: str) -> tuple[int, int]`, que dá os modificadores (`MOD_CONTROL`/`MOD_ALT`/`MOD_SHIFT`/`MOD_WIN` mais `MOD_NOREPEAT`) e o código virtual; um spec inválido levanta `ValueError`.
  - `GlobalHotkey(spec: str, on_press: Callable[[], None], api=None)`:
    - `start() -> bool` devolve False se o registro falhar ou se o sistema não for Windows;
    - `stop()`;
    - `ok: bool`;
    - `error: str`;
    - `api` é injetável, com `register(id, mods, vk) -> bool`, `unregister(id)`, `get_message() -> int | None` e `post_quit(thread_id)`.
  - A implementação real roda o `RegisterHotKey(None, id, mods, vk)` e o `GetMessageW` na **mesma** thread daemon, e trata `WM_HOTKEY` chamando `on_press` dentro de try/except.
  - `stop()` posta `WM_QUIT` para aquela thread com `PostThreadMessageW` e espera ≤ 0.5 s.

- [ ] **Passo 1:** escreva os testes, com `api` falsa:
  - `test_parse_hotkey` (`"ctrl+alt+e"`, `"shift+win+f9"`, inválido);
  - `test_press_calls_callback`;
  - `test_register_failure_reports_error`, com `ok False`, `error` não vazio e sem exceção;
  - `test_stop_is_fast`;
  - `test_callback_exception_contained`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services/perception`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m5): global eyes hotkey`.

### Tarefa 5: Telas de permissões, tecla de olhos, olhos na cena e arrastar arquivo

**Arquivos:**
- Criar: `engrama/app/ui/permissions.py`.
- Modificar:
  - `engrama/app/ui/window.py`: F8 abre o painel "permissions"; F9 alterna os olhos por `set_eyes_closed` injetado; o `FirstUsePanel` abre sozinho enquanto `config.perception_asked` for falso e o atributo `window.config` existir; `pygame.DROPFILE` chama `window.on_file_drop(path)` se existir;
  - `engrama/app/ui/scene.py`: com `snap.eyes_closed`, desenha os olhos fechados por cima do sprite, sem mudar `ANIMS`;
  - `engrama/app/ui/__init__.py`: o registro dos painéis;
  - `engrama/app/i18n/{pt,en}.json`: as chaves `ui.perm.*`, com os títulos e a descrição de cada uma das 5 fontes, permitir, agora não, lista de bloqueio, intervalo, temas silenciados, limpar categorias, `ui.perm.hotkey_failed`, `ui.eyes.closed` e `ui.file.refused`.
- Teste: `tests/app/test_permissions_panel.py`.

**Interfaces:**
- Consome, por duck typing (a UI não importa `services`):
  - `window.config` (com `permissions`, `perception_asked`, `perception_interval_s`, `perception_blocklist`, `eyes_closed`);
  - `window.save_config()`;
  - `window.set_eyes_closed(on)`;
  - `window.perception_provider`, com `silenced_themes()`, `unsilence_theme(name)`, `clear_app_categories()` e `hotkey_error() -> str`.
- Produz:
  - `FirstUsePanel(window)`, um painel modal: enquanto aberto, o chat e os cliques na criatura não recebem eventos e a simulação segue.
    - Para cada fonte há "permitir" ou "agora não".
    - No fim grava `permissions[...]` e `perception_asked=True` e chama `save_config()`.
    - Esc ou fechar sem responder conta como "agora não" para o que faltar, e também grava `perception_asked=True`.
    - F9 e o atalho continuam funcionando com o painel aberto.
  - `PermissionsPanel(window)`:
    - liga e desliga as 5 fontes;
    - escolhe o intervalo entre 15, 30 e 60 s, mostrados como "rápido/normal/lento" no modo normal (sem números);
    - adiciona e remove entradas da lista de bloqueio por campo de texto;
    - lista os temas silenciados com "reativar";
    - tem um botão "limpar categorias";
    - mostra `ui.perm.hotkey_failed` se `hotkey_error()` não for vazio.
  - Todo texto passa por `hud.draw_text`, sem dígitos no modo normal.

- [ ] **Passo 1:** escreva os testes, headless e com fakes:
  - `test_first_use_opens_until_answered_and_saves`;
  - `test_close_without_answer_means_not_now`;
  - `test_first_use_is_modal_but_f9_works`;
  - `test_toggle_permission_saves_config`;
  - `test_blocklist_add_remove`;
  - `test_unsilence_theme_calls_provider`;
  - `test_no_digits_in_permissions_panel_normal_mode`;
  - `test_eyes_closed_drawn_changes_frame`, comparando o hash da superfície com e sem `eyes_closed`;
  - `test_dropfile_calls_handler`;
  - `test_hotkey_failed_notice`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/app tests/test_architecture.py`. Esperado: PASS. As chaves PT e EN continuam iguais.
- [ ] **Passo 5:** commit `feat(m5): permissions screens, eyes key and drawing, file drop hook`.

### Tarefa 6: Arquivo arrastado

**Arquivos:**
- Criar: `engrama/services/perception/files.py`.
- Modificar:
  - `engrama/services/language/service.py`: `share_file(glimpse) -> None`;
  - `engrama/services/language/persona.py`: `FILE_PROMPT[lang]`.
- Testes: `tests/services/perception/test_files.py` e `tests/services/language/test_share_file.py`.

**Interfaces:**
- Produz:
  - `@dataclass(frozen=True) FileGlimpse(name: str, kind: str, size_word: str, text: str | None, entries: tuple[str, ...])`:
    - `kind ∈ {"texto","codigo","imagem","pasta","binario"}`;
    - `size_word` vale "pequeno", "médio" ou "grande", sem número;
    - `name` é só o nome base, nunca o caminho.
  - `read_dropped(path: str, blocklist=None, cap=FILE_READ_CAP) -> FileGlimpse | None`:
    - devolve None se o nome casar com a lista de bloqueio, se o arquivo não existir ou não for legível, ou se for um `.lnk` (que não é seguido);
    - texto ou código, por uma lista de extensões: lê no máximo `cap` bytes e decodifica UTF-8 com `errors="replace"`; mais de 10% de U+FFFD rebaixa o arquivo para `binario` sem texto;
    - pasta: só os nomes do primeiro nível, no máximo 20, ordenados, sem abrir nada;
    - imagem ou binário: só metadados.
  - `LanguageService.share_file(glimpse)`:
    - põe na fila de prioridade de chat um job que monta o prompt com `FILE_PROMPT` (nome, tipo e o trecho de texto com dígitos removidos do **prompt de sistema**, mas o trecho entra como mensagem do usuário truncada);
    - responde pelo LLM ou, se ele não estiver pronto, balbucia e guarda o glimpse como mensagem pendente (o mecanismo do M3), só em memória;
    - grava `add_episode("arquivo", "mostrou um arquivo de <kind>", importance=0.5)`, sem nome e sem dígitos;
    - no ovo, não chama o LLM.

- [ ] **Passo 1:** escreva os testes:
  - `test_text_capped`: um `.py` de 50 KB dá `len(text.encode()) ≤ 8192`.
  - `test_folder_first_level_only`.
  - `test_image_metadata_only`.
  - `test_blocked_name_refused`.
  - `test_binary_disguised_as_txt`.
  - `test_unreadable_and_lnk_return_none`.
  - `test_share_file_ready_replies_and_stores_safe_summary`: o episódio gravado não contém o nome do arquivo, o caminho nem dígitos.
  - `test_share_file_offline_babbles_then_answers_after_warm`.
  - `test_share_file_egg_no_llm`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m5): show-a-file reading and comments`.

### Tarefa 7: Iniciativa de atividade, PC pesado, ligação no `main()`, aceitação e README

**Arquivos:**
- Modificar:
  - `engrama/services/language/initiative.py`: os parâmetros `activity` e `eyes_closed`, e o tipo `"activity"`;
  - `engrama/services/language/service.py`: `spontaneous("activity", topic)`, com o prompt `SPONTANEOUS_PROMPT[lang]["activity"]` em persona.py;
  - `engrama/app/rest.py`: `update(..., heavy_pc: bool = False)` com o motivo `"heavy_pc"`;
  - `engrama/app/host.py`: `main()` e o host passam o `heavy_pc` para o `RestPolicy`, e `user_active` de sistema conta como input;
  - `README.md` (PT e EN);
  - `pyproject.toml`: a versão `0.5.0`.
- Criar: `tests/test_m5_acceptance.py`, marcado `slow`.

**Interfaces:**
- Consome: tudo acima.
- Produz:
  - `InitiativePolicy.update(..., activity: str | None = None, eyes_closed: bool = False)`:
    - `eyes_closed` bloqueia tudo;
    - para criança+, alterna entre `("activity", activity)` e `"current"` quando `activity` não é None nem `"privado"`;
    - a cota continua a do M4.
  - Em `main()`:
    - `PerceptionService(host.post, make_sources(), lambda: cfg, lambda: cfg.eyes_closed, on_theme=make_theme_sink(memory, time.time), on_heavy=host.set_heavy_pc, categorize=Categorizer(memory, language))`;
    - `GlobalHotkey(cfg.eyes_hotkey, toggle_eyes)`, em que `toggle_eyes` muda `cfg.eyes_closed`, chama `save_config()` e `host.set_eyes_closed`;
    - `window.on_file_drop = lambda p: language.share_file(g)` quando `read_dropped(p, blocklist)` não for None, e senão um balão `ui.file.refused`;
    - `window.perception_provider`;
    - a `activity` para a iniciativa é o último tema ou categoria permitida (guardado pelo sink em memória, nunca o título);
    - o encerramento é perception → hotkey → host → language → server.
  - `Host.set_heavy_pc(on: bool)`.

- [ ] **Passo 1:** escreva `tests/test_m5_acceptance.py`, cobrindo os critérios 1–9 da spec §7 com o `Host` real (`pump`, relógio falso), `PerceptionService` com `FakeSources`, LLM falso e `--no-llm` onde couber:
  - `test_first_use_blocks_all_reads`;
  - `test_permission_per_source`;
  - `test_blocked_app_never_leaks`, que procura "bradesco" e o título em `memory.sqlite`, `explog.sqlite`, nos saves, em `repr(snapshot)` e nos prompts do cliente falso;
  - `test_eyes_closed_persists_and_shows`;
  - `test_title_theme_not_raw`;
  - `test_llm_category_only_when_ready`;
  - `test_activity_comment_quota_and_blocks`;
  - `test_file_drop_cases`;
  - `test_source_exceptions_harmless`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente o resto da ligação.
- [ ] **Passo 4:** rode `-m pytest -q tests/test_m5_acceptance.py` e depois `-m pytest -q`, a suíte inteira. Esperado: tudo PASS.
- [ ] **Passo 5:** rode o bench `tools/bench.py --app --seconds 30`, com percepção usando fontes falsas (adicione `--fake-perception` ao bench). Esperado: ≤ 150 MB e ≤ 2% de CPU. Rode também o smoke `python -m engrama --frames 120 --no-llm --data-dir <tmp>`, que deve sair com código 0.
- [ ] **Passo 6:** atualize o README em PT e EN:
  - permissões e a tela de primeiro uso;
  - F8 e F9;
  - o atalho global;
  - a lista de bloqueio;
  - o que é e o que nunca é guardado;
  - arrastar arquivo.
- [ ] **Passo 7:** commit `feat(m5): activity initiative, heavy-PC rest, wiring, M5 acceptance and README`.
- [ ] **Passo 8:** o controlador pede ao usuário o smoke manual no Windows real:
  - `python -m engrama`;
  - a tela de primeiro uso aparece;
  - o atalho de olhos funciona com a janela sem foco;
  - um jogo em tela cheia faz ela se esconder.
