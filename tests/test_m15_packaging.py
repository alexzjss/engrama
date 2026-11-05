"""M15 packaging: static checks on the PyInstaller spec (no build)."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "engrama.spec"


def _data_entries() -> list[tuple[str, str]]:
    return re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', SPEC.read_text(encoding="utf-8").split("DATA_FILES = [")[1].split("]")[0])


def test_spec_exists_and_lists_required_data():
    text = SPEC.read_text(encoding="utf-8")
    for needle in ("engrama/recipes/*.toml", "engrama/app/i18n/*.json", "engrama/app/assets/*", "icon.ico", "walk_packages"):
        assert needle in text


def test_spec_data_sources_exist_in_repo():
    entries = _data_entries()
    assert len(entries) >= 3
    for pattern, dest in entries:
        assert dest.startswith("engrama/")
        if pattern.startswith("tests"):
            continue
        assert list(ROOT.glob(pattern)), f"no files match {pattern}"


def test_windows_icon_exists():
    assert (ROOT / "engrama" / "app" / "assets" / "icon.ico").is_file()


def test_release_workflow_is_draft_and_tag_triggered():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "draft: true" in text and 'tags: ["v*"]' in text and "workflow_dispatch" in text
