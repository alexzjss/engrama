# Engrama v2 — Plataforma + Mente padrão (M1+M2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a headless Engrama in which a deterministic body (kernel) and a mind made of swappable ML modules (wired by a TOML recipe) live 30 simulated days in under 2 minutes. Every experience is logged so modules can be replayed, run in shadow mode and compared. The default mind is: needs-driven drives, PAD affect, utility policy, contextual Q-learning, preferences, trait drift, and a temporal SNN that measures novelty and habituation.

**Architecture:** single process with a single-writer simulation loop. The `kernel` (body) publishes channels and observations onto a `Blackboard`. The `mind` scheduler runs modules at their own rates. An arbiter picks one action from the modules' proposals, and the kernel validates and executes it. Every tick becomes an `Experience` that is sent to learners and to the experience log. The `lab` package drives everything headless, with simulated users and metrics.

**Tech Stack:** Python 3.13, numpy, psutil, stdlib (`tomllib`, `sqlite3`, `json`, `argparse`), pytest. No UI and no LLM in this plan (those are M3/M4).

**Spec:** `docs/superpowers/specs/2026-10-31-engrama-arquitetura-v2.md`. Sections 3–6 and 9–10 are the binding ones.

## Global Constraints

- Python 3.13. Shared venv at `E:/Documentos/GitHub/digimon/.venv` (run `E:/Documentos/GitHub/digimon/.venv/Scripts/python -m pytest`).
- Core dependencies: numpy and psutil only. No pygame import anywhere in this plan.
- Nothing is written to drive C. Tests write only to `tmp_path`.
- Dependency rule, checked by `tests/test_architecture.py`:
  - `engrama.kernel` never imports `engrama.mind`, `engrama.modules`, `engrama.lab` or `engrama.services`.
  - `engrama.modules.*` imports only `engrama.mind`, `engrama.vocab`, `engrama.balance`, numpy and stdlib.
  - `engrama.mind` never imports `engrama.kernel` or `engrama.modules`. The registry resolves modules by dotted path string through importlib.
- Determinism: all randomness comes from `numpy.random.Generator` objects derived from the run seed (`np.random.default_rng(seed)`, with children created via `rng.spawn`). Same seed + recipe + profile → identical experience log.
- Initial traits: curiosidade 50, sociabilidade 40, paciencia 70, independencia 30, criatividade 50. ASCII keys, in the order given by `vocab.TRAIT_KEYS`.
- Needs are 0–100, where high = urge. Keys and order come from `vocab.NEED_KEYS`.
- Never use pickle. Arrays are stored with `np.savez` / `np.load(allow_pickle=False)`, everything else as JSON.
- Commits: conventional message as given in each task.
  - NO `Co-Authored-By` line, and no Claude/AI attribution anywhere (user rule; it overrides any harness default).
  - Never push.
- Code style: small focused modules, type hints, sparse comments, `from __future__ import annotations` not needed (3.13).

## Review Focus

1. **Long `dt` ticks.** Lab sims use `dt=60` sim-seconds per tick. Every rate (needs, affect decay, SNN) must scale correctly with `dt`, with no explosion or NaN. Tests run the kernel at dt=1 and dt=60 and compare needs within 1%.
2. **A crashing or slow module must never stop the creature.** The scheduler catches the exception, disables that module and logs it. A module that goes over its budget 5 ticks in a row is demoted to half rate. With no proposals, the kernel fallback policy acts.
3. **Shadow modules must never affect behavior.** A run with a shadow module produces the same action sequence as a run without it (same seed).
4. **Save → load → continue must be identical to an uninterrupted run.** The kernel state, every module's `state_dict` and the RNG states must all round-trip.
5. **SNN activity must stay bounded at every hidden size (32–160) and for several seeds.** This is the failure the v1 SNN had (saturation).

Each line is pinned by a test in the owning task: 1 → T3, 2 → T4, 3 → T11, 4 → T7/T8, 5 → T9.

---

## File structure

```
engrama/
  __init__.py
  vocab.py            shared vocabularies (needs, traits, actions, events, rewards, stages, foods)
  balance.py          every tunable number
  config.py           Config (data_dir on E:, recipe name, time_scale, permissions) — ported
  clock.py            SimClock — ported
  kernel/
    __init__.py
    needs.py          Needs (ported, without empolgacao: mood belongs to the mind)
    lifecycle.py      StageMachine (ported) + health stub
    genome.py         Genome (ported)
    foods.py          FOODS catalog (ported, without Tastes)
    actions.py        ActionSpec catalog, availability, effects
    rewards.py        RewardTracker: primitive reward signals per tick
    sensors.py        Observation dataclass + world-state from events
    fallback.py       rule policy used when the mind proposes nothing
    kernel.py         Kernel: ingest/step/execute/snapshot/state
  mind/
    __init__.py
    contracts.py      Channel, CHANNELS, Blackboard, Proposal, Experience, VizSpec, Module, reward_combine
    scheduler.py      Scheduler (rates, budgets, crash isolation, shadow namespace)
    arbiter.py        SoftmaxArbiter
    recipe.py         Recipe/ModuleSpec + load_recipe(path)
    registry.py       REGISTRY type-name -> dotted path; build(spec, ctx)
  modules/
    __init__.py
    drives/needs.py           NeedDrives
    affect/pad.py             PadAffect + pad_label()
    policy/utility.py         UtilityPolicy
    policy/qlearning.py       QLearningPolicy
    prefs/food.py             FoodPrefs
    traits/drift.py           TraitDrift
    temporal/snn.py           TemporalSNN
  services/
    __init__.py
    persistence.py    save_run/load_run, atomic writes, daily backups
  lab/
    __init__.py
    explog.py         ExperienceLog (SQLite, rotation, channel sampling) + read_log
    simuser.py        SimUser profiles
    runtime.py        Runtime: kernel+mind+log loop; run_days()
    metrics.py        compute_metrics(log rows) -> dict
    replay.py         replay_module(log, spec) -> series
    ope.py            ips_estimate(...)
    cli.py            `python -m engrama.lab` : sim | compare | replay | report
    __main__.py
recipes/
  minimal-v1.toml     drives + pad + utility
  default-v1.toml     minimal + qlearning + prefs + traits + snn
tests/                mirrors the package (tests/kernel, tests/mind, tests/modules/..., tests/lab)
tools/bench.py
```

**Execution order:** waves can run in parallel worktrees; their files are disjoint.

| Wave | Tasks | Notes |
|---|---|---|
| 0 | T1 | serial |
| A | T2, T4, T5, T6, T7 | parallel |
| B | T3 (after T2), T9, T10 (after T4) | parallel |
| C | T8 (after T3–T7) | serial |
| D | T11 (after T8) | serial |
| E | T12 | serial |

Only T3, T6, T9 and T10 append constants to `balance.py`. Each appends a block headed with its task number, and the controller resolves the trivial merges.

