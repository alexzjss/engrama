"""Body plans: 8 families x 3 sub-plans, each with its own skeleton and silhouette.

Every plan is a pure function of (genes, persona, stage index). Stage only scales proportions and grows the
features (horns, wings, fins, petals...), so a lineage keeps one body plan for life. 3/4 plans are drawn facing
left; gen.sprite flips them by the seed's `side`. Every plan names its torso "body" and its head "head" (markings
and accessories rely on that) and fills the anchors of `D`.
"""

from .aquatic import aquatico
from .bird import ave
from .beast import fera
from .dragon import draco
from .insect import inseto
from .machine import maquina
from .plant import planta
from .spirit import espirito

FAMILY_FN = dict(draco=draco, fera=fera, ave=ave, inseto=inseto, planta=planta, espirito=espirito,
                 aquatico=aquatico, maquina=maquina)
