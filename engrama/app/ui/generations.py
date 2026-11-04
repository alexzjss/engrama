"""Generations panel (F10): past lives, newest last, with a miniature, time and cause in words.

`window.generations_provider` is duck-typed: records() -> list of objects with GenerationRecord fields
(n, lineage, seed, days, cause, ancestral) and delete_archive(n). The UI never imports services or the kernel.
"""
from __future__ import annotations
import pygame
from engrama.app import i18n
from engrama.app.art import sprites
from engrama.app.art.sprites import Look
from engrama.app.ui.hud import draw_text
from engrama.app.ui.menus import draw_frame

STAGE_BY_LINEAGE_LEN = ("baby", "child", "adult", "perfect", "final")
ROW_H = 60
TXT = (230, 230, 240)
DIM = (150, 150, 170)


def duration_key(days: float) -> str:
    if days < 7:
        return "ui.gen.dur.days"
    if days < 40:
        return "ui.gen.dur.weeks"
    if days < 75:
        return "ui.gen.dur.two_months"
    if days < 105:
        return "ui.gen.dur.three_months"
    return "ui.gen.dur.long"


def cause_key(cause: str) -> str:
    return f"ui.gen.cause.{cause}" if cause in ("old_age", "neglect") else "ui.gen.cause.unknown"


def branch_label(rec) -> str:
    lin = tuple(getattr(rec, "lineage", ()) or ())
    return i18n.t(f"branch.{lin[-1] if lin else 'base'}")


def miniature(rec) -> pygame.Surface:
    lin = tuple(getattr(rec, "lineage", ()) or ())
    look = Look.from_dict({"seed": rec.seed, "branch": lin[-1] if lin else "base", "lineage": list(lin)})
    stage = "final" if len(lin) >= 4 else STAGE_BY_LINEAGE_LEN[len(lin)]
    return sprites.frames(look, stage, "idle")[0]


class GenerationsPanel:
    def __init__(self, window) -> None:
        self.window = window
        self.sel = 0
        self.pending: int | None = None   # row index awaiting the second Delete
        self._recs: list = []
        self._gone: set[int] = set()
        self._rows: list[tuple[pygame.Rect, int]] = []

    @property
    def provider(self):
        return getattr(self.window, "generations_provider", None)

    def on_open(self) -> None:
        self.pending = None
        self._refresh()

    def on_close(self) -> None:
        self.pending = None

    def _refresh(self) -> None:
        p = self.provider
        try:
            self._recs = list(p.records()) if p is not None else []
        except Exception:
            self._recs = []
        self.sel = max(0, min(self.sel, len(self._recs) - 1))

    def _visible(self, r: pygame.Rect) -> int:
        return max(1, (r.h - 84) // ROW_H)

    def draw(self, surface, snap) -> None:
        r = draw_frame(surface, i18n.t("ui.gen.title"))
        self._rows = []
        dev = bool(getattr(self.window, "dev", False))
        if not self._recs:
            draw_text(surface, i18n.t("ui.gen.empty"), (r.centerx, r.centery), DIM, 22, "center")
            return
        vis = self._visible(r)
        start = max(0, min(self.sel - vis + 1, len(self._recs) - vis)) if self.sel >= vis else 0
        y = r.y + 50
        for i in range(start, min(len(self._recs), start + vis)):
            rec = self._recs[i]
            row = pygame.Rect(r.x + 14, y, r.w - 28, ROW_H - 6)
            self._rows.append((row, i))
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), row, border_radius=6)
            try:
                img = miniature(rec)
                surface.blit(img, img.get_rect(center=(row.x + 30, row.centery)))
            except Exception:
                pass
            x = row.x + 66
            gone = rec.n in self._gone
            head = f"{branch_label(rec)}  -  {i18n.t(duration_key(rec.days))}"
            if dev:
                head += f"   #{rec.n} {rec.days:.1f}d seed={rec.seed}"
            draw_text(surface, head, (x, row.y + 6), TXT, 22)
            line2 = i18n.t(cause_key(rec.cause))
            if getattr(rec, "ancestral", ()):
                line2 += "  -  " + i18n.t("ui.gen.ancestral")
            draw_text(surface, line2, (x, row.y + 28), DIM, 18)
            if gone:
                draw_text(surface, i18n.t("ui.gen.archive_gone"), (row.right - 8, row.y + 6), (240, 160, 120), 18, "topright")
            y += ROW_H
        if self.pending is not None:
            draw_text(surface, i18n.t("ui.gen.confirm"), (r.centerx, r.bottom - 12), (240, 160, 120), 20, "midbottom")
        else:
            draw_text(surface, i18n.t("ui.gen.delete"), (r.centerx, r.bottom - 12), DIM, 18, "midbottom")

    def _delete(self) -> None:
        if not (0 <= self.sel < len(self._recs)):
            return
        if self.pending != self.sel:
            self.pending = self.sel
            return
        self.pending = None
        n = self._recs[self.sel].n
        try:
            self.provider.delete_archive(n)
            self._gone.add(n)
        except Exception:
            pass

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for rect, i in self._rows:
                if rect.collidepoint(event.pos):
                    if i != self.sel:
                        self.pending = None
                    self.sel = i
                    break
            return True
        if event.type == pygame.KEYDOWN:
            n = len(self._recs)
            if event.key == pygame.K_DELETE:
                self._delete()
                return True
            if event.key in (pygame.K_DOWN, pygame.K_RIGHT) and n:
                self.sel, self.pending = (self.sel + 1) % n, None
            elif event.key in (pygame.K_UP, pygame.K_LEFT) and n:
                self.sel, self.pending = (self.sel - 1) % n, None
            else:
                self.pending = None
                return False
            return True
        return False
