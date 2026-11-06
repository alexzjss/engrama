"""Linux: freedesktop .desktop entry, hicolor icon and an autostart entry. Only files carrying MARKER are removed."""
from __future__ import annotations
from pathlib import Path
from typing import Mapping, Sequence

from engrama.app.integration import MARKER


def _quote(arg: str) -> str:
    """Desktop Entry Exec quoting: double quotes around args with specials, backslash-escape the reserved ones."""
    if arg and not any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    out = arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    return f'"{out}"'


class LinuxIntegration:
    def __init__(self, env: Mapping[str, str], home: Path, command: Sequence[str], icon: Path | None = None) -> None:
        home = Path(home)
        data = Path(env["XDG_DATA_HOME"]) if env.get("XDG_DATA_HOME") else home / ".local" / "share"
        conf = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
        self.desktop_file = data / "applications" / "engrama.desktop"
        self.icon_file = data / "icons" / "hicolor" / "256x256" / "apps" / "engrama.png"
        self.autostart_file = conf / "autostart" / "engrama.desktop"
        self.command = list(command)
        self.icon_src = Path(icon) if icon else None

    def _entry(self, autostart: bool) -> str:
        lines = ["[Desktop Entry]", "Type=Application", "Name=Engrama",
                 "Comment=A local virtual companion", "Comment[pt_BR]=Um companheiro virtual local",
                 "Exec=" + " ".join(_quote(a) for a in self.command), "Icon=engrama",
                 "Terminal=false", "Categories=Game;Utility;", f"X-Engrama-Managed={MARKER}"]
        if autostart:
            lines.append("X-GNOME-Autostart-enabled=true")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _ours(p: Path) -> bool:
        try:
            return p.is_file() and MARKER in p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False

    def _write(self, p: Path, text: str) -> bool:
        """Write only over nothing or over our own file; a foreign file is never touched."""
        if p.exists() and not self._ours(p):
            return False
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return True

    def install(self) -> list[Path]:
        written = []
        if self._write(self.desktop_file, self._entry(False)):
            written.append(self.desktop_file)
        if self.icon_src is not None and self.icon_src.is_file() and not self.icon_file.exists():
            self.icon_file.parent.mkdir(parents=True, exist_ok=True)
            self.icon_file.write_bytes(self.icon_src.read_bytes())
            written.append(self.icon_file)
        elif self.icon_file.exists() and self.icon_src is not None and self.icon_src.is_file() \
                and self.icon_file.read_bytes() == self.icon_src.read_bytes():
            written.append(self.icon_file)
        return written

    def uninstall(self) -> list[Path]:
        removed = []
        for p in (self.desktop_file, self.autostart_file):
            if self._ours(p):
                p.unlink()
                removed.append(p)
        if self.icon_file.is_file() and self.icon_src is not None and self.icon_src.is_file() \
                and self.icon_file.read_bytes() == self.icon_src.read_bytes():
            self.icon_file.unlink()
            removed.append(self.icon_file)
        return removed

    def autostart_enabled(self) -> bool:
        return self._ours(self.autostart_file)

    def set_autostart(self, on: bool) -> None:
        if on:
            self._write(self.autostart_file, self._entry(True))
        elif self._ours(self.autostart_file):
            self.autostart_file.unlink()
