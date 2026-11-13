"""Actions panel (M20): the three permitted tools, each with its own switch, usable by menu alone (no LLM needed).

`window.actions` is duck-typed: allowed(tool), set_allowed(tool, on), run(intent-like), store (reminders, focus_*),
and `make_intent(kind, minutes, text)`. Without it the panel only says the feature is unavailable."""
from __future__ import annotations
import time
import pygame
from engrama.app import i18n
from engrama.app.ui.hud import draw_text, fit, font, wrap
from engrama.app.ui.menus import EDGE, OK_COL, TXT, _btn, draw_frame

TOOLS = ("reminders", "focus", "notes")
QUICK_MIN = (5, 15, 30, 60)
FOCUS_MIN = (25, 50)
MAX_TEXT = 120
DIM = (150, 150, 170)


def left_text(seconds: float) -> str:
    """Time left, short: "40 s", "12 min", "1 h 05"."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{(s + 59) // 60} min"
    return f"{s // 3600} h {s % 3600 // 60:02d}"


class ActionsPanel:
    def __init__(self, window) -> None:
        self.window = window
        self.text = ""
        self._hits: list[tuple[pygame.Rect, tuple]] = []   # (rect, command) of the last draw

    @property
    def actions(self):
        return getattr(self.window, "actions", None)

    def _do(self, cmd: tuple) -> None:
        a = self.actions
        if a is None:
            return
        kind = cmd[0]
        if kind == "perm":
            a.set_allowed(cmd[1], not a.allowed(cmd[1]))
        elif kind == "remind":
            if a.run(a.make_intent("reminder", cmd[1], self.text)) == "ok":
                self.text = ""
        elif kind == "note":
            if self.text.strip() and a.run(a.make_intent("note", 0, self.text)) == "ok":
                self.text = ""
        elif kind == "focus":
            a.run(a.make_intent("focus", cmd[1], ""))
        elif kind == "focus_stop":
            a.run(a.make_intent("focus_stop", 0, ""))
        elif kind == "cancel":
            a.store.cancel(cmd[1])

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.actions.title"))
        self._hits = []
        a = self.actions
        x, w, y = r.x + 14, r.w - 28, r.y + 50
        if a is None:
            draw_text(surface, i18n.t("ui.actions.unavailable"), (x, y), DIM, 20)
            return
        for ln in wrap(i18n.t("ui.actions.intro"), 18, w):
            draw_text(surface, ln, (x, y), DIM, 18)
            y += 18
        y += 6
        for tool in TOOLS:   # one switch per tool, all off until the user says so
            row = pygame.Rect(x, y, w, 28)
            on = a.allowed(tool)
            pygame.draw.rect(surface, (42, 40, 62), row, border_radius=6)
            name = i18n.t(f"ui.actions.{tool}")
            nr = draw_text(surface, name, (row.x + 10, row.centery), TXT, 20, "midleft")
            state = i18n.t("ui.perm.on" if on else "ui.perm.off")
            sr = draw_text(surface, state, (row.right - 10, row.centery), OK_COL if on else DIM, 20, "midright")
            draw_text(surface, fit(i18n.t(f"ui.actions.{tool}.desc"), 16, sr.x - nr.right - 24), (nr.right + 12, row.centery),
                      DIM, 16, "midleft")
            self._hits.append((row, ("perm", tool)))
            y += 32
        y += 6
        # focus
        store = a.store
        if store.focus_active:
            bar = pygame.Rect(x, y + 4, w - 130, 18)
            pygame.draw.rect(surface, (42, 40, 62), bar, border_radius=6)
            fill = bar.copy()
            fill.w = max(6, int(bar.w * store.focus_progress()))
            pygame.draw.rect(surface, OK_COL, fill, border_radius=6)
            draw_text(surface, f"{i18n.t('ui.actions.focus')}: {left_text(store.focus_left())}", (bar.x + 8, bar.centery),
                      (30, 26, 40), 18, "midleft")
            stop = pygame.Rect(bar.right + 10, y, 120, 26)
            _btn(surface, stop, i18n.t("ui.actions.stop"))
            self._hits.append((stop, ("focus_stop",)))
        else:
            bx = x
            for m in FOCUS_MIN:
                b = pygame.Rect(bx, y, 150, 26)
                _btn(surface, b, f"{i18n.t('ui.actions.focus')} {m} min", active=False)
                if a.allowed("focus"):
                    self._hits.append((b, ("focus", m)))
                bx += 158
        y += 36
        # one text field feeds both the reminder buttons and the note button
        field = pygame.Rect(x, y, w, 28)
        pygame.draw.rect(surface, (34, 32, 50), field, border_radius=6)
        pygame.draw.rect(surface, EDGE, field, 1, border_radius=6)
        blink = "_" if int(time.monotonic() * 2) % 2 == 0 else ""
        if self.text:
            shown = self.text
            while shown and draw_width(shown + "_") > field.w - 16:
                shown = shown[1:]
            draw_text(surface, shown + blink, (field.x + 8, field.centery), TXT, 20, "midleft")
        else:
            draw_text(surface, i18n.t("ui.actions.placeholder"), (field.x + 8, field.centery), (110, 110, 132), 20, "midleft")
        y += 34
        draw_text(surface, i18n.t("ui.actions.remind_in"), (x, y + 13), DIM, 18, "midleft")
        bx = x + draw_width(i18n.t("ui.actions.remind_in"), 18) + 10
        for m in QUICK_MIN:
            b = pygame.Rect(bx, y, 64, 26)
            _btn(surface, b, f"{m} min" if m < 60 else f"{m // 60} h")
            if a.allowed("reminders"):
                self._hits.append((b, ("remind", m)))
            bx += 70
        nb = pygame.Rect(r.right - 14 - 110, y, 110, 26)
        _btn(surface, nb, i18n.t("ui.actions.note_btn"), active=bool(self.text.strip()) and a.allowed("notes"))
        if a.allowed("notes"):
            self._hits.append((nb, ("note",)))
        y += 36
        # pending reminders, soonest first
        now = time.time()
        bottom = r.bottom - 30
        if not store.reminders:
            draw_text(surface, i18n.t("ui.actions.none"), (x, y), DIM, 18)
        for rem in store.reminders:
            if y + 24 > bottom:
                draw_text(surface, "…", (x, y), DIM, 18)
                break
            row = pygame.Rect(x, y, w, 22)
            lr = draw_text(surface, left_text(rem.due - now), (row.x + 4, row.centery), OK_COL, 18, "midleft")
            kill = pygame.Rect(row.right - 22, row.y, 22, 22)
            draw_text(surface, fit(rem.text or i18n.t("ui.actions.plain"), 18, kill.x - lr.right - 20),
                      (max(lr.right + 12, row.x + 76), row.centery), TXT, 18, "midleft")
            pygame.draw.rect(surface, (54, 50, 82), kill, border_radius=5)
            draw_text(surface, "x", kill.center, (220, 215, 240), 18, "center")
            self._hits.append((kill, ("cancel", rem.id)))
            y += 24
        draw_text(surface, fit(i18n.t("ui.actions.hint"), 16, w), (x, r.bottom - 22), DIM, 16)

    def handle_event(self, event) -> bool:
        if event.type == pygame.TEXTINPUT:
            self.text = (self.text + event.text.replace("\n", " "))[:MAX_TEXT]
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for rect, cmd in self._hits:
                if rect.collidepoint(event.pos):
                    self._do(cmd)
                    break
            return True
        return False


def draw_width(text: str, size: int = 20) -> int:
    return font(size).size(text)[0]
