from scripts.ui_app import SyncTUI, RunOptions


def test_ui_app_initializes_cpu_mem_ema_fields(monkeypatch):
    def fake_load_config(project_root, config_file):
        return {"aws": {"profile": "default"}, "s3": {"bucket_name": "b"}, "sync": {"local_path": "."}}

    monkeypatch.setattr("scripts.ui_app.load_config", fake_load_config)

    opts = RunOptions(config_file=None, profile=None, bucket_name=None, local_path=".")
    app = SyncTUI(opts)

    assert hasattr(app, "_cpu_pct_ema")
    assert hasattr(app, "_mem_pct_ema")
    assert hasattr(app, "_cpu_pct_tau_seconds")
    assert hasattr(app, "_mem_pct_tau_seconds")
    assert isinstance(app._cpu_pct_tau_seconds, float)
    assert isinstance(app._mem_pct_tau_seconds, float)


def test_cpu_mem_ema_returns_smoothed_values(monkeypatch):
    # Prepare app
    def fake_load_config(project_root, config_file):
        return {"aws": {"profile": "default"}, "s3": {"bucket_name": "b"}, "sync": {"local_path": "."}}

    monkeypatch.setattr("scripts.ui_app.load_config", fake_load_config)
    opts = RunOptions(config_file=None, profile=None, bucket_name=None, local_path=".")
    app = SyncTUI(opts)

    # Fake psutil module
    class _FakeVM:
        percent = 42.0

    class _FakePsutil:
        @staticmethod
        def cpu_percent(interval=None):
            return 50.0

        @staticmethod
        def virtual_memory():
            return _FakeVM()

    # Fake time to ensure a non-zero dt across calls
    class _FakeTime:
        _t = 1000.0

        @classmethod
        def monotonic(cls):
            cls._t += 0.5
            return cls._t

    monkeypatch.setattr("scripts.ui_app.psutil", _FakePsutil)
    monkeypatch.setattr("scripts.ui_app.time", _FakeTime)

    # First call seeds EMA and returns 0.0 per implementation
    assert app._current_cpu_percent() == 0.0
    assert app._current_mem_percent() == 0.0

    # Subsequent calls should move towards the sample values (>0 and <sample)
    cpu_val = app._current_cpu_percent()
    mem_val = app._current_mem_percent()
    assert 0.0 < cpu_val < 50.0
    assert 0.0 < mem_val < 42.0


