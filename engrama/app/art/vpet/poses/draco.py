"""Poses of the draco family (M14). Keys: "draco" (every plan) or ("draco", plan). Values: {anim: [pose per frame]}.

Authored for the unflipped creature (head left, tail right): tail rot + = down, - = up.
"""


def _p(leg=0, arm=0, tail=0, wing=0, lalt=True, aalt=True, walt=False):
    """One pose from per-role rotations (degrees); roles at 0 are left at rest."""
    p = {}
    for role, rot, alt in (("leg", leg, lalt), ("arm", arm, aalt), ("tail", tail, False), ("wing", wing, walt)):
        if rot:
            p[role] = {"rot": rot, "alt": True} if alt else {"rot": rot}
    return p


def _plan(leg=0, arm=0, tail=0, wing=0, walt=False):
    """Animation set from the amplitude of each role: leg/arm swing, tail (+ = down), wing (+ = folded down)."""
    def p(l=0, a=0, t=0, w=0, **k):
        return _p(l * leg, a * arm, t * tail, w * wing, walt=walt, **k)
    return {
        "idle": [{}, p(t=-.5, w=-.15)],
        "walk": [p(1, -1, .6), p(), p(-1, 1, -.6), p()],
        "eat": [{}, p(a=1, t=.4, aalt=False), p(a=.6, t=-.4, aalt=False)],
        "sleep": [p(.5, .8, 1.4, 1, lalt=False, aalt=False), p(.5, .8, 1.6, 1, lalt=False, aalt=False)],
        "happy": [p(0, -1.4, -.8, -1, aalt=False), p(0, -1.8, -1.2, -1.4, aalt=False)],
        "sad": [p(0, .7, 1.1, .8, aalt=False), p(0, .7, 1.3, .9, aalt=False)],
        "old": [p(t=1.2), p(t=1.2)],
        "jump": [p(.8, .6, .6, .5, lalt=False, aalt=False), p(-1, -1.6, -.8, -1.2, lalt=False, aalt=False),
                 p(-1.2, -1.8, -1, -1.5, lalt=False, aalt=False), p(-.4, -.6, 0, -.4, lalt=False, aalt=False)],
        "dance": [p(.7, -1, .6, -.6), p(0, 0, 0, .3), p(-.7, 1, -.6, -.6), p(0, 0, 0, .3)],
    }


POSES: dict = {
    ("draco", 0): _plan(leg=16, tail=16, wing=14),
    ("draco", 1): _plan(leg=14, arm=18, tail=14, wing=14, walt=True),
    ("draco", 2): _plan(arm=14, tail=18),
}