Old v1 code is **not** the base, but it can be ported. The `m1-m2` branch still holds it, and T1–T2 port named files with `git show m1-m2:<path>`. Nothing else from v1 is used.

---

### Task 1: Branch, scaffold, vocab, balance and the mind contracts

**Files:**
- Branch: `git switch -c v2 m1-m2`, then `git rm -r -q engrama tests` (v1 stays in branch m1-m2), then commit the v2 spec file `docs/superpowers/specs/2026-10-31-engrama-arquitetura-v2.md` and this plan together with the scaffold.
- Create: `engrama/__init__.py`, `engrama/vocab.py`, `engrama/balance.py`, `engrama/config.py`, `engrama/clock.py`, `engrama/mind/__init__.py`, `engrama/mind/contracts.py`, empty `__init__.py` for `kernel`, `modules` (+ each subfolder `drives affect policy prefs traits temporal`), `services`, `lab`.
- Modify: `pyproject.toml` (dependencies `["numpy", "psutil"]`; optional `ui = ["pygame-ce"]`, `dev = ["pytest"]`; keep the pytest pythonpath).
- Port: `config.py` from `git show m1-m2:engrama/core/config.py`; add the field `recipe: str = "default-v1"` and drop the `model`/`keep_alive` fields. `clock.py` from `m1-m2:engrama/core/clock.py` unchanged.
- Test: `tests/test_contracts.py`, `tests/test_architecture.py`, `tests/test_config.py`, `tests/test_clock.py` (port v1 tests for config/clock with `git show m1-m2:tests/core/...`, adjusting imports).

**Interfaces — Produces (exact, other tasks rely on these):**

`engrama/vocab.py`:
```python
NEED_KEYS = ("fome", "sono", "tedio", "carinho", "curiosidade", "apoio")
TRAIT_KEYS = ("curiosidade", "sociabilidade", "paciencia", "independencia", "criatividade")
INITIAL_TRAITS = {"curiosidade": 50.0, "sociabilidade": 40.0, "paciencia": 70.0, "independencia": 30.0, "criatividade": 50.0}
STAGES = ("egg", "baby", "child", "adult", "perfect", "final")
ACTIONS = ("idle", "wander", "play_alone", "sleep", "ask_attention", "explore", "show_something", "hide")
EVENT_KINDS = ("click", "pet", "message", "food", "user_active", "user_idle",
               "app_focus", "fullscreen_on", "fullscreen_off", "answered")
REWARD_KEYS = ("need_relief", "need_pain", "user_response", "ignored", "petting", "msg_valence", "novelty")
FOOD_IDS = ("carne", "fruta", "peixe", "bolinho", "pacote", "cookie", "bug", "cache", "byte", "ram")
```

`engrama/balance.py` holds these constants, verbatim. Later tasks only read it; T3/T6/T9/T10 may append at the end if a constant is missing, and must say so in their report.
```python
HOUR = 3600.0
NEED_RATES_PER_H = {"fome": 14.3, "sono": 6.25, "tedio": 66.7, "carinho": 25.0, "curiosidade": 33.3, "apoio": 0.0}
SLEEP_RECOVERY_PER_H = 25.0
STAGE_MIN_SECONDS = {"egg": 300.0, "baby": 36 * HOUR, "child": 7 * 24 * HOUR, "adult": 21 * 24 * HOUR, "perfect": 45 * 24 * HOUR}
CARE_MIN_TO_EVOLVE = 0.3
CARE_EMA_SECONDS = 6 * HOUR
EGG_HATCH_CLICKS = 5
OFFLINE_NEED_CAP = 70.0
DECISION_PERIOD = 5.0            # sim-seconds between action decisions (at least once per tick)
ASK_MIN_INTERVAL = 20 * 60.0
ASK_ANSWER_WINDOW = 120.0
TRAIT_MAX_DRIFT_PER_DAY = 2.0
REWARD_WEIGHTS = {"need_relief": 1.0, "need_pain": -1.0, "user_response": 1.0, "ignored": -0.3,
                  "petting": 0.4, "msg_valence": 0.5, "novelty": 0.2}
MODULE_DEFAULT_BUDGET_MS = 5.0
MODULE_OVERBUDGET_STRIKES = 5
PAD_HALF_LIFE_S = 30 * 60.0
SNN_HIDDEN_BY_STAGE = {"egg": 32, "baby": 32, "child": 64, "adult": 96, "perfect": 128, "final": 160}
EXPLOG_CHANNEL_SAMPLE_S = 600.0  # blackboard snapshot into the log at most every 10 sim-minutes
EXPLOG_MAX_ROWS = 2_000_000
```

`engrama/mind/contracts.py` is the shared contract. Write it exactly like this; docstrings may be added.
```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
import numpy as np
from engrama import balance as B
from engrama.vocab import NEED_KEYS, TRAIT_KEYS, ACTIONS, EVENT_KINDS, REWARD_KEYS, FOOD_IDS

@dataclass(frozen=True)
class Channel:
    name: str
    dim: int
    lo: float = -1.0
    hi: float = 1.0
    doc: str = ""

CHANNELS: dict[str, Channel] = {c.name: c for c in (
    Channel("body.needs", len(NEED_KEYS), 0, 1, "needs/100, NEED_KEYS order"),
    Channel("body.stage", 1, 0, 5, "index into STAGES"),
    Channel("body.asleep", 1, 0, 1),
    Channel("world.hour", 2, -1, 1, "sin, cos of 2*pi*hour/24"),
    Channel("world.user_active", 1, 0, 1),
    Channel("world.fullscreen", 1, 0, 1),
    Channel("drives", len(NEED_KEYS), 0, 1, "urgency per need"),
    Channel("affect.pad", 3, -1, 1, "pleasure, arousal, dominance"),
    Channel("traits", len(TRAIT_KEYS), 0, 1, "traits/100, TRAIT_KEYS order"),
    Channel("temporal.surprise", 1, 0, 1),
    Channel("temporal.familiarity", 1, 0, 1),
    Channel("temporal.expectation", len(EVENT_KINDS), 0, 1, "P(event kind next bin)"),
    Channel("prefs.food", len(FOOD_IDS), -1, 1),
)}

@dataclass(frozen=True)
class Observation:
    t: float
    kind: str                 # one of EVENT_KINDS
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Proposal:
    action: str               # one of ACTIONS
    score: float              # module-local scale; arbiter weights it
    reason: str               # human-readable, required, non-empty
    source: str = ""          # filled by the scheduler with module name

@dataclass(frozen=True)
class Experience:
    t: float
    dt: float
    events: tuple[Observation, ...]          # observations of this tick
    channels: dict[str, np.ndarray]          # copies, BEFORE the decision
    action: str                              # action executed during [t-dt, t]
    action_prob: float                       # arbiter probability of that action (1.0 if forced)
    rewards: dict[str, float]                # REWARD_KEYS -> value observed at t
    next_channels: dict[str, np.ndarray]     # copies, AFTER kernel step at t

VizKind = Literal["raster", "heatmap", "series", "bars", "pad3d", "table"]

@dataclass(frozen=True)
class VizSpec:
    kind: VizKind
    title: str
    data: Any

class Blackboard:
    """Typed channel store + this tick's events. Single writer: the simulation thread."""
    def __init__(self) -> None:
        self._v: dict[str, np.ndarray] = {}
        self.events: tuple[Observation, ...] = ()
        self.t: float = 0.0
        self.available_actions: tuple[str, ...] = ACTIONS
    def write(self, name: str, value) -> None: ...   # validates name in CHANNELS (or "shadow/<mod>/<name>"), dim, clips to [lo,hi], stores float64 copy; raises KeyError/ValueError
    def read(self, name: str) -> np.ndarray: ...     # copy; KeyError if never written
    def get(self, name: str, default=None): ...      # copy or default
    def has(self, name: str) -> bool: ...
    def snapshot(self) -> dict[str, np.ndarray]: ... # deep copy of all channels

class Module:
    name: str = ""                 # instance name, set by registry from recipe (default = type)
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    rate_hz: float = 1.0           # in SIM time; scheduler runs it at most once per tick
    budget_ms: float = B.MODULE_DEFAULT_BUDGET_MS
    def __init__(self, params: dict, rng: np.random.Generator) -> None:
        self.params = dict(params); self.rng = rng
    def step(self, bb: Blackboard, dt: float) -> None: ...
    def propose(self, bb: Blackboard) -> list[Proposal]: return []
    def learn(self, exp: Experience) -> None: ...
    def state_dict(self) -> dict: return {}
    def load_state_dict(self, d: dict) -> None: ...
    def viz(self) -> list[VizSpec]: return []

def reward_combine(rewards: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = B.REWARD_WEIGHTS if weights is None else weights
    return float(sum(w.get(k, 0.0) * rewards.get(k, 0.0) for k in REWARD_KEYS))
```

