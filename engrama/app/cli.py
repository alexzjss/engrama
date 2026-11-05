"""Command-line entry point of the app: the composition root (moved out of host.py, unchanged)."""
from __future__ import annotations
import logging
import threading
import time
from pathlib import Path

from engrama.app import i18n
from engrama.resources import recipes_dir
from engrama.app.host import FORGET_EVERY_S, Host
from engrama.app.providers import (_Activity, _build_persona, _memory_provider, _NullServer, _PerceptionProvider)


def open_in_display_mode(window, cfg) -> bool:
    """Reopen in the saved display mode; if the overlay is unavailable the window stays in the terrarium."""
    if getattr(cfg, "display_mode", "terrarium") != "overlay":
        return False
    try:
        return bool(window.set_mode("overlay"))
    except Exception:
        logging.getLogger("engrama.app").exception("overlay start failed")
        return False


def resolve_recipe_arg(arg: str | Path) -> Path | None:
    """`--recipe X`: an existing path, else `recipes/X.toml` (with or without the extension); None if neither."""
    p = Path(arg)
    if p.exists():
        return p
    q = recipes_dir() / (p.name if p.suffix == ".toml" else p.name + ".toml")
    return q if q.exists() else None


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
    ap.add_argument("--recipe", type=str, default=None,
                    help="recipe name (recipes/NAME.toml) or path; only for a new data dir (a saved creature keeps its own)")
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

    requested = None
    if a.recipe is not None:
        requested = resolve_recipe_arg(a.recipe)
        if requested is None:
            print(f"Receita não encontrada: {a.recipe} (use um nome de recipes/ ou um caminho). / "
                  f"Recipe not found: {a.recipe} (use a name from recipes/ or a path).", file=sys.stderr)
            return 2
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
    recipe = requested or recipes_dir() / f"{cfg.recipe}.toml"

    host = Host(cfg, data_dir, recipe, seed=a.seed, warn_recipe_mismatch=requested is not None)
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
