"""Bottom toolbar: one visible button per panel, so nothing depends on knowing the function keys.

Icons are tiny procedural bitmaps (same spirit as the sprites: no image files). Hovering shows the panel name and its key."""
from __future__ import annotations
import pygame
from engrama.app import i18n
from engrama.app.ui.hud import draw_text, font

BTN = 28
GAP = 4
MARGIN = 10
# id -> (i18n key of the name, key label shown in the tooltip)
BUTTONS: tuple[tuple[str, str, str], ...] = (
    ("food", "ui.menu.food", "F4"), ("digital", "ui.menu.digital", "F1"), ("memories", "ui.memories.title", "F7"),
    ("mind", "ui.mind.title", "F2"), ("models", "ui.menu.models", "F5"), ("permissions", "ui.perm.title", "F8"),
    ("generations", "ui.menu.generations", "F10"), ("settings", "ui.menu.settings", "F6"), ("help", "ui.help.title", ""))

# 12x12 bitmaps: '#' main colour, '-' light fill, 'o' detail, '.' transparent
_ART: dict[str, tuple[tuple[tuple[int, int, int], ...], tuple[str, ...]]] = {
    "food": (((214, 70, 70), (240, 130, 120), (90, 170, 80)), (
        "......oo....", ".....oo.....", "..###.###...", ".####-####..", "####--#####.", "###--######.",
        "###########.", "###########.", ".#########..", ".#########..", "..###.###...", "............")),
    "digital": (((90, 200, 220), (200, 240, 250), (50, 110, 150)), (
        "............", ".##########.", ".#--------#.", ".#-o----o-#.", ".#--------#.", ".#--oooo--#.",
        ".#--------#.", ".##########.", ".....##.....", "...######...", "............", "............")),
    "memories": (((150, 110, 200), (245, 240, 230), (150, 140, 160)), (
        "............", ".####..####.", "#----##----#", "#-oo-##-oo-#", "#----##----#", "#-oo-##-oo-#",
        "#----##----#", "#-oo-##-oo-#", "#----##----#", ".####..####.", ".....##.....", "............")),
    "mind": (((240, 150, 190), (250, 205, 225), (190, 90, 140)), (
        "............", "...###.###..", "..#--o#---#.", ".#---o----#.", ".#-oo--oo-#.", ".#----o---#.",
        ".#-o--o-o-#.", "..#-oo---#..", "...##-###...", ".....#-#....", ".....###....", "............")),
    "models": (((250, 250, 245), (250, 250, 245), (70, 64, 90)), (
        "............", "..########..", ".#--------#.", "#----------#", "#--o--o--o-#", "#----------#",
        ".#--------#.", "..###--###..", ".....#-#....", ".....##.....", "............", "............")),
    "permissions": (((230, 230, 240), (250, 250, 250), (90, 150, 220)), (
        "............", "............", "...######...", ".##------##.", "#---oooo---#", "#--oo##oo--#",
        "#--oo##oo--#", "#---oooo---#", ".##------##.", "...######...", "............", "............")),
    "generations": (((200, 180, 140), (250, 240, 215), (230, 150, 90)), (
        "............", ".....##.....", "....#--#....", "...#----#...", "..#--oo--#..", "..#-o--o-#..",
        ".#--------#.", ".#-oo--oo-#.", ".#--------#.", "..#------#..", "...######...", "............")),
    "settings": (((190, 190, 205), (120, 120, 140), (0, 0, 0)), (
        "............", ".....##.....", "..#.####.#..", "..########..", ".###----###.", "####-..-####",
        "####-..-####", ".###----###.", "..########..", "..#.####.#..", ".....##.....", "............")),
    "help": (((250, 220, 110), (0, 0, 0), (0, 0, 0)), (
        "............", "...######...", "..##....##..", "..##....##..", "........##..", "......###...",
        ".....##.....", ".....##.....", "............", ".....##.....", ".....##.....", "............")),
}
_icons: dict[str, pygame.Surface] = {}


def icon(name: str) -> pygame.Surface:
    """The 24x24 icon of a toolbar button (cached)."""
    img = _icons.get(name)
    if img is None:
        cols, rows = _ART[name]
        small = pygame.Surface((12, 12), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    small.set_at((x, y), cols["#-o".index(ch)])
        img = _icons[name] = pygame.transform.scale(small, (24, 24))
    return img


class Toolbar:
    def __init__(self) -> None:
        self.hover: str | None = None
        self._rects: dict[str, pygame.Rect] = {}

    @property
    def width(self) -> int:
        """Horizontal space the buttons take at the bottom right (the chat field stops short of it)."""
        return len(BUTTONS) * (BTN + GAP)

    def layout(self, size: tuple[int, int]) -> None:
        w, h = size
        x = w - MARGIN - self.width + GAP
        self._rects = {}
        for bid, _k, _f in BUTTONS:
            self._rects[bid] = pygame.Rect(x, h - 36, BTN, BTN)
            x += BTN + GAP

    def hit(self, pos) -> str | None:
        for bid, r in self._rects.items():
            if r.collidepoint(pos):
                return bid
        return None

    def set_hover(self, pos) -> None:
        self.hover = self.hit(pos) if pos is not None else None

    def key(self, active: str | None) -> tuple:
        return (self.hover, active, i18n.get_lang())

    def draw(self, surface: pygame.Surface, active: str | None = None) -> None:
        self.layout(surface.get_size())
        for bid, r in self._rects.items():
            on = bid == active
            col = (84, 76, 132) if on else (58, 54, 86) if bid == self.hover else (36, 33, 50)
            pygame.draw.rect(surface, col, r, border_radius=6)
            pygame.draw.rect(surface, (150, 140, 210) if on or bid == self.hover else (80, 76, 110), r, 1, border_radius=6)
            surface.blit(icon(bid), icon(bid).get_rect(center=r.center))
        if self.hover in self._rects:
            self._tooltip(surface, self.hover)

    def _tooltip(self, surface: pygame.Surface, bid: str) -> None:
        name_key, fkey = next((k, f) for b, k, f in BUTTONS if b == bid)
        text = i18n.t(name_key) + (f"  ·  {fkey}" if fkey else "")
        r = self._rects[bid]
        tw = font(18).size(text)[0] + 14
        box = pygame.Rect(0, 0, tw, 22)
        box.midbottom = (r.centerx, r.y - 5)
        box.right = min(box.right, surface.get_width() - 6)
        pygame.draw.rect(surface, (24, 22, 34), box, border_radius=6)
        pygame.draw.rect(surface, (120, 110, 170), box, 1, border_radius=6)
        draw_text(surface, text, box.center, (235, 235, 245), 18, "center")
