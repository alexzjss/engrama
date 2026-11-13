"""Terrarium window: scene at low resolution (integer upscale), HUD and pluggable panels."""
from __future__ import annotations
import queue
import time
from typing import Callable
import pygame
from engrama import balance, vocab
from engrama.app import i18n
from engrama.resources import assets_dir
from engrama.app.audio.growl import Growler
from engrama.app.art import digital_fx
from engrama.app.art.sprites import look_of
from engrama.app.desktop import Desktop, NullDesktop
from engrama.app.snapshot import Snapshot
from engrama.app.ui import menus
from engrama.app.ui.chat import ChatBox, _wrap as chat_wrap
from engrama.app.ui.hud import Hud, draw_text, font
from engrama.app.ui.overlay import OverlayController
from engrama.app.ui.scene import FAREWELL_BUBBLE_AT, Scene
from engrama.app.ui.toolbar import Toolbar
from engrama.app.ui.variants import VariantCtx, pick_variant

SCALE = 4
KEEPALIVE_S = 2.0   # an identical frame is still re-presented this often (cheap insurance against lost expose events)
_EXPOSE = tuple(getattr(pygame, n) for n in ("VIDEOEXPOSE", "WINDOWEXPOSED", "WINDOWSHOWN", "WINDOWRESTORED",
                                              "WINDOWMAXIMIZED", "WINDOWSIZECHANGED") if hasattr(pygame, n))
EAT_SECONDS = 2.0
TIME_SCALES = (1.0, 10.0, 60.0, 600.0)
KEY_PANELS = {pygame.K_F1: "digital", pygame.K_F2: "mind", pygame.K_F4: "food", pygame.K_F5: "models", pygame.K_F6: "settings",
              pygame.K_F7: "memories", pygame.K_F8: "permissions", pygame.K_F10: "generations"}

# Panel registry: name -> factory(window) -> panel (draw(surface, snap), handle_event(event) -> bool,
# optional on_open()/on_close()). T7/T8/T9 call register_panel (or set window.panels[name]) to plug in.
PANELS: dict[str, Callable[["Window"], object]] = {}


