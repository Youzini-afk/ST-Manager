import json
import logging
import os
import sqlite3
import threading
import time
from copy import deepcopy
from typing import Any

from core.config import CARDS_FOLDER, DEFAULT_DB_PATH, load_config
from core.context import ctx
from core.data.index_store import ensure_index_schema
from core.data.ui_store import load_ui_data
from core.services.index_job_worker import enqueue_index_job as enqueue_index_job
from core.services.index_job_worker import start_index_job_worker
from core.utils.image import extract_card_info
from core.utils.source_revision import build_file_source_revision


logger = logging.getLogger(__name__)


SUPPORTED_REBUILD_SCOPES = {'cards', 'worldinfo'}


def _normalize_category_path(value) -> str:
    if value is None:
        return ''
    path = str(value).replace('\\', '/').strip().strip('/')
    if not path:
        return ''
    parts = [part.strip() for part in path.split('/') if part.strip()]
    return '/'.join(parts)


def _iter_category_ancestors(category: str):
    current = _normalize_category_path(category)
    while current:
        yield current
        if '/' not in current:
            break
        current = current.rsplit('/', 1)[0]


def _normalize_resource_item_key(path: str) -> str:
    if not path:
        return ''
    try:
        return os.path.normcase(os.path.normpath(str(path))).replace('\\', '/')
    except Exception:
        return ''


def _worldinfo_note_summary(ui_data: dict, source_type: str, *, file_path: str = '', card_id: str = '') -> str:
    notes = (ui_data.get('_worldinfo_notes_v1') or {}) if isinstance(ui_data, dict) else {}
    if source_type == 'embedded':
        key = f'embedded::{card_id}'
    else:
        key = f'{source_type}::{_normalize_resource_item_key(file_path)}'
    note = notes.get(key) or {}
    return str(note.get('summary') or '') if isinstance(note, dict) else ''


def _embedded_summary(ui_data: dict, card_id: str) -> str:
    if not isinstance(ui_data, dict):
        return ''
    card_meta = ui_data.get(card_id) or {}
    if isinstance(card_meta, dict):
        summary = str(card_meta.get('summary') or '')
        if summary.strip():
            return summary
    return _worldinfo_note_summary(ui_data, 'embedded', card_id=card_id)


def _upsert_worldinfo_search(conn, entity_id: str, *parts):
    content = ' '.join(str(part or '').strip() for part in parts if str(part or '').strip())
    conn.execute(
        'INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)',
        (entity_id, content),
    )


def _upsert_card_search(conn, entity_id: str, content: str):
    conn.execute(
        'INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)',
        (entity_id, content),
    )
    conn.execute(
        'INSERT OR REPLACE INTO index_search_full(entity_id, content) VALUES (?, ?)',
        (entity_id, content),
    )


def _rebuild_worldinfo_category_stats(conn, global_dir: str):
    conn.execute("DELETE FROM index_category_stats WHERE scope = 'worldinfo'")

    direct_counts = {}
    subtree_counts = {}

    rows = conn.execute(
        "SELECT entity_type, display_category FROM index_entities WHERE entity_type LIKE 'world_%'"
    ).fetchall()
    for row in rows:
        entity_type = str(row['entity_type'] or '')
        category = _normalize_category_path(row['display_category'])
        if not category:
            continue

        direct_counts[(entity_type, category)] = direct_counts.get((entity_type, category), 0) + 1
        direct_counts[('world_all', category)] = direct_counts.get(('world_all', category), 0) + 1

        for path in _iter_category_ancestors(category):
            subtree_counts[(entity_type, path)] = subtree_counts.get((entity_type, path), 0) + 1
            subtree_counts[('world_all', path)] = subtree_counts.get(('world_all', path), 0) + 1

    physical_paths = set()
    if global_dir and os.path.isdir(global_dir):
        for root, dirs, _files in os.walk(global_dir):
            rel_root = os.path.relpath(root, global_dir).replace('\\', '/')
            current_category = '' if rel_root == '.' else _normalize_category_path(rel_root)
            if not current_category:
                continue
            for path in _iter_category_ancestors(current_category):
                physical_paths.add(path)

    stat_keys = set(direct_counts) | set(subtree_counts)
    stat_keys.update(('world_global', path) for path in physical_paths)
    stat_keys.update(('world_all', path) for path in physical_paths)

    for entity_type, category in sorted(stat_keys):
        conn.execute(
            'INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)',
            (
                'worldinfo',
                entity_type,
                category,
                int(direct_counts.get((entity_type, category), 0)),
                int(subtree_counts.get((entity_type, category), 0)),
            ),
        )


