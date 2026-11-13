"""M20 in the app: permissions gate every action, the chat hands commands over, the panel works without an LLM."""
import queue
import pygame
import pytest
from engrama.app import i18n
from engrama.app.actions import Actions, note_key
from engrama.app.snapshot import Snapshot
from engrama.app.ui import Window
from engrama.services import actions as A


class Cfg:
    def __init__(self, **on):
        self.action_permissions = {"reminders": False, "focus": False, "notes": False, **on}
        self.creature_name = "Mika"
        self.perception_asked = True


class Memory:
    def __init__(self, blocked=()):
        self.facts, self.blocked = {}, blocked

    def upsert_fact(self, key, value, confidence, source):
        if any(b in value for b in self.blocked):
            return False
        self.facts[key] = (value, confidence, source)
        return True


class Lang:
    def __init__(self, status="ready", raw=""):
        self.status, self.raw, self.replies = status, raw, queue.Queue()
        self.requests, self.structured = [], []

    def request(self, text):
        self.requests.append(text)

    def request_structured(self, text, messages, schema, handler):
        self.structured.append(text)
        if not handler(self.raw):
            self.request(text)


def make(stage="child", lang=None, memory=None, **on):
    now = [1000.0]
    said, alerts, saves = [], [], []
    cfg = Cfg(**on)
    acts = Actions(A.ActionStore(None, lambda: now[0]), cfg, memory or Memory(), lang or Lang(),
                   lambda: Snapshot(stage=stage), save_config=lambda: saves.append(1), say=said.append,
                   on_alert=alerts.append)
    return acts, now, said, alerts, saves


@pytest.fixture(autouse=True)
def _pt():
    i18n.set_lang("pt")
    yield


def test_everything_is_off_by_default_and_a_denied_command_does_nothing():
    acts, _now, said, _alerts, _saves = make()
    assert not any(acts.allowed(t) for t in A.TOOLS)
    assert acts.handle_text("me lembra em 20 min de tirar o bolo") is True      # she answers, but does not do it
    assert acts.store.reminders == [] and said == [i18n.t("action.denied.reminders")]
    assert acts.run(A.Intent("focus", 25)) == "denied" and not acts.store.focus_active
    assert acts.run(A.Intent("note", 0, "x")) == "denied" and acts.memory.facts == {}


def test_reminder_from_chat_fires_once_with_an_alert():
    acts, now, said, alerts, _ = make(reminders=True)
    assert acts.handle_text("me lembra em 20 min de tirar o bolo")
    assert [r.text for r in acts.store.reminders] == ["tirar o bolo"]
    assert "tirar o bolo" in said[-1] and "20 min" in said[-1]      # the time is said back
    acts.tick()
    assert alerts == []
    now[0] += 20 * 60
    acts.tick()
    acts.tick()
    assert len(alerts) == 1 and "tirar o bolo" in alerts[0] and acts.store.reminders == []


def test_focus_session_keeps_her_quiet_and_ends_with_a_cheer():
    acts, now, said, alerts, _ = make(focus=True)
    assert acts.handle_text("foco por 25 min") and acts.quiet
    now[0] += 25 * 60
    acts.tick()
    assert not acts.quiet and alerts == [i18n.t("action.focus.done")]
    assert acts.handle_text("para o foco") and said[-1] == i18n.t("action.focus.none")
    acts.handle_text("pomodoro")
    acts.set_allowed("focus", False)             # turning the permission off stops what it allowed
    assert not acts.quiet


def test_note_goes_to_memory_and_a_blocked_one_is_refused():
    mem = Memory(blocked=("senha",))
    acts, _now, said, _a, _s = make(memory=mem, notes=True)
    assert acts.handle_text("anota: comprar ração")
    assert mem.facts[note_key("comprar ração")] == ("comprar ração", 1.0, "note") and said[-1] == i18n.t("action.note.ok")
    assert acts.run(A.Intent("note", 0, "a senha é abc")) == "blocked" and said[-1] == i18n.t("action.note.blocked")
    assert len(mem.facts) == 1


def test_ordinary_talk_and_eggs_are_left_alone():
    acts, *_ = make(reminders=True, focus=True, notes=True)
    assert acts.handle_text("oi, tudo bem?") is False
    egg, *_ = make(stage="egg", reminders=True)
    assert egg.handle_text("me lembra em 5 min de x") is False and egg.store.reminders == []


def test_llm_fallback_only_for_command_like_text_and_only_what_is_permitted():
    lang = Lang(raw='{"action": "reminder", "minutes": 15, "text": "ligar pro banco"}')
    acts, *_ = make(lang=lang, reminders=True)
    assert acts.handle_text("me lembra de ligar pro banco daqui a pouquinho") is True
    assert lang.structured and lang.requests == [] and [r.text for r in acts.store.reminders] == ["ligar pro banco"]
    for raw in ('{"action": "none"}', '{"action": "note", "text": "x"}', "garbage",
                '{"action": "shell", "text": "rm -rf ~"}'):
        lang = Lang(raw=raw)
        acts, *_ = make(lang=lang, reminders=True)          # notes are off here: a note intent must not run
        assert acts.handle_text("me lembra disso depois") is True
        assert lang.requests == ["me lembra disso depois"] and acts.store.reminders == [] and acts.memory.facts == {}
    off = Lang(status="missing")
    acts, *_ = make(lang=off, reminders=True)
    assert acts.handle_text("me lembra disso depois") is False and off.structured == []   # no LLM: plain chat (babble)
    none_on = Lang()
    acts, *_ = make(lang=none_on)
    assert acts.handle_text("me lembra disso depois") is False and none_on.structured == []


