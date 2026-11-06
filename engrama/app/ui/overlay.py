"""Desktop overlay (M7): a small borderless colour-keyed window that walks along the bottom of the work area.

The window is only as big as needed (creature + bubble room; bigger with the mini-menu, chat or a panel) and is
always clipped to the work area. Everything is drawn at low resolution, scaled with nearest neighbour (so the
background stays exactly COLORKEY, which the OS makes invisible and click-through) and decorated at screen
resolution only on solid boxes.
"""
from __future__ import annotations

import dataclasses
import math
import random
from dataclasses import dataclass

import pygame

from engrama import balance, vocab
from engrama.app import i18n
from engrama.app.art import sprites
from engrama.app.desktop import COLORKEY, Desktop, Rect
from engrama.app.ui import hud, menus
from engrama.app.ui.chat import _wrap
from engrama.app.ui.scene import FAREWELL_BUBBLE_AT, Scene
from engrama.app.ui.world import Surface, Walker, edge_surfaces_for, flee_target, temper_of

SCALE = 4
BASE_TOP = 130            # room above the sprite for bubbles / balloons (screen px)
MENU_EXTRA = 176          # extra height while the mini-menu is open
CHAT_EXTRA = 130          # extra height while the chat box is open
PANEL_SIZE = (600, 560)   # food / digital / settings panels reuse the terrarium widgets
MENU_W, BTN_H = 200, 30
DRAG_PX = 5
PEEK_PERMISSION = "active_window"
TIGHT_W, TIGHT_H = 88, 28      # extra room around the sprite when the OS cannot pass clicks through (Wayland)
ROOM_HOLD_S = 1.0              # keep the roomy window this long after a bubble goes away (no resize flapping)
CALM_ACTIONS = ("idle", "wander", "explore", "play_alone", "show_something", "ask_attention")


@dataclass(frozen=True)
class Strip:
    x0: int
    x1: int
    floor_y: int


