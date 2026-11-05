import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "engrama"
FORBIDDEN = {
    "kernel": ("engrama.mind", "engrama.modules", "engrama.lab", "engrama.services", "engrama.app", "engrama.osapi"),
    "mind": ("engrama.kernel", "engrama.modules", "engrama.app", "engrama.osapi"),
    "services": ("engrama.mind", "engrama.modules", "engrama.kernel", "engrama.lab", "engrama.app"),
    "osapi": ("engrama",),
    "services/memory": ("engrama.services.language",),   # M9: memory never knows the LLM
}
OSAPI_SELF = "engrama.osapi"
APP_PRESENTATION = ("ui", "art", "audio", "i18n")
APP_ALLOWED = ("engrama.app", "engrama.vocab", "engrama.balance", "engrama.resources")
APP_OSAPI = ("app/desktop.py",)
APP_THIRD_PARTY = {"numpy", "pygame"}
MODULE_ALLOWED = ("engrama.mind", "engrama.vocab", "engrama.balance")
STDLIB = set(sys.stdlib_module_names)


def _package(path: Path, root: Path) -> list[str]:
    return list(path.relative_to(root.parent).parts[:-1])


def _imports(path: Path, root: Path) -> set[str]:
    pkg = _package(path, root)
    out = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg[: len(pkg) - (n.level - 1)]
                mod = ".".join(base + ([n.module] if n.module else []))
            else:
                mod = n.module or ""
            if not mod:
                continue
            out.update(mod if a.name == "*" else f"{mod}.{a.name}" for a in n.names)
    return out


def _under(mod: str, pkg: str) -> bool:
    return mod == pkg or mod.startswith(pkg + ".")


def check(root: Path) -> list[tuple[str, str]]:
    bad = []
    for sub, banned in FORBIDDEN.items():
        for f in sorted((root / sub).rglob("*.py")) if (root / sub).exists() else []:
            for m in _imports(f, root):
                if sub == "osapi" and _under(m, OSAPI_SELF):
                    continue
                if any(_under(m, b) for b in banned):
                    bad.append((f.relative_to(root).as_posix(), m))
                elif sub == "osapi" and m.split(".")[0] not in STDLIB:
                    bad.append((f.relative_to(root).as_posix(), m))
    app = root / "app"
    files = [app / n for n in ("snapshot.py", "desktop.py", "digital.py") if (app / n).exists()]
    for sub in APP_PRESENTATION:
        files += sorted((app / sub).rglob("*.py")) if (app / sub).exists() else []
    for f in files:
        allowed = APP_ALLOWED + ((OSAPI_SELF,) if f.relative_to(root).as_posix() in APP_OSAPI else ())
        for m in _imports(f, root):
            top = m.split(".")[0]
            if top == "engrama":
                if not any(_under(m, a) for a in allowed) or _under(m, "engrama.app.host"):
                    bad.append((f.relative_to(root).as_posix(), m))
            elif top not in APP_THIRD_PARTY and top not in STDLIB:
                bad.append((f.relative_to(root).as_posix(), m))
    mods = root / "modules"
    for f in sorted(mods.rglob("*.py")) if mods.exists() else []:
        pkg = _package(f, root)
        own = ".".join(pkg[:3]) if len(pkg) >= 3 else None
        allowed = MODULE_ALLOWED + ((own,) if own else ())
        for m in _imports(f, root):
            top = m.split(".")[0]
            if top == "engrama":
                if not any(_under(m, a) for a in allowed):
                    bad.append((f.relative_to(root).as_posix(), m))
            elif top != "numpy" and top not in STDLIB:
                bad.append((f.relative_to(root).as_posix(), m))
    return bad


def test_real_tree_respects_dependency_rules():
    assert not check(ROOT)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "engrama"
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return root


def test_detects_relative_imports(tmp_path):
    root = _tree(tmp_path, {
        "kernel/a.py": "from ..mind import contracts\n",
        "mind/b.py": "from ..kernel.a import x\n",
        "modules/drives/c.py": "from ..affect import d\n",
    })
    assert len(check(root)) == 3


def test_from_engrama_import_name_resolved(tmp_path):
    root = _tree(tmp_path, {
        "modules/temporal/ok.py": "from engrama import balance, vocab\nimport numpy\n",
        "modules/temporal/bad.py": "from engrama import kernel\n",
    })
    assert check(root) == [("modules/temporal/bad.py", "engrama.kernel")]


def test_modules_may_not_import_other_families(tmp_path):
    root = _tree(tmp_path, {
        "modules/temporal/snn.py": "from engrama.modules.temporal import x\nfrom . import y\n",
        "modules/drives/d.py": "from engrama.modules.temporal.snn import z\n",
        "modules/e.py": "import engrama.modules.drives\n",
    })
    bad = check(root)
    assert ("modules/drives/d.py", "engrama.modules.temporal.snn.z") in bad
    assert ("modules/e.py", "engrama.modules.drives") in bad
    assert not [b for b in bad if b[0] == "modules/temporal/snn.py"]


