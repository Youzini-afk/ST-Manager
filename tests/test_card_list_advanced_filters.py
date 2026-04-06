import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api.v1 import cards as cards_api
from core.data import ui_store as ui_store_module


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(cards_api.bp)
    return app


def _write_ui_data(ui_path: Path, payload):
    ui_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _ts(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp()


def _make_card(
    card_id,
    *,
    char_name,
    category='',
    import_time=0.0,
    last_modified=0.0,
    token_count=0,
    tags=None,
    is_favorite=False,
):
    return {
        'id': card_id,
        'category': category,
        'char_name': char_name,
        'filename': card_id,
        'tags': list(tags or []),
        'is_favorite': is_favorite,
        'ui_summary': '',
        'last_modified': last_modified,
        'import_time': import_time,
        'token_count': token_count,
    }


class _FakeCache:
    def __init__(self, cards):
        self.cards = list(cards)
        self.visible_folders = []
        self.category_counts = {}
        self.global_tags = set()
        self.lock = threading.Lock()
        self.initialized = True

    def reload_from_db(self):
        raise AssertionError('reload_from_db should not run in advanced filter tests')


def _install_fake_cache(monkeypatch, cards):
    fake_cache = _FakeCache(cards)
    monkeypatch.setattr(cards_api.ctx, 'cache', fake_cache)
    return fake_cache


def test_list_cards_filters_import_date_range(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    _install_fake_cache(
        monkeypatch,
        [
            _make_card(
                'old.png',
                char_name='Old Card',
                import_time=_ts(2026, 3, 1, 12),
                last_modified=_ts(2026, 3, 1, 12),
            ),
            _make_card(
                'match.png',
                char_name='Match Card',
                import_time=_ts(2026, 3, 15, 9),
                last_modified=_ts(2026, 3, 15, 9),
            ),
            _make_card(
                'late.png',
                char_name='Late Card',
                import_time=_ts(2026, 4, 2, 18),
                last_modified=_ts(2026, 4, 2, 18),
            ),
        ],
    )

    client = _make_test_app().test_client()
    res = client.get('/api/list_cards?page=1&page_size=20&import_date_from=2026-03-10&import_date_to=2026-03-31')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['cards']] == ['match.png']


def test_list_cards_filters_token_range(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    _install_fake_cache(
        monkeypatch,
        [
            _make_card('tiny.png', char_name='Tiny', token_count=800, last_modified=_ts(2026, 4, 1, 8)),
            _make_card('fit.png', char_name='Fit', token_count=3200, last_modified=_ts(2026, 4, 1, 9)),
            _make_card('huge.png', char_name='Huge', token_count=12000, last_modified=_ts(2026, 4, 1, 10)),
        ],
    )

    client = _make_test_app().test_client()
    res = client.get('/api/list_cards?page=1&page_size=20&token_min=2000&token_max=8000')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['cards']] == ['fit.png']


def test_list_cards_filters_modified_date_range(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    _install_fake_cache(
        monkeypatch,
        [
            _make_card(
                'old-edit.png',
                char_name='Old Edit',
                import_time=_ts(2026, 4, 1, 8),
                last_modified=_ts(2026, 4, 2, 8),
                token_count=2000,
            ),
            _make_card(
                'target-edit.png',
                char_name='Target Edit',
                import_time=_ts(2026, 4, 1, 9),
                last_modified=_ts(2026, 4, 5, 8),
                token_count=2400,
            ),
            _make_card(
                'late-edit.png',
                char_name='Late Edit',
                import_time=_ts(2026, 4, 1, 10),
                last_modified=_ts(2026, 4, 9, 8),
                token_count=2800,
            ),
        ],
    )

    client = _make_test_app().test_client()
    res = client.get(
        '/api/list_cards?page=1&page_size=20&modified_date_from=2026-04-04&modified_date_to=2026-04-07'
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['cards']] == ['target-edit.png']


def test_list_cards_full_search_keeps_time_and_token_filters(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    _install_fake_cache(
        monkeypatch,
        [
            _make_card(
                'alpha-new.png',
                char_name='Alpha New',
                import_time=_ts(2026, 4, 4, 8),
                last_modified=_ts(2026, 4, 4, 8),
                token_count=5200,
                tags=['blue'],
                is_favorite=False,
            ),
            _make_card(
                'alpha-old.png',
                char_name='Alpha Old',
                import_time=_ts(2026, 3, 20, 8),
                last_modified=_ts(2026, 3, 20, 8),
                token_count=5200,
                tags=['blue'],
                is_favorite=False,
            ),
        ],
    )

    client = _make_test_app().test_client()
    res = client.get(
        '/api/list_cards?page=1&page_size=20'
        '&search_scope=full'
        '&search=alpha'
        '&import_date_from=2026-04-01'
        '&token_min=4000'
        '&fav_filter=included'
        '&tags=rare'
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['cards']] == ['alpha-new.png']


def test_list_cards_rejects_invalid_advanced_filter_params(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))
    _install_fake_cache(monkeypatch, [])

    client = _make_test_app().test_client()
    res = client.get('/api/list_cards?page=1&page_size=20&token_min=bad-value')

    assert res.status_code == 400
    payload = res.get_json()
    assert payload['success'] is False
    assert 'token_min' in payload['msg']


@pytest.mark.parametrize(
    ('field_name', 'raw_value'),
    [('import_date_from', '2026/04/01'), ('modified_date_to', 'not-a-date')],
)
def test_list_cards_rejects_malformed_advanced_filter_dates(monkeypatch, tmp_path, field_name, raw_value):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))
    _install_fake_cache(monkeypatch, [])

    client = _make_test_app().test_client()
    res = client.get(f'/api/list_cards?page=1&page_size=20&{field_name}={raw_value}')

    assert res.status_code == 400
    payload = res.get_json()
    assert payload['success'] is False
    assert field_name in payload['msg']


def test_list_cards_rejects_token_range_when_min_exceeds_max(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))
    _install_fake_cache(monkeypatch, [])

    client = _make_test_app().test_client()
    res = client.get('/api/list_cards?page=1&page_size=20&token_min=9000&token_max=1000')

    assert res.status_code == 400
    payload = res.get_json()
    assert payload['success'] is False
    assert 'token_min' in payload['msg']
