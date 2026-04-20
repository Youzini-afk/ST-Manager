import io
import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import beautify as beautify_api


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(beautify_api.bp)
    return app


class FakeBeautifyService:
    def __init__(self):
        self.calls = []
        self.library_root = 'D:/Workspace/MyOwn/ST-Manager/data/library/beautify'

    def list_packages(self):
        self.calls.append(('list_packages',))
        return [{'id': 'pkg_demo', 'name': 'Demo', 'platforms': ['pc']}]

    def get_package(self, package_id):
        self.calls.append(('get_package', package_id))
        if package_id == 'missing':
            return None
        return {'id': package_id, 'name': 'Demo', 'variants': {}, 'wallpapers': {}}

    def import_theme(self, source_path, package_id=None, platform=None, source_name=None):
        self.calls.append(('import_theme', source_path, package_id, platform, source_name))
        return {
            'package': {'id': package_id or 'pkg_demo', 'name': 'Demo'},
            'variant': {'id': 'var_demo', 'platform': platform or 'dual'},
        }

    def import_wallpaper(self, package_id, variant_id, source_path, source_name=None):
        self.calls.append(('import_wallpaper', package_id, variant_id, source_path, source_name))
        return {
            'package': {'id': package_id, 'name': 'Demo'},
            'variant': {'id': variant_id},
            'wallpaper': {'id': 'wp_demo', 'variant_id': variant_id},
        }

    def update_variant(self, package_id, variant_id, platform):
        self.calls.append(('update_variant', package_id, variant_id, platform))
        return {'id': variant_id, 'platform': platform}

    def delete_package(self, package_id):
        self.calls.append(('delete_package', package_id))
        return True

    def get_preview_asset_path(self, subpath):
        self.calls.append(('get_preview_asset_path', subpath))
        if subpath == 'packages/pkg_demo/wallpapers/demo.png':
            return __file__
        return None


def test_list_endpoint_returns_package_summaries(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.get('/api/beautify/list')
    payload = response.get_json()

    assert payload['success'] is True
    assert payload['items'][0]['id'] == 'pkg_demo'
    assert ('list_packages',) in fake_service.calls


def test_detail_endpoint_returns_404_for_missing_package(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.get('/api/beautify/missing')
    payload = response.get_json()

    assert response.status_code == 404
    assert payload['success'] is False


def test_import_theme_endpoint_requires_uploaded_json_file(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.post('/api/beautify/import-theme', data={}, content_type='multipart/form-data')
    payload = response.get_json()

    assert response.status_code == 400
    assert payload['success'] is False
    assert fake_service.calls == []


def test_import_theme_endpoint_forwards_optional_target_package_and_platform(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.post(
        '/api/beautify/import-theme',
        data={
            'file': (io.BytesIO(b'{"name": "Demo", "main_text_color": "#fff"}'), 'demo.json'),
            'package_id': 'pkg_demo',
            'platform': 'pc',
        },
        content_type='multipart/form-data',
    )
    payload = response.get_json()

    assert payload['success'] is True
    assert fake_service.calls[0][0] == 'import_theme'
    assert fake_service.calls[0][2:4] == ('pkg_demo', 'pc')


def test_import_wallpaper_endpoint_requires_package_and_variant(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.post(
        '/api/beautify/import-wallpaper',
        data={'file': (io.BytesIO(b'png'), 'demo.png')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 400


def test_update_variant_endpoint_rejects_invalid_platform(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.post('/api/beautify/update-variant', json={'package_id': 'pkg_demo', 'variant_id': 'var_demo', 'platform': 'tablet'})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload['success'] is False


def test_install_and_apply_endpoints_are_removed(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    install_response = client.post('/api/beautify/install', json={'package_id': 'pkg_demo', 'variant_id': 'var_demo'})
    apply_response = client.post('/api/beautify/apply', json={'package_id': 'pkg_demo', 'variant_id': 'var_demo'})

    assert install_response.status_code in (404, 405)
    assert apply_response.status_code in (404, 405)


def test_delete_package_endpoint_requires_package_id(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    response = client.post('/api/beautify/delete-package', json={})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload['success'] is False


def test_preview_asset_endpoint_blocks_unknown_paths(monkeypatch):
    app = _make_test_app()
    client = app.test_client()
    fake_service = FakeBeautifyService()
    monkeypatch.setattr(beautify_api, 'get_beautify_service', lambda: fake_service)

    blocked = client.get('/api/beautify/preview-asset/../../evil.txt')
    allowed = client.get('/api/beautify/preview-asset/packages/pkg_demo/wallpapers/demo.png')

    assert blocked.status_code == 404
    assert allowed.status_code == 200
