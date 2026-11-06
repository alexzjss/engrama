"""Windows: Start menu shortcut (PowerShell WScript.Shell, no extra dependency) and HKCU Run autostart (winreg)."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from engrama.app.integration import MARKER

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Engrama"


class WinRegistry:
    """HKCU Run key through winreg, imported lazily so Linux/CI can import this module."""

    def get(self, name: str) -> str | None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None

    def set(self, name: str, value: str) -> None:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass


def run_powershell(script: str) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, timeout=30, check=True)
    return r.stdout


def _ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


class WindowsIntegration:
    def __init__(self, start_menu_dir: Path, registry, powershell, command: Sequence[str],
                 icon: Path | None = None) -> None:
        self.shortcut = Path(start_menu_dir) / "Engrama.lnk"
        self.registry = registry
        self.powershell = powershell
        self.command = list(command)
        self.icon = Path(icon) if icon else None

    @classmethod
    def real(cls, env: Mapping[str, str]) -> "WindowsIntegration":
        from engrama.app.integration import icon_ico, launch_command
        appdata = Path(env.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return cls(appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs", WinRegistry(),
                   run_powershell, launch_command(), icon_ico())

    def _run_value(self) -> str:
        return subprocess.list2cmdline(self.command)

    def install(self) -> list[Path]:
        if self.shortcut.exists() and not self._ours():
            return []
        self.shortcut.parent.mkdir(parents=True, exist_ok=True)
        script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + _ps(str(self.shortcut)) + ");"
                  "$s.TargetPath=" + _ps(self.command[0]) + ";"
                  "$s.Arguments=" + _ps(subprocess.list2cmdline(self.command[1:])) + ";"
                  "$s.Description=" + _ps(f"Engrama ({MARKER})") + ";")
        if self.icon is not None and self.icon.is_file():
            script += "$s.IconLocation=" + _ps(str(self.icon)) + ";"
        script += "$s.Save()"
        self.powershell(script)
        return [self.shortcut]

    def _ours(self) -> bool:
        if not self.shortcut.exists():
            return False
        out = self.powershell("(New-Object -ComObject WScript.Shell).CreateShortcut("
                              + _ps(str(self.shortcut)) + ").Description")
        return MARKER in (out or "")

    def uninstall(self) -> list[Path]:
        removed = []
        if self._ours():
            self.shortcut.unlink()
            removed.append(self.shortcut)
        if self.registry.get(RUN_NAME) is not None:
            self.registry.delete(RUN_NAME)
        return removed

    def autostart_enabled(self) -> bool:
        return self.registry.get(RUN_NAME) is not None

    def set_autostart(self, on: bool) -> None:
        if on:
            self.registry.set(RUN_NAME, self._run_value())
        else:
            self.registry.delete(RUN_NAME)
