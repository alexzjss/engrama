"""Poses of the ave family (M14). Keys: "ave" (every plan) or ("ave", plan). Values: {anim: [pose per frame]}.

Authored for the unflipped creature. Multipliers: tail/wing positive = down/folded. Paired wings use "alt", which on
the frontal plans (owl, flight) is a mirror-symmetric flap; the perched bird has a single wing.
"""


def _pose(amps, alts, spec):
    """One pose. spec = {role: multiplier of amps[role]}; a trailing "~" on the role forces both sides to move
    together, otherwise roles listed in `alts` get opposite phase on the far side."""
    p = {}
    for key, m in spec.items():
        role = key.rstrip("~")
        rot = round(m * amps.get(role, 0), 1)
        if not rot:
            continue
        p[role] = {"rot": rot, "alt": True} if role in alts and not key.endswith("~") else {"rot": rot}
    return p


def _plan(amps, alts, table):
    """Animation set: table = {anim: [spec per frame]} -> {anim: [pose per frame]}."""
    return {anim: [_pose(amps, alts, s) for s in specs] for anim, specs in table.items()}


_PERCH = {   # side view: tail, one leg, one wing
    "idle": [{}, {"tail": -.5, "wing": -.3}],
    "walk": [{"leg": 1, "tail": .5, "wing": -.3}, {"wing": .2}, {"leg": -1, "tail": -.5, "wing": -.3}, {"wing": .2}],
    "eat": [{}, {"tail": .4, "wing": -.4}, {"tail": -.4}],
    "sleep": [{"tail": 1.2, "wing": 1.2}, {"tail": 1.4, "wing": 1.2}],
    "happy": [{"tail": -.9, "wing": -1.6}, {"tail": -1.3, "wing": -2}],
    "sad": [{"tail": 1.2, "wing": 1}, {"tail": 1.5, "wing": 1.2}],
    "old": [{"tail": 1.2}, {"tail": 1.2}],
    "jump": [{"leg": .8, "tail": .5}, {"leg": -1, "tail": -.8, "wing": -1.6}, {"leg": -1.3, "tail": -1, "wing": -2},
             {"leg": -.4, "wing": -.6}],
    "dance": [{"leg": .8, "tail": .6, "wing": -.8}, {"wing": .2}, {"leg": -.8, "tail": -.6, "wing": -.8}, {"wing": .2}],
}
_OWL = {   # front view: tiny wings at the sides, two feet
    "idle": [{}, {"wing": -.3}],
    "walk": [{"leg": 1, "wing": -.6}, {}, {"leg": -1, "wing": -.6}, {}],
    "eat": [{}, {"wing": -.6}, {"wing": -.3}],
    "sleep": [{"wing": 1}, {"wing": 1.2}],
    "happy": [{"wing": -1.5}, {"wing": -2}],
    "sad": [{"wing": 1}, {"wing": 1.3}],
    "old": [{}, {}],
    "jump": [{"leg": .8, "wing": 0}, {"leg": -1, "wing": -1.8}, {"leg": -1.2, "wing": -2.2}, {"leg": -.4, "wing": -.8}],
    "dance": [{"leg": .8, "wing": -1.4}, {"wing": .3}, {"leg": -.8, "wing": -1.4}, {"wing": .3}],
}
_FLY = {   # front view in flight: both wings flap together, tail bulb sways
    "idle": [{}, {"wing": -.3, "tail": -.4}],
    "walk": [{"wing": -1.2, "tail": .5}, {"wing": .8}, {"wing": -1.2, "tail": -.5}, {"wing": .8}],
    "eat": [{}, {"wing": -.5, "tail": .4}, {"wing": -.2, "tail": -.4}],
    "sleep": [{"wing": 1.4, "tail": 1}, {"wing": 1.6, "tail": 1.2}],
    "happy": [{"wing": -1.5, "tail": -.8}, {"wing": 1, "tail": .8}],
    "sad": [{"wing": 1.3, "tail": 1}, {"wing": 1.5, "tail": 1.2}],
    "old": [{"tail": 1}, {"tail": 1}],
    "jump": [{"wing": 1, "tail": .5}, {"wing": -1.6, "tail": -.8}, {"wing": -1.8, "tail": -1}, {"wing": .6}],
    "dance": [{"wing": -1.4, "tail": .6}, {"wing": .8}, {"wing": -1.4, "tail": -.6}, {"wing": .8}],
}

POSES: dict = {
    ("ave", 0): _plan({"tail": 18, "leg": 10, "wing": 16}, set(), _PERCH),
    ("ave", 1): _plan({"leg": 8, "wing": 18}, {"leg", "wing"}, _OWL),
    ("ave", 2): _plan({"tail": 16, "wing": 22}, {"wing"}, _FLY),
}