`state_dict` values: `np.ndarray`, `float`, `int`, `str`, `bool`, or a list/dict of those. Persistence (T7) splits arrays into npz and everything else into JSON.

- [ ] **Step 1:** Create the branch and remove the v1 tree, as listed in Files.
- [ ] **Step 2: Write failing tests** in `tests/test_contracts.py`:
  - `test_blackboard_write_clips_and_copies`: writing `[2.0, -1, 0.5, 0, 0, 0]` to `body.needs` reads back `[1, 0, .5, 0, 0, 0]`, and mutating the returned array does not change the stored one.
  - `test_blackboard_rejects_unknown_and_bad_dim`: `KeyError` on `"nope"`, `ValueError` on `body.needs` with dim 3.
  - `test_shadow_namespace_allowed`: `write("shadow/x/affect.pad", [0, 0, 0])` works and is validated against `affect.pad`.
  - `test_reward_combine_default_weights`: `{"need_relief": 1, "ignored": 1}` → `0.7`.
  - `test_vocab_sizes`: `len(ACTIONS) == 8`, `len(EVENT_KINDS) == 10`, `len(FOOD_IDS) == 10`.
- [ ] **Step 3: Write `tests/test_architecture.py`.** It walks `engrama/**/*.py`, parses imports with `ast`, and asserts the dependency rule from Global Constraints. Packages that don't exist yet are skipped, so it passes from day one and guards later tasks.
- [ ] **Step 4:** Run `pytest tests -q`, expected FAIL. Implement. Run again, expected PASS.
- [ ] **Step 5:** Commit:
  ```bash
  git add -A engrama tests pyproject.toml docs/superpowers/specs/2026-10-31-engrama-arquitetura-v2.md docs/superpowers/plans/2026-10-31-engrama-v2-plataforma.md
  git commit -m "feat(v2): scaffold, vocab, balance and mind contracts"
  ```

---

### Task 2: Kernel body state (port)

**Files:**
- Create: `engrama/kernel/needs.py`, `lifecycle.py`, `genome.py`, `foods.py`.
- Test: `tests/kernel/test_needs.py`, `test_lifecycle.py`, `test_genome.py`, `test_foods.py`.

**Port sources:** `git show m1-m2:engrama/life/{needs,stages,genome,foods}.py` and their tests in `m1-m2:tests/life/`.

**Changes from v1:**
- `Needs`: remove `empolgacao` and everything about mood. Imports become `engrama.balance` and `engrama.vocab`. Keep `decay(dt, awake, interacting)`, `apply(delta)`, `top(n, threshold)`, `mean()`, `to_dict()` / `from_dict()`. Add `as_vector() -> np.ndarray` (values/100 in NEED_KEYS order).
- `StageMachine` goes to `lifecycle.py` unchanged. Add `stage_index` (property, index in STAGES), plus `class Health` with `sick: bool = False` and `update(dt, needs_mean)`. In M1, `update` is a no-op stub that always stays False, with `to_dict` / `from_dict`. M6 fills it in.
- `Genome`: unchanged (seed-based; uses `random.Random(seed)`; this is the one allowed stdlib RNG because the visual genome must match v1 seeds).
- `foods.py`: keep `Food` and `FOODS` only. Drop `Tastes`, `verdict` and the Traits import (preferences are now the `prefs.food` module, T10). Assert `tuple(FOODS) == FOOD_IDS`.

- [ ] Step 1: port the tests, adjust imports and delete the Tastes/empolgacao tests. Add `test_needs_vector_order` and `test_food_ids_match_vocab`. Run them: FAIL.
- [ ] Step 2: port the code with the changes above. Run them: PASS.
- [ ] Step 3: commit `feat(kernel): needs, lifecycle, genome and food catalog`.

---

### Task 3: Kernel actions, sensors, rewards and the Kernel facade

**Depends on:** T2.

**Files:**
- Create: `engrama/kernel/actions.py`, `sensors.py`, `rewards.py`, `fallback.py`, `kernel.py`.
- Test: `tests/kernel/test_actions.py`, `test_rewards.py`, `test_kernel.py`.

