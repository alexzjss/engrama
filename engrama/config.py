import json
import re
import shutil
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Callable, Mapping

from engrama.vocab import DISPLAY_MODES

_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def default_data_dir() -> Path:
    import os
    from engrama.paths import resolve_data_dir
    return resolve_data_dir(None, os.environ, sys.platform, Path.home(), Path(__file__).resolve().parent)


def _windows_ollama_candidates(env: Mapping[str, str]) -> list[Path]:
    out = []
    if env.get("LOCALAPPDATA"):
        out.append(Path(env["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe")   # official installer
    if env.get("ProgramFiles"):
        out.append(Path(env["ProgramFiles"]) / "Ollama" / "ollama.exe")
    return out


def default_ollama_exe(platform: str | None = None, env: Mapping[str, str] | None = None,
                       exists: Callable[[Path], bool] | None = None, which=None) -> Path:
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        import os
        env = os.environ if env is None else env
        exists = exists or (lambda p: p.exists())
        found = (which or shutil.which)("ollama")
        if found:
            return Path(found)
        cands = _windows_ollama_candidates(env)
        for c in cands:
            if exists(c):
                return c
        # Not installed: keep the official install location, which does not exist yet, so the
        # UI says "Ollama not found" (server.available() is False) and nothing crashes.
        return cands[0] if cands else Path("ollama.exe")
    found = (which or shutil.which)("ollama")
    return Path(found) if found else Path("/usr/local/bin/ollama")


def _default_ollama_home(platform: str | None = None) -> Path | None:
    return None


def _default_ollama_models(platform: str | None = None) -> Path | None:
    return None


def _default_permissions() -> dict[str, bool]:
    return {"time": False, "idle": False, "active_window": False, "process": False, "system_load": False}


@dataclass
class Config:
    data_dir: Path = field(default_factory=default_data_dir)
    ollama_exe: Path = field(default_factory=default_ollama_exe)
    ollama_home: Path | None = field(default_factory=_default_ollama_home)     # None = do not touch HOME
    ollama_models: Path | None = field(default_factory=_default_ollama_models)  # None = do not set OLLAMA_MODELS
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:1.7b"
    keep_alive_s: float = 600.0
    recommended_models: tuple[str, ...] = ("qwen3:1.7b", "qwen3:0.6b", "gemma3:1b", "llama3.2:1b")
    recipe: str = "default-v1"
    ui_lang: str | None = None
    time_scale: float = 1.0
    dev_mode: bool = False
    permissions: dict[str, bool] = field(default_factory=_default_permissions)
    perception_asked: bool = False
    eyes_closed: bool = False
    perception_interval_s: float = 30.0
    perception_blocklist: list[str] = field(default_factory=list)
    eyes_hotkey: str = "ctrl+alt+e"
    display_mode: str = "terrarium"   # M7: "terrarium" | "overlay"; unknown values load as "terrarium"
    embed_model: str = "embeddinggemma"          # M9: "" = semantic recall off
    semantic_recall: bool = True
    recommended_embed_models: tuple[str, ...] = ("embeddinggemma", "nomic-embed-text", "bge-m3")
    creature_name: str = ""                      # given by the user after the hatch (or in Settings); "" = unnamed

    @classmethod
    def load(cls, path: Path) -> "Config":
        path = Path(path)
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        raw = json.loads(path.read_text(encoding="utf-8"))
        kwargs = {}
        for f in fields(cls):
            if f.name not in raw:
                continue
            v = raw[f.name]
            if f.name in ("data_dir", "ollama_exe", "ollama_home", "ollama_models"):
                if f.name in ("ollama_exe", "ollama_home", "ollama_models") and sys.platform != "win32" \
                        and isinstance(v, str) and _WINDOWS_PATH.match(v):
                    # M8: a Windows path saved on another machine is replaced by the Linux default
                    v = default_ollama_exe() if f.name == "ollama_exe" else None
                elif v is not None:
                    v = Path(v)
            elif f.name == "recommended_models":
                v = tuple(v)
            elif f.name == "permissions":
                v = {**_default_permissions(), **v}
            elif f.name == "perception_blocklist":
                v = [str(x) for x in v]
            elif f.name == "display_mode":
                v = v if v in DISPLAY_MODES else "terrarium"
            elif f.name == "embed_model":
                v = str(v or "")
            elif f.name == "semantic_recall":
                v = bool(v)
            elif f.name == "recommended_embed_models":
                v = tuple(str(x) for x in v)
            kwargs[f.name] = v
        return cls(**kwargs)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        for k, v in d.items():
            if isinstance(v, Path):
                d[k] = str(v)
            elif isinstance(v, tuple):
                d[k] = list(v)
        path.write_text(json.dumps(d, indent=2), encoding="utf-8")
