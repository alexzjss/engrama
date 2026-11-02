"""Terrarium window: scene at low resolution (integer upscale), HUD and pluggable panels."""
from __future__ import annotations
import queue
import time
from typing import Callable
import pygame
from engrama import vocab
from engrama.app import i18n
from engrama.app.audio.growl import Growler
from engrama.app.art.sprites import Look
from engrama.app.snapshot import Snapshot
from engrama.app.ui import menus
from engrama.app.ui.chat import ChatBox, _wrap as chat_wrap
from engrama.app.ui.hud import Hud, draw_text, font
from engrama.app.ui.scene import FAREWELL_BUBBLE_AT, Scene

SCALE = 4
EAT_SECONDS = 2.0
TIME_SCALES = (1.0, 10.0, 60.0, 600.0)
KEY_PANELS = {pygame.K_F2: "mind", pygame.K_F4: "food", pygame.K_F5: "models", pygame.K_F6: "settings",
              pygame.K_F7: "memories", pygame.K_F8: "permissions", pygame.K_F10: "generations"}

# Panel registry: name -> factory(window) -> panel (draw(surface, snap), handle_event(event) -> bool,
# optional on_open()/on_close()). T7/T8/T9 call register_panel (or set window.panels[name]) to plug in.
PANELS: dict[str, Callable[["Window"], object]] = {}


def register_panel(name: str, factory: Callable[["Window"], object]) -> None:
    PANELS[name] = factory


def _mind_factory(win: "Window"):
    try:
        from engrama.app.ui.mind_view import MindView
        mv = MindView()
        provider = getattr(win, "memory_provider", None)
        if provider is not None:
            mv.memory_summary = lambda: provider.summary()
        return mv
    except Exception:
        return menus.PlaceholderPanel("ui.mind.title")


register_panel("mind", _mind_factory)
register_panel("food", lambda w: menus.FoodMenu(w.give_food))
register_panel("models", lambda w: menus.PlaceholderPanel("ui.menu.models"))
register_panel("settings", lambda w: menus.PlaceholderPanel("ui.menu.settings"))
register_panel("memories", lambda w: menus.PlaceholderPanel("ui.memories.title"))
register_panel("permissions", lambda w: menus.PlaceholderPanel("ui.perm.title"))
register_panel("first_use", lambda w: menus.PlaceholderPanel("ui.perm.first.title"))
register_panel("generations", lambda w: _generations_factory(w))


def _generations_factory(win: "Window"):
    from engrama.app.ui.generations import GenerationsPanel
    return GenerationsPanel(win)