**Interfaces — Produces:**
```python
# sensors.py — kernel-side Observation is the same shape; kernel must not import mind,
# so define an identical frozen dataclass here and lab/runtime converts by field copy.
@dataclass(frozen=True)
class Obs: t: float; kind: str; data: dict

@dataclass
class WorldState:
    user_active: bool = False; fullscreen: bool = False; last_app: str = ""
    seen_apps: set[str] = field(default_factory=set)
    def apply(self, obs: Obs) -> bool: ...   # updates; returns True if the obs is novel (new app category first seen)

# actions.py
@dataclass(frozen=True)
class ActionSpec:
    name: str; duration_s: float; min_stage: str
    effects_per_h: dict[str, float]          # need deltas per sim-hour while running (negative = relieves)
ACTION_SPECS: dict[str, ActionSpec]          # one per vocab.ACTIONS
def available(stage: str, asleep: bool, fullscreen: bool) -> tuple[str, ...]
#   egg -> ("idle",); fullscreen -> ("hide",); asleep -> ("sleep",) unless sono < 20 then normal set;
#   otherwise every action whose min_stage <= stage, excluding "hide".

# rewards.py
class RewardTracker:
    def __init__(self) -> None
    def on_action_started(self, action: str, t: float) -> None   # remembers ask_attention time
    def on_events(self, events: list[Obs], t: float) -> None      # answered/message/pet/click within ASK_ANSWER_WINDOW -> user_response=1
    def on_needs(self, before: np.ndarray, after: np.ndarray, dt: float) -> None  # relief = sum of drops of needs that were >= 0.5 before; pain = sum of rises crossing 0.8
    def on_novel(self) -> None
    def collect(self, t: float) -> dict[str, float]   # all REWARD_KEYS present; resets; "ignored"=1 when an ask window expired unanswered

# fallback.py
def fallback_action(needs: dict[str, float], available: tuple[str, ...]) -> str
#   sono>=80 and "sleep" in available -> "sleep"; tedio>=60 -> "play_alone"; else first of ("idle","hide") in available

# kernel.py
class Kernel:
    def __init__(self, seed: int, now: float = 0.0) -> None      # fresh egg, genome from seed
    def ingest(self, events: list[Obs]) -> None                  # queued for next step
    def step(self, dt: float) -> tuple[list[Obs], dict[str, float]]
        # advances needs (awake/asleep, current action effects), lifecycle, world; applies food events
        # (FOODS effects; egg ignores food), pet/click reduce carinho by 8, clicks hatch egg after
        # EGG_HATCH_CLICKS; returns (events processed this step, rewards collected at the new t)
    def channels(self) -> dict[str, np.ndarray]   # body.needs, body.stage, body.asleep, world.hour, world.user_active, world.fullscreen
    def available_actions(self) -> tuple[str, ...]
    def execute(self, proposed: str | None) -> tuple[str, bool]
        # returns (action actually running, forced). None or unavailable -> fallback_action, forced=True.
        # An action keeps running until its duration elapses unless a forced change (fullscreen, wake) happens;
        # while running, execute() returns the running action with forced=False only when it equals proposed.
    def offline_catchup(self, seconds: float) -> None   # needs rise but capped at OFFLINE_NEED_CAP; no stage advance beyond one
    @property t, stage, asleep, genome
    def state_dict(self) -> dict ; @classmethod from_state_dict(cls, d) -> "Kernel"   # JSON-safe
```
`world.hour` uses `t` as seconds from the local midnight of the run start. `Kernel(seed, now=hour*3600)` starts at that hour.

- [ ] **Step 1: Write failing tests:**
  - `test_dt_invariance`: two kernels with the same seed, run 6 sim-hours (one at dt=1, one at dt=60), with no events and the action fixed to `idle`. Needs are equal within 1%. **(Review Focus 1)**
  - `test_egg_only_idle_and_hatch_after_clicks`.
  - `test_fullscreen_forces_hide`: forced is True and `available == ("hide",)`.
  - `test_unavailable_proposal_uses_fallback`.
  - `test_food_relieves_fome`: `carne` lowers fome by 40.
  - `test_need_relief_reward_on_food`.
  - `test_ask_answered_within_window_gives_user_response`.
  - `test_ask_unanswered_gives_ignored_once`.
  - `test_new_app_category_is_novel`.
  - `test_offline_catchup_caps_needs`.
  - `test_state_roundtrip_continues_identically`: run 1000 ticks, save state, then run 500 more ticks on the original and on the loaded copy. Channels must be equal.
  - `test_no_nan_long_dt`: dt=3600 for 24 ticks gives finite values.
- [ ] **Step 2:** run them, expect FAIL. Implement, run again, expect PASS.
- [ ] **Step 3:** commit `feat(kernel): actions, sensors, primitive rewards and kernel facade`.

---

### Task 4: Mind runtime — scheduler, arbiter, recipe, registry

**Depends on:** T1 only. Tests use small fake modules defined inside the test files.

**Files:**
- Create: `engrama/mind/scheduler.py`, `arbiter.py`, `recipe.py`, `registry.py`.
- Test: `tests/mind/test_scheduler.py`, `test_arbiter.py`, `test_recipe.py`.

**Interfaces — Produces:**
```python
# recipe.py
@dataclass(frozen=True)
class ModuleSpec: type: str; name: str; params: dict; weight: float = 1.0; shadow: bool = False
@dataclass(frozen=True)
class Recipe: name: str; version: int; modules: tuple[ModuleSpec, ...]; arbiter: dict
def load_recipe(path: Path) -> Recipe
#   TOML: [recipe] name, version; [[module]] type=..., name? (default=type), weight?, any other keys -> params;
#   [[shadow]] same keys -> shadow=True; [arbiter] temperature?=1.0, trait_temperature?=true.
#   Errors: duplicate names, unknown keys in [recipe] -> ValueError with message naming the key.

# registry.py
REGISTRY: dict[str, str] = {
  "drives.needs": "engrama.modules.drives.needs:NeedDrives",
  "affect.pad": "engrama.modules.affect.pad:PadAffect",
  "policy.utility": "engrama.modules.policy.utility:UtilityPolicy",
  "policy.qlearning": "engrama.modules.policy.qlearning:QLearningPolicy",
  "prefs.food": "engrama.modules.prefs.food:FoodPrefs",
  "traits.drift": "engrama.modules.traits.drift:TraitDrift",
  "temporal.snn": "engrama.modules.temporal.snn:TemporalSNN",
}
def register(type_name: str, dotted: str) -> None
def build(spec: ModuleSpec, rng: np.random.Generator) -> Module   # importlib; sets .name; unknown type -> KeyError listing known types;
                                                                 # ImportError of an optional dep -> ModuleUnavailable (custom exception)

# scheduler.py
@dataclass
class ModuleStatus: name: str; enabled: bool = True; rate_factor: float = 1.0; strikes: int = 0
                    last_ms: float = 0.0; mean_ms: float = 0.0; error: str = ""; shadow: bool = False
class Scheduler:
    def __init__(self, modules: list[Module], specs: list[ModuleSpec]) -> None
    def step(self, bb: Blackboard, dt: float) -> None
        # for each enabled module in recipe order: accumulate dt; run step() if acc >= 1/(rate_hz*rate_factor)
        # passing the accumulated dt (then acc=0). Shadow modules get a ShadowBlackboard view whose
        # write(name) redirects to "shadow/<module>/<name>" and whose read(name) prefers its own shadow copy.
        # Exceptions: disable module, store repr in status.error. Timing via time.perf_counter;
        # > budget_ms for MODULE_OVERBUDGET_STRIKES consecutive runs -> rate_factor *= 0.5, strikes=0.
    def proposals(self, bb) -> tuple[list[Proposal], list[Proposal]]   # (live, shadow), source=module name; exceptions disable
    def learn(self, exp: Experience) -> None                           # all enabled modules incl. shadow; exceptions disable
    def status(self) -> list[ModuleStatus]
    def modules(self) -> dict[str, Module]

# arbiter.py
class SoftmaxArbiter:
    def __init__(self, weights: dict[str, float], temperature: float = 1.0, trait_temperature: bool = True) -> None
    def choose(self, proposals: list[Proposal], available: tuple[str, ...], bb: Blackboard,
               rng: np.random.Generator) -> tuple[str | None, float, dict[str, float]]
        # score[a] = sum(weight[source] * p.score) over proposals for a in available; actions with no
        # proposal are excluded. T = temperature * (0.5 + traits[curiosidade]) if trait_temperature and
        # bb.has("traits") else temperature. Returns (action, prob, full prob dict); (None, 1.0, {}) if empty.
```

