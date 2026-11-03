# Engrama M7: Presença — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a criatura sai da janela e anda sobre a barra de tarefas (overlay), pede coisas digitais de brincadeira e ganha variantes visuais de comportamento por estágio.

**Architecture:** tudo no app. Um módulo `app/desktop.py` isola as APIs do Windows (ctypes) com um fake para testes; `app/ui/variants.py` escolhe variantes visuais das 8 ações; `app/digital.py` é a máquina de estados pura dos pedidos digitais; `app/ui/overlay.py` controla a janela pequena que anda na faixa. Kernel, mente e lab não mudam.

**Tech Stack:** Python 3.13, pygame-ce, numpy, ctypes (user32), pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-engrama-m7-presenca-design.md`

## Global Constraints

- `ACTIONS`, `EVENT_KINDS`, `FOOD_IDS`, `NEED_KEYS`, `CHANNELS` não mudam. Kernel, `mind`, `modules`, `lab`, `services` não são editados (exceto se um teste provar bug; reportar).
- Camadas (`tests/test_architecture.py`): `app/ui`, `app/art`, `app/desktop.py`, `app/digital.py` importam só `engrama.app` (não `host`), `vocab`, `balance`, stdlib, numpy, pygame, ctypes. Só `app/host.py` e `__main__` ligam tudo.
- Orçamento: ≤150 MB RSS, ≤2% CPU médio, inclusive com overlay (`tools/bench.py --app --overlay`).
- Todo texto novo em PT e EN (`engrama/app/i18n/{pt,en}.json`); nada de dígitos no modo normal.
- Testes com SDL dummy; `desktop` real nunca é chamado em testes (usar `FakeDesktop`).
- Nada de internet; dados só no data dir (E:).
- Commits sem trailer de coautoria nem atribuição a IA. Não fazer push.

## Review Focus

1. Tela cheia/jogo: o overlay some enquanto `snap.fullscreen` e nunca fica por cima. (T4)
2. Clique fora da criatura atravessa: a janela usa cor-chave; o fundo do overlay é preenchido exatamente com `COLORKEY` e nada desenhado tem essa cor. (T1/T4)
3. Área de trabalho estranha (barra em cima/lateral, auto-ocultar, área menor que a janela): a criatura fica sempre dentro da área útil. (T4)
4. Mini-menu/chat perto da borda: a janela cresce para dentro da tela. (T4)
5. Save M6 / config sem `display_mode` carrega no terrário; overlay indisponível → aviso e fica no terrário. (T0/T4/T5)

---

### Tarefa 0: vocabulário, config, snapshot, i18n — onda 0

**Files:** `engrama/vocab.py`, `engrama/balance.py`, `engrama/config.py`, `engrama/app/snapshot.py`, `engrama/app/i18n/{pt,en}.json`; Test: `tests/test_vocab_m7.py`

**Produces:**
- `vocab.DIGITAL_IDS = ("ram", "defrag", "update", "cache", "cooler")`; `vocab.VARIANTS = ("jump", "dance", "yawn", "nap_clock", "chase", "look_cursor", "peek", "dig", "found")`; `vocab.DISPLAY_MODES = ("terrarium", "overlay")`.
- `balance` (bloco `# M7`): `DIGITAL_REQUEST_MIN_GAP_S = 2*HOUR`, `DIGITAL_REQUEST_TTL_S = 30*60`, `DIGITAL_REQUEST_P = 0.35` (chance de um `ask_attention` virar pedido), `CURSOR_POLL_HZ = 10`, `CURSOR_NEAR_PX = 150`, `OVERLAY_WALK_PX_S = 40`.
- `Config.display_mode: str = "terrarium"` (valor desconhecido no load → `"terrarium"`).
- `Snapshot` novos campos com padrão: `fullscreen: bool = False`, `theme: str = ""` (tema percebido atual, M5), `digital_request: str = ""`.
- i18n: `digital.<id>` (nome), `digital.ask.<id>` (fala do pedido), `ui.menu.digital`, `ui.overlay.unavailable`, `ui.overlay.back`, `ui.overlay.talk`, `ui.menu.overlay` (PT/EN).

- [ ] Teste `tests/test_vocab_m7.py`: tuplas acima exatas; `Config.load` de um JSON sem `display_mode` → `"terrarium"`, com `"xyz"` → `"terrarium"`, roundtrip `"overlay"`; `Snapshot()` tem os padrões; toda chave nova existe em pt e en e nenhum valor tem dígitos.
- [ ] Implementar; rodar `pytest -q tests/test_vocab_m7.py tests/test_architecture.py`; commit `feat(m7): vocab, config and snapshot fields for presence`.

---

### Tarefa 1: `app/desktop.py` — onda A

