"""Poses of the fera family (M14). Keys: "fera" (every plan) or ("fera", plan). Values: {anim: [pose per frame]}.

Authored for the unflipped creature. In the table a positive multiplier means droop for ear and tail (the
sign of the amplitude per plan takes care of the direction) and, for legs and arms, swing in the walk phase.
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


_T = {
    "idle": [{}, {"tail": -.5, "ear": -.3}],
    "walk": [{"leg": 1, "arm": -1, "tail": .5}, {"ear": .3}, {"leg": -1, "arm": 1, "tail": -.5}, {"ear": .3}],
    "eat": [{}, {"arm~": 1, "tail": .4}, {"arm~": .6, "tail": -.4}],
    "sleep": [{"leg~": .6, "arm~": .6, "tail": 1.4, "ear": .8}, {"leg~": .6, "arm~": .6, "tail": 1.6, "ear": .9}],
    "happy": [{"arm~": -1.4, "tail": -.8, "ear": -.4}, {"arm~": -1.8, "tail": -1.2, "ear": -.4}],
    "sad": [{"ear": 1, "tail": 1.2, "arm~": .4}, {"ear": 1.2, "tail": 1.5, "arm~": .4}],
    "old": [{"tail": 1.2}, {"tail": 1.2}],
    "jump": [{"leg~": .8, "arm~": .5, "tail": .5}, {"leg~": -1, "arm~": -1.5, "tail": -.8, "ear": .4},
             {"leg~": -1.3, "arm~": -1.8, "tail": -1, "ear": .6}, {"leg~": -.4, "arm~": -.6, "ear": .3}],
    "dance": [{"leg": .7, "arm": -1.2, "tail": .6}, {"ear": .3}, {"leg": -.7, "arm": 1.2, "tail": -.6}, {"ear": .3}],
}

POSES: dict = {
    ("fera", 0): _plan({"leg": 16, "tail": 16, "ear": 6}, {"leg"}, _T),
    ("fera", 1): _plan({"leg": 10, "tail": 16, "ear": 15, "arm": 14}, {"leg", "arm", "ear"}, _T),
    ("fera", 2): _plan({"leg": 14, "tail": -16, "ear": 20, "arm": 18}, {"leg", "arm", "ear"}, _T),
}
