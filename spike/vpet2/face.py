"""Eyes and mouths as small pixel stamps, stamped per frame (bodies are rendered eyeless)."""
import numpy as np

from .core import OUT

WHITE = (252, 250, 242)
RED = (226, 44, 58)
TEAR = (120, 196, 255)
MOUTH_IN = (196, 64, 78)

# eye (w, h) per stage index; the face scales with the creature
EYE_WH = {0: (3, 4), 1: (4, 5), 2: (4, 6), 3: (5, 6), 4: (5, 7)}


def _oval(w, h):
    m = np.ones((h, w), bool)
    if w >= 4 and h >= 5:
        for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
            m[y, x] = False
    return m


def eye_stamp(w, h, style, expr, red=False):
    """Codes for the LEFT eye (inner side = right): 0 none, 1 dark, 2 white, 3 iris, 5 red, 6 tear."""
    E = np.zeros((h + 2, w), np.int8)       # +2 rows for a tear below
    if expr == "closed":
        y = h // 2 + 1
        E[y, :] = 1
        E[y - 1, 0] = 1; E[y, 0] = 0
        E[y - 1, w - 1] = 1; E[y, w - 1] = 0
        return E
    if expr == "happy":
        y = h // 2
        E[y, 1:w - 1] = 1
        E[y + 1, 0] = 1; E[y + 1, w - 1] = 1
        if w >= 5:
            E[y + 2, 0] = 1; E[y + 2, w - 1] = 1; E[y + 1, 0] = 0; E[y + 1, w - 1] = 0
            E[y + 1, 1] = 1; E[y + 1, w - 2] = 1
        return E
    if expr == "dead":
        n = min(w, h)
        o = (h - n) // 2
        for i in range(n):
            E[o + i, i * (w - 1) // max(1, n - 1)] = 1
            E[o + i, (w - 1) - i * (w - 1) // max(1, n - 1)] = 1
        return E
    m = _oval(w, h)
    pupil = 5 if red else 1
    if style in ("sclera", "sharp") and w >= 4:
        E[:h][m] = 1
        inner = np.zeros((h, w), bool)
        inner[1:h - 1, 1:w - 1] = True
        inner &= m
        E[:h][inner] = 2
        pw = max(1, w - 2 - (1 if w >= 5 else 0))
        E[2:h - 1, w - 1 - pw:w - 1] = pupil if not red else 5
        E[2, w - 2] = 2                 # glint
    else:                                   # gem: dark oval with glints
        E[:h][m] = pupil
        E[1, 1] = 2
        if h >= 5:
            E[2, 1] = 2
        if h >= 6 and w >= 4:
            E[h - 2, w - 2] = 2 if not red else 1
        if style == "gem" and h >= 6 and w >= 5:
            E[h - 2, 1:w - 1][E[h - 2, 1:w - 1] == pupil] = 3   # iris band at the bottom
            E[h - 2, w - 2] = 2
    if style == "sharp" or expr == "angry":
        # brow slant: the inner-top corner is cut away (fierce look)
        E[0, w // 2:] = 0
        E[1, w - 1] = 0
        E[1, w // 2:w - 1] = 1
        if h >= 6:
            E[0, :w // 2] = 1
    if style == "calm" or expr == "sick":
        lid = 2 if expr != "sick" else h // 2
        lid = max(lid, 2)
        E[:lid - 1, :] = 0
        E[lid - 1, :] = np.where(m[lid - 1], 1, 0)
    if expr == "sad":
        # outer-top corner drops (worried), tear under the outer edge
        E[0, :] = 0
        E[1, :w // 2] = 0
        E[1, w // 2:] = np.where(m[1, w // 2:], 1, 0)
        E[2, 0] = 1 if m[2, 0] else 0
        E[h, 0] = 6; E[h + 1, 0] = 6
    return E


MOUTHS = {
    # rows; X dark, W white tooth, R mouth interior
    "smile": {3: ["X.X", ".X."], 4: ["X..X", ".XX."], 5: ["X...X", ".XXX."]},
    "fang": {3: ["XXX", "..W"], 4: ["X..X", ".XXW"], 5: ["XXXXX", ".W.W."]},
    "cat": {3: ["X.X", ".X."], 4: ["X.X.X"[:4], ".X.X"], 5: ["X.X.X", ".X.X."]},
    "line": {3: ["XXX"], 4: [".XX."], 5: [".XXX."]},
    "open": {3: ["XXX", "XRX", ".X."], 4: ["XXXX", "XRRX", ".XX."], 5: [".XXX.", "XRRRX", ".XXX."]},
    "chew": {3: ["X.X", ".X."], 4: [".XX.", "X..X"], 5: [".XXX.", "X...X"]},
    "frown": {3: [".X.", "X.X"], 4: [".XX.", "X..X"], 5: [".XXX.", "X...X"]},
    "wavy": {3: ["X.X", ".X."], 4: ["X.X.", ".X.X"], 5: ["X.X.X", ".X.X."]},
}


def stamp_face(a, face, eyes="normal", mouth="normal", tear=0):
    """face: dict(ecx, ey, w, h, style, red, mcx, my, mw, mouth, cx2, iris, lid) in pixel coords."""
    w, h = face["w"], face["h"]
    expr = {"normal": "open", "closed": "closed", "happy": "happy", "sad": "sad", "sick": "sick",
            "dead": "dead"}.get(eyes, "open")
    E = eye_stamp(w, h, face["style"], expr, face.get("red", False))
    if tear == 0:
        E[E == 6] = 0
    elif tear == 1:
        E[h + 1][E[h + 1] == 6] = 0
    cols = {1: OUT, 2: WHITE, 3: face["iris"], 5: RED, 6: TEAR}
    N = a.shape[0]
    ex0 = face["ex0"]            # left column of the left eye
    ey0 = face["ey0"]
    axis = face["axis"]          # mirror: col' = axis - col
    for (yy, xx), c in np.ndenumerate(E):
        if not c:
            continue
        for x in (ex0 + xx, axis - (ex0 + xx)):
            y = ey0 + yy
            if 0 <= x < N and 0 <= y < N:
                a[y, x, :3] = cols[c]; a[y, x, 3] = 255
    mk = face["mouth"] if mouth == "normal" else mouth
    if mk == "none":
        return a
    mw = face["mw"]
    rows = MOUTHS.get(mk, MOUTHS["smile"]).get(mw) or MOUTHS["smile"][mw]
    mx0 = face["mx0"]
    my0 = face["my0"]
    mc = {"X": OUT, "W": WHITE, "R": MOUTH_IN}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in mc:
                x, y = mx0 + i, my0 + j
                if 0 <= x < N and 0 <= y < N:
                    a[y, x, :3] = mc[ch]; a[y, x, 3] = 255
    return a
