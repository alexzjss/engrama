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
        self._rects: list[pygame.Rect] = []

    def _layout(self, surface) -> None:
        r = panel_rect(surface)
        cols = max(1, (r.w - 28) // self.CELL[0])
        self._rects = []
        for i in range(len(vocab.FOOD_IDS)):
            x = r.x + 14 + (i % cols) * self.CELL[0]
            y = r.y + 50 + (i // cols) * self.CELL[1]
            self._rects.append(pygame.Rect(x, y, self.CELL[0] - 8, self.CELL[1] - 8))

    def draw(self, surface, snap) -> None:
        draw_frame(surface, i18n.t("ui.menu.food"))
        self._layout(surface)
        for i, (fid, rect) in enumerate(zip(vocab.FOOD_IDS, self._rects)):
            pygame.draw.rect(surface, (60, 56, 90) if i == self.sel else (42, 40, 62), rect, border_radius=6)
            icon = pygame.transform.scale(sprites.food_icon(fid), (40, 40))
            surface.blit(icon, icon.get_rect(midtop=(rect.centerx, rect.y + 6)))
            draw_text(surface, i18n.t(f"food.{fid}"), (rect.centerx, rect.bottom - 6), (230, 230, 240), 20, "midbottom")

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            for i, r in enumerate(self._rects):
                if r.collidepoint(event.pos):
                    self.on_pick(vocab.FOOD_IDS[i])
                    return True
            return True
        if event.type == pygame.KEYDOWN:
            n = len(vocab.FOOD_IDS)
            if event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self.sel = (self.sel + 1) % n
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                self.sel = (self.sel - 1) % n
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_pick(vocab.FOOD_IDS[self.sel])
            else:
                return False
            return True
        return False