def test_language_service_structured_request_falls_back_to_chat():
    from engrama.services.language.service import LanguageService
    calls = []

    class Svc:
        status, cfg, client, _chatting = "ready", type("C", (), {"model": "m"})(), None, 0
        _now = staticmethod(lambda: 0.0)

        def _enqueue(self, prio, fn):
            fn()

        def _chat(self, text, t_msg=None):
            calls.append(("chat", text))

    class Client:
        def __init__(self, out):
            self.out = out

        def chat_json(self, model, messages, schema):
            if isinstance(self.out, Exception):
                raise self.out
            return self.out

    for out, handled, expect in (("{}", True, []), ("{}", False, [("chat", "oi")]), (OSError("down"), True, [("chat", "oi")])):
        calls.clear()
        s = Svc()
        s.client = Client(out)
        LanguageService.request_structured(s, "oi", [], {}, lambda raw: handled)
        assert calls == expect and s._chatting == 0
    s = Svc()
    s.status = "loading"
    s.client = Client("{}")
    calls.clear()
    LanguageService.request_structured(s, "oi", [], {}, lambda raw: True)
    assert calls == [("chat", "oi")]


# ---------------------------------------------------------------- window and panel
class G:
    def growl(self, *a):
        pass


def window(acts):
    w = Window(lambda: Snapshot(stage="child", look={"seed": 3}), lambda k, d=None: None, growler=G(),
               language=acts.language)
    w.config = acts.cfg
    w.actions = acts
    return w


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def hit(panel, cmd):
    return next(r for r, c in panel._hits if c == cmd)


def test_chat_box_hands_commands_to_actions_and_everything_else_to_the_llm():
    acts, *_ = make(reminders=True)
    w = window(acts)
    for text in ("me lembra em 5 min de alongar", "oi!"):
        w.chat.text = text
        w.chat.send()
    assert acts.language.requests == ["oi!"] and [r.text for r in acts.store.reminders] == ["alongar"]


def test_panel_drives_all_three_tools_by_menu_without_any_llm():
    acts, _now, _said, _alerts, saves = make(lang=Lang(status="missing"))
    w = window(acts)
    w.open_panel("actions")
    w.frame(1.0)
    p = w.panel
    assert not any(c[0] in ("remind", "focus", "note") for _r, c in p._hits)     # all off: only the switches answer
    for tool in A.TOOLS:
        w.handle_event(click(hit(p, ("perm", tool)).center))
        w.frame(1.0)
    assert all(acts.allowed(t) for t in A.TOOLS) and len(saves) == 3
    for ch in "tirar o bolo":
        w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    w.handle_event(click(hit(p, ("remind", 15)).center))
    assert [(r.text, round(r.due - 1000.0)) for r in acts.store.reminders] == [("tirar o bolo", 900)] and p.text == ""
    for ch in "gosto de chá":
        w.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    w.handle_event(click(hit(p, ("note",)).center))
    assert acts.memory.facts[note_key("gosto de chá")][0] == "gosto de chá"
    w.handle_event(click(hit(p, ("focus", 25)).center))
    w.frame(1.0)
    assert acts.quiet and w._focus_px() >= 1
    w.handle_event(click(hit(p, ("focus_stop",)).center))
    w.frame(1.0)
    assert not acts.quiet and w._focus_px() == 0
    w.handle_event(click(hit(p, ("cancel", acts.store.reminders[0].id)).center))
    assert acts.store.reminders == []


def test_panel_without_the_feature_and_time_left_text():
    from engrama.app.actions import when_text
    from engrama.app.ui.actions_panel import left_text
    assert [when_text(m) for m in (0.5, 20, 1.5, 60, 90)] == ["30 s", "20 min", "1.5 min", "1 h", "1 h 30"]
    acts, *_ = make()
    w = window(acts)
    w.actions = None
    w.open_panel("actions")
    w.frame(1.0)
    w.handle_event(click((320, 240)))
    assert w.panel_name == "actions"
    assert (left_text(40), left_text(61), left_text(12 * 60), left_text(3900)) == ("40 s", "2 min", "12 min", "1 h 05")


def test_config_round_trip_keeps_action_permissions_and_ignores_junk(tmp_path):
    import json
    from engrama.config import Config
    cfg = Config(data_dir=tmp_path)
    assert cfg.action_permissions == {"reminders": False, "focus": False, "notes": False}
    cfg.action_permissions["focus"] = True
    cfg.save(tmp_path / "config.json")
    assert Config.load(tmp_path / "config.json").action_permissions == {"reminders": False, "focus": True, "notes": False}
    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    raw["action_permissions"] = {"shell": True, "notes": 1}
    (tmp_path / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    assert Config.load(tmp_path / "config.json").action_permissions == {"reminders": False, "focus": False, "notes": True}
