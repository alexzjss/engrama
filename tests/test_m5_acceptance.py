"""M5 acceptance (spec section 7): the creature perceives the PC only with permission, never leaks what it must not,
closes its eyes on demand, turns titles into themes, comments rarely and survives broken sources."""
import random
import re
from pathlib import Path

import pytest

from engrama.app.host import Host, _Activity, _memory_provider
from engrama.clock import SimClock
from engrama.config import Config
from engrama.services.language.initiative import InitiativePolicy
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import LanguageService
from engrama.services.memory.store import MemoryStore, WorkingMemory
from engrama.services.perception import FILE_READ_CAP, PRIVATE
from engrama.services.perception.blocklist import Blocklist
from engrama.services.perception.categories import Categorizer
from engrama.services.perception.files import read_dropped
from engrama.services.perception.service import PerceptionService
from engrama.services.perception.themes import make_theme_sink

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "recipes" / "minimal-v1.toml"
BANK_TITLE = "Bradesco Internet Banking - Meu Extrato Secreto"
GAME_TITLE = "Hollow Knight - Greenpath Segredo"


class FakeTime:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class FakeSources:
    def __init__(self):
        self.fg = ("code.exe", "main.py - engrama")
        self.idle, self.full, self.cpu = 0.0, False, 10.0
        self.calls = {"foreground": 0, "idle": 0, "full": 0, "cpu": 0}
        self.raise_exc = None

    def _maybe(self):
        if self.raise_exc:
            raise self.raise_exc

    def foreground(self):
        self.calls["foreground"] += 1
        self._maybe()
        return self.fg

    def idle_seconds(self):
        self.calls["idle"] += 1
        self._maybe()
        return self.idle

    def is_fullscreen(self):
        self.calls["full"] += 1
        self._maybe()
        return self.full

    def cpu_percent(self):
        self.calls["cpu"] += 1
        self._maybe()
        return self.cpu


class ScriptedClient:
    def __init__(self, category="jogo"):
        self.category = category
        self.chats: list[list[dict]] = []
        self.warms = 0

    def warm(self, model):
        self.warms += 1

    def unload(self, model):
        pass

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        head = messages[0]["content"]
        if head.lower().startswith("classify") and messages[-1]["role"] == "user" and len(messages) == 2 \
                and num_predict <= 8:
            return self.category
        return "oi, e ai"

    def tags(self):
        return {"qwen3:1.7b"}

    def pull(self, name, on_progress):
        on_progress(100, "ok")


class FakeServer:
    def available(self): return True
    def running(self): return True
    def start(self): return True


def cfg_for(tmp, *perms, asked=True, blocklist=None, **kw):
    cfg = Config(data_dir=tmp)
    cfg.perception_asked = asked
    cfg.perception_interval_s = 15.0
    cfg.perception_blocklist = list(blocklist or [])
    for p in perms:
        cfg.permissions[p] = True
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def make_host(tmp, cfg, ft):
    return Host(cfg, tmp, MINIMAL, seed=7, clock=SimClock(1.0, now_fn=ft), ram_free_mb_fn=lambda: 8000.0)


def make_lang(tmp, ft, client, stage="child", idle=lambda: True, name="memory.sqlite", mem=None):
    mem = mem or MemoryStore(tmp / name, now_fn=ft)
    work = WorkingMemory()
    lang = LanguageService(client, FakeServer(), Config(data_dir=tmp), mem, work,
                           get_state=lambda: PersonaState(stage=stage), food_name=lambda i, l: i,
                           idle=idle, now_fn=ft, sync=True)
    return lang, mem, work


def make_svc(cfg, ft, posts, src, mem=None, eyes=None, categorize=None, host=None):
    eyes = eyes if eyes is not None else {"on": False}
    post = host.post if host is not None else (lambda k, d=None: None)

    def rec(kind, data=None):
        posts.append((kind, dict(data or {})))
        post(kind, data)
    sink = make_theme_sink(mem, ft) if mem is not None else None
    return PerceptionService(rec, src, lambda: cfg, lambda: eyes["on"], now_fn=ft, on_theme=sink,
                             categorize=categorize), eyes


