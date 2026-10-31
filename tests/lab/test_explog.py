import numpy as np
from engrama.lab.explog import ExperienceLog, read_log, list_runs
from engrama.mind.contracts import Experience, Observation, Proposal


def mk(t, events=(), dt=60.0):
    ch = {"body.needs": np.linspace(0, 1, 6)}
    return Experience(t=t, dt=dt, events=tuple(events), channels=ch, action="idle",
                      action_prob=0.5, rewards={"a": 1.0}, next_channels=ch)


def test_roundtrip_rows_and_channels(tmp_path):
    p = tmp_path / "log.db"
    log = ExperienceLog(p, "r1", "rec", 7)
    ev = Observation(60.0, "fed", {"x": 1})
    log.write(mk(60.0, [ev]), [Proposal("eat", 0.9, "hungry", "drives")], [Proposal("play", 0.1, "s", "shadow")])
    log.close()
    rows = list(read_log(p))
    assert len(rows) == 1
    r = rows[0]
    assert r.t == 60.0 and r.dt == 60.0 and r.action == "idle" and r.prob == 0.5
    assert r.rewards == {"a": 1.0}
    assert r.events == [{"t": 60.0, "kind": "fed", "data": {"x": 1}}]
    assert r.proposals[0] == {"action": "eat", "score": 0.9, "reason": "hungry", "source": "drives"}
    assert r.shadow[0]["action"] == "play"
    np.testing.assert_allclose(r.channels["body.needs"], np.linspace(0, 1, 6), atol=1e-6)
    assert r.channels["body.needs"].dtype == np.float32


def test_channel_sampling_interval(tmp_path):
    p = tmp_path / "log.db"
    log = ExperienceLog(p, "r1", "rec", 1, sample_s=600.0)
    for i in range(1, 31):
        log.write(mk(60.0 * i), [], [])
    log.close()
    rows = list(read_log(p))
    assert sum(1 for r in rows if r.channels) == 3


def test_events_force_channel_snapshot(tmp_path):
    p = tmp_path / "log.db"
    log = ExperienceLog(p, "r1", "rec", 1, sample_s=600.0)
    log.write(mk(60.0), [], [])
    log.write(mk(120.0, [Observation(120.0, "fed", {})]), [], [])
    log.close()
    rows = list(read_log(p))
    assert rows[1].channels


def test_private_event_redacted(tmp_path):
    p = tmp_path / "log.db"
    log = ExperienceLog(p, "r1", "rec", 1)
    log.write(mk(60.0, [Observation(60.0, "fed", {"private": True, "secret": "x"})]), [], [])
    log.close()
    assert list(read_log(p))[0].events[0]["data"] == {"private": True}


def test_rotation_keeps_newest(tmp_path):
    p = tmp_path / "log.db"
    log = ExperienceLog(p, "r1", "rec", 1, max_rows=100)
    for i in range(150):
        log.write(mk(float(i)), [], [])
    log.close()
    ts = [r.t for r in read_log(p)]
    assert len(ts) <= 100 and ts[-1] == 149.0
    assert ts == sorted(ts) and ts[0] >= 50.0


def test_multiple_runs_latest_default(tmp_path):
    p = tmp_path / "log.db"
    for rid in ("a", "b"):
        log = ExperienceLog(p, rid, "rec", 1)
        log.write(mk(60.0), [], [])
        log.write(mk(120.0), [], [])
        log.close()
    log = ExperienceLog(p, "b", "rec", 1)  # reopen same run
    log.close()
    assert [r["run_id"] for r in list_runs(p)] == ["a", "b"]
    assert len(list(read_log(p))) == 2
    assert len(list(read_log(p, "a"))) == 2