**Files:** Create `engrama/app/desktop.py`; Test `tests/app/test_desktop.py`

**Produces:**
```python
COLORKEY = (255, 0, 255)
Rect = tuple[int, int, int, int]          # x, y, w, h em pixels de tela
class Desktop:                            # interface; NullDesktop implementa tudo inerte
    available: bool
    def work_area(self) -> Rect: ...      # área útil do monitor principal (SPI_GETWORKAREA)
    def cursor(self) -> tuple[int, int] | None: ...          # GetCursorPos
    def foreground_rect(self) -> Rect | None: ...            # GetForegroundWindow + GetWindowRect; None se for a própria janela
    def make_overlay(self, hwnd: int) -> bool: ...           # sem borda, WS_EX_LAYERED|TOOLWINDOW|TOPMOST, LWA_COLORKEY=COLORKEY
    def place(self, hwnd: int, rect: Rect) -> None: ...      # SetWindowPos(HWND_TOPMOST, SWP_NOACTIVATE); só chama se mudou
    def show(self, hwnd: int, visible: bool) -> None: ...
    def restore(self, hwnd: int) -> None: ...                # desfaz make_overlay (estilos originais guardados)
class NullDesktop(Desktop): available = False   # work_area=(0,0,1280,720), cursor=None, foreground_rect=None, make_overlay=False
class FakeDesktop(Desktop):              # para testes: available=True, atributos settable work=..., cur=..., fg=...; registra calls em .calls
def get_desktop() -> Desktop             # WinDesktop se sys.platform=="win32" e user32 carrega e SDL_VIDEODRIVER != "dummy"; senão NullDesktop
```
- `WinDesktop` usa `ctypes.windll.user32` com assinaturas declaradas; qualquer exceção → método retorna o valor inerte (nunca lança). Chamar `SetProcessDpiAwareness`/`SetProcessDPIAware` uma vez para coordenadas reais.

- [ ] Testes: `NullDesktop` nunca lança e retorna inertes; `FakeDesktop.place` só registra quando o rect muda; `get_desktop()` com `SDL_VIDEODRIVER=dummy` → `NullDesktop`; em win32, instanciar `WinDesktop` e chamar `work_area()` retorna 4 ints com w,h>0 (pular fora do Windows); `make_overlay(0)` não lança.
- [ ] Implementar; commit `feat(m7): desktop API wrapper for the overlay`.

---

### Tarefa 2: variantes de comportamento e animações — onda A

**Files:** Create `engrama/app/ui/variants.py`, `engrama/app/art/items.py`; Modify `engrama/app/art/vpet/anim.py`, `engrama/app/ui/scene.py`; Test `tests/app/test_variants.py`

**Produces:**
```python
@dataclass(frozen=True)
class VariantCtx:
    stage: str; pad: tuple[float, float, float]; needs: dict[str, float]; overlay: bool
    cursor_near: bool = False; theme: str = ""; peek_ok: bool = False; asleep: bool = False
def pick_variant(action: str, ctx: VariantCtx, seed: int, n: int) -> str   # "" = sem variante; n = contador de inícios de ação
VARIANT_RULES: dict[str, dict]   # variante -> {"actions": (...), "min_stage": str, "mode": "any"|"overlay"|"terrarium"}
```
- Tabela exata do spec §6 (ações base, estágio mínimo, modo). Condições: jump/dance precisam `pad[0] > 0.3`; dance também se `theme == "musica"`; yawn se `needs["sono"] > 60`; chase/look_cursor precisam `cursor_near`; peek precisa `peek_ok`; found só para `show_something`. Entre as elegíveis, sorteio com `random.Random(hash((seed, action, n)) & 0xffffffff)` incluindo a opção "" com peso 1 (nunca obrigatório variar). Ovo e `ctx.asleep` (exceto nap_clock em `sleep`) → "".
- `anim.ANIM_FRAMES` ganha `jump`, `dance`, `yawn`, `dig` (reusando dy/sq/lean/eyes/mouth; 2–4 quadros) — `found` reusa `happy`, `chase` reusa `walk`, `look_cursor` reusa `idle` com lean, `peek`/`nap_clock` reusam `idle`/`sleep`.
- `items.found_item(kind: str) -> pygame.Surface` (8×8 pixel, kinds `osso`, `chip`, `pedra`, `arquivo`), cache.
- `Scene.draw(surface, snap, now, eating=False, variant="", background=True, item="")`: `variant` mapeia para a anim (tabela `VARIANT_ANIM`); prioridades atuais (dead > evolve > sleep > sick > old) continuam acima da variante; `dig` desenha terra levantada no chão; `found` desenha `item` ao lado da criatura; `background=False` não desenha cenário (usado pelo overlay; o chamador já preencheu com a cor-chave). Chamadas antigas sem os novos args continuam iguais pixel a pixel.

