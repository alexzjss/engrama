import re
import threading
import time

import pytest

from engrama.config import Config
from engrama.services.language.client import LLMOffline
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import MAX_INPUT, OFFLINE_COOLDOWN, LanguageService
from engrama.services.memory.store import MemoryStore, WorkingMemory


class FakeClient:
    def __init__(self, reply="oi amigo", warm_exc=None, gate=None):
        self.reply, self.warm_exc, self.gate = reply, warm_exc, gate
        self.calls, self.chats, self.unloads, self.warms = [], [], 0, 0

    def warm(self, model):
        self.warms += 1
        if self.gate:
            self.gate.wait(5)
        if self.warm_exc:
            raise self.warm_exc

    def unload(self, model):
        self.unloads += 1

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        return self.reply

    def tags(self):
        return {"qwen3:1.7b"}

    def pull(self, name, on_progress):
        on_progress(50, "x")


class FakeServer:
    def __init__(self, available=True):
        self._a = available

    def available(self):
        return self._a

    def running(self):
        return True

    def start(self):
        return True


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def make(tmp_path, client=None, server=None, sync=True, stage="baby", idle=lambda: True, clock=None):
    cfg = Config(data_dir=tmp_path)
    mem = MemoryStore(tmp_path / "m.sqlite")
    work = WorkingMemory()
    state = PersonaState(stage=stage)
    svc = LanguageService(client or FakeClient(), server or FakeServer(), cfg, mem, work,
                          lambda: state, lambda i, l: i, idle=idle, now_fn=clock or Clock(), sync=sync)
    return svc, mem, work


def _sys(client, prefix):
    return next(m[0]["content"] for m in client.chats if m[-1]["content"].startswith(prefix))


def get(svc, timeout=1.0):
    return svc.replies.get(timeout=timeout)


def _wait_until(cond, timeout=10.0):
    deadline = time.monotonic() + timeout
    while not cond() and time.monotonic() < deadline:
        time.sleep(0.005)
    return cond()


def test_offline_babbles_and_retries_after_cooldown(tmp_path):
    clock = Clock()
    client = FakeClient(warm_exc=LLMOffline("down"))
    svc, _, _ = make(tmp_path, client=client, sync=False, clock=clock)
    try:
        svc.request("oi")
        r = get(svc, timeout=10.0)
        assert r.source == "babble"
        assert _wait_until(lambda: client.warms >= 1)
        assert client.warms == 1
        # warms is bumped before the failure is handled: wait for the cooldown to be armed (state offline,
        # _down_until set from the *current* clock) before moving the fake clock, else the window shifts
        assert _wait_until(lambda: svc._state == "offline" and svc._down_until > clock.t)
        clock.t += OFFLINE_COOLDOWN - 1          # still cooling down
        svc.request("oi de novo")
        assert get(svc, timeout=10.0).source == "babble"
        time.sleep(0.1)
        assert client.warms == 1
        clock.t += 2                              # cooldown over
        svc.request("oi outra vez")
        assert get(svc, timeout=10.0).source == "babble"
        assert _wait_until(lambda: client.warms >= 2)
        assert client.warms == 2
    finally:
        svc.shutdown()


def test_loading_babbles_with_hint(tmp_path):
    gate = threading.Event()
    svc, _, _ = make(tmp_path, client=FakeClient(gate=gate), sync=False)
    try:
        svc.request("oi")
        r = get(svc)
        assert r.source == "babble"
        assert "cérebro carregando" in r.text
        assert svc.status == "loading"
    finally:
        gate.set()
        svc.shutdown()


def test_ready_replies_in_message_language(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client)
    svc.request("oi, você quer comer?")
    svc.pump()
    r = get(svc)
    assert r.source == "llm" and r.lang == "pt"
    assert _sys(client, "oi, você").endswith("Responda em português.")
    svc.request("hello, do you want to eat?")
    svc.pump()
    assert get(svc).lang == "en"
    assert _sys(client, "hello,").endswith("Reply in English.")
    assert svc.status == "ready"


def test_llm_reply_is_cleaned(tmp_path):
    svc, _, _ = make(tmp_path, client=FakeClient(reply="oi 42 amigo \U0001F600 tudo bem hoje sim"))
    svc.request("oi")
    svc.pump()
    r = get(svc)
    assert r.source == "llm" and not re.search(r"\d", r.text) and len(r.text.split()) <= 6


def test_assistant_reply_falls_back_to_babble(tmp_path):
    svc, _, _ = make(tmp_path, client=FakeClient(reply="Como posso ajudar?"))
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "babble"