def _set_app_icon() -> None:
    """Window icon from the packaged PNG; a missing file or a driver without icons never stops the window."""
    try:
        pygame.display.set_icon(pygame.image.load(str(assets_dir() / "icon-256.png")))
    except (OSError, pygame.error):
        pass


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
register_panel("digital", lambda w: menus.DigitalMenu(w.give_digital))
register_panel("models", lambda w: menus.PlaceholderPanel("ui.menu.models"))
register_panel("settings", lambda w: menus.PlaceholderPanel("ui.menu.settings"))
register_panel("memories", lambda w: menus.PlaceholderPanel("ui.memories.title"))
register_panel("permissions", lambda w: menus.PlaceholderPanel("ui.perm.title"))
register_panel("first_use", lambda w: menus.PlaceholderPanel("ui.perm.first.title"))
register_panel("generations", lambda w: _generations_factory(w))
register_panel("help", lambda w: menus.HelpPanel())
register_panel("name", lambda w: menus.NamePanel(w))


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
        self.mode = "terrarium"
        self.desktop: Desktop = NullDesktop()
        self.set_rest = set_rest
        self.set_time_scale = set_time_scale
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(size)
        pygame.display.set_caption("Engrama")
        _set_app_icon()
        self.low = pygame.Surface((size[0] // SCALE, size[1] // SCALE))
        self.scene = Scene(self.low.get_size())
        self.hud = Hud()
        self.toolbar = Toolbar()
        self.growler = growler if growler is not None else Growler()
        self.chat = ChatBox(language, post, self.growler, valence_fn,
                            lambda: look_of(self._snap.look).voice_pitch)
        self.chat.reserve_right = self.toolbar.width + 4
        self.toolbar.layout(size)
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
        self.on_digital: Callable[[str], object] | None = None
        self.digital_fx: tuple[str, float] | None = None
        self._scale_i = 0
        self._last_active = 0.0
        self._events: queue.SimpleQueue = queue.SimpleQueue()
        self._snap = self.get_snapshot()
        self.variant = ""
        self.variant_item = ""
        self.variant_n = 0
        self._variant_key: tuple | None = None
        self._prev_now: float | None = None
        self._overlay: OverlayController | None = None
        self.skip_identical = True
        self._sig: tuple | None = None            # what the screen currently shows, when the frame was "plain"
        self._sig_at = 0.0
        self._sig_screen: pygame.Surface | None = None

    # --- display mode
    @property
    def overlay(self) -> OverlayController:
        if self._overlay is None or self._overlay.desktop is not self.desktop:
            if self._overlay is not None and self._overlay.active:
                self._overlay.leave()
            self._overlay = OverlayController(self, self.desktop)
        return self._overlay

    def set_mode(self, mode: str) -> bool:
        if mode not in vocab.DISPLAY_MODES:
            return False
        if mode == self.mode:
            return True
        self.close_panel()
        if mode == "overlay":
            if not self.desktop.available or not self.overlay.enter():
                key = "ui.overlay.unavailable_wayland" if self.desktop.unavailable_reason == "wayland" else "ui.overlay.unavailable"
                self._notice = (i18n.t(key), time.monotonic() + 4.0)
                return False
        else:
            self.overlay.leave()
        self.mode = mode
        self._variant_key = None
        self._sig = None
        cfg = getattr(self, "config", None)
        if cfg is not None:
            cfg.display_mode = mode
            if callable(self.save_config):
                self.save_config()
        return True

    def refresh_variant(self, snap) -> None:
        """Re-roll the purely visual behaviour variant whenever the action (or stage) changes."""
        key = (snap.action, snap.stage)
        if key == self._variant_key:
            return
        self._variant_key = key
        self.variant_n += 1
        look = snap.look or {}
        seed = int(look.get("seed", 0)) if isinstance(look, dict) else 0
        in_overlay = self.mode == "overlay"
        ov = self._overlay
        ctx = VariantCtx(stage=snap.stage, pad=tuple(snap.pad), needs=dict(snap.needs), overlay=in_overlay,
                         cursor_near=bool(in_overlay and ov is not None and ov.cursor_near), theme=snap.theme,
                         peek_ok=bool(in_overlay and ov is not None and ov.peek_ok), asleep=snap.asleep)
        self.variant = pick_variant(snap.action, ctx, seed, self.variant_n)
        self.variant_item = ("osso", "chip", "pedra", "arquivo")[(seed + self.variant_n) % 4] if self.variant == "found" else ""

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

    def give_digital(self, digital_id: str) -> None:
        self.post("pet", {"digital": digital_id})
        if callable(self.on_digital):
            try:
                self.on_digital(digital_id)
            except Exception:
                pass
        self.digital_fx = (digital_id, time.monotonic())
        self.close_panel()

    def _draw_digital(self, snap, scene=None) -> None:
        r = (scene or self.scene).creature_rect
        rect = pygame.Rect(r.x * SCALE, r.y * SCALE, r.w * SCALE, r.h * SCALE)
        if self.digital_fx is not None:
            did, t0 = self.digital_fx
            if not digital_fx.draw_effect(self.screen, did, time.monotonic() - t0, rect):
                self.digital_fx = None
        req = getattr(snap, "digital_request", "")
        if req and not snap.dead and r.w > 0:
            ic = pygame.transform.scale(digital_fx.icon(req), (30, 30))
            box = pygame.Rect(0, 0, 40, 40)
            box.midbottom = (rect.centerx, rect.top - 4)
            pygame.draw.rect(self.screen, (250, 250, 245), box, border_radius=8)
            pygame.draw.polygon(self.screen, (250, 250, 245), [(box.centerx - 5, box.bottom), (box.centerx + 5, box.bottom),
                                                               (box.centerx, box.bottom + 7)])
            self.screen.blit(ic, ic.get_rect(center=box.center))

    def on_host_event(self, name: str, data: dict) -> None:
        """Thread-safe: called from the simulation thread; consumed in frame()."""
        self._events.put((name, data))

    @property
    def target_fps(self) -> int:
        if self._snap.resting:
            return balance.FPS_RESTING
        if not self.focused:
            base = balance.FPS_UNFOCUSED
        else:
            base = balance.FPS_FOCUSED if self._busy_ui() else balance.FPS_STILL
        if self.mode == "overlay" and self._overlay is not None and self._overlay.moving:
            if self._overlay.airborne:
                return max(base, balance.FPS_OVERLAY_AIR)
            return max(base, balance.FPS_OVERLAY_MOVING)   # walking needs a few more frames than standing
        return base

    def _busy_ui(self) -> bool:
        """Something on screen changes fast enough to need the full rate (a moving creature, a panel, chat, effects)."""
        now = time.monotonic() if self._prev_now is None else self._prev_now
        ov = self._overlay if self.mode == "overlay" else None
        scene = ov.scene if ov is not None else self.scene
        if scene.moving or self.panel is not None or self.digital_fx is not None or not self.chat.quiet(now):
            return True
        if self._notice[0] and time.monotonic() < self._notice[1]:
            return True
        return ov is not None and (ov.moving or ov.menu_open or ov.chat_open or self._snap.dead)

    # --- input
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type in _EXPOSE:
            self._sig = None   # the surface may need to be presented again even if the pixels did not change
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
            elif e.key == pygame.K_F11:
                self.set_mode("terrarium" if self.mode == "overlay" else "overlay")
            elif e.key == pygame.K_ESCAPE:
                self.close_panel()
                if self.mode == "overlay":
                    self.overlay.close_menus()
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
            elif self._chat_listens():
                self.chat.handle_event(e)
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            self._touch()
            if self.panel is not None:
                if not self._panel_chrome_click(e.pos):
                    self.panel.handle_event(e)
            elif self.mode == "overlay":
                self.overlay.handle_event(e)
            else:
                self._click(e.pos)
        elif self.mode == "overlay" and self.panel is None and e.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            self.overlay.handle_event(e)
        elif e.type == pygame.MOUSEMOTION and self.mode != "overlay":
            self.toolbar.set_hover(e.pos)
            self.hud.hover = tuple(e.pos)
        elif self.panel is not None and e.type in (pygame.TEXTINPUT, pygame.TEXTEDITING, pygame.MOUSEWHEEL):
            self.panel.handle_event(e)
        elif e.type in (pygame.TEXTINPUT, pygame.TEXTEDITING) and self._chat_listens():
            self.chat.handle_event(e)
        elif e.type == pygame.DROPFILE:
            self._drop(getattr(e, "file", None))

    def _chat_listens(self) -> bool:
        """The terrarium chat is always on; in the overlay it only takes keys once "Talk" opened its box."""
        return self.mode != "overlay" or self.overlay.chat_open

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

    def farewell_click(self, scene) -> bool:
        """A click after the farewell text is shown (or after the fade) moves on."""
        shown = bool(self.farewell_text) and scene.farewell_age >= FAREWELL_BUBBLE_AT
        if (shown or scene.farewell_done) and callable(self.on_farewell_skip):
            self.on_farewell_skip()
        return True

    def _panel_chrome_click(self, pos) -> bool:
        """Clicks a panel never sees: its "x", the dimmed area around it and the toolbar (which switches panels).
        The first-use screen is modal and the overlay draws its panels in a window of their own."""
        if self.panel_name == "first_use" or self.mode == "overlay":
            return False
        bid = self.toolbar.hit(pos)
        if bid is not None:
            self.toggle_panel(bid)
            return True
        if menus.close_rect(self.screen).collidepoint(pos) or not menus.panel_rect(self.screen).collidepoint(pos):
            self.close_panel()
            return True
        return False

    def _click(self, pos) -> None:
        bid = self.toolbar.hit(pos)
        if bid is not None:
            self.toggle_panel(bid)
            return
        if self.chat.status_rect.collidepoint(pos) and self.chat.status(time.monotonic()) == "missing":
            self.open_panel("models")
            return
        if self._snap.dead:
            self.farewell_click(self.scene)
            return
        r = self.scene.creature_rect
        hit = pygame.Rect(r.x * SCALE, r.y * SCALE, r.w * SCALE, r.h * SCALE).inflate(16, 16)
        if hit.collidepoint(pos):
            self.post("click" if self.scene.is_egg else "pet", None)

    # --- frame loop
    def _drain_host_events(self) -> None:
        pitch = look_of(self._snap.look).voice_pitch
        while True:
            try:
                name, data = self._events.get_nowait()
            except queue.Empty:
                return
            if name == "hatch":
                self.growler.growl(pitch, "hatch")
                cfg = getattr(self, "config", None)
                if (cfg is not None and not getattr(cfg, "creature_name", "") and self.panel is None
                        and self.mode != "overlay"):
                    self.open_panel("name")
            elif name == "evolve":
                self.growler.growl(pitch, "evolve")
            elif name == "action_change" and (data or {}).get("to") == "ask_attention":
                self.growler.growl(pitch, "ask")

    def frame(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._snap = snap = self.get_snapshot()
        self._maybe_first_use()
        self._drain_host_events()
        dt = 0.0 if self._prev_now is None else max(0.0, min(0.5, now - self._prev_now))
        self._prev_now = now
        if self.mode == "overlay":
            ov = self.overlay
            ov.update(snap, dt, now)
            if not ov.hidden and ov.draw(self.screen, snap, now) is not False:
                ov.present()
            return
        self.refresh_variant(snap)
        self.scene.draw(self.low, snap, now, eating=time.monotonic() < self.eat_until, variant=self.variant,
                        item=self.variant_item)
        if self._identical(snap, now):
            return
        pygame.transform.scale(self.low, self.size, self.screen)
        self.hud.name = getattr(getattr(self, "config", None), "creature_name", "") or ""
        self.hud.draw(self.screen, snap, self.dev)
        if snap.dead:
            self._draw_farewell_bubble()
        else:
            self.chat.draw(self.screen, self.scene.creature_rect, now)
        self._draw_digital(snap)
        if snap.eyes_closed and not snap.dead:
            draw_text(self.screen, i18n.t("ui.eyes.closed"), (self.size[0] // 2, 20), (170, 180, 240), 20, "midtop")
        if self._notice[0] and time.monotonic() < self._notice[1]:
            draw_text(self.screen, self._notice[0], (self.size[0] // 2, self.size[1] - 24), (240, 160, 120), 22, "midbottom")
        if self.panel is not None:
            self.panel.draw(self.screen, snap)
        if self.panel_name != "first_use":
            self.toolbar.draw(self.screen, self.panel_name)
        pygame.display.flip()

    def _identical(self, snap, now: float) -> bool:
        """True when this frame would paint exactly what the screen already shows (so the upscale, HUD and flip can go).

        Only "plain" frames qualify: no panel, no chat activity, no notice, no digital effect, not dead."""
        plain = (self.skip_identical and self.panel is None and not snap.dead and self.digital_fx is None
                 and not (self._notice[0] and time.monotonic() < self._notice[1]))
        if plain:
            self.chat.poll(now)
            plain = self.chat.quiet(now)
        if not plain:
            self._sig = None
            return False
        r = self.scene.creature_rect
        sig = (self.low.get_buffer().raw, self.hud.key(snap, self.dev), bool(snap.eyes_closed),
               getattr(snap, "digital_request", ""), tuple(self.chat.history), self.chat.status_line(now),
               (r.x, r.y, r.w, r.h), self.size, self.toolbar.key(self.panel_name))
        if (sig == self._sig and self._sig_screen is self.screen and 0.0 <= now - self._sig_at < KEEPALIVE_S):
            return True
        self._sig, self._sig_at, self._sig_screen = sig, now, self.screen
        return False

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
