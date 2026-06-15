import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import cards as cards_api
from core.services.card_service import _resolve_safe_skin_path


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(cards_api.bp)
    return app


def test_api_set_skin_cover_accepts_nested_relative_path(monkeypatch):
    calls = []

    def _fake_swap(card_id, skin_filename, save_old):
        calls.append((card_id, skin_filename, save_old))
        return {'success': True}

    monkeypatch.setattr(cards_api, 'swap_skin_to_cover', _fake_swap)

    client = _make_app().test_client()
    res = client.post(
        '/api/set_skin_cover',
        json={'card_id': 'cards/hero.png', 'skin_filename': 'poses/happy.png'},
    )

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    assert calls == [('cards/hero.png', 'poses/happy.png', False)]


def test_api_set_skin_cover_still_accepts_basename(monkeypatch):
    calls = []

    def _fake_swap(card_id, skin_filename, save_old):
        calls.append((card_id, skin_filename, save_old))
        return {'success': True}

    monkeypatch.setattr(cards_api, 'swap_skin_to_cover', _fake_swap)

    client = _make_app().test_client()
    res = client.post(
        '/api/set_skin_cover',
        json={'card_id': 'hero.png', 'skin_filename': 'cover.png'},
    )

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    assert calls == [('hero.png', 'cover.png', False)]


def test_api_set_skin_cover_rejects_traversal_and_absolute_paths(monkeypatch):
    called = []

    def _fake_swap(*args, **kwargs):
        called.append(True)
        return {'success': True}

    monkeypatch.setattr(cards_api, 'swap_skin_to_cover', _fake_swap)

    client = _make_app().test_client()
    bad_names = [
        '../secret.png',
        'poses/../../secret.png',
        '/etc/passwd',
        'C:\\Windows\\secret.png',
        'a/./b.png',
        'a/../b.png',
        '..',
        '.',
    ]
    for bad in bad_names:
        res = client.post(
            '/api/set_skin_cover',
            json={'card_id': 'cards/hero.png', 'skin_filename': bad},
        )
        assert res.status_code == 400, bad
        payload = res.get_json()
        assert payload['success'] is False
        assert '非法' in payload['msg']

    assert not called


def test_resolve_safe_skin_path_accepts_nested_files(tmp_path):
    res_dir = tmp_path / 'hero'
    res_dir.mkdir()

    nested = res_dir / 'poses' / 'happy.png'
    nested.parent.mkdir()
    nested.write_text('x', encoding='utf-8')

    root_file = res_dir / 'cover.png'
    root_file.write_text('x', encoding='utf-8')

    assert _resolve_safe_skin_path(str(res_dir), 'poses/happy.png') == str(nested.resolve())
    assert _resolve_safe_skin_path(str(res_dir), 'cover.png') == str(root_file.resolve())


def test_resolve_safe_skin_path_rejects_escape_and_absolute_paths(tmp_path):
    res_dir = tmp_path / 'hero'
    res_dir.mkdir()

    secret = tmp_path / 'secret.png'
    secret.write_text('x', encoding='utf-8')

    assert _resolve_safe_skin_path(str(res_dir), '../secret.png') is None
    assert _resolve_safe_skin_path(str(res_dir), 'poses/../../secret.png') is None
    assert _resolve_safe_skin_path(str(res_dir), '/tmp/secret.png') is None
    assert _resolve_safe_skin_path(str(res_dir), 'C:\\secret.png') is None
    assert _resolve_safe_skin_path(str(res_dir), '') is None
    assert _resolve_safe_skin_path(str(res_dir), 'a/../b.png') is None


def test_resolve_safe_skin_path_blocks_symlink_escape(tmp_path):
    res_dir = tmp_path / 'hero'
    res_dir.mkdir()

    secret = tmp_path / 'secret.png'
    secret.write_text('x', encoding='utf-8')

    link_dir = tmp_path / 'link_res'
    link_dir.symlink_to(res_dir)

    assert _resolve_safe_skin_path(str(link_dir), '../secret.png') is None
