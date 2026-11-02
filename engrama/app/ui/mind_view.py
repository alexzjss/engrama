"""Mind View: the recipe graph, tick proposals, module costs and each module's viz, all from a Snapshot."""
from __future__ import annotations

import pygame

from engrama.app import i18n
from engrama.app.snapshot import ModuleView, Snapshot
from engrama.app.ui import viz_draw as vd
from engrama.app.ui.viz_draw import VizState, draw_text, draw_viz

_BOX_H = 30
_LINE = 13
_CELL_H = 150


def _family(name: str) -> str:
    return name.split(".", 1)[0]


def _dashed_rect(surface, rect, color) -> None:
    for x in range(rect.left, rect.right, 6):
        pygame.draw.line(surface, color, (x, rect.top), (min(x + 3, rect.right), rect.top))
        pygame.draw.line(surface, color, (x, rect.bottom - 1), (min(x + 3, rect.right), rect.bottom - 1))
    for y in range(rect.top, rect.bottom, 6):
        pygame.draw.line(surface, color, (rect.left, y), (rect.left, min(y + 3, rect.bottom)))
        pygame.draw.line(surface, color, (rect.right - 1, y), (rect.right - 1, min(y + 3, rect.bottom)))


def _arrow(surface, a, b, color) -> None:
    pygame.draw.line(surface, color, a, b, 1)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / n, dy / n
    for s in (1, -1):
        px, py = b[0] - 6 * ux - s * 3 * uy, b[1] - 6 * uy + s * 3 * ux
        pygame.draw.line(surface, color, b, (int(px), int(py)), 1)


class MindView:
    def __init__(self) -> None:
        self.state = VizState()

    def draw(self, surface: pygame.Surface, snap: Snapshot) -> None:
        try:
            self._draw(surface, snap)
        except Exception:   # a render glitch must never take the window down
            pass

    # ---- sections -----------------------------------------------------------------------------------

    def _draw(self, surface, snap: Snapshot) -> None:
        W, H = surface.get_size()
        surface.fill(vd.BG)
        y = 4
        y += draw_text(surface, f"{i18n.t('ui.mind.title')}  {snap.recipe_name} v{snap.recipe_version}"
                       f"  t={snap.t:.0f}s", (6, y), vd.ACCENT, 12) + 4
        y = self._graph(surface, snap, y, W) + 6
        y = self._proposals(surface, snap, y, W) + 6
        y = self._costs(surface, snap, y, W) + 6
        self._grid(surface, snap, y, W, H)

    def _graph(self, surface, snap, y, W) -> int:
        mods = snap.modules
        if not mods:
            return y
        bw, gap = 104, 10
        per_row = max(1, (W - 12 + gap) // (bw + gap))
        pos: dict[str, pygame.Rect] = {}
        for i, m in enumerate(mods):
            r, c = divmod(i, per_row)
            pos[m.name] = pygame.Rect(6 + c * (bw + gap), y + r * (_BOX_H + 22), bw, _BOX_H)
        rows = (len(mods) + per_row - 1) // per_row
        # arrows: writer -> reader, one per shared channel
        for w in mods:
            for rd in mods:
                if w is rd:
                    continue
                for ch in sorted(set(w.writes) & set(rd.reads)):
                    a, b = pos[w.name], pos[rd.name]
                    p0 = (a.centerx, a.bottom if b.centery > a.centery else a.top if b.centery < a.centery else a.centery)
                    p1 = (b.centerx, b.top if b.centery > a.centery else b.bottom if b.centery < a.centery else b.centery)
                    if a.centery == b.centery:
                        p0, p1 = (a.right, a.centery), (b.left, b.centery)
                        if a.x > b.x:
                            p0, p1 = (a.left, a.centery), (b.right, b.centery)
                    col = vd.DIM if (w.shadow or rd.shadow) else vd.GOOD
                    _arrow(surface, p0, p1, col)
        for m in mods:
            r = pos[m.name]
            pygame.draw.rect(surface, (34, 37, 46), r)
            if m.shadow:
                _dashed_rect(surface, r, vd.DIM)
            else:
                pygame.draw.rect(surface, vd.BORDER if not m.disabled else vd.BAD, r, 1)
            draw_text(surface, m.name, (r.x + 3, r.y + 2), vd.DIM if m.shadow else vd.FG, 10, clip=r)
            chans = ",".join(m.writes) or "-"
            draw_text(surface, ">" + chans, (r.x + 3, r.y + 15), vd.DIM, 9, clip=r)
        return y + rows * (_BOX_H + 22)

    def _proposals(self, surface, snap, y, W) -> int:
        y += draw_text(surface, "propostas", (6, y), vd.DIM, 10) + 1
        seen_winner = False
        for shadow, props in ((False, snap.proposals), (True, snap.shadow_proposals)):
            for p in props:
                is_win = (not shadow) and (not seen_winner) and p.action == snap.winner
                row = pygame.Rect(4, y, W - 8, _LINE)
                if is_win:
                    seen_winner = True
                    pygame.draw.rect(surface, (70, 60, 20), row)
                    pygame.draw.rect(surface, vd.ACCENT, row, 1)
                col = vd.ACCENT if is_win else (vd.DIM if shadow else vd.FG)
                mark = ">> " if is_win else ("~ " if shadow else "   ")
                draw_text(surface, f"{mark}{p.action:<12} {p.score:+.2f}  {p.reason}", (8, y), col, 10, clip=row)
                y += _LINE
        return y

    def _costs(self, surface, snap, y, W) -> int:
        y += draw_text(surface, "custo", (6, y), vd.DIM, 10) + 1
        for m in snap.modules:
            tag = ""
            if m.disabled:
                tag = " [desligado]"
            elif m.rate_factor < 1.0:
                tag = " [rebaixado]"
            col = vd.BAD if m.disabled else (vd.ACCENT if tag else (vd.DIM if m.shadow else vd.FG))
            draw_text(surface, f"{m.name:<20} {m.mean_ms:6.2f} ms{tag}", (8, y), col, 10, clip=pygame.Rect(0, y, W, _LINE))
            y += _LINE
        return y

    def _grid(self, surface, snap, y, W, H) -> None:
        fams: dict[str, list[ModuleView]] = {}
        for m in snap.modules:
            fams.setdefault(_family(m.name), []).append(m)
        for fam, ms in fams.items():
            if y >= H:
                break
            ms = sorted(ms, key=lambda m: m.shadow)   # live first, shadows beside it
            cw = max(60, (W - 8) // len(ms))
            for i, m in enumerate(ms):
                cell = pygame.Rect(4 + i * cw, y, cw - 4, _CELL_H)
                pygame.draw.rect(surface, vd.BORDER, cell, 1)
                vs = snap.viz.get(m.name, ())
                label = m.name + (" (sombra)" if m.shadow else "")
                draw_text(surface, label, (cell.x + 3, cell.y + 2), vd.DIM if m.shadow else vd.ACCENT, 10, clip=cell)
                inner = pygame.Rect(cell.x + 2, cell.y + 14, cell.w - 4, cell.h - 16)
                if not vs:
                    continue
                vh = inner.h // len(vs)
                for k, v in enumerate(vs):
                    draw_viz(surface, pygame.Rect(inner.x, inner.y + k * vh, inner.w, vh), v, self.state)
            y += _CELL_H + 4
