from pathlib import Path

from scripts.ui_app import SyncTUI


def test_build_overview_line_with_identity_and_counts():
    identity = {
        'account_id': '123456789012',
        'account_alias': 'prod',
        'username': 's3-sync-user',
        'region': 'us-east-1',
    }
    lines = SyncTUI.build_overview_line(Path('/data/photos'), 'my-bucket', identity, 1234, 10 * 1024 * 1024 * 1024, status='check complete')
    assert isinstance(lines, list) and len(lines) >= 1
    text = " ".join(lines)
    assert 'Sync: [/data/photos] => [s3://my-bucket]' in text
    assert 'AWS: prod/s3-sync-user @us-east-1' in text
    assert 'Files: 1234' in text
    assert 'Size: 10.0 GB' in text
    assert 'Status: check complete' in text


def test_build_overview_line_without_identity_or_counts():
    lines = SyncTUI.build_overview_line(Path('/tmp/data'), 'bucket-1', None, None, None, status='preparing')
    text = " ".join(lines)
    assert 'AWS: unknown' in text
    assert 'Files: …' in text and 'Size: …' in text
    assert 'preparing' in text


