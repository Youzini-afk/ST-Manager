import logging
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import deployment


def test_parse_env_port_accepts_positive_integer(monkeypatch):
    monkeypatch.setenv('PORT', '7132')

    assert deployment.get_env_port() == 7132


def test_parse_env_port_rejects_invalid_value(monkeypatch, caplog):
    monkeypatch.setenv('PORT', 'abc')

    with caplog.at_level(logging.WARNING):
        assert deployment.get_env_port() is None

    assert 'Ignoring invalid PORT value' in caplog.text


def test_parse_env_port_rejects_out_of_range_value(monkeypatch, caplog):
    monkeypatch.setenv('PORT', '70000')

    with caplog.at_level(logging.WARNING):
        assert deployment.get_env_port() is None

    assert 'Ignoring invalid PORT value' in caplog.text


def test_server_profile_detects_port_and_explicit_flag(monkeypatch):
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.delenv('STM_SERVER_PROFILE', raising=False)
    assert deployment.is_server_profile(False) is False

    monkeypatch.setenv('PORT', '9000')
    assert deployment.is_server_profile(False) is True

    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.setenv('STM_SERVER_PROFILE', '1')
    assert deployment.is_server_profile(False) is True


def test_browser_auto_open_is_disabled_for_server_and_docker(monkeypatch):
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.delenv('STM_SERVER_PROFILE', raising=False)
    monkeypatch.delenv('STM_DISABLE_BROWSER_OPEN', raising=False)

    assert deployment.should_auto_open_browser(False) is True
    assert deployment.should_auto_open_browser(True) is False

    monkeypatch.setenv('PORT', '7000')
    assert deployment.should_auto_open_browser(False) is False

    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.setenv('STM_DISABLE_BROWSER_OPEN', '1')
    assert deployment.should_auto_open_browser(False) is False


def test_security_status_warns_only_for_server_profile_without_auth():
    status = deployment.build_security_status(server_profile=True, auth_enabled=False)

    assert status['server_profile'] is True
    assert status['auth_enabled'] is False
    assert status['public_auth_warning'] is True
    assert 'STM_AUTH_USER' in status['message']

    local_status = deployment.build_security_status(server_profile=False, auth_enabled=False)
    assert local_status['public_auth_warning'] is False


def test_wsgi_exposes_flask_app_and_bootstraps_once(monkeypatch):
    calls = []

    monkeypatch.setenv('STM_SERVER_PROFILE', '1')
    monkeypatch.setattr('app.is_running_in_docker', lambda: True)
    monkeypatch.setattr('app.ensure_startup_config', lambda in_docker: calls.append(('config', in_docker)) or {})
    monkeypatch.setattr('core.init_services', lambda: calls.append(('services', None)))

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr('threading.Thread', ImmediateThread)

    module = importlib.import_module('wsgi')
    module = importlib.reload(module)

    assert module.app.name == 'core'
    assert ('config', True) in calls
    assert ('services', None) in calls