- [ ] **Step 1: Write failing tests:**
  - `test_rate_respected`: a module with rate 0.1 Hz runs 6 times over 60 ticks of dt=1, and receives dt=10 each time.
  - `test_rate_with_long_dt`: rate 1 Hz with dt=60 runs every tick and receives dt=60.
  - `test_crashing_module_disabled_others_continue` **(Review Focus 2)**.
  - `test_overbudget_demoted`: a fake module that sleeps 10 ms with budget 1 ms ends at `rate_factor == 0.5` after 5 runs.
  - `test_shadow_writes_namespaced`: a shadow module writing `affect.pad` leaves the live `affect.pad` untouched.
  - `test_arbiter_deterministic_with_seed`.
  - `test_arbiter_respects_available_and_weights`.
  - `test_arbiter_empty_returns_none`.
  - `test_load_recipe_ok_and_errors` (write TOML to `tmp_path`).
  - `test_build_unknown_type_lists_known`.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(mind): scheduler, softmax arbiter, recipes and registry`.

---

### Task 5: Experience log

**Depends on:** T1.

**Files:**
- Create: `engrama/lab/explog.py`.
- Test: `tests/lab/test_explog.py`.

**Interfaces — Produces:**
```python
class ExperienceLog:
    def __init__(self, path: Path, run_id: str, recipe: str, seed: int,
                 sample_s: float = B.EXPLOG_CHANNEL_SAMPLE_S, max_rows: int = B.EXPLOG_MAX_ROWS) -> None
    def write(self, exp: Experience, proposals: list[Proposal], shadow: list[Proposal]) -> None
        # tables: runs(run_id, recipe, seed, started), ticks(run_id, t, dt, action, prob, rewards_json,
        #   events_json, proposals_json, shadow_json), channels(run_id, t, name, blob float32 bytes).
        # channels written only if t - last_sample >= sample_s OR exp.events non-empty (events always keep context).
        # Privacy: events with data["private"] True are stored with data replaced by {"private": True}.
        # Rotation: when ticks rows > max_rows, delete the oldest 10%.
        # Batched commits every 500 writes and on close().
    def close(self) -> None
@dataclass(frozen=True)
class TickRow: t: float; dt: float; action: str; prob: float; rewards: dict; events: list[dict];
               proposals: list[dict]; shadow: list[dict]; channels: dict[str, np.ndarray]   # channels empty if not sampled
def read_log(path: Path, run_id: str | None = None) -> Iterator[TickRow]   # ordered by t; run_id None = latest run
def list_runs(path: Path) -> list[dict]
```

- [ ] **Step 1: Failing tests:**
  - `test_roundtrip_rows_and_channels`.
  - `test_channel_sampling_interval`: sample_s=600, dt=60 and no events give one channel snapshot per 10 ticks.
  - `test_events_force_channel_snapshot`.
  - `test_private_event_redacted`.
  - `test_rotation_keeps_newest`: max_rows=100 with 150 writes leaves ≤100 rows, all from the newest t.
  - `test_multiple_runs_latest_default`.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(lab): experience log with sampling, privacy and rotation`.

---

### Task 6: M1 modules — drives, PAD affect, utility policy

**Depends on:** T1. Tests build a `Blackboard` by hand.

**Files:**
- Create: `engrama/modules/drives/needs.py`, `engrama/modules/affect/pad.py`, `engrama/modules/policy/utility.py`.
- Test: `tests/modules/test_drives.py`, `test_pad.py`, `test_utility.py`.

**Behavior (values for `balance.py` are appended by this task with the names given):**
- **`NeedDrives`**
  - Reads `body.needs`, writes `drives`, rate 1 Hz.
  - Formula: `urgency = 1 / (1 + exp(-(n - mid[k]) / 0.08))`, where `n` is the need in 0..1. `DRIVE_MIDPOINTS` = fome .55, sono .6, tedio .5, carinho .5, curiosidade .5, apoio .6.
  - `viz`: `bars` of drives.
- **`PadAffect`**
  - Reads `drives`, `traits` (optional; uses INITIAL_TRAITS/100 when absent) and `temporal.surprise` (optional). Writes `affect.pad`. Rate 1 Hz. State: the pad vector.
  - Baseline from traits:
    - `P0 = 0.1 + 0.2*(sociabilidade - .5)`;
    - `A0 = 0.2*(curiosidade - .5)`;
    - `D0 = 0.3*(independencia - .5)`.
  - Each step: decay toward the baseline with `PAD_HALF_LIFE_S` (exact exponential in dt). Then add the appraisal of this tick's events using `APPRAISAL`:

    | Event | ΔP | ΔA | ΔD | Condition |
    |---|---|---|---|---|
    | pet | +.15 | +.05 | 0 | — |
    | click | +.05 | +.1 | 0 | — |
    | message | `+.2*valence` | +.1 | 0 | — |
    | food | +.1 | 0 | +.05 | — |
    | answered | +.2 | +.1 | +.05 | — |
    | fullscreen_on | −.05 | −.1 | 0 | — |

    Patience scales the arousal deltas by `(1.2 - paciencia)`.
  - Drive pressure per sim-hour: `P -= 0.3*max(drives)`, `A += 0.2*(drives[tedio] - drives[sono])`.
  - Surprise: `A += 0.3*surprise*dt/60` (capped at the clip).
  - `pad_label(pad) -> str`: the octant name, from the sign of (P, A, D).
    - `+++` "exuberant", `++-` "excited";
    - `+-+` "relaxed", `+--` "content";
    - `-++` "angry", `-+-` "anxious";
    - `--+` "bored", `---` "sad".
    
    The magnitude check comes first: `|pad| < 0.15` → "neutral".
  - `viz`: `pad3d` plus `series`.
- **`UtilityPolicy`**
  - Reads `drives`, `affect.pad`, `traits` (optional), `body.stage`. Proposes every action in `bb.available_actions`. Rate 1 Hz (`propose` is called at every decision).
  - Scores (d = drives, tr = traits 0..1):

    | Action | Score |
    |---|---|
    | sleep | `d.sono*1.5` |
    | play_alone | `d.tedio*(0.6 + tr.criatividade)` |
    | ask_attention | `(d.carinho + 0.5*d.apoio)*(0.4 + tr.sociabilidade)` |
    | explore | `d.curiosidade*(0.5 + tr.curiosidade)` |
    | show_something | `0.3*(P>0)*tr.sociabilidade + 0.2*d.curiosidade` |
    | wander | `0.25 + 0.2*A` |
    | idle | `0.2 + 0.3*(1 - A)/2` |
    | hide | `1.0` |

  - Reason: a short string naming the top term, e.g. `"sono alto"` or `"tédio + criatividade"`.

