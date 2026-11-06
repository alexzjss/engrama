"""M6 acceptance: death, farewell, rebirth with inheritance, the generations registry and old saves.

The host is driven with a fake wall clock and a fake language service; death is forced through the kernel state
instead of simulating a whole life."""
import json
import threading
from pathlib import Path

import pytest

from engrama import balance as B
from engrama.app.host import Host
from engrama.clock import SimClock
from engrama.config import Config
from engrama.services.generations import load_generations
from engrama.services.memory.store import MemoryStore, WorkingMemory

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "engrama" / "recipes" / "minimal-v1.toml"


class FakeTime:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class FakeLanguage:
    def __init__(self, text="adeus, humano"):
        self.text, self.calls = text, []

    def farewell(self, cause, on_text):
        self.calls.append(cause)
        th = threading.Thread(target=lambda: on_text(self.text))   # like the real worker: another thread
        th.start()
        th.join()


@pytest.fixture
def make_host():
    made = []

    def make(tmp, ft, seed=7, with_services=True, text="adeus, humano"):
        h = Host(Config(data_dir=tmp), tmp, MINIMAL, seed=seed, clock=SimClock(1.0, now_fn=ft),
                 ram_free_mb_fn=lambda: 8000.0)
        made.append(h)
        mem = work = lang = None
        if with_services:
            mem, work, lang = MemoryStore(tmp / "memory.sqlite"), WorkingMemory(), FakeLanguage(text)
            h.attach_services(mem, work, lang)
        return h, mem, work, lang

    yield make
    for h in made:
        h.stop()
        if h.memory is not None:
            h.memory.close()


def run(h, ft, n, step=1.0):
    for _ in range(n):
        ft.tick(step)
        h.pump(1)


def kill(h, cause="neglect"):
    k = h.runtime.kernel
    k.dead, k.death_cause = True, cause


def seed_memory(mem):
    mem.add_episode("conversa", "o humano riu muito comigo", valence=0.8, importance=0.9)
    mem.add_episode("conversa", "falamos de gatos", valence=0.5, importance=0.7, topic="gatos")
    mem.add_episode("conversa", "ele ficou quieto", valence=-0.2, importance=0.5)
    mem.add_episode("conversa", "um dia comum", valence=0.1, importance=0.4)
    mem.add_episode("conversa", "brincamos de novo", valence=0.4, importance=0.6)


@pytest.mark.slow
def test_death_farewell_then_rebirth(tmp_path, make_host):
    ft = FakeTime()
    h, mem, work, lang = make_host(tmp_path, ft)
    seed_memory(mem)
    mem.delete_topic("politica")   # a blocklist entry that must survive the rebirth
    work.add("user", "oi")
    run(h, ft, 3)
    kill(h)
    ft.tick(); h.pump(1)
    assert lang.calls == ["neglect"]
    assert h.farewell_text == "adeus, humano"
    assert h.snapshot().dead and h.snapshot().death_cause == "neglect"
    assert h.runtime.kernel.generation == 1            # not before FAREWELL_S
    run(h, ft, int(B.FAREWELL_S) - 2)
    assert h.runtime.kernel.generation == 1
    run(h, ft, 4)
    k = h.runtime.kernel
    assert k.generation == 2 and not k.dead and k.stage == "egg"
    assert h.farewell_text == ""
    recs = load_generations(tmp_path / "generations.json")
    assert len(recs) == 1 and recs[0].n == 1 and recs[0].cause == "neglect"
    assert 0 < len(recs[0].ancestral) <= B.ANCESTRAL_MAX
    assert (tmp_path / "generations" / "1" / "memory.sqlite").exists()
    assert (tmp_path / "generations" / "1" / "save" / "meta.json").exists()
    # the new memory holds only ancestral episodes; the blocklist is kept; working memory is cleared
    assert work.messages() == []
    assert mem.is_blocked("topic", "politica")
    assert mem.facts() == [] and mem.top_topics() == []
    assert 0 < len(mem.ancestral_rows(10)) <= B.ANCESTRAL_MAX
    # the saved game is the new egg
    assert json.loads((tmp_path / "save" / "kernel.json").read_text(encoding="utf-8"))["generation"] == 2
    assert h.snapshot().generation == 2 and not h.snapshot().dead


@pytest.mark.slow
def test_skip_rebirths_early(tmp_path, make_host):
    ft = FakeTime()
    h, mem, work, lang = make_host(tmp_path, ft)
    run(h, ft, 2)
    kill(h, "old_age")
    run(h, ft, 2)
    assert h.farewell_text and h.runtime.kernel.generation == 1
    h.skip_farewell()
    run(h, ft, 1)
    assert h.runtime.kernel.generation == 2
    assert load_generations(tmp_path / "generations.json")[0].cause == "old_age"


