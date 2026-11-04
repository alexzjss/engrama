"""Eyes and mouths as small pixel stamps, stamped per frame (bodies are rendered eyeless).

Eye styles: gem (dark oval + glints), sclera (white + pupil), slit (coloured iris + slit pupil), beady (small dot),
compound (big faceted), glow (light, no pupil), visor (one dark band with two light eyes), sleepy (gem + lid).
Overlays from the persona: brow "sharp" (fierce) and lid "calm".
"""
import numpy as np

from .core import OUT

WHITE = (252, 250, 242)
RED = (226, 44, 58)
TEAR = (120, 196, 255)
MOUTH_IN = (196, 64, 78)

# eye (w, h) per stage index
EYE_WH = {0: (3, 4), 1: (4, 5), 2: (4, 6), 3: (5, 6), 4: (5, 7)}
# style -> (dw, dh) size change
STYLE_DWH = {"beady": (-1, -2), "compound": (1, 0), "glow": (0, -1), "visor": (1, -2), "slit": (0, 0),
             "gem": (0, 0), "sclera": (0, 0), "sleepy": (0, 0)}


def _oval(w, h):
    m = np.ones((h, w), bool)
    if w >= 4 and h >= 4:
        for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
            m[y, x] = False
    return m


def eye_size(t, style, bump=0):
    w, h = EYE_WH[t]
    dw, dh = STYLE_DWH.get(style, (0, 0))
    return max(2, w + dw), max(2, h + dh + bump)