- [ ] **Step 1: Failing tests:**
  - `test_drives_monotonic_and_midpoint` (n = mid gives 0.5).
  - `test_pad_decays_to_baseline_dt_invariant`: 1 h at dt=1 vs dt=60, within 1e-3.
  - `test_pad_pet_raises_pleasure`.
  - `test_pad_high_drives_lower_pleasure`.
  - `test_pad_label_octants_and_neutral`.
  - `test_utility_sleepy_prefers_sleep`.
  - `test_utility_only_available_actions`.
  - `test_utility_reasons_nonempty`.
  - `test_traits_change_utility`: sociabilidade 0.9 vs 0.1 changes the ask_attention score.
- [ ] **Step 2:** FAIL → implement → PASS (including `tests/test_architecture.py`).
- [ ] **Step 3:** commit `feat(modules): need drives, PAD affect and utility policy`.

---

### Task 7: Persistence

**Depends on:** T1.

**Files:**
- Create: `engrama/services/persistence.py`.
- Test: `tests/services/test_persistence.py`.

**Interfaces — Produces:**
```python
class SaveCorrupted(Exception): ...
def save_state_dict(path_base: Path, d: dict) -> None    # arrays (recursively, keyed by dotted path) -> path_base.npz; rest -> path_base.json; atomic (tmp + os.replace)
def load_state_dict(path_base: Path) -> dict             # exact inverse; np.load(allow_pickle=False)
def save_run(save_dir: Path, kernel_state: dict, modules: dict[str, dict], meta: dict) -> None
    # save_dir/kernel.json, save_dir/modules/<name>.{npz,json}, save_dir/meta.json (recipe, seed, rng states, version=1)
    # daily backup: copies save_dir contents into save_dir/backups/YYYY-MM-DD/ once per day; keep newest 7
def load_run(save_dir: Path) -> tuple[dict, dict[str, dict], dict]   # SaveCorrupted on bad/missing files; falls back to newest backup that loads
def rng_state(rng: np.random.Generator) -> dict ; def rng_from_state(d: dict) -> np.random.Generator   # via bit_generator.state (JSON-safe ints)
```

- [ ] **Step 1: Failing tests:**
  - `test_state_dict_roundtrip_nested_arrays_and_scalars`.
  - `test_atomic_no_partial_file_on_error` (monkeypatch `os.replace` to raise; the old file stays intact).
  - `test_backup_rotation_keeps_7`.
  - `test_corrupt_kernel_json_falls_back_to_backup`.
  - `test_corrupt_without_backup_raises`.
  - `test_rng_state_roundtrip_same_draws`.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(services): atomic module-aware persistence with backups`.

---

### Task 8: Runtime, simulated users, metrics and `lab sim` — the M1 milestone

**Depends on:** T2–T7.

**Files:**
- Create: `engrama/lab/runtime.py`, `simuser.py`, `metrics.py`, `cli.py`, `__main__.py`, `recipes/minimal-v1.toml`.
- Test: `tests/lab/test_runtime.py`, `test_simuser.py`, `test_metrics.py`, `test_cli.py`.

**Interfaces — Produces:**
```python
# simuser.py
@dataclass(frozen=True)
class Profile: name: str; active_hours: tuple[int, int]; answer_prob: float; pet_per_h: float;
               feed_when_fome: float; msgs_per_h: float; msg_valence: float; apps: tuple[str, ...]; fullscreen_per_day: float
PROFILES: dict[str, Profile]   # "attentive", "absent", "night_owl", "gamer" with sensible values (attentive answers 0.8, absent 0.1, ...)
class SimUser:
    def __init__(self, profile: Profile, rng: np.random.Generator) -> None
    def events(self, t: float, dt: float, creature: dict) -> list[Obs]
        # creature = {"action": str, "needs": dict, "stage": str}; Poisson draws scaled by dt; responds to
        # ask_attention with "answered" within ASK_ANSWER_WINDOW with answer_prob; feeds a random FOOD_ID when
        # fome >= feed_when_fome*100 during active hours; emits user_active/user_idle at active window edges,
        # app_focus {"app": choice(apps)}, fullscreen_on/off pairs.

# runtime.py
class Runtime:
    def __init__(self, recipe: Recipe, seed: int, log: ExperienceLog | None = None, start_hour: float = 8.0) -> None
        # rng = default_rng(seed); kernel_rng, module rngs (one per module via spawn), arbiter rng
    def tick(self, dt: float, events: list[Obs]) -> str
        # 1 kernel.ingest(events); evs, rewards = kernel.step(dt)
        # 2 write kernel.channels() to bb; bb.events = converted evs; bb.t; bb.available_actions
        # 3 complete previous Experience with rewards + next_channels=bb.snapshot(); scheduler.learn(exp); log.write
        # 4 scheduler.step(bb, dt)
        # 5 if decision due: live, shadow = scheduler.proposals(bb); action, prob, _ = arbiter.choose(...)
        # 6 running, forced = kernel.execute(action); prob = 1.0 if forced
        # 7 start new pending Experience(channels=bb.snapshot() before decision, action=running, prob)
    def run(self, seconds: float, dt: float, user: SimUser | None = None) -> None
    def save(self, save_dir: Path) -> None ; @classmethod load(cls, save_dir: Path, log=None) -> "Runtime"
    @property bb, kernel, scheduler
def run_days(recipe_path: Path, days: float, profile: str, seed: int, dt: float, log_path: Path | None) -> dict  # returns metrics

# metrics.py
def compute_metrics(rows: Iterable[TickRow]) -> dict
  # wellbeing = 1 - fraction of sim time with any need >= 0.9 (from sampled channels)
  # ask_count, ignored_rate = ignored / max(1, asks), answered_rate
  # behavior_entropy (bits, time-weighted action distribution), action_share: dict
  # pad_mean[3], pad_std[3], surprise_mean (if channel present)
  # shadow_agreement: dict module -> fraction of decisions where shadow top proposal == chosen action
  # days_simulated, ticks

