# ST-Manager Server Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ST-Manager friendly for Docker, server, and Zeabur one-click deployments while preserving local desktop behavior.

**Architecture:** Add a small deployment helper layer for server-profile detection, env parsing, browser-open rules, and public-auth warning status. Extend config bootstrap so `STM_DATA_DIR` and `STM_CONFIG_FILE` redirect mutable state to `/data`, add an unauthenticated `/healthz`, and expose production startup through `wsgi.py` for Gunicorn.

**Tech Stack:** Python 3.10, Flask, pytest, Docker, Gunicorn, Zeabur template YAML.

---

## File Structure

- Modify `core/config.py`: env-aware `CONFIG_FILE`, `DATA_DIR`, generated defaults, runtime dir resolution.
- Create `core/deployment.py`: server profile helpers, env port parsing, browser auto-open decisions, public auth warning payload/logging.
- Modify `app.py`: use deployment helpers for env `HOST`/`PORT`, browser-open rules, and startup warning.
- Create `wsgi.py`: production entrypoint that prepares config/data, starts background services once, and exposes `app`.
- Modify `core/__init__.py`: add `/healthz`.
- Modify `core/auth.py`: exclude `/healthz` from auth middleware.
- Modify `core/api/v1/system.py`: attach security warning status to `/api/status`.
- Modify `static/js/components/layout.js`: expose warning state to template.
- Modify `templates/layout.html`: render the warning banner.
- Modify `requirements.txt`: add `gunicorn`.
- Modify `Dockerfile`: server-profile env vars, `/data` volume, Gunicorn CMD, healthcheck.
- Modify `docker-compose.yaml`: single service, `/data` mount, auth env examples.
- Create `zeabur.yaml`: one-click deployment metadata.
- Modify `README.md` and `docs/CONFIG.md`: document server and Zeabur deployment.
- Modify `tests/test_config_bootstrap.py`: env/config startup tests.
- Create `tests/test_deployment_runtime.py`: helper and WSGI tests.
- Create `tests/test_health_and_security_status.py`: `/healthz`, auth bypass, `/api/status` security payload.
- Create or modify a frontend contract test for the UI warning banner.

---

### Task 1: Deployment Helper Layer

**Files:**
- Create: `core/deployment.py`
- Test: `tests/test_deployment_runtime.py`

- [ ] **Step 1: Write failing helper tests**

Add these tests to `tests/test_deployment_runtime.py`:

```python
import logging

from core import deployment


def test_parse_env_port_accepts_positive_integer(monkeypatch):
    monkeypatch.setenv('PORT', '7132')

    assert deployment.get_env_port() == 7132


def test_parse_env_port_rejects_invalid_value(monkeypatch, caplog):
    monkeypatch.setenv('PORT', 'abc')

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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pytest tests/test_deployment_runtime.py -v
```

Expected: FAIL because `core.deployment` does not exist.

- [ ] **Step 3: Implement deployment helpers**

Create `core/deployment.py`:

```python
import logging
import os


logger = logging.getLogger(__name__)

TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def env_flag(name: str) -> bool:
    return os.environ.get(name, '').strip().lower() in TRUE_VALUES


def get_env_host():
    value = os.environ.get('HOST', '').strip()
    return value or None


def get_env_port():
    raw = os.environ.get('PORT', '').strip()
    if not raw:
        return None
    try:
        port = int(raw)
    except ValueError:
        logger.warning("Ignoring invalid PORT value: %s", raw)
        return None
    if port <= 0 or port > 65535:
        logger.warning("Ignoring invalid PORT value: %s", raw)
        return None
    return port


def is_server_profile(in_docker: bool = False) -> bool:
    if env_flag('STM_SERVER_PROFILE'):
        return True
    if os.environ.get('PORT', '').strip():
        return True
    return bool(in_docker)


def should_auto_open_browser(in_docker: bool = False) -> bool:
    if env_flag('STM_DISABLE_BROWSER_OPEN'):
        return False
    return not is_server_profile(in_docker)


def build_security_status(*, server_profile: bool, auth_enabled: bool) -> dict:
    public_auth_warning = bool(server_profile and not auth_enabled)
    message = ''
    if public_auth_warning:
        message = (
            '公网部署未启用登录保护。请设置 STM_AUTH_USER / STM_AUTH_PASS '
            '或在设置中配置外网访问账号密码。'
        )
    return {
        'server_profile': bool(server_profile),
        'auth_enabled': bool(auth_enabled),
        'public_auth_warning': public_auth_warning,
        'message': message,
    }


def log_public_auth_warning_if_needed(*, server_profile: bool, auth_enabled: bool):
    if not server_profile or auth_enabled:
        return
    logger.warning(
        '\n'
        '============================================================\n'
        'ST-Manager is running in server profile without login auth.\n'
        'Set STM_AUTH_USER and STM_AUTH_PASS before exposing it publicly.\n'
        '============================================================'
    )
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
pytest tests/test_deployment_runtime.py -v
```

