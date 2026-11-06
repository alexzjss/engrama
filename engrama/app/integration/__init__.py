"""Desktop integration (menu entry, Start menu shortcut, opt-in autostart).

Every OS touch goes through an injectable facade so tests never see the real HOME, registry or PowerShell."""
from __future__ import annotations
import sys
from pathlib import Path

MARKER = "engrama-managed"   # written into every file we create; uninstall only removes files that carry it


def launch_command(frozen: bool | None = None, executable: str | None = None) -> list[str]:
    """Bundle: the bundled executable. Installed: `<python> -m engrama`."""
    exe = executable or sys.executable
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return [exe] if frozen else [exe, "-m", "engrama"]


def is_dev(package_root: Path | None = None) -> bool:
    from engrama.paths import is_dev_checkout
    root = package_root or Path(__file__).resolve().parents[2]
    return (not getattr(sys, "frozen", False)) and is_dev_checkout(root)


def icon_png() -> Path | None:
    from engrama.resources import _pkg_dir
    p = _pkg_dir("app", "assets") / "icon-256.png"
    return p if p.is_file() else None


def icon_ico() -> Path | None:
    from engrama.resources import _pkg_dir
    p = _pkg_dir("app", "assets") / "icon.ico"
    return p if p.is_file() else None


class Autostart:
    """What the Settings panel talks to. State is always read from the OS; `reason` is set when unavailable."""

    def __init__(self, backend, dev: bool = False) -> None:
        self.backend = backend
        self.dev = dev

    @property
    def available(self) -> bool:
        return not self.dev and self.backend is not None

    def enabled(self) -> bool:
        if not self.available:
            return False
        try:
            return bool(self.backend.autostart_enabled())
        except Exception:
            return False

    def set(self, on: bool) -> bool:
        if not self.available:
            return False
        try:
            self.backend.set_autostart(bool(on))
        except Exception:
            return False
        return True


def make_backend(platform: str | None = None, env=None, home: Path | None = None):
    """The facade for this OS, or None where there is none (macOS)."""
    import os
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if platform == "win32":
        from engrama.app.integration.windows import WindowsIntegration
        return WindowsIntegration.real(env)
    if platform.startswith("linux"):
        from engrama.app.integration.linux import LinuxIntegration
        return LinuxIntegration(env=env, home=home or Path.home(), command=launch_command(), icon=icon_png())
    return None


def make_autostart() -> Autostart:
    dev = is_dev()
    return Autostart(None if dev else make_backend(), dev=dev)
