"""Perception permission screens: modal first-use panel and the permissions panel (F8).

Duck-typed against the window: window.config (permissions, perception_asked, perception_interval_s,
perception_blocklist), window.save_config(), window.perception_provider (silenced_themes(), unsilence_theme(name),
clear_app_categories(), hotkey_error()). The UI never imports services."""
from __future__ import annotations
import re
import pygame
from engrama.app import i18n
from engrama.app.ui.hud import draw_text
from engrama.app.ui.menus import draw_frame, EDGE

SOURCES = ("process", "active_window", "idle", "time", "system_load")
INTERVALS = ((15.0, "fast"), (30.0, "normal"), (60.0, "slow"))
TXT = (230, 230, 240)
DIM = (150, 150, 170)
WARN = (240, 160, 120)
HEAD = (170, 160, 240)
OK = (130, 210, 140)
ROW_H = 24
MAX_LIST = 5


def _enter(e) -> bool:
    return e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)


def _save(window) -> None:
    fn = getattr(window, "save_config", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def _clean(window, s) -> str:
    s = str(s)
    return s if getattr(window, "dev", False) else re.sub(r"\d", "", s)


def _button(surface, rect, label, selected) -> None:
    pygame.draw.rect(surface, (70, 66, 110) if selected else (44, 42, 66), rect, border_radius=6)
    pygame.draw.rect(surface, EDGE, rect, 1, border_radius=6)
    draw_text(surface, label, rect.center, TXT, 22, "center")


class FirstUsePanel:
    """Modal: asks, one source at a time, allow or not now. Esc = not now for everything left."""

    def __init__(self, window) -> None:
        self.window = window
        self.idx = 0
        self.sel = 0          # 0 = allow, 1 = not now
        self._rects = [pygame.Rect(0, 0, 0, 0), pygame.Rect(0, 0, 0, 0)]

    def _answer(self, allow: bool) -> None:
        if self.idx >= len(SOURCES):
            return
        self.window.config.permissions[SOURCES[self.idx]] = bool(allow)
        self.idx += 1
        self.sel = 0
        if self.idx >= len(SOURCES):
            self._finish()

    def _finish(self) -> None:
        cfg = self.window.config
        for s in SOURCES[self.idx:]:
            cfg.permissions[s] = False
        self.idx = len(SOURCES)
        cfg.perception_asked = True
        _save(self.window)
        self.window.close_panel()

    def draw(self, surface, snap) -> None:
        if self.idx >= len(SOURCES):
            return
        r = draw_frame(surface, i18n.t("ui.perm.first.title"), closable=False)
        src = SOURCES[self.idx]
        draw_text(surface, i18n.t(f"ui.perm.src.{src}.title"), (r.x + 14, r.y + 60), HEAD, 28)
        draw_text(surface, i18n.t(f"ui.perm.src.{src}.desc"), (r.x + 14, r.y + 100), TXT, 22)
        draw_text(surface, i18n.t("ui.perm.first.hint"), (r.x + 14, r.y + 140), DIM, 20)
        self._rects = [pygame.Rect(r.x + 14, r.bottom - 60, 160, 36), pygame.Rect(r.x + 190, r.bottom - 60, 160, 36)]
        _button(surface, self._rects[0], i18n.t("ui.perm.allow"), self.sel == 0)
        _button(surface, self._rects[1], i18n.t("ui.perm.not_now"), self.sel == 1)

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, rc in enumerate(list(self._rects)):
                if rc.collidepoint(event.pos):
                    self._answer(i == 0)
                    break
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._finish()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self.sel = 1 - self.sel
            elif event.key == pygame.K_y:
                self._answer(True)
            elif event.key == pygame.K_n:
                self._answer(False)
            elif _enter(event) or event.key == pygame.K_SPACE:
                self._answer(self.sel == 0)
            return True
        return event.type in (pygame.TEXTINPUT, pygame.TEXTEDITING, pygame.MOUSEWHEEL)


class PermissionsPanel:
    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self.text = ""
        self._items: list[tuple[pygame.Rect, str, object]] = []   # (rect, kind, arg)
        self._kinds: list[tuple[str, object]] = []

    @property
    def cfg(self):
        return self.window.config

    @property
    def provider(self):
        return getattr(self.window, "perception_provider", None)

    def _call(self, name: str, *args):
        try:
            return getattr(self.provider, name)(*args)
        except Exception:
            return None

    # --- actions
    def toggle(self, src: str) -> None:
        self.cfg.permissions[src] = not self.cfg.permissions.get(src, False)
        _save(self.window)

    def cycle_interval(self) -> None:
        vals = [v for v, _ in INTERVALS]
        cur = self.cfg.perception_interval_s
        i = vals.index(cur) if cur in vals else 1
        self.cfg.perception_interval_s = vals[(i + 1) % len(vals)]
        _save(self.window)

    def add_block(self) -> None:
        entry = self.text.strip()
        self.text = ""
        if entry and entry not in self.cfg.perception_blocklist:
            self.cfg.perception_blocklist.append(entry)
            _save(self.window)

    def remove_block(self, entry: str) -> None:
        if entry in self.cfg.perception_blocklist:
            self.cfg.perception_blocklist.remove(entry)
            _save(self.window)

    def _activate(self, kind: str, arg) -> None:
        if kind == "src":
            self.toggle(arg)
        elif kind == "interval":
            self.cycle_interval()
        elif kind == "field":
            self.add_block()
        elif kind == "block":
            self.remove_block(arg)
        elif kind == "theme":
            self._call("unsilence_theme", arg)
        elif kind == "clear":
            self._call("clear_app_categories")

    # --- view
    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.perm.title"))
        dev = getattr(self.window, "dev", False)
        self._items, self._kinds = [], []
        y = r.y + 46
        x = r.x + 14

        def row(label, kind, arg, tag=None, color=TXT):
            nonlocal y
            rect = pygame.Rect(r.x + 10, y, r.w - 20, ROW_H - 2)
            idx = len(self._kinds)
            self._kinds.append((kind, arg))
            self._items.append((rect, kind, arg))
            if idx == self.sel:
                pygame.draw.rect(surface, (60, 56, 90), rect, border_radius=4)
            draw_text(surface, label, (x, rect.centery), color, 20, "midleft")
            if tag:
                draw_text(surface, tag, (rect.right - 8, rect.centery), OK, 20, "midright")
            y += ROW_H

        for src in SOURCES:
            on = self.cfg.permissions.get(src, False)
            row(i18n.t(f"ui.perm.src.{src}.title"), "src", src,
                i18n.t("ui.perm.on" if on else "ui.perm.off"), TXT if on else DIM)
        cur = self.cfg.perception_interval_s
        word = next((w for v, w in INTERVALS if v == cur), "normal")
        tag = i18n.t(f"ui.perm.interval.{word}") + (f" ({cur:g}s)" if dev else "")
        row(i18n.t("ui.perm.interval"), "interval", None, tag)
        y += 6
        draw_text(surface, i18n.t("ui.perm.blocklist"), (x, y), HEAD, 22)
        y += ROW_H
        shown = (self.text + "_") if self.text else i18n.t("ui.perm.blocklist_hint")
        row(_clean(self.window, shown) if self.text else shown, "field", None, None, TXT if self.text else DIM)
        for entry in self.cfg.perception_blocklist[:MAX_LIST]:
            row(_clean(self.window, entry), "block", entry, "x", WARN)
        themes = list(self._call("silenced_themes") or []) if self.provider is not None else []
        if themes:
            y += 6
            draw_text(surface, i18n.t("ui.perm.silenced"), (x, y), HEAD, 22)
            y += ROW_H
            for t in themes[:MAX_LIST]:
                row(_clean(self.window, t), "theme", t, i18n.t("ui.perm.reactivate"), TXT)
        if self.provider is not None:
            y += 6
            row(i18n.t("ui.perm.clear_categories"), "clear", None)
            err = self._call("hotkey_error")
            if err:
                key = "ui.perm.hotkey_wayland" if err == "wayland" else "ui.perm.hotkey_failed"
                draw_text(surface, i18n.t(key), (x, y + 4), WARN, 20)
        if self.sel >= len(self._kinds):
            self.sel = max(0, len(self._kinds) - 1)

    def handle_event(self, event) -> bool:
        if event.type == pygame.TEXTINPUT:
            if self._kinds and self._kinds[self.sel][0] == "field":
                self.text += getattr(event, "text", "")
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, (rect, kind, arg) in enumerate(list(self._items)):
                if rect.collidepoint(event.pos):
                    self.sel = i
                    self._activate(kind, arg)
                    break
            return True
        if event.type == pygame.KEYDOWN:
            n = max(1, len(self._kinds))
            field = bool(self._kinds) and self._kinds[self.sel][0] == "field"
            if event.key == pygame.K_DOWN:
                self.sel = min(n - 1, self.sel + 1)
            elif event.key == pygame.K_UP:
                self.sel = max(0, self.sel - 1)
            elif field and event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif _enter(event) or (event.key == pygame.K_SPACE and not field):
                if self._kinds:
                    self._activate(*self._kinds[self.sel])
            elif event.key == pygame.K_DELETE and self._kinds and self._kinds[self.sel][0] == "block":
                self.remove_block(self._kinds[self.sel][1])
            else:
                return False
            return True
        return event.type in (pygame.TEXTEDITING, pygame.MOUSEWHEEL)