Expected: PASS.

---

### Task 2: Env-Aware Config and Runtime Directories

**Files:**
- Modify: `core/config.py`
- Modify: `tests/test_config_bootstrap.py`

- [ ] **Step 1: Write failing config tests**

Add tests to `tests/test_config_bootstrap.py`:

```python
import importlib


def test_config_module_uses_env_config_file_and_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / 'persisted'
    config_file = data_dir / 'config.json'
    monkeypatch.setenv('STM_DATA_DIR', str(data_dir))
    monkeypatch.setenv('STM_CONFIG_FILE', str(config_file))

    reloaded = importlib.reload(config_module)
    try:
        assert reloaded.DATA_DIR == str(data_dir)
        assert reloaded.CONFIG_FILE == str(config_file)
        assert reloaded.SYSTEM_DIR == str(data_dir / 'system')
        assert reloaded.TEMP_DIR == str(data_dir / 'temp')
    finally:
        monkeypatch.delenv('STM_DATA_DIR', raising=False)
        monkeypatch.delenv('STM_CONFIG_FILE', raising=False)
        importlib.reload(config_module)


def test_build_default_config_is_data_root_aware(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data-root'
    monkeypatch.setenv('STM_DATA_DIR', str(data_dir))

    reloaded = importlib.reload(config_module)
    try:
        cfg = reloaded.build_default_config()
        assert cfg['cards_dir'] == str(data_dir / 'library' / 'characters')
        assert cfg['world_info_dir'] == str(data_dir / 'library' / 'lorebooks')
        assert cfg['quick_replies_dir'] == str(data_dir / 'library' / 'extensions' / 'quick-replies')
        assert cfg['resources_dir'] == str(data_dir / 'assets' / 'card_assets')
    finally:
        monkeypatch.delenv('STM_DATA_DIR', raising=False)
        importlib.reload(config_module)
```

- [ ] **Step 2: Run targeted config tests and confirm failure**

Run:

```bash
pytest tests/test_config_bootstrap.py::test_config_module_uses_env_config_file_and_data_dir tests/test_config_bootstrap.py::test_build_default_config_is_data_root_aware -v
```

Expected: FAIL because env-aware config paths are not implemented.

- [ ] **Step 3: Implement env-aware config paths**

In `core/config.py`, add path helpers near the top and use them for `CONFIG_FILE` and `DATA_DIR`:

```python
def _env_path(name):
    raw = os.environ.get(name, '').strip()
    return os.path.abspath(raw) if raw else None


def _resolve_config_file():
    return _env_path('STM_CONFIG_FILE') or os.path.join(BASE_DIR, 'config.json')


def _resolve_data_dir():
    return _env_path('STM_DATA_DIR') or os.path.join(BASE_DIR, 'data')


CONFIG_FILE = _resolve_config_file()
DATA_DIR = _resolve_data_dir()
```

Add runtime default helpers:

