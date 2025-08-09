from __future__ import annotations

import math


def exponential_moving_average(
    previous_value: float | None,
    sample_value: float,
    delta_seconds: float,
    time_constant_seconds: float,
) -> float:
    """Compute an exponential moving average (EMA) update.

    The smoothing factor alpha is computed from the elapsed time and the
    chosen time constant: alpha = 1 - exp(-dt / tau).

    - If previous_value is None, returns the sample_value (EMA seed).
    - If dt <= 0 or tau <= 0, returns the sample_value.
    """
    if previous_value is None:
        return float(sample_value)
    if delta_seconds <= 0 or time_constant_seconds <= 0:
        return float(sample_value)
    alpha = 1.0 - math.exp(-float(delta_seconds) / float(time_constant_seconds))
    # Clamp alpha to [0,1] for numerical safety
    if alpha < 0.0:
        alpha = 0.0
    elif alpha > 1.0:
        alpha = 1.0
    return float(previous_value) + alpha * (float(sample_value) - float(previous_value))


