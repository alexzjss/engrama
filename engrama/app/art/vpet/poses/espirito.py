"""Poses of the espirito family (M14). Sheet ghost (0) and wraith (2): floating arms (child+).
Flame (1): wisp tail, arms from adult."""
O = -1


def arm(r):
    return {"rot": O * r, "alt": True}


def wisp(r, dx=0):
    return {"rot": r, "dx": dx, "px": True}


def sw(r):                       # same screen direction on both sides (stride / swing)
    return {"rot": O * r}


ARMS = {
    "idle": [{}, {"arm": arm(6)}],
    "walk": [{"arm": sw(14)}, {"arm": sw(4)}, {"arm": sw(-14)}, {"arm": sw(4)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-34)}, {"arm": sw(-26)}],
    "sleep": [{"arm": arm(-14)}, {"arm": arm(-18)}],
    "happy": [{"arm": arm(26)}, {"arm": arm(34)}],
    "sad": [{"arm": arm(-10)}, {"arm": arm(-14)}],
    "old": [{"arm": arm(-12)}, {"arm": arm(-12)}],
    "jump": [{"arm": arm(-10)}, {"arm": arm(28)}, {"arm": arm(36)}, {"arm": arm(22)}],
    "dance": [{"arm": sw(26)}, {"arm": sw(4)}, {"arm": sw(-26)}, {"arm": sw(4)}],
}

def fa(r):                         # flame arms rest raised: positive r lowers them towards horizontal
    return {"rot": r, "alt": True}


FLAME = {
    "idle": [{}, {"tail": wisp(8)}],
    "walk": [{"tail": wisp(12), "arm": sw(14)}, {"tail": wisp(0), "arm": fa(6)},
             {"tail": wisp(-12), "arm": sw(-14)}, {"tail": wisp(0), "arm": fa(6)}],
    "eat": [{"arm": sw(-18)}, {"arm": sw(-30), "tail": wisp(6)}, {"arm": sw(-24)}],
    "sleep": [{"tail": wisp(-14), "arm": fa(22)}, {"tail": wisp(-20), "arm": fa(28)}],
    "happy": [{"tail": wisp(10), "arm": fa(-6)}, {"tail": wisp(-10), "arm": fa(-12)}],
    "sad": [{"tail": wisp(-18), "arm": fa(26)}, {"tail": wisp(-24), "arm": fa(32)}],
    "old": [{"tail": wisp(-18), "arm": fa(26)}, {"tail": wisp(-18), "arm": fa(26)}],
    "jump": [{"arm": fa(20)}, {"tail": wisp(12), "arm": fa(-8)}, {"tail": wisp(-12), "arm": fa(-12)},
             {"tail": wisp(8), "arm": fa(0)}],
    "dance": [{"tail": wisp(14), "arm": sw(30)}, {"tail": wisp(0), "arm": fa(10)},
              {"tail": wisp(-14), "arm": sw(-30)}, {"tail": wisp(0), "arm": fa(10)}],
}

# sheet ghost: the arms are small hem corners, so the swings are larger
def _scaled(poses, k):
    return {a: [{r: {**v, "rot": v["rot"] * k} if "rot" in v else dict(v) for r, v in f.items()} for f in fr]
            for a, fr in poses.items()}


# wraith hands float near the bottom edge: droops stay tiny so they never leave the canvas
WRAITH = {**ARMS,
          "sleep": [{"arm": arm(-3)}, {"arm": arm(-4)}], "sad": [{"arm": arm(-3)}, {"arm": arm(-4)}],
          "old": [{"arm": arm(-4)}, {"arm": arm(-4)}], "eat": [{"arm": sw(-4)}, {"arm": sw(-10)}, {"arm": sw(-6)}],
          "jump": [{"arm": arm(-3)}, {"arm": arm(28)}, {"arm": arm(36)}, {"arm": arm(22)}]}

POSES: dict = {"espirito": ARMS, ("espirito", 2): WRAITH, ("espirito", 0): _scaled(ARMS, 2.2), ("espirito", 1): FLAME}