```python
LEGACY_RUNTIME_DIR_DEFAULTS = {
    'cards_dir': 'data/library/characters',
    'world_info_dir': 'data/library/lorebooks',
    'chats_dir': 'data/library/chats',
    'presets_dir': 'data/library/presets',
    'regex_dir': 'data/library/extensions/regex',
    'scripts_dir': 'data/library/extensions/tavern_helper',
    'quick_replies_dir': 'data/library/extensions/quick-replies',
    'beautify_dir': 'data/library/beautify',
    'resources_dir': 'data/assets/card_assets',
}


def _data_root_runtime_defaults(data_dir):
    root = os.path.abspath(data_dir)
    return {
        'cards_dir': os.path.join(root, 'library', 'characters'),
        'world_info_dir': os.path.join(root, 'library', 'lorebooks'),
        'chats_dir': os.path.join(root, 'library', 'chats'),
        'presets_dir': os.path.join(root, 'library', 'presets'),
        'regex_dir': os.path.join(root, 'library', 'extensions', 'regex'),
        'scripts_dir': os.path.join(root, 'library', 'extensions', 'tavern_helper'),
        'quick_replies_dir': os.path.join(root, 'library', 'extensions', 'quick-replies'),
        'beautify_dir': os.path.join(root, 'library', 'beautify'),
        'resources_dir': os.path.join(root, 'assets', 'card_assets'),
    }


def _is_external_data_dir_active():
    return bool(os.environ.get('STM_DATA_DIR', '').strip())


def get_runtime_dir_defaults():
    if _is_external_data_dir_active():
        return _data_root_runtime_defaults(DATA_DIR)
    return dict(LEGACY_RUNTIME_DIR_DEFAULTS)
```

Change `build_default_config` to merge data-root defaults before overrides:

```python
def build_default_config(default_overrides=None):
    cfg = {**DEFAULT_CONFIG, **get_runtime_dir_defaults()}
    cfg.update(default_overrides or {})
    return normalize_config(cfg)
```

Set `RUNTIME_DIR_DEFAULTS = get_runtime_dir_defaults()` and keep `ensure_runtime_dirs` using it.

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config_bootstrap.py -v
```

Expected: PASS.

---

### Task 3: Startup Env Precedence and Browser Rules

**Files:**
- Modify: `app.py`
- Modify: `tests/test_config_bootstrap.py`

- [ ] **Step 1: Write failing startup tests**

Add tests to `tests/test_config_bootstrap.py`:

```python
def test_resolve_server_settings_uses_env_between_cli_and_config(monkeypatch):
    monkeypatch.setenv('HOST', '0.0.0.0')
    monkeypatch.setenv('PORT', '8124')
    monkeypatch.delenv('FLASK_DEBUG', raising=False)
    cfg = {'host': '127.0.0.1', 'port': 5000}
    cli_args = Namespace(debug=False, host=None, port=None)

    host, port, debug = app_module.resolve_server_settings(cfg, cli_args)

    assert host == '0.0.0.0'
    assert port == 8124
    assert debug is False


def test_resolve_server_settings_cli_still_wins_over_env(monkeypatch):
    monkeypatch.setenv('HOST', '0.0.0.0')
    monkeypatch.setenv('PORT', '8124')
    cfg = {'host': '127.0.0.1', 'port': 5000}
    cli_args = Namespace(debug=False, host='127.0.0.2', port=9001)

    host, port, debug = app_module.resolve_server_settings(cfg, cli_args)

    assert (host, port, debug) == ('127.0.0.2', 9001, False)


def test_resolve_server_settings_ignores_invalid_env_port(monkeypatch):
    monkeypatch.setenv('PORT', 'nope')
    cfg = {'host': '127.0.0.1', 'port': 5000}
    cli_args = Namespace(debug=False, host=None, port=None)

    host, port, debug = app_module.resolve_server_settings(cfg, cli_args)

    assert port == 5000
```

- [ ] **Step 2: Run startup tests and confirm failure**

Run:

```bash
pytest tests/test_config_bootstrap.py::test_resolve_server_settings_uses_env_between_cli_and_config tests/test_config_bootstrap.py::test_resolve_server_settings_cli_still_wins_over_env tests/test_config_bootstrap.py::test_resolve_server_settings_ignores_invalid_env_port -v
```

Expected: FAIL because env host/port are not used.

- [ ] **Step 3: Implement startup env precedence and warnings**

In `app.py`, import helpers:

```python
from core.deployment import (
    get_env_host,
    get_env_port,
    is_server_profile,
    log_public_auth_warning_if_needed,
    should_auto_open_browser,
)
from core.auth import is_auth_enabled
```

Update `resolve_server_settings`:

```python
def resolve_server_settings(cfg, cli_args):
    env_host = get_env_host()
    env_port = get_env_port()
    host = cli_args.host if cli_args.host is not None else (env_host or cfg.get('host', '127.0.0.1'))
    port = cli_args.port if cli_args.port is not None else (env_port if env_port is not None else cfg.get('port', 5000))
    debug = cli_args.debug or os.environ.get('FLASK_DEBUG') == '1'
    return host, port, debug
