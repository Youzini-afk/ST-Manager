import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import remote_backups as remote_backups_api
from core.services.remote_backup_service import RemoteBackupConfigStore


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(remote_backups_api.bp)
    return app


def test_config_endpoint_masks_saved_bridge_key(tmp_path, monkeypatch):
    monkeypatch.setattr(
        remote_backups_api,
        'RemoteBackupConfigStore',
        lambda: RemoteBackupConfigStore(base_dir=tmp_path / 'remote_backups'),
    )

    response = _make_test_app().test_client().post(
        '/api/remote_backups/config',
        json={
            'st_url': 'http://st.example',
            'remote_bridge_key': 'super-secret-key',
            'enabled_resource_types': ['characters'],
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['config']['bridge_key_masked'] == 'supe...-key'
    assert payload['config']['bridge_key_fingerprint']
    assert 'super-secret-key' not in json.dumps(payload, ensure_ascii=False)


def test_start_endpoint_delegates_backup_request(monkeypatch):
    calls = []

    class FakeService:
        def create_backup(self, **kwargs):
            calls.append(kwargs)
            return {'backup_id': 'backup-api', 'total_files': 1}

    monkeypatch.setattr(remote_backups_api, 'RemoteBackupService', lambda: FakeService())

    response = _make_test_app().test_client().post(
        '/api/remote_backups/start',
        json={
            'resource_types': ['characters'],
            'backup_id': 'backup-api',
            'description': 'manual',
            'ingest': False,
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {'success': True, 'backup': {'backup_id': 'backup-api', 'total_files': 1}}
    assert calls == [
        {
            'resource_types': ['characters'],
            'backup_id': 'backup-api',
            'description': 'manual',
            'ingest': False,
        }
    ]
