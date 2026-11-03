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
from typing import Any, Callable

from engrama import balance as B
from engrama.app import i18n
from engrama.app.digital import DigitalRequests
from engrama.app.rest import RestPolicy, system_ram_free_mb
from engrama.app.snapshot import ModuleView, ProposalView, Snapshot, Viz, plain, to_viz
from engrama.clock import SimClock
from engrama.kernel.branches import branch_name
from engrama.kernel.sensors import Obs
from engrama.lab.explog import ExperienceLog
from engrama.lab.runtime import Runtime
from engrama.mind.recipe import load_recipe
from engrama.modules.affect.pad import pad_label
from engrama.services.generations import (GenerationRecord, append_generation, delete_generation_archive,
                                          load_generations)
from engrama.vocab import EVENT_KINDS, FOOD_IDS, NEED_KEYS, TRAIT_KEYS

__all__ = ["Host", "RestPolicy", "Snapshot", "Viz", "to_viz", "main"]

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


class _GenerationsProvider:
    """Adapter the Generations panel (F10) talks to: the registry file plus per-generation archive folders."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def records(self) -> list[GenerationRecord]:
        return load_generations(self.data_dir / "generations.json")

    def delete_archive(self, n: int) -> None:
        delete_generation_archive(self.data_dir, n)


class Host:
    def __init__(self, cfg, data_dir: Path, recipe_path: Path, seed: int | None = None,
                 clock: SimClock | None = None, *, wall_fn: Callable[[], float] | None = None,
                 ram_free_mb_fn: Callable[[], float] = system_ram_free_mb) -> None:
        self.cfg = cfg
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


# ---- app entry point (composition root; everything below is wiring only) ---------------------------------

def _build_persona(snap: Snapshot, memory):
    from engrama.services.language.persona import PersonaState
    needs = sorted(((v, n) for n, v in snap.needs.items() if v > 0.6), reverse=True)
    liking = sorted(snap.food_liking.items(), key=lambda kv: kv[1])
    try:
        memories = memory.recent(3)
    except Exception:
        memories = []
    return PersonaState(
        stage=snap.stage, needs_top=[n for _, n in needs], traits=dict(snap.traits), mood=snap.pad_label,
        curious=snap.surprise > B.SURPRISE_CURIOUS,
        favorites=[f for f, v in reversed(liking) if v > 0][:2],
        disliked=[f for f, v in liking if v < 0][:2],
        memories=list(memories))


class _MemoryProvider:
    """Adapter the Memories panel (F7) talks to: MemoryStore + WorkingMemory behind the duck-typed protocol."""

    def __init__(self, memory, working, language=None) -> None:
        self.memory, self.working, self.language = memory, working, language

    @staticmethod
    def _lang() -> str:
        from engrama.app import i18n
        return i18n.get_lang()

    def facts(self) -> list[tuple[str, str]]:
        return [(r["key"], r["value"]) for r in self.memory.fact_rows()]

    def topics(self) -> list[tuple[str, bool]]:
        cur = set(self.memory.current_topics(10 ** 6))
        return [(r["name"], r["name"] in cur) for r in self.memory.topic_rows()]

    def opinions(self) -> list[tuple[str, str]]:
        from engrama.services.memory.opinions import stance_word
        lang = self._lang()
        return [(r["topic"], r["phrase"] or stance_word(r["stance"], lang))
                for r in self.memory.opinion_rows() if r["confidence"] > 0]

    def reflections(self) -> list[str]:
        return list(self.memory.recent_reflections(5))

    def _embed_state(self) -> tuple[str, dict]:
        """(embedder status, vector counts). Reads only what is already known; never calls the embedder."""
        lang = self.language
        if lang is None:
            try:
                counts = self.memory.vector_counts()
            except Exception:
                counts = {}
            return "off", counts
        try:
            status = str(getattr(lang, "embed_status", "off") or "off")
        except Exception:
            status = "off"
        try:
            counts = dict(lang.embed_counts() or {})
        except Exception:
            counts = {}
        return status, counts

    SUMMARY_TTL_S = 2.0   # the Mind View asks every frame; the counts are COUNT(*) queries

    def _counts(self, status: str) -> dict:
        """Counts behind summary(), refreshed at most every SUMMARY_TTL_S (or when the embedder status changes
        or something is deleted through this adapter)."""
        now = time.monotonic()
        c = getattr(self, "_cache", None)
        if c is not None and c[2] == status and now - c[0] < self.SUMMARY_TTL_S:
            return c[1]
        refl = self.memory.recent_reflections(1)
        _, vcounts = self._embed_state()
        data = {"episodes": len(self.memory.recent(10 ** 6)), "facts": len(self.memory.fact_rows()),
                "topics": len(self.memory.topic_rows()),
                "opinions": len([r for r in self.memory.opinion_rows() if r["confidence"] > 0]),
                "last_reflection": refl[0] if refl else "",
                "vectors": int(vcounts.get("vectors", 0) or 0), "items": int(vcounts.get("items", 0) or 0)}
        self._cache = (now, data, status)
        return data

    def _invalidate(self) -> None:
        self._cache = None

    def summary(self) -> dict:
        lang = self.language
        try:
            status = str(getattr(lang, "embed_status", "off") or "off") if lang is not None else "off"
        except Exception:
            status = "off"
        data = dict(self._counts(status))
        vectors = data["vectors"]
        # "on" when the embedder is ready, or when vectors are stored and the embedder is not off
        data["semantic"] = "on" if (status == "ready" or (vectors > 0 and status != "off")) else "words"
        return data

    def _drop_working(self, needles: list[str]) -> None:
        from engrama.services.memory.topics import plain_text
        needles = [plain_text(n) for n in needles if n]
        keep = [m for m in self.working.messages()
                if not any(n and n in plain_text(m.get("content", "")) for n in needles)]
        self.working.clear()
        for m in keep:
            self.working.add(m["role"], m["content"])

    def delete_fact(self, key: str) -> None:
        value = next((v for k, v in self.facts() if k == key), "")
        self.memory.delete_fact(key)
        self._invalidate()
        self._drop_working([value, key.replace("_", " ")])

    def delete_topic(self, name: str) -> None:
        from engrama.services.memory.topics import SYNONYMS, normalize_topic
        key = normalize_topic(name)
        try:
            perceived = any(r["name"] == key and r.get("source") == "percepcao" for r in self.memory.topic_rows())
        except Exception:
            perceived = False
        self.memory.delete_topic(name)
        self._invalidate()
        if perceived:   # a deleted screen-derived theme stays silenced (and is listed in F8 to undo)
            self.memory.silence_theme(name)
        self._drop_working([key] + [k for k, v in SYNONYMS.items() if v == key])

    def forget_all(self) -> None:
        self.memory.forget_all_about_user()
        self._invalidate()
        self.working.clear()


class _PerceptionProvider:
    """Adapter the Permissions panel (F8) talks to."""

    def __init__(self, memory, hotkey_error: Callable[[], str]) -> None:
        self.memory, self._hk = memory, hotkey_error

    def silenced_themes(self) -> list[str]: return self.memory.silenced_themes()
    def unsilence_theme(self, name: str) -> None: self.memory.unsilence_theme(name)
    def clear_app_categories(self) -> None: self.memory.clear_app_categories()
    def hotkey_error(self) -> str: return self._hk() or ""


class _Activity:
    """Last allowed thing the user is doing (a theme, else a category), kept in memory only.

    Never holds a title or process: the service only emits categories/themes. A private app yields None."""

    def __init__(self, post: Callable[[str, dict | None], None], theme_sink: Callable[[str, str, str], None]) -> None:
        self._post, self._sink = post, theme_sink
        self._category: str | None = None
        self._theme: str | None = None

    def post(self, kind: str, data: dict | None = None) -> None:
        if kind == "app_focus":
            cat = (data or {}).get("category")
            if cat != self._category:
                self._category, self._theme = cat, None
        self._post(kind, data)

    def on_theme(self, process: str, title: str, category: str) -> None:
        from engrama.services.perception.themes import extract_theme
        self._sink(process, title, category)
        theme = extract_theme(process, title, category)
        if theme:
            self._theme = theme

    def current(self) -> str | None:
        from engrama.services.perception import PRIVATE
        if self._category is None or self._category == PRIVATE:
            return None
        return self._theme or self._category


def _memory_provider(memory, working, language=None) -> _MemoryProvider:
    return _MemoryProvider(memory, working, language)


class _NullServer:
    """Stands in for OllamaServer under --no-llm: never available, never spawns anything."""
    started_by_us = False

    def available(self) -> bool: return False
    def running(self) -> bool: return False
    def start(self) -> bool: return False
    def stop(self) -> None: pass


def open_in_display_mode(window, cfg) -> bool:
    """Reopen in the saved display mode; if the overlay is unavailable the window stays in the terrarium."""
    if getattr(cfg, "display_mode", "terrarium") != "overlay":
        return False
    try:
        return bool(window.set_mode("overlay"))
    except Exception:
        logging.getLogger("engrama.app").exception("overlay start failed")
        return False


def main(argv: list[str] | None = None) -> int:
    held: list = []
    try:
        return _main(argv, held)
    finally:
        for lk in held:
            lk.release()


def _main(argv: list[str] | None, held: list) -> int:
    import argparse
    import signal
    import sys
    import pygame
    from engrama.app.ui.menus import ModelsPanel, SettingsPanel
    from engrama.app.ui.window import Window
    from engrama.config import Config, default_data_dir
    from engrama.services.language.client import OllamaClient
    from engrama.services.language.embedder import Embedder
    from engrama.services.language.lang import detect_lang
    from engrama.services.language.persona import valence
    from engrama.services.language.server import OllamaServer
    from engrama.services.language.service import LanguageService
    from engrama.services.language.initiative import InitiativePolicy
    from engrama.services.memory import ACTIVE_WINDOW_S
    from engrama.services.memory.opinions import innate_lean
    from engrama.services.memory.store import MemoryStore, WorkingMemory
    from engrama.services.perception.blocklist import Blocklist
    from engrama.services.perception.categories import Categorizer
    from engrama.services.perception.files import read_dropped
    from engrama.services.perception.hotkey import GlobalHotkey
    from engrama.services.perception.service import PerceptionService
    from engrama.services.perception.sources import ScriptedSources, make_sources
    from engrama.services.perception.themes import make_theme_sink

    ap =argparse.ArgumentParser(prog="engrama", description="Engrama: a local virtual companion.")
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--recipe", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--time-scale", type=float, default=None)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="never start or contact Ollama (babble only)")
    ap.add_argument("--frames", type=int, default=None, help="exit after N frames (smoke test; unthrottled)")
    ap.add_argument("--seconds", type=float, default=None, help="exit after S wall seconds (bench)")
    ap.add_argument("--eyes", choices=["toggle"], default=None,
                    help="signal the running instance to open/close its eyes, then exit")
    ap.add_argument("--fake-perception", action="store_true", help="bench: scripted machine instead of the real one")
    a = ap.parse_args(argv)

    data_dir = Path(a.data_dir) if a.data_dir else default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    from engrama.app.instance import InstanceLock, send_eyes_toggle
    if a.eyes == "toggle":
        cfg0 = Config.load(data_dir / "config.json") if (data_dir / "config.json").exists() else None
        if cfg0 is not None and cfg0.ui_lang in ("pt", "en"):
            i18n.set_lang(cfg0.ui_lang)
        return send_eyes_toggle(data_dir)
    lock = InstanceLock(data_dir)
    if not lock.acquire():
        print("O Engrama já está aberto nesta pasta de dados. / "
              "Engrama is already running for this data dir.", file=sys.stderr)
        return 1
    held.append(lock)
    cfg_path = data_dir / "config.json"
    if cfg_path.exists():
        cfg = Config.load(cfg_path)
    else:
        cfg = Config(data_dir=data_dir)
        cfg.save(cfg_path)
    cfg.data_dir = data_dir
    if a.time_scale is not None:
        cfg.time_scale = a.time_scale
    if cfg.ui_lang in ("pt", "en"):
        i18n.set_lang(cfg.ui_lang)
    recipe = a.recipe or Path(__file__).resolve().parents[2] / "recipes" / f"{cfg.recipe}.toml"

    host = Host(cfg, data_dir, recipe, seed=a.seed)
    memory = MemoryStore(data_dir / "memory.sqlite")
    working = WorkingMemory()
    server = _NullServer() if a.no_llm else OllamaServer(cfg)
    language = None
    window = None
    start_thread = None
    perception = None
    hotkey = None
    try:
        def food_name(food_id: str, lang: str) -> str:
            return i18n._table(lang if lang in ("pt", "en") else "en").get(f"food.{food_id}", food_id)

        def lean_fn(topic: str) -> float:
            snap0 = host.snapshot()
            return innate_lean(int((snap0.look or {}).get("seed", 0) or 0), topic,
                               dict(snap0.traits or {}))

        client = OllamaClient(cfg)
        embedder = None if a.no_llm else Embedder(client, cfg)   # --no-llm: no embedding calls at all
        language = LanguageService(
            client, server, cfg, memory, working,
            get_state=lambda: _build_persona(host.snapshot(), memory), food_name=food_name,
            idle=lambda: not host.snapshot().resting, lean_fn=lean_fn, now_fn=time.time, embedder=embedder)
        embed_log = logging.getLogger("engrama.app")
        last_embed = ""
        policy = InitiativePolicy(memory, time.time)
        last_input = float("-inf")
        next_policy = 0.0
        next_forget = 0.0
        if not a.no_llm:   # never block the window on Ollama start-up
            start_thread = threading.Thread(target=server.start, daemon=True, name="ollama-start")
            start_thread.start()

        window = Window(host.snapshot, host.post, language=language, set_rest=host.set_rest,
                        set_time_scale=host.set_time_scale,
                        valence_fn=lambda text: valence(text, detect_lang(text, "pt")))
        window.config = cfg
        host.attach_services(memory, working, language)
        window.generations_provider = host.generations_provider
        window.on_farewell_skip = host.skip_farewell
        window.memory_provider = _memory_provider(memory, working, language)
        window.save_config = lambda: cfg.save(cfg_path)
        window.dev = bool(a.dev or cfg.dev_mode)
        from engrama.app.desktop import get_desktop
        window.desktop = get_desktop()
        window.on_digital = host.fulfill_digital

        eyes_lock = threading.Lock()

        def set_eyes(on: bool) -> None:
            """Persist + apply the eyes-closed state; called from the UI (F9) and the hotkey thread."""
            with eyes_lock:
                cfg.eyes_closed = bool(on)
                try:
                    cfg.save(cfg_path)
                except Exception:
                    logging.getLogger("engrama.app").exception("config save failed")
                host.set_eyes_closed(cfg.eyes_closed)

        def toggle_eyes() -> None:
            set_eyes(not cfg.eyes_closed)

        eyes_flag = threading.Event()
        if hasattr(signal, "SIGUSR1"):
            try:
                signal.signal(signal.SIGUSR1, lambda *_: eyes_flag.set())   # handler only sets the flag
            except ValueError:   # not the main thread
                pass

        activity = _Activity(host.post, make_theme_sink(memory, time.time))
        host.theme_fn = lambda: (activity.current() or "") if cfg.permissions.get("process") else ""

        def say(key: str) -> None:   # a short creature line through the same queue the language service feeds
            try:
                from engrama.services.language.service import Reply
                lang = i18n.get_lang()
                language.replies.put(Reply(i18n.t(key), lang, "babble"))
            except Exception:
                logging.getLogger("engrama.app").exception("digital line failed")

        host.on_digital_ask = lambda did: say(f"digital.ask.{did}")
        host.on_digital_thanks = lambda did: say("digital.thanks")
        sources = ScriptedSources() if a.fake_perception else make_sources()
        try:
            from engrama.osapi.session import detect as _detect_session
            _s = _detect_session()
            logging.getLogger("engrama.app").info(
                "session platform=%s kind=%s compositor=%s sources=%s", _s.platform, _s.kind,
                _s.compositor or "-", getattr(sources, "backends", "") or type(sources).__name__)
        except Exception:
            pass
        perception = PerceptionService(
            activity.post, sources, lambda: cfg,
            lambda: cfg.eyes_closed, on_theme=activity.on_theme, on_heavy=host.set_heavy_pc,
            categorize=Categorizer(memory, language))
        hotkey = GlobalHotkey(cfg.eyes_hotkey, toggle_eyes)

        def on_file_drop(path: str) -> bool:
            glimpse = read_dropped(path, Blocklist(list(cfg.perception_blocklist)))
            if glimpse is None:
                return False
            language.share_file(glimpse)
            return True

        window.set_eyes_closed = set_eyes
        window.on_file_drop = on_file_drop
        window.perception_provider = _PerceptionProvider(memory, lambda: hotkey.error)
        window.panels["models"] = lambda w: ModelsPanel(w)
        window.panels["settings"] = lambda w: SettingsPanel(w)

        def on_rest(resting: bool, reason: str) -> None:
            if resting:
                language.unload()
        host.on_event = window.on_host_event
        host.on_rest_change = on_rest
        host.start()
        perception.start()
        if not a.fake_perception:   # Windows RegisterHotKey, X11 XGrabKey; inert (error code) elsewhere
            hotkey.start()
        open_in_display_mode(window, cfg)

        clock = pygame.time.Clock()
        n, t0 = 0, time.monotonic()
        while window.running and (a.frames is None or n < a.frames)                 and (a.seconds is None or time.monotonic() - t0 < a.seconds):
            for e in pygame.event.get():
                if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT):
                    last_input = time.time()
                window.handle_event(e)
            if not window.running:
                break
            if eyes_flag.is_set():
                eyes_flag.clear()
                toggle_eyes()
            host.want_viz = window.panel_name == "mind"
            window.farewell_text = host.farewell_text
            now_w = time.time()
            language.tick(now_w)
            if embedder is not None:   # one line per change: state and model name only, never memory text
                st = language.embed_status
                if st != last_embed:
                    last_embed = st
                    embed_log.info("embedder status=%s model=%s", st, embedder.model or "-")
            if now_w >= next_forget:   # at startup, then every 6 h of wall time
                next_forget = now_w + FORGET_EVERY_S
                try:
                    memory.forget()
                except Exception:
                    logging.getLogger("engrama.app").exception("memory.forget failed")
            if now_w >= next_policy:
                next_policy = now_w + 1.0
                try:
                    snap = host.snapshot()
                    res = policy.update(
                        now_w, stage=snap.stage, user_active=now_w - last_input < ACTIVE_WINDOW_S,
                        llm_ready=language.status == "ready", resting=snap.resting,
                        fullscreen=snap.rest_reason == "fullscreen", action=snap.action,
                        activity=activity.current() if cfg.permissions.get("process") else None,
                        eyes_closed=cfg.eyes_closed)
                    if res:
                        language.spontaneous(res[0], res[1])
                except Exception:
                    logging.getLogger("engrama.app").exception("initiative failed")
            window.frame()
            n += 1
            if a.frames is None:
                clock.tick(window.target_fps)
    finally:
        if window is not None:
            try:
                window.close_panel()
                pygame.display.quit()
            except Exception:
                pass
        if perception is not None:
            perception.stop()
            closer = getattr(getattr(perception, "_src", None), "close", None)
            if callable(closer):
                closer()
        if hotkey is not None:
            hotkey.stop()
        host.stop()
        if language is not None:
            language.shutdown()
        if server.started_by_us:
            server.stop()
        try:
            memory.close()
        except Exception:
            pass
    return 0
