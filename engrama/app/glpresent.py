"""Mostra uma pygame.Surface numa janela OpenGL com fundo transparente (M17, overlay no Wayland).

O SDL2 no Wayland não tem janela com alfa por pixel no modo software; com um contexto EGL com canal alfa (e
SDL_VIDEO_EGL_ALLOW_TRANSPARENCY=1) o compositor respeita o alfa. Só ctypes + libGL (GL 1.x fixo), sem PyOpenGL.
A cor-chave do overlay vira alfa 0 aqui; todo o resto do desenho continua igual (superfície offscreen).
"""
from __future__ import annotations

import ctypes
import ctypes.util

import pygame

_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TEXTURE_2D = 0x0DE1
_GL_RGBA = 0x1908
_GL_UNSIGNED_BYTE = 0x1401
_GL_TEXTURE_MIN_FILTER, _GL_TEXTURE_MAG_FILTER = 0x2801, 0x2800
_GL_NEAREST = 0x2600
_GL_QUADS = 0x0007
_GL_BLEND = 0x0BE2


def load_gl(find=ctypes.util.find_library, cdll=ctypes.CDLL):
    """libGL já com argtypes, ou None se não houver."""
    for name in (find("GL"), "libGL.so.1"):
        if not name:
            continue
        try:
            gl = cdll(name)
            c = ctypes
            sig = {
                "glViewport": [c.c_int] * 4, "glClearColor": [c.c_float] * 4, "glClear": [c.c_uint],
                "glEnable": [c.c_uint], "glDisable": [c.c_uint], "glGenTextures": [c.c_int, c.POINTER(c.c_uint)],
                "glBindTexture": [c.c_uint, c.c_uint], "glTexParameteri": [c.c_uint, c.c_uint, c.c_int],
                "glTexImage2D": [c.c_uint, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_uint, c.c_uint,
                                 c.c_char_p],
                "glTexSubImage2D": [c.c_uint, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_uint, c.c_uint,
                                    c.c_char_p],
                "glBegin": [c.c_uint], "glEnd": [], "glTexCoord2f": [c.c_float] * 2,
                "glVertex2f": [c.c_float] * 2, "glDeleteTextures": [c.c_int, c.POINTER(c.c_uint)],
            }
            for fn, args in sig.items():
                f = getattr(gl, fn)
                f.argtypes, f.restype = args, None
            return gl
        except (OSError, AttributeError):
            continue
    return None


_scratch: dict[tuple[int, int], tuple[None, pygame.Surface]] = {}


def rgba_bytes(surface: pygame.Surface, key: tuple[int, int, int]) -> bytes:
    """RGBA from the bottom row up (as GL wants it): the colour key becomes (0, 0, 0, 0), the rest is opaque.

    Done with blits (all in C): a colour-keyed surface blitted onto a cleared per-pixel-alpha surface leaves the key
    pixels untouched, so RGB is 0 wherever alpha is 0, which is what premultiplied-alpha compositors expect.
    The scratch surface is reused per size; the source gets the colour key set in place.
    """
    size = surface.get_size()
    pair = _scratch.get(size)
    if pair is None:
        if len(_scratch) > 8:
            _scratch.clear()
        pair = _scratch[size] = (None, pygame.Surface(size, pygame.SRCALPHA))
    _, out = pair
    if surface.get_colorkey() != (*key, 255):
        surface.set_colorkey(key)       # only affects the surface when it is used as a blit source
    out.fill((0, 0, 0, 0))
    out.blit(surface, (0, 0))
    return pygame.image.tobytes(out, "RGBA", True)


class GLPresenter:
    """Precisa de um contexto GL corrente (pygame.display.set_mode com OPENGL)."""

    def __init__(self, key: tuple[int, int, int], gl=None) -> None:
        self.key = key
        self.gl = gl if gl is not None else load_gl()
        self.tex = 0
        self.size = (0, 0)

    @property
    def ok(self) -> bool:
        return self.gl is not None

    def reset(self) -> None:
        """O contexto foi recriado (set_mode novo): a textura antiga morreu junto."""
        self.tex = 0
        self.size = (0, 0)

    def present(self, surface: pygame.Surface) -> None:
        gl = self.gl
        if gl is None:
            return
        w, h = surface.get_size()
        data = rgba_bytes(surface, self.key)
        gl.glViewport(0, 0, w, h)
        gl.glDisable(_GL_BLEND)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(_GL_COLOR_BUFFER_BIT)
        gl.glEnable(_GL_TEXTURE_2D)
        if not self.tex:
            t = ctypes.c_uint(0)
            gl.glGenTextures(1, ctypes.byref(t))
            self.tex = int(t.value)
        gl.glBindTexture(_GL_TEXTURE_2D, self.tex)
        if self.size != (w, h):
            gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MIN_FILTER, _GL_NEAREST)
            gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MAG_FILTER, _GL_NEAREST)
            gl.glTexImage2D(_GL_TEXTURE_2D, 0, _GL_RGBA, w, h, 0, _GL_RGBA, _GL_UNSIGNED_BYTE, data)
        else:
            gl.glTexSubImage2D(_GL_TEXTURE_2D, 0, 0, 0, w, h, _GL_RGBA, _GL_UNSIGNED_BYTE, data)
        gl.glBegin(_GL_QUADS)
        for tx, ty, vx, vy in ((0, 0, -1, -1), (1, 0, 1, -1), (1, 1, 1, 1), (0, 1, -1, 1)):
            gl.glTexCoord2f(tx, ty)
            gl.glVertex2f(vx, vy)
        gl.glEnd()
        self.size = (w, h)
