# Engrama M8 — Suporte a Linux: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** o Engrama roda no Linux tão bem quanto no Windows, dentro do que cada sessão permite:
- suíte verde no Linux, com o orçamento de CPU de volta a ≤2%;
- `Config` e Ollama sem `E:\` no Linux;
- percepção no X11, no Hyprland e no Sway, e ociosidade também no KDE e no GNOME;
- olhos por atalho global no X11 e por `engrama --eyes toggle` em qualquer POSIX;
- overlay do M7 em sessão X11;
- inerte em tudo o que a sessão não oferece. Windows sem mudança.

**Arquitetura:**
- Um pacote novo, `engrama/osapi/`, só stdlib, isola o SO do Linux: detecção de sessão pelo ambiente, `ctypes` sobre `libX11`/`libXss`/`libXext`, um cliente Wayland mínimo para `ext_idle_notifier_v1`, IPC do Hyprland e do Sway por socket Unix e ociosidade por `gdbus`.
- A percepção ganha `LinuxSources`, que implementa o protocolo `Sources` do M5 compondo esses backends. O `PerceptionService`, a ordem de checagem e a higienização não mudam.
- `app/desktop.py` ganha `X11Desktop` (mesma interface `Desktop` do M7) com máscara XShape feita da cor-chave.
- O atalho dos olhos ganha uma API X11; o comando `--eyes toggle` manda `SIGUSR1` ao PID do lock do M7.
- O orçamento de CPU volta ao limite com bench em estado estável, cache de `Look`, pulo de quadros idênticos e FPS adaptativo.
- Kernel, mente, módulos, lab e vocabulário não mudam.

**Stack:** Python 3.13, stdlib (`ctypes`, `socket`, `struct`, `select`, `subprocess`, `signal`), psutil, numpy e pygame-ce 2.5 (SDL 2.32). Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-06-engrama-m8-linux-design.md` (as seções 2, 3, 5, 6, 7 e 9 são requisito; a §10 é a base da Tarefa 2). Contexto: specs e planos M5 e M7.

## Restrições globais

- Branch `m8`. Cada agente começa com `git reset --hard m8` no seu worktree.
- **Não mudam:** `EVENT_KINDS`, `ACTIONS`, `FOOD_IDS`, `NEED_KEYS`, `CHANNELS`, `DIGITAL_IDS`, `VARIANTS`, `DISPLAY_MODES`. Kernel, `mind`, `modules` e `lab` não são editados (se um teste provar bug, reportar).
- **Windows sem regressão:** todo caminho novo é escolhido só fora do `win32`. Testes que simulam `sys.platform == "win32"` garantem que `WinSources`, `WinDesktop`, `_WinApi`, os padrões do `Config` e os `creationflags` do `OllamaServer` continuam os do M7.
- **Camadas** (`tests/test_architecture.py`, atualizado na Tarefa 0):
  - `engrama/osapi/**` importa só stdlib, nada de `engrama` nem terceiros;
  - `engrama/services/perception/**` e `engrama/app/desktop.py` podem importar `engrama.osapi`;
  - UI, arte, áudio, i18n, kernel, mente e módulos não importam `engrama.osapi`;
  - as regras antigas continuam.
- **Nada bloqueia a thread principal:** IPC e `gdbus` só na thread da percepção (ou nas chamadas já existentes do overlay, que são `ctypes` locais). Tempo limite em todo socket e subprocesso.
- **Sessão Wayland nunca usa X11** para percepção ou overlay, mesmo com `DISPLAY` presente (XWayland).
- **Privacidade (M5) igual:** nada de `/dev/input`, teclado, tela ou área de transferência; título cru e nome de processo nunca saem do serviço de percepção; ordem olhos → permissão → bloqueio → higienização.
- **Constantes** num bloco `# Task M8` de `engrama/osapi/__init__.py` e de `engrama/balance.py`:

  | Constante | Onde | Valor |
  |---|---|---|
  | `IPC_TIMEOUT_S` | osapi | 0.2 |
  | `GDBUS_TIMEOUT_S` | osapi | 0.5 |
  | `BACKEND_RETRY_S` | osapi | 60 |
  | `FPS_FOCUSED` | balance | 20 |
  | `FPS_STILL` | balance | 10 |
  | `FPS_UNFOCUSED` | balance | 5 |
  | `FPS_RESTING` | balance | 2 |
  | `FPS_OVERLAY_MOVING` | balance | 10 |

  Os quatro valores de FPS que já existem como literais em `Window.target_fps` passam a vir do `balance` com o mesmo valor; só `FPS_STILL` é novo.
- **Orçamento:** ≤150 MB RSS e ≤2% de CPU médio em `test_core_budget` e em `test_overlay_bench_within_budget`, **sem mudar os limites dos testes**. Se não fechar, parar e reportar ao controlador (decisão pendente do usuário, spec §2).
- PT/EN em todo texto novo (`engrama/app/i18n/{pt,en}.json`); sem dígitos no modo normal.
- Commits sem `Co-Authored-By` e sem atribuição a IA. Mensagem exata dada em cada tarefa. Não fazer push.
- Python: `.venv/bin/python` do worktree (no Windows, `.venv\Scripts\python.exe`). Testes com `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`. Os testes gravam em `.pytest_tmp`. **Nunca rode dois pytest ao mesmo tempo.**
- Máquina de referência: CachyOS + Hyprland (Wayland). Nenhum teste automático fala com o Hyprland, o X ou o DBus de verdade; testes "reais" são `skipif` sem a sessão certa e nunca são exigidos.

## Foco de revisão

1. **Windows intocado:** com `sys.platform` simulado `win32`, toda fábrica (`make_sources`, `get_desktop`, `GlobalHotkey.start`, `Config()`, `OllamaServer.start`) escolhe exatamente o que escolhia no M7. (T1, T6, T7, T8)
2. **Sessão vazia ou estranha** (TTY, `SDL_VIDEODRIVER=dummy`, `XDG_SESSION_TYPE=tty`, compositor desconhecido, socket que aceita e não responde, `gdbus` ausente ou travado): tudo inerte, sem exceção, sem atraso perceptível na abertura. (T3, T4, T5, T6)
3. **Parser Wayland:** mensagem cortada entre dois `recv`, tamanho inválido, `wl_display.error`, conexão fechada. Nunca laço infinito nem exceção para fora. (T4)
4. **Pulo de quadros idênticos não muda o que se vê:** a sequência de hashes da tela com e sem o pulo é a mesma. (T2)
5. **Sinal no meio de um save:** o tratador de `SIGUSR1` só marca uma flag; a troca dos olhos acontece no laço principal. O comando confere que o PID é do Engrama. (T7)
6. **Máscara XShape** acompanha a mudança de tamanho da janela do overlay (mini-menu, chat) no mesmo quadro e só é reenviada quando muda. (T8)

