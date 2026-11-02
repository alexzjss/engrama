"""The live host: the composition root that runs the v2 Runtime on a single simulation thread.

The UI only reads `snapshot()` (an immutable copy swapped by reference) and publishes events with `post()`.
Callbacks (`on_event`, `on_rest_change`) run on the simulation thread; keep them quick and thread-safe.
"""
from __future__ import annotations
import collections
import json
import os
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from engrama import balance as B
from engrama.app.rest import RestPolicy, system_ram_free_mb
from engrama.app.snapshot import ModuleView, ProposalView, Snapshot, Viz, plain, to_viz
from engrama.clock import SimClock
from engrama.kernel.sensors import Obs
from engrama.lab.explog import ExperienceLog
from engrama.lab.runtime import Runtime
from engrama.mind.recipe import load_recipe
from engrama.modules.affect.pad import pad_label
from engrama.vocab import EVENT_KINDS, FOOD_IDS, NEED_KEYS, TRAIT_KEYS

__all__ = ["Host", "RestPolicy", "Snapshot", "Viz", "to_viz", "main"]

_INPUT_KINDS = frozenset({"click", "pet", "message", "food", "user_active", "answered"})
_POST_CAP = 1000
_VIZ_EVERY_S = 1.0


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

        self._save_dir = self.data_dir / "save"
        self._host_json = self.data_dir / "host.json"
        self._rt, self._types = self._load_or_create(seed)
        self._prev_stage = self._rt.kernel.stage
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
        return rt, types

    def _write_host_json(self, seed: int) -> None:
        tmp = self._host_json.with_name(self._host_json.name + ".tmp")
        tmp.write_text(json.dumps({"wall": self._wall(), "seed": seed}), encoding="utf-8")
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

    def set_rest(self, on: bool) -> None:
        """Manual rest override; applied at the next tick."""
        self.rest_policy.manual = bool(on)

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
        self._emit_changes()
        self._update_rest(wall)
        if wall - self._last_save_wall >= B.AUTOSAVE_S:
            self._save()
        self._snap = self._build_snapshot()

    def _emit_changes(self) -> None:
        k = self._rt.kernel
        stage, action = k.stage, k.action or "idle"
        if stage != self._prev_stage:
            old, self._prev_stage = self._prev_stage, stage
            if old == "egg":
                _safe(self.on_event, "hatch", {"stage": stage})
            else:
                _safe(self.on_event, "evolve", {"from": old, "to": stage})
        if action != self._prev_action:
            old, self._prev_action = self._prev_action, action
            if old:
                _safe(self.on_event, "action_change", {"from": old, "to": action})

    def _update_rest(self, wall: float) -> None:
        k = self._rt.kernel
        reason = self.rest_policy.update(k.world.fullscreen, self._last_input_wall)
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
            resting=self._resting, rest_reason=self._rest_reason)

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


class _NullServer:
    """Stands in for OllamaServer under --no-llm: never available, never spawns anything."""
    started_by_us = False

    def available(self) -> bool: return False
    def running(self) -> bool: return False
    def start(self) -> bool: return False
    def stop(self) -> None: pass


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    import pygame
    from engrama.app import i18n
    from engrama.app.ui.menus import ModelsPanel, SettingsPanel
    from engrama.app.ui.window import Window
    from engrama.config import Config, default_data_dir
    from engrama.services.language.client import OllamaClient
    from engrama.services.language.lang import detect_lang
    from engrama.services.language.persona import valence
    from engrama.services.language.server import OllamaServer
    from engrama.services.language.service import LanguageService
    import logging
    from engrama.services.language.initiative import InitiativePolicy
    from engrama.services.memory import ACTIVE_WINDOW_S
    from engrama.services.memory.opinions import innate_lean
    from engrama.services.memory.store import MemoryStore, WorkingMemory

    ap =argparse.ArgumentParser(prog="engrama", description="Engrama: a local virtual companion.")
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--recipe", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--time-scale", type=float, default=None)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="never start or contact Ollama (babble only)")
    ap.add_argument("--frames", type=int, default=None, help="exit after N frames (smoke test; unthrottled)")
    ap.add_argument("--seconds", type=float, default=None, help="exit after S wall seconds (bench)")
    a = ap.parse_args(argv)

    data_dir = Path(a.data_dir) if a.data_dir else default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
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
    try:
        def food_name(food_id: str, lang: str) -> str:
            return i18n._table(lang if lang in ("pt", "en") else "en").get(f"food.{food_id}", food_id)

        def lean_fn(topic: str) -> float:
            snap0 = host.snapshot()
            return innate_lean(int((snap0.look or {}).get("seed", 0) or 0), topic,
                               dict(snap0.traits or {}))

        language = LanguageService(
            OllamaClient(cfg), server, cfg, memory, working,
            get_state=lambda: _build_persona(host.snapshot(), memory), food_name=food_name,
            idle=lambda: not host.snapshot().resting, lean_fn=lean_fn)
        policy = InitiativePolicy(memory, time.time)
        last_input = float("-inf")
        next_policy = 0.0
        if not a.no_llm:   # never block the window on Ollama start-up
            start_thread = threading.Thread(target=server.start, daemon=True, name="ollama-start")
            start_thread.start()

        window = Window(host.snapshot, host.post, language=language, set_rest=host.set_rest,
                        set_time_scale=host.set_time_scale,
                        valence_fn=lambda text: valence(text, detect_lang(text, "pt")))
        window.config = cfg
        window.save_config = lambda: cfg.save(cfg_path)
        window.dev = bool(a.dev or cfg.dev_mode)
        window.panels["models"] = lambda w: ModelsPanel(w)
        window.panels["settings"] = lambda w: SettingsPanel(w)

        def on_rest(resting: bool, reason: str) -> None:
            if resting:
                language.unload()
        host.on_event = window.on_host_event
        host.on_rest_change = on_rest
        host.start()

        clock = pygame.time.Clock()
        n, t0 = 0, time.monotonic()
        while window.running and (a.frames is None or n < a.frames)                 and (a.seconds is None or time.monotonic() - t0 < a.seconds):
            for e in pygame.event.get():
                if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT):
                    last_input = time.time()
                window.handle_event(e)
            if not window.running:
                break
            host.want_viz = window.panel_name == "mind"
            now_w = time.time()
            language.tick(now_w)
            if now_w >= next_policy:
                next_policy = now_w + 1.0
                try:
                    snap = host.snapshot()
                    res = policy.update(
                        now_w, stage=snap.stage, user_active=now_w - last_input < ACTIVE_WINDOW_S,
                        llm_ready=language.status == "ready", resting=snap.resting,
                        fullscreen=snap.rest_reason == "fullscreen", action=snap.action)
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
