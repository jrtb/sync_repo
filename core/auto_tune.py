from __future__ import annotations

"""
Worker auto-tuning heuristics.

These functions estimate reasonable defaults for concurrent workers based on
CPU count, available memory, and chunk size. The goal is to avoid
overcommitting memory while providing sufficient parallelism to saturate
network and I/O on typical developer and server machines.
"""

from dataclasses import dataclass


@dataclass
class SystemSnapshot:
    cpu_count_logical: int
    total_memory_bytes: int | None
    available_memory_bytes: int | None


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def estimate_upload_workers(
    chunk_size_mb: int,
    system: SystemSnapshot,
    hard_cap: int = 32,
) -> int:
    """Estimate number of concurrent upload workers.

    Heuristics:
    - CPU bound: <= 2x logical cores
    - Memory bound: use at most ~25% of available memory for in-flight buffers
      assuming ~2× chunk size per worker (multipart buffers + overhead)
    - Hard cap for safety
    """
    cpu = max(1, int(system.cpu_count_logical or 1))
    available_bytes = system.available_memory_bytes or 0
    # Assume each worker might hold ~2x chunk in memory at times
    per_worker_bytes = max(8, int(chunk_size_mb)) * 1024 * 1024 * 2
    if available_bytes <= 0:
        max_by_mem = 1
    else:
        max_by_mem = max(1, int((available_bytes * 0.25) // per_worker_bytes))

    max_by_cpu = max(1, min(hard_cap, cpu * 2))

    estimate = min(hard_cap, max_by_cpu, max_by_mem)
    return clamp(int(estimate), 1, hard_cap)


def estimate_check_workers(
    system: SystemSnapshot,
    hard_cap: int = 64,
) -> int:
    """Estimate number of concurrent HEAD/check workers.

    Checks are lightweight (network + small JSON). Favor higher parallelism
    bounded by CPU and a conservative hard cap to avoid overwhelming the API.
    """
    cpu = max(1, int(system.cpu_count_logical or 1))
    estimate = min(hard_cap, cpu * 4)
    return clamp(int(estimate), 1, hard_cap)


def estimate_worker_counts(
    chunk_size_mb: int,
    system: SystemSnapshot,
) -> tuple[int, int]:
    """Return (uploads, checks) worker estimates."""
    return (
        estimate_upload_workers(chunk_size_mb, system),
        estimate_check_workers(system),
    )


