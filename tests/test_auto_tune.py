from core.auto_tune import SystemSnapshot, estimate_upload_workers, estimate_check_workers, estimate_worker_counts


def test_estimate_upload_workers_scales_with_cpu_and_mem():
    # Plenty of memory: expect about 2x CPU but capped reasonably
    sys1 = SystemSnapshot(cpu_count_logical=8, total_memory_bytes=32 * 1024**3, available_memory_bytes=24 * 1024**3)
    w1 = estimate_upload_workers(chunk_size_mb=100, system=sys1)
    assert 8 <= w1 <= 16

    # Tight memory: should reduce workers due to memory constraint
    sys2 = SystemSnapshot(cpu_count_logical=8, total_memory_bytes=4 * 1024**3, available_memory_bytes=512 * 1024**2)
    w2 = estimate_upload_workers(chunk_size_mb=256, system=sys2)
    assert 1 <= w2 < w1


def test_estimate_check_workers_scales_with_cpu():
    sys1 = SystemSnapshot(cpu_count_logical=4, total_memory_bytes=None, available_memory_bytes=None)
    c1 = estimate_check_workers(system=sys1)
    assert c1 >= 4 and c1 <= 64

    sys2 = SystemSnapshot(cpu_count_logical=32, total_memory_bytes=None, available_memory_bytes=None)
    c2 = estimate_check_workers(system=sys2)
    assert c2 >= c1 and c2 <= 64


def test_estimate_worker_counts_tuple():
    sys1 = SystemSnapshot(cpu_count_logical=4, total_memory_bytes=16 * 1024**3, available_memory_bytes=8 * 1024**3)
    up, chk = estimate_worker_counts(100, sys1)
    assert isinstance(up, int) and isinstance(chk, int)
    assert up >= 1 and chk >= 1


