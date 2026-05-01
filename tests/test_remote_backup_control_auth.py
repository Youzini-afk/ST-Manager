import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import core.auth as auth_module
from core.auth import init_auth
from core.services.remote_backup_control_auth import RemoteBackupControlStore


def test_control_store_authorizes_only_rotated_key(tmp_path):
    store = RemoteBackupControlStore(base_dir=tmp_path / 'remote_backups')
    rotated = store.rotate()

    assert store.authorize(rotated['control_key']) is True
    assert store.authorize('wrong') is False
    assert 'control_key_hash' not in rotated


def test_global_auth_allows_valid_remote_backup_control_request(monkeypatch):
    app = Flask(__name__)

    @app.route('/api/remote_backups/probe', methods=['POST'])
    def probe():
        return {'success': True}

    monkeypatch.setattr(auth_module, 'load_config', lambda: {
        'auth_username': 'admin',
        'auth_password': 'secret',
        'auth_trusted_ips': [],
        'auth_trusted_proxies': [],
    })
    monkeypatch.setattr(auth_module, 'is_remote_backup_control_authorized', lambda path, headers: True)

    init_auth(app)
    response = app.test_client().post('/api/remote_backups/probe')

    assert response.status_code == 200
    assert response.get_json() == {'success': True}
