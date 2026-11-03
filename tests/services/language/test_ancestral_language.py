import random

from engrama.services.language.client import LLMOffline
from engrama.services.language.initiative import InitiativePolicy
from engrama.services.memory.store import MemoryStore
from tests.services.language.test_initiative import T0, make, run
from tests.services.language.test_reflection import Client, make as make_svc, ready


def test_initiative_ancestral_rare_and_quota(tmp_path):
    s, clock = make(tmp_path, topics=False, opinion=False)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    assert run(p, 30, start=clock["t"]) == []        # nothing to say without memories
    s.new_generation(["um sonho com jardim"])
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(2))
    fires = run(p, 300, start=clock["t"])
    assert fires and all(k == "ancestral" and t == "um sonho com jardim" for k, t in fires)
    assert len(fires) <= 300                          # shared quota: at most one per active hour
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(2))
    assert run(p, 30, start=clock["t"], stage="baby") == []     # stage gate
    s.close()


def test_initiative_ancestral_is_minority(tmp_path):
    s, clock = make(tmp_path)
    s.add_episode("ancestral", "sonho raro", 0.0, 0.6)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(3))
    kinds = [k for k, _ in run(p, 600, start=clock["t"])]
    assert kinds and kinds.count("ancestral") < len(kinds) / 2
    s.close()


def test_farewell_offline_babbles_never_raises(tmp_path):
    got = []
    svc, _, _ = make_svc(tmp_path, Client())
    svc.farewell("old_age", got.append)              # LLM not warmed: offline
    svc.pump()
    assert len(got) == 1 and got[0]
    svc.farewell("neglect", lambda t: 1 / 0)         # callback explodes
    svc.pump()

    class Boom(Client):
        def chat(self, *a, **k):
            raise RuntimeError("boom")
    (tmp_path / "b").mkdir()
    svc2, _, _ = make_svc(tmp_path / "b", Boom())
    ready(svc2)
    got.clear()
    svc2.farewell("old_age", got.append)
    svc2.pump()
    assert len(got) == 1
    (tmp_path / "c").mkdir()
    svc3, _, _ = make_svc(tmp_path / "c", Client(), stage="baby")
    ready(svc3)
    got.clear()
    svc3.farewell("old_age", got.append)
    svc3.pump()
    assert got and got[0] != "oi amigo"              # baby never gets LLM speech


def test_farewell_llm_short_speech(tmp_path):
    got = []
    client = Client(chat="obrigado por tudo, foi lindo")
    svc, _, _ = make_svc(tmp_path, client)
    ready(svc)
    svc.farewell("old_age", got.append)
    svc.pump()
    assert got == ["obrigado por tudo, foi lindo"]
    assert "partir" in client.calls[-1][0]["content"] or "partir" in client.calls[-1][-1]["content"]
