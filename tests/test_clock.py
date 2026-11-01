from engrama.clock import SimClock


def test_clock_scale_and_clamp():
    t = iter([0.0, 1.0, 1000.0, 999.0])
    clock = SimClock(time_scale=60, now_fn=lambda: next(t))
    assert clock.advance() == 60
    assert clock.advance() == 5 * 60
    assert clock.advance() == 0
    assert clock.sim_time == 360