class Window:
    def __init__(self, get_snapshot: Callable[[], Snapshot], post: Callable[[str, dict | None], None],
                 language=None, size: tuple[int, int] = (640, 480), growler=None,
                 set_rest: Callable[[bool], None] | None = None,
                 set_time_scale: Callable[[float], None] | None = None,
                 valence_fn: Callable[[str], float] | None = None) -> None:
        self.get_snapshot = get_snapshot
        self.post = post
        self.language = language
        self.size = size
        self.set_rest = set_rest
        self.set_time_scale = set_time_scale
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(size)
        pygame.display.set_caption("Engrama")
        self.low = pygame.Surface((size[0] // SCALE, size[1] // SCALE))
        self.scene = Scene(self.low.get_size())
        self.hud = Hud()
        self.growler = growler if growler is not None else Growler()
        self.chat = ChatBox(language, post, self.growler, valence_fn,
                            lambda: Look.from_dict(self._snap.look).voice_pitch)
        self.panels: dict[str, Callable[["Window"], object]] = dict(PANELS)
        self.panel_name: str | None = None
        self.panel = None
        self.focused = True
        self.dev = False
        self.set_eyes_closed: Callable[[bool], None] | None = None
        self.on_file_drop: Callable[[str], object] | None = None
        self.perception_provider = None
        self.generations_provider = None          # duck-typed: records() -> list, delete_archive(n)
        self.farewell_text = ""                   # shown in the bubble while the creature is dead
        self.on_farewell_skip: Callable[[], object] | None = None
        self.save_config: Callable[[], None] | None = None
        self._notice = ("", 0.0)
        self._first_use_done = False
        self.rest_manual = False
        self.running = True
        self.eat_until = 0.0
        self._scale_i = 0
        self._last_active = 0.0
        self._events: queue.SimpleQueue = queue.SimpleQueue()
        self._snap = self.get_snapshot()

    # --- panels
    def open_panel(self, name: str) -> None:
        self.close_panel()
        factory = self.panels.get(name)
        if factory is None:
            return
        self.panel_name, self.panel = name, factory(self)
        getattr(self.panel, "on_open", lambda: None)()

    def close_panel(self) -> None:
        if self.panel is not None:
            getattr(self.panel, "on_close", lambda: None)()
        self.panel_name = self.panel = None

    def toggle_panel(self, name: str) -> None:
        if self.panel_name == name:
            self.close_panel()
        else:
            self.open_panel(name)

    # --- actions
    def give_food(self, food_id: str) -> None:
        self.post("food", {"food": food_id})
        if food_id != vocab.MEDICINE_ID:
            self.eat_until = time.monotonic() + EAT_SECONDS
        self.close_panel()

    def on_host_event(self, name: str, data: dict) -> None:
        """Thread-safe: called from the simulation thread; consumed in frame()."""
        self._events.put((name, data))

    @property
    def target_fps(self) -> int:
        if self._snap.resting:
            return 2
        return 20 if self.focused else 5

    # --- input
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.WINDOWFOCUSGAINED:
            self._set_focus(True)
        elif e.type == pygame.WINDOWFOCUSLOST:
            self._set_focus(False)
        elif e.type == pygame.KEYDOWN:
            self._touch()
            if e.key == pygame.K_F9:
                self.toggle_eyes()
            elif self.panel_name == "first_use":
                self.panel.handle_event(e)   # modal: nothing else reacts while it is open
            elif e.key == pygame.K_ESCAPE:
                self.close_panel()
            elif e.key in KEY_PANELS:
                self.toggle_panel(KEY_PANELS[e.key])
            elif e.key == pygame.K_F3:
                self.rest_manual = not self.rest_manual
                if self.set_rest:
                    self.set_rest(self.rest_manual)
            elif e.key == pygame.K_F12:
                self.dev = not self.dev
            elif self.dev and e.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN) and self.set_time_scale:
                step = 1 if e.key == pygame.K_PAGEUP else -1
                self._scale_i = max(0, min(len(TIME_SCALES) - 1, self._scale_i + step))
                self.set_time_scale(TIME_SCALES[self._scale_i])
            elif self.panel is not None:
                self.panel.handle_event(e)
            else:
                self.chat.handle_event(e)
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            self._touch()
            if self.panel is not None:
                self.panel.handle_event(e)
            else:
                self._click(e.pos)
        elif self.panel is not None and e.type in (pygame.TEXTINPUT, pygame.TEXTEDITING, pygame.MOUSEWHEEL):
            self.panel.handle_event(e)
        elif e.type in (pygame.TEXTINPUT, pygame.TEXTEDITING):
            self.chat.handle_event(e)
        elif e.type == pygame.DROPFILE:
            self._drop(getattr(e, "file", None))

    def toggle_eyes(self) -> None:
        cfg = getattr(self, "config", None)
        cur = bool(cfg.eyes_closed) if cfg is not None else bool(self._snap.eyes_closed)
        if callable(self.set_eyes_closed):
            try:
                self.set_eyes_closed(not cur)
            except Exception:
                pass

    def _drop(self, path) -> None:
        if not path or not callable(self.on_file_drop):
            return
        try:
            ok = self.on_file_drop(str(path))
        except Exception:
            ok = False
        if ok is False:
            self._notice = (i18n.t("ui.file.refused"), time.monotonic() + 3.0)

    def _maybe_first_use(self) -> None:
        cfg = getattr(self, "config", None)
        if cfg is None or self._first_use_done or getattr(cfg, "perception_asked", True):
            return
        self._first_use_done = True
        self.open_panel("first_use")

    def _set_focus(self, on: bool) -> None:
        self.focused = on

    def _touch(self) -> None:
        now = time.monotonic()
        if now - self._last_active > 1.0:
            self._last_active = now
            self.post("user_active", None)

    def _click(self, pos) -> None:
        if self._snap.dead:   # farewell: a click after the text is shown (or after the fade) moves on
            shown = bool(self.farewell_text) and self.scene.farewell_age >= FAREWELL_BUBBLE_AT
            if (shown or self.scene.farewell_done) and callable(self.on_farewell_skip):
                self.on_farewell_skip()
            return
        r = self.scene.creature_rect
        hit = pygame.Rect(r.x * SCALE, r.y * SCALE, r.w * SCALE, r.h * SCALE).inflate(16, 16)
        if hit.collidepoint(pos):
            self.post("click" if self.scene.is_egg else "pet", None)

    # --- frame loop
    def _drain_host_events(self) -> None:
        pitch = Look.from_dict(self._snap.look).voice_pitch
        while True:
            try:
                name, data = self._events.get_nowait()
            except queue.Empty:
                return
            if name == "hatch":
                self.growler.growl(pitch, "hatch")
            elif name == "evolve":
                self.growler.growl(pitch, "evolve")
            elif name == "action_change" and (data or {}).get("to") == "ask_attention":
                self.growler.growl(pitch, "ask")

    def frame(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._snap = snap = self.get_snapshot()
        self._maybe_first_use()
        self._drain_host_events()
        self.scene.draw(self.low, snap, now, eating=time.monotonic() < self.eat_until)
        pygame.transform.scale(self.low, self.size, self.screen)
        self.hud.draw(self.screen, snap, self.dev)
        if snap.dead:
            self._draw_farewell_bubble()
        else:
            self.chat.draw(self.screen, self.scene.creature_rect, now)
        if snap.eyes_closed and not snap.dead:
            draw_text(self.screen, i18n.t("ui.eyes.closed"), (self.size[0] // 2, 20), (170, 180, 240), 20, "midtop")
        if self._notice[0] and time.monotonic() < self._notice[1]:
            draw_text(self.screen, self._notice[0], (self.size[0] // 2, self.size[1] - 24), (240, 160, 120), 22, "midbottom")
        if self.panel is not None:
            self.panel.draw(self.screen, snap)
        pygame.display.flip()

    def _draw_farewell_bubble(self) -> None:
        text = (self.farewell_text or "").strip()
        if not text or self.scene.farewell_age < FAREWELL_BUBBLE_AT:
            return
        sw = self.size[0]
        lines = chat_wrap(text, 20, min(260, sw - 40))
        f = font(20)
        bw = max(f.size(ln)[0] for ln in lines) + 16
        bh = len(lines) * 18 + 12
        r = self.scene.creature_rect
        cx = r.centerx * SCALE if r.w > 0 else sw // 2
        top = (r.y * SCALE if r.w > 0 else 200) - bh - 12
        box = pygame.Rect(0, max(50, top), bw, bh)
        box.centerx = max(bw // 2 + 4, min(sw - bw // 2 - 4, cx))
        pygame.draw.rect(self.screen, (250, 250, 245), box, border_radius=8)
        pygame.draw.polygon(self.screen, (250, 250, 245), [(box.centerx - 6, box.bottom),
                                                           (box.centerx + 6, box.bottom), (box.centerx, box.bottom + 8)])
        for i, ln in enumerate(lines):
            draw_text(self.screen, ln, (box.x + 8, box.y + 6 + i * 18), (40, 36, 50), 20)

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for e in pygame.event.get():
                self.handle_event(e)
            if not self.running:
                break
            self.frame()
            clock.tick(self.target_fps)
        self.close_panel()
        pygame.display.quit()
