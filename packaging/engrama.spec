# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir bundle: `pyinstaller packaging/engrama.spec --noconfirm`
# Data lands under engrama/... so that engrama.resources finds it in sys._MEIPASS.
import pkgutil
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821  (SPECPATH is injected by PyInstaller)
sys.path.insert(0, str(ROOT))

import engrama  # noqa: E402

IS_WIN = sys.platform == "win32"

# Data entries: (source glob relative to the repo root, destination dir inside the bundle).
DATA_FILES = [
    ("engrama/recipes/*.toml", "engrama/recipes"),
    ("engrama/app/i18n/*.json", "engrama/app/i18n"),
    ("engrama/app/assets/*", "engrama/app/assets"),
]
datas = []
for pattern, dest in DATA_FILES:
    for p in sorted(ROOT.glob(pattern)):
        datas.append((str(p), dest))

# cli._main imports lots of modules lazily: bundle every submodule of the package.
hiddenimports = [m.name for m in pkgutil.walk_packages(engrama.__path__, "engrama.")]
hiddenimports = [m for m in hiddenimports if ".tests" not in m]

excludes = [
    "tkinter", "unittest", "pytest", "_pytest", "pydoc", "doctest", "test", "tests",
    "numpy.tests", "numpy.testing", "numpy.f2py", "numpy.distutils",
    "setuptools", "pkg_resources", "distutils", "IPython", "matplotlib",
    "pygame.tests", "pygame.examples", "pygame.docs",
]

a = Analysis(
    [str(ROOT / "engrama" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="engrama",
    console=not IS_WIN,  # windowed (no console) on Windows only
    icon=str(ROOT / "engrama" / "app" / "assets" / "icon.ico") if IS_WIN else None,
    upx=False,
)
coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="engrama",
)
