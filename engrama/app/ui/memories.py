"""Memories panel (F7): facts, topics, opinions and reflections the creature keeps, with deletion.

Talks to a duck-typed provider found at window.memory_provider (facts(), topics(), opinions(), reflections(),
delete_fact(key), delete_topic(name), forget_all(), summary()). The UI never imports services."""
from __future__ import annotations
import re
import time
import pygame
from engrama.app import i18n
from engrama.app.ui.hud import draw_text
from engrama.app.ui.menus import draw_frame, EDGE

TXT = (230, 230, 240)
DIM = (150, 150, 170)
WARN = (240, 160, 120)
HEAD = (170, 160, 240)
OK = (130, 210, 140)
ROW_H = 24
REFRESH_S = 2.0


def _enter(e) -> bool:
    return e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)


class MemoriesPanel:
    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self.scroll = 0
        self.pending: tuple[str, str | None, int] | None = None   # (kind, key, stage)
        self._data: dict = {}
        self._t = -1e9
        self._rows: list[pygame.Rect] = []                # selectable item rects (index == item index, minus forget)
        self._x_rects: list[tuple[pygame.Rect, int]] = []
        self._forget_rect = pygame.Rect(0, 0, 0, 0)
        self._items: list[tuple[str, str | None]] = []    # selectable: (kind, key); last is forget_all
        self._item_y: list[int] = []                      # content-space y of each item
        self._max_scroll = 0
        self._body_h = 0
        self._follow = False

    @property
    def provider(self):
        return getattr(self.window, "memory_provider", None)

    def on_open(self) -> None:
        self.pending = None
        self._refresh()

    def on_close(self) -> None:
        self.pending = None

    def _refresh(self) -> None:
        p = self.provider
        self._t = time.monotonic()
        if p is None:
            self._data = {}
            return
        d = {}
        for name in ("facts", "topics", "opinions", "reflections"):
            try:
                d[name] = list(getattr(p, name)())
            except Exception:
                d[name] = []
        self._data = d

    def _clean(self, s) -> str:
        s = str(s)
        return s if getattr(self.window, "dev", False) else re.sub(r"\d", "", s)

    # --- actions
    def _call(self, name: str, *args) -> None:
        try:
            getattr(self.provider, name)(*args)
        except Exception:
            pass
        self._refresh()

    def _execute(self) -> None:
        kind, key, stage = self.pending
        if kind == "all" and stage < 2:
            self.pending = (kind, key, stage + 1)
            return
        self.pending = None
        if kind == "fact":
            self._call("delete_fact", key)
        elif kind == "topic":
            self._call("delete_topic", key)
        elif kind == "all":
            self._call("forget_all")
            self.sel = 0
            self.scroll = 0

    def _ask(self, idx: int) -> None:
        if 0 <= idx < len(self._items):
            kind, key = self._items[idx]
            self.pending = (kind, key, 1)

    # --- view
    def draw(self, surface, snap) -> None:
        if time.monotonic() - self._t > REFRESH_S:
            self._refresh()
        r = draw_frame(surface, i18n.t("ui.memories.title"))
        self._rows, self._x_rects, self._items, self._item_y = [], [], [], []
        self._forget_rect = pygame.Rect(0, 0, 0, 0)
        if self.provider is None:
            draw_text(surface, i18n.t("ui.memories.empty"), (r.x + 14, r.y + 60), DIM, 24)
            return
        d = self._data
        body = pygame.Rect(r.x + 10, r.y + 46, r.w - 20, r.h - 46 - 44)
        old = surface.get_clip()
        surface.set_clip(body)
        y = body.y - self.scroll
        x_w = 24

        def head(label):
            nonlocal y
            draw_text(surface, label, (body.x + 4, y), HEAD, 22)
            y += ROW_H

        def row(text, kind, key, tag=None):
            nonlocal y
            rect = pygame.Rect(body.x, y, body.w, ROW_H - 2)
            idx = None
            if kind is not None:
                idx = len(self._items)
                self._items.append((kind, key))
                self._item_y.append(y - body.y + self.scroll)
                self._rows.append(rect)
                if idx == self.sel:
                    pygame.draw.rect(surface, (60, 56, 90), rect, border_radius=4)
            draw_text(surface, self._clean(text), (rect.x + 8, rect.centery), TXT, 20, "midleft")
            if tag:
                draw_text(surface, tag, (rect.right - x_w - 8, rect.centery), OK, 18, "midright")
            if idx is not None:
                xr = pygame.Rect(rect.right - x_w, rect.y, x_w, rect.h)
                draw_text(surface, "x", xr.center, WARN, 20, "center")
                self._x_rects.append((xr, idx))
            y += ROW_H

        head(i18n.t("ui.memories.facts"))
        for k, v in d.get("facts", []):
            row(v if str(v).startswith(str(k)) else f"{k}: {v}", "fact", k)
        head(i18n.t("ui.memories.topics"))
        cur = i18n.t("ui.memories.current")
        for name, is_cur in d.get("topics", []):
            row(name, "topic", name, cur if is_cur else None)
        head(i18n.t("ui.memories.opinions"))
        for topic, pos in d.get("opinions", []):
            row(f"{topic}: {pos}", None, None)
        head(i18n.t("ui.memories.reflections"))
        for s in d.get("reflections", []):
            row(s, None, None)
        content_h = y + self.scroll - body.y + 4
        surface.set_clip(old)
        self._items.append(("all", None))
        self._item_y.append(content_h)

        self._body_h = body.h
        self._max_scroll = max(0, content_h - body.h)
        if self._follow and self.sel < len(self._item_y) - 1:
            top = self._item_y[self.sel]
            if top < self.scroll:
                self.scroll = top
            elif top + ROW_H > self.scroll + body.h:
                self.scroll = top + ROW_H - body.h
        self._follow = False
        self.scroll = max(0, min(self._max_scroll, self.scroll))

        on_forget = self.sel == len(self._items) - 1
        self._forget_rect = pygame.Rect(r.x + 14, r.bottom - 38, 180, 28)
        pygame.draw.rect(surface, (110, 60, 60) if on_forget else (80, 46, 52), self._forget_rect, border_radius=6)
        pygame.draw.rect(surface, EDGE, self._forget_rect, 1, border_radius=6)
        draw_text(surface, i18n.t("ui.memories.forget_all"), self._forget_rect.center, TXT, 22, "center")
        if self.pending is not None:
            draw_text(surface, i18n.t("ui.memories.confirm"), (self._forget_rect.right + 14, self._forget_rect.centery),
                      WARN, 22, "midleft")

    def handle_event(self, event) -> bool:
        if self.provider is None:
            return event.type == pygame.MOUSEBUTTONDOWN
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * ROW_H))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            if self.pending is not None:
                return True
            if self._forget_rect.collidepoint(event.pos):
                self.sel = max(0, len(self._items) - 1)
                self.pending = ("all", None, 1)
                return True
            for xr, idx in self._x_rects:
                if xr.collidepoint(event.pos):
                    self.sel = idx
                    self._ask(idx)
                    return True
            for i, rect in enumerate(self._rows):
                if rect.collidepoint(event.pos):
                    self.sel = i
            return True
        if event.type == pygame.KEYDOWN:
            if self.pending is not None:
                if _enter(event):
                    self._execute()
                elif event.key == pygame.K_ESCAPE:
                    self.pending = None
                return True
            n = max(1, len(self._items))
            if event.key == pygame.K_DOWN:
                self.sel = min(n - 1, self.sel + 1)
                self._follow = True
            elif event.key == pygame.K_UP:
                self.sel = max(0, self.sel - 1)
                self._follow = True
            elif event.key == pygame.K_DELETE or (_enter(event) and self.sel == n - 1):
                self._ask(self.sel)
            else:
                return False
            return True
        return False
