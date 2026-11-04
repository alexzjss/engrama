"""Poses of the aquatico family (M14). Jellyfish (0): tentacles (fin, left/right alternate) + oral arm (fin 0).
Fish (1): fins and tail. Axolotl (2): head gills (ear), legs, tail, arms (child+)."""
O = -1


def alt(r):
    return {"rot": O * r, "alt": True}


def sw(r):                       # same screen direction on both sides (stride / swing)
    return {"rot": O * r}


def same(r):
    return {"rot": r}


JELLY = {
    "idle": [{}, {"fin": alt(6)}],
    "walk": [{"fin": sw(14)}, {"fin": sw(0)}, {"fin": sw(-14)}, {"fin": sw(0)}],
    "eat": [{"fin": alt(-10)}, {"fin": alt(-22)}, {"fin": alt(-14)}],
    "sleep": [{"fin": alt(-12)}, {"fin": alt(-16)}],
    "happy": [{"fin": alt(12)}, {"fin": alt(18)}],
    "sad": [{"fin": alt(-8)}, {"fin": alt(-12)}],
    "old": [{"fin": alt(-10)}, {"fin": alt(-10)}],
    "jump": [{"fin": alt(-12)}, {"fin": alt(20)}, {"fin": alt(30)}, {"fin": alt(16)}],
    "dance": [{"fin": sw(18)}, {"fin": sw(-6)}, {"fin": sw(-18)}, {"fin": sw(-6)}],
}

FISH = {
    "idle": [{}, {"fin": same(6), "tail": same(8)}],
    "walk": [{"fin": same(12), "tail": same(16)}, {"fin": same(0), "tail": same(0)},
             {"fin": same(-12), "tail": same(-16)}, {"fin": same(0), "tail": same(0)}],
    "eat": [{"fin": same(6)}, {"fin": same(-8), "tail": same(8)}, {"fin": same(6)}],
    "sleep": [{"fin": same(-10), "tail": same(-12)}, {"fin": same(-14), "tail": same(-16)}],
    "happy": [{"fin": same(14), "tail": same(14)}, {"fin": same(-14), "tail": same(-14)}],
    "sad": [{"fin": same(-10), "tail": same(-18)}, {"fin": same(-14), "tail": same(-22)}],
    "old": [{"fin": same(-10), "tail": same(-18)}, {"fin": same(-10), "tail": same(-18)}],
    "jump": [{"tail": same(-10)}, {"fin": same(16), "tail": same(16)}, {"fin": same(-16), "tail": same(-18)},
             {"fin": same(10), "tail": same(10)}],
    "dance": [{"fin": same(14), "tail": same(18)}, {"fin": same(0), "tail": same(0)},
              {"fin": same(-14), "tail": same(-18)}, {"fin": same(0), "tail": same(0)}],
}

AXOLOTL = {
    "idle": [{}, {"ear": alt(8), "tail": same(6)}],
    "walk": [{"ear": sw(12), "leg": sw(14), "arm": sw(-16), "tail": same(12)},
             {"leg": sw(0), "arm": sw(6), "tail": same(0)},
             {"ear": sw(-12), "leg": sw(-14), "arm": sw(16), "tail": same(-12)},
             {"leg": sw(0), "arm": sw(6), "tail": same(0)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-34), "ear": alt(8)}, {"arm": sw(-28)}],
    "sleep": [{"ear": alt(-10), "arm": alt(-12), "leg": alt(-6), "tail": same(-6)},
              {"ear": alt(-12), "arm": alt(-14), "leg": alt(-6), "tail": same(-8)}],
    "happy": [{"ear": alt(16), "arm": alt(32)}, {"ear": alt(26), "arm": alt(48), "tail": same(10)}],
    "sad": [{"ear": alt(-14), "arm": alt(-10), "tail": same(-14)}, {"ear": alt(-20), "arm": alt(-14), "tail": same(-20)}],
    "old": [{"ear": alt(-16), "tail": same(-18)}, {"ear": alt(-16), "tail": same(-18)}],
    "jump": [{"arm": alt(-12), "leg": alt(-6)}, {"arm": alt(40), "leg": alt(14), "ear": alt(14)},
             {"arm": alt(52), "leg": alt(18), "ear": alt(20)}, {"arm": alt(30), "leg": alt(8)}],
    "dance": [{"arm": sw(38), "leg": sw(12), "ear": sw(14), "tail": same(12)}, {"arm": sw(20)},
              {"arm": sw(-38), "leg": sw(-12), "ear": sw(-14), "tail": same(-12)}, {"arm": sw(20)}],
}

POSES: dict = {("aquatico", 0): JELLY, ("aquatico", 1): FISH, ("aquatico", 2): AXOLOTL}
