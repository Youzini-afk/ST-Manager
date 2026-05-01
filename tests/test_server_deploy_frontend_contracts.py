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