# cli.py  (python -m engrama.lab ...)
#   sim --recipe recipes/default-v1.toml --days 30 --profile attentive --seed 1 --dt 60 [--log PATH] [--save DIR]
#   report --log PATH [--run ID]
#   (compare and replay are added in T11)
# prints metrics as indented JSON; exit 0
```

`recipes/minimal-v1.toml` contains drives.needs, affect.pad and policy.utility (weight 1.0), with arbiter temperature 0.5.

- [ ] **Step 1: Failing tests:**
  - `test_tick_order_and_experience_alignment`: the experience logged at tick k has the action chosen at k−1 and the rewards from tick k.
  - `test_same_seed_same_log` (determinism).
  - `test_save_load_continue_identical` **(Review Focus 4)**: run 2 days, save, load, run 1 day. Compare with an uninterrupted 3-day run; the action sequences must be equal.
  - `test_creature_never_stalls_with_broken_module`: a recipe with a registered fake module that raises still makes the creature act (fallback or utility).
  - `test_simuser_profiles_differ`: attentive gives a higher answered_rate than absent over 3 days.
  - `test_metrics_entropy_and_rates` on synthetic TickRows.
  - `test_cli_sim_smoke`: 1 day, prints JSON with the key "wellbeing".
  - **M1 acceptance**, `test_30_days_under_2_minutes` (mark `@pytest.mark.slow`; the default run includes it): minimal recipe, dt=60, attentive profile, log to tmp_path. It must take < 120 s, give wellbeing > 0.5, and have no NaN in pad.
- [ ] **Step 2:** FAIL → implement → PASS. Also run `python -m engrama.lab sim --recipe recipes/minimal-v1.toml --days 30 --profile attentive --seed 1 --dt 60` and paste its output in the report.
- [ ] **Step 3:** commit `feat(lab): runtime loop, simulated users, metrics and sim CLI`.

---

### Task 9: Temporal SNN module

**Depends on:** T1 and T4 (contracts + registry entry). It is independent of T8, and its tests use a hand-built Blackboard and event sequences.

**Files:**
- Create: `engrama/modules/temporal/snn.py`.
- Test: `tests/modules/test_snn.py`.

**Design** (constants appended to balance.py under `SNN_*`):
- **Purpose:** detect patterns in time. The outputs are `temporal.surprise`, `temporal.familiarity` and `temporal.expectation`. It reads `bb.events`, `world.hour` and `world.user_active`, and `body.stage` for growth.
- **Input encoding per step ("bin"):**
  - x = [one-hot count (clipped to 1) per EVENT_KIND (10)], 4 hour-phase units (cos/sin halves → rectified, i.e. 4 non-negative values), user_active (1). That is 15 inputs.
  - Each input unit drives a population of 4 Poisson neurons at rate `x*SNN_INPUT_HZ` (80 Hz), for `SNN_SUBSTEPS` = 20 substeps of 1 ms.
- **Network:**
  - Hidden: N excitatory LIF (N = `SNN_HIDDEN_BY_STAGE[stage]`), plus N/4 inhibitory neurons.
  - Input→E is sparse at 20%. E→E is recurrent at 10%. E→I and I→E are dense.
  - Weights are scaled by `1/sqrt(fan_in)` so the dynamics don't depend on size; this fixes the v1 saturation.
  - Pair-based STDP with traces on Input→E and E→E, with weights clipped to [0, `SNN_WMAX`].
  - **Homeostasis:** each E neuron's threshold adapts toward the target rate `SNN_TARGET_HZ` = 10 Hz with time constant `SNN_HOMEO_TAU_BINS` = 50 bins.
- **Readout (the part that makes it temporal):**
  - A linear predictor W_pred (10 × N) maps the hidden rate vector at bin k to the event-kind vector at bin k+1, through a sigmoid. It is trained online with the delta rule (lr `SNN_PRED_LR`).
  - `surprise_k = mean(|x_events_k - pred_{k-1}|)`, and the output is an EMA-smoothed value of it with factor 0.3.
  - `familiarity = 1 - EMA_long(surprise)`, with a 200-bin EMA.
  - `expectation = pred_k`.
- **`grow(new_N)`** (when `body.stage` changes): keep the existing weights, initialise the new rows/columns with the same scaling rule, and extend W_pred with zeros.
- **Learning and persistence:**
  - `learn()` is a no-op: plasticity is unsupervised and happens inside `step`.
  - `state_dict`: all weight matrices, thresholds, traces, W_pred, EMAs and the stage. Rate 1 Hz.
  - `budget_ms` = 3.
- **Viz:**
  - `raster` of the last bin's E spikes (bool matrix substeps × N);
  - `heatmap` of Input→E;
  - `series` of surprise and familiarity.

- [ ] **Step 1: Failing tests:**
  - `test_bounded_rates_all_sizes_and_seeds` **(Review Focus 5)**: for N in 32, 64, 96, 128, 160 and seeds 0..4, after 300 bins of a random event stream, the mean E rate is within [2, 40] Hz and no neuron is above 200 Hz.
  - `test_habituation`: the same event (`pet`) every bin, with nothing else. Mean surprise in bins 200–300 is < 0.5 × mean surprise in bins 0–20.
  - `test_novelty_spike`: after 300 bins of routine A (pet on even bins, idle on odd), insert an unseen kind (`fullscreen_on`). Surprise in that bin is > 2× the mean of the routine's last 50 bins.
  - `test_routine_expectation`: after training on "message every 3rd bin", `expectation[message]` is higher on bins where a message is due than on the others (mean over the last 60 bins).
  - `test_grow_preserves_weights`.
  - `test_state_roundtrip_identical_outputs`.
  - `test_step_cost`: N=160 averages < 3 ms per step over 100 steps on the dev machine (skip if `CI` is set).
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(modules): temporal SNN with homeostasis and predictive readout`.

---

### Task 10: Learning modules — contextual Q-learning, food preferences, trait drift

**Depends on:** T1 and T4. Tests use hand-built Blackboard and Experience objects.

**Files:**
- Create: `engrama/modules/policy/qlearning.py`, `engrama/modules/prefs/food.py`, `engrama/modules/traits/drift.py`.
- Test: `tests/modules/test_qlearning.py`, `test_food_prefs.py`, `test_trait_drift.py`.

**Behavior:**
- **`QLearningPolicy`**
  - Context: `hour_bucket(4, from world.hour) × user_active(2) × pad quadrant(4: sign P × sign A; zero counts as +)` = 32 states. Missing channels count as 0.
  - Table: `Q[32, len(ACTIONS)]`, initialised to 0.
  - `learn(exp)`: `s` = context(exp.channels), `a` = exp.action, `r` = `reward_combine(exp.rewards)`, `s'` = context(exp.next_channels). Update: `Q[s,a] += alpha*(r + gamma*max Q[s'] - Q[s,a])` with alpha `QL_ALPHA` = 0.1 and gamma `QL_GAMMA` = 0.5.
  - `propose`: every available action, with score = `Q[s,a]` and reason `"aprendi: <hour>/<active>"`.
  - `viz`: `heatmap` of Q.
  - `state_dict`: Q and the visit counts.
- **`FoodPrefs`**
  - Writes `prefs.food`.
  - Initial liking from the module rng: `normal(0, 0.3)` per food. The seed comes from the recipe rng, so each creature differs.
  - On a `food` event: `liking += 0.05*(curiosidade - 0.5)` if the food was eaten fewer than 3 times (curious creatures like novelty), else `+= 0.03*(paciencia - 0.5)` (comfort food). Then add noise `normal(0, 0.02)` and clip.
  - It does **not** converge to the user: there is no term that follows the user.
  - `propose`: none.
  - `state_dict`: liking and counts.
