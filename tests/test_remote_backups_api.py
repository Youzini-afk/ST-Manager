import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import remote_backups as remote_backups_api
from core.services.remote_backup_control_auth import RemoteBackupControlStore
from core.services.remote_backup_incoming_service import RemoteBackupIncomingService
from core.services.remote_backup_scheduler import RemoteBackupScheduleStore
from core.services.remote_backup_service import RemoteBackupConfigStore


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(remote_backups_api.bp)
    return app


def test_config_defaults_to_authority_bridge_mode(tmp_path):
    store = RemoteBackupConfigStore(base_dir=tmp_path / 'remote_backups')

    public = store.public()

    assert public['remote_connection_mode'] == 'authority_bridge'


def test_config_endpoint_persists_connection_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(
        remote_backups_api,
        'RemoteBackupConfigStore',
        lambda: RemoteBackupConfigStore(base_dir=tmp_path / 'remote_backups'),
    )

    response = _make_test_app().test_client().post(
        '/api/remote_backups/config',
        json={
            'st_url': 'https://st.example',
            'remote_connection_mode': 'st_auth',
            'remote_bridge_key': 'secret',
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['config']['remote_connection_mode'] == 'st_auth'


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


def test_incoming_push_endpoints_delegate_to_incoming_service(monkeypatch):
    calls = []

    class FakeIncomingService:
        def start_backup(self, payload):
            calls.append(('start', payload))
            return {'backup_id': 'push-api'}

        def write_file_init(self, payload):
            calls.append(('init', payload))
            return {'upload_id': 'upload-1'}

        def write_file_chunk(self, payload):
            calls.append(('chunk', payload))
            return {'offset': 4}

        def write_file_commit(self, payload):
            calls.append(('commit', payload))
            return {'relative_path': 'Ava.png'}

        def complete_backup(self, backup_id, *, ingest=True):
            calls.append(('complete', backup_id, ingest))
            return {'backup_id': backup_id, 'total_files': 1}

        def read_backup_file(self, payload):
            calls.append(('read', payload))
            return {'data_base64': 'Y2FyZA==', 'bytes_read': 4, 'eof': True}

    monkeypatch.setattr(remote_backups_api, 'RemoteBackupIncomingService', lambda: FakeIncomingService())
    client = _make_test_app().test_client()

    assert client.post('/api/remote_backups/incoming/start', json={'resource_types': ['characters']}).status_code == 200
    assert client.post('/api/remote_backups/incoming/file/write-init', json={'backup_id': 'push-api'}).status_code == 200
    assert client.post('/api/remote_backups/incoming/file/write-chunk', json={'upload_id': 'upload-1'}).status_code == 200
    assert client.post('/api/remote_backups/incoming/file/write-commit', json={'upload_id': 'upload-1'}).status_code == 200
    assert client.post('/api/remote_backups/incoming/complete', json={'backup_id': 'push-api', 'ingest': False}).status_code == 200
    assert client.post('/api/remote_backups/file/read', json={'backup_id': 'push-api'}).status_code == 200

    assert calls == [
        ('start', {'resource_types': ['characters']}),
        ('init', {'backup_id': 'push-api'}),
        ('chunk', {'upload_id': 'upload-1'}),
        ('commit', {'upload_id': 'upload-1'}),
        ('complete', 'push-api', False),
        ('read', {'backup_id': 'push-api'}),
    ]


def test_control_key_rotate_returns_plaintext_once_and_masks_afterward(tmp_path, monkeypatch):
    monkeypatch.setattr(
        remote_backups_api,
        'RemoteBackupControlStore',
        lambda: RemoteBackupControlStore(base_dir=tmp_path / 'remote_backups'),
    )

    client = _make_test_app().test_client()
    rotated = client.post('/api/remote_backups/control-key/rotate').get_json()
    public = client.get('/api/remote_backups/control').get_json()

    assert rotated['success'] is True
    assert rotated['control']['control_key'].startswith('stmc_')
    assert rotated['control']['control_key_masked'].startswith('stmc')
    assert 'control_key_hash' not in json.dumps(rotated, ensure_ascii=False)
    assert 'control_key' not in public['control']
    assert public['control']['control_key_masked'] == rotated['control']['control_key_masked']
    assert public['control']['control_key_fingerprint'] == rotated['control']['control_key_fingerprint']


def test_control_endpoint_advertises_remote_backup_protocol_features(monkeypatch):
    class FakeControlStore:
        def public(self):
            return {'enabled': True}

    monkeypatch.setattr(remote_backups_api, 'RemoteBackupControlStore', lambda: FakeControlStore())

    payload = _make_test_app().test_client().get('/api/remote_backups/control').get_json()

    assert payload['success'] is True
    assert payload['protocol_version'] == 2
    assert payload['features']['incoming_skip_by_sha'] is True


def test_schedule_endpoint_persists_normalized_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(
        remote_backups_api,
        'RemoteBackupScheduleStore',
        lambda: RemoteBackupScheduleStore(base_dir=tmp_path / 'remote_backups'),
    )

    client = _make_test_app().test_client()
    saved = client.post(
        '/api/remote_backups/schedule',
        json={
            'enabled': True,
            'interval_minutes': 30,
            'retention_limit': 3,
            'resource_types': ['characters', 'regex', 'bad'],
        },
    ).get_json()
    loaded = client.get('/api/remote_backups/schedule').get_json()

    assert saved['success'] is True
    assert saved['schedule']['enabled'] is True
    assert saved['schedule']['interval_minutes'] == 30
    assert saved['schedule']['retention_limit'] == 3
    assert saved['schedule']['resource_types'] == ['characters', 'regex']
    assert saved['schedule']['next_run_at']
    assert loaded['schedule'] == saved['schedule']
