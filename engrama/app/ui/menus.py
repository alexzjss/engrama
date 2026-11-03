"""Panels: food menu and a placeholder. A panel has draw(surface, snap), handle_event(event) -> bool and optional
on_open()/on_close(). T9 adds models/settings panels here."""
from __future__ import annotations
import pygame
from engrama import vocab
from engrama.app import i18n
from engrama.app.art import sprites
from engrama.app.ui.hud import draw_text

BG = (28, 26, 40)
EDGE = (120, 110, 170)


def panel_rect(surface: pygame.Surface) -> pygame.Rect:
    return surface.get_rect().inflate(-80, -80)


def draw_frame(surface: pygame.Surface, title: str) -> pygame.Rect:
    r = panel_rect(surface)
    pygame.draw.rect(surface, BG, r, border_radius=8)
    pygame.draw.rect(surface, EDGE, r, 2, border_radius=8)
    draw_text(surface, title, (r.x + 14, r.y + 10), (240, 235, 255), 26)
    return r


class PlaceholderPanel:
    def __init__(self, title_key: str) -> None:
        self.title_key = title_key

    def draw(self, surface, snap) -> None:
        draw_frame(surface, i18n.t(self.title_key))

    def handle_event(self, event) -> bool:
        return False


class FoodMenu:
    CELL = (110, 84)

    def __init__(self, on_pick) -> None:
        self.on_pick = on_pick
        self.sel = 0
        self._ids: tuple[str, ...] = tuple(vocab.FOOD_IDS)   # medicine is appended in draw() unless the creature is an egg
        self._rects: list[pygame.Rect] = []

    def _layout(self, surface) -> None:
        r = panel_rect(surface)
        cols = max(1, (r.w - 28) // self.CELL[0])
        self._rects = []
        for i in range(len(self._ids)):
            x = r.x + 14 + (i % cols) * self.CELL[0]
            y = r.y + 50 + (i // cols) * self.CELL[1]
            self._rects.append(pygame.Rect(x, y, self.CELL[0] - 8, self.CELL[1] - 8))

    def draw(self, surface, snap) -> None:
        draw_frame(surface, i18n.t("ui.menu.food"))
        self._ids = tuple(vocab.FOOD_IDS) + (() if snap.stage == "egg" else (vocab.MEDICINE_ID,))
        self.sel = min(self.sel, len(self._ids) - 1)
        self._layout(surface)
        for i, (fid, rect) in enumerate(zip(self._ids, self._rects)):
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), rect, border_radius=6)
            icon = pygame.transform.scale(sprites.food_icon(fid), (40, 40))
            surface.blit(icon, icon.get_rect(midtop=(rect.centerx, rect.y + 6)))
            draw_text(surface, i18n.t(f"food.{fid}"), (rect.centerx, rect.bottom - 6), (230, 230, 240), 20, "midbottom")

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, r in enumerate(self._rects):
                if r.collidepoint(event.pos):
                    self.on_pick(self._ids[i])
                    return True
            return True
        if event.type == pygame.KEYDOWN:
            n = len(self._ids)
            if event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self.sel = (self.sel + 1) % n
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                self.sel = (self.sel - 1) % n
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_pick(self._ids[self.sel])
            else:
                return False
            return True
        return False


