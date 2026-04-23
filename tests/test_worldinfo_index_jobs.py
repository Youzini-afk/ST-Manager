import logging
import sqlite3
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services import cache_service
from core.services import index_build_service
from core.services import scan_service
from core.services import index_job_worker


def test_worldinfo_watch_filter_accepts_global_and_resource_lorebooks(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('D:/data/lorebooks/main/book.json') is True
    assert scan_service._is_worldinfo_watch_path('D:/data/resources/lucy/lorebooks/book.json') is True
    assert scan_service._is_worldinfo_watch_path('D:/data/resources/lucy/images/cover.png') is False


def test_resolve_resource_worldinfo_owner_card_ids_returns_all_matching_cards(monkeypatch):
    monkeypatch.setattr(index_build_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})
    monkeypatch.setattr(
        index_build_service,
        'load_ui_data',
        lambda: {
            'cards/zeta.png': {'resource_folder': 'shared-pack'},
            'cards/alpha.png': {'resource_folder': 'shared-pack'},
            'cards/other.png': {'resource_folder': 'other-pack'},
        },
    )

    assert index_build_service.resolve_resource_worldinfo_owner_card_ids('D:/data/resources/shared-pack/lorebooks/book.json') == [
        'cards/alpha.png',
        'cards/zeta.png',
    ]


def test_update_card_cache_enqueues_embedded_owner_refresh(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {'is_favorite': 0, 'has_character_book': 0}

        def commit(self):
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': [], 'character_book': {'name': 'Book', 'entries': {}}}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (True, 'Book'))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))

    cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0)

    job_names = [call[0][0] for call in calls]
    assert 'upsert_card' in job_names
    assert 'upsert_world_embedded' in job_names


def test_update_card_cache_enqueues_single_upsert_card_with_stale_cleanup_payload(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {'is_favorite': 0, 'has_character_book': 0}

        def commit(self):
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': ['blue']}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))

    cache_service.update_card_cache(
        'cards/hero-renamed.png',
        'D:/cards/hero-renamed.png',
        mtime=123.0,
        remove_entity_ids=['cards/hero.json'],
    )

    assert calls == [
        (
            ('upsert_card',),
            {
                'entity_id': 'cards/hero-renamed.png',
                'source_path': 'D:/cards/hero-renamed.png',
                'payload': {'remove_entity_ids': ['cards/hero.json']},
            },
        )
    ]


def test_update_card_cache_enqueues_embedded_owner_refresh_when_worldinfo_removed(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, query, *_args, **_kwargs):
            self._last_query = query
            return self

        def fetchone(self):
            if 'SELECT is_favorite, has_character_book' in getattr(self, '_last_query', ''):
                return {'is_favorite': 0, 'has_character_book': 1}
            return {'is_favorite': 0}

        def commit(self):
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': []}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))

    cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0)

    job_names = [call[0][0] for call in calls]
    assert 'upsert_card' in job_names
    assert 'upsert_world_embedded' in job_names


def test_worldinfo_watch_filter_rejects_sibling_prefix_paths(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('D:/data/lorebooks2/x.json') is False


def test_worldinfo_watch_filter_is_case_tolerant_for_valid_paths(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('d:/DATA/LOREBOOKS/main/book.JSON') is True
    assert scan_service._is_worldinfo_watch_path('d:/DATA/RESOURCES/lucy/LOREBOOKS/book.JSON') is True


def test_worldinfo_watcher_move_into_lorebook_path_enqueues_dest_path(monkeypatch):
    calls = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **_kwargs: calls.append((('scan',), {})))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='moved',
        src_path='D:/tmp/book.json',
        dest_path='D:/data/lorebooks/main/book.json',
    )
    scheduled['handler'].on_any_event(event)

    assert calls == [(('upsert_worldinfo_path',), {'source_path': 'D:/data/lorebooks/main/book.json'})]


def test_worldinfo_watcher_routes_resource_lorebook_to_owner_refresh(monkeypatch):
    calls = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **_kwargs: calls.append((('scan',), {})))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})
    monkeypatch.setattr(
        scan_service,
        'resolve_resource_worldinfo_owner_card_ids',
        lambda source_path: ['cards/alpha.png', 'cards/zeta.png'] if 'hero-assets' in source_path else [],
        raising=False,
    )

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='modified',
        src_path='D:/data/resources/hero-assets/lorebooks/book.json',
        dest_path='',
    )
    scheduled['handler'].on_any_event(event)

    assert calls == [
        (('upsert_world_owner',), {'entity_id': 'cards/alpha.png', 'source_path': 'D:/data/resources/hero-assets/lorebooks/book.json'}),
        (('upsert_world_owner',), {'entity_id': 'cards/zeta.png', 'source_path': 'D:/data/resources/hero-assets/lorebooks/book.json'}),
    ]


