"""Chat box: text field, short history, speech bubble above the creature, LLM status line.

Never blocks: replies are read with `get_nowait()` only. `language` is duck-typed
(request(text), replies: queue.Queue, status); `valence_fn` is injected by the host.
"""
from __future__ import annotations
import queue
import re
from typing import Callable
import pygame
from engrama.app import i18n
from engrama.app.ui import hud

MAX_INPUT = 500
HISTORY = 4
BUBBLE_BASE = 4.0
BUBBLE_PER_WORD = 0.3
STATUS_POLL = 1.0
SCALE = 4
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")
_STATUS_KEYS = {"missing": "ui.ollama.missing", "loading": "ui.ollama.loading", "pulling": "ui.ollama.pulling"}


def strip_emoji(text: str) -> str:
    return _EMOJI.sub("", text or "")


def bubble_seconds(text: str) -> float:
    return BUBBLE_BASE + BUBBLE_PER_WORD * len(text.split())


_wrap = hud.wrap


class ChatBox:
    def __init__(self, language, post: Callable[[str, dict | None], None], growler,
                 valence_fn: Callable[[str], float] | None = None,
                 get_pitch: Callable[[], float] = lambda: 1.0) -> None:
        self.language, self.post, self.growler = language, post, growler
        self.valence_fn = valence_fn
        self.get_pitch = get_pitch
        self.text = ""
        self.composing = ""
        self.history: list[str] = []
        self.bubble = ""
        self.bubble_until = 0.0
        self._status = "missing"
        self._status_at = -1e9
        self.reserve_right = 0                      # px kept free at the right of the field (the toolbar lives there)
        self.status_rect = pygame.Rect(0, 0, 0, 0)  # where the LLM status line was last drawn (click target)
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    # --- input
    def handle_event(self, e: pygame.event.Event) -> bool:
        if e.type == pygame.TEXTINPUT:
            self.composing = ""
            self.text = (self.text + strip_emoji(e.text))[:MAX_INPUT * 2]
            return True
        if e.type == pygame.TEXTEDITING:
            self.composing = getattr(e, "text", "")
            return True
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if getattr(e, "mod", 0) & pygame.KMOD_SHIFT:
                    self.text += "\n"
                else:
                    self.send()
                return True
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
        return False

    def send(self) -> None:
        text = strip_emoji(self.text).strip()[:MAX_INPUT]
        self.text = self.composing = ""
        if not text:
            return
        self.history = (self.history + ["> " + text])[-HISTORY:]
        v = 0.0
        if self.valence_fn is not None:
            try:
                v = float(self.valence_fn(text))
            except Exception:
                v = 0.0
        self.post("message", {"valence": v})
        try:
            self.language.request(text)
        except Exception:
            pass

    # --- frame
    def poll(self, now: float) -> None:
        replies = getattr(self.language, "replies", None)
        while replies is not None:
            try:
                r = replies.get_nowait()
            except queue.Empty:
                break
            speech = strip_emoji(getattr(r, "text", "")).strip()
            if not speech:
                continue
            self.bubble, self.bubble_until = speech, now + bubble_seconds(speech)
            self.history = (self.history + [speech])[-HISTORY:]
            try:
                self.growler.growl(self.get_pitch(), "talk")
            except Exception:
                pass

    def status(self, now: float) -> str:
        if now - self._status_at >= STATUS_POLL or now < self._status_at:
            self._status_at = now
            try:
                self._status = str(self.language.status) if self.language is not None else "missing"
            except Exception:
                self._status = "missing"
        return self._status

    @property
    def busy(self) -> bool:
        """Attribute read each frame (cheap); duck-typed so any language object works."""
        try:
            return bool(getattr(self.language, "busy", False))
        except Exception:
            return False

    def quiet(self, now: float) -> bool:
        """Nothing animated or being typed: no visible bubble, no text, no "thinking" dots."""
        return not (self.bubble and now < self.bubble_until) and not self.text and not self.composing and not self.busy

    def status_line(self, now: float) -> str:
        key = _STATUS_KEYS.get(self.status(now))
        return i18n.t(key) if key else ""

    def draw(self, surface: pygame.Surface, creature_rect: pygame.Rect, now: float) -> None:
        """creature_rect is in low-res scene coordinates (scaled by SCALE onto the screen)."""
        self.poll(now)
        w, h = surface.get_size()
        if self.bubble and now < self.bubble_until:
            self._draw_bubble(surface, creature_rect)
        elif self.busy:
            self._draw_thinking(surface, creature_rect, now)
        field = pygame.Rect(10, h - 34, w - 20 - self.reserve_right, 24)
        pygame.draw.rect(surface, (30, 28, 40), field, border_radius=6)
        pygame.draw.rect(surface, (90, 90, 120), field, 1, border_radius=6)
        shown = self.text + self.composing
        if shown:
            last = shown.split("\n")[-1]
            while last and hud.font(20).size(last)[0] > field.w - 12:
                last = last[1:]
            hud.draw_text(surface, last, (field.x + 6, field.centery), (235, 235, 240), 20, "midleft")
        else:
            hud.draw_text(surface, i18n.t("ui.chat.placeholder"), (field.x + 6, field.centery),
                          (120, 120, 140), 20, "midleft")
        y = field.y - 16
        line = self.status_line(now)
        self.status_rect = pygame.Rect(0, 0, 0, 0)
        if line:
            missing = self._status == "missing"   # not an error: she babbles; the line doubles as a way into Models
            self.status_rect = hud.draw_text(surface, line, (field.x + 2, y), (170, 165, 195) if missing else (230, 190, 120), 16).inflate(8, 6)
            y -= 14
        live = self.bubble if self.bubble and now < self.bubble_until else None
        for item in reversed(self.history):
            if item == live:
                continue
            if y < 60:
                break
            hud.draw_text(surface, item, (field.x + 2, y), (150, 150, 170), 16)
            y -= 14

    def _draw_thinking(self, surface: pygame.Surface, creature_rect: pygame.Rect, now: float) -> None:
        sw, _ = surface.get_size()
        bw, bh = 44, 24
        known = creature_rect.w > 0
        cx = creature_rect.centerx * SCALE if known else sw // 2
        top = (creature_rect.y * SCALE if known else 200) - bh - 12
        box = pygame.Rect(0, max(50, top), bw, bh)
        box.centerx = max(bw // 2 + 4, min(sw - bw // 2 - 4, cx))
        pygame.draw.rect(surface, (250, 250, 245), box, border_radius=8)
        pygame.draw.polygon(surface, (250, 250, 245), [(box.centerx - 6, box.bottom),
                                                       (box.centerx + 6, box.bottom), (box.centerx, box.bottom + 8)])
        lit = int(now * 3) % 3
        for i in range(3):
            y = box.centery - (3 if i == lit else 0)
            pygame.draw.circle(surface, (40, 36, 50) if i == lit else (150, 150, 165), (box.x + 12 + i * 10, y), 3)

    def _draw_bubble(self, surface: pygame.Surface, creature_rect: pygame.Rect) -> None:
        sw, _ = surface.get_size()
        lines = _wrap(self.bubble, 20, min(260, sw - 40))
        f = hud.font(20)
        bw = max(f.size(ln)[0] for ln in lines) + 16
        bh = len(lines) * 18 + 12
        known = creature_rect.w > 0
        cx = creature_rect.centerx * SCALE if known else sw // 2
        top = (creature_rect.y * SCALE if known else 200) - bh - 12
        box = pygame.Rect(0, max(50, top), bw, bh)
        box.centerx = max(bw // 2 + 4, min(sw - bw // 2 - 4, cx))
        pygame.draw.rect(surface, (250, 250, 245), box, border_radius=8)
        pygame.draw.polygon(surface, (250, 250, 245), [(box.centerx - 6, box.bottom),
                                                       (box.centerx + 6, box.bottom), (box.centerx, box.bottom + 8)])
        for i, ln in enumerate(lines):
            hud.draw_text(surface, ln, (box.x + 8, box.y + 6 + i * 18), (40, 36, 50), 20)
