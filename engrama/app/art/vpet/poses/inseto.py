"""Poses of the inseto family (M14). Keys: "inseto" (every plan) or ("inseto", plan). Values: {anim: [pose per frame]}.

All three plans are frontal and mirror-symmetric: a role in `alts` moves both sides in mirror (spread / close, flap),
a role marked "~" in the table tilts both sides the same way (sway).
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


_BEETLE = {
    "idle": [{}, {"antenna~": .5}],
    "walk": [{"antenna~": .6, "leg": 1}, {"leg": .2}, {"antenna~": -.6, "leg": -1}, {"leg": .2}],
    "eat": [{}, {"antenna~": .6}, {"antenna~": -.6}],
    "sleep": [{"antenna": 1.2, "leg": .8}, {"antenna": 1.4, "leg": .8}],
    "happy": [{"antenna~": -1, "leg": -.8}, {"antenna~": 1, "leg": .8}],
    "sad": [{"antenna": 1.2}, {"antenna": 1.5}],
    "old": [{"antenna": 1}, {"antenna": 1}],
    "jump": [{"antenna": 1, "leg": .8}, {"antenna": -1, "leg": -1.2}, {"antenna": -1.3, "leg": -1.4}, {"leg": -.4}],
    "dance": [{"antenna~": 1, "leg": 1}, {"leg": .2}, {"antenna~": -1, "leg": -1}, {"leg": .2}],
}
_BEE = {
    "idle": [{}, {"antenna~": .5, "wing": -.3}],
    "walk": [{"antenna~": .6, "leg": 1, "wing": -.6}, {"wing": .4}, {"antenna~": -.6, "leg": -1, "wing": -.6},
             {"wing": .4}],
    "eat": [{}, {"arm": 1, "antenna~": .5}, {"arm": .6, "antenna~": -.5}],
    "sleep": [{"antenna": 1.2, "leg": .8, "arm": .8, "wing": 1}, {"antenna": 1.4, "leg": .8, "arm": .8, "wing": 1.1}],
    "happy": [{"antenna~": -1, "arm": -1.5, "wing": -1}, {"antenna~": 1, "arm": -1.9, "wing": 1}],
    "sad": [{"antenna": 1.2, "wing": 1}, {"antenna": 1.5, "wing": 1.2}],
    "old": [{"antenna": 1}, {"antenna": 1}],
    "jump": [{"leg": .8, "wing": .6}, {"leg": -1, "arm": -1.5, "wing": -1.2}, {"leg": -1.3, "arm": -1.8, "wing": 1.2},
             {"leg": -.4, "wing": -.6}],
    "dance": [{"antenna~": 1, "arm": -1.2, "leg": .8, "wing": -.8}, {"wing": .6},
              {"antenna~": -1, "arm": 1.2, "leg": -.8, "wing": -.8}, {"wing": .6}],
}
_MOTH = {
    "idle": [{}, {"antenna~": .5, "wing": -.3}],
    "walk": [{"antenna~": .6, "wing": -.5}, {"wing": 1}, {"antenna~": -.6, "wing": -.5}, {"wing": 1}],
    "eat": [{}, {"antenna~": .6, "wing": -.3}, {"antenna~": -.6}],
    "sleep": [{"antenna": 1.2, "wing": 1.4}, {"antenna": 1.4, "wing": 1.6}],
    "happy": [{"antenna~": -1, "wing": -.5}, {"antenna~": 1, "wing": 1}],
    "sad": [{"antenna": 1.2, "wing": 1.2}, {"antenna": 1.5, "wing": 1.4}],
    "old": [{"antenna": 1}, {"antenna": 1}],
    "jump": [{"wing": 1}, {"wing": -.5, "antenna": -1}, {"wing": 1.4, "antenna": -1.3}, {"wing": -.3}],
    "dance": [{"antenna~": 1, "wing": -.5}, {"wing": 1}, {"antenna~": -1, "wing": -.5}, {"wing": 1}],
}

POSES: dict = {
    ("inseto", 0): _plan({"antenna": 14, "leg": 14}, {"antenna", "leg"}, _BEETLE),
    ("inseto", 1): _plan({"antenna": 14, "arm": 14, "leg": 12, "wing": 14}, {"antenna", "arm", "leg", "wing"}, _BEE),
    ("inseto", 2): _plan({"antenna": 14, "wing": 18}, {"antenna", "wing"}, _MOTH),
}
