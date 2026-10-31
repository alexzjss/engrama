import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "engrama"
FORBIDDEN = {
    "kernel": ("engrama.mind", "engrama.modules", "engrama.lab", "engrama.services"),
    "mind": ("engrama.kernel", "engrama.modules"),
}
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
                if any(_under(m, b) for b in banned):
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
