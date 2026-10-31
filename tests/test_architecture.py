import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "engrama"
FORBIDDEN = {
    "kernel": ("engrama.mind", "engrama.modules", "engrama.lab", "engrama.services"),
    "mind": ("engrama.kernel", "engrama.modules"),
}
MODULE_ALLOWED = ("engrama.mind", "engrama.vocab", "engrama.balance", "engrama.modules")
STDLIB = set(sys.stdlib_module_names)


def _imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            out.add(n.module)
            out.update(f"{n.module}.{a.name}" for a in n.names)
    return out


def _under(mod: str, pkg: str) -> bool:
    return mod == pkg or mod.startswith(pkg + ".")


def _files(sub: str):
    d = ROOT / sub
    return sorted(d.rglob("*.py")) if d.exists() else []


def test_kernel_and_mind_dependency_rules():
    bad = []
    for sub, banned in FORBIDDEN.items():
        for f in _files(sub):
            for m in _imports(f):
                if any(_under(m, b) for b in banned):
                    bad.append((str(f.relative_to(ROOT)), m))
    assert not bad, bad


def test_modules_import_only_allowed():
    bad = []
    for f in _files("modules"):
        for m in _imports(f):
            top = m.split(".")[0]
            if top == "engrama":
                if not any(_under(m, a) for a in MODULE_ALLOWED):
                    bad.append((str(f.relative_to(ROOT)), m))
            elif top != "numpy" and top not in STDLIB:
                bad.append((str(f.relative_to(ROOT)), m))
    assert not bad, bad