```

In `__main__`, after resolving settings, add:

```python
    server_profile = is_server_profile(in_docker)
    log_public_auth_warning_if_needed(
        server_profile=server_profile,
        auth_enabled=is_auth_enabled(),
    )
```

Change browser-open condition to:

```python
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and should_auto_open_browser(in_docker):
```

- [ ] **Step 4: Run config/startup tests**

Run:

```bash
pytest tests/test_config_bootstrap.py tests/test_deployment_runtime.py -v
```

Expected: PASS.

---

### Task 4: Health Endpoint and Security Status

**Files:**
- Modify: `core/__init__.py`
- Modify: `core/auth.py`
- Modify: `core/api/v1/system.py`
- Create: `tests/test_health_and_security_status.py`

- [ ] **Step 1: Write failing health/security tests**

Create `tests/test_health_and_security_status.py`:

```python
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pytest tests/test_health_and_security_status.py -v
```

Expected: FAIL because `/healthz` and security status are not implemented.

- [ ] **Step 3: Add health endpoint and auth exclusion**

In `core/__init__.py`, after creating the Flask app:

```python
    @app.route('/healthz')
    def healthz():
        return {'ok': True, 'service': 'st-manager'}
```

In `core/auth.py`, add `'/healthz'` to `excluded_paths`.

- [ ] **Step 4: Attach security status to `/api/status`**

In `core/api/v1/system.py`, import:

```python
from core.auth import is_auth_enabled
from core.deployment import build_security_status, is_server_profile
```

Change `api_status`:

```python
@bp.route('/api/status')
def api_status():
    payload = dict(ctx.init_status)
    payload['security'] = build_security_status(
        server_profile=is_server_profile(False),
        auth_enabled=is_auth_enabled(),
    )
    return jsonify(payload)
```

- [ ] **Step 5: Run health/security tests**

Run:

```bash
pytest tests/test_health_and_security_status.py -v
```

Expected: PASS.

---

### Task 5: UI Warning Banner

**Files:**
- Modify: `static/js/components/layout.js`
- Modify: `templates/layout.html`
- Test: `tests/test_settings_frontend_contracts.py` or new `tests/test_server_deploy_frontend_contracts.py`

- [ ] **Step 1: Write failing frontend contract test**

Create `tests/test_server_deploy_frontend_contracts.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_layout_template_contains_public_auth_warning_banner():
    source = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')

    assert 'showPublicAuthWarning' in source
    assert '公网部署未启用登录保护' in source
    assert 'STM_AUTH_USER / STM_AUTH_PASS' in source


def test_layout_component_exposes_public_auth_warning_state():
    source = (ROOT / 'static' / 'js' / 'components' / 'layout.js').read_text(encoding='utf-8')

    assert 'showPublicAuthWarning' in source
    assert 'public_auth_warning' in source
```

- [ ] **Step 2: Run frontend contract test and confirm failure**

Run:

```bash
pytest tests/test_server_deploy_frontend_contracts.py -v
```

Expected: FAIL because the banner does not exist.

- [ ] **Step 3: Add layout component getters**

In `static/js/components/layout.js`, near other getters:

```javascript
    get securityStatus() {
      return this.serverStatus?.security || {};
    },
    get showPublicAuthWarning() {
      return !!this.securityStatus.public_auth_warning;
    },
```

- [ ] **Step 4: Add template banner**

In `templates/layout.html`, immediately after `<body ...>`:

```html
    <div
      x-show="showPublicAuthWarning"
      x-cloak
      class="fixed top-0 left-0 right-0 z-[10000] bg-red-700 text-white px-4 py-2 text-sm font-semibold text-center shadow-lg"
    >
      公网部署未启用登录保护。请设置 STM_AUTH_USER / STM_AUTH_PASS 或在设置中配置外网访问账号密码。
    </div>
