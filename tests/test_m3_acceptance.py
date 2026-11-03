"""M3 acceptance: the app opens, hatches and lives; chat stays in character; offline degrades to babble;
the Mind View shows the SNN reacting; rest unloads the LLM and drops the frame rate; the core stays light."""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama.app.host import Host, _build_persona, main
from engrama.app.ui.window import Window
from engrama.clock import SimClock
from engrama.config import Config
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import LanguageService
from engrama.services.memory.store import MemoryStore, WorkingMemory

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "recipes" / "default-v1.toml"


class FakeTime:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class FakeClient:
    def __init__(self, replies=("oi!",)):
        self.replies, self.chats, self.unloads, self.warms = list(replies), [], 0, 0

    def warm(self, model):
        self.warms += 1

    def unload(self, model):
        self.unloads += 1

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

    def tags(self):
        return {"qwen3:1.7b"}

    def pull(self, name, on_progress):
        on_progress(100, "ok")


class FakeServer:
    def __init__(self, available=True):
        self._a = available

    def available(self):
        return self._a

    def running(self):
        return self._a

    def start(self):
        return self._a


def make_host(tmp, ft, scale=1.0, seed=7):
    return Host(Config(data_dir=tmp), tmp, DEFAULT, seed=seed, clock=SimClock(scale, now_fn=ft),
                ram_free_mb_fn=lambda: 8000.0)


def run(h, ft, n, step=1.0):
    for _ in range(n):
        ft.tick(step)
        h.pump(1)


def make_lang(tmp, host, client, server, stage=None):
    mem = MemoryStore(tmp / "mem.sqlite")
    cfg = Config(data_dir=tmp)
    lang = LanguageService(client, server, cfg, mem, WorkingMemory(),
                           get_state=lambda: PersonaState(stage=stage or host.snapshot().stage),
                           food_name=lambda i, l: i, sync=True)
    return lang, mem


def test_open_hatch_and_live(tmp_path, monkeypatch):
    # the app opens, runs 300 frames and exits cleanly; --no-llm never touches Ollama
    import engrama.services.language.server as srv

    def boom(*a, **k):
        raise AssertionError("Ollama server must not be created under --no-llm")
    monkeypatch.setattr(srv, "OllamaServer", boom)
    assert main(["--frames", "300", "--no-llm", "--data-dir", str(tmp_path / "app"), "--seed", "3"]) == 0
    assert (tmp_path / "app" / "save" / "meta.json").exists()
    # a host with a fast clock: clicks hatch the egg, then the creature changes action on its own
    ft = FakeTime()
    h = make_host(tmp_path / "h", ft)
    events = []
    h.on_event = lambda k, d: events.append((k, d))
    assert h.snapshot().stage == "egg"
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 2)
    assert h.snapshot().stage == "baby" and any(k == "hatch" for k, _ in events)
    run(h, ft, 600)
    assert any(k == "action_change" for k, _ in events)
    h.stop()


def test_chat_pt_and_en_in_character(tmp_path):
    ft = FakeTime()
    h = make_host(tmp_path, ft)
    client = FakeClient(["How can I help you today?", "pii 123 oi \U0001F600 oi", "Posso ajudar?", "brr 42 sim sim"])
    lang, mem = make_lang(tmp_path, h, client, FakeServer(), stage="child")
    lang.request("oi, tudo bem com você?")
    lang.pump()
    lang.request("hello, how are you today?")
    lang.pump()
    replies = []
    while not lang.replies.empty():
        replies.append(lang.replies.get())
    assert [r.source for r in replies] == ["llm", "llm"]
    for r in replies:
        assert r.text and not re.search(r"\d", r.text)
        assert not re.search("[\U0001F000-\U0001FAFF]", r.text)
        assert not re.search(r"assistant|assistente|help|ajudar", r.text, re.I)
    assert [r.lang for r in replies] == ["pt", "en"]
    persona_prompts = [m[0]["content"] for m in client.chats if "Engrama" in m[0]["content"]]
    pt_sys, en_sys = persona_prompts[0], persona_prompts[-1]
    assert "Responda em português" in pt_sys and "Reply in English" in en_sys
    assert not re.search(r"\d", pt_sys) and not re.search(r"\d", en_sys)
    # the persona handed to the LLM is built from the live snapshot, without raw numbers
    persona = _build_persona(h.snapshot(), mem)
    assert persona.stage == h.snapshot().stage and isinstance(persona.needs_top, list)
    h.stop()
    mem.close()