---

## Mapa de arquivos

```
engrama/osapi/__init__.py                  constantes, ActiveWindow
engrama/osapi/session.py                   Session, detect(env, platform)
engrama/osapi/x11.py                       X11 (ctypes libX11/libXss/libXext), X11KeyGrab, keysym_for
engrama/osapi/wayland.py                   codificação do protocolo, IdleWatcher (ext_idle_notifier_v1)
engrama/osapi/hyprland.py                  socket_path, request, active_window
engrama/osapi/sway.py                      socket_path, request, active_window (i3-ipc)
engrama/osapi/dbus_idle.py                 idle_ms (gdbus: Mutter IdleMonitor, org.freedesktop.ScreenSaver)
engrama/config.py                          padrões por plataforma; ollama_home/models opcionais
engrama/services/language/server.py        creationflags só no win32; env só com campos definidos
engrama/app/i18n/__init__.py               idioma do sistema no Linux
engrama/app/i18n/{pt,en}.json              textos novos
engrama/balance.py                         FPS
engrama/app/art/sprites.py                 look_of() com cache
engrama/app/ui/window.py, scene.py, hud.py, chat.py, overlay.py   pulo de quadros idênticos, FPS adaptativo, aviso Wayland
tools/bench.py                             estado estável, --first-use, --threads, overlay sem foco
engrama/services/perception/sources.py     LinuxSources, make_sources por sessão
engrama/services/perception/categories.py  normalize_process, nomes do Linux
engrama/services/perception/themes.py      players de música do Linux
engrama/services/perception/hotkey.py      _X11Api, escolha por sessão, erro "wayland"
engrama/app/instance.py                    holder_pid, send_eyes_toggle
engrama/app/host.py                        --eyes, SIGUSR1, ligações
engrama/app/ui/permissions.py              dica de atalho no Wayland
engrama/app/desktop.py                     X11Desktop, update_shape, unavailable_reason
tests/osapi/*, tests/test_architecture.py, tests/test_m8_acceptance.py (+ acréscimos nos testes existentes)
README.md, pyproject.toml
```

## Ondas e modelos

| Onda | Tarefas | Modelo |
|---|---|---|
| 0 | T0 | haiku |
| A | T1 (haiku); T2, T3, T4, T5 (sonnet), paralelas | haiku / sonnet |
| B | T6, T7, T8 (sonnet), paralelas; dependem de T3–T5 e T2 | sonnet |
| C | T9 | sonnet |

Arquivos por onda não se cruzam: em A, só a T2 toca `window.py`/`overlay.py`/`bench.py`; em B, só a T7 toca `host.py` e só a T8 toca `desktop.py`/`overlay.py`/`window.py`.

---

### Tarefa 0: base do `osapi`, regras de arquitetura, textos e constantes — onda 0 (haiku)

**Arquivos:**
- Criar: `engrama/osapi/__init__.py`, `engrama/osapi/session.py`.
- Modificar: `engrama/balance.py` (bloco `# Task M8`), `engrama/app/i18n/pt.json`, `engrama/app/i18n/en.json`, `tests/test_architecture.py`.
- Testes: `tests/osapi/__init__.py`, `tests/osapi/test_session.py`, `tests/test_architecture.py` (acréscimos).

**Interfaces:**
- Produz:
  ```python
  # engrama/osapi/__init__.py
  IPC_TIMEOUT_S = 0.2; GDBUS_TIMEOUT_S = 0.5; BACKEND_RETRY_S = 60.0
  Rect = tuple[int, int, int, int]
  @dataclass(frozen=True)
  class ActiveWindow:
      pid: int | None          # PID no espaço do host, se conhecido
      cls: str                 # classe/app_id da janela, minúsculas ("" se não houver)
      title: str               # cru; nunca sai do serviço de percepção
      fullscreen: bool | None
      rect: Rect | None
  # engrama/osapi/session.py
  @dataclass(frozen=True)
  class Session:
      platform: str            # "win32" | "linux" | outro sys.platform
      kind: str                # "x11" | "wayland" | "none"
      compositor: str          # "hyprland" | "sway" | "kde" | "gnome" | "other" | ""
      env: Mapping[str, str]
  def detect(env: Mapping[str, str] | None = None, platform: str | None = None) -> Session
  ```
  - `kind`: `"none"` no win32, com `SDL_VIDEODRIVER=dummy` ou sem `DISPLAY`/`WAYLAND_DISPLAY`; `"wayland"` se `XDG_SESSION_TYPE == "wayland"` ou (`WAYLAND_DISPLAY` e não `XDG_SESSION_TYPE == "x11"`); `"x11"` se `DISPLAY` e não Wayland.
  - `compositor`: `HYPRLAND_INSTANCE_SIGNATURE` → hyprland; `SWAYSOCK` → sway; `XDG_CURRENT_DESKTOP` contendo `KDE` → kde, `GNOME` → gnome; senão `"other"` (`""` com `kind == "none"`).
  - `balance`: as constantes de FPS das Restrições globais.
  - i18n (PT e EN, sem dígitos): `ui.overlay.unavailable_wayland` ("O overlay ainda não funciona no Wayland" / "The overlay does not work on Wayland yet"), `ui.perm.hotkey_wayland` (dica: "No Wayland, crie um atalho do sistema que rode: engrama --eyes toggle"), `cli.eyes.not_running`, `cli.eyes.windows` (use o atalho global), `cli.eyes.toggled`.
  - Arquitetura: `FORBIDDEN["osapi"] = ("engrama",)` com terceiros proibidos (só stdlib); `"engrama.osapi"` adicionado às listas proibidas de `kernel` e `mind`; os arquivos de `APP_PRESENTATION` não podem importar `engrama.osapi`; `app/desktop.py` pode (`APP_ALLOWED` por arquivo).

