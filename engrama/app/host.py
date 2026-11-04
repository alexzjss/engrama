"""The live host: the composition root that runs the v2 Runtime on a single simulation thread.

The UI only reads `snapshot()` (an immutable copy swapped by reference) and publishes events with `post()`.
Callbacks (`on_event`, `on_rest_change`) run on the simulation thread; keep them quick and thread-safe.
"""
from __future__ import annotations
import collections
import dataclasses
import json
import logging
import os
import random
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from engrama import balance as B
from engrama.app import i18n
from engrama.app.digital import DigitalRequests
from engrama.app.rest import RestPolicy, system_ram_free_mb
from engrama.app.providers import (_Activity, _build_persona, _GenerationsProvider, _memory_provider,  # noqa: F401  re-exports
                                   _MemoryProvider, _NullServer, _PerceptionProvider)
from engrama.app.snapshot import ModuleView, ProposalView, Snapshot, Viz, plain, to_viz
from engrama.clock import SimClock
from engrama.kernel.branches import branch_name
from engrama.kernel.sensors import Obs
from engrama.lab.explog import ExperienceLog
from engrama.lab.runtime import Runtime
from engrama.mind.recipe import load_recipe
from engrama.modules.affect.pad import pad_label
from engrama.services.generations import GenerationRecord, append_generation
from engrama.vocab import EVENT_KINDS, FOOD_IDS, NEED_KEYS, TRAIT_KEYS

__all__ = ["Host", "RestPolicy", "Snapshot", "Viz", "to_viz", "main"]  # noqa: F822  ("main" is lazy, see __getattr__)

_INPUT_KINDS = frozenset({"click", "pet", "message", "food", "user_active", "answered"})
_POST_CAP = 1000
_VIZ_EVERY_S = 1.0
FORGET_EVERY_S = 6 * 3600.0


def _safe(cb: Callable | None, *args) -> None:
    if cb is None:
        return
    try:
        cb(*args)
    except Exception:   # a UI callback must never kill the simulation
        pass


