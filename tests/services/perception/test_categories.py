from engrama.services.memory.store import MemoryStore
from engrama.services.perception.categories import Categorizer
from tests.services.language.test_service import FakeClient, make


class Lang:
    def __init__(self):
        self.calls = []

    def classify_app(self, p):
        self.calls.append(p)


def test_table_then_cache_then_llm_once(tmp_path):
    mem, lang = MemoryStore(tmp_path / "m.sqlite"), Lang()
    c = Categorizer(mem, lang)
    assert c("Chrome.exe") == "navegador" and lang.calls == []
    mem.set_app_category("foo.exe", "desenho", "llm")
    assert c("foo.exe") == "desenho" and lang.calls == []
    assert c("bar.exe") == "programa" and c("bar.exe") == "programa"
    assert lang.calls == ["bar.exe"]


def test_unknown_offline_stays_programa_and_client_not_called(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    assert Categorizer(mem, None)("bar.exe") == "programa"


def test_user_correction_wins(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.set_app_category("a.exe", "jogo", "user")
    assert mem.set_app_category("a.exe", "chat", "llm") is False
    assert mem.app_category("a.exe") == "jogo"
    mem.set_app_category("a.exe", "video", "user")
    assert mem.app_category("A.EXE") == "video"
    assert mem.app_category_rows()[0]["source"] == "user"


def test_llm_answer_outside_list_discarded(tmp_path):
    client = FakeClient(reply="banana")
    svc, mem, _ = make(tmp_path, client=client)
    svc._state = "ready"
    svc.classify_app("zzz.exe")
    svc.pump()
    assert client.chats and client.chats[0][-1]["content"] == "zzz.exe"
    assert mem.app_category("zzz.exe") is None
    client.reply = "Jogo."
    svc.classify_app("zzz.exe")
    svc.pump()
    assert mem.app_category("zzz.exe") == "jogo"
    assert mem.app_category_rows()[0]["source"] == "llm"


def test_classify_never_raises(tmp_path):
    class Boom(FakeClient):
        def chat(self, *a, **k):
            raise RuntimeError("x")
    svc, mem, _ = make(tmp_path, client=Boom())
    svc._state = "ready"
    svc.classify_app("zzz.exe")
    svc.pump()
    assert mem.app_category("zzz.exe") is None
