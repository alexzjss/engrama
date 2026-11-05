"""Poses of the maquina family (M14). Biped (0): bolts/antenna (ear/antenna), legs, arms. Tank (1): antennas,
arms from perfect (treads have no role). Drone (2): mast+rotor (antenna), arms from child."""
O = -1


def alt(r):
    return {"rot": O * r, "alt": True}


def sw(r):                       # same screen direction on both sides (stride / swing)
    return {"rot": O * r}


def same(r):
    return {"rot": r}


BIPED = {
    "idle": [{}, {"ear": alt(8), "antenna": same(6)}],
    "walk": [{"ear": sw(10), "antenna": same(8), "leg": sw(14), "arm": sw(-16)},
             {"leg": sw(0), "arm": sw(6)},
             {"ear": sw(-10), "antenna": same(-8), "leg": sw(-14), "arm": sw(16)},
             {"leg": sw(0), "arm": sw(6)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-34), "antenna": same(6)}, {"arm": sw(-28)}],
    "sleep": [{"ear": alt(-14), "antenna": same(-14), "arm": alt(-14), "leg": alt(-6)},
              {"ear": alt(-18), "antenna": same(-18), "arm": alt(-18), "leg": alt(-6)}],
    "happy": [{"ear": alt(14), "arm": alt(32)}, {"ear": alt(-14), "antenna": same(10), "arm": alt(48)}],
    "sad": [{"ear": alt(-14), "antenna": same(-20), "arm": alt(-10)},
            {"ear": alt(-20), "antenna": same(-26), "arm": alt(-14)}],
    "old": [{"ear": alt(-16), "antenna": same(-22)}, {"ear": alt(-16), "antenna": same(-22)}],
    "jump": [{"arm": alt(-12), "leg": alt(-6)}, {"arm": alt(40), "leg": alt(14), "ear": alt(12)},
             {"arm": alt(52), "leg": alt(18), "ear": alt(18)}, {"arm": alt(30), "leg": alt(8)}],
    "dance": [{"arm": sw(38), "leg": sw(12), "ear": sw(12), "antenna": same(10)}, {"arm": sw(20)},
              {"arm": sw(-38), "leg": sw(-12), "ear": sw(-12), "antenna": same(-10)}, {"arm": sw(20)}],
}

TANK = {
    "idle": [{}, {"antenna": alt(6)}],
    "walk": [{"antenna": sw(12), "arm": sw(-14)}, {"antenna": sw(0), "arm": sw(5)},
             {"antenna": sw(-12), "arm": sw(14)}, {"antenna": sw(0), "arm": sw(5)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-30), "antenna": alt(6)}, {"arm": sw(-24)}],
    "sleep": [{"antenna": alt(-14), "arm": alt(-14)}, {"antenna": alt(-18), "arm": alt(-18)}],
    "happy": [{"antenna": alt(14), "arm": alt(30)}, {"antenna": alt(-14), "arm": alt(44)}],
    "sad": [{"antenna": alt(-14), "arm": alt(-10)}, {"antenna": alt(-20), "arm": alt(-14)}],
    "old": [{"antenna": alt(-18), "arm": alt(-10)}, {"antenna": alt(-18), "arm": alt(-10)}],
    "jump": [{"antenna": alt(-8)}, {"antenna": alt(14), "arm": alt(38)}, {"antenna": alt(20), "arm": alt(50)},
             {"antenna": alt(10), "arm": alt(28)}],
    "dance": [{"antenna": sw(14), "arm": sw(36)}, {"arm": sw(18)}, {"antenna": sw(-14), "arm": sw(-36)},
              {"arm": sw(18)}],
}

DRONE = {
    "idle": [{}, {"antenna": same(6)}],
    "walk": [{"antenna": same(12), "arm": sw(-14)}, {"antenna": same(0), "arm": sw(5)},
             {"antenna": same(-12), "arm": sw(14)}, {"antenna": same(0), "arm": sw(5)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-30), "antenna": same(6)}, {"arm": sw(-24)}],
    "sleep": [{"antenna": same(-16), "arm": alt(-14)}, {"antenna": same(-20), "arm": alt(-18)}],
    "happy": [{"antenna": same(12), "arm": alt(30)}, {"antenna": same(-12), "arm": alt(44)}],
    "sad": [{"antenna": same(-18), "arm": alt(-10)}, {"antenna": same(-24), "arm": alt(-14)}],
    "old": [{"antenna": same(-20), "arm": alt(-10)}, {"antenna": same(-20), "arm": alt(-10)}],
    "jump": [{"antenna": same(-8)}, {"antenna": same(14), "arm": alt(38)}, {"antenna": same(-14), "arm": alt(50)},
             {"antenna": same(10), "arm": alt(28)}],
    "dance": [{"antenna": same(14), "arm": sw(36)}, {"arm": sw(18)}, {"antenna": same(-14), "arm": sw(-36)},
              {"arm": sw(18)}],
}

POSES: dict = {("maquina", 0): BIPED, ("maquina", 1): TANK, ("maquina", 2): DRONE}
