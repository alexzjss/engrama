"""Panels: food menu and a placeholder. A panel has draw(surface, snap), handle_event(event) -> bool and optional
on_open()/on_close(). T9 adds models/settings panels here."""
from __future__ import annotations
import pygame
from engrama import vocab
from engrama.app import i18n
from engrama.app.art import sprites
from engrama.app.ui.hud import draw_text, fit, font, wrap

BG = (28, 26, 40)
EDGE = (120, 110, 170)


def panel_rect(surface: pygame.Surface) -> pygame.Rect:
    return surface.get_rect().inflate(-80, -80)


def close_rect(surface: pygame.Surface) -> pygame.Rect:
    """The "x" at the top right of every panel frame."""
    r = panel_rect(surface)
    return pygame.Rect(r.right - 34, r.y + 8, 24, 24)


_dim: dict[tuple[int, int], pygame.Surface] = {}


def draw_frame(surface: pygame.Surface, title: str, closable: bool = True) -> pygame.Rect:
    size = surface.get_size()
    veil = _dim.get(size)
    if veil is None:   # the scene behind a panel is dimmed so the panel reads as the one thing to look at
        _dim.clear()
        veil = _dim[size] = pygame.Surface(size, pygame.SRCALPHA)
        veil.fill((12, 10, 22, 120))
    surface.blit(veil, (0, 0))
    r = panel_rect(surface)
    pygame.draw.rect(surface, BG, r, border_radius=8)
    pygame.draw.rect(surface, EDGE, r, 2, border_radius=8)
    draw_text(surface, title, (r.x + 14, r.y + 10), (240, 235, 255), 26)
    pygame.draw.line(surface, (58, 54, 86), (r.x + 12, r.y + 40), (r.right - 12, r.y + 40))
    if closable:
        c = close_rect(surface)
        pygame.draw.rect(surface, (54, 50, 82), c, border_radius=6)
        pygame.draw.line(surface, (220, 215, 240), (c.x + 7, c.y + 7), (c.right - 8, c.bottom - 8), 2)
        pygame.draw.line(surface, (220, 215, 240), (c.right - 8, c.y + 7), (c.x + 7, c.bottom - 8), 2)
    return r


def draw_cell_label(surface: pygame.Surface, text: str, rect: pygame.Rect, size: int = 18) -> None:
    """An item name under its icon: up to two centred lines, never wider than the cell."""
    lines = wrap(text, size, rect.w - 6)[:2]
    if len(lines) == 2:
        lines[1] = fit(lines[1], size, rect.w - 6)
    y = rect.bottom - 5 - (len(lines) - 1) * (size - 4)
    for ln in lines:
        draw_text(surface, fit(ln, size, rect.w - 6), (rect.centerx, y), (230, 230, 240), size, "midbottom")
        y += size - 4


class PlaceholderPanel:
    def __init__(self, title_key: str) -> None:
        self.title_key = title_key

    def draw(self, surface, snap) -> None:
        draw_frame(surface, i18n.t(self.title_key))

    def handle_event(self, event) -> bool:
        return False