class DigitalMenu:
    """Joke maintenance items (M7), laid out like FoodMenu: icon + i18n name, on_pick(id)."""
    CELL = (110, 84)

    def __init__(self, on_pick) -> None:
        self.on_pick = on_pick
        self.sel = 0
        self._ids: tuple[str, ...] = tuple(vocab.DIGITAL_IDS)
        self._rects: list[pygame.Rect] = []

    def _layout(self, surface) -> None:
        r = panel_rect(surface)
        cols = max(1, (r.w - 28) // self.CELL[0])
        self._rects = [pygame.Rect(r.x + 14 + (i % cols) * self.CELL[0], r.y + 50 + (i // cols) * self.CELL[1],
                                   self.CELL[0] - 8, self.CELL[1] - 8) for i in range(len(self._ids))]

    def draw(self, surface, snap) -> None:
        from engrama.app.art import digital_fx
        draw_frame(surface, i18n.t("ui.menu.digital"))
        self._layout(surface)
        asked = getattr(snap, "digital_request", "")
        for i, (did, rect) in enumerate(zip(self._ids, self._rects)):
            col = (60, 56, 90) if i == self.sel else (42, 40, 62)
            pygame.draw.rect(surface, col, rect, border_radius=6)
            if did == asked:
                pygame.draw.rect(surface, (240, 210, 90), rect, 2, border_radius=6)
            ic = pygame.transform.scale(digital_fx.icon(did), (40, 40))
            surface.blit(ic, ic.get_rect(midtop=(rect.centerx, rect.y + 6)))
            draw_text(surface, i18n.t(f"digital.{did}"), (rect.centerx, rect.bottom - 6), (230, 230, 240), 18, "midbottom")

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, r in enumerate(self._rects):
                if r.collidepoint(event.pos):
                    self.on_pick(self._ids[i])
                    return True
            return True
        if event.type == pygame.KEYDOWN:
            n = len(self._ids)
            if event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self.sel = (self.sel + 1) % n
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                self.sel = (self.sel - 1) % n
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_pick(self._ids[self.sel])
            else:
                return False
            return True
        return False


# ---------------------------------------------------------------- models / settings (T9)
import threading

OK_COL = (130, 210, 140)
ERR_COL = (240, 120, 120)
TXT = (230, 230, 240)


def _btn(surface, rect: pygame.Rect, label: str, active: bool = False) -> None:
    pygame.draw.rect(surface, (80, 74, 130) if active else (54, 50, 82), rect, border_radius=6)
    pygame.draw.rect(surface, EDGE, rect, 1, border_radius=6)
    draw_text(surface, label, rect.center, TXT, 22, "center")


def _enter(event) -> bool:
    return event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)


class ModelsPanel:
    """Lists recommended models, a free-text row, a download button with progress.

    Window attributes used: config (recommended_models, model), save_config(), language
    (status, installed_models(), pull(name, on_progress))."""
    ROW_H = 34

    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self.text = ""
        self._lock = threading.Lock()
        self._pct = -2          # -2 idle, -1 failed, 0..100 running/done
        self._stat = ""
        self._dirty = False     # a pull finished: refresh installed set
        self._installed: set[str] | None = None
        self._rows: list[pygame.Rect] = []
        self._dl_rect = pygame.Rect(0, 0, 0, 0)

    @property
    def config(self):
        return getattr(self.window, "config", None)

    @property
    def language(self):
        return getattr(self.window, "language", None)

    def _models(self) -> list[str]:
        cfg = self.config
        return list(getattr(cfg, "recommended_models", ()) or ()) if cfg is not None else []

    def _missing(self) -> bool:
        lang = self.language
        return lang is None or getattr(lang, "status", None) == "missing"

    def _target(self) -> str:
        models = self._models()
        if self.sel < len(models):
            return models[self.sel]
        return self.text.strip()

    def on_open(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        lang = self.language
        try:
            self._installed = lang.installed_models() if lang is not None else None
        except Exception:
            self._installed = None

    # --- actions
    def select(self, name: str) -> None:
        cfg = self.config
        if not name or cfg is None:
            return
        cfg.model = name
        save = getattr(self.window, "save_config", None)
        if save:
            save()

    def _progress(self, pct: int, status: str) -> None:  # may run on another thread
        with self._lock:
            self._pct, self._stat = int(pct), str(status)
            if pct >= 100 or pct < 0:
                self._dirty = True

    def download(self) -> None:
        name = self._target()
        if not name or self._missing():
            return
        with self._lock:
            if 0 <= self._pct < 100:
                return
            self._pct, self._stat = 0, ""
        try:
            self.language.pull(name, self._progress)
        except Exception as ex:
            self._progress(-1, f"error: {ex}")

    # --- view
    def draw(self, surface, snap) -> None:
        with self._lock:
            pct, dirty = self._pct, self._dirty
            self._dirty = False
        if dirty:
            self._refresh()
        r = draw_frame(surface, i18n.t("ui.menu.models"))
        if self._missing():
            draw_text(surface, i18n.t("ui.ollama.missing"), (r.x + 14, r.y + 60), ERR_COL, 24)
            self._rows = []
            self._dl_rect = pygame.Rect(0, 0, 0, 0)
            return
        cur = getattr(self.config, "model", None)
        models = self._models()
        self._rows = []
        y = r.y + 50
        for i in range(len(models) + 1):
            rect = pygame.Rect(r.x + 14, y, r.w - 28 - 120, self.ROW_H - 4)
            self._rows.append(rect)
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), rect, border_radius=6)
            if i < len(models):
                name = models[i]
                draw_text(surface, name, (rect.x + 10, rect.centery), TXT, 22, "midleft")
                tags = []
                if name == cur:
                    tags.append(i18n.t("ui.models.active"))
                if self._installed is not None and name in self._installed:
                    tags.append(i18n.t("ui.models.installed"))
                if tags:
                    draw_text(surface, " / ".join(tags), (rect.right - 10, rect.centery), OK_COL, 20, "midright")
            else:
                shown = self.text or i18n.t("ui.models.custom")
                col = TXT if self.text else (140, 140, 160)
                if i == self.sel and self.text:
                    shown += "_"
                draw_text(surface, shown, (rect.x + 10, rect.centery), col, 22, "midleft")
            y += self.ROW_H
        self._dl_rect = pygame.Rect(r.right - 14 - 110, r.y + 50, 110, 32)
        _btn(surface, self._dl_rect, i18n.t("ui.download"))
        y += 10
        if 0 <= pct < 100:
            bar = pygame.Rect(r.x + 14, y, r.w - 28, 16)
            pygame.draw.rect(surface, (42, 40, 62), bar, border_radius=6)
            fill = bar.copy()
            fill.w = int(bar.w * pct / 100)
            pygame.draw.rect(surface, OK_COL, fill, border_radius=6)
            draw_text(surface, i18n.t("ui.ollama.pulling"), (bar.x, bar.bottom + 6), TXT, 20)
        elif pct == -1:
            draw_text(surface, i18n.t("ui.models.failed"), (r.x + 14, y), ERR_COL, 22)

    def handle_event(self, event) -> bool:
        if self._missing():
            return event.type == pygame.MOUSEBUTTONDOWN
        n = len(self._models()) + 1
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            if self._dl_rect.collidepoint(event.pos):
                self.download()
                return True
            for i, rc in enumerate(self._rows):
                if rc.collidepoint(event.pos):
                    self.sel = i
                    if i < len(self._models()):
                        self.select(self._models()[i])
            return True
        if event.type == pygame.TEXTINPUT:
            self.sel = n - 1
            self.text += event.text
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.sel = (self.sel + 1) % n
            elif event.key == pygame.K_UP:
                self.sel = (self.sel - 1) % n
            elif event.key == pygame.K_BACKSPACE and self.sel == n - 1:
                self.text = self.text[:-1]
            elif event.key == pygame.K_TAB:
                self.download()
            elif _enter(event):
                self.select(self._target())
            else:
                return False
            return True
        return False