class Host:
    def __init__(self, cfg, data_dir: Path, recipe_path: Path, seed: int | None = None,
                 clock: SimClock | None = None, *, wall_fn: Callable[[], float] | None = None,
                 ram_free_mb_fn: Callable[[], float] = system_ram_free_mb,
                 warn_recipe_mismatch: bool = True) -> None:
        self.cfg = cfg
        self._warn_recipe_mismatch = warn_recipe_mismatch
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._recipe_path = Path(recipe_path)
        self.clock = clock if clock is not None else SimClock(float(getattr(cfg, "time_scale", 1.0)))
        self._wall: Callable[[], float] = wall_fn or getattr(self.clock, "_now", None) or time.time
        self.rest_policy = RestPolicy(self._wall, ram_free_mb_fn)

        self.want_viz = False
        self.on_rest_change: Callable[[bool, str], None] | None = None
        self.on_event: Callable[[str, dict], None] | None = None
        self.on_eyes_change: Callable[[bool], None] | None = None
        self.on_digital_ask: Callable[[str], None] | None = None     # a request just opened (sim thread)
        self.on_digital_thanks: Callable[[str], None] | None = None  # the open request was fulfilled (UI thread)
        self.theme_fn: Callable[[], str] | None = None               # current perceived theme ("" = none)
        self._digital_lock = threading.Lock()
        self._eyes_closed = bool(getattr(cfg, "eyes_closed", False))
        self._heavy_pc = False
        self.last_error = ""

        self._posts: collections.deque[tuple[str, dict]] = collections.deque(maxlen=_POST_CAP)
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self._save_lock = threading.RLock()
        self._stopped = False
        self._log: ExperienceLog | None = None
        self._log_thread = 0
        self._run_id = uuid.uuid4().hex
        self._last_input_wall = self._wall()
        self._last_save_wall = self._wall()
        self._last_viz_wall = float("-inf")
        self._viz: dict[str, tuple[Viz, ...]] = {}
        self._resting, self._rest_reason = False, ""
        self._prev_stage = ""
        self._prev_action = ""
        self._evolved_at = float("-inf")
        self.memory = None            # MemoryStore, attached by attach_services()
        self.working = None           # WorkingMemory
        self.language = None          # LanguageService (farewell only)
        self.generations_provider = _GenerationsProvider(self.data_dir)
        self._farewell_text = ""
        self._farewell_requested = False
        self._dead_wall = 0.0
        self._skip_farewell = False
        self._startup_dead = False

        self._save_dir = self.data_dir / "save"
        self._host_json = self.data_dir / "host.json"
        self._digital: DigitalRequests | None = None
        self._rt, self._types = self._load_or_create(seed)
        self._prev_stage = self._rt.kernel.stage
        self._startup_dead = bool(self._rt.kernel.dead)
        self._snap: Snapshot = self._build_snapshot()

    # ---- construction -------------------------------------------------------------------------------

    def _read_host_json(self) -> dict:
        try:
            d = json.loads(self._host_json.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _load_or_create(self, seed: int | None) -> tuple[Runtime, dict[str, str]]:
        recipe = load_recipe(self._recipe_path)
        meta = self._read_host_json()
        self._born_wall = float(meta["born"]) if isinstance(meta.get("born"), (int, float)) else self._wall()
        rt: Runtime | None = None
        if (self._save_dir / "meta.json").exists():
            rt = Runtime.load(self._save_dir, None)
            if self._warn_recipe_mismatch and rt.recipe.name != recipe.name:   # the creature keeps its own recipe
                logging.getLogger("engrama.app").warning(
                    "A criatura salva usa a receita '%s'; --recipe '%s' vale só para uma pasta de dados nova. / "
                    "The saved creature uses recipe '%s'; --recipe '%s' only applies to a new data dir.",
                    rt.recipe.name, recipe.name, rt.recipe.name, recipe.name)
            gap = self._wall() - float(meta.get("wall", self._wall()))
            if gap > 0:
                rt.kernel.offline_catchup(gap)
        if rt is None:
            if seed is None:
                seed = int(meta["seed"]) if isinstance(meta.get("seed"), int) else random.SystemRandom().randrange(2 ** 31)
            rt = Runtime(recipe, int(seed))
            self._write_host_json(rt.seed)
        types = {s.name: s.type for s in rt.recipe.modules}
        self._digital = DigitalRequests(rt.seed)
        try:
            self._digital.load_state_dict(meta.get("digital") if isinstance(meta.get("digital"), dict) else {})
        except Exception:   # a corrupt block must not stop start-up: defaults
            self._digital = DigitalRequests(rt.seed)
        return rt, types

    def _write_host_json(self, seed: int) -> None:
        tmp = self._host_json.with_name(self._host_json.name + ".tmp")
        data: dict = {"wall": self._wall(), "seed": seed, "born": self._born_wall}
        if self._digital is not None:
            with self._digital_lock:
                data["digital"] = self._digital.state_dict()
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self._host_json)

    # ---- public API ---------------------------------------------------------------------------------

    runtime = property(lambda self: self._rt)

    def snapshot(self) -> Snapshot:
        return self._snap

    def post(self, kind: str, data: dict | None = None) -> None:
        """Thread-safe. Becomes an Obs (stamped with the simulation time) at the next tick."""
        if kind not in EVENT_KINDS:
            return
        self._posts.append((kind, dict(data or {})))
        if kind in _INPUT_KINDS:
            self._last_input_wall = self._wall()

    def fulfill_digital(self, digital_id: str) -> bool:
        """UI thread: the user gave a digital item. True (and a happy reaction) if it was the open request.
        The body already got the `pet` event from the Window; this only closes the request and cheers."""
        try:
            with self._digital_lock:
                ok = self._digital.fulfill(str(digital_id), float(self._rt.kernel.t))
                if ok:
                    self._snap = dataclasses.replace(self._snap, digital_request=self._digital.open)
            if ok:
                _safe(self.on_digital_thanks, str(digital_id))
            return bool(ok)
        except Exception as e:
            self.last_error = f"digital: {e!r}"
            return False

    def set_rest(self, on: bool) -> None:
        """Manual rest override; applied at the next tick."""
        self.rest_policy.manual = bool(on)

    @property
    def eyes_closed(self) -> bool:
        return self._eyes_closed

    def set_eyes_closed(self, on: bool) -> None:
        """Eyes-closed (privacy) state; reaches the snapshot at the next tick."""
        self._eyes_closed = bool(on)
        _safe(self.on_eyes_change, self._eyes_closed)

    def set_heavy_pc(self, on: bool) -> None:
        """Thread-safe flag from the perception service: a sustained heavy PC makes the creature rest."""
        self._heavy_pc = bool(on)

    def attach_services(self, memory=None, working=None, language=None) -> None:
        """Wire the services death and rebirth touch (all optional: a bare Host still dies and is reborn)."""
        self.memory, self.working, self.language = memory, working, language
        self._cache: tuple[float, dict, str] | None = None

    @property
    def farewell_text(self) -> str:
        return self._farewell_text

    def skip_farewell(self) -> None:
        """Thread-safe: the user moved past the farewell scene; rebirth happens at the next tick."""
        self._skip_farewell = True

    def set_time_scale(self, scale: float) -> None:
        self.clock.set_scale(float(scale))

    def start(self) -> None:
        if self._thread is not None or self._stopped:
            return
        self._warm_log()
        self._thread = threading.Thread(target=self._run, name="engrama-sim", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the simulation thread, write the final save and release the log, within `timeout` seconds."""
        if self._stopped:
            return
        self._stop_evt.set()
        th = self._thread
        if th is not None:
            th.join(timeout)
            if th.is_alive():
                return   # daemon thread: it finishes its own save; never block the UI past the budget
        else:
            self._finish()
        self._stopped = True

    def pump(self, n: int = 1) -> None:
        """Run n ticks on the calling thread (tests / headless use). Not for use while the thread runs."""
        for _ in range(n):
            self._tick()

    def _warm_log(self) -> None:
        """Create the explog schema on the caller's thread, before the sim thread exists.

        On a cold database the schema creation fsyncs for 0.4-1.6 s; if it ran inside the first tick, a stop()
        arriving meanwhile would have to wait for it. Once the schema exists the sim thread's own open is cheap."""
        path = self.data_dir / "explog.sqlite"
        if path.exists():
            return
        try:
            ExperienceLog(path, self._run_id, self._rt.recipe.name, self._rt.seed,
                          recipe_version=self._rt.recipe.version).close()
        except Exception as e:
            self.last_error = f"explog: {e!r}"

    # ---- simulation thread --------------------------------------------------------------------------

    def _run(self) -> None:
        try:
            while not self._stop_evt.is_set():
                self._tick()
                self._stop_evt.wait(B.HOST_TICK_S)
        finally:
            self._finish()

    def _finish(self) -> None:
        try:
            self._save()
        except Exception as e:
            self.last_error = f"save: {e!r}"
        self._close_log()

    def _ensure_log(self) -> None:
        tid = threading.get_ident()
        if self._log is not None and self._log_thread == tid:
            return
        if self._log is not None:   # sqlite connections are thread-bound: reopen the same run here
            self._close_log()
        self._log = ExperienceLog(self.data_dir / "explog.sqlite", self._run_id, self._rt.recipe.name,
                                  self._rt.seed, recipe_version=self._rt.recipe.version)
        self._log_thread = tid
        self._rt.log = self._log

    def _close_log(self) -> None:
        log, self._log = self._log, None
        self._rt.log = None
        if log is not None:
            try:
                log.close()
            except Exception:
                pass

    def _commit_log(self) -> None:
        try:
            if self._log is not None:
                self._log._db.commit()
        except Exception:
            pass

    def _save(self) -> None:
        with self._save_lock:
            self._commit_log()
            self._rt.save(self._save_dir)
            self._last_save_wall = self._wall()
            self._write_host_json(self._rt.seed)

    def _tick(self) -> None:
        try:
            self._tick_inner()
        except Exception as e:   # keep the creature alive; the UI can surface last_error
            self.last_error = f"tick: {e!r}"

    def _tick_inner(self) -> None:
        rt = self._rt
        wall = self._wall()
        if self._startup_dead:   # a save that was already dead: reborn at once, no farewell scene
            self._startup_dead = False
            self._rebirth(wall)
            rt = self._rt
        dt = self.clock.advance()   # capped at 5 s x time_scale per call
        if dt <= 0.0:
            return
        self._ensure_log()
        k = rt.kernel
        events: list[Obs] = []
        for _ in range(len(self._posts)):   # bounded: a flood of posts cannot pin the tick
            kind, data = self._posts.popleft()
            events.append(Obs(k.t, kind, data))
        rt.tick(dt, events)
        self._emit_changes(wall)
        self._update_rest(wall)
        self._handle_death(wall)
        if wall - self._last_save_wall >= B.AUTOSAVE_S:
            self._save()
        self._snap = self._build_snapshot()

    def _emit_changes(self, wall: float) -> None:
        k = self._rt.kernel
        stage, action = k.stage, k.action or "idle"
        if stage != self._prev_stage:
            self._evolved_at = wall
            old, self._prev_stage = self._prev_stage, stage
            if old == "egg":
                _safe(self.on_event, "hatch", {"stage": stage})
            else:
                _safe(self.on_event, "evolve", {"from": old, "to": stage})
        with self._digital_lock:
            self._digital.tick(float(k.t))
            opened = self._digital.on_action_start(action, float(k.t)) if action != self._prev_action else ""
        if opened:
            _safe(self.on_digital_ask, opened)
        if action != self._prev_action:
            old, self._prev_action = self._prev_action, action
            if old:
                _safe(self.on_event, "action_change", {"from": old, "to": action})

    # ---- death, farewell, rebirth -------------------------------------------------------------------

    def _handle_death(self, wall: float) -> None:
        k = self._rt.kernel
        if not k.dead:
            return
        if not self._farewell_requested:
            self._farewell_requested, self._dead_wall = True, wall
            self._request_farewell(k.generation, k.death_cause)
        if k.world.fullscreen:
            return
        if self._skip_farewell or wall - self._dead_wall >= B.FAREWELL_S:
            self._rebirth(wall)

    def _request_farewell(self, generation: int, cause: str) -> None:
        def on_text(text: str) -> None:   # worker thread; drop a stale text that arrives after the rebirth
            if self._rt.kernel.generation == generation and self._rt.kernel.dead:
                self._farewell_text = str(text or "")
        lang = self.language
        if lang is None:
            return
        try:
            lang.farewell(cause, on_text)
        except Exception as e:
            self.last_error = f"farewell: {e!r}"

    def _rebirth(self, wall: float) -> None:
        """Archive the finished life (memory, save, registry record), start the next one, save. Sim thread only."""
        with self._save_lock:
            rt = self._rt
            gen = rt.kernel.generation
            gen_dir = self.data_dir / "generations" / str(gen)
            ancestral: list[str] = []
            if self.memory is not None:
                try:
                    ancestral = list(self.memory.ancestral_candidates(B.ANCESTRAL_MAX))
                    self.memory.archive_to(gen_dir / "memory.sqlite")
                except Exception as e:
                    self.last_error = f"archive memory: {e!r}"
            try:
                self._commit_log()
                rt.save(self._save_dir)
                shutil.rmtree(gen_dir / "save", ignore_errors=True)
                shutil.copytree(self._save_dir, gen_dir / "save")
            except Exception as e:
                self.last_error = f"archive save: {e!r}"
            summary = rt.life_summary()
            try:
                append_generation(self.data_dir / "generations.json", GenerationRecord(
                    n=gen, lineage=tuple(summary["lineage"]), seed=int(summary["seed"]),
                    born_wall=float(self._born_wall), died_wall=float(wall), days=float(summary["days"]),
                    cause=str(summary["cause"]), ancestral=tuple(ancestral)))
            except Exception as e:
                self.last_error = f"generations.json: {e!r}"
            rt.rebirth()
            if self.memory is not None:
                try:
                    self.memory.new_generation(ancestral)
                except Exception as e:
                    self.last_error = f"new generation: {e!r}"
            if self.working is not None:
                self.working.clear()
            self._born_wall = float(wall)
            self._farewell_text, self._farewell_requested, self._skip_farewell = "", False, False
            self._prev_stage = rt.kernel.stage
            self._prev_action = ""
            self._save()

    def _update_rest(self, wall: float) -> None:
        k = self._rt.kernel
        reason = self.rest_policy.update(k.world.fullscreen, self._last_input_wall, self._heavy_pc)
        resting = reason is not None
        if resting != self._resting or (resting and reason != self._rest_reason):
            changed = resting != self._resting
            self._resting, self._rest_reason = resting, reason or ""
            self._rt.scheduler.set_rest(resting)
            if changed:
                _safe(self.on_rest_change, resting, self._rest_reason)

    # ---- snapshot -----------------------------------------------------------------------------------

    def _build_snapshot(self) -> Snapshot:
        rt, k = self._rt, self._rt.kernel
        bb = rt.bb
        wall = self._wall()
        pad_arr = bb.get("affect.pad")
        pad = tuple(float(x) for x in pad_arr) if pad_arr is not None else (0.0, 0.0, 0.0)
        tr = bb.get("traits")
        traits = ({n: float(v) * 100.0 for n, v in zip(TRAIT_KEYS, tr)} if tr is not None else {})
        fl = bb.get("prefs.food")
        liking = ({n: float(v) for n, v in zip(FOOD_IDS, fl)} if fl is not None else {})
        sur, fam = bb.get("temporal.surprise"), bb.get("temporal.familiarity")
        live, shadow = rt.last_proposals
        mods = rt.scheduler.modules()
        views = tuple(ModuleView(st.name, self._types.get(st.name, ""), tuple(mods[st.name].reads),
                                 tuple(mods[st.name].writes), st.shadow, float(st.mean_ms),
                                 float(st.rate_factor), not st.enabled)
                      for st in rt.scheduler.status())
        if self.want_viz:
            if wall - self._last_viz_wall >= _VIZ_EVERY_S:
                self._last_viz_wall = wall
                self._viz = self._collect_viz(mods)
            viz = {n: tuple(Viz(v.kind, v.title, plain(v.data)) for v in vs) for n, vs in self._viz.items()}
        else:
            viz = {}
        return Snapshot(
            t=float(k.t), wall=float(wall), stage=k.stage, action=k.action or "idle", asleep=k.asleep,
            egg_clicks=int(k.egg_clicks),
            needs={n: float(k.needs.values[n]) for n in NEED_KEYS},
            pad=pad, pad_label=pad_label(pad) if pad_arr is not None else "neutral",
            traits=traits, food_liking=liking,
            surprise=float(sur[0]) if sur is not None else 0.0,
            familiarity=float(fam[0]) if fam is not None else 0.0,
            look=plain(k.genome.to_dict()),
            proposals=tuple(ProposalView(p.action, float(p.score), p.reason, p.source) for p in live),
            shadow_proposals=tuple(ProposalView(p.action, float(p.score), p.reason, p.source) for p in shadow),
            winner=rt.last_choice, modules=views, viz=viz,
            recipe_name=rt.recipe.name, recipe_version=int(rt.recipe.version),
            resting=self._resting, rest_reason=self._rest_reason,
            eyes_closed=self._eyes_closed,
            branch=k.genome.branch, branch_name=branch_name(k.genome.branch, i18n.get_lang()),
            lineage=tuple(k.lineage), generation=int(k.generation),
            sick=bool(k.health.sick), sick_kind=str(k.health.kind), grave=bool(k.health.grave),
            old=bool(k.lifecycle.old), dead=bool(k.dead), death_cause=str(k.death_cause),
            evolved_at=float(self._evolved_at), fullscreen=bool(k.world.fullscreen),
            theme=self._current_theme(), digital_request=self._digital.open)

    def _current_theme(self) -> str:
        fn = self.theme_fn
        if fn is None:
            return ""
        try:
            return str(fn() or "")
        except Exception:
            return ""

    def _collect_viz(self, mods) -> dict[str, tuple[Viz, ...]]:
        out: dict[str, tuple[Viz, ...]] = {}
        for name, m in mods.items():
            try:
                out[name] = tuple(to_viz(s) for s in m.viz())
            except Exception:
                out[name] = ()
        return out


_CLI_NAMES = frozenset({"main", "_main", "resolve_recipe_arg", "open_in_display_mode"})


def __getattr__(name: str):
    """Lazy re-export of the CLI entry points (cli.py imports Host from here, so a top-level import would cycle)."""
    if name in _CLI_NAMES:
        from engrama.app import cli
        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
