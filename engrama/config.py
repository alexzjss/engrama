import json
from dataclasses import dataclass, field, fields
from pathlib import Path


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _default_permissions() -> dict[str, bool]:
    return {"time": False, "idle": False, "active_window": False, "process": False, "system_load": False}


@dataclass
class Config:
    data_dir: Path = field(default_factory=default_data_dir)
    ollama_exe: Path = Path(r"E:\Ollama\ollama.exe")
    ollama_home: Path = Path(r"E:\Ollama\home")
    ollama_models: Path = Path(r"E:\Ollama\models")
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
                v = Path(v)
            elif f.name == "recommended_models":
                v = tuple(v)
            elif f.name == "permissions":
                v = {**_default_permissions(), **v}
            elif f.name == "perception_blocklist":
                v = [str(x) for x in v]
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
