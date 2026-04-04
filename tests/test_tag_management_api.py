import json
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


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


def test_tag_taxonomy_normalization_preserves_only_valid_category_tag_order_entries():
    normalized = ui_store_module._normalize_tag_taxonomy(
        {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
                'Mood': {'color': '#abcdef', 'opacity': 35},
            },
            'tag_to_category': {
                'calm': 'Mood',
                'tense': 'Mood',
                'misc': 'General',
            },
            'category_tag_order': {
                'Mood': [' tense ', '', 'calm', 'unknown', 'tense', None],
                'Missing': ['ghost'],
                'General': 'misc',
            },
        }
    )

    assert normalized['category_tag_order'] == {
        'Mood': ['tense', 'calm'],
    }


def test_tag_taxonomy_normalization_drops_wrong_bucket_category_tag_order_entries():
    normalized = ui_store_module._normalize_tag_taxonomy(
        {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
                'Mood': {'color': '#abcdef', 'opacity': 35},
            },
            'tag_to_category': {
                'calm': 'Mood',
                'misc': 'General',
            },
            'category_tag_order': {
                'General': ['calm'],
                'Mood': ['misc'],
            },
        }
    )

    assert normalized['category_tag_order'] == {}


def test_tag_management_prefs_normalization_dedupes_blacklist_and_normalizes_lock_flag():
    normalized = ui_store_module._normalize_tag_management_prefs(
        {
            'lock_tag_library': 'yes',
            'tag_blacklist': [' spoiler ', 'spoiler', '', ' nsfw ', None, 'nsfw'],
            'updated_at': '17',
        }
    )

    assert normalized == {
        'lock_tag_library': True,
        'tag_blacklist': ['spoiler', 'nsfw'],
        'updated_at': 17,
    }


def test_api_tag_taxonomy_round_trips_category_tag_order(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    client = _make_test_app().test_client()
    payload = {
        'taxonomy': {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
                'Mood': {'color': '#abcdef', 'opacity': 35},
            },
            'category_order': ['Mood', 'General'],
            'tag_to_category': {
                'calm': 'Mood',
                'tense': 'Mood',
                'misc': 'General',
            },
            'category_tag_order': {
                'Mood': ['tense', 'calm', 'unknown'],
                'General': ['misc'],
            },
        }
    }

    post_res = client.post('/api/tag_taxonomy', json=payload)

    assert post_res.status_code == 200
    post_body = post_res.get_json()
    assert post_body['success'] is True
    assert post_body['taxonomy']['category_tag_order'] == {
        'Mood': ['tense', 'calm'],
        'General': ['misc'],
    }

    get_res = client.get('/api/tag_taxonomy')

    assert get_res.status_code == 200
    get_body = get_res.get_json()
    assert get_body['success'] is True
    assert get_body['taxonomy']['category_tag_order'] == {
        'Mood': ['tense', 'calm'],
        'General': ['misc'],
    }


def test_api_tag_taxonomy_cleanup_migrates_category_tag_order_on_category_rename_and_delete(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    client = _make_test_app().test_client()

    rename_payload = {
        'taxonomy': {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
                'Emotion': {'color': '#abcdef', 'opacity': 35},
            },
            'category_order': ['General', 'Emotion'],
            'tag_to_category': {
                'calm': 'Emotion',
                'tense': 'Emotion',
                'misc': 'General',
            },
            'category_tag_order': {
                'Mood': ['tense', 'calm'],
                'General': ['misc'],
            },
        }
    }

    rename_res = client.post('/api/tag_taxonomy', json=rename_payload)

    assert rename_res.status_code == 200
    rename_body = rename_res.get_json()
    assert rename_body['success'] is True
    assert rename_body['taxonomy']['category_tag_order'] == {
        'General': ['misc'],
    }

    delete_payload = {
        'taxonomy': {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
            },
            'category_order': ['General'],
            'tag_to_category': {
                'calm': 'General',
                'tense': 'General',
                'misc': 'General',
            },
            'category_tag_order': {
                'Emotion': ['tense', 'calm'],
                'General': ['misc'],
            },
        }
    }

    delete_res = client.post('/api/tag_taxonomy', json=delete_payload)

    assert delete_res.status_code == 200
    delete_body = delete_res.get_json()
    assert delete_body['success'] is True
    assert delete_body['taxonomy']['category_tag_order'] == {
        'General': ['misc'],
    }


def test_api_tag_taxonomy_rejects_oversized_category_tag_order(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    client = _make_test_app().test_client()
    payload = {
        'taxonomy': {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
            },
            'tag_to_category': {
                'tag-0': 'General',
            },
            'category_tag_order': {
                'General': ['tag-0'] * 20001,
            },
        }
    }

    res = client.post('/api/tag_taxonomy', json=payload)

    assert res.status_code == 400
    assert res.get_json() == {
        'success': False,
        'msg': '分类内标签排序数量过多',
    }


