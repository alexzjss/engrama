"""Evolution branch choice: pure, deterministic, no mind imports.

Score per branch = weighted sum of inputs (t_* = trait 0..1, i_* = interest share,
sc = stage_care_mean, lc = life_care_mean, mx = highest trait, mi = highest interest).
Neglect branches never score; they win only through the neglect rule below.

  stage    branch       score
  child    brincalhao   2.0*t_soc
  child    curioso      2.0*t_cur
  child    sonhador     1.2*t_cri + 1.0*t_pac
  adult    companheiro  1.5*t_soc + 1.0*sc + 0.5*i_social + 0.3 if lineage[-1]=brincalhao
  adult    explorador   1.2*t_cur + 1.2*t_ind + 0.3*i_jogos + 0.3 if lineage[-1]=curioso
  adult    artista      1.5*t_cri + 1.5*i_arte + 0.3 if lineage[-1]=sonhador
  adult    tecnico      2.0*i_tecnologia + 1.2*i_trabalho + 0.3*t_cur
  perfect  guardiao     1.2*sc + 1.0*t_soc + 0.4 if lineage[-1]=companheiro
  perfect  sabio        1.2*t_pac + 1.2*t_cur + 0.4 if lineage[-1]=explorador
  perfect  virtuoso     1.0*t_cri + 1.5*i_arte + 0.6 if lineage[-1]=artista
  perfect  aventureiro  1.8*i_jogos + 1.0*t_ind
  final    lendario     4.0 only if lc >= 0.85 (else excluded)
  final    mestre       2.5*max(0, mx - 0.5)
  final    eco          2.0*mi
  neglect  arisco/sombrio/rebelde/sombra: win if stage_care_mean < NEGLECT_BRANCH_CARE,
           unless lineage[-1] is a neglect branch and stage_care_mean >= REDEEM_CARE.

Ties (within 1e-9) are broken by sha256 of "seed|stage|branch" (never Python hash()).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from engrama.balance import NEGLECT_BRANCH_CARE, REDEEM_CARE
from engrama.vocab import BRANCHES, INTEREST_KEYS, NEGLECT_BRANCHES, TRAIT_KEYS

LEGENDARY_LIFE_CARE = 0.85
_T = {k: i for i, k in enumerate(TRAIT_KEYS)}

BRANCH_NAMES: dict[str, tuple[str, str]] = {
    "base": ("Criatura", "Creature"),
    "brincalhao": ("Brincalhão", "Playful"),
    "curioso": ("Curioso", "Curious"),
    "sonhador": ("Sonhador", "Dreamy"),
    "arisco": ("Arisco", "Skittish"),
    "companheiro": ("Companheiro", "Companion"),
    "explorador": ("Explorador", "Explorer"),
    "artista": ("Artista", "Artist"),
    "tecnico": ("Técnico", "Tinkerer"),
    "sombrio": ("Sombrio", "Shadow"),
    "guardiao": ("Guardião", "Guardian"),
    "sabio": ("Sábio", "Sage"),
    "virtuoso": ("Virtuoso", "Virtuoso"),
    "aventureiro": ("Aventureiro", "Adventurer"),
    "rebelde": ("Rebelde", "Rebel"),
    "lendario": ("Lendário", "Legendary"),
    "mestre": ("Mestre", "Master"),
    "eco": ("Eco", "Echo"),
    "sombra": ("Sombra", "Umbra"),
}


@dataclass(frozen=True)
class BranchContext:
    stage: str                      # stage being entered (in BRANCH_STAGES)
    care_now: float                 # StageMachine.care_quality
    stage_care_mean: float          # mean care over the stage just finished
    life_care_mean: float           # mean care over the whole life
    traits: tuple[float, ...]       # TRAIT_KEYS order, 0..1
    interests: dict[str, float]     # INTEREST_KEYS -> share of perceived app time
    lineage: tuple[str, ...]        # branches already taken, oldest first


def _scores(c: BranchContext) -> dict[str, float]:
    def t(k: str) -> float:
        return float(c.traits[_T[k]])

    def i(k: str) -> float:
        return float(c.interests.get(k, 0.0))

    sc, lc = c.stage_care_mean, c.life_care_mean
    last = c.lineage[-1] if c.lineage else ""

    def b(name: str, v: float = 0.3) -> float:
        return v if last == name else 0.0

    mx = max(c.traits) if c.traits else 0.0
    mi = max((float(c.interests.get(k, 0.0)) for k in INTEREST_KEYS), default=0.0)
    s = c.stage
    if s == "child":
        return {
            "brincalhao": 2.0 * t("sociabilidade"),
            "curioso": 2.0 * t("curiosidade"),
            "sonhador": 1.2 * t("criatividade") + 1.0 * t("paciencia"),
        }
    if s == "adult":
        return {
            "companheiro": 1.5 * t("sociabilidade") + sc + 0.5 * i("social") + b("brincalhao"),
            "explorador": 1.2 * t("curiosidade") + 1.2 * t("independencia") + 0.3 * i("jogos") + b("curioso"),
            "artista": 1.5 * t("criatividade") + 1.5 * i("arte") + b("sonhador"),
            "tecnico": 2.0 * i("tecnologia") + 1.2 * i("trabalho") + 0.3 * t("curiosidade"),
        }
    if s == "perfect":
        return {
            "guardiao": 1.2 * sc + t("sociabilidade") + b("companheiro", 0.4),
            "sabio": 1.2 * t("paciencia") + 1.2 * t("curiosidade") + b("explorador", 0.4),
            "virtuoso": t("criatividade") + 1.5 * i("arte") + b("artista", 0.6),
            "aventureiro": 1.8 * i("jogos") + t("independencia"),
        }
    out = {"mestre": 2.5 * max(0.0, mx - 0.5), "eco": 2.0 * mi}
    if lc >= LEGENDARY_LIFE_CARE:
        out["lendario"] = 4.0
    return out


def _tie(seed: int, stage: str, branch: str) -> bytes:
    return hashlib.sha256(f"{seed}|{stage}|{branch}".encode()).digest()


def pick_branch(ctx: BranchContext, seed: int) -> str:
    if ctx.stage not in BRANCHES:
        raise ValueError(f"stage without branches: {ctx.stage!r}")
    neglect = next(b for b in BRANCHES[ctx.stage] if b in NEGLECT_BRANCHES)
    redeemed = bool(ctx.lineage) and ctx.lineage[-1] in NEGLECT_BRANCHES and ctx.stage_care_mean >= REDEEM_CARE
    if ctx.stage_care_mean < NEGLECT_BRANCH_CARE and not redeemed:
        return neglect
    scores = _scores(ctx)
    top = max(scores.values())
    tied = [b for b, v in scores.items() if v >= top - 1e-9]
    return min(tied, key=lambda b: _tie(seed, ctx.stage, b))


def branch_name(branch: str, lang: str) -> str:
    pt, en = BRANCH_NAMES.get(branch, BRANCH_NAMES["base"])
    return en if lang == "en" else pt


def derive_seed(seed: int, generation: int) -> int:
    h = hashlib.sha256(f"engrama-seed|{seed}|{generation}".encode()).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF
