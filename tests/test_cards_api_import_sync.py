import json
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import cards as cards_api


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(cards_api.bp)
    return app


def test_import_from_url_enqueues_card_and_world_sync_jobs(monkeypatch, tmp_path):
    cards_dir = tmp_path / 'cards'
    temp_dir = tmp_path / 'temp'
    cards_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    downloaded_path = temp_dir / 'temp_dl_1_Hero.png'

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=8192):
            del chunk_size
            yield b'fake-card'

    sync_calls = []

    monkeypatch.setattr(cards_api, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(cards_api, 'TEMP_DIR', str(temp_dir))
    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cards_api, 'requests', type('Requests', (), {'get': staticmethod(lambda *_args, **_kwargs: _FakeResponse())})())
    monkeypatch.setattr(cards_api, 'extract_card_info', lambda _path: {
        'data': {
            'name': 'Hero',
            'tags': ['blue'],
            'description': '',
            'first_mes': '',
            'mes_example': '',
            'alternate_greetings': [],
            'creator_notes': '',
            'personality': '',
            'scenario': '',
            'system_prompt': '',
            'post_history_instructions': '',
            'character_version': '',
            'character_book': {'name': 'Book', 'entries': {}},
            'extensions': {},
            'creator': '',
        }
    })
    monkeypatch.setattr(cards_api, 'sanitize_filename', lambda value: value)
    monkeypatch.setattr(cards_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(cards_api, 'save_ui_data', lambda _payload: None)
    monkeypatch.setattr(cards_api, 'ensure_import_time', lambda *_args, **_kwargs: (False, 123.0))
    monkeypatch.setattr(cards_api, 'get_file_hash_and_size', lambda _path: ('hash', 8))
    monkeypatch.setattr(cards_api, 'calculate_token_count', lambda _data: 0)
    monkeypatch.setattr(cards_api, 'schedule_reload', lambda **_kwargs: None)
    monkeypatch.setattr(cards_api, 'auto_run_rules_on_card', lambda _card_id: None)
    monkeypatch.setattr(cards_api, 'update_card_cache', lambda *_args, **_kwargs: {
        'cache_updated': True,
        'has_embedded_wi': True,
        'previous_has_embedded_wi': False,
    })
    monkeypatch.setattr(cards_api, 'sync_card_index_jobs', lambda **kwargs: sync_calls.append(kwargs) or {'jobs_enqueued': ['upsert_card', 'upsert_world_embedded', 'upsert_world_owner']})
    monkeypatch.setattr(cards_api, '_is_safe_rel_path', lambda _path, allow_empty=False: True)
    monkeypatch.setattr(cards_api, 'current_config', {'auto_rename_on_import': True})

    class _FakeCache:
        category_counts = {}

        def add_card_update(self, payload):
            return payload

    monkeypatch.setattr(cards_api.ctx, 'cache', _FakeCache())

    client = _make_app().test_client()
    res = client.post('/api/import_from_url', json={'url': 'https://example.com/hero.png', 'category': ''})

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    assert sync_calls == [
        {
            'card_id': 'Hero.png',
            'source_path': str(cards_dir / 'Hero.png'),
            'file_content_changed': True,
            'cache_updated': True,
            'has_embedded_wi': True,
            'previous_has_embedded_wi': False,
        }
    ]
    assert downloaded_path.exists() is False


def test_upload_commit_enqueues_card_and_world_sync_jobs(monkeypatch, tmp_path):
    cards_dir = tmp_path / 'cards'
    temp_dir = tmp_path / 'temp'
    stage_dir = temp_dir / 'batch_upload' / 'batch-1'
    cards_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged_card = stage_dir / 'hero.png'
    staged_card.write_bytes(b'fake-card')

    sync_calls = []

    monkeypatch.setattr(cards_api, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(cards_api, 'TEMP_DIR', str(temp_dir))
    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cards_api, '_is_safe_filename', lambda _value: True)
    monkeypatch.setattr(cards_api, '_is_safe_rel_path', lambda _value, allow_empty=False: True)
    monkeypatch.setattr(cards_api, 'current_config', {'auto_rename_on_import': True})
    monkeypatch.setattr(cards_api, 'extract_card_info', lambda _path: {
        'data': {
            'name': 'Hero',
            'tags': ['blue'],
            'description': '',
            'first_mes': '',
            'mes_example': '',
            'alternate_greetings': [],
            'creator_notes': '',
            'personality': '',
            'scenario': '',
            'system_prompt': '',
            'post_history_instructions': '',
            'character_version': '',
            'character_book': {'name': 'Book', 'entries': {}},
            'extensions': {},
            'creator': '',
        }
    })
    monkeypatch.setattr(cards_api, 'sanitize_filename', lambda value: value)
    monkeypatch.setattr(cards_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(cards_api, 'save_ui_data', lambda _payload: None)
    monkeypatch.setattr(cards_api, 'ensure_import_time', lambda *_args, **_kwargs: (False, 123.0))
    monkeypatch.setattr(cards_api, 'get_import_time', lambda _ui_data, _ui_key, fallback: fallback)
    monkeypatch.setattr(cards_api, 'get_file_hash_and_size', lambda _path: ('hash', 8))
    monkeypatch.setattr(cards_api, 'calculate_token_count', lambda _data: 0)
    monkeypatch.setattr(cards_api, 'auto_run_rules_on_card', lambda _card_id: None)
    monkeypatch.setattr(cards_api, 'update_card_cache', lambda *_args, **_kwargs: {
        'cache_updated': True,
        'has_embedded_wi': True,
        'previous_has_embedded_wi': False,
    })
    monkeypatch.setattr(cards_api, 'sync_card_index_jobs', lambda **kwargs: sync_calls.append(kwargs) or {'jobs_enqueued': ['upsert_card', 'upsert_world_embedded', 'upsert_world_owner']})

    class _FakeCache:
        category_counts = {}

        def add_card_update(self, payload):
            return payload

    monkeypatch.setattr(cards_api.ctx, 'cache', _FakeCache())

    client = _make_app().test_client()
    res = client.post(
        '/api/upload/commit',
        json={
            'batch_id': 'batch-1',
            'category': '',
            'decisions': [{'filename': 'hero.png', 'action': 'overwrite'}],
        },
    )

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    assert sync_calls == [
        {
            'card_id': 'Hero.png',
            'source_path': str(cards_dir / 'Hero.png'),
            'file_content_changed': True,
            'cache_updated': True,
            'has_embedded_wi': True,
            'previous_has_embedded_wi': False,
        }
    ]


def test_move_card_internal_enqueues_incremental_cleanup_for_single_card(monkeypatch, tmp_path):
    from core.services import card_service

    cards_root = tmp_path / 'cards'
    src_dir = cards_root / 'src'
    dst_dir = cards_root / 'dst'
    src_dir.mkdir(parents=True, exist_ok=True)
    dst_dir.mkdir(parents=True, exist_ok=True)
    src_path = src_dir / 'demo.json'
    src_path.write_text('{"spec":"chara_card_v2"}', encoding='utf-8')

    sync_calls = []
    cache_calls = {}
    saved_ui_payloads = []

    class _FakeConn:
        def execute(self, _sql, _params=()):
            return self

        def commit(self):
            return None

    monkeypatch.setattr(card_service, 'CARDS_FOLDER', str(cards_root), raising=False)
    monkeypatch.setattr(card_service, 'load_ui_data', lambda: {'src/demo.json': {'summary': 'note'}})
    monkeypatch.setattr(card_service, 'save_ui_data', lambda payload: saved_ui_payloads.append(dict(payload)))
    monkeypatch.setattr(card_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(card_service, 'update_card_cache', lambda *args, **kwargs: (
        cache_calls.setdefault('update_card_cache', {'args': args, 'kwargs': kwargs}),
        {
            'cache_updated': True,
            'has_embedded_wi': False,
            'previous_has_embedded_wi': False,
        }
    )[1])
    monkeypatch.setattr(card_service, 'sync_card_index_jobs', lambda **kwargs: sync_calls.append(kwargs) or {})
    monkeypatch.setattr(
        card_service.ctx,
        'cache',
        SimpleNamespace(
            id_map={'src/demo.json': {'id': 'src/demo.json', 'category': 'src'}},
            move_card_update=lambda *args, **kwargs: cache_calls.setdefault('move_card_update', (args, kwargs)),
        ),
        raising=False,
    )

    ok, new_id, msg = card_service.move_card_internal('src/demo.json', 'dst')

    assert ok is True
    assert msg == 'Success'
    assert new_id == 'dst/demo.json'
    assert sync_calls == [
        {
            'card_id': 'dst/demo.json',
            'source_path': str(dst_dir / 'demo.json'),
            'file_content_changed': False,
            'rename_changed': True,
            'cache_updated': True,
            'has_embedded_wi': False,
            'previous_has_embedded_wi': False,
            'remove_entity_ids': ['src/demo.json'],
            'remove_owner_ids': ['src/demo.json'],
        }
    ]


def test_api_move_card_uses_shared_move_card_internal(monkeypatch):
    move_calls = []

    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cards_api, '_is_safe_rel_path', lambda _value, allow_empty=False: True)
    monkeypatch.setattr(cards_api, 'move_card_internal', lambda card_id, target_category: move_calls.append((card_id, target_category)) or (True, 'dst/demo.json', 'Success'))
    monkeypatch.setattr(
        cards_api.ctx,
        'cache',
        SimpleNamespace(
            id_map={'dst/demo.json': {'image_url': '/cards_file/dst%2Fdemo.json?t=1'}},
            category_counts={},
        ),
        raising=False,
    )

    client = _make_app().test_client()
    res = client.post('/api/move_card', json={'card_ids': ['src/demo.json'], 'target_category': 'dst'})

    assert res.status_code == 200
    assert res.get_json() == {
        'success': True,
        'count': 1,
        'moved_details': [
            {
                'old_id': 'src/demo.json',
                'new_id': 'dst/demo.json',
                'new_filename': 'demo.json',
                'new_category': 'dst',
                'new_image_url': '/cards_file/dst%2Fdemo.json?t=1',
            }
        ],
        'category_counts': {},
    }
    assert move_calls == [('src/demo.json', 'dst')]


def test_move_card_internal_directory_migrates_prefixed_ui_data_and_nested_categories(monkeypatch, tmp_path):
    from core.services import card_service

    cards_root = tmp_path / 'cards'
    src_dir = cards_root / 'src' / 'pack' / 'sub'
    dst_dir = cards_root / 'dst'
    src_dir.mkdir(parents=True, exist_ok=True)
    dst_dir.mkdir(parents=True, exist_ok=True)
    moved_file = src_dir / 'hero.json'
    moved_file.write_text('{"spec":"chara_card_v2"}', encoding='utf-8')

    saved_ui_payloads = []
    update_calls = []
    sync_calls = []

    class _FakeConn:
        def __init__(self):
            self.executed = []
            self._rows = []

        def execute(self, sql, params=()):
            self.executed.append((sql, params))
            normalized_sql = ' '.join(str(sql).split())
            if normalized_sql.startswith("SELECT id FROM card_metadata WHERE id LIKE ? || '/%' ESCAPE '\\'"):
                self._rows = [('src/pack/sub/hero.json',)]
            return self

        def fetchall(self):
            return list(self._rows)

        def commit(self):
            return None

    class _FakeCache:
        def __init__(self):
            self.id_map = {
                'src/pack/sub/hero.json': {
                    'id': 'src/pack/sub/hero.json',
                    'category': 'src/pack/sub',
                    'is_bundle': False,
                    'last_modified': 1,
                }
            }
            self.bundle_map = {}
            self.visible_folders = []

        def move_bundle_update(self, old_bundle_path, new_bundle_path, old_category, new_category):
            moved_items = []
            for card_id in list(self.id_map.keys()):
                if card_id == old_bundle_path or card_id.startswith(old_bundle_path + '/'):
                    moved_items.append((card_id, self.id_map.pop(card_id)))

            for old_id, card in moved_items:
                if old_id == old_bundle_path:
                    new_id = new_bundle_path
                else:
                    new_id = new_bundle_path + old_id[len(old_bundle_path):]

                card = dict(card)
                card['id'] = new_id
                card['category'] = new_category
                self.id_map[new_id] = card

        def move_folder_update(self, old_path_prefix, new_path_prefix):
            new_bundle_map = {}
            for bundle_dir, bundle_card_id in self.bundle_map.items():
                if bundle_dir == old_path_prefix:
                    remapped_dir = new_path_prefix
                elif bundle_dir.startswith(old_path_prefix + '/'):
                    remapped_dir = new_path_prefix + bundle_dir[len(old_path_prefix):]
                else:
                    remapped_dir = bundle_dir

                if bundle_card_id.startswith(old_path_prefix + '/'):
                    remapped_card_id = new_path_prefix + bundle_card_id[len(old_path_prefix):]
                else:
                    remapped_card_id = bundle_card_id

                new_bundle_map[remapped_dir] = remapped_card_id

            moved_items = []
            for card_id in list(self.id_map.keys()):
                if not card_id.startswith(old_path_prefix + '/'):
                    continue
                moved_items.append((card_id, self.id_map.pop(card_id)))

            for old_id, card in moved_items:
                suffix = old_id[len(old_path_prefix):]
                new_id = new_path_prefix + suffix
                old_category = card.get('category', '')
                if old_category == old_path_prefix:
                    new_category = new_path_prefix
                elif old_category.startswith(old_path_prefix + '/'):
                    new_category = new_path_prefix + old_category[len(old_path_prefix):]
                else:
                    new_category = new_id.rsplit('/', 1)[0] if '/' in new_id else ''

                card = dict(card)
                card['id'] = new_id
                card['category'] = new_category
                self.id_map[new_id] = card

    fake_conn = _FakeConn()
    fake_cache = _FakeCache()

    monkeypatch.setattr(card_service, 'CARDS_FOLDER', str(cards_root), raising=False)
    monkeypatch.setattr(
        card_service,
        'load_ui_data',
        lambda: {
            'src/pack/sub/hero.json': {'summary': 'nested note'},
            'src/pack': {'summary': 'folder note'},
        },
    )
    monkeypatch.setattr(
        card_service,
        'save_ui_data',
        lambda payload: saved_ui_payloads.append(json.loads(json.dumps(payload, ensure_ascii=False))),
    )
    monkeypatch.setattr(card_service, 'get_db', lambda: fake_conn)
    monkeypatch.setattr(
        card_service,
        'update_card_cache',
        lambda card_id, full_path, **kwargs: (
            update_calls.append({'card_id': card_id, 'full_path': full_path, 'kwargs': kwargs}),
            {
                'cache_updated': True,
                'has_embedded_wi': False,
                'previous_has_embedded_wi': False,
            },
        )[1],
    )
    monkeypatch.setattr(card_service, 'sync_card_index_jobs', lambda **kwargs: sync_calls.append(kwargs) or {})
    monkeypatch.setattr(card_service.ctx, 'cache', fake_cache, raising=False)

    ok, new_id, msg = card_service.move_card_internal('src/pack', 'dst')

    assert ok is True
    assert msg == 'Success'
    assert new_id == 'dst/pack'
    assert saved_ui_payloads[-1] == {
        'dst/pack': {'summary': 'folder note'},
        'dst/pack/sub/hero.json': {'summary': 'nested note'},
    }
    assert fake_conn.executed == [
        ("SELECT id FROM card_metadata WHERE id LIKE ? || '/%' ESCAPE '\\'", ('src/pack',)),
        (
            """
            UPDATE card_metadata 
            SET id = ?, category = REPLACE(category, ?, ?) 
            WHERE id = ?
        """,
            ('dst/pack/sub/hero.json', 'src/pack', 'dst/pack', 'src/pack/sub/hero.json'),
        ),
    ]
    assert update_calls == [
        {
            'card_id': 'dst/pack/sub/hero.json',
            'full_path': str(cards_root / 'dst' / 'pack' / 'sub' / 'hero.json'),
            'kwargs': {'remove_entity_ids': ['src/pack/sub/hero.json']},
        }
    ]
    assert sync_calls == [
        {
            'card_id': 'dst/pack/sub/hero.json',
            'source_path': str(cards_root / 'dst' / 'pack' / 'sub' / 'hero.json'),
            'file_content_changed': False,
            'rename_changed': True,
            'cache_updated': True,
            'has_embedded_wi': False,
            'previous_has_embedded_wi': False,
            'remove_entity_ids': ['src/pack/sub/hero.json'],
            'remove_owner_ids': ['src/pack/sub/hero.json'],
        }
    ]
    assert fake_cache.id_map == {
        'dst/pack/sub/hero.json': {
            'id': 'dst/pack/sub/hero.json',
            'category': 'dst/pack/sub',
            'is_bundle': False,
            'last_modified': 1,
        }
    }


def test_move_card_internal_bundle_directory_migrates_version_remarks_and_bundle_cache(monkeypatch, tmp_path):
    from core.services import card_service

    cards_root = tmp_path / 'cards'
    src_dir = cards_root / 'src' / 'bundle'
    dst_dir = cards_root / 'dst'
    src_dir.mkdir(parents=True, exist_ok=True)
    dst_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / '.bundle').write_text('1', encoding='utf-8')
    (src_dir / 'cover.json').write_text('{"spec":"chara_card_v2"}', encoding='utf-8')
    (src_dir / 'alt.json').write_text('{"spec":"chara_card_v2"}', encoding='utf-8')

    saved_ui_payloads = []
    update_calls = []
    sync_calls = []

    class _FakeConn:
        def __init__(self):
            self.executed = []
            self._rows = []

        def execute(self, sql, params=()):
            self.executed.append((sql, params))
            normalized_sql = ' '.join(str(sql).split())
            if normalized_sql.startswith("SELECT id FROM card_metadata WHERE id LIKE ? || '/%' ESCAPE '\\'"):
                self._rows = [
                    ('src/bundle/cover.json',),
                    ('src/bundle/alt.json',),
                ]
            return self

        def fetchall(self):
            return list(self._rows)

        def commit(self):
            return None

    class _FakeCache:
        def __init__(self):
            self.id_map = {
                'src/bundle/cover.json': {
                    'id': 'src/bundle/cover.json',
                    'category': 'src',
                    'is_bundle': True,
                    'bundle_dir': 'src/bundle',
                    'last_modified': 1,
                    'versions': [
                        {'id': 'src/bundle/cover.json', 'filename': 'cover.json'},
                        {'id': 'src/bundle/alt.json', 'filename': 'alt.json'},
                    ],
                }
            }
            self.bundle_map = {'src/bundle': 'src/bundle/cover.json'}
            self.visible_folders = []

        def move_bundle_update(self, old_bundle_path, new_bundle_path, old_category, new_category):
            moved_items = []
            for card_id in list(self.id_map.keys()):
                if card_id == old_bundle_path or card_id.startswith(old_bundle_path + '/'):
                    moved_items.append((card_id, self.id_map.pop(card_id)))

            for old_id, card in moved_items:
                if old_id == old_bundle_path:
                    new_id = new_bundle_path
                else:
                    new_id = new_bundle_path + old_id[len(old_bundle_path):]

                card = dict(card)
                card['id'] = new_id
                card['category'] = new_category
                if card.get('is_bundle'):
                    card['bundle_dir'] = new_bundle_path
                self.id_map[new_id] = card

            main_id = self.bundle_map.pop(old_bundle_path, None)
            if main_id:
                self.bundle_map[new_bundle_path] = new_bundle_path + main_id[len(old_bundle_path):]

        def move_folder_update(self, old_path_prefix, new_path_prefix):
            new_bundle_map = {}
            for bundle_dir, bundle_card_id in self.bundle_map.items():
                if bundle_dir == old_path_prefix:
                    remapped_dir = new_path_prefix
                elif bundle_dir.startswith(old_path_prefix + '/'):
                    remapped_dir = new_path_prefix + bundle_dir[len(old_path_prefix):]
                else:
                    remapped_dir = bundle_dir

                if bundle_card_id.startswith(old_path_prefix + '/'):
                    remapped_card_id = new_path_prefix + bundle_card_id[len(old_path_prefix):]
                else:
                    remapped_card_id = bundle_card_id

                new_bundle_map[remapped_dir] = remapped_card_id

            moved_items = []
            for card_id in list(self.id_map.keys()):
                if not card_id.startswith(old_path_prefix + '/'):
                    continue
                moved_items.append((card_id, self.id_map.pop(card_id)))

            for old_id, card in moved_items:
                suffix = old_id[len(old_path_prefix):]
                new_id = new_path_prefix + suffix
                card = dict(card)
                card['id'] = new_id
                if card.get('bundle_dir') == old_path_prefix:
                    card['bundle_dir'] = new_path_prefix
                versions = card.get('versions')
                if isinstance(versions, list):
                    for version in versions:
                        if not isinstance(version, dict):
                            continue
                        version_id = str(version.get('id') or '')
                        if version_id.startswith(old_path_prefix + '/'):
                            version['id'] = new_path_prefix + version_id[len(old_path_prefix):]
                self.id_map[new_id] = card

            self.bundle_map = new_bundle_map

    fake_conn = _FakeConn()
    fake_cache = _FakeCache()

    monkeypatch.setattr(card_service, 'CARDS_FOLDER', str(cards_root), raising=False)
    monkeypatch.setattr(
        card_service,
        'load_ui_data',
        lambda: {
            'src/bundle': {
                card_service.VERSION_REMARKS_KEY: {
                    'src/bundle/cover.json': {'summary': 'cover note'},
                    'src/bundle/alt.json': {'summary': 'alt note'},
                },
                'resource_folder': 'hero-assets',
            }
        },
    )
    monkeypatch.setattr(
        card_service,
        'save_ui_data',
        lambda payload: saved_ui_payloads.append(json.loads(json.dumps(payload, ensure_ascii=False))),
    )
    monkeypatch.setattr(card_service, 'get_db', lambda: fake_conn)
    monkeypatch.setattr(
        card_service,
        'update_card_cache',
        lambda card_id, full_path, **kwargs: (
            update_calls.append({'card_id': card_id, 'full_path': full_path, 'kwargs': kwargs}),
            {
                'cache_updated': True,
                'has_embedded_wi': False,
                'previous_has_embedded_wi': False,
            },
        )[1],
    )
    monkeypatch.setattr(card_service, 'sync_card_index_jobs', lambda **kwargs: sync_calls.append(kwargs) or {})
    monkeypatch.setattr(card_service.ctx, 'cache', fake_cache, raising=False)

    ok, new_id, msg = card_service.move_card_internal('src/bundle', 'dst')

    assert ok is True
    assert msg == 'Success'
    assert new_id == 'dst/bundle'
    assert saved_ui_payloads[-1] == {
        'dst/bundle': {
            card_service.VERSION_REMARKS_KEY: {
                'dst/bundle/cover.json': {'summary': 'cover note'},
                'dst/bundle/alt.json': {'summary': 'alt note'},
            },
            'resource_folder': 'hero-assets',
        }
    }
    assert update_calls == [
        {
            'card_id': 'dst/bundle/cover.json',
            'full_path': str(cards_root / 'dst' / 'bundle' / 'cover.json'),
            'kwargs': {'remove_entity_ids': ['src/bundle/cover.json']},
        },
        {
            'card_id': 'dst/bundle/alt.json',
            'full_path': str(cards_root / 'dst' / 'bundle' / 'alt.json'),
            'kwargs': {'remove_entity_ids': ['src/bundle/alt.json']},
        },
    ]
    assert sync_calls == [
        {
            'card_id': 'dst/bundle/cover.json',
            'source_path': str(cards_root / 'dst' / 'bundle' / 'cover.json'),
            'file_content_changed': False,
            'rename_changed': True,
            'cache_updated': True,
            'has_embedded_wi': False,
            'previous_has_embedded_wi': False,
            'remove_entity_ids': ['src/bundle/cover.json'],
            'remove_owner_ids': ['src/bundle/cover.json'],
        },
        {
            'card_id': 'dst/bundle/alt.json',
            'source_path': str(cards_root / 'dst' / 'bundle' / 'alt.json'),
            'file_content_changed': False,
            'rename_changed': True,
            'cache_updated': True,
            'has_embedded_wi': False,
            'previous_has_embedded_wi': False,
            'remove_entity_ids': ['src/bundle/alt.json'],
            'remove_owner_ids': ['src/bundle/alt.json'],
        },
    ]
    assert fake_cache.bundle_map == {'dst/bundle': 'dst/bundle/cover.json'}
    assert fake_cache.id_map['dst/bundle/cover.json']['bundle_dir'] == 'dst/bundle'
    assert fake_cache.id_map['dst/bundle/cover.json']['versions'] == [
        {'id': 'dst/bundle/cover.json', 'filename': 'cover.json'},
        {'id': 'dst/bundle/alt.json', 'filename': 'alt.json'},
    ]