def test_api_tag_management_prefs_round_trips_blacklist_and_lock_flag(monkeypatch, tmp_path):
    ui_path = tmp_path / 'ui_data.json'
    _write_ui_data(ui_path, {})
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    client = _make_test_app().test_client()
    payload = {
        'tag_management_prefs': {
            'lock_tag_library': 1,
            'tag_blacklist': [' spoiler ', 'spoiler', 'nsfw', '', 'nsfw'],
        }
    }

    post_res = client.post('/api/tag_management_prefs', json=payload)

    assert post_res.status_code == 200
    post_body = post_res.get_json()
    assert post_body['success'] is True
    assert post_body['tag_management_prefs']['lock_tag_library'] is True
    assert post_body['tag_management_prefs']['tag_blacklist'] == ['spoiler', 'nsfw']

    get_res = client.get('/api/tag_management_prefs')

    assert get_res.status_code == 200
    get_body = get_res.get_json()
    assert get_body['success'] is True
    assert get_body['tag_management_prefs']['lock_tag_library'] is True
    assert get_body['tag_management_prefs']['tag_blacklist'] == ['spoiler', 'nsfw']


def test_build_tag_groups_applies_category_tag_order_within_each_group():
    groups = cards_api._build_tag_groups(
        ['zeta', 'alpha', 'misc', 'beta'],
        {
            'default_category': 'General',
            'categories': {
                'General': {'color': '#123456', 'opacity': 20},
                'Mood': {'color': '#abcdef', 'opacity': 35},
            },
            'category_order': ['Mood', 'General'],
            'tag_to_category': {
                'alpha': 'Mood',
                'beta': 'Mood',
                'zeta': 'Mood',
                'misc': 'General',
            },
            'category_tag_order': {
                'Mood': ['beta', 'alpha'],
                'General': ['misc'],
            },
        },
    )

    assert groups == [
        {
            'category': 'Mood',
            'color': '#abcdef',
            'opacity': 35,
            'tags': ['beta', 'alpha', 'zeta'],
        },
        {
            'category': 'General',
            'color': '#123456',
            'opacity': 20,
            'tags': ['misc'],
        },
    ]


def test_api_batch_tags_skips_unknown_and_blacklisted_tags_with_structured_feedback(monkeypatch):
    client = _make_test_app().test_client()
    card_id = 'folder/demo.json'
    card_info = {
        'data': {
            'tags': ['keep'],
        },
        'tags': ['keep'],
    }
    writes = {}

    class _FakeCursor:
        def __init__(self):
            self.executed = []

        def execute(self, sql, params=()):
            self.executed.append((sql, params))

    class _FakeConn:
        def __init__(self):
            self.cursor_obj = _FakeCursor()
            self.committed = 0

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed += 1

    fake_conn = _FakeConn()
    fake_cache = SimpleNamespace(
        update_tags_update=lambda cid, tags: writes.setdefault('cache_updates', []).append((cid, list(tags))),
    )

    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *args, **kwargs: None)
    monkeypatch.setattr(cards_api, 'get_db', lambda: fake_conn)
    monkeypatch.setattr(cards_api, 'extract_card_info', lambda path: card_info)
    monkeypatch.setattr(cards_api, 'write_card_metadata', lambda path, info: writes.setdefault('metadata', []).append(info['data']['tags']))
    monkeypatch.setattr(cards_api, 'load_ui_data', lambda: {
        '_tag_management_prefs_v1': {
            'lock_tag_library': True,
            'tag_blacklist': ['blocked-tag'],
        },
        '_tag_taxonomy_v1': {
            'default_category': 'General',
            'categories': {'General': {'color': '#123456', 'opacity': 30}},
            'tag_to_category': {
                'allowed-tag': 'General',
                'keep': 'General',
            },
        },
    })
    monkeypatch.setattr(cards_api, 'save_ui_data', lambda payload: writes.setdefault('saved_ui', payload))
    monkeypatch.setattr(cards_api, 'ctx', SimpleNamespace(cache=fake_cache), raising=False)

    response = client.post(
        '/api/batch_tags',
        json={
            'card_ids': [card_id],
            'add': ['allowed-tag', 'unknown-tag', 'blocked-tag'],
            'remove': [],
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'updated': 1,
        'added_count': 1,
        'skipped_unknown': ['unknown-tag'],
        'skipped_blacklist': ['blocked-tag'],
        'tag_merge': {
            'cards': 0,
            'replacements': [],
        },
    }
    assert card_info['data']['tags'] == ['keep', 'allowed-tag']
    assert fake_conn.cursor_obj.executed == [
        ('UPDATE card_metadata SET tags = ? WHERE id = ?', (json.dumps(['keep', 'allowed-tag']), card_id)),
    ]
    assert fake_conn.committed == 1
