"""M20: intent parsing (the PT/EN harness), validation of LLM output, and the reminder / focus store."""
import json
import pytest
from engrama.services import actions as A
from engrama.services.actions import Intent

# (message, kind, minutes, text) -- the harness: every line a person might plausibly type
COMMANDS = [
    ("me lembra em 20 min de tirar o bolo", "reminder", 20, "tirar o bolo"),
    ("me lembre daqui a 5 minutos de beber água", "reminder", 5, "beber água"),
    ("Em 10 minutos me avisa que a reunião começa", "reminder", 10, "a reunião começa"),
    ("me avisa em meia hora", "reminder", 30, ""),
    ("lembra-me em 1 hora de ligar pra mãe", "reminder", 60, "ligar pra mãe"),
    ("me lembra daqui a uma hora e meia de sair", "reminder", 90, "sair"),
    ("pode me lembrar em 45 min do remédio?", "reminder", 45, "remédio"),
    ("timer de 3 minutos", "reminder", 3, ""),
    ("põe um alarme pra daqui a 15 min", "reminder", 15, ""),
    ("me lembra em 30 segundos de testar", "reminder", 0.5, "testar"),
    ("me avisa em 2h pra buscar as crianças", "reminder", 120, "buscar as crianças"),
    ("lembrete em 1,5 hora: enviar o relatório", "reminder", 90, "enviar o relatório"),
    ("remind me in 20 minutes to take the cake out", "reminder", 20, "take the cake out"),
    ("in 10 min remind me to call Ana", "reminder", 10, "call Ana"),
    ("remind me in an hour about the meeting", "reminder", 60, "the meeting"),
    ("set a timer for 5 minutes", "reminder", 5, ""),
    ("remind me in half an hour to stretch", "reminder", 30, "stretch"),
    ("please remind me in 2 hours to eat", "reminder", 120, "eat"),
    ("foco por 25 min", "focus", 25, ""),
    ("modo foco", "focus", 25, ""),
    ("pomodoro", "focus", 25, ""),
    ("vamos focar por 50 minutos", "focus", 50, ""),
    ("quero foco de uma hora", "focus", 60, ""),
    ("bora pomodoro de 15 min", "focus", 15, ""),
    ("focus for 30 minutes", "focus", 30, ""),
    ("start a pomodoro", "focus", 25, ""),
    ("let's focus for an hour", "focus", 60, ""),
    ("para o foco", "focus_stop", 0, ""),
    ("cancela o pomodoro", "focus_stop", 0, ""),
    ("stop the focus session", "focus_stop", 0, ""),
    ("anota isso: a senha do wifi mudou", "note", 0, "a senha do wifi mudou"),
    ("anota: comprar ração", "note", 0, "comprar ração"),
    ("anote que a Bia faz aniversário em maio", "note", 0, "a Bia faz aniversário em maio"),
    ("toma nota: dentista na quinta", "note", 0, "dentista na quinta"),
    ("guarda isso: prefiro café sem açúcar", "note", 0, "prefiro café sem açúcar"),
    ("note that my sister is called Lia", "note", 0, "my sister is called Lia"),
    ("write this down: buy cat food", "note", 0, "buy cat food"),
    ("remember that I like green tea", "note", 0, "I like green tea"),
]
TALK = [
    "oi, tudo bem?", "hoje eu não consegui manter o foco em nada, que dia", "você lembra do que eu te contei ontem?",
    "meu foco ultimamente tem sido o trabalho e isso me cansa bastante", "qual é a sua comida favorita?",
    "eu anotei tudo no caderno", "passei 20 minutos no trânsito", "em 2 horas eu saio daqui", "do you remember me?",
    "I lost my focus at work today and it made me sad all afternoon", "what time is it?", "that was a nice note",
    "me lembra às 15h da reunião", "remind me at 5 to leave", "o timer do forno quebrou", "boa noite!",
    "eu te aviso quando chegar", "gosto de você", "I worked for 3 hours straight", "",
]


def test_harness_extraction_rate_and_no_false_alarms():
    hits = 0
    for msg, kind, minutes, text in COMMANDS:
        got = A.parse_intent(msg)
        ok = (got is not None and got.kind == kind and got.minutes == pytest.approx(minutes) and got.text == text)
        hits += ok
        assert got is None or got.kind == kind, (msg, got)     # a wrong action is worse than no action
    rate = hits / len(COMMANDS)
    assert rate >= 0.95, f"extraction rate {rate:.0%}: " + "; ".join(
        f"{m!r} -> {A.parse_intent(m)}" for m, k, mi, t in COMMANDS
        if A.parse_intent(m) != Intent(k, float(mi), t))
    assert [m for m in TALK if A.parse_intent(m) is not None] == []


