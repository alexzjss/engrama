"""Limb poses per family and body plan (M14). One module per family; anim.POSES merges them.

A pose is {role: {"rot": degrees, "dx": units, "dy": units, "alt": bool, "px": bool}}; see core.posed.
"""
from . import aquatico, ave, draco, espirito, fera, inseto, maquina, planta

POSES: dict = {}
for _m in (draco, fera, ave, inseto, planta, espirito, aquatico, maquina):
    POSES.update(_m.POSES)