- [ ] **Passo 1:** escreva os testes:
  - `test_detect_windows`, `test_detect_dummy_is_none`, `test_detect_hyprland` (ambiente da máquina de referência: `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-1`, `DISPLAY=:1`, `HYPRLAND_INSTANCE_SIGNATURE=x` → `("linux","wayland","hyprland")`), `test_detect_x11_kde`, `test_detect_sway`, `test_detect_tty_none`;
  - `test_active_window_frozen`;
  - `test_osapi_only_stdlib` (árvore falsa com `osapi/a.py` importando `engrama.vocab` e `numpy` → 2 violações);
  - `test_ui_cannot_import_osapi`, `test_desktop_may_import_osapi`, `test_perception_may_import_osapi`;
  - `test_m8_i18n_keys_pt_en_no_digits`;
  - `test_fps_constants_match_m7` (`FPS_FOCUSED == 20`, `FPS_UNFOCUSED == 5`, `FPS_RESTING == 2`, `FPS_OVERLAY_MOVING == 10`).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/osapi tests/test_architecture.py tests/app/test_i18n.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): osapi session detection, layering rules and texts`.

---

### Tarefa 1: `Config`, Ollama e idioma multiplataforma — onda A (haiku)

**Arquivos:**
- Modificar: `engrama/config.py`, `engrama/services/language/server.py`, `engrama/app/i18n/__init__.py`.
- Testes: `tests/test_config.py` (acréscimos), `tests/services/language/test_server.py` (ajuste + acréscimos), `tests/app/test_i18n.py` (acréscimos).

**Interfaces:**
- Produz:
  - `config.default_ollama_exe(platform=None) -> Path`: win32 → `E:\Ollama\ollama.exe` (igual ao M7); senão `shutil.which("ollama")` ou `/usr/local/bin/ollama`.
  - `Config.ollama_home: Path | None` e `Config.ollama_models: Path | None`: padrão no win32 = os `E:\` do M7; fora dele `None` ("não mexer"). `save` grava `None` como `null`; `load` lê `null` como `None`.
  - Fora do win32, `load` troca por padrão do Linux qualquer valor desses três campos que pareça caminho de Windows (`^[A-Za-z]:[\\/]`). No win32 nada muda.
  - `OllamaServer.start()`:
    - `creationflags=CREATE_NO_WINDOW` só no win32;
    - `USERPROFILE`/`HOME` só se `ollama_home` não for `None` (`USERPROFILE` só no win32); `OLLAMA_MODELS` só se `ollama_models` não for `None`;
    - `ValueError` do `popen` também conta como falha (devolve False).
  - `i18n._ui_locale_name()`: win32 igual ao M7; fora dele, primeiro valor não vazio de `LANGUAGE` (primeiro item antes de `:`), `LC_ALL`, `LC_MESSAGES`, `LANG`; depois `locale.getlocale()[0]`. `C`/`POSIX` → `""`. Recebe `env` e `platform` opcionais para teste.

- [ ] **Passo 1:** escreva os testes:
  - `test_config_linux_defaults_no_drive_letter` (`Config()` com plataforma simulada linux e `shutil.which` simulado; `"E:"` fora do JSON salvo; `ollama_home is None`);
  - `test_config_windows_defaults_unchanged` (plataforma simulada win32 → os três caminhos `E:\` do M7);
  - `test_windows_config_loaded_on_linux_falls_back`;
  - `test_null_paths_roundtrip`;
  - em `test_server.py`: `test_server_env_points_to_drive_e` passa a simular win32 (`monkeypatch` de `server.sys.platform`) e continua exigindo `creationflags`; novo `test_server_linux_no_creationflags_no_home` (exige que `"creationflags"` não esteja nos kwargs e que `HOME` seja o do ambiente); `test_popen_valueerror_is_failure`;
  - `test_system_lang_linux_env` (`LANG=pt_BR.UTF-8` → pt; `LANGUAGE=en_US:pt_BR` → en; `LANG=C` → en; vazio → `locale`).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente. A seleção por plataforma lê `sys.platform` no momento da chamada (não na importação), para os testes poderem simular.
- [ ] **Passo 4:** rode `-m pytest -q tests/test_config.py tests/services/language tests/app/test_i18n.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): platform-aware config, Ollama start and system language`.

---

### Tarefa 2: orçamento de CPU de volta a ≤2% — onda A (sonnet)

Base: spec §10 (medições da máquina de referência). Meça antes e depois de cada passo de implementação com `tools/bench.py --app --seconds 30` e `--overlay --seconds 20` e anote a tabela no corpo do commit.

**Arquivos:**
- Modificar: `tools/bench.py`, `engrama/app/art/sprites.py`, `engrama/app/ui/window.py`, `engrama/app/ui/scene.py`, `engrama/app/ui/hud.py`, `engrama/app/ui/chat.py`, `engrama/app/ui/overlay.py`.
- Testes: `tests/app/test_window.py`, `tests/app/test_sprites_audio.py`, `tests/tools/test_bench.py` (novo; rápido, `--seconds 3`).
- **Não** mudar os limites de `tests/test_m3_acceptance.py::test_core_budget` nem de `tests/test_m7_acceptance.py::test_overlay_bench_within_budget`.

**Interfaces:**
- Consome: `balance.FPS_*` (T0).
- Produz:
  - `bench_app(..., first_use: bool = False, threads: bool = False)`: sem `--fake-perception` e sem `--first-use`, grava antes um `config.json` com `perception_asked=True` e todas as permissões `False` (estado estável). `--first-use` mantém o comportamento antigo. `--threads` acrescenta `"threads": {nome_ou_tid: cpu%}` (Linux, de `/proc/<pid>/task/*/stat`; vazio fora do Linux).
  - `bench_overlay`: `window.focused = False` depois de `set_mode("overlay")` (o overlay real não pega foco; spec §9). Sai `"focused": false` no JSON.
  - `sprites.look_of(d: dict | None) -> Look`: cache de uma entrada por identidade do dict (`is`); `Scene.draw` e `Window._drain_host_events`/growler usam `look_of`.
  - `Hud.key(snap, dev) -> tuple`: os valores que o HUD desenha.
  - `ChatBox.quiet(now) -> bool`: sem balão visível, sem texto digitado, sem animação de "pensando".
  - `Scene.moving: bool`: True quando o último `draw` deslocou a criatura (`wander`/variantes com movimento, pulo, squash animado).
  - `Window.skip_identical: bool = True`. No terrário, se `panel is None`, `chat.quiet(now)`, sem aviso, sem efeito digital, sem despedida, e os bytes de `self.low` e `hud.key` forem iguais aos do quadro anterior, o quadro **não** amplia, não desenha HUD e não chama `flip`. No overlay, a mesma regra sobre a superfície baixa do overlay quando a janela não se moveu.
  - `Window.target_fps`: resting → `FPS_RESTING`; sem foco → `FPS_UNFOCUSED`; overlay andando → `max(base, FPS_OVERLAY_MOVING)`; terrário com foco → `FPS_FOCUSED` se `scene.moving` ou painel/chat ativo, senão `FPS_STILL`.

- [ ] **Passo 1:** meça e anote a linha de base (`--app`, `--app --first-use`, `--overlay`, `--app --threads`).
- [ ] **Passo 2:** escreva os testes:
  - `test_look_of_cached_by_identity` (mesmo dict → mesmo objeto; dict novo igual → valor igual);
  - `test_skip_identical_same_pixels`: com relógio falso e snapshot fixo, 60 quadros com `skip_identical=True` e `False` produzem a mesma sequência de hashes de `screen` depois de cada `frame` e o número de `flip` cai (contar com `monkeypatch` de `pygame.display.flip`);
  - `test_no_skip_with_panel_chat_or_notice`;
  - `test_target_fps_still_vs_moving` (parado com foco → 10; andando → 20; sem foco → 5; descansando → 2; overlay andando → 10);
  - `test_bench_app_steady_state_config` (rodar `bench_app` 3 s e conferir que o `config.json` gerado tem `perception_asked` True e permissões False; com `first_use=True`, sem config);
  - `test_bench_threads_key_on_linux` (`skipif` fora do Linux).
- [ ] **Passo 3:** rode os testes. Esperado: FAIL.
- [ ] **Passo 4:** implemente na ordem bench → `look_of` → pulo de quadros → FPS adaptativo, medindo depois de cada um.
- [ ] **Passo 5:** rode `-m pytest -q tests/app tests/tools`, depois `-m pytest -q tests/test_m3_acceptance.py::test_core_budget tests/test_m7_acceptance.py::test_overlay_bench_within_budget`. Esperado: PASS com ≤2%. Se não fechar, **pare** e reporte a tabela ao controlador.
- [ ] **Passo 6:** commit `perf(m8): steady-state bench, cached looks, skip identical frames, adaptive fps` com a tabela antes/depois no corpo.

---

### Tarefa 3: `osapi.x11` — onda A (sonnet)

**Arquivos:**
- Criar: `engrama/osapi/x11.py`.
- Testes: `tests/osapi/test_x11.py`.

**Interfaces:**
- Consome: `ActiveWindow`, `Rect` (T0).
- Produz:
  ```python
  def keysym_for(key: str) -> int | None        # "e"->0x65, "5"->0x35, "f1"->0xFFBE ... "f24"
  MODMASK = {"shift": 1, "ctrl": 4, "control": 4, "alt": 8, "win": 64, "windows": 64}
  LOCK_VARIANTS = (0, 2, 16, 18)                 # nenhum, CapsLock, NumLock, ambos
  class X11:
      @classmethod
      def open(cls, display: str | None = None, loader=ctypes.util.find_library) -> "X11 | None"
      def active(self) -> ActiveWindow | None      # _NET_ACTIVE_WINDOW + _NET_WM_PID + WM_CLASS + _NET_WM_NAME/WM_NAME + geometria + _NET_WM_STATE
      def idle_ms(self) -> int | None              # XScreenSaverQueryInfo; None sem libXss
      def work_area(self) -> Rect | None           # _NET_WORKAREA (área do desktop atual); None sem a propriedade
      def screen_size(self) -> tuple[int, int] | None
      def pointer(self) -> tuple[int, int] | None  # XQueryPointer na raiz
      def set_state(self, win: int, atom: str, on: bool) -> bool   # ClientMessage _NET_WM_STATE para a raiz
      def set_shape(self, win: int, mask: bytes | None, w: int, h: int) -> bool  # XBM LSB-first, linhas alinhadas a byte; None remove; bounding + input
      def close(self) -> None
  class X11KeyGrab:                               # conexão própria, para a thread do atalho
      @classmethod
      def open(cls, display: str | None = None, loader=...) -> "X11KeyGrab | None"
      def grab(self, mask: int, keysym: int) -> bool        # XGrabKey em todas as LOCK_VARIANTS; BadAccess → False
      def wait(self) -> bool                                 # bloqueia (select na conexão + self-pipe); True = tecla, False = parar
      def wake(self) -> None                                 # escreve no self-pipe (chamável de outra thread)
      def ungrab(self) -> None; def close(self) -> None
  ```
  - `open` devolve `None` sem `DISPLAY`, sem `libX11` ou se `XOpenDisplay` falhar. Instala um tratador de erro X (`XSetErrorHandler`) que só registra o último erro; nunca deixa o Xlib encerrar o processo.
  - Todo método público captura qualquer exceção e devolve o valor inerte.
  - Funções puras testáveis sem X: `_parse_wm_class(bytes) -> str`, `_decode_utf8(bytes) -> str`, `_workarea_from(cards, current_desktop) -> Rect | None`.

- [ ] **Passo 1:** escreva os testes:
  - `test_keysym_for` (letras, dígitos, F1/F12/F24, inválidos → None);
  - `test_open_without_display_is_none` (env sem `DISPLAY`) e `test_open_without_lib_is_none` (`loader` devolvendo None);
  - `test_parse_wm_class`, `test_workarea_from` (lista de 4×N cards e desktop atual);
  - `test_real_x11_smoke` (`skipif` se `XDG_SESSION_TYPE != "x11"` ou sem `DISPLAY`): `open()`, `active()`, `idle_ms()`, `pointer()` não lançam.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente com `argtypes`/`restype` declarados em todas as funções usadas e `XFree` em toda propriedade lida.
- [ ] **Passo 4:** rode `-m pytest -q tests/osapi tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): X11 bindings via ctypes`.

---

### Tarefa 4: `osapi.wayland` — ociosidade por `ext_idle_notifier_v1` — onda A (sonnet)

**Arquivos:**
- Criar: `engrama/osapi/wayland.py`.
- Testes: `tests/osapi/test_wayland.py` (com um compositor falso em `socket.socketpair()`).

**Interfaces:**
- Produz:
  ```python
  def encode(obj: int, opcode: int, payload: bytes = b"") -> bytes     # cabeçalho: id u32, (tamanho<<16 | opcode) u32
  def wl_string(s: str) -> bytes                                       # u32 tamanho com NUL + bytes + padding a 4
  def decode(buf: bytes) -> tuple[list[tuple[int, int, bytes]], bytes] # mensagens completas e o resto
  def socket_path(env) -> str | None                                   # XDG_RUNTIME_DIR + WAYLAND_DISPLAY (ou caminho absoluto)
  class IdleWatcher:
      def __init__(self, timeout_s: float, env=None, connect=None, now=time.monotonic) -> None
      def start(self) -> bool       # registro, sync, bind wl_seat e ext_idle_notifier_v1, get_idle_notification(timeout_ms, seat)
      def idle_seconds(self) -> float | None   # lê eventos sem bloquear; idled em T → timeout_s + (now - T); resumed → 0.0
      def close(self) -> None
  ```
  - `start` devolve False (e fecha o socket) sem `WAYLAND_DISPLAY`, se o global não for anunciado até o `wl_callback.done`, por tempo limite (`IPC_TIMEOUT_S` por leitura, no máximo 1 s no total) ou em qualquer erro.
  - Antes do primeiro `idled`, `idle_seconds()` devolve 0.0 (o usuário acabou de estar ativo, ou não há como saber melhor).
  - `wl_display.error` (opcode 0 no objeto 1) ou conexão fechada → o watcher marca-se quebrado e devolve `None` daí em diante.
  - Tamanho de mensagem < 8 ou > 4096 → quebrado. Ids de objeto alocados em sequência a partir de 2.
  - Só lê o socket dentro de `idle_seconds()` e `start()`; nenhuma thread própria.

- [ ] **Passo 1:** escreva os testes:
  - `test_encode_decode_roundtrip`, `test_decode_partial_message_kept`, `test_wl_string_padding`;
  - `test_idle_watcher_full_flow` (compositor falso anuncia `wl_seat` e `ext_idle_notifier_v1`, responde ao sync; depois manda `idled` → `idle_seconds() >= timeout`; depois `resumed` → `< 1`; confere que o cliente pediu `get_idle_notification` com o timeout em ms);
  - `test_no_notifier_global_returns_false`;
  - `test_display_error_breaks_watcher`, `test_closed_socket_returns_none`, `test_garbage_size_breaks_watcher`;
  - `test_no_wayland_display_false`;
  - `test_silent_compositor_times_out` (servidor que não responde → `start()` False em ≤ 1,2 s).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/osapi`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): minimal Wayland client for idle notifications`.

---

### Tarefa 5: `osapi.hyprland`, `osapi.sway` e `osapi.dbus_idle` — onda A (sonnet)

**Arquivos:**
- Criar: `engrama/osapi/hyprland.py`, `engrama/osapi/sway.py`, `engrama/osapi/dbus_idle.py`.
- Testes: `tests/osapi/test_hyprland.py`, `tests/osapi/test_sway.py`, `tests/osapi/test_dbus_idle.py`, fixture `tests/osapi/fixtures/hypr_activewindow.json` (gravada da máquina de referência, com título trocado por `"Exemplo - Editor"`).

**Interfaces:**
- Consome: `ActiveWindow`, `IPC_TIMEOUT_S`, `GDBUS_TIMEOUT_S` (T0).
- Produz:
  ```python
  # hyprland.py
  def socket_path(env) -> str | None     # $XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock (e o caminho antigo /tmp/hypr/... como alternativa)
  def request(cmd: str, env=None, connect=None, timeout=IPC_TIMEOUT_S) -> bytes | None   # escreve cmd, lê até EOF
  def active_window(env=None, connect=None) -> ActiveWindow | None    # "j/activewindow"; pid, class, title, fullscreen (>=2 ou bit de fullscreen), at+size
  # sway.py
  def socket_path(env) -> str | None     # $SWAYSOCK
  def request(msg_type: int, payload: bytes = b"", env=None, connect=None, timeout=IPC_TIMEOUT_S) -> bytes | None   # "i3-ipc" + len u32 + type u32
  def active_window(env=None, connect=None) -> ActiveWindow | None    # GET_TREE (4); nó com "focused": true; pid, app_id ou window_properties.class, name, fullscreen_mode > 0, rect
  # dbus_idle.py
  def idle_ms(run=None, timeout=GDBUS_TIMEOUT_S) -> int | None
  ```
  - `connect(path) -> socket` injetável; o real usa `AF_UNIX` com `settimeout`.
  - Hyprland: objeto vazio `{}` (nenhuma janela) ou JSON inválido → `None`.
  - `dbus_idle.idle_ms`: tenta `gdbus call --session --dest org.gnome.Mutter.IdleMonitor --object-path /org/gnome/Mutter/IdleMonitor/Core --method org.gnome.Mutter.IdleMonitor.GetIdletime` e depois `org.freedesktop.ScreenSaver ... GetSessionIdleTime`; lembra qual funcionou; analisa `(uint64 N,)` e `(uint32 N,)`; `gdbus` ausente (`FileNotFoundError`), código ≠ 0 ou tempo limite → próximo ou `None`. `run` padrão = `subprocess.run(args, capture_output=True, text=True, timeout=timeout)`. O ScreenSaver devolve segundos em algumas implementações e ms em outras: o builder decide pela documentação do KDE e registra a escolha num comentário.

- [ ] **Passo 1:** escreva os testes:
  - Hyprland: `test_socket_path`, `test_active_window_from_fixture` (servidor falso num socket Unix em `tmp_path`), `test_fullscreen_flags`, `test_empty_object_is_none`, `test_missing_socket_none`, `test_silent_socket_times_out` (≤ 0,3 s);
  - Sway: `test_ipc_header`, `test_focused_node_found` (árvore aninhada com nó flutuante focado), `test_xwayland_class_fallback`, `test_no_focus_none`;
  - DBus: `test_mutter_reply_parsed`, `test_screensaver_fallback`, `test_gdbus_missing_none`, `test_timeout_none`, `test_remembers_working_backend` (o runner falso conta chamadas).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/osapi tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): Hyprland and Sway IPC, DBus idle time`.

---

### Tarefa 6: `LinuxSources` e categorias do Linux — onda B (sonnet; depende de T3, T4, T5)

**Arquivos:**
- Modificar: `engrama/services/perception/sources.py`, `engrama/services/perception/categories.py`, `engrama/services/perception/themes.py`.
- Testes: `tests/services/perception/test_linux_sources.py` (novo), `tests/services/perception/test_service.py` (ajuste de `test_null_sources_off_windows`), `tests/services/perception/test_categories.py` e `test_themes.py` (acréscimos).

**Interfaces:**
- Consome: `Session`/`detect` (T0), `X11` (T3), `IdleWatcher` (T4), `hyprland.active_window`, `sway.active_window`, `dbus_idle.idle_ms` (T5).
- Produz:
  ```python
  class LinuxSources:   # implementa Sources (M5)
      def __init__(self, window: Callable[[], ActiveWindow | None] | None,
                   idle: Sequence[Callable[[], float | None]], now=time.monotonic) -> None
      def foreground(self) -> tuple[str, str] | None   # (nome do processo em minúsculas, título)
      def idle_seconds(self) -> float | None           # primeiro backend que responde
      def is_fullscreen(self) -> bool | None
      def cpu_percent(self) -> float | None            # psutil, igual ao WinSources
  def build_linux_sources(session: Session) -> Sources # NullSources se nenhum backend existir
  def make_sources(env=None, platform=None) -> Sources
  # categories.py
  def normalize_process(name: str) -> str   # minúsculas; tira .exe, .x86_64, .x86, .bin, .appimage, .sh, -bin
  ```
  - `foreground`: nome = `psutil.Process(aw.pid).name().lower()` quando há PID; sem PID, `NoSuchProcess`/`AccessDenied`, ou nome genérico de sandbox (`bwrap`, `flatpak-bwrap`) → `aw.cls`. Nome e classe vazios → `None`.
  - Backend de janela por sessão: hyprland → `hyprland.active_window`; sway → `sway.active_window`; x11 → `X11.active`; outros → `None`.
  - Backends de ociosidade por sessão, nesta ordem: wayland → `IdleWatcher(IDLE_AFTER_S)` (iniciado na primeira leitura, na thread da percepção), `dbus_idle.idle_ms`; x11 → `X11.idle_ms`, `dbus_idle.idle_ms`. ms → s.
  - Backend que lança ou devolve `None` fica desligado por `BACKEND_RETRY_S` (com o `now` injetado); toda exceção vira `None`.
  - `make_sources`: win32 → `WinSources` como no M7; linux → `build_linux_sources(detect(env, platform))`; outras → `NullSources`. Uma sessão `kind == "none"` dá `NullSources`.
  - `table_category(p)`: tenta a chave crua (comportamento M7) e depois `normalize_process(p)`. `APP_TABLE` ganha chaves sem sufixo para os apps do Windows que existem no Linux e nomes só do Linux, por exemplo: `firefox`, `chromium`, `google-chrome`, `brave`, `code`, `codium`, `cursor`, `nvim`, `zed`, `pycharm`, `idea`, `steam`, `lutris`, `heroic`, `minecraft-launcher`, `spotify`, `rhythmbox`, `elisa`, `strawberry`, `vlc`, `mpv`, `celluloid`, `discord`, `vesktop`, `telegram-desktop`, `slack`, `soffice.bin`, `libreoffice`, `krita`, `gimp`, `inkscape`, `blender`, `aseprite`, `kitty`, `alacritty`, `foot`, `wezterm-gui`, `konsole`, `gnome-terminal-server`, `ghostty`. O cache `app_categories` continua com a chave crua.
  - `themes._MUSIC_PLAYERS` compara `normalize_process` e ganha `spotify`, `rhythmbox`, `elisa`, `strawberry`, `audacious`, `lollypop`, `amberol`.

- [ ] **Passo 1:** escreva os testes:
  - `test_foreground_pid_name` (psutil simulado), `test_foreground_sandbox_falls_back_to_class`, `test_foreground_dead_pid_class`, `test_fullscreen_passthrough`;
  - `test_idle_chain_first_wins`, `test_idle_backend_disabled_then_retried` (relógio falso: 59 s sem chamar, 61 s chama de novo), `test_backend_exceptions_harmless`;
  - `test_make_sources_windows_unchanged` (`platform="win32"` com `WinSources` substituído por um marcador), `test_make_sources_hyprland_picks_ipc`, `test_make_sources_wayland_never_x11` (env com `DISPLAY` e Wayland → backend de janela não é X11), `test_make_sources_tty_null`, `test_make_sources_darwin_null`;
  - ajuste de `test_null_sources_off_windows`: chama `make_sources(env={}, platform="linux")`;
  - `test_permission_order_with_linux_sources`: os testes de fonte desligada e de bloqueio do M5 rodando com `LinuxSources` sobre backends falsos que contam chamadas (0 sem permissão; `privado` para bloqueado);
  - categorias: `test_linux_names` (`firefox`, `code`, `kitty`, `hollow_knight.x86_64`, `HollowKnight.exe`), `test_windows_keys_unchanged` (toda chave de `APP_TABLE` do M7 dá a mesma categoria); temas: `test_spotify_linux_theme`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services/perception tests/test_m5_acceptance.py tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): Linux perception sources and app names`.

---

### Tarefa 7: olhos no Linux — atalho X11, `--eyes toggle` e dica no Wayland — onda B (sonnet; depende de T3)

**Arquivos:**
- Modificar: `engrama/services/perception/hotkey.py`, `engrama/app/instance.py`, `engrama/app/host.py` (só `main()`: argumento `--eyes`, tratador de sinal e checagem no laço), `engrama/app/ui/permissions.py`.
- Testes: `tests/services/perception/test_hotkey.py` (acréscimos), `tests/app/test_instance.py` (acréscimos), `tests/app/test_permissions_panel.py` (acréscimos), `tests/app/test_eyes_cli.py` (novo).

**Interfaces:**
- Consome: `X11KeyGrab`, `keysym_for`, `MODMASK` (T3); `detect` (T0); `cli.eyes.*`, `ui.perm.hotkey_wayland` (T0).
- Produz:
  - `hotkey._X11Api` com a mesma interface de `_WinApi` (`register`, `unregister`, `get_message`, `post_quit`), sobre `X11KeyGrab`: converte os bits `MOD_*` e o código virtual de `parse_hotkey` em máscara e keysym X; `get_message` devolve `HOTKEY_ID` a cada tecla e `None` ao parar; `post_quit` chama `wake()`.
  - `GlobalHotkey.start()` sem `api` injetada: win32 → `_WinApi` (igual); linux com sessão x11 → `_X11Api`; linux com sessão wayland → `ok=False`, `error="wayland"`; resto → `error="unsupported"`. `GlobalHotkey(..., session=None)` aceita uma `Session` para teste.
  - `InstanceLock.holder_pid(data_dir) -> int | None`: PID gravado no lock se o lock estiver **preso por outro processo** (tenta `flock` não bloqueante; se conseguir, solta e devolve None).
  - `instance.send_eyes_toggle(data_dir, kill=os.kill, is_engrama=None) -> int`: win32 → imprime `cli.eyes.windows`, devolve 2; sem instância → `cli.eyes.not_running`, 1; PID que não é do Engrama (psutil: `cmdline` sem `engrama`) → 1; senão `kill(pid, SIGUSR1)`, imprime `cli.eyes.toggled`, devolve 0.
  - `main()`: `--eyes {toggle}` roda `send_eyes_toggle(data_dir)` e sai **antes** de pegar o lock; com o app aberto e `hasattr(signal, "SIGUSR1")`, instala um tratador que só faz `eyes_flag.set()`; o laço principal, a cada volta, consome a flag e chama `toggle_eyes()`.
  - Painel de permissões: se `hotkey_error() == "wayland"`, mostra `ui.perm.hotkey_wayland` no lugar de `ui.perm.hotkey_failed`.

- [ ] **Passo 1:** escreva os testes:
  - `test_x11api_maps_mods_and_keysym` (`X11KeyGrab` falso registra `grab(mask, keysym)`; `ctrl+alt+e` → máscara 12, keysym 0x65);
  - `test_x11api_loop_and_quit` (o falso devolve uma tecla e depois para; `on_press` chamado uma vez; `stop()` em < 0,6 s);
  - `test_start_wayland_error`, `test_start_windows_uses_winapi` (`sys.platform` simulado e `_WinApi` substituído), `test_start_x11_uses_x11api`;
  - `test_holder_pid_none_when_free`, `test_holder_pid_when_held` (lock preso num subprocesso filho);
  - `test_send_eyes_toggle_codes` (sem instância → 1; Windows simulado → 2; PID estranho → 1; ok → `kill` chamado com `SIGUSR1`, 0);
  - `test_sigusr1_toggles_eyes_in_main_loop` (`skipif` win32, `slow`): rode `python -m engrama --no-llm --seconds 6 --data-dir d` como subprocesso com SDL dummy, espere o lock ficar preso, rode `python -m engrama --eyes toggle --data-dir d` (código 0) e confira `eyes_closed: true` no `config.json` depois que o primeiro sair;
  - `test_permissions_wayland_hint` (provider com `hotkey_error` = "wayland" → texto da dica, sem dígitos).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services/perception tests/app tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m8): eyes hotkey on X11 and eyes toggle command`.

---

### Tarefa 8: overlay em sessão X11 — onda B (sonnet; depende de T2 e T3)

**Arquivos:**
- Modificar: `engrama/app/desktop.py`, `engrama/app/ui/overlay.py` (chamar `update_shape`), `engrama/app/ui/window.py` (aviso por motivo).
- Testes: `tests/app/test_desktop.py` (acréscimos), `tests/app/test_overlay.py` (acréscimos).

**Interfaces:**
- Consome: `X11` (T3), `detect` (T0), pulo de quadros do overlay (T2), `ui.overlay.unavailable_wayland` (T0).
- Produz:
  - `Desktop.update_shape(self, hwnd: int, surface: pygame.Surface) -> None` (padrão: nada). `WinDesktop` não muda (a cor-chave já basta). `FakeDesktop` registra `("shape", hwnd, size, digest)` só quando a máscara muda.
  - `Desktop.unavailable_reason: str = ""`; `NullDesktop(reason="")`. `get_desktop()` usa `"wayland"` numa sessão Wayland e `"unsupported"` nos outros casos inertes.
  - `X11Desktop(Desktop)`, `available = True`:
    - `work_area`: `X11.work_area()`, senão tamanho da tela, senão o fallback do M7;
    - `cursor`: `X11.pointer()`;
    - `foreground_rect`: `X11.active().rect`, ignorando a própria janela (XID de `pygame.display.get_wm_info()["window"]`);
    - `make_overlay(hwnd)`: `pygame.Window.from_display_module()` → `always_on_top = True`; `set_state(hwnd, "_NET_WM_STATE_SKIP_TASKBAR", True)`, `_SKIP_PAGER`, `_STICKY`; guarda o estado anterior; devolve True se a janela e a conexão X existem;
    - `place(hwnd, rect)`: posição e tamanho pelo `pygame.Window` (só quando mudam);
    - `show(hwnd, visible)`: `Window.show()`/`hide()`;
    - `update_shape(hwnd, surface)`: máscara = pixels diferentes de `COLORKEY` (numpy sobre `pygame.surfarray.pixels2d` e `surface.map_rgb(COLORKEY)`), empacotada em XBM com `np.packbits(..., bitorder="little")` por linha; reenvia `X11.set_shape` só se o digest ou o tamanho mudou;
    - `restore(hwnd)`: remove a forma (`set_shape(None)`), desliga sempre-no-topo e os estados, esquece o cache.
  - `get_desktop()`: win32 → igual ao M7; `SDL_VIDEODRIVER=dummy` → `NullDesktop("unsupported")`; linux com `detect().kind == "wayland"` → `NullDesktop("wayland")`; linux x11 com `pygame.display.get_driver() == "x11"` e `X11.open()` ok → `X11Desktop`; resto → `NullDesktop("unsupported")`.
  - `OverlayController.draw` chama `self.desktop.update_shape(self.hwnd, screen)` depois de desenhar e antes do `flip`, também logo depois de uma mudança de tamanho.
  - `Window.set_mode("overlay")` indisponível: aviso `ui.overlay.unavailable_wayland` se `desktop.unavailable_reason == "wayland"`, senão `ui.overlay.unavailable` (igual ao M7).

- [ ] **Passo 1:** escreva os testes:
  - `test_get_desktop_windows_unchanged` (plataforma simulada e `WinDesktop` substituído), `test_get_desktop_wayland_null_with_reason`, `test_get_desktop_dummy_unsupported`;
  - `test_x11desktop_with_fake_x` (`X11` falso e `pygame.Window` simulado): `make_overlay` liga os estados; `place` repetido não reenvia; `restore` remove forma e estados;
  - `test_shape_mask_bits`: superfície 10×3 com um pixel não-chave em (0,0) e (9,2) → bytes XBM esperados;
  - `test_shape_sent_only_on_change` e `test_shape_follows_resize` (overlay com `FakeDesktop`: abrir o mini-menu muda o tamanho e gera um novo `shape` no mesmo quadro);
  - `test_f11_wayland_notice` (`NullDesktop("wayland")` → aviso do Wayland, modo continua terrário).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/app tests/test_architecture.py tests/test_m7_acceptance.py`. Esperado: PASS (o bench do overlay continua ≤2%).
- [ ] **Passo 5:** commit `feat(m8): desktop overlay on X11 sessions`.

---

### Tarefa 9: wiring, acceptance and README — onda C (sonnet)

**Arquivos:**
- Modificar: `engrama/app/host.py` (`main()`), `README.md` (PT e EN), `pyproject.toml` (versão `0.8.0`).
- Criar: `tests/test_m8_acceptance.py` (marcado `slow` onde roda subprocesso ou bench).

**Interfaces:**
- Consome: tudo acima.
- Produz:
  - `main()`: `make_sources()` já escolhe por sessão (sem mudança de chamada); `GlobalHotkey` sem `api` escolhe por sessão; `hotkey.start()` também no Linux; `_PerceptionProvider.hotkey_error` devolve o código cru (`"wayland"`, `"unsupported"` ou a mensagem); `get_desktop()` depois da janela existir; encerramento igual ao M7 (percepção → atalho → host → linguagem → servidor), fechando as conexões `osapi`.
  - Um log de uma linha no início (`logging`, nunca na UI) com `Session.kind`, `compositor` e os backends escolhidos, sem título nem processo.

- [ ] **Passo 1:** escreva `tests/test_m8_acceptance.py`, cobrindo os critérios da spec §7 com o `Host` real, relógio falso, backends falsos e `--no-llm`:
  - `test_windows_choices_unchanged` (critério 2: `sys.platform` simulado `win32` em `Config`, `OllamaServer`, `make_sources`, `get_desktop`, `GlobalHotkey`);
  - `test_linux_config_and_ollama` (critério 3);
  - `test_hyprland_perception_end_to_end` (critérios 5 e 10: servidor IPC falso + `IdleWatcher` falso + `PerceptionService` + `Host`; `app_focus {category}` chega ao host; título cru ausente de `memory.sqlite`, `explog.sqlite`, saves e `repr(snapshot)`);
  - `test_blocked_app_linux_never_leaks` (critério 10);
  - `test_all_backends_failing_harmless` (critério 14);
  - `test_eyes_command_end_to_end` (critério 12, `skipif` win32, subprocesso);
  - `test_overlay_wayland_notice_and_x11_fake` (critério 13);
  - `test_lab_identical_to_m7` (critério 15: mesma fixture de métricas do M7);
  - `test_vocab_frozen` (tuplas iguais às do M7);
  - `test_smoke_frames` (`python -m engrama --frames 120 --no-llm --data-dir <tmp>` sai com 0).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente o resto da ligação.
- [ ] **Passo 4:** rode `-m pytest -q tests/test_m8_acceptance.py` e depois `-m pytest -q`, a suíte inteira. Esperado: tudo PASS, incluindo os dois testes de orçamento.
- [ ] **Passo 5:** rode `tools/bench.py --app --seconds 60 --threads`, `--app --seconds 60 --fake-perception` e `--overlay --seconds 30`. Esperado: ≤150 MB e ≤2%. Anote no PR.
- [ ] **Passo 6:** atualize o README em PT e EN:
  - "Instalar" com os comandos do Linux (`python -m venv .venv`, `source .venv/bin/activate` ou `.venv/bin/activate.fish`, `pip install -e .[dev]`) ao lado dos do Windows;
  - seção nova "Linux (M8)" / "Linux (M8)": tabela do que funciona por sessão (X11; Hyprland; Sway; KDE Wayland; GNOME Wayland), Ollama do sistema, `engrama --eyes toggle` com exemplos de atalho (Hyprland `bind = CTRL ALT, E, exec, ...`, Sway `bindsym`, KDE e GNOME pelas configurações de atalhos personalizados), overlay só no X11;
  - "Testes e bench": `--threads`, `--first-use` e estado estável;
  - "Onde ficam os arquivos": a pasta de dados conforme a decisão do usuário (spec §2).
- [ ] **Passo 7:** commit `feat(m8): Linux wiring, M8 acceptance and README`.
- [ ] **Passo 8:** o controlador pede ao usuário o smoke manual na máquina de referência (Hyprland), e, se houver, numa sessão X11:
  - `python -m engrama` abre; a tela de primeiro uso aparece;
  - com as permissões ligadas, a criatura nota o app em foco (trocar entre terminal e navegador) e se esconde num app em tela cheia;
  - depois de dois minutos sem mexer, chega `user_idle`; ao mexer, `user_active`;
  - um `bind` do Hyprland para `engrama --eyes toggle` fecha e abre os olhos com a janela sem foco;
  - F11 avisa que o overlay não funciona no Wayland;
  - na sessão X11: o atalho `ctrl+alt+e` funciona sem foco, o overlay anda sobre o painel, o clique fora da criatura atravessa e a tela cheia o esconde.