def test_input_truncated_to_500(tmp_path):
    client = FakeClient()
    svc, mem, work = make(tmp_path, client=client)
    svc.request("a" * 900)
    svc.pump()
    assert len(client.chats[0][-1]["content"]) == MAX_INPUT
    assert len(work.messages()[0]["content"]) == MAX_INPUT


def test_empty_input_ignored(tmp_path):
    client = FakeClient()
    svc, mem, work = make(tmp_path, client=client)
    svc.request("")
    svc.request("   \n ")
    svc.request(None)
    assert svc.pump() == 0
    assert svc.replies.empty() and not work.messages() and not client.chats


def test_missing_server_status(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client, server=FakeServer(available=False))
    assert svc.status == "missing"
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "babble"
    assert client.warms == 0 and not client.chats


def test_egg_always_babbles(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client, stage="egg")
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "babble"
    assert not client.chats


def test_unload_after_keep_alive(tmp_path):
    clock = Clock()
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client, clock=clock)
    svc.request("oi")
    svc.pump()
    t0 = clock.t
    svc.tick(t0 + 100)
    assert client.unloads == 0
    svc.tick(t0 + 601)
    svc.tick(t0 + 700)
    assert client.unloads == 1
    assert svc.status == "offline"


def test_background_jobs_wait_for_idle(tmp_path):
    idle = {"v": False}
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client, idle=lambda: idle["v"])
    svc.request("oi")                      # warms, replies, queues a facts job (prio 3)
    svc.pump()
    chats = len(client.chats)
    ran = []
    svc.submit_job(2, lambda: ran.append("reflect"))
    svc.comment("olha isso")
    svc.pump()
    assert not ran and len(client.chats) == chats      # busy: nothing in background
    svc.request("oi")                                   # chat still runs when not idle
    svc.pump()
    assert get(svc).source == "llm"
    idle["v"] = True
    svc.pump()
    assert ran == ["reflect"]
    assert svc._jobs == []


def test_priority_order(tmp_path):
    svc, _, _ = make(tmp_path)
    svc.request("oi")
    svc.pump()
    order = []
    svc.submit_job(3, lambda: order.append("facts"))
    svc.submit_job(2, lambda: order.append("reflect"))
    svc.submit_job(1, lambda: order.append("comment"))
    svc.request("quer brincar?")
    svc.pump()
    assert order == ["comment", "reflect", "facts"] or order[-1] == "facts"
    assert order.index("comment") < order.index("reflect") < order.index("facts")


def test_chat_recorded_in_working_and_episodic_memory(tmp_path):
    svc, mem, work = make(tmp_path)
    svc.request("eu te amo 100 vezes \U0001F600")
    svc.pump()
    msgs = work.messages()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    rec = mem.recent(1)
    assert rec and not re.search(r"\d", rec[0]) and "amo" in rec[0]
    row = mem._db.execute("SELECT kind, valence FROM episodes").fetchone()
    assert row[0] == "chat" and row[1] > 0


def test_babble_also_recorded(tmp_path):
    svc, mem, work = make(tmp_path, server=FakeServer(available=False))
    svc.request("oi")
    svc.pump()
    assert len(work.messages()) == 2 and mem.recent(1)


def test_facts_extracted_when_idle(tmp_path):
    client = FakeClient(reply='oi {"facts":[["nome","Ana",0.9]],"topics":[["musica",0.5]],"valence":0.2}')
    svc, mem, _ = make(tmp_path, client=client)
    svc.request("oi, meu nome é Ana")
    svc.pump()
    assert ("nome", "Ana") in mem.facts()


def test_pull_and_installed_models(tmp_path):
    svc, _, _ = make(tmp_path)
    seen = []
    svc.pull("m", lambda p, s: seen.append(p))
    assert seen == [50] and svc.status != "pulling"
    assert svc.installed_models() == {"qwen3:1.7b"}


def test_pull_failure_reports_minus_one(tmp_path):
    client = FakeClient()
    client.pull = lambda n, cb: (_ for _ in ()).throw(RuntimeError("boom"))
    svc, _, _ = make(tmp_path, client=client)
    seen = []
    svc.pull("m", lambda p, s: seen.append((p, s)))
    assert seen[0][0] == -1 and "boom" in seen[0][1]


@pytest.mark.perf
def test_shutdown_is_fast_even_when_worker_blocked(tmp_path):
    gate = threading.Event()
    client = FakeClient(gate=gate)
    client.chat = lambda *a, **k: gate.wait(10) or "x"
    svc, _, _ = make(tmp_path, client=client, sync=False)
    svc.request("oi")
    time.sleep(0.05)
    t0 = time.monotonic()
    svc.shutdown()
    assert time.monotonic() - t0 <= 1.0
    gate.set()