def run(svc, ft, secs=600, step=5.0, host=None):
    end = ft.t + secs
    while ft.t < end:
        svc.tick(ft.t)
        if host is not None:
            host.pump(1)
        ft.tick(step)


def file_bytes(tmp) -> bytes:
    blob = b""
    for p in sorted(tmp.rglob("*")):
        if p.is_file() and p.name != "config.json":
            blob += p.read_bytes()
    return blob


# 1 -------------------------------------------------------------------------------------------------------
def test_first_use_blocks_all_reads(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "idle", "process", "active_window", "system_load", "time", asked=False)
    src, posts = FakeSources(), []
    svc, _ = make_svc(cfg, ft, posts, src)
    run(svc, ft, 600)
    assert sum(src.calls.values()) == 0 and posts == []


# 2 -------------------------------------------------------------------------------------------------------
def test_permission_per_source(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "idle")
    host = make_host(tmp_path, cfg, ft)
    src, posts = FakeSources(), []
    svc, _ = make_svc(cfg, ft, posts, src, host=host)
    run(svc, ft, 300, host=host)
    src.idle = 600.0
    run(svc, ft, 300, host=host)
    src.idle = 0.0
    run(svc, ft, 300, host=host)
    assert src.calls["foreground"] == 0 and src.calls["full"] == 0 and src.calls["cpu"] == 0
    kinds = [(k, d.get("source")) for k, d in posts]
    assert ("user_idle", "system") in kinds and ("user_active", "system") in kinds
    assert not any(k in ("app_focus", "fullscreen_on") for k, _ in posts)
    assert host.snapshot().t > 0
    host.stop()


# 3 -------------------------------------------------------------------------------------------------------
def test_blocked_app_never_leaks(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "process", "active_window", "idle", "system_load")
    host = make_host(tmp_path, cfg, ft)
    client = ScriptedClient()
    lang, mem, _ = make_lang(tmp_path, ft, client, idle=lambda: not host.snapshot().resting)
    lang.warm()
    src, posts = FakeSources(), []
    src.fg = ("chrome.exe", BANK_TITLE)
    svc, _ = make_svc(cfg, ft, posts, src, mem=mem, host=host, categorize=Categorizer(mem, lang))
    run(svc, ft, 600, host=host)
    lang.request("oi")
    lang.pump()
    lang.spontaneous("activity", None)
    lang.pump()
    assert ("app_focus", {"category": PRIVATE}) in posts
    snap_repr = repr(host.snapshot())
    host._save()
    host.stop()
    mem.close()
    secrets = (BANK_TITLE, "bradesco", "Extrato", "chrome.exe")
    blob = file_bytes(tmp_path).lower()
    prompts = repr(client.chats).lower()
    for s in secrets:
        assert s.lower().encode() not in blob, s
        assert s.lower() not in snap_repr.lower() and s.lower() not in prompts, s


# 4 -------------------------------------------------------------------------------------------------------
def test_eyes_closed_persists_and_shows(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "idle", "process", "active_window", "system_load")
    host = make_host(tmp_path, cfg, ft)
    src, posts = FakeSources(), []
    svc, eyes = make_svc(cfg, ft, posts, src, host=host)
    run(svc, ft, 60, host=host)
    assert sum(src.calls.values()) > 0
    before = dict(src.calls)
    eyes["on"] = cfg.eyes_closed = True              # what main()'s set_eyes does, then saves the config
    cfg.save(tmp_path / "config.json")
    host.set_eyes_closed(True)
    run(svc, ft, 600, host=host)
    assert src.calls == before                        # nothing was read while the eyes were closed
    assert host.snapshot().eyes_closed
    host.stop()
    cfg2 = Config.load(tmp_path / "config.json")      # survives a restart
    host2 = make_host(tmp_path, cfg2, ft)
    host2.pump(1)
    assert cfg2.eyes_closed and host2.snapshot().eyes_closed
    from engrama.app.ui.scene import Scene
    import pygame
    scene = Scene((160, 120))
    surf = pygame.Surface((160, 120))
    scene.draw(surf, host2.snapshot(), 0.0)           # the scene draws closed lids without error
    host2.stop()


