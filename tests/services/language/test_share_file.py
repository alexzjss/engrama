import re

from engrama.services.language.persona import PersonaState
from engrama.services.perception.files import FileGlimpse
from tests.services.language.test_service import FakeClient, get, make

G = FileGlimpse("segredo_2026.py", "codigo", "pequeno", "def f():\n    return 42\n", ())


def _episodes(mem):
    return [r[0] for r in mem._db.execute("SELECT summary FROM episodes WHERE kind='arquivo'").fetchall()]


def test_share_file_ready_replies_and_stores_safe_summary(tmp_path):
    client = FakeClient(reply="que código bonito")
    svc, mem, _ = make(tmp_path, client=client)
    svc._state = "ready"
    svc.share_file(G)
    svc.pump()
    assert get(svc).source == "llm"
    sysmsg = client.chats[0][0]["content"]
    assert "segredo_.py" in sysmsg and not re.search(r"\d", sysmsg)
    assert "return 42" in client.chats[0][-1]["content"]
    eps = _episodes(mem)
    assert eps == ["mostrou um arquivo de codigo"]
    assert not re.search(r"\d|segredo|\.py", eps[0])


def test_share_file_offline_babbles_then_answers_after_warm(tmp_path):
    client = FakeClient(reply="hmm legal")
    svc, mem, _ = make(tmp_path, client=client)
    svc._state = "loading"
    svc.share_file(G)
    svc.pump()
    assert get(svc).source == "babble"
    assert not client.chats
    assert svc._pending is not None
    svc.warm()
    svc.pump()
    assert get(svc).source == "llm"
    assert svc._pending is None
    assert len(_episodes(mem)) == 1


def test_share_file_egg_no_llm(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client, stage="egg")
    svc._state = "ready"
    svc.share_file(G)
    svc.pump()
    assert get(svc).source == "babble"
    assert not client.chats and client.warms == 0