def test_card_watcher_routes_modify_to_targeted_card_task(monkeypatch):
    queued = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service.ctx.scan_queue, 'put', lambda task: queued.append(task))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: queued.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **kwargs: queued.append({'type': 'FULL_SCAN', **kwargs}))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='modified',
        src_path='D:/cards/hero.png',
        dest_path='',
    )
    scheduled['handler'].on_any_event(event)

    assert queued == [
        {'type': 'CARD_UPSERT', 'path': 'D:/cards/hero.png'}
    ]


def test_card_watcher_routes_move_to_targeted_card_task(monkeypatch):
    queued = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service.ctx.scan_queue, 'put', lambda task: queued.append(task))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: queued.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **kwargs: queued.append({'type': 'FULL_SCAN', **kwargs}))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='moved',
        src_path='D:/cards/old-name.png',
        dest_path='D:/cards/new-name.png',
    )
    scheduled['handler'].on_any_event(event)

    assert queued == [
        {'type': 'CARD_MOVE', 'src_path': 'D:/cards/old-name.png', 'dest_path': 'D:/cards/new-name.png'}
    ]


def test_card_watcher_routes_delete_to_targeted_card_task(monkeypatch):
    queued = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service.ctx.scan_queue, 'put', lambda task: queued.append(task))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: queued.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **kwargs: queued.append({'type': 'FULL_SCAN', **kwargs}))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='deleted',
        src_path='D:/cards/deleted.png',
        dest_path='',
    )
    scheduled['handler'].on_any_event(event)

    assert queued == [
        {'type': 'CARD_DELETE', 'path': 'D:/cards/deleted.png'}
    ]


def test_worldinfo_watcher_ignores_non_write_events(monkeypatch):
    calls = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **_kwargs: calls.append((('scan',), {})))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='opened',
        src_path='D:/data/lorebooks/main/book.json',
        dest_path='',
    )
    scheduled['handler'].on_any_event(event)

    assert calls == []


def test_start_fs_watcher_skips_missing_watch_paths(monkeypatch, caplog, tmp_path):
    scheduled_paths = []
    started = []

    class _FakeObserver:
        daemon = False

        def schedule(self, _handler, watch_path, recursive=True):
            scheduled_paths.append((watch_path, recursive))
            if watch_path != str(cards_dir):
                raise FileNotFoundError(watch_path)

        def start(self):
            started.append(True)

    class _FakeHandlerBase:
        pass

    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir()

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(
        scan_service,
        'load_config',
        lambda: {
            'world_info_dir': str(tmp_path / 'missing-lorebooks'),
            'resources_dir': str(tmp_path / 'missing-resources'),
        },
    )

    with caplog.at_level(logging.WARNING):
        scan_service.start_fs_watcher()

    assert scheduled_paths == [
        (str(cards_dir), True),
        (str(tmp_path / 'missing-lorebooks'), True),
        (str(tmp_path / 'missing-resources'), True),
    ]
    assert started == [True]
    assert 'does not exist yet' in caplog.text


def test_update_card_cache_returns_false_when_cache_write_fails(monkeypatch):
    monkeypatch.setattr(cache_service, 'get_db', lambda: (_ for _ in ()).throw(RuntimeError('db down')))

    assert cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0) is False


def test_cards_api_worldinfo_owner_enqueue_is_gated_by_update_card_cache_success_contract():
    source = (ROOT / 'core/api/v1/cards.py').read_text(encoding='utf-8')

    assert "remove_entity_ids=[raw_id] if raw_id != final_rel_path_id else None" in source
    assert "should_enqueue_world_owner = bool(resource_folder_changed or cache_updated)" in source
    assert "if should_enqueue_world_owner:" in source
    assert "enqueue_index_job('upsert_world_owner', entity_id=final_rel_path_id, source_path=current_full_path)" in source
    assert "enqueue_index_job(\n                    'upsert_card'" not in source
    assert "enqueue_index_job('upsert_world_embedded', entity_id=final_rel_path_id, source_path=current_full_path)" not in source