def test_validation_bounds_every_intent_whatever_its_source():
    assert A.valid(Intent("reminder", 20, " de tirar o bolo. ")) == Intent("reminder", 20.0, "tirar o bolo")
    assert A.valid(Intent("reminder", 0, "x")) is None and A.valid(Intent("reminder", 25 * 60, "x")) is None
    assert A.valid(Intent("note", 0, "   ")) is None and A.valid(Intent("shell", 1, "rm -rf")) is None
    assert len(A.valid(Intent("note", 0, "x" * 500)).text) == A.MAX_TEXT
    assert A.valid(Intent("focus", 25, "ignored")) == Intent("focus", 25.0, "")


def test_llm_json_goes_through_the_same_gate():
    f = A.intent_from_json
    assert f('{"action": "reminder", "minutes": 20, "text": "tirar o bolo"}') == Intent("reminder", 20.0, "tirar o bolo")
    assert f('sure! {"action":"focus"}') == Intent("focus", A.FOCUS_DEFAULT_MIN, "")
    assert f('{"action": "note", "text": "comprar pão"}') == Intent("note", 0.0, "comprar pão")
    for bad in ('{"action": "none"}', '{"action": "run", "text": "ls"}', '{"action": "reminder", "minutes": "20"}',
                '{"action": "reminder", "minutes": -5}', '{"action": "reminder", "minutes": true, "text": "x"}',
                '{"action": "note"}', "not json", "", '["reminder"]', '{"action": "reminder", "minutes": 99999}'):
        assert f(bad) is None, bad
    assert A.INTENT_SCHEMA["properties"]["action"]["enum"] == ["reminder", "focus", "note", "none"]
    assert A.looks_like_command("me lembra da reunião amanhã") and not A.looks_like_command("oi, tudo bem?")
    assert not A.looks_like_command("me lembra às 15h da reunião")


def test_store_reminders_fire_once_in_order_and_survive_a_restart(tmp_path):
    now = [1000.0]
    path = tmp_path / "actions.json"
    st = A.ActionStore(path, lambda: now[0])
    a = st.add_reminder(10, "b")
    b = st.add_reminder(1, "a")
    assert [r.text for r in st.reminders] == ["a", "b"] and a.id != b.id
    assert st.pop_due() == []
    st2 = A.ActionStore(path, lambda: now[0])                 # restart
    assert [(r.id, r.text) for r in st2.reminders] == [(b.id, "a"), (a.id, "b")]
    now[0] += 61
    assert [r.text for r in st2.pop_due()] == ["a"] and st2.pop_due() == []
    assert st2.cancel(a.id) and not st2.cancel(a.id) and st2.reminders == []
    assert json.loads(path.read_text(encoding="utf-8"))["reminders"] == []
    for i in range(A.MAX_REMINDERS + 5):
        st2.add_reminder(5, f"r{i}")
    assert len(st2.reminders) == A.MAX_REMINDERS and st2.add_reminder(5, "extra") is None
    assert st2.add_reminder(0, "x") is None


def test_store_focus_session_ends_once(tmp_path):
    now = [0.0]
    st = A.ActionStore(tmp_path / "a.json", lambda: now[0])
    assert not st.focus_active and st.focus_progress() == 0.0 and not st.pop_focus_done()
    assert st.start_focus(25) and st.focus_active and st.focus_left() == 1500
    now[0] = 750
    assert st.focus_progress() == pytest.approx(0.5)
    assert A.ActionStore(tmp_path / "a.json", lambda: now[0]).focus_left() == 750    # survives a restart
    now[0] = 1500
    assert st.pop_focus_done() and not st.pop_focus_done() and not st.focus_active
    assert st.start_focus(25) and st.stop_focus() and not st.stop_focus()


def test_a_broken_store_file_starts_empty(tmp_path):
    p = tmp_path / "a.json"
    p.write_text("{nope", encoding="utf-8")
    st = A.ActionStore(p, lambda: 0.0)
    assert st.reminders == [] and not st.focus_active
    assert A.ActionStore(None, lambda: 0.0).add_reminder(5, "x").text == "x"     # no path: memory only