- [ ] Testes: determinismo (mesmos args → mesmo resultado; n variando produz pelo menos 2 resultados distintos em 50); travas de estágio (baby nunca `dance`); variantes `overlay` nunca com `overlay=False` e `dig` nunca com `overlay=True`; `peek` nunca com `peek_ok=False`; ovo → ""; toda anim nova existe para cada estágio em `creature_frames`; `Scene.draw` sem args novos dá o mesmo hash de antes (gravar hash antes da mudança no próprio teste via `background=True, variant=""` vs chamada antiga); `background=False` deixa pixels fora da criatura iguais ao preenchimento prévio; nenhum pixel da criatura/itens é `COLORKEY` (importar a constante de `engrama.app.desktop` só no teste, ou duplicar `(255,0,255)`).
- [ ] Implementar; `pytest -q tests/app`; commit `feat(m7): behaviour variants and new animations`.

---

### Tarefa 3: pedidos e ações digitais — onda A

**Files:** Create `engrama/app/digital.py`, `engrama/app/art/digital_fx.py`; Modify `engrama/app/ui/menus.py`, `engrama/app/ui/window.py` (só registrar o painel e a tecla); Test `tests/app/test_digital.py`

**Produces:**
```python
class DigitalRequests:                              # puro, sem pygame
    def __init__(self, seed: int) -> None
    open: str                                       # "" ou id em DIGITAL_IDS
    def on_action_start(self, action: str, t: float) -> str     # se action=="ask_attention", gap>=MIN_GAP, nenhum aberto e sorteio < P: abre e retorna id; senão ""
    def tick(self, t: float) -> None                             # expira após TTL
    def fulfill(self, id: str, t: float) -> bool                 # True se atendeu o pedido aberto (fecha); False se não havia/era outro
    def state_dict(self) -> dict; def load_state_dict(self, d: dict) -> None   # open, opened_t, last_t, rng state
# digital_fx
def icon(id: str) -> pygame.Surface                              # 10x10
def draw_effect(surface, id: str, age: float, rect: pygame.Rect) -> bool   # desenha o efeito (~2 s); False quando acabou
class DigitalMenu  # painel como FoodMenu: lista DIGITAL_IDS com ícone e nome i18n; on_pick(id)
```
- Window: `PANELS["digital"]`, tecla **F1**; `Window.give_digital(id)` posta `("pet", {"digital": id})`, chama `self.on_digital(id)` se definido (atributo duck-typed `on_digital: Callable[[str], object] | None = None`) e inicia o efeito (`self.digital_fx = (id, now)`), desenhado sobre a criatura em `frame` até `draw_effect` retornar False. Pedido aberto (`snap.digital_request`) desenha o ícone num balão acima da criatura.

- [ ] Testes: `on_action_start` só abre em `ask_attention`, respeita gap de 2 h e P (seed fixa: em 1000 tentativas espaçadas de 3 h a taxa fica em 0.35±0.05); expira em 30 min; `fulfill` certo → True e fecha, errado → False e mantém; roundtrip de estado; F1 abre o painel; escolher item posta `pet` com `{"digital": id}` e chama `on_digital`; ícones e efeitos de todos os ids desenham sem erro e sem pixel `COLORKEY`; textos do painel sem dígitos em PT e EN.
- [ ] Implementar; commit `feat(m7): digital requests and joke maintenance actions`.

---

### Tarefa 4: overlay na UI — onda B (depende de T1, T2, T3)

**Files:** Create `engrama/app/ui/overlay.py`; Modify `engrama/app/ui/window.py`, `engrama/app/ui/menus.py` (item "overlay" nas configurações); Test `tests/app/test_overlay.py`

**Consumes:** `Desktop`/`FakeDesktop`/`COLORKEY` (T1), `pick_variant`/`VariantCtx`/`Scene.draw(... variant, background, item)` (T2), `DigitalMenu`, `give_digital` (T3).

