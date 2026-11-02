import random

from engrama.services.language.initiative import InitiativePolicy
from engrama.services.memory.store import MemoryStore

T0 = 1_800_000_000.0
HOUR = 3600.0


def make(tmp_path, topics=True, opinion=True, past=False):
    clock = {"t": T0}
    s = MemoryStore(tmp_path / "mem.db", now_fn=lambda: clock["t"])
    if past:
        s.bump_topic("jardim", 0.8)
        clock["t"] += 30 * 86400.0
    if topics:
        s.bump_topic("musica", 0.5)
    if opinion:
        for _ in range(5):
            s.update_opinion("musica", lambda t: 0.3, 0.5)
    return s, clock


def run(policy, hours, *, start=T0, step=60.0, **kw):
    args = dict(stage="adult", user_active=True, llm_ready=True, resting=False,
                fullscreen=False, action="idle")
    args.update(kw)
    fires, t = [], start
    for _ in range(int(hours * HOUR / step)):
        t += step
        r = policy.update(t, **args)
        if r:
            fires.append(r)
    return fires


def test_quota_one_per_active_hour(tmp_path):
    s, clock = make(tmp_path)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    fires = run(p, 10, start=clock["t"])
    assert 1 <= len(fires) <= 10
    s.close()


def test_blocked_states(tmp_path):
    s, clock = make(tmp_path)
    for kw in (dict(stage="baby"), dict(stage="egg"), dict(llm_ready=False),
               dict(resting=True), dict(fullscreen=True)):
        p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
        assert run(p, 10, start=clock["t"], **kw) == []
    s.close()


def test_inactive_time_does_not_count(tmp_path):
    s, clock = make(tmp_path)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    assert run(p, 10, start=clock["t"], user_active=False) == []
    s.close()


def test_quota_persists_across_restart(tmp_path):
    s, clock = make(tmp_path)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    t, fired = clock["t"], None
    while fired is None:
        t += 60.0
        fired = p.update(t, stage="adult", user_active=True, llm_ready=True,
                         resting=False, fullscreen=False, action="ask_attention")
    p2 = InitiativePolicy(s, lambda: t, rng=random.Random(1))
    assert run(p2, 0.9, start=t, action="ask_attention") == []
    assert len(run(p2, 3, start=t + 0.9 * HOUR, action="ask_attention")) >= 1
    s.close()


def test_clock_backwards_safe(tmp_path):
    s, clock = make(tmp_path)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    kw = dict(stage="adult", user_active=True, llm_ready=True, resting=False,
              fullscreen=False, action="ask_attention")
    for i in range(100):
        assert p.update(T0 - i * 1000.0, **kw) is None
    s.close()


def test_kind_by_stage(tmp_path):
    s, clock = make(tmp_path, past=True)
    kw = dict(user_active=True, llm_ready=True, resting=False, fullscreen=False,
              action="ask_attention")

    def first(stage):
        p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
        t = clock["t"]
        for _ in range(2000):
            t += 60.0
            r = p.update(t, stage=stage, **kw)
            if r:
                return r
        return None

    assert first("child") == ("current", "musica")
    assert first("adult") == ("opinion", "musica")
    assert first("perfect") == ("past", "jardim")
    s.close()


def test_activity_alternates_with_current_and_obeys_blocks(tmp_path):
    s, clock = make(tmp_path, opinion=False)
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    kinds = {k for k, _ in run(p, 10, start=clock["t"], stage="child", activity="jogo")}
    assert kinds == {"activity", "current"}
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    assert run(p, 10, start=clock["t"], stage="child", activity="jogo", eyes_closed=True) == []
    p = InitiativePolicy(s, lambda: clock["t"], rng=random.Random(1))
    assert "activity" not in {k for k, _ in run(p, 10, start=clock["t"], stage="child", activity="privado")}
    s.close()