# 5 -------------------------------------------------------------------------------------------------------
def test_title_theme_not_raw(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "process", "active_window")
    host = make_host(tmp_path, cfg, ft)
    mem = MemoryStore(tmp_path / "memory.sqlite", now_fn=ft)
    src, posts = FakeSources(), []
    src.fg = ("hollow_knight.exe", GAME_TITLE)
    svc, _ = make_svc(cfg, ft, posts, src, mem=mem, host=host)
    run(svc, ft, 120, host=host)
    row = next(r for r in mem.topic_rows() if r["name"] == "hollow knight")
    assert row["source"] == "percepcao"
    assert ("app_focus", {"category": "jogo"}) in posts
    host._save()
    host.stop()
    mem.close()
    blob = file_bytes(tmp_path)
    assert GAME_TITLE.encode() not in blob and b"Segredo" not in blob and b"segredo" not in blob.lower()


# 6 -------------------------------------------------------------------------------------------------------
def test_llm_category_only_when_ready(tmp_path):
    ft = FakeTime()
    client = ScriptedClient(category="musica")
    lang, mem, _ = make_lang(tmp_path, ft, client)
    cat = Categorizer(mem, lang)
    assert cat("zzzplayer.exe") == "programa"         # LLM offline: fallback, client untouched
    lang.pump()
    assert client.chats == [] and client.warms == 0
    lang.warm()
    assert lang.status == "ready"
    assert cat("zzzplayer.exe") == "programa"         # the offline request was queued; it runs now that it is ready
    lang.pump()
    assert len(client.chats) == 1
    assert cat("zzzplayer.exe") == "musica"
    lang.pump()
    assert len(client.chats) == 1                      # reused, not asked again
    mem.close()


# 7 -------------------------------------------------------------------------------------------------------
def _activity_run(tmp, activity, *, fullscreen=False, eyes=False, topics=True, hours=10, seed=11):
    ft = FakeTime()
    host = make_host(tmp, cfg_for(tmp), ft)
    host.runtime.kernel.lifecycle.stage = "adult"
    client = ScriptedClient()
    lang, mem, _ = make_lang(tmp, ft, client, stage="adult", idle=lambda: not host.snapshot().resting)
    if topics:
        mem.bump_topic("jogo", 0.6)
    lang.warm()
    policy = InitiativePolicy(mem, ft, rng=random.Random(seed))
    if fullscreen:
        host.post("fullscreen_on")
    kinds = []
    for _ in range(hours * 60):
        ft.tick(60)
        host.post("user_active")
        host.pump(1)
        snap = host.snapshot()
        res = policy.update(ft.t, stage=snap.stage, user_active=True, llm_ready=lang.status == "ready",
                            resting=snap.resting, fullscreen=snap.rest_reason == "fullscreen",
                            action=snap.action, activity=activity, eyes_closed=eyes)
        if res:
            kinds.append(res[0])
            lang.spontaneous(res[0], res[1])
        lang.pump()
    spoken = [c for c in client.chats]
    host.stop()
    mem.close()
    return kinds, spoken


def test_activity_comment_quota_and_blocks(tmp_path):
    kinds, chats = _activity_run(tmp_path / "a", "jogo")
    assert 1 <= len(kinds) <= 10                       # the M4 quota covers every kind together
    assert "activity" in kinds
    assert any("jogo" in repr(c) for c in chats)
    assert _activity_run(tmp_path / "p", PRIVATE, topics=False)[0] == []
    assert _activity_run(tmp_path / "f", "jogo", fullscreen=True)[0] == []
    assert _activity_run(tmp_path / "e", "jogo", eyes=True)[0] == []