**Produces:**
```python
@dataclass(frozen=True)
class Strip:  x0: int; x1: int; floor_y: int          # faixa em pixels de tela
def strip_from_work_area(area: Rect, sprite_h: int) -> Strip   # floor_y = y+h (base da área útil); x0..x1 dentro da área
class OverlayController:
    def __init__(self, window, desktop: Desktop) -> None
    x: float                                           # posição horizontal (centro) na faixa
    def enter(self) -> bool                            # make_overlay; False se indisponível
    def leave(self) -> None                            # restore e volta ao tamanho do terrário
    def update(self, snap, dt: float, now: float) -> None   # movimento, cursor (≤ CURSOR_POLL_HZ), hide em fullscreen, place()
    def draw(self, screen, snap, now: float) -> None   # fill(COLORKEY), Scene.draw(background=False), sinais pequenos, balão, mini-menu, chat
    def handle_event(self, e) -> bool                  # clique na criatura → mini-menu; arrastar; mini-menu e chat
Window.mode: str; Window.desktop: Desktop (padrão NullDesktop); Window.set_mode(mode: str) -> bool; tecla F11 alterna
```
- Movimento (spec §4): `wander`/`explore` caminham para alvos sorteados na faixa a `OVERLAY_WALK_PX_S` (escala 4); `hide` desliza até a borda e mostra só metade; `nap_clock` vai até `x1` antes de dormir; `chase` segue `cursor.x` limitado à faixa; `peek` vai até o centro de `foreground_rect` (só se `config.permissions["active_window"]`); `look_cursor` vira o sprite para o cursor (flip horizontal).
- Janela: tamanho base = sprite×4 + margens para balão; com mini-menu/chat cresce, sempre recortada à área útil (Review Focus 3/4). `place` só quando o rect muda.
- Mini-menu: Comida (abre `FoodMenu` compacto), Remédio (oculto no ovo), Digital, Conversar (caixa de chat pequena acima), Terrário (volta). Mesmos eventos que no terrário.
- `snap.fullscreen` → `desktop.show(hwnd, False)` até acabar.
- `set_mode("overlay")` com `desktop.available False` ou `enter()` False → aviso `ui.overlay.unavailable`, fica no terrário, retorna False. Mudança de modo grava `config.display_mode` e chama `save_config`.
- Variantes no terrário também: Window chama `pick_variant` quando `snap.action` muda (contador `n`) e passa `variant` ao `Scene.draw`.

- [ ] Testes (com `FakeDesktop`): `strip_from_work_area` para barra embaixo, em cima e lateral (criatura sempre dentro da área); F11 alterna, grava `display_mode` e salva; indisponível → aviso e fica terrário; fullscreen esconde e volta; clique fora da criatura não abre nada e não posta; clique nela abre mini-menu; itens postam `food`, `food remedio`, `pet {"digital": …}`; "Terrário" volta; janela com mini-menu na borda direita fica dentro da área; `place` não é chamado em quadros sem mudança; fundo fora da criatura é exatamente `COLORKEY`; chase segue o cursor e respeita a faixa; peek desligado sem permissão.
- [ ] Implementar; `pytest -q tests/app tests/test_architecture.py`; commit `feat(m7): desktop overlay along the taskbar`.

---

### Tarefa 5: host, aceite, bench, README — onda C

**Files:** `engrama/app/host.py`, `tools/bench.py`, `tests/test_m7_acceptance.py`, `README.md`, `pyproject.toml`

- Host: snapshot preenche `fullscreen` (mundo atual), `theme` (tema percebido atual do M5, "" sem percepção) e `digital_request`; `DigitalRequests(seed)` vive no host, `on_action_start` quando a ação escolhida muda, `tick` a cada passo; ao abrir um pedido, fala curta `digital.ask.<id>` via o caminho de comentário espontâneo existente (fallback babble); `window.on_digital = host.fulfill_digital` (feliz se atendeu o pedido; isso é só UI/fala, o corpo recebe o `pet`); estado em `host.json` (`digital`), ausente → padrão.
- `main()`: `window.desktop = get_desktop()`; abre em `config.display_mode` (se overlay falhar, terrário).
- `tools/bench.py --overlay`: igual a `--app` mas em modo overlay com `FakeDesktop` e cursor falso se mexendo.
- Aceite (`tests/test_m7_acceptance.py`): save M6 carrega (sem `digital` e sem `display_mode`); pedido aberto aparece no snapshot e some ao atender; config overlay reabre em overlay com FakeDesktop; corrida de lab curta (`sim --days 1 --seed 1`) com métricas idênticas às da `m6` (gravar o JSON esperado gerado na `m6` como fixture); bench overlay ≤150 MB e ≤2% CPU (slow).
- README PT/EN seção "Presença (M7)"/"Presence (M7)" (F11, F1, mini-menu, pedidos digitais, variantes, privacidade do cursor); `pyproject` 0.7.0.
- [ ] Verificar: `pytest -q` completo; `tools/bench.py --app --seconds 60` e `--overlay`; `python -m engrama --frames 120 --no-llm`; commit `feat(m7): host wiring, acceptance and docs for presence`.

## Ondas e modelos

| Onda | Tarefas | Modelo |
|---|---|---|
| 0 | T0 | haiku |
| A | T1, T2, T3 (paralelas) | sonnet |
| B | T4 | sonnet |
| C | T5 | sonnet |
