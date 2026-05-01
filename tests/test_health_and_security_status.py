import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import create_app
from core.context import ctx


def test_healthz_is_public_even_when_auth_enabled(monkeypatch):
    monkeypatch.setenv('STM_AUTH_USER', 'admin')
    monkeypatch.setenv('STM_AUTH_PASS', 'secret')

    app = create_app()
    client = app.test_client()
    response = client.get('/healthz', environ_base={'REMOTE_ADDR': '203.0.113.10'})

    assert response.status_code == 200
    assert response.get_json() == {'ok': True, 'service': 'st-manager'}


def test_api_status_includes_public_auth_warning(monkeypatch):
    monkeypatch.setenv('STM_SERVER_PROFILE', '1')
    monkeypatch.delenv('STM_AUTH_USER', raising=False)
    monkeypatch.delenv('STM_AUTH_PASS', raising=False)
    ctx.set_status(status='ready', message='ok')

    app = create_app()
    client = app.test_client()
    response = client.get('/api/status', environ_base={'REMOTE_ADDR': '127.0.0.1'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'ready'
    assert payload['security']['server_profile'] is True
    assert payload['security']['auth_enabled'] is False
    assert payload['security']['public_auth_warning'] is True
    assert 'STM_AUTH_USER' in payload['security']['message']


def test_api_status_reports_auth_enabled_without_warning(monkeypatch):
    monkeypatch.setenv('STM_SERVER_PROFILE', '1')
    monkeypatch.setenv('STM_AUTH_USER', 'admin')
    monkeypatch.setenv('STM_AUTH_PASS', 'secret')
    ctx.set_status(status='ready', message='ok')

    app = create_app()
    client = app.test_client()
    response = client.get('/api/status', environ_base={'REMOTE_ADDR': '127.0.0.1'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['security']['auth_enabled'] is True
    assert payload['security']['public_auth_warning'] is False
