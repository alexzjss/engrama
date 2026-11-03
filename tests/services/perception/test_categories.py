from engrama.services.memory.store import MemoryStore
from engrama.services.perception.categories import Categorizer
from tests.services.language.test_service import FakeClient, make


M7_TABLE = {
    "chrome.exe": "navegador", "msedge.exe": "navegador", "firefox.exe": "navegador",
    "brave.exe": "navegador", "opera.exe": "navegador", "vivaldi.exe": "navegador",
    "code.exe": "programacao", "devenv.exe": "programacao", "pycharm64.exe": "programacao",
    "idea64.exe": "programacao", "sublime_text.exe": "programacao", "notepad++.exe": "programacao",
    "cursor.exe": "programacao", "rider64.exe": "programacao",
    "steam.exe": "jogo", "epicgameslauncher.exe": "jogo", "minecraft.exe": "jogo",
    "javaw.exe": "jogo", "hollow_knight.exe": "jogo", "godot.exe": "jogo",
    "spotify.exe": "musica", "foobar2000.exe": "musica", "musicbee.exe": "musica", "itunes.exe": "musica",
    "vlc.exe": "video", "mpv.exe": "video", "netflix.exe": "video", "potplayermini64.exe": "video",
    "discord.exe": "chat", "telegram.exe": "chat", "whatsapp.exe": "chat",
    "slack.exe": "chat", "teams.exe": "chat", "zoom.exe": "chat",
    "winword.exe": "escritorio", "excel.exe": "escritorio", "powerpnt.exe": "escritorio",
    "soffice.exe": "escritorio", "onenote.exe": "escritorio",
    "photoshop.exe": "desenho", "krita.exe": "desenho", "gimp-2.10.exe": "desenho",
    "mspaint.exe": "desenho", "blender.exe": "desenho", "aseprite.exe": "desenho",
    "windowsterminal.exe": "terminal", "cmd.exe": "terminal", "powershell.exe": "terminal",
    "pwsh.exe": "terminal", "wt.exe": "terminal",
}


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


def test_linux_names():
    from engrama.services.perception.categories import normalize_process, table_category
    assert table_category("firefox") == "navegador"
    assert table_category("code") == "programacao"
    assert table_category("kitty") == "terminal"
    assert table_category("hollow_knight.x86_64") == "jogo"
    assert table_category("HollowKnight.exe") == "jogo"
    assert table_category("soffice.bin") == "escritorio"
    assert table_category("nonexistent-app") is None
    assert normalize_process("Foo.AppImage") == "foo"
    assert normalize_process("brave-bin") == "brave"
    assert normalize_process("x.sh") == "x" and normalize_process("a.x86") == "a"


def test_windows_keys_unchanged():
    from engrama.services.perception.categories import APP_TABLE, table_category
    for k, v in M7_TABLE.items():
        assert APP_TABLE[k] == v and table_category(k) == v