def test_app_ui_cannot_import_kernel(tmp_path):
    root = _tree(tmp_path, {
        "app/ui/a.py": "from engrama.kernel import kernel\n",
        "app/art/b.py": "from ...mind import contracts\nimport requests\n",
        "app/i18n/c.py": "from engrama.app.host import Host\n",
        "app/snapshot.py": "from engrama.lab import runtime\n",
        "app/audio/ok.py": "import numpy, pygame, json\nfrom engrama import vocab, balance\nfrom engrama.app import i18n\n",
    })
    bad = check(root)
    assert ("app/ui/a.py", "engrama.kernel.kernel") in bad
    assert ("app/art/b.py", "engrama.mind.contracts") in bad
    assert ("app/art/b.py", "requests") in bad
    assert ("app/i18n/c.py", "engrama.app.host.Host") in bad
    assert ("app/snapshot.py", "engrama.lab.runtime") in bad
    assert not [b for b in bad if b[0] == "app/audio/ok.py"]


def test_app_desktop_and_digital_are_checked(tmp_path):
    root = _tree(tmp_path, {
        "app/desktop.py": "import ctypes\nfrom engrama.kernel import kernel\n",
        "app/digital.py": "import random\nfrom engrama import balance, vocab\nfrom engrama.app.host import Host\n",
    })
    bad = check(root)
    assert ("app/desktop.py", "engrama.kernel.kernel") in bad
    assert ("app/digital.py", "engrama.app.host.Host") in bad
    assert len(bad) == 2


def test_services_cannot_import_mind(tmp_path):
    root = _tree(tmp_path, {
        "services/a.py": "from engrama.mind import contracts\n",
        "services/b.py": "from ..kernel import kernel\n",
        "services/c.py": "from engrama.app import i18n\nfrom engrama.modules import x\nfrom engrama.lab import y\n",
        "services/ok.py": "import json\nfrom engrama.config import Config\n",
    })
    bad = check(root)
    assert len(bad) == 5
    assert not [b for b in bad if b[0] == "services/ok.py"]


def test_kernel_and_mind_cannot_import_app(tmp_path):
    root = _tree(tmp_path, {
        "kernel/a.py": "from engrama.app import i18n\n",
        "mind/b.py": "from ..app import snapshot\n",
    })
    assert len(check(root)) == 2


def test_host_may_import_everything(tmp_path):
    root = _tree(tmp_path, {
        "app/host.py": "from engrama.kernel import kernel\nfrom engrama.mind import scheduler\n"
                       "from engrama.services import persistence\nfrom engrama.lab import runtime\nimport psutil\n",
        "__main__.py": "from engrama.app import host\nfrom engrama.modules import x\n",
    })
    assert check(root) == []


def test_osapi_only_stdlib(tmp_path):
    root = _tree(tmp_path, {
        "osapi/a.py": "from engrama.vocab import x\nimport numpy\nimport json\n",
    })
    assert len(check(root)) == 2


def test_osapi_may_import_itself(tmp_path):
    root = _tree(tmp_path, {
        "osapi/__init__.py": "IPC = 1\n",
        "osapi/session.py": "from engrama.osapi import IPC\n",
    })
    assert check(root) == []


def test_ui_cannot_import_osapi(tmp_path):
    root = _tree(tmp_path, {"app/ui/x.py": "from engrama.osapi import session\n"})
    assert check(root) == [("app/ui/x.py", "engrama.osapi.session")]


def test_desktop_may_import_osapi(tmp_path):
    root = _tree(tmp_path, {"app/desktop.py": "from engrama.osapi.x11 import X11\n"})
    assert check(root) == []


def test_perception_may_import_osapi(tmp_path):
    root = _tree(tmp_path, {"services/perception/sources.py": "from engrama.osapi import session\n"})
    assert check(root) == []


def test_kernel_and_mind_cannot_import_osapi(tmp_path):
    root = _tree(tmp_path, {
        "kernel/a.py": "from engrama.osapi import session\n",
        "mind/b.py": "from ..osapi import session\n",
    })
    assert len(check(root)) == 2


def test_fps_constants_match_m7():
    from engrama import balance

    assert balance.FPS_FOCUSED == 20
    assert balance.FPS_STILL == 10
    assert balance.FPS_UNFOCUSED == 5
    assert balance.FPS_RESTING == 2
    assert balance.FPS_OVERLAY_MOVING == 10


def test_memory_cannot_import_language(tmp_path):
    root = _tree(tmp_path, {
        "services/memory/a.py": "from engrama.services.language.client import OllamaClient\n",
        "services/memory/ok.py": "import numpy\nfrom engrama.services.memory import recall\n",
        "services/language/b.py": "from engrama.services.memory import store\n",
    })
    assert check(root) == [("services/memory/a.py", "engrama.services.language.client.OllamaClient")]


def test_real_tree_memory_does_not_import_language():
    bad = [b for b in check(ROOT) if b[0].startswith("services/memory/")]
    assert bad == []