- **`TraitDrift`**
  - Writes `traits`. State starts at INITIAL_TRAITS.
  - `learn(exp)` accumulates the nudges below:

    | Signal | Nudge |
    |---|---|
    | `user_response` | sociabilidade +0.5 |
    | `ignored` | independencia +0.3, sociabilidade −0.2 |
    | `novelty` while action ∈ {explore, show_something} | curiosidade +0.3 |
    | positive `need_relief` while play_alone | criatividade +0.1 |
    | `petting` | paciencia +0.05 |

  - Applied in trait points. Per trait, the total |change| within one sim-day (`floor(t/86400)`) is capped at `TRAIT_MAX_DRIFT_PER_DAY`. Values are clipped to 0..100 and written /100.
  - `viz`: `bars`.

- [ ] **Step 1: Failing tests:**
  - `test_q_learns_rewarded_action_in_context`: 200 experiences where `ask_attention` in context X gives user_response=1 and other actions give 0. Q argmax in X is ask_attention, and context Y is unaffected.
  - `test_q_dt_independent_reward_scale` (sanity: the reward does not depend on dt).
  - `test_food_prefs_differ_by_seed`.
  - `test_food_prefs_novelty_vs_comfort` (curious vs patient traits on the blackboard).
  - `test_trait_drift_daily_cap`: 100 user_response events in one day give sociabilidade +2.0 exactly, and the next day allows more.
  - `test_trait_drift_ignored_raises_independence`.
  - `test_state_roundtrips`.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(modules): contextual Q-learning, food preferences and trait drift`.

---

### Task 11: Lab experiments — shadow comparison, replay, compare and OPE

**Depends on:** T8. It uses real modules from T6 and fakes for the rest.

**Files:**
- Create: `engrama/lab/replay.py`, `engrama/lab/ope.py`. Modify `engrama/lab/cli.py` (add `compare` and `replay`).
- Test: `tests/lab/test_shadow.py`, `test_replay.py`, `test_ope.py`, `test_cli_compare.py`.

**Interfaces — Produces:**
```python
# replay.py
def replay_module(log_path: Path, spec: ModuleSpec, seed: int = 0, run_id: str | None = None) -> dict[str, list]
  # rebuilds a Blackboard per logged tick from the last sampled channels + that tick's events + t,
  # steps the module with the logged dt, calls learn() with Experiences rebuilt from consecutive rows,
  # and returns {"t": [...], "<channel>": [...] for each channel it writes, "proposals_top": [...]}
# ope.py
def ips_estimate(rows: Iterable[TickRow], target_probs: Callable[[TickRow], dict[str, float]],
                 clip: float = 10.0) -> dict   # {"value": mean(clip(pi_t/pi_b) * r), "logged_value": mean(r), "n": int, "ess": float}
  # r = reward_combine(row.rewards) of the NEXT row (reward that followed the action)
# cli.py additions
#   compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10 --profile attentive --seed 1 --dt 60
#       runs both with the same seed/profile, prints {"a": metrics, "b": metrics, "diff": {numeric key: b-a}}
#   replay --log PATH --module temporal.snn [--param k=v ...]   prints summary stats (mean/min/max) per written channel
```

- [ ] **Step 1: Failing tests:**
  - `test_shadow_does_not_change_actions` **(Review Focus 3)**: the minimal recipe vs the minimal recipe plus `[[shadow]] policy.utility name="u2"` (with different params), same seed, 2 days. The action sequences are identical, and `metrics["shadow_agreement"]["u2"]` exists.
  - `test_replay_matches_live_for_deterministic_module`: replaying `drives.needs` on a log reproduces the logged `drives` at the sampled ticks (atol 1e-6).
  - `test_ips_equals_logged_when_target_equals_behavior`.
  - `test_ips_clip`.
  - `test_cli_compare_outputs_diff`.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** commit `feat(lab): shadow comparison, replay, recipe compare and IPS evaluation`.

---

### Task 12: Default recipe, M2 acceptance, bench and README

**Depends on:** T8–T11.

**Files:**
- Create: `recipes/default-v1.toml`, `tests/test_m2_acceptance.py`, `tools/bench.py`, `README.md` (replacing the old one).

**`recipes/default-v1.toml`:**
- Modules, in order: drives.needs; temporal.snn; affect.pad; traits.drift; prefs.food; policy.utility (weight 1.0); policy.qlearning (weight 0.6).
- Arbiter: temperature 0.5.

**`tools/bench.py`:** runs the default recipe headless in real time (dt=1, `time.sleep` pacing) for `--seconds` (default 120). It reports peak RSS, mean CPU % (psutil) and per-module mean_ms from the scheduler status, as JSON.

**README.md** (PT and EN sections, short):
- what Engrama is;
- install: venv plus `pip install numpy psutil pytest`;
- `python -m engrama.lab sim|compare|replay|report`;
- how to write a module: the contract, registering it, and adding it to a recipe as live or `[[shadow]]`;
- the dependency rule;
- where the save and log files live (Config.data_dir on E:).

- [ ] **Step 1: Failing acceptance tests:**
  - `test_default_recipe_30_days_stable`: dt=60, attentive profile. No module gets disabled, wellbeing > 0.5, traits drift but stay within the per-day caps, and runtime < 180 s (mark slow).
  - `test_snn_measures_novelty_in_replay`: in the log of a 7-day gamer-profile run, take the ticks whose events include a kind that occurred fewer than 2 times in the preceding 24 sim-hours. Their mean `temporal.surprise` (logged, since event ticks always sample channels) is greater than the mean at ticks whose kinds all occurred ≥ 5 times in that window.
  - `test_recipes_differ_on_metric`: `compare` minimal vs default over 10 days with the same seed gives a different `behavior_entropy` or `answered_rate` (|diff| > 0.01). This is the measurable "the mind matters" criterion.
  - `test_creatures_diverge`: the default recipe with seeds 1 and 2 over 10 days gives different `prefs.food` argmax or a trait-vector L1 distance > 1.
- [ ] **Step 2:** make them PASS; tune the `SNN_*` / `QL_*` constants only if needed, and record any change in the report.
- [ ] **Step 3:** run `python tools/bench.py --seconds 60` and put the JSON in the report. Targets (measured, not gated): RSS ≤ 150 MB, CPU ≤ 2%.
- [ ] **Step 4:** run the full suite: `pytest -q` (including slow tests).
- [ ] **Step 5:** commit `feat(v2): default recipe, M2 acceptance tests, bench and README`.
- [ ] **Step 6 (controller, after the final review):**
  - push branch `v2` and open a PR to `main` on `alexzjss/engrama`. The PR body has no Claude/AI attribution (user rule).
  - merge it into main (the user pre-approved PR + merge for this repo).