```

- [ ] **Step 5: Run frontend contract test**

Run:

```bash
pytest tests/test_server_deploy_frontend_contracts.py -v
```

Expected: PASS.

---

### Task 6: Production WSGI Entrypoint

**Files:**
- Create: `wsgi.py`
- Modify: `tests/test_deployment_runtime.py`

- [ ] **Step 1: Write failing WSGI test**

Add to `tests/test_deployment_runtime.py`:

```python
import importlib
import types


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
```

- [ ] **Step 2: Run WSGI test and confirm failure**

Run:

```bash
pytest tests/test_deployment_runtime.py::test_wsgi_exposes_flask_app_and_bootstraps_once -v
```

Expected: FAIL because `wsgi.py` does not exist.

- [ ] **Step 3: Create WSGI entrypoint**

Create `wsgi.py`:

```python
import threading

from app import ensure_startup_config, is_running_in_docker
from core import create_app, init_services
from core.auth import is_auth_enabled
from core.deployment import is_server_profile, log_public_auth_warning_if_needed


in_docker = is_running_in_docker()
ensure_startup_config(in_docker)
log_public_auth_warning_if_needed(
    server_profile=is_server_profile(in_docker),
    auth_enabled=is_auth_enabled(),
)
threading.Thread(target=init_services, daemon=True).start()

app = create_app()
```

- [ ] **Step 4: Run WSGI test**

Run:

```bash
pytest tests/test_deployment_runtime.py::test_wsgi_exposes_flask_app_and_bootstraps_once -v
```

Expected: PASS.

---

### Task 7: Docker, Compose, Zeabur, and Docs

**Files:**
- Modify: `requirements.txt`
- Modify: `Dockerfile`
- Modify: `docker-compose.yaml`
- Create: `zeabur.yaml`
- Modify: `README.md`
- Modify: `docs/CONFIG.md`

- [ ] **Step 1: Write docs/config contract tests**

Add to `tests/test_server_deploy_frontend_contracts.py`:

```python
def test_dockerfile_uses_server_profile_and_healthcheck():
    source = (ROOT / 'Dockerfile').read_text(encoding='utf-8')

    assert 'STM_SERVER_PROFILE=1' in source
    assert 'STM_DATA_DIR=/data' in source
    assert 'STM_CONFIG_FILE=/data/config.json' in source
    assert 'HEALTHCHECK' in source
    assert '/healthz' in source
    assert 'gunicorn' in source
    assert 'wsgi:app' in source


def test_zeabur_template_documents_volume_env_and_healthcheck():
    source = (ROOT / 'zeabur.yaml').read_text(encoding='utf-8')

    assert '/data' in source
    assert 'STM_AUTH_USER' in source
    assert 'STM_AUTH_PASS' in source
    assert '/healthz' in source


def test_readme_mentions_zeabur_and_server_envs():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    config_doc = (ROOT / 'docs' / 'CONFIG.md').read_text(encoding='utf-8')
    combined = readme + '\n' + config_doc

    assert 'Zeabur' in combined
    assert 'STM_DATA_DIR' in combined
    assert 'STM_CONFIG_FILE' in combined
    assert 'PORT' in combined
    assert '/healthz' in combined
```

- [ ] **Step 2: Run contract tests and confirm failure**

Run:

```bash
pytest tests/test_server_deploy_frontend_contracts.py -v
```

Expected: FAIL until files/docs are updated.

- [ ] **Step 3: Add Gunicorn dependency**

Append to `requirements.txt`:

```text
gunicorn>=21.2.0
```

- [ ] **Step 4: Update Dockerfile**

Set server env, `/data`, healthcheck, and Gunicorn command:

```dockerfile
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    STM_SERVER_PROFILE=1 \
    STM_DATA_DIR=/data \
    STM_CONFIG_FILE=/data/config.json \
    STM_DISABLE_BROWSER_OPEN=1

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '5000'), timeout=3).read()" || exit 1

CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-1} --threads ${WEB_THREADS:-8} --timeout ${WEB_TIMEOUT:-120}"]
```

- [ ] **Step 5: Simplify docker-compose.yaml**

Replace the two-service compose file with one service:

```yaml
services:
  st-manager:
    build: .
    container_name: st-manager
    ports:
      - "5000:5000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      STM_SERVER_PROFILE: "1"
      STM_DATA_DIR: /data
      STM_CONFIG_FILE: /data/config.json
      STM_DISABLE_BROWSER_OPEN: "1"
      HOST: 0.0.0.0
      PORT: "5000"
      # STM_AUTH_USER: admin
      # STM_AUTH_PASS: change-me
      # STM_SECRET_KEY: replace-with-a-long-random-secret
    volumes:
      - ./data:/data
    restart: unless-stopped
```

- [ ] **Step 6: Add Zeabur template**

Create `zeabur.yaml`:

```yaml
apiVersion: zeabur.com/v1
kind: Template
metadata:
  name: ST-Manager
spec:
  description: SillyTavern resource manager and remote backup dashboard.
  services:
    - name: st-manager
      template: PREBUILT
      spec:
        source:
          image: ghcr.io/youzini-afk/st-manager:latest
        ports:
          - id: web
            port: 5000
            type: HTTP
        volumes:
          - id: data
            dir: /data
        env:
          STM_SERVER_PROFILE:
            default: "1"
          STM_DATA_DIR:
            default: /data
          STM_CONFIG_FILE:
            default: /data/config.json
          STM_DISABLE_BROWSER_OPEN:
            default: "1"
          STM_AUTH_USER:
            default: ""
          STM_AUTH_PASS:
            default: ""
          STM_SECRET_KEY:
            default: ""
        healthcheck:
          path: /healthz
```

If Zeabur rejects the exact template schema later, keep the documented env/volume/health fields and adjust the schema to Zeabur's current validator before publishing.

- [ ] **Step 7: Update docs**

In `README.md`, update Docker deployment and add a Zeabur section covering `PORT`, `/data`, `/healthz`, auth env vars, and remote ST URL reachability.

In `docs/CONFIG.md`, add a server environment variables section:

```markdown
| 环境变量 | 说明 |
| --- | --- |
| `HOST` | 服务监听地址，低于 CLI、高于 `config.json` |
| `PORT` | 服务监听端口，适配 Zeabur 等平台 |
| `STM_SERVER_PROFILE` | 启用服务端运行提示和默认行为 |
| `STM_DATA_DIR` | 运行数据根目录，推荐 `/data` |
| `STM_CONFIG_FILE` | 配置文件路径，推荐 `/data/config.json` |
| `STM_DISABLE_BROWSER_OPEN` | 禁止启动时自动打开浏览器 |
```

- [ ] **Step 8: Run docs/contracts**

Run:

```bash
pytest tests/test_server_deploy_frontend_contracts.py -v
```

Expected: PASS.

---

### Task 8: Full Verification and Commits

**Files:**
- All files changed in previous tasks.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest tests/test_config_bootstrap.py tests/test_deployment_runtime.py tests/test_health_and_security_status.py tests/test_server_deploy_frontend_contracts.py -v
```

Expected: PASS.

- [ ] **Step 2: Run related existing auth/ST tests**

Run:

```bash
pytest tests/test_st_auth_flow.py tests/test_remote_st_bridge_client.py tests/test_remote_backup_service.py tests/test_remote_backups_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Check git diff**

Run:

```bash
git diff --stat
git diff --check
```

Expected: no whitespace errors, changes limited to deployment/config/docs/tests/UI warning files.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add app.py core/config.py core/deployment.py core/__init__.py core/auth.py core/api/v1/system.py static/js/components/layout.js templates/layout.html requirements.txt Dockerfile docker-compose.yaml zeabur.yaml README.md docs/CONFIG.md tests/test_config_bootstrap.py tests/test_deployment_runtime.py tests/test_health_and_security_status.py tests/test_server_deploy_frontend_contracts.py wsgi.py
git commit -m "feat: improve server and Zeabur deployment"
```

Expected: one feature commit after the spec/plan commits.

- [ ] **Step 5: Push when requested**

If the user wants the branch pushed, run:

```bash
git push origin main
```

Expected: `main` updates on the configured ST-Manager remote.