def test_background_scanner_enqueues_targeted_card_reconcile_when_changes_detected(monkeypatch):
    calls = []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_args, **_kwargs):
            return None

        def cursor(self):
            return self

        def fetchall(self):
            return [('gone.png', 10.0, 100, 0, 'hash', 0)]

        def commit(self):
            return None

    monkeypatch.setattr(scan_service.sqlite3, 'connect', lambda *_args, **_kwargs: _FakeConn())
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'schedule_reload', lambda **_kwargs: None)
    monkeypatch.setattr(scan_service.os, 'walk', lambda _root: iter([('D:/cards', [], [])]))

    scan_service._perform_scan_logic()

    assert calls == [
        (('upsert_card',), {'entity_id': 'gone.png', 'source_path': 'D:\\cards\\gone.png'}),
        (('upsert_world_owner',), {'entity_id': 'gone.png', 'source_path': 'D:\\cards\\gone.png', 'payload': {'remove_owner_ids': ['gone.png']}}),
    ]


def test_process_card_upsert_task_updates_metadata_and_enqueues_targeted_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    card_path = cards_dir / 'nested' / 'hero.png'
    card_path.parent.mkdir(parents=True)
    card_path.write_bytes(b'hero')

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''
            CREATE TABLE card_metadata (
                id TEXT PRIMARY KEY,
                char_name TEXT,
                description TEXT,
                first_mes TEXT,
                mes_example TEXT,
                tags TEXT,
                category TEXT,
                creator TEXT,
                char_version TEXT,
                last_modified REAL,
                file_hash TEXT,
                file_size INTEGER,
                token_count INTEGER DEFAULT 0,
                has_character_book INTEGER DEFAULT 0,
                character_book_name TEXT DEFAULT '',
                is_favorite INTEGER DEFAULT 0
            )
            '''
        )
        conn.commit()

    calls = []
    reloads = []

    monkeypatch.setattr(scan_service, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(scan_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': ['blue'], 'description': 'desc'}})
    monkeypatch.setattr(scan_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(scan_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'schedule_reload', lambda **kwargs: reloads.append(kwargs))

    assert scan_service._process_card_upsert_task(str(card_path)) is True

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT id, char_name, category, token_count FROM card_metadata ORDER BY id'
        ).fetchone()

    assert row == ('nested/hero.png', 'Hero', 'nested', 111)
    assert calls == [
        (('upsert_card',), {'entity_id': 'nested/hero.png', 'source_path': str(card_path)}),
        (('upsert_world_owner',), {'entity_id': 'nested/hero.png', 'source_path': str(card_path)}),
    ]
    assert reloads == [{'reason': 'watchdog_card_upsert'}]


def test_process_card_move_task_replaces_old_metadata_and_enqueues_targeted_cleanup(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    new_card_path = cards_dir / 'renamed' / 'new-name.png'
    new_card_path.parent.mkdir(parents=True)
    new_card_path.write_bytes(b'new')

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''
            CREATE TABLE card_metadata (
                id TEXT PRIMARY KEY,
                char_name TEXT,
                description TEXT,
                first_mes TEXT,
                mes_example TEXT,
                tags TEXT,
                category TEXT,
                creator TEXT,
                char_version TEXT,
                last_modified REAL,
                file_hash TEXT,
                file_size INTEGER,
                token_count INTEGER DEFAULT 0,
                has_character_book INTEGER DEFAULT 0,
                character_book_name TEXT DEFAULT '',
                is_favorite INTEGER DEFAULT 0
            )
            '''
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, category, last_modified, file_hash, file_size, token_count, has_character_book, character_book_name, is_favorite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('old-name.png', 'Old Hero', 'legacy', 10.0, '', 3, 7, 0, '', 1),
        )
        conn.commit()

    calls = []
    reloads = []

    monkeypatch.setattr(scan_service, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(scan_service, 'extract_card_info', lambda _path: {'data': {'name': 'New Hero', 'tags': ['green']}})
    monkeypatch.setattr(scan_service, 'calculate_token_count', lambda _payload: 222)
    monkeypatch.setattr(scan_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'schedule_reload', lambda **kwargs: reloads.append(kwargs))

    assert scan_service._process_card_move_task('old-name.png', str(new_card_path)) is True

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute('SELECT id, char_name, category, token_count FROM card_metadata ORDER BY id').fetchall()

    assert rows == [('renamed/new-name.png', 'New Hero', 'renamed', 222)]
    assert calls == [
        (
            ('upsert_card',),
            {
                'entity_id': 'renamed/new-name.png',
                'source_path': str(new_card_path),
                'payload': {'remove_entity_ids': ['old-name.png']},
            },
        ),
        (
            ('upsert_world_owner',),
            {
                'entity_id': 'renamed/new-name.png',
                'source_path': str(new_card_path),
                'payload': {'remove_owner_ids': ['old-name.png']},
            },
        ),
    ]
    assert reloads == [{'reason': 'watchdog_card_move'}]


def test_process_card_delete_task_removes_metadata_and_enqueues_targeted_cleanup(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''
            CREATE TABLE card_metadata (
                id TEXT PRIMARY KEY,
                char_name TEXT,
                description TEXT,
                first_mes TEXT,
                mes_example TEXT,
                tags TEXT,
                category TEXT,
                creator TEXT,
                char_version TEXT,
                last_modified REAL,
                file_hash TEXT,
                file_size INTEGER,
                token_count INTEGER DEFAULT 0,
                has_character_book INTEGER DEFAULT 0,
                character_book_name TEXT DEFAULT '',
                is_favorite INTEGER DEFAULT 0
            )
            '''
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, category, last_modified, file_hash, file_size, token_count, has_character_book, character_book_name, is_favorite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('nested/deleted.png', 'Deleted Hero', 'nested', 10.0, '', 3, 7, 0, '', 0),
        )
        conn.commit()

    calls = []
    reloads = []

    monkeypatch.setattr(scan_service, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'schedule_reload', lambda **kwargs: reloads.append(kwargs))

    assert scan_service._process_card_delete_task(str(cards_dir / 'nested' / 'deleted.png')) is True

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute('SELECT id FROM card_metadata ORDER BY id').fetchall()

    assert rows == []
    assert calls == [
        (('upsert_card',), {'entity_id': 'nested/deleted.png', 'source_path': str(cards_dir / 'nested' / 'deleted.png')}),
        (
            ('upsert_world_owner',),
            {
                'entity_id': 'nested/deleted.png',
                'source_path': str(cards_dir / 'nested' / 'deleted.png'),
                'payload': {'remove_owner_ids': ['nested/deleted.png']},
            },
        ),
    ]
    assert reloads == [{'reason': 'watchdog_card_delete'}]


def test_process_scan_task_falls_back_to_full_scan_when_card_task_fails(monkeypatch):
    queued = []

    monkeypatch.setattr(scan_service, '_process_card_upsert_task', lambda _path: False)
    monkeypatch.setattr(scan_service.ctx.scan_queue, 'put', lambda task: queued.append(task))

    assert scan_service._process_scan_task({'type': 'CARD_UPSERT', 'path': 'D:/cards/missing.png'}) is False

    assert queued == [
        {'type': 'FULL_SCAN', 'reason': 'card_upsert_failed'}
    ]


def test_enqueue_index_job_persists_pending_row(monkeypatch, tmp_path):
    import sqlite3

    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        from core.data.index_runtime_store import ensure_index_runtime_schema

        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    index_job_worker.enqueue_index_job('rebuild_scope', payload={'scope': 'worldinfo'})

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT job_type, status, payload_json FROM index_jobs ORDER BY id DESC LIMIT 1'
        ).fetchone()

    assert row[0] == 'rebuild_scope'
    assert row[1] == 'pending'
    assert 'worldinfo' in row[2]


def test_update_card_cache_returns_true_when_enqueue_fails_after_commit(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {'is_favorite': 0, 'has_character_book': 0}

        def commit(self):
            calls.append('commit')
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': [], 'character_book': {'name': 'Book', 'entries': {}}}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (True, 'Book'))

    def _boom(*_args, **_kwargs):
        raise RuntimeError('queue down')

    monkeypatch.setattr(cache_service, 'enqueue_index_job', _boom)

    assert cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0) is True
    assert calls == ['commit']


def test_worldinfo_watch_filter_returns_false_for_cross_drive_path(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('E:/other/book.json') is False


def test_start_fs_watcher_schedules_cards_and_distinct_worldinfo_roots(monkeypatch):
    scheduled = []

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled.append((handler, watch_path, recursive))

        def start(self):
            return None

    class _FakeHandlerBase:
        pass

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'load_config', lambda: {
        'world_info_dir': 'D:/data/lorebooks',
        'resources_dir': 'D:/data/resources',
    })

    scan_service.start_fs_watcher()

    assert [item[1] for item in scheduled] == ['D:/cards', 'D:/data/lorebooks', 'D:/data/resources']
    assert all(item[2] is True for item in scheduled)