def test_llm_offline_creature_keeps_living(tmp_path):
    ft = FakeTime()
    h = make_host(tmp_path, ft)
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 2)
    client = FakeClient()
    lang, mem = make_lang(tmp_path, h, client, FakeServer(available=False))
    before = dict(h.snapshot().needs)
    t0 = h.snapshot().t
    lang.request("oi!")
    lang.pump()
    r = lang.replies.get_nowait()
    assert r.source == "babble" and r.text and client.chats == []
    assert lang.status == "missing"
    run(h, ft, 120)
    s = h.snapshot()
    assert s.t > t0 + 100 and s.needs != before
    h.stop()
    mem.close()


def test_mind_view_shows_snn_reacting(tmp_path):
    ft = FakeTime()
    h = make_host(tmp_path, ft, scale=60.0)   # 60 s of simulated time per tick: one SNN bin each
    h.want_viz = True
    for _ in range(B.EGG_HATCH_CLICKS):
        h.post("click")
    run(h, ft, 5)

    def raster():
        for vs in h.snapshot().viz.values():
            for v in vs:
                if v.kind == "raster":
                    return np.asarray(v.data, dtype=float).copy()
        return None

    seen_r, seen_s = [], []
    for i in range(40):
        if i % 3 == 0:
            h.post("pet")
        if i == 20:
            for _ in range(4):
                h.post("click")
        run(h, ft, 1, step=1.2)
        h._last_viz_wall = float("-inf")   # force a fresh viz collection each tick
        r = raster()
        assert r is not None and np.all(np.isfinite(r))
        seen_r.append(r)
        seen_s.append(h.snapshot().surprise)
    assert any(not np.array_equal(seen_r[0], r) for r in seen_r[1:]), "raster never changed"
    assert max(seen_s) - min(seen_s) > 1e-6, "surprise never changed"
    h.stop()


def test_rest_mode_unloads_llm_and_drops_fps(tmp_path):
    ft = FakeTime()
    h = make_host(tmp_path, ft)
    client = FakeClient()
    lang, mem = make_lang(tmp_path, h, client, FakeServer())
    h.on_rest_change = lambda resting, reason: lang.unload() if resting else None
    win = Window(h.snapshot, h.post, language=lang, set_rest=h.set_rest)
    win.frame(0.0)
    assert win.target_fps in (20, 10) and client.unloads == 0   # FPS_FOCUSED, or FPS_STILL when nothing moves (M8)
    win.set_rest(True)   # manual rest (what F3 does)
    run(h, ft, 2)
    win.frame(1.0)
    assert h.snapshot().resting and h.snapshot().rest_reason == "manual"
    assert client.unloads == 1 and win.target_fps == 2
    win.set_rest(False)
    run(h, ft, 2)
    win.frame(2.0)
    assert not h.snapshot().resting and win.target_fps in (20, 10)   # FPS_FOCUSED, or FPS_STILL when nothing moves (M8)
    h.post("fullscreen_on")   # automatic rest
    run(h, ft, 2)
    win.frame(3.0)
    assert h.snapshot().resting and h.snapshot().rest_reason == "fullscreen"
    assert client.unloads == 2 and win.target_fps == 2
    h.post("fullscreen_off")
    run(h, ft, 2)
    assert not h.snapshot().resting
    h.stop()
    mem.close()


def test_core_budget(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "bench.py"), "--app", "--seconds", "30",
                          "--data-dir", str(tmp_path / "bench")], capture_output=True, text=True,
                         cwd=ROOT, timeout=120, check=True).stdout
    r = json.loads(out)
    assert r["alive"], "the app exited during the bench"
    tol = 1.5 if r["loaded"] else 1.0   # tolerance only on a loaded machine; recorded in the report below
    print("core budget:", r, "tolerance", tol)
    assert r["peak_rss_mb"] <= 150 * tol
    assert r["mean_cpu_percent"] <= 2.0 * tol
