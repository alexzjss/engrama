import json

import pygame

from engrama.app import i18n
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window, hud
from engrama.app.ui.generations import GenerationsPanel, duration_key

LOOK = {"seed": 3, "body": 1, "eyes": 1, "ears": 1, "tail": 1, "pattern": 1}


class FakeGrowler:
    def growl(self, pitch, kind):
        pass


class Rec:
    def __init__(self, n, days, cause, lineage=("brincalhao", "companheiro", "guardiao", "lendario"), seed=7):
        self.n, self.days, self.cause, self.lineage, self.seed = n, days, cause, tuple(lineage), seed
        self.ancestral = ("a",)


class Provider:
    def __init__(self, recs):
        self.recs, self.deleted = recs, []

    def records(self):
        return list(self.recs)

    def delete_archive(self, n):
        self.deleted.append(n)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def make(recs):
    w = Window(lambda: Snapshot(look=LOOK, stage="adult"), lambda k, d=None: None, growler=FakeGrowler())
    w.generations_provider = Provider(recs)
    return w


def texts(fn):
    seen = []
    hud.add_text_hook(seen.append)
    try:
        fn()
    finally:
        hud.remove_text_hook(seen.append)
    return seen


RECS = [Rec(1, 3, "neglect", lineage=()), Rec(2, 50, "old_age"), Rec(3, 110, "old_age", lineage=("arisco",))]


def test_generations_panel_lists_and_deletes():
    i18n.set_lang("pt")
    w = make(RECS)
    w.handle_event(key(pygame.K_F10))
    assert w.panel_name == "generations" and isinstance(w.panel, GenerationsPanel)
    seen = texts(lambda: w.frame(1.0))
    assert i18n.t("ui.gen.dur.days") in " ".join(seen)
    assert i18n.t("ui.gen.cause.neglect") in " ".join(seen)
    assert i18n.t("ui.gen.dur.two_months") in " ".join(seen)
    assert len(w.panel._rows) == 3
    w.handle_event(key(pygame.K_DOWN))
    w.handle_event(key(pygame.K_DELETE))
    assert w.generations_provider.deleted == []        # needs a second press
    seen = texts(lambda: w.frame(1.0))
    assert i18n.t("ui.gen.confirm") in seen
    w.handle_event(key(pygame.K_DELETE))
    assert w.generations_provider.deleted == [2]
    # moving away cancels a pending confirmation
    w.handle_event(key(pygame.K_DELETE))
    w.handle_event(key(pygame.K_DOWN))
    w.handle_event(key(pygame.K_DELETE))
    assert w.generations_provider.deleted == [2]
    w.handle_event(key(pygame.K_ESCAPE))
    assert w.panel is None


def test_duration_words():
    assert [duration_key(d) for d in (2, 20, 60, 90, 200)] == [
        "ui.gen.dur.days", "ui.gen.dur.weeks", "ui.gen.dur.two_months", "ui.gen.dur.three_months", "ui.gen.dur.long"]


def test_panel_no_digits_normal_mode():
    for lang in ("pt", "en"):
        i18n.set_lang(lang)
        w = make(RECS)
        w.open_panel("generations")
        seen = texts(lambda: w.frame(1.0))
        assert seen and not any(c.isdigit() for s in seen for c in s), seen
        w.dev = True
        assert any(c.isdigit() for c in " ".join(texts(lambda: w.frame(1.0))))
    i18n.set_lang("pt")


def test_empty_and_missing_provider():
    w = make([])
    w.open_panel("generations")
    assert i18n.t("ui.gen.empty") in texts(lambda: w.frame(1.0))
    w.generations_provider = None
    w.open_panel("generations")
    w.frame(1.0)


def test_i18n_pt_en_in_sync():
    pt = json.loads((i18n._DIR / "pt.json").read_text(encoding="utf-8"))
    en = json.loads((i18n._DIR / "en.json").read_text(encoding="utf-8"))
    assert set(pt) == set(en)
    new = [k for k in pt if k.startswith(("ui.life.", "ui.gen.", "branch."))]
    assert len(new) > 20
    assert not any(c.isdigit() for k in new for c in pt[k] + en[k])
    assert all(pt[k].strip() and en[k].strip() for k in new)