# 8 -------------------------------------------------------------------------------------------------------
def test_file_drop_cases(tmp_path):
    drop = tmp_path / "drops"
    drop.mkdir()
    big = drop / "script_123.py"
    big.write_text("x = 1234567890\n" * 4000, encoding="utf-8")        # ~60 KB, full of digits
    assert big.stat().st_size > 50_000
    g = read_dropped(str(big))
    assert g.kind == "codigo" and len(g.text.encode("utf-8")) <= FILE_READ_CAP
    folder = drop / "pasta"
    (folder / "sub").mkdir(parents=True)
    (folder / "a.txt").write_text("a")
    (folder / "sub" / "deep_file.txt").write_text("b")
    gf = read_dropped(str(folder))
    assert gf.kind == "pasta" and "sub" in gf.entries and "a.txt" in gf.entries
    assert "deep_file.txt" not in gf.entries
    png = drop / "foto.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    gi = read_dropped(str(png))
    assert gi.kind == "imagem" and gi.text is None and gi.entries == ()
    secret = drop / "extrato_bradesco.txt"
    secret.write_text("saldo 100")
    assert read_dropped(str(secret), Blocklist(["bradesco"])) is None
    # what gets stored about it: no digits, no path
    ft = FakeTime()
    client = ScriptedClient()
    lang, mem, _ = make_lang(tmp_path, ft, client)
    lang.warm()
    lang.share_file(g)
    lang.pump()
    eps = mem.recent(50)
    assert eps and not any(re.search(r"\d", e) for e in eps)
    assert not any(str(drop) in e or "script_" in e for e in eps)
    mem.close()


# 9 -------------------------------------------------------------------------------------------------------
def test_source_exceptions_harmless(tmp_path):
    ft = FakeTime()
    cfg = cfg_for(tmp_path, "idle", "process", "active_window", "system_load")
    host = make_host(tmp_path, cfg, ft)
    mem = MemoryStore(tmp_path / "memory.sqlite", now_fn=ft)
    src, posts = FakeSources(), []
    src.raise_exc = OSError("boom")
    svc, _ = make_svc(cfg, ft, posts, src, mem=mem, host=host)
    run(svc, ft, 600, host=host)                       # every read raises: nothing escapes, nothing posted
    assert posts == [] and host.last_error == ""
    src.raise_exc = None
    run(svc, ft, 120, host=host)                       # and the service carries on once the source recovers
    assert any(k == "app_focus" for k, _ in posts)
    assert host.snapshot().t > 0
    host.stop()
    mem.close()


# extra: wiring helpers --------------------------------------------------------------------------------
def test_activity_tracker_hides_private_and_stale_themes():
    seen = []
    act = _Activity(lambda k, d=None: seen.append(k), lambda p, t, c: None)
    assert act.current() is None
    act.post("app_focus", {"category": "jogo"})
    assert act.current() == "jogo"
    act.on_theme("hollow_knight.exe", "Hollow Knight - x", "jogo")
    assert act.current() == "hollow knight"
    act.post("app_focus", {"category": "musica"})
    assert act.current() == "musica"                   # a stale theme does not follow a new category
    act.post("app_focus", {"category": PRIVATE})
    assert act.current() is None
    assert seen == ["app_focus"] * 3


def test_deleting_perceived_topic_silences_it(tmp_path):
    ft = FakeTime()
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=ft)
    mem.bump_perceived("hollow knight", ft.t)
    prov = _memory_provider(mem, WorkingMemory())
    prov.delete_topic("hollow knight")
    assert "hollow knight" in mem.silenced_themes()
    assert mem.bump_perceived("hollow knight", ft.t) == ""
    mem.close()