def eye_stamp(w, h, style, expr, red=False, brow=False):
    """Codes for the LEFT eye (inner side = right): 0 none, 1 dark, 2 white, 3 iris, 4 iris dark, 5 red,
    6 tear, 8 glow."""
    E = np.zeros((h + 2, w), np.int8)       # +2 rows for a tear below
    if expr in ("closed", "happy", "dead"):
        w2 = max(3, w)
        E = np.zeros((h + 2, w2), np.int8)
        y = max(1, h // 2)
        if expr == "closed":
            E[y, :] = 1
            E[y - 1, 0] = 1; E[y, 0] = 0; E[y - 1, w2 - 1] = 1; E[y, w2 - 1] = 0
        elif expr == "happy":
            E[y - 1, 1:w2 - 1] = 1
            E[y, 0] = 1; E[y, w2 - 1] = 1
        else:
            n = min(w2, h)
            o = (h - n) // 2
            for i in range(n):
                k = i * (w2 - 1) // max(1, n - 1)
                E[o + i, k] = 1; E[o + i, w2 - 1 - k] = 1
        return E
    m = _oval(w, h)
    pupil = 5 if red else 1
    if style == "visor":
        E[:h, :] = 1                       # the band; eyes are glowing slots inside
        E[1:h - 1, 1:w - 1] = 5 if red else 8
        if h >= 4:
            E[1, 1] = 2
    elif style == "glow":
        E[:h][m] = 1
        inner = np.zeros((h, w), bool); inner[1:h - 1, 1:w - 1] = True
        E[:h][inner & m] = 5 if red else 8
        E[1, 1] = 2
    elif style == "slit":
        E[:h][m] = 1
        inner = np.zeros((h, w), bool); inner[1:h - 1, 1:w - 1] = True
        E[:h][inner & m] = 5 if red else 3
        E[1:h - 1, w // 2] = 1             # slit pupil
        E[1, max(1, w // 2 - 1)] = 2
    elif style == "compound":
        E[:h][m] = 4
        for y in range(h):
            for x in range(w):
                if m[y, x] and (x + y) % 2 == 0:
                    E[y, x] = 5 if red else 3
        E[1, 1] = 2; E[1, 2 if w > 3 else 1] = 2
        if h >= 5:
            E[h - 2, w - 2] = 2
    elif style == "sclera" and w >= 4:
        E[:h][m] = 1
        inner = np.zeros((h, w), bool); inner[1:h - 1, 1:w - 1] = True
        E[:h][inner & m] = 2
        pw = max(1, w - 2 - (1 if w >= 5 else 0))
        E[2:h - 1, w - 1 - pw:w - 1] = pupil
        E[2, w - 2] = 2
    else:                                  # gem / beady / sleepy
        E[:h][m] = pupil
        E[0 if h <= 3 else 1, 1 if w >= 3 else 0] = 2
        if h >= 5:
            E[2, 1] = 2
        if h >= 6 and w >= 4:
            E[h - 2, w - 2] = 2 if not red else 1
        if style == "gem" and h >= 6 and w >= 5:
            E[h - 2, 1:w - 1][E[h - 2, 1:w - 1] == pupil] = 3
            E[h - 2, w - 2] = 2
    if (brow or expr == "angry") and h >= 4 and style != "visor":
        E[0, w // 2:] = 0
        E[1, w - 1] = 0
        E[1, w // 2:w - 1] = 1
    if (style == "sleepy" or expr == "sick") and style != "visor":
        lid = max(2, h // 2 if expr == "sick" else 2)
        E[:lid - 1, :] = 0
        E[lid - 1, :] = np.where(m[lid - 1], 1, 0)
    if expr == "sad":
        E[0, :] = 0
        E[1, :w // 2] = 0
        E[1, w // 2:] = np.where(m[1, w // 2:], 1, 0)
        E[h, 0] = 6; E[h + 1, 0] = 6
    return E


MOUTHS = {
    # rows; X dark, W white tooth, R mouth interior
    "smile": {4: ["X..X", ".XX."], 6: ["X....X", ".XXXX."]},
    "fang": {4: ["X..X", ".XXW"], 6: ["XXXXXX", ".W..W."]},
    "cat": {4: ["X.X.", ".X.X"], 6: ["X..X..", ".XX.XX"]},
    "wide": {4: ["XXXX"], 6: ["X....X", ".XXXX."]},
    "o": {4: [".XX.", "XRRX", ".XX."], 6: ["..XX..", ".XRRX.", "..XX.."]},
    "grille": {4: ["XXXX", "X.X.", "XXXX"], 6: ["XXXXXX", "X.X.X.", "XXXXXX"]},
    "line": {4: [".XX."], 6: [".XXXX."]},
    "open": {4: ["XXXX", "XRRX", ".XX."], 6: [".XXXX.", "XRRRRX", ".XXXX."]},
    "chew": {4: [".XX.", "X..X"], 6: [".XXXX.", "X....X"]},
    "frown": {4: [".XX.", "X..X"], 6: [".XXXX.", "X....X"]},
    "wavy": {4: ["X.X.", ".X.X"], 6: ["X.X.X.", ".X.X.X"]},
}


def stamp_face(a, face, eyes="normal", mouth="normal", tear=0):
    """face: dict(ex0, ey0, w, h, axis, style, red, brow, iris, iris2, glow, mx0, my0, mw, mouth)."""
    w, h = face["w"], face["h"]
    expr = {"normal": "open", "closed": "closed", "happy": "happy", "sad": "sad", "sick": "sick",
            "dead": "dead"}.get(eyes, "open")
    E = eye_stamp(w, h, face["style"], expr, face.get("red", False), face.get("brow", False))
    if tear == 0:
        E[E == 6] = 0
    elif tear == 1:
        E[h + 1][E[h + 1] == 6] = 0
    cols = {1: OUT, 2: WHITE, 3: face["iris"], 4: face["iris2"], 5: RED, 6: TEAR, 8: face["glow"]}
    N = a.shape[0]
    ex0, ey0, axis = face["ex0"], face["ey0"], face["axis"]
    if face["style"] == "visor" and expr in ("open", "sad", "sick"):   # band joins the two eyes
        for y in range(ey0, ey0 + h):
            for x in range(ex0 + w, axis - (ex0 + w) + 1):
                if 0 <= x < N and 0 <= y < N:
                    a[y, x, :3] = OUT; a[y, x, 3] = 255
    for (yy, xx), c in np.ndenumerate(E):
        if not c:
            continue
        for x in (ex0 + xx, axis - (ex0 + xx)):
            y = ey0 + yy
            if 0 <= x < N and 0 <= y < N:
                a[y, x, :3] = cols[c]; a[y, x, 3] = 255
    mk = face["mouth"] if mouth == "normal" else mouth
    if mk == "none" or face["mouth"] == "none" and mouth in ("normal", "line", "chew"):
        return a
    mw = face["mw"]
    rows = MOUTHS.get(mk, MOUTHS["smile"]).get(mw) or MOUTHS["smile"][mw]
    mc = {"X": OUT, "W": WHITE, "R": MOUTH_IN}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in mc:
                x, y = face["mx0"] + i, face["my0"] + j
                if 0 <= x < N and 0 <= y < N:
                    a[y, x, :3] = mc[ch]; a[y, x, 3] = 255
    return a
