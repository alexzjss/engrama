"""Permission-gated perception loop.

Check order on every source read: eyes closed -> permission -> blocklist -> sanitize.
Process names and titles never leave this module except category / allowed theme.
"""
import logging
import threading
import time

from . import FULLSCREEN_POLL_S, HEAVY_CPU_PCT, HEAVY_FOR_S, IDLE_AFTER_S, PRIVATE
from .blocklist import Blocklist
from .categories import table_category

log = logging.getLogger("engrama.perception")


class PerceptionService:
    def __init__(self, post, sources, get_config, eyes_closed, now_fn=time.time,
                 on_theme=None, on_heavy=None, categorize=None):
        self._post = post
        self._src = sources
        self._cfg = get_config
        self._eyes = eyes_closed
        self._now = now_fn
        self._on_theme = on_theme
        self._on_heavy = on_heavy
        self._categorize = categorize or (lambda p: table_category(p) or "programa")
        self._next_main = 0.0
        self._next_fast = 0.0
        self._category: str | None = None
        self._idle: bool | None = None
        self._fullscreen: bool | None = None
        self._heavy_since: float | None = None
        self._heavy = False
        self._last_err: dict[str, float] = {}
        self._blk_key: tuple | None = None
        self._blk: Blocklist | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- lifecycle
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="perception", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t:
            t.join(0.5)

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            try:
                self.tick(self._now())
            except Exception as e:
                self._warn("loop", e, self._now())

    # ---- helpers
    def _warn(self, source: str, exc: Exception, now: float) -> None:
        # Only the source name and exception type: messages may carry process names.
        if now - self._last_err.get(source, -1e9) >= 60:
            self._last_err[source] = now
            log.warning("perception source %s failed (%s)", source, type(exc).__name__)

    def _allowed(self, *keys: str) -> bool:
        """Evaluated right before each read, so mid-cycle changes apply immediately."""
        try:
            if self._eyes():
                return False
            cfg = self._cfg()
            if not getattr(cfg, "perception_asked", False):
                return False
            perms = getattr(cfg, "permissions", {}) or {}
            return any(perms.get(k, False) for k in keys)
        except Exception:
            return False

    def _perm(self, key: str) -> bool:
        try:
            perms = getattr(self._cfg(), "permissions", {}) or {}
            return bool(perms.get(key, False))
        except Exception:
            return False

    def _read(self, name: str, fn, now: float):
        try:
            return fn()
        except Exception as e:  # includes psutil.NoSuchProcess
            self._warn(name, e, now)
            return None

    def _blocklist(self) -> Blocklist:
        entries = tuple(getattr(self._cfg(), "perception_blocklist", None) or ())
        if self._blk is None or entries != self._blk_key:
            self._blk_key, self._blk = entries, Blocklist(list(entries))
        return self._blk

    # ---- one cycle
    def tick(self, now: float) -> None:
        if self._eyes():
            return
        try:
            interval = float(getattr(self._cfg(), "perception_interval_s", 30.0))
        except Exception:
            interval = 30.0
        if now >= self._next_fast:
            self._next_fast = now + FULLSCREEN_POLL_S
            self._fast(now)
        if now >= self._next_main:
            self._next_main = now + max(1.0, interval)
            self._main(now)

    def _fast(self, now: float) -> None:
        if self._allowed("system_load"):
            fs = self._read("fullscreen", self._src.is_fullscreen, now)
            if fs is not None and bool(fs) != self._fullscreen:
                self._fullscreen = bool(fs)
                self._post("fullscreen_on" if fs else "fullscreen_off", {})
        if self._allowed("system_load"):
            cpu = self._read("cpu", self._src.cpu_percent, now)
            if cpu is not None:
                self._update_heavy(float(cpu) > HEAVY_CPU_PCT, now)

    def _update_heavy(self, hot: bool, now: float) -> None:
        if not hot:
            self._heavy_since = None
            if self._heavy:
                self._heavy = False
                self._notify_heavy(False)
            return
        if self._heavy_since is None:
            self._heavy_since = now
        if not self._heavy and now - self._heavy_since >= HEAVY_FOR_S:
            self._heavy = True
            self._notify_heavy(True)

    def _notify_heavy(self, on: bool) -> None:
        if self._on_heavy:
            try:
                self._on_heavy(on)
            except Exception as e:
                self._warn("heavy", e, self._now())

    def _main(self, now: float) -> None:
        if self._allowed("idle"):
            idle = self._read("idle", self._src.idle_seconds, now)
            if idle is not None:
                is_idle = float(idle) >= IDLE_AFTER_S
                if is_idle != self._idle:
                    self._idle = is_idle
                    self._post("user_idle" if is_idle else "user_active", {"source": "system"})
        if self._allowed("process", "active_window"):
            fg = self._read("foreground", self._src.foreground, now)
            if fg:
                self._handle_foreground(fg, now)

    def _handle_foreground(self, fg, now: float) -> None:
        try:
            process, title = str(fg[0] or "").lower(), str(fg[1] or "")
        except Exception:
            return
        if not process and not title:
            return
        if self._blocklist().is_blocked(process, title):
            self._set_category(PRIVATE)
            return
        cat = self._category if self._category not in (None, PRIVATE) else "programa"
        if self._perm("process"):
            try:
                cat = self._categorize(process) if process else "programa"
            except Exception as e:
                self._warn("categorize", e, now)
                cat = "programa"
            self._set_category(cat)
        if self._on_theme and self._allowed("active_window"):
            try:
                self._on_theme(process, title, cat)
            except Exception as e:
                self._warn("theme", e, now)

    def _set_category(self, cat: str) -> None:
        if not self._perm("process"):
            return
        if cat != self._category:
            self._category = cat
            self._post("app_focus", {"category": cat})
