from scripts.ui_app import SyncTUI, RunOptions


def test_ui_app_initializes_net_ema_fields(monkeypatch):
    # Provide minimal options and monkeypatch load_config to avoid file IO
    def fake_load_config(project_root, config_file):
        return {"aws": {"profile": "default"}, "s3": {"bucket_name": "b"}, "sync": {"local_path": "."}}

    monkeypatch.setattr("scripts.ui_app.load_config", fake_load_config)

    opts = RunOptions(config_file=None, profile=None, bucket_name=None, local_path=".")
    app = SyncTUI(opts)
    assert hasattr(app, "_net_bw_ema_mb_s")
    assert hasattr(app, "_net_bw_tau_seconds")
    assert isinstance(app._net_bw_tau_seconds, float)


