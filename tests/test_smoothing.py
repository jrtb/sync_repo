import math

from core.smoothing import exponential_moving_average


def test_ema_seeds_with_sample_when_no_previous():
    assert exponential_moving_average(None, 10.0, 1.0, 5.0) == 10.0


def test_ema_returns_sample_if_nonpositive_dt_or_tau():
    # Non-positive dt
    assert exponential_moving_average(5.0, 10.0, 0.0, 5.0) == 10.0
    # Non-positive tau
    assert exponential_moving_average(5.0, 10.0, 1.0, 0.0) == 10.0


def test_ema_moves_towards_sample_with_reasonable_alpha():
    prev = 0.0
    sample = 10.0
    dt = 1.0
    tau = 5.0
    updated = exponential_moving_average(prev, sample, dt, tau)
    # alpha = 1 - exp(-1/5) ~ 0.1813, so result ~ 1.813
    assert 1.7 < updated < 1.9


def test_ema_multiple_steps_monotonic_increase_when_sample_constant():
    # Seed EMA below the sample to observe monotonic increase
    value = 0.0
    sample = 10.0
    tau = 5.0
    # simulate five 1-second samples
    results = []
    for _ in range(5):
        value = exponential_moving_average(value, sample, 1.0, tau)
        results.append(value)
    # Should be strictly increasing and below sample
    assert all(x < sample for x in results)
    assert all(results[i] < results[i+1] for i in range(len(results)-1))


