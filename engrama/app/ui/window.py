"""Terrarium window: scene at low resolution (integer upscale), HUD and pluggable panels."""
from __future__ import annotations
import queue
import time
from typing import Callable
import pygame
from engrama.app.audio.growl import Growler
from engrama.app.art.sprites import Look
from engrama.app.snapshot import Snapshot
from engrama.app.ui import menus
from engrama.app.ui.chat import ChatBox
from engrama.app.ui.hud import Hud
from engrama.app.ui.scene import Scene

SCALE = 4
EAT_SECONDS = 2.0
TIME_SCALES = (1.0, 10.0, 60.0, 600.0)
KEY_PANELS = {pygame.K_F2: "mind", pygame.K_F4: "food", pygame.K_F5: "models", pygame.K_F6: "settings"}

# Panel registry: name -> factory(window) -> panel (draw(surface, snap), handle_event(event) -> bool,
# optional on_open()/on_close()). T7/T8/T9 call register_panel (or set window.panels[name]) to plug in.
PANELS: dict[str, Callable[["Window"], object]] = {}


def register_panel(name: str, factory: Callable[["Window"], object]) -> None:
    PANELS[name] = factory


def _mind_factory(win: "Window"):
    try:
        from engrama.app.ui.mind_view import MindView
        return MindView()
    except Exception:
        return menus.PlaceholderPanel("ui.mind.title")


register_panel("mind", _mind_factory)
register_panel("food", lambda w: menus.FoodMenu(w.give_food))
register_panel("models", lambda w: menus.PlaceholderPanel("ui.menu.models"))
register_panel("settings", lambda w: menus.PlaceholderPanel("ui.menu.settings"))


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
            if e.key == pygame.K_ESCAPE:
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

    def _set_focus(self, on: bool) -> None:
        self.focused = on
        self.post("app_focus", {"on": on})

    def _touch(self) -> None:
        now = time.monotonic()
        if now - self._last_active > 1.0:
            self._last_active = now
            self.post("user_active", None)

    def _click(self, pos) -> None:
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
        self._drain_host_events()
        self.scene.draw(self.low, snap, now, eating=time.monotonic() < self.eat_until)
        pygame.transform.scale(self.low, self.size, self.screen)
        self.hud.draw(self.screen, snap, self.dev)
        self.chat.draw(self.screen, self.scene.creature_rect, now)
        if self.panel is not None:
            self.panel.draw(self.screen, snap)
        pygame.display.flip()

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