@pytest.mark.slow
def test_fullscreen_delays_rebirth(tmp_path, make_host):
    ft = FakeTime()
    h, mem, work, lang = make_host(tmp_path, ft)
    run(h, ft, 2)
    h.runtime.kernel.world.fullscreen = True
    kill(h)
    run(h, ft, int(B.FAREWELL_S) + 5)
    h.skip_farewell()
    run(h, ft, 3)
    assert h.runtime.kernel.generation == 1 and h.snapshot().dead     # fullscreen: the scene waits
    assert len(lang.calls) == 1                                       # farewell requested only once
    h.runtime.kernel.world.fullscreen = False
    run(h, ft, 2)
    assert h.runtime.kernel.generation == 2


@pytest.mark.slow
def test_dead_save_is_reborn_at_startup(tmp_path, make_host):
    ft = FakeTime()
    h, mem, work, lang = make_host(tmp_path, ft)
    run(h, ft, 2)
    kill(h)
    h._save()
    h.stop()
    mem.close()
    h2, mem2, work2, lang2 = make_host(tmp_path, ft)
    assert h2.snapshot().dead                       # as loaded
    run(h2, ft, 1)
    assert h2.runtime.kernel.generation == 2 and not h2.runtime.kernel.dead
    assert lang2.calls == []                        # no farewell scene
    assert [r.n for r in load_generations(tmp_path / "generations.json")] == [1]
    assert (tmp_path / "generations" / "1" / "memory.sqlite").exists()


@pytest.mark.slow
def test_bare_host_still_reborns(tmp_path, make_host):
    ft = FakeTime()
    h, *_ = make_host(tmp_path, ft, with_services=False)
    run(h, ft, 1)
    kill(h)
    h.skip_farewell()
    run(h, ft, 2)
    assert h.runtime.kernel.generation == 2
    assert len(load_generations(tmp_path / "generations.json")) == 1


@pytest.mark.slow
def test_m5_save_loads_with_defaults(tmp_path, make_host):
    ft = FakeTime()
    h, mem, work, lang = make_host(tmp_path, ft)
    run(h, ft, 5)
    h._save()
    h.stop()
    mem.close()
    kp = tmp_path / "save" / "kernel.json"
    d = json.loads(kp.read_text(encoding="utf-8"))
    for key in ("health", "generation", "lineage", "dead", "death_cause", "interest_s", "traits", "last_message_t",
                "interact"):
        d.pop(key, None)
    d["genome"].pop("branch", None)
    kp.write_text(json.dumps(d), encoding="utf-8")
    h2, *_ = make_host(tmp_path, ft)
    run(h2, ft, 5)
    s = h2.snapshot()
    assert s.generation == 1 and s.lineage == () and not s.dead and not s.sick and not s.old
    assert s.branch == "base" and s.branch_name
    assert h2.last_error == ""


def test_snapshot_carries_life_fields(tmp_path, make_host):
    ft = FakeTime()
    h, *_ = make_host(tmp_path, ft, with_services=False)
    run(h, ft, 2)
    s = h.snapshot()
    assert s.branch_name and s.generation == 1 and not s.sick and s.sick_kind == "" and not s.grave
    assert s.evolved_at == float("-inf")
    k = h.runtime.kernel
    k.health.sick, k.health.kind = True, "cold"
    k.lifecycle.old = True
    run(h, ft, 1)
    s = h.snapshot()
    assert s.sick and s.sick_kind == "cold" and s.old
    h._emit_changes(ft())          # no stage change: evolved_at unchanged
    h._prev_stage = "bogus"
    h._emit_changes(ft())
    assert h._evolved_at == ft()
    run(h, ft, 1)
    assert h.snapshot().evolved_at == h._evolved_at


def test_generations_provider(tmp_path, make_host):
    ft = FakeTime()
    h, *_ = make_host(tmp_path, ft, with_services=False)
    assert h.generations_provider.records() == []
    kill(h)
    h.skip_farewell()
    run(h, ft, 2)
    recs = h.generations_provider.records()
    assert [r.n for r in recs] == [1]
    # the save copy holds the dead life; deleting the archive keeps the record
    assert (tmp_path / "generations" / "1").exists()
    h.generations_provider.delete_archive(1)
    assert not (tmp_path / "generations" / "1").exists()
    assert [r.n for r in h.generations_provider.records()] == [1]