def _connect():
    conn = sqlite3.connect(DEFAULT_DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    ensure_index_schema(conn)
    return conn


def get_index_status() -> dict[str, Any]:
    with ctx.index_lock:
        snapshot = deepcopy(dict(ctx.index_state))

    try:
        with sqlite3.connect(DEFAULT_DB_PATH, timeout=60) as conn:
            conn.row_factory = sqlite3.Row

            schema_rows = conn.execute(
                'SELECT component, applied_version, state, last_error FROM index_schema_state'
            ).fetchall()
            schema_map = {str(row['component']): row for row in schema_rows}

            db_row = schema_map.get('db')
            runtime_row = schema_map.get('index_runtime')
            schema_state = 'ready'
            for row in (db_row, runtime_row):
                if not row:
                    schema_state = 'empty'
                    continue
                if str(row['state'] or '') not in ('ready', ''):
                    schema_state = str(row['state'] or 'empty')
                    break

            snapshot['schema'] = {
                'db_version': int((db_row['applied_version'] if db_row else 0) or 0),
                'index_runtime_version': int((runtime_row['applied_version'] if runtime_row else 0) or 0),
                'state': schema_state,
                'message': str(snapshot.get('schema', {}).get('message') or ''),
            }

            build_rows = conn.execute(
                'SELECT scope, active_generation, building_generation, state, phase, items_written, last_error FROM index_build_state'
            ).fetchall()
    except sqlite3.OperationalError:
        return snapshot

    persisted_scopes: dict[str, dict[str, Any]] = {}
    for row in build_rows:
        scope = str(row['scope'] or '')
        if scope not in ('cards', 'worldinfo'):
            continue
        persisted_scopes[scope] = {
            'state': str(row['state'] or 'empty'),
            'phase': str(row['phase'] or ''),
            'active_generation': int(row['active_generation'] or 0),
            'building_generation': int(row['building_generation'] or 0),
            'items_written': int(row['items_written'] or 0),
            'last_error': str(row['last_error'] or ''),
        }

    for scope in ('cards', 'worldinfo'):
        if scope in persisted_scopes:
            snapshot[scope] = persisted_scopes[scope]

    pending_jobs = int(snapshot.get('jobs', {}).get('pending_jobs') or snapshot.get('pending_jobs') or 0)
    worker_state = str(snapshot.get('jobs', {}).get('worker_state') or 'idle')
    active_scope = str(snapshot.get('scope') or 'cards')
    if active_scope not in ('cards', 'worldinfo'):
        active_scope = 'cards'

    if pending_jobs > 0 or worker_state in ('waiting', 'processing'):
        snapshot['state'] = 'building' if pending_jobs > 0 or worker_state == 'processing' else 'idle'
        snapshot['scope'] = active_scope
    else:
        ready_scope = next(
            (
                scope
                for scope in ('cards', 'worldinfo')
                if str(snapshot.get(scope, {}).get('state') or '') == 'ready'
            ),
            active_scope,
        )
        snapshot['scope'] = ready_scope
        snapshot['state'] = str(snapshot.get(ready_scope, {}).get('state') or snapshot['schema']['state'] or 'empty')

    snapshot['pending_jobs'] = pending_jobs
    snapshot['jobs'] = {
        'pending_jobs': pending_jobs,
        'worker_state': worker_state,
    }
    snapshot['progress'] = int(snapshot.get('progress') or 0)
    snapshot['message'] = str(snapshot.get('message') or '')
    return snapshot


def _set_index_state(**updates):
    with ctx.index_lock:
        ctx.index_state.update(updates)


def request_index_rebuild(scope: str = 'cards') -> str:
    if scope not in SUPPORTED_REBUILD_SCOPES:
        raise ValueError(f'unsupported rebuild scope: {scope}')
    enqueue_index_job('rebuild_scope', payload={'scope': scope})
    _set_index_state(state='building', scope=scope, message='queued rebuild')
    return scope


def _get_cards_root() -> str:
    cfg = load_config()
    cards_dir = cfg.get('cards_dir', '')
    if cards_dir and os.path.isabs(cards_dir):
        return cards_dir
    base_dir = os.path.dirname(DEFAULT_DB_PATH)
    if cards_dir:
        return os.path.abspath(os.path.join(base_dir, '..', '..', '..', cards_dir))
    return ''


def _build_card_source_path(card_id: str, source_path: str = '') -> str:
    if source_path:
        return source_path
    cards_root = _get_cards_root()
    if not cards_root:
        return card_id
    return os.path.join(cards_root, card_id.replace('/', os.sep))


def _upsert_card_index_row(conn, row, ui_data, source_path: str = ''):
    card_id = row['id']
    entity_id = f'card::{card_id}'
    tags = json.loads(row['tags'] or '[]') if row['tags'] else []
    summary = str((ui_data.get(card_id) or {}).get('summary', ''))
    source_path = _build_card_source_path(card_id, source_path)
    revision = build_file_source_revision(source_path)

    conn.execute(
        '''
        INSERT OR REPLACE INTO index_entities(
            entity_id, entity_type, source_path, name, filename,
            display_category, physical_category, category_mode,
            favorite, summary_preview, updated_at, token_count,
            sort_name, sort_mtime, source_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            entity_id,
            'card',
            source_path,
            row['char_name'] or '',
            card_id.split('/')[-1],
            row['category'] or '',
            row['category'] or '',
            'physical',
            int(row['is_favorite'] or 0),
            summary,
            float(row['last_modified'] or 0),
            int(row['token_count'] or 0),
            str(row['char_name'] or '').lower(),
            float(row['last_modified'] or 0),
            revision,
        ),
    )

    conn.execute('DELETE FROM index_entity_tags WHERE entity_id = ?', (entity_id,))
    for tag in tags:
        conn.execute(
            'INSERT OR REPLACE INTO index_entity_tags(entity_id, tag) VALUES (?, ?)',
            (entity_id, str(tag).strip()),
        )

    fast_content = ' '.join([
        str(row['char_name'] or ''),
        card_id.split('/')[-1],
        str(row['category'] or ''),
        summary,
        ' '.join(str(tag) for tag in tags),
    ]).strip()
    _upsert_card_search(conn, entity_id, fast_content)


def rebuild_card_index():
    with _connect() as conn:
        conn.execute("DELETE FROM index_entities WHERE entity_type = 'card'")
        conn.execute("DELETE FROM index_entity_tags WHERE entity_id LIKE 'card::%'")
        conn.execute("DELETE FROM index_search_fast WHERE entity_id LIKE 'card::%'")
        conn.execute("DELETE FROM index_search_full WHERE entity_id LIKE 'card::%'")

        ui_data = load_ui_data()
        rows = conn.execute(
            'SELECT id, char_name, tags, category, last_modified, token_count, is_favorite FROM card_metadata'
        ).fetchall()

        for row in rows:
            _upsert_card_index_row(conn, row, ui_data)

        conn.commit()


def rebuild_worldinfo_index():
    cfg = load_config()
    ui_data = load_ui_data()
    global_dir = str(cfg.get('world_info_dir') or '')
    resources_dir = str(cfg.get('resources_dir') or '')

    with _connect() as conn:
        conn.execute("DELETE FROM index_entities WHERE entity_type LIKE 'world_%'")
        conn.execute("DELETE FROM index_search_fast WHERE entity_id LIKE 'world::%'")

        card_rows = conn.execute(
            'SELECT id, char_name, category, has_character_book, character_book_name, last_modified FROM card_metadata'
        ).fetchall()

        if global_dir and os.path.isdir(global_dir):
            for root, _dirs, files in os.walk(global_dir):
                for filename in files:
                    if not filename.lower().endswith('.json'):
                        continue
                    full_path = os.path.join(root, filename)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as handle:
                            data = json.load(handle)
                    except (OSError, json.JSONDecodeError):
                        logger.warning('Skipping invalid worldinfo file during index rebuild: %s', full_path, exc_info=True)
                        continue
                    rel_path = os.path.relpath(full_path, global_dir).replace('\\', '/')
                    display_category = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''
                    name = (data.get('name') or '').strip() or filename
                    entity_id = f'world::global::{rel_path}'
                    summary = _worldinfo_note_summary(ui_data, 'global', file_path=full_path)
                    conn.execute(
                        '''
                        INSERT OR REPLACE INTO index_entities(
                            entity_id, entity_type, source_path, owner_entity_id, name, filename,
                            display_category, physical_category, category_mode, favorite,
                            summary_preview, updated_at, sort_name, sort_mtime, source_revision
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            entity_id,
                            'world_global',
                            full_path,
                            '',
                            name,
                            filename,
                            display_category,
                            display_category,
                            'physical',
                            0,
                            summary,
                            float(os.path.getmtime(full_path)),
                            name.lower(),
                            float(os.path.getmtime(full_path)),
                            build_file_source_revision(full_path),
                        ),
                    )
                    _upsert_worldinfo_search(
                        conn,
                        entity_id,
                        name,
                        filename,
                        display_category,
                        summary,
                    )

        resource_item_categories = ((ui_data.get('_resource_item_categories_v1') or {}).get('worldinfo') or {})
        for row in card_rows:
            card_id = str(row['id'])
            owner_entity_id = f'card::{card_id}'
            resource_folder = str((ui_data.get(card_id) or {}).get('resource_folder', '')).strip()
            if resource_folder:
                lore_dir = os.path.join(resources_dir, resource_folder, 'lorebooks')
                if os.path.isdir(lore_dir):
                    for filename in os.listdir(lore_dir):
                        if not filename.lower().endswith('.json'):
                            continue
                        full_path = os.path.join(lore_dir, filename)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as handle:
                                data = json.load(handle)
                        except (OSError, json.JSONDecodeError):
                            logger.warning('Skipping invalid resource worldinfo file during index rebuild: %s', full_path, exc_info=True)
                            continue
                        path_key = str(full_path).replace('\\', '/').lower()
                        override = (resource_item_categories.get(path_key) or {}).get('category', '')
                        display_category = override or str(row['category'] or '')
                        mode = 'override' if override else 'inherited'
                        name = (data.get('name') or '').strip() or filename
                        entity_id = f'world::resource::{card_id}::{filename}'
                        card_name = str(row['char_name'] or '')
                        summary = _worldinfo_note_summary(ui_data, 'resource', file_path=full_path)
                        conn.execute(
                            '''
                            INSERT OR REPLACE INTO index_entities(
                                entity_id, entity_type, source_path, owner_entity_id, name, filename,
                                display_category, physical_category, category_mode, favorite,
                                summary_preview, updated_at, sort_name, sort_mtime, source_revision
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (
                                entity_id,
                                'world_resource',
                                full_path,
                                owner_entity_id,
                                name,
                                filename,
                                display_category,
                                '',
                                mode,
                                0,
                                summary,
                                float(os.path.getmtime(full_path)),
                                name.lower(),
                                float(os.path.getmtime(full_path)),
                                build_file_source_revision(full_path),
                            ),
                        )
                        _upsert_worldinfo_search(
                            conn,
                            entity_id,
                            name,
                            filename,
                            display_category,
                            summary,
                            card_name,
                        )

            if int(row['has_character_book'] or 0):
                card_path = _build_card_source_path(card_id)
                info = extract_card_info(card_path)
                data_block = info.get('data', {}) if isinstance(info, dict) and 'data' in info else info
                book = data_block.get('character_book') if isinstance(data_block, dict) else None
                if book is not None:
                    name = str(row['character_book_name'] or f"{row['char_name']}'s WI")
                    entity_id = f'world::embedded::{card_id}'
                    summary = _embedded_summary(ui_data, card_id)
                    conn.execute(
                        '''
                        INSERT OR REPLACE INTO index_entities(
                            entity_id, entity_type, source_path, owner_entity_id, name, filename,
                            display_category, physical_category, category_mode, favorite,
                            summary_preview, updated_at, sort_name, sort_mtime, source_revision
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            entity_id,
                            'world_embedded',
                            card_path,
                            owner_entity_id,
                            name,
                            os.path.basename(card_path),
                            str(row['category'] or ''),
                            '',
                            'inherited',
                            0,
                            summary,
                            float(row['last_modified'] or 0),
                            name.lower(),
                            float(row['last_modified'] or 0),
                            build_file_source_revision(card_path),
                        ),
                    )
                    _upsert_worldinfo_search(
                        conn,
                        entity_id,
                        name,
                        os.path.basename(card_path),
                        str(row['category'] or ''),
                        summary,
                        str(row['char_name'] or ''),
                    )

        _rebuild_worldinfo_category_stats(conn, global_dir)

        conn.commit()


def _process_upsert_card(conn, row):
    metadata_row = conn.execute(
        'SELECT id, char_name, tags, category, last_modified, token_count, is_favorite FROM card_metadata WHERE id = ?',
        (row['entity_id'],),
    ).fetchone()
    if metadata_row is None:
        raise ValueError(f'card metadata not found: {row["entity_id"]}')

    ui_data = load_ui_data()
    _upsert_card_index_row(conn, metadata_row, ui_data, source_path=row['source_path'])


def _bootstrap_index():
    cfg = load_config()
    if cfg.get('index_auto_bootstrap', True):
        request_index_rebuild('cards')


def start_index_service():
    threading.Thread(target=_bootstrap_index, daemon=True).start()
    start_index_job_worker()
