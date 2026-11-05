"""Poses of the planta family (M14). Keys: "planta" (every plan) or ("planta", plan). Values: {anim: [pose per frame]}.

Bulb (plan 0): crown sprout (antenna), legs, arms. Flower (1) and cactus (2): leaf / spine arms only (child+).
"""
O = -1     # sign of "rot" that swings a hanging arm outward (alt mirrors it on the other side)


def arm(r):                        # r > 0: outward on both sides
    return {"rot": O * r, "alt": True}


def swing(r):                      # both limbs move the same way on screen (stride / swing)
    return {"rot": O * r}


def leg(r, dx=0):
    return {"rot": O * r, "dx": dx, "alt": True}


def sprout(r, dy=0):
    return {"rot": r, "dy": dy, "px": True}


def scaled(poses, k, roles=None):
    """Copy of `poses` with every rot multiplied by k (tiny limbs need bigger swings to read)."""
    return {a: [{r: ({**v, "rot": v["rot"] * k} if "rot" in v else dict(v)) for r, v in f.items()
                 if roles is None or r in roles} for f in fr] for a, fr in poses.items()}


# arms only (flower, cactus; fallback for the whole family)
ARMS = {
    "idle": [{}, {"arm": arm(6)}],
    "walk": [{"arm": swing(18)}, {"arm": swing(8)}, {"arm": swing(-18)}, {"arm": swing(8)}],
    "eat": [{"arm": swing(-18)}, {"arm": swing(-34)}, {"arm": swing(-28)}],
    "sleep": [{"arm": arm(-14)}, {"arm": arm(-18)}],
    "happy": [{"arm": arm(32)}, {"arm": arm(48)}],
    "sad": [{"arm": arm(-10)}, {"arm": arm(-14)}],
    "old": [{"arm": arm(-12)}, {"arm": arm(-12)}],
    "jump": [{"arm": arm(-12)}, {"arm": arm(40)}, {"arm": arm(52)}, {"arm": arm(30)}],
    "dance": [{"arm": swing(38)}, {"arm": swing(20)}, {"arm": swing(-38)}, {"arm": swing(20)}],
}

BULB = {
    "idle": [{}, {"antenna": sprout(8)}],
    "walk": [{"antenna": sprout(10), "leg": swing(14), "arm": swing(-16)},
             {"antenna": sprout(0), "leg": swing(0), "arm": swing(6)},
             {"antenna": sprout(-10), "leg": swing(-14), "arm": swing(16)},
             {"antenna": sprout(0), "leg": swing(0), "arm": swing(6)}],
    "eat": [{"arm": swing(-18)}, {"arm": swing(-34), "antenna": sprout(6)}, {"arm": swing(-28)}],
    "sleep": [{"antenna": sprout(22), "arm": arm(-14), "leg": leg(-6)},
              {"antenna": sprout(30), "arm": arm(-18), "leg": leg(-6)}],
    "happy": [{"arm": arm(32), "antenna": sprout(0, -1)}, {"arm": arm(48), "antenna": sprout(10, -1)}],
    "sad": [{"antenna": sprout(24), "arm": arm(-10)}, {"antenna": sprout(30), "arm": arm(-14)}],
    "old": [{"antenna": sprout(26)}, {"antenna": sprout(26)}],
    "jump": [{"arm": arm(-12), "leg": leg(-6)}, {"arm": arm(40), "leg": leg(14)},
             {"arm": arm(52), "leg": leg(18), "antenna": sprout(0, -1)}, {"arm": arm(30), "leg": leg(8)}],
    "dance": [{"arm": swing(38), "leg": swing(12), "antenna": sprout(10)}, {"arm": swing(20), "antenna": sprout(0)},
              {"arm": swing(-38), "leg": swing(-12), "antenna": sprout(-10)}, {"arm": swing(20), "antenna": sprout(0)}],
}

# cactus arms rest flexed up: smaller raises, clearer droops
CACTUS = {**ARMS,
          "sleep": [{"arm": arm(-22)}, {"arm": arm(-28)}],
          "sad": [{"arm": arm(-26)}, {"arm": arm(-32)}],
          "old": [{"arm": arm(-28)}, {"arm": arm(-28)}],
          "happy": [{"arm": arm(14)}, {"arm": arm(22)}],
          "jump": [{"arm": arm(-24)}, {"arm": arm(18)}, {"arm": arm(24)}, {"arm": arm(10)}]}

# flower "arms" are the small leaves at the stem foot
FLOWER = scaled(ARMS, 1.7)

POSES: dict = {"planta": ARMS, ("planta", 0): BULB, ("planta", 1): FLOWER, ("planta", 2): CACTUS}