class FoodMenu:
    CELL = (122, 100)

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
            draw_cell_label(surface, i18n.t(f"food.{fid}"), rect)

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
    CELL = (122, 100)

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
            draw_cell_label(surface, i18n.t(f"digital.{did}"), rect)

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
    """Lists recommended models, a free-text row, a download button with progress, and (M9) the
    'Busca por significado' block: embedding model choice, download and on/off switch.

    Window attributes used: config (recommended_models, model, recommended_embed_models, embed_model,
    semantic_recall), save_config(), language (status, embed_status, installed_models(),
    pull(name, on_progress), set_embed_model(name), set_semantic_recall(on))."""
    ROW_H = 34
    EMBED_SUB = 3          # embed block rows: 0 model, 1 download, 2 switch

    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self.text = ""
        self.embed_focus = False
        self.esel = 0
        self._lock = threading.Lock()
        self._pct = -2          # -2 idle, -1 failed, 0..100 running/done
        self._stat = ""
        self._kind = "chat"     # which download the progress belongs to: "chat" or "embed"
        self._dirty = False     # a pull finished: refresh installed set
        self._installed: set[str] | None = None
        self._rows: list[pygame.Rect] = []
        self._dl_rect = pygame.Rect(0, 0, 0, 0)
        self._embed_model_rect = pygame.Rect(0, 0, 0, 0)
        self._embed_dl_rect = pygame.Rect(0, 0, 0, 0)
        self._embed_sw_rect = pygame.Rect(0, 0, 0, 0)

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

    # --- M9 embedding block helpers
    def _embed_models(self) -> list[str]:
        cfg = self.config
        if cfg is None:
            return []
        names = list(getattr(cfg, "recommended_embed_models", ()) or ())
        cur = getattr(cfg, "embed_model", "") or ""
        if cur and cur not in names:
            names.insert(0, cur)
        return names

    def _embed_target(self) -> str:
        cfg = self.config
        return (getattr(cfg, "embed_model", "") or "") if cfg is not None else ""

    def _embed_installed(self) -> bool:
        name = self._embed_target()
        inst = self._installed
        return bool(name) and inst is not None and (name in inst or f"{name}:latest" in inst)

    def _embed_status(self) -> str:
        return str(getattr(self.language, "embed_status", "off") or "off")

    def _embed_on(self) -> bool:
        return bool(getattr(self.config, "semantic_recall", True))

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

    def select_embed(self, name: str) -> None:
        cfg = self.config
        lang = self.language
        if not name or cfg is None or lang is None:
            return
        try:
            fn = getattr(lang, "set_embed_model", None)
            if fn:
                fn(name)
        except Exception:
            pass
        cfg.embed_model = name
        save = getattr(self.window, "save_config", None)
        if save:
            save()

    def cycle_embed(self, step: int = 1) -> None:
        names = self._embed_models()
        if not names:
            return
        cur = self._embed_target()
        i = names.index(cur) if cur in names else -1
        self.select_embed(names[(i + step) % len(names)])

    def toggle_embed(self) -> None:
        cfg = self.config
        lang = self.language
        if cfg is None or lang is None:
            return
        new = not self._embed_on()
        try:
            fn = getattr(lang, "set_semantic_recall", None)
            if fn:
                fn(new)
        except Exception:
            pass
        cfg.semantic_recall = new
        save = getattr(self.window, "save_config", None)
        if save:
            save()

    def _progress(self, pct: int, status: str) -> None:  # may run on another thread
        with self._lock:
            self._pct, self._stat = int(pct), str(status)
            if pct >= 100 or pct < 0:
                self._dirty = True

    def _start_pull(self, kind: str) -> bool:
        with self._lock:
            if 0 <= self._pct < 100:
                return False
            self._pct, self._stat, self._kind = 0, "", kind
            return True

    def download(self) -> None:
        name = self._target()
        if not name or self._missing():
            return
        if not self._start_pull("chat"):
            return
        try:
            self.language.pull(name, self._progress)
        except Exception as ex:
            self._progress(-1, f"error: {ex}")

    def download_embed(self) -> None:
        name = self._embed_target()
        if not name or self._missing():
            return
        if not self._start_pull("embed"):
            return
        try:
            self.language.pull(name, self._progress)
        except Exception as ex:
            self._progress(-1, f"error: {ex}")

    # --- view
    def draw(self, surface, snap) -> None:
        with self._lock:
            pct, dirty, kind = self._pct, self._dirty, self._kind
            self._dirty = False
        if dirty:
            self._refresh()
        r = draw_frame(surface, i18n.t("ui.menu.models"))
        if self._missing():
            draw_text(surface, i18n.t("ui.ollama.missing"), (r.x + 14, r.y + 56), ERR_COL, 24)
            y = r.y + 88
            for k in ("ui.ollama.help.alive", "ui.ollama.help.install", "ui.ollama.help.then"):
                for ln in wrap(i18n.t(k), 20, r.w - 28):   # what it means and what to do, not just an error
                    draw_text(surface, ln, (r.x + 14, y), TXT, 20)
                    y += 20
                y += 6
            self._rows = []
            self._dl_rect = pygame.Rect(0, 0, 0, 0)
            self._embed_rects_clear()
            self._draw_embed(surface, r, y + 14, enabled=False, pct=-2)
            return
        cur = getattr(self.config, "model", None)
        models = self._models()
        self._rows = []
        y = r.y + 50
        for i in range(len(models) + 1):
            rect = pygame.Rect(r.x + 14, y, r.w - 28 - 120, self.ROW_H - 4)
            self._rows.append(rect)
            pygame.draw.rect(surface, (60, 56, 90) if (i == self.sel and not self.embed_focus) else (42, 40, 62),
                             rect, border_radius=6)
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
                if i == self.sel and self.text and not self.embed_focus:
                    shown += "_"
                draw_text(surface, shown, (rect.x + 10, rect.centery), col, 22, "midleft")
            y += self.ROW_H
        self._dl_rect = pygame.Rect(r.right - 14 - 110, r.y + 50, 110, 32)
        _btn(surface, self._dl_rect, i18n.t("ui.download"))
        y += 10
        chat_pull = kind == "chat"
        if chat_pull and 0 <= pct < 100:
            bar = pygame.Rect(r.x + 14, y, r.w - 28, 16)
            pygame.draw.rect(surface, (42, 40, 62), bar, border_radius=6)
            fill = bar.copy()
            fill.w = int(bar.w * pct / 100)
            pygame.draw.rect(surface, OK_COL, fill, border_radius=6)
            draw_text(surface, i18n.t("ui.ollama.pulling"), (bar.x, bar.bottom + 6), TXT, 20)
            y += 30
        elif chat_pull and pct == -1:
            draw_text(surface, i18n.t("ui.models.failed"), (r.x + 14, y), ERR_COL, 22)
            y += 30
        self._draw_embed(surface, r, y + 10, enabled=True, pct=pct if kind == "embed" else -2,
                         failed=(kind == "embed" and pct == -1))

    def _embed_rects_clear(self) -> None:
        self._embed_model_rect = self._embed_dl_rect = self._embed_sw_rect = pygame.Rect(0, 0, 0, 0)

    def _draw_embed(self, surface, r, y, enabled: bool, pct: int, failed: bool = False) -> None:
        head = (170, 160, 240) if enabled else (90, 90, 110)
        draw_text(surface, i18n.t("ui.models.embed_title"), (r.x + 14, y), head, 22)
        if not enabled:
            self._embed_rects_clear()
            draw_text(surface, i18n.t("ui.models.embed_hint"), (r.x + 14, y + 26), (90, 90, 110), 18)
            return
        if self._embed_installed():
            draw_text(surface, i18n.t("ui.models.installed"), (r.right - 14, y), OK_COL, 20, "midright")
        else:
            draw_text(surface, i18n.t("ui.models.embed_missing"), (r.right - 14, y), ERR_COL, 20, "midright")
        draw_text(surface, i18n.t("ui.models.embed_hint"), (r.x + 14, y + 26), (150, 150, 170), 18)
        row_y = y + 52
        sw_w, dl_w, gap = 150, 110, 8
        model_w = r.w - 28 - sw_w - dl_w - 2 * gap
        self._embed_model_rect = pygame.Rect(r.x + 14, row_y, model_w, 30)
        self._embed_dl_rect = pygame.Rect(self._embed_model_rect.right + gap, row_y, dl_w, 30)
        self._embed_sw_rect = pygame.Rect(self._embed_dl_rect.right + gap, row_y, sw_w, 30)
        focus = self.embed_focus
        pygame.draw.rect(surface, (60, 56, 90) if focus and self.esel == 0 else (42, 40, 62),
                         self._embed_model_rect, border_radius=6)
        draw_text(surface, self._embed_target() or "-", (self._embed_model_rect.x + 10, self._embed_model_rect.centery),
                  TXT, 22, "midleft")
        _btn(surface, self._embed_dl_rect, i18n.t("ui.download"), active=focus and self.esel == 1)
        on = self._embed_on()
        _btn(surface, self._embed_sw_rect, i18n.t("ui.models.embed_on" if on else "ui.models.embed_off"),
             active=on or (focus and self.esel == 2))
        if 0 <= pct < 100:
            bar = pygame.Rect(r.x + 14, row_y + 40, r.w - 28, 12)
            pygame.draw.rect(surface, (42, 40, 62), bar, border_radius=6)
            fill = bar.copy()
            fill.w = int(bar.w * pct / 100)
            pygame.draw.rect(surface, OK_COL, fill, border_radius=6)
        elif failed:
            draw_text(surface, i18n.t("ui.models.failed"), (r.x + 14, row_y + 40), ERR_COL, 20)

    def _embed_click(self, pos) -> bool:
        if self._embed_model_rect.collidepoint(pos):
            self.embed_focus, self.esel = True, 0
            self.cycle_embed(1)
            return True
        if self._embed_dl_rect.collidepoint(pos):
            self.embed_focus, self.esel = True, 1
            self.download_embed()
            return True
        if self._embed_sw_rect.collidepoint(pos):
            self.embed_focus, self.esel = True, 2
            self.toggle_embed()
            return True
        return False

    def _embed_key(self, event) -> bool:
        if event.key == pygame.K_DOWN:
            if self.esel < self.EMBED_SUB - 1:
                self.esel += 1
            else:
                self.embed_focus = False
                self.sel = 0
        elif event.key == pygame.K_UP:
            if self.esel > 0:
                self.esel -= 1
            else:
                self.embed_focus = False
                self.sel = len(self._models())
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and self.esel == 0:
            self.cycle_embed(1 if event.key == pygame.K_RIGHT else -1)
        elif event.key == pygame.K_TAB or (_enter(event) and self.esel == 1) or (
                event.key == pygame.K_SPACE and self.esel == 1):
            self.download_embed()
        elif _enter(event) or event.key == pygame.K_SPACE:
            if self.esel == 0:
                self.cycle_embed(1)
            elif self.esel == 2:
                self.toggle_embed()
        else:
            return False
        return True

    def handle_event(self, event) -> bool:
        if self._missing():
            return event.type == pygame.MOUSEBUTTONDOWN
        n = len(self._models()) + 1
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            if self._dl_rect.collidepoint(event.pos):
                self.embed_focus = False
                self.download()
                return True
            if self._embed_click(event.pos):
                return True
            self.embed_focus = False
            for i, rc in enumerate(self._rows):
                if rc.collidepoint(event.pos):
                    self.sel = i
                    if i < len(self._models()):
                        self.select(self._models()[i])
            return True
        if self.embed_focus and event.type == pygame.KEYDOWN:
            return self._embed_key(event)
        if event.type == pygame.TEXTINPUT:
            self.embed_focus = False
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
        self.naming = False     # the name row is taking text

    def _items(self) -> list[str]:
        items = ["lang", "mute", "rest"]
        if hasattr(getattr(self.window, "config", None), "creature_name"):
            items.append("name")
        if getattr(getattr(self.window, "desktop", None), "available", False):
            items.append("overlay")
        if getattr(self.window, "autostart", None) is not None:
            items.append("autostart")
        if getattr(self.window, "dev", False):
            items.append("scale")
        return items

    def _muted(self) -> bool:
        return bool(getattr(self.window.growler, "muted", False))

    def activate(self, item: str) -> None:
        w = self.window
        if item == "name":
            self.naming = not self.naming
            if not self.naming:
                save_name(w, w.config.creature_name)
        elif item == "lang":
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
        elif item == "overlay":
            w.set_mode("terrarium" if getattr(w, "mode", "terrarium") == "overlay" else "overlay")
        elif item == "autostart":
            a = getattr(w, "autostart", None)
            if a is not None and a.available:
                a.set(not a.enabled())   # the state is read back from the OS on every draw
        elif item == "scale":
            scales = (1.0, 10.0, 60.0)
            self._scale_i = (self._scale_i + 1) % len(scales)
            fn = getattr(w, "set_time_scale", None)
            if fn:
                fn(scales[self._scale_i])

    def on_close(self) -> None:
        if self.naming:
            self.activate("name")

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.menu.settings"))
        w = self.window
        self._rows = []
        y = r.y + 54
        for i, item in enumerate(self._items()):
            rect = pygame.Rect(r.x + 14, y, r.w - 28, self.ROW_H - 4)
            self._rows.append((item, rect))
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), rect, border_radius=6)
            if item == "name":
                cur = getattr(w.config, "creature_name", "") or ""
                label = i18n.t("ui.name.label")
                val = fit(cur + ("_" if self.naming else ""), 22, rect.w // 2) if (cur or self.naming) else "…"
            elif item == "lang":
                label, val = i18n.t("ui.lang"), i18n.get_lang().upper()
            elif item == "mute":
                label, val = i18n.t("ui.mute"), "[x]" if self._muted() else "[ ]"
            elif item == "rest":
                on = getattr(w, "rest_manual", False)
                label, val = i18n.t("ui.rest.on") if on else i18n.t("ui.rest.off"), "[x]" if on else "[ ]"
            elif item == "overlay":
                label = i18n.t("ui.menu.overlay")
                val = "[x]" if getattr(w, "mode", "terrarium") == "overlay" else "[ ]"
            elif item == "autostart":
                a = w.autostart
                label = i18n.t("settings.autostart") if a.available else i18n.t("settings.autostart_dev")
                val = ("[x]" if a.enabled() else "[ ]") if a.available else "--"
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
            if self.naming:
                self.activate("name")   # a click elsewhere confirms the name
            return True
        if self.naming:
            cfg = self.window.config
            if event.type == pygame.TEXTINPUT:
                cfg.creature_name = clean_name(cfg.creature_name + event.text)
                return True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    cfg.creature_name = cfg.creature_name[:-1]
                elif _enter(event):
                    self.activate("name")
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


# ---------------------------------------------------------------- name and help (MVP polish)
MAX_NAME = 16


def clean_name(text: str) -> str:
    """A creature name: printable, single line, no digits (the UI never shows numbers), at most MAX_NAME chars."""
    return "".join(c for c in text if c.isprintable() and not c.isdigit()).lstrip()[:MAX_NAME]


def save_name(window, name: str) -> None:
    cfg = getattr(window, "config", None)
    if cfg is None:
        return
    cfg.creature_name = clean_name(name).strip()
    save = getattr(window, "save_config", None)
    if save:
        save()


class NamePanel:
    """Asked once, right after the hatch: a name makes her someone. Enter keeps it, Esc leaves her unnamed for now
    (the name can always be set in Settings)."""

    def __init__(self, window) -> None:
        self.window = window
        self.text = ""
        self._ok = pygame.Rect(0, 0, 0, 0)

    def confirm(self) -> None:
        if self.text.strip():
            save_name(self.window, self.text)
        self.window.close_panel()

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.name.title"))
        y = r.y + 60
        for ln in wrap(i18n.t("ui.name.ask"), 22, r.w - 28):
            draw_text(surface, ln, (r.x + 14, y), TXT, 22)
            y += 22
        field = pygame.Rect(r.x + 14, y + 14, r.w - 28, 36)
        pygame.draw.rect(surface, (42, 40, 62), field, border_radius=6)
        pygame.draw.rect(surface, EDGE, field, 1, border_radius=6)
        draw_text(surface, self.text + "_", (field.x + 10, field.centery), TXT, 26, "midleft")
        self._ok = pygame.Rect(field.right - 120, field.bottom + 14, 120, 32)
        _btn(surface, self._ok, i18n.t("ui.name.ok"), active=bool(self.text.strip()))
        draw_text(surface, i18n.t("ui.name.later"), (r.x + 14, self._ok.centery), (150, 150, 170), 18, "midleft")

    def handle_event(self, event) -> bool:
        if event.type == pygame.TEXTINPUT:
            self.text = clean_name(self.text + event.text)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.type == pygame.KEYDOWN and _enter(event):
            self.confirm()
        elif event.type == pygame.MOUSEBUTTONDOWN and self._ok.collidepoint(event.pos):
            self.confirm()
        else:
            return False
        return True


HELP_TIPS = ("ui.help.pet", "ui.help.talk", "ui.help.feed", "ui.help.file", "ui.help.voice")
HELP_KEYS = (("F3", "ui.help.key.rest"), ("F9", "ui.help.key.eyes"), ("F11", "ui.help.key.overlay"),
             ("Esc", "ui.help.key.close"))


class HelpPanel:
    """What you can do, in plain words, plus the keys that have no button."""

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.help.title"))
        y = r.y + 54
        for k in HELP_TIPS:
            pygame.draw.circle(surface, (170, 160, 240), (r.x + 20, y + 9), 3)
            for ln in wrap(i18n.t(k), 20, r.w - 50):
                draw_text(surface, ln, (r.x + 32, y), TXT, 20)
                y += 20
            y += 8
        y += 6
        kw = max(font(20).size(k)[0] for k, _ in HELP_KEYS) + 16
        for k, label in HELP_KEYS:
            box = pygame.Rect(r.x + 14, y, kw, 22)
            pygame.draw.rect(surface, (54, 50, 82), box, border_radius=5)
            draw_text(surface, k, box.center, (240, 235, 255), 20, "center")
            draw_text(surface, fit(i18n.t(label), 20, r.w - kw - 40), (box.right + 10, box.centery), (190, 190, 210), 20,
                      "midleft")
            y += 26

    def handle_event(self, event) -> bool:
        return False