def _wait(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        time.sleep(0.01)
    return cond()


def test_pending_message_answered_after_warm(tmp_path):
    gate = threading.Event()
    client = FakeClient(reply="oi amigo", gate=gate)
    svc, _, work = make(tmp_path, client=client, sync=False)
    try:
        svc.request("oi")
        r = get(svc)
        assert r.source == "babble" and "cérebro carregando" in r.text
        assert svc.busy                       # waiting on warm-up counts as thinking
        gate.set()
        r2 = get(svc, 3.0)
        assert r2.source == "llm" and r2.text
        assert [m["content"] for m in work.messages() if m["role"] == "user"] == ["oi"]
        assert _wait(lambda: not svc.busy)
    finally:
        gate.set()
        svc.shutdown()


def test_pending_answered_in_sync_mode_without_duplicate_user_turn(tmp_path):
    client = FakeClient()
    svc, mem, work = make(tmp_path, client=client)
    svc._state = "loading"
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "babble"
    assert not client.chats
    svc.warm()                                # warm succeeds inline
    svc.pump()
    r = get(svc)
    assert r.source == "llm"
    users = [m for m in work.messages() if m["role"] == "user"]
    assert len(users) == 1
    assert sum(1 for m in client.chats[0] if m["content"] == "oi") == 1   # prompt has the turn once
    assert len(mem._db.execute("SELECT 1 FROM episodes WHERE kind='chat'").fetchall()) == 1


def test_pending_dropped_if_warm_fails(tmp_path):
    client = FakeClient(warm_exc=LLMOffline("down"))
    svc, _, _ = make(tmp_path, client=client)
    svc._state = "loading"
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "babble"
    svc.warm()
    svc.pump()
    assert svc.replies.empty() and not client.chats
    assert not svc.busy


def test_only_latest_pending_is_answered(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client)
    svc._state = "loading"
    svc.request("primeira")
    svc.request("segunda")
    svc.pump()
    svc.warm()
    svc.pump()
    sources = []
    while not svc.replies.empty():
        sources.append(svc.replies.get().source)
    assert sources == ["babble", "babble", "llm"]
    chats = [c for c in client.chats if "JSON" not in c[0]["content"]]
    assert len(chats) == 1 and chats[0][-1]["content"].startswith("segunda")


def test_pending_not_answered_after_newer_llm_reply(tmp_path):
    client = FakeClient()
    svc, _, _ = make(tmp_path, client=client)
    svc._state = "loading"
    svc.request("velha")
    svc.pump()
    get(svc)
    svc._state = "ready"                      # warm finished elsewhere, no pending job queued
    svc.request("nova")
    svc.pump()
    assert get(svc).source == "llm"
    svc._answer_pending(("velha", "pt", []))  # stale job must be a no-op
    assert svc.replies.empty()


def test_busy_true_during_chat_call(tmp_path):
    class Blocking(FakeClient):
        def __init__(self):
            super().__init__()
            self.started, self.release = threading.Event(), threading.Event()

        def chat(self, *a, **k):
            self.started.set()
            self.release.wait(5)
            return "oi amigo"

    client = Blocking()
    svc, _, _ = make(tmp_path, client=client, sync=False)
    try:
        assert not svc.busy
        svc.request("oi")
        assert _wait(lambda: svc.busy)
        client.release.set()
        assert _wait(lambda: not svc.busy)
    finally:
        client.release.set()
        svc.shutdown()


class SeqClient(FakeClient):
    def __init__(self, replies):
        super().__init__()
        self.seq = list(replies)

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


def test_repeat_of_recent_reply_is_rejected_then_retried(tmp_path):
    svc, _, _ = make(tmp_path, client=SeqClient(["oi amigo", "oi amigo!", "tudo bem hoje"]))
    svc.request("oi")
    svc.pump()
    assert get(svc).text == "oi amigo"
    svc.request("e aí")
    svc.pump()
    r = get(svc)       # first attempt repeats the stock line, the retry at 0.9 is new
    assert r.source == "llm" and r.text == "tudo bem hoje"


def test_repeat_twice_falls_back_to_babble(tmp_path):
    svc, _, _ = make(tmp_path, client=SeqClient(["oi amigo"]))
    svc.request("oi")
    svc.pump()
    assert get(svc).source == "llm"
    svc.request("e aí")
    svc.pump()
    assert get(svc).source == "babble"