class SettingsPanel:
    """Language, mute, manual rest and (dev only) time scale.

    Window attributes used: growler (set_muted, muted), set_rest, rest_manual, set_time_scale, dev,
    config (ui_lang), save_config()."""
    ROW_H = 38

    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self._rows: list[tuple[str, pygame.Rect]] = []
        self._scale_i = 0

    def _items(self) -> list[str]:
        items = ["lang", "mute", "rest"]
        if getattr(self.window, "dev", False):
            items.append("scale")
        return items

    def _muted(self) -> bool:
        return bool(getattr(self.window.growler, "muted", False))

    def activate(self, item: str) -> None:
        w = self.window
        if item == "lang":
            new = "en" if i18n.get_lang() == "pt" else "pt"
            i18n.set_lang(new)
            cfg = getattr(w, "config", None)
            if cfg is not None:
                cfg.ui_lang = new
                save = getattr(w, "save_config", None)
                if save:
                    save()
        elif item == "mute":
            w.growler.set_muted(not self._muted())
        elif item == "rest":
            w.rest_manual = not getattr(w, "rest_manual", False)
            fn = getattr(w, "set_rest", None)
            if fn:
                fn(w.rest_manual)
        elif item == "scale":
            scales = (1.0, 10.0, 60.0)
            self._scale_i = (self._scale_i + 1) % len(scales)
            fn = getattr(w, "set_time_scale", None)
            if fn:
                fn(scales[self._scale_i])

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.menu.settings"))
        w = self.window
        self._rows = []
        y = r.y + 54
        for i, item in enumerate(self._items()):
            rect = pygame.Rect(r.x + 14, y, r.w - 28, self.ROW_H - 4)
            self._rows.append((item, rect))
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), rect, border_radius=6)
            if item == "lang":
                label, val = i18n.t("ui.lang"), i18n.get_lang().upper()
            elif item == "mute":
                label, val = i18n.t("ui.mute"), "[x]" if self._muted() else "[ ]"
            elif item == "rest":
                on = getattr(w, "rest_manual", False)
                label, val = i18n.t("ui.rest.on") if on else i18n.t("ui.rest.off"), "[x]" if on else "[ ]"
            else:
                label = i18n.t("ui.dev")
                val = ("1x", "10x", "60x")[self._scale_i]
            draw_text(surface, label, (rect.x + 10, rect.centery), TXT, 22, "midleft")
            draw_text(surface, val, (rect.right - 10, rect.centery), OK_COL, 22, "midright")
            y += self.ROW_H

    def handle_event(self, event) -> bool:
        items = self._items()
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, (item, rect) in enumerate(self._rows):
                if rect.collidepoint(event.pos):
                    self.sel = i
                    self.activate(item)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.sel = (self.sel + 1) % len(items)
            elif event.key == pygame.K_UP:
                self.sel = (self.sel - 1) % len(items)
            elif _enter(event) or event.key == pygame.K_SPACE:
                self.activate(items[min(self.sel, len(items) - 1)])
            else:
                return False
            return True
        return False