def strip_from_work_area(area: Rect, sprite_h: int) -> Strip:
    """Walkable band for the creature's centre: feet on the bottom of the work area, body inside it."""
    x, y, w, h = area
    half = max(0, min(int(sprite_h) // 2, w // 2))
    return Strip(x + half, x + w - half, y + h)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class OverlayController:
    def __init__(self, window, desktop: Desktop) -> None:
        self.window = window
        self.desktop = desktop
        self.x: float = 0.0
        self.active = False
        self.hidden = False
        self.moving = False
        self.menu_open = False
        self.chat_open = False
        self.hwnd = 0
        self.size = (0, 0)
        self.rect: Rect = (0, 0, 0, 0)
        self.area: Rect = desktop.work_area()
        self.cursor: tuple[int, int] | None = None
        self.cursor_near = False
        self.fg: Rect | None = None
        self.wins: list[Rect] = []
        self.surfaces: list[Surface] = []
        self.walker = Walker()
        self.feet: float = float(self.area[1] + self.area[3])
        self.airborne = False
        self.temper = "calm"
        self._last_win_poll = -1e9
        self._hop_at = 0.0
        self._room_until = 0.0
        self._room = False
        self._gl_screen: pygame.Surface | None = None
        self.facing = 1
        self.scene = Scene((1, 1))
        self.low = pygame.Surface((1, 1))
        self._last_poll = -1e9
        self._last_rect: Rect | None = None
        self._target: float | None = None
        self._rng = random.Random(0)
        self._press: tuple[int, int] | None = None
        self._dragging = False
        self._grab = 0.0
        self._menu_rects: list[tuple[str, pygame.Rect]] = []
        self._sig: tuple | None = None
        self._sig_at = 0.0
        self._sig_screen: pygame.Surface | None = None

    # ---------------------------------------------------------------- geometry helpers
    @property
    def strip(self) -> Strip:
        return strip_from_work_area(self.area, self._sprite_px(self.window._snap))

    @staticmethod
    def _sprite_px(snap) -> int:
        return sprites.SIZES.get(snap.stage, 24) * SCALE

    def _dims(self, snap) -> tuple[int, int]:
        sp = self._sprite_px(snap)
        if self.window.panel is not None:
            w, h = PANEL_SIZE
        elif not self.desktop.click_through and not (self._room or self.menu_open or self.chat_open or snap.dead):
            w, h = sp + TIGHT_W, sp + TIGHT_H     # the window blocks clicks: stay close to the body
        else:
            w, h = max(300, sp + 120), sp + BASE_TOP
            if self.menu_open and not snap.dead:
                h += MENU_EXTRA
            elif self.chat_open and not snap.dead:
                h += CHAT_EXTRA
        ax, ay, aw, ah = self.area
        w, h = min(w, aw), min(h, ah)
        return max(SCALE, w // SCALE * SCALE), max(SCALE, h // SCALE * SCALE)

    def _layout(self, snap) -> Rect:
        ww, wh = self._dims(snap)
        ax, ay, aw, ah = self.area
        wx = int(round(_clamp(self.x - ww / 2, ax, max(ax, ax + aw - ww))))
        wy = int(round(_clamp(self.feet - wh, ay, max(ay, ay + ah - wh))))
        return (wx, wy, ww, wh)

    def _hwnd(self) -> int:
        # On Wayland (and the dummy driver) get_wm_info() segfaults or has no native handle: no HWND.
        try:
            if pygame.display.get_driver() in ("wayland", "dummy"):
                return 0
        except Exception:
            pass
        try:
            return int(pygame.display.get_wm_info().get("window", 0) or 0)
        except Exception:
            return 0

    def _resize(self, ww: int, wh: int) -> bool:
        self.size = (ww, wh)
        self.desktop.prepare_window()
        real = pygame.display.set_mode((ww, wh), pygame.NOFRAME | self.desktop.display_flags)
        if self.desktop.offscreen:
            # The real window is a GL surface; everything is drawn on a plain Surface that present() shows.
            self._gl_screen = pygame.Surface((ww, wh))
            self.window.screen = self._gl_screen
        else:
            self._gl_screen = None
            self.window.screen = real
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        self.hwnd = self._hwnd()
        ok = bool(self.desktop.make_overlay(self.hwnd))
        self.low = pygame.Surface((ww // SCALE, wh // SCALE))
        self.scene.size = self.low.get_size()
        self._last_rect = None
        return ok

    # ---------------------------------------------------------------- enter / leave
    def enter(self) -> bool:
        if not self.desktop.available:
            return False
        try:
            self.area = self.desktop.work_area()
            snap = self.window._snap
            self.hidden = False
            self.x = (self.strip.x0 + self.strip.x1) / 2
            self.feet = float(self.strip.floor_y)
            self.walker = Walker(random.Random(int((snap.look or {}).get("seed", 0))))
            self.walker.place(self.x, self.feet)
            self._hop_at = 0.0
            self._last_win_poll = -1e9
            self.wins, self.surfaces = [], []
            self._target = None
            self._rng = random.Random(int((snap.look or {}).get("seed", 0)))
            self._last_poll = -1e9
            ww, wh = self._dims(snap)
            if not self._resize(ww, wh):
                self.desktop.restore(self.hwnd)
                self.window.screen = pygame.display.set_mode(self.window.size)
                return False
        except Exception:
            try:
                self.window.screen = pygame.display.set_mode(self.window.size)
            except Exception:
                pass
            return False
        self.active = True
        self._apply_geometry(snap)
        return True

    def leave(self) -> None:
        if not self.active:
            return
        self.active = False
        self.menu_open = self.chat_open = False
        self._press, self._dragging = None, False
        try:
            if self.hidden:
                self.desktop.show(self.hwnd, True)
            self.desktop.restore(self.hwnd)
        except Exception:
            pass
        self.hidden = False
        self.window.screen = pygame.display.set_mode(self.window.size)
        try:
            pygame.display.set_caption("Engrama")
        except Exception:
            pass
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def close_menus(self) -> None:
        self.menu_open = self.chat_open = False

    # ---------------------------------------------------------------- per-frame update
    def _poll(self, snap, now: float) -> None:
        if now - self._last_poll < 1.0 / max(1, balance.CURSOR_POLL_HZ):
            return
        self._last_poll = now
        self.area = self.desktop.work_area()
        self.cursor = self.desktop.cursor()
        cfg = getattr(self.window, "config", None)
        allowed = bool(cfg is not None and cfg.permissions.get(PEEK_PERMISSION, False))
        self.fg = self.desktop.foreground_rect() if allowed else None   # never touched without the permission
        near = False
        if self.cursor is not None:
            cy = self.feet - self._sprite_px(snap) / 2
            near = math.hypot(self.cursor[0] - self.x, self.cursor[1] - cy) <= balance.CURSOR_NEAR_PX
        self.cursor_near = near
        if now - self._last_win_poll >= 1.0 / max(1, balance.WINDOWS_POLL_HZ):
            self._last_win_poll = now
            try:
                self.wins = list(self.desktop.windows())   # geometry only, never titles
            except Exception:
                self.wins = []
            self.surfaces = edge_surfaces_for(self.wins, self.area, self._sprite_px(snap))

    @property
    def peek_ok(self) -> bool:
        return self.fg is not None

    def _surface_list(self) -> list[Surface]:
        st = self.strip
        return [Surface(st.x0, st.x1, float(st.floor_y), "strip")] + self.surfaces

    def _needs_room(self, snap, now: float) -> bool:
        w = self.window
        chat = w.chat
        need = bool(snap.dead or w.digital_fx is not None or getattr(snap, "digital_request", "")
                    or (chat.bubble and now < chat.bubble_until) or chat.busy)
        if need:
            self._room_until = now + ROOM_HOLD_S
        return need or now < self._room_until

    def update(self, snap, dt: float, now: float) -> None:
        self._poll(snap, now)
        self.window.refresh_variant(snap)
        self._room = self._needs_room(snap, now)
        self.temper = temper_of(getattr(snap, "branch", ""), getattr(snap, "traits", None))
        if snap.fullscreen != self.hidden:
            self.hidden = bool(snap.fullscreen)
            self.desktop.show(self.hwnd, not self.hidden)
        if self.hidden:
            self.moving = False
            return
        self._move(snap, dt, now)
        self._apply_geometry(snap)

    def _wander_target(self, lo: float, hi: float) -> float | None:
        if hi - lo < 8:
            return None
        if self._target is None or not lo <= self._target <= hi:
            self._target = self._rng.uniform(lo, hi)
        return self._target

    def _plan_hop(self, surfaces: list[Surface], now: float) -> None:
        wk = self.walker
        lo, hi = balance.OVERLAY_HOP_S
        if self._hop_at == 0.0:                       # just arrived: settle before the first outing
            self._hop_at = now + self._rng.uniform(lo, hi)
            return
        if now < self._hop_at or wk.goal is not None or len(surfaces) < 2:
            return
        self._hop_at = now + self._rng.uniform(lo, hi)
        top = self.surfaces[0] if self.surfaces else None     # topmost visible window = the active one
        wk.choose_goal(surfaces, prefer=top)

    def _move(self, snap, dt: float, now: float = 0.0) -> None:
        w = self.window
        strip = self.strip
        wk = self.walker
        ax, _ay, aw, _ah = self.area
        surfaces = self._surface_list()
        wk.x = self.x
        frozen = (self.menu_open or self.chat_open or w.panel is not None or self._dragging or snap.dead
                  or snap.stage == "egg")
        self.moving = False
        here = wk.support(surfaces)
        lo, hi = (here.x0, here.x1) if here is not None else (strip.x0, strip.x1)
        if self._dragging:
            self.x = _clamp(self.x, lo, hi)
            wk.x = self.x
            return
        if frozen:
            if wk.airborne:
                self.moving = wk.update(dt, surfaces, None, 0.0)
                self.x, self.feet, self.airborne = wk.x, wk.y, wk.airborne
            return
        action, variant = snap.action, w.variant
        target: float | None = None
        speed = float(balance.OVERLAY_WALK_PX_S)
        hiding = action == "hide" and not snap.asleep
        on_strip = here is None or here.kind == "strip"
        if (snap.asleep or hiding) and not on_strip and wk.goal is None:
            wk.goal = surfaces[0]                    # sleeping and hiding happen on the floor
        if snap.asleep:
            if action == "sleep" and variant == "nap_clock" and on_strip:
                target = strip.x1
            elif action == "sleep" and on_strip:
                target = strip.x1 if self.x >= (strip.x0 + strip.x1) / 2 else strip.x0   # a corner to curl up in
        elif hiding:
            if on_strip:
                target = float(ax if self.x < ax + aw / 2 else ax + aw)   # half the body slides out of view
        elif variant == "peek" and self.fg is not None:
            target = self.fg[0] + self.fg[2] / 2
        elif variant == "chase" and self.cursor is not None:
            target = float(self.cursor[0])
        else:
            react = self._react(snap, here, lo, hi) if action in CALM_ACTIONS else None
            if react is not None:
                target, speed = react
            elif action in ("wander", "explore"):
                target = self._wander_target(lo, hi)
        if not snap.asleep and not hiding and action in CALM_ACTIONS:
            self._plan_hop(surfaces, now)
        if target is not None and not hiding:
            target = _clamp(target, lo, hi)
        if target is None and not hiding and here is not None and not lo <= self.x <= hi:
            target = _clamp(self.x, lo, hi)   # came back from hiding: walk into the strip
        old = self.x
        self.moving = wk.update(dt, surfaces, target, speed)
        self.x, self.feet, self.airborne = wk.x, wk.y, wk.airborne
        if target is not None and not hiding and action in ("wander", "explore") and variant not in ("chase", "peek") \
                and abs(self.x - target) < 1e-6:
            self._target = None
        if abs(self.x - old) > 0.01:
            self.facing = 1 if self.x > old else -1
        if (variant == "look_cursor" or self.temper == "curious" and self.cursor_near) and self.cursor is not None \
                and abs(self.cursor[0] - self.x) > 8 and not self.moving:
            self.facing = 1 if self.cursor[0] > self.x else -1

    def _react(self, snap, here: Surface | None, lo: float, hi: float) -> tuple[float, float] | None:
        """Cursor reaction by temper: skittish flees, playful follows (curious only looks, see _move)."""
        if self.cursor is None or not self.cursor_near or here is None:
            return None
        cx = float(self.cursor[0])
        if self.temper == "skittish":
            goal = flee_target(self.x, cx, Surface(lo, hi, here.y, here.kind))
            if abs(goal - self.x) < 6 and self.walker.goal is None and len(self.surfaces) > 0:
                self._hop_at = -1.0      # cornered: look for another ledge now
            return goal, float(balance.OVERLAY_FLEE_PX_S)
        if self.temper == "playful" and abs(cx - self.x) > 70:
            return cx, float(balance.OVERLAY_WALK_PX_S)
        return None

    def _apply_geometry(self, snap) -> None:
        rect = self._layout(snap)
        if (rect[2], rect[3]) != self.size:
            self._resize(rect[2], rect[3])
        if rect != self._last_rect:
            self.rect = rect
            self._last_rect = rect
            self.desktop.place(self.hwnd, rect)

    def present(self, screen: pygame.Surface | None = None) -> None:
        """Flip the finished frame (offscreen desktops upload the surface to their GL window first)."""
        if self.desktop.offscreen and self._gl_screen is not None:
            self.desktop.present(self._gl_screen)
        pygame.display.flip()

    # ---------------------------------------------------------------- drawing
    def _creature_screen_rect(self) -> pygame.Rect:
        r = self.scene.creature_rect
        return pygame.Rect(r.x * SCALE, r.y * SCALE, r.w * SCALE, r.h * SCALE)

    def _identical(self, screen: pygame.Surface, snap, now: float) -> bool:
        """True when nothing visible changed since the last presented frame (same pixels, same window rect)."""
        w = self.window
        plain = (w.skip_identical and w.panel is None and not self.menu_open and not self.chat_open
                 and not snap.dead and w.digital_fx is None and not getattr(snap, "digital_request", ""))
        if plain:
            w.chat.poll(now)
            plain = w.chat.quiet(now)
        if not plain:
            self._sig = None
            return False
        r = self.scene.creature_rect
        # Where the window sits does not change what it shows; only desktops that repaint on every move need it.
        where = self.rect if self.desktop.click_through else self.size
        sig = (self.low.get_buffer().raw, self.size, where, hud.mood_kind(snap), bool(snap.grave), bool(snap.sick),
               (r.x, r.y, r.w, r.h))
        if sig == self._sig and self._sig_screen is screen and 0.0 <= now - self._sig_at < 2.0:
            return True
        self._sig, self._sig_at, self._sig_screen = sig, now, screen
        return False

    def draw(self, screen: pygame.Surface, snap, now: float) -> bool:
        """Paint the overlay; False when the frame was identical to the one on screen (nothing drawn, no flip needed)."""
        w = self.window
        self.low.fill(COLORKEY)
        scene_snap = dataclasses.replace(snap, action="idle") if snap.action == "hide" else snap
        pos_x = int((self.x - self.rect[0]) / SCALE)
        ground = max(0, min(self.low.get_height(), int(round((self.feet - self.rect[1]) / SCALE))))
        flip = self.facing < 0 and not snap.dead
        self.scene.draw(self.low, scene_snap, now, eating=now_mono() < w.eat_until, variant=w.variant,
                        background=False, item=w.variant_item, flip=flip, pos_x=pos_x,
                        ground=ground)
        if self._identical(screen, snap, now):
            return False
        pygame.transform.scale(self.low, self.size, screen)   # nearest neighbour: COLORKEY stays exact
        cr = self._creature_screen_rect()
        if snap.dead:
            self._farewell_bubble(screen, cr)
        else:
            self._signals(screen, snap, cr)
            if self.chat_open:
                self._draw_chat(screen, now)
            w.chat.poll(now)
            if w.chat.bubble and now < w.chat.bubble_until:
                w.chat._draw_bubble(screen, self.scene.creature_rect)
            elif w.chat.busy:
                w.chat._draw_thinking(screen, self.scene.creature_rect, now)
            if self.menu_open:
                self._draw_menu(screen, snap, cr)
        w._draw_digital(snap, self.scene)
        if w.panel is not None:
            w.panel.draw(screen, snap)
        self.desktop.update_shape(self.hwnd, screen)
        return True

    def _signals(self, screen, snap, cr: pygame.Rect) -> None:
        """Tiny status marks beside the head: mood face and sick/grave."""
        if cr.w <= 0:
            return
        x, y = min(self.size[0] - 16, cr.right + 12), max(14, cr.y + 8)
        hud._mood_icon(screen, x, y, hud.mood_kind(snap))
        if snap.grave or snap.sick:
            col, glyph = ((235, 90, 80), "!") if snap.grave else ((150, 210, 110), "+")
            cx = max(14, cr.x - 12)
            pygame.draw.circle(screen, col, (cx, y), 11)
            hud.draw_text(screen, glyph, (cx, y), (30, 26, 40), 22, "center")

    def _farewell_bubble(self, screen, cr: pygame.Rect) -> None:
        text = (self.window.farewell_text or "").strip()
        if not text or self.scene.farewell_age < FAREWELL_BUBBLE_AT:
            return
        sw = self.size[0]
        lines = _wrap(text, 20, min(260, sw - 40))
        f = hud.font(20)
        bw = max(f.size(ln)[0] for ln in lines) + 16
        bh = len(lines) * 18 + 12
        top = (cr.y if cr.w > 0 else 100) - bh - 12
        box = pygame.Rect(0, max(2, top), bw, bh)
        box.centerx = int(_clamp(cr.centerx if cr.w > 0 else sw // 2, bw // 2 + 4, sw - bw // 2 - 4))
        pygame.draw.rect(screen, (250, 250, 245), box, border_radius=8)
        pygame.draw.polygon(screen, (250, 250, 245), [(box.centerx - 6, box.bottom), (box.centerx + 6, box.bottom),
                                                      (box.centerx, box.bottom + 8)])
        for i, ln in enumerate(lines):
            hud.draw_text(screen, ln, (box.x + 8, box.y + 6 + i * 18), (40, 36, 50), 20)

    def _draw_chat(self, screen, now: float) -> None:
        chat = self.window.chat
        ww = self.size[0]
        box = pygame.Rect(4, 4, ww - 8, CHAT_EXTRA - 12)
        pygame.draw.rect(screen, menus.BG, box, border_radius=8)
        pygame.draw.rect(screen, menus.EDGE, box, 2, border_radius=8)
        field = pygame.Rect(box.x + 8, box.bottom - 32, box.w - 16, 24)
        pygame.draw.rect(screen, (30, 28, 40), field, border_radius=6)
        pygame.draw.rect(screen, (90, 90, 120), field, 1, border_radius=6)
        shown = (chat.text + chat.composing).split("\n")[-1]
        while shown and hud.font(20).size(shown)[0] > field.w - 12:
            shown = shown[1:]
        if shown:
            hud.draw_text(screen, shown, (field.x + 6, field.centery), (235, 235, 240), 20, "midleft")
        else:
            hud.draw_text(screen, i18n.t("ui.chat.placeholder"), (field.x + 6, field.centery), (120, 120, 140), 20,
                          "midleft")
        y = field.y - 16
        for item in reversed(chat.history):
            if y < box.y + 4:
                break
            line = item
            while line and hud.font(16).size(line)[0] > box.w - 16:
                line = line[:-1]
            hud.draw_text(screen, line, (box.x + 8, y), (150, 150, 170), 16)
            y -= 14

    # ---------------------------------------------------------------- mini-menu
    def _menu_items(self, snap) -> list[tuple[str, str]]:
        items = [("food", i18n.t("ui.menu.food"))]
        if snap.stage != "egg":
            items.append(("remedio", i18n.t("ui.menu.medicine")))
        items += [("digital", i18n.t("ui.menu.digital")), ("talk", i18n.t("ui.overlay.talk")),
                  ("terrarium", i18n.t("ui.overlay.back"))]
        return items

    def _layout_menu(self, snap, cr: pygame.Rect | None = None) -> pygame.Rect:
        items = self._menu_items(snap)
        cr = cr if cr is not None else self._creature_screen_rect()
        ww = self.size[0]
        box = pygame.Rect(0, 4, MENU_W + 16, len(items) * BTN_H + 12)
        box.centerx = int(_clamp(cr.centerx if cr.w > 0 else ww // 2, box.w // 2 + 2, ww - box.w // 2 - 2))
        self._menu_rects = [(k, pygame.Rect(box.x + 8, box.y + 6 + i * BTN_H, MENU_W, BTN_H - 4))
                            for i, (k, _lbl) in enumerate(items)]
        return box

    def _draw_menu(self, screen, snap, cr: pygame.Rect) -> None:
        box = self._layout_menu(snap, cr)
        pygame.draw.rect(screen, menus.BG, box, border_radius=8)
        pygame.draw.rect(screen, menus.EDGE, box, 2, border_radius=8)
        labels = dict(self._menu_items(snap))
        for key, rect in self._menu_rects:
            menus._btn(screen, rect, labels[key])

    def _activate(self, key: str) -> None:
        w = self.window
        self.menu_open = False
        if key == "food":
            w.open_panel("food")
        elif key == "remedio":
            w.give_food(vocab.MEDICINE_ID)
        elif key == "digital":
            w.open_panel("digital")
        elif key == "talk":
            self.chat_open = True
        elif key == "terrarium":
            w.set_mode("terrarium")

    # ---------------------------------------------------------------- input
    def _hit(self, pos) -> bool:
        cr = self._creature_screen_rect()
        return cr.w > 0 and cr.inflate(16, 16).collidepoint(pos)

    def handle_event(self, e) -> bool:
        w = self.window
        snap = w._snap
        if e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            if snap.dead:
                return w.farewell_click(self.scene)
            if self.menu_open:
                self._layout_menu(snap)
                for key, rect in self._menu_rects:
                    if rect.collidepoint(e.pos):
                        self._activate(key)
                        return True
                self.menu_open = False
                return True
            if not self._hit(e.pos):
                return False
            if self.scene.is_egg:
                w.post("click", None)
                return True
            self._press, self._dragging = tuple(e.pos), False
            return True
        if e.type == pygame.MOUSEMOTION and self._press is not None:
            cur = self.desktop.cursor()
            if not self._dragging:
                if math.hypot(e.pos[0] - self._press[0], e.pos[1] - self._press[1]) < DRAG_PX:
                    return True
                self._dragging = True
                self._grab = (cur[0] - self.x) if cur is not None else 0.0
            if cur is not None:
                self.x = _clamp(cur[0] - self._grab, self.strip.x0, self.strip.x1)
            else:
                self.x = _clamp(self.x + getattr(e, "rel", (0, 0))[0], self.strip.x0, self.strip.x1)
            return True
        if e.type == pygame.MOUSEBUTTONUP and getattr(e, "button", 1) == 1 and self._press is not None:
            dragged = self._dragging
            self._press, self._dragging = None, False
            if not dragged:
                self.menu_open, self.chat_open = True, False
            return True
        return False


def now_mono() -> float:
    import time
    return time.monotonic()
