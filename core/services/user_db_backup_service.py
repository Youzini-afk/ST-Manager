import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from core.config import BASE_DIR, CARDS_FOLDER, DEFAULT_DB_PATH
from core.context import ctx
from core.services.card_index_sync_service import sync_card_index_jobs
from core.services.card_service import _apply_card_index_increment_now as _card_apply_card_index_increment_now
from core.services.wi_entry_history_service import get_history_limit


logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join('data', 'system', 'backups', 'user_db')


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _timestamp_for_file() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _apply_card_index_increment_now(card_id, source_path):
    _card_apply_card_index_increment_now(card_id, source_path)


class UserDbBackupService:
    def export_backup(self):
        file_name = f'user_db_backup_{_timestamp_for_file()}.json'
        relative_path = os.path.join(BACKUP_DIR, file_name).replace('\\', '/')
        full_path = os.path.join(BASE_DIR, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with sqlite3.connect(DEFAULT_DB_PATH, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            favorites = [
                {
                    'card_id': row['id'],
                    'is_favorite': bool(row['is_favorite']),
                }
                for row in conn.execute(
                    'SELECT id, is_favorite FROM card_metadata ORDER BY id ASC'
                ).fetchall()
            ]
            wi_clipboard = [
                {
                    'content': json.loads(row['content_json']),
                    'sort_order': row['sort_order'],
                    'created_at': row['created_at'],
                }
                for row in conn.execute(
                    'SELECT content_json, sort_order, created_at FROM wi_clipboard ORDER BY sort_order ASC, id ASC'
                ).fetchall()
            ]
            wi_entry_history = [
                {
                    'scope_key': row['scope_key'],
                    'entry_uid': row['entry_uid'],
                    'snapshot_json': row['snapshot_json'],
                    'snapshot_hash': row['snapshot_hash'],
                    'created_at': row['created_at'],
                }
                for row in conn.execute(
                    '''
                    SELECT scope_key, entry_uid, snapshot_json, snapshot_hash, created_at
                    FROM wi_entry_history
                    ORDER BY created_at ASC, id ASC
                    '''
                ).fetchall()
            ]

        payload = {
            'schema_version': 1,
            'exported_at': _utc_now_iso(),
            'app': 'ST-Manager',
            'data': {
                'favorites': favorites,
                'wi_clipboard': wi_clipboard,
                'wi_entry_history': wi_entry_history,
            },
        }
        with open(full_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

        return {
            'file_name': file_name,
            'file_path': relative_path,
            'stats': {
                'favorites': len(favorites),
                'wi_clipboard': len(wi_clipboard),
                'wi_entry_history': len(wi_entry_history),
            },
        }

    def import_backup(self, source_path, source_name=''):
        payload = self._load_backup_payload(source_path)
        data = payload.get('data') or {}
        favorites = self._validate_favorites(data.get('favorites'))
        wi_clipboard = self._validate_clipboard(data.get('wi_clipboard'))
        wi_entry_history = self._validate_history(data.get('wi_entry_history'))

        favorite_changes = []
        rollback_snapshot = self._snapshot_db_only_state()
        stats = {
            'favorites': {
                'imported': 0,
                'skipped_missing_cards': 0,
                'unchanged': 0,
            },
            'wi_clipboard': {
                'imported': 0,
                'deduplicated': 0,
            },
            'wi_entry_history': {
                'imported': 0,
                'deduplicated': 0,
                'trimmed': 0,
            },
        }

        with sqlite3.connect(DEFAULT_DB_PATH, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('BEGIN')

            for item in favorites:
                row = cursor.execute(
                    'SELECT is_favorite FROM card_metadata WHERE id = ?',
                    (item['card_id'],),
                ).fetchone()
                if row is None:
                    stats['favorites']['skipped_missing_cards'] += 1
                    continue
                new_value = 1 if item['is_favorite'] else 0
                old_value = 1 if row['is_favorite'] else 0
                if old_value == new_value:
                    stats['favorites']['unchanged'] += 1
                    continue
                cursor.execute(
                    'UPDATE card_metadata SET is_favorite = ? WHERE id = ?',
                    (new_value, item['card_id']),
                )
                favorite_changes.append(
                    {
                        'card_id': item['card_id'],
                        'old_value': bool(old_value),
                        'new_value': bool(new_value),
                    }
                )
                stats['favorites']['imported'] += 1

            existing_clipboard = set()
            for row in cursor.execute('SELECT content_json FROM wi_clipboard').fetchall():
                try:
                    existing_clipboard.add(_stable_json(json.loads(row['content_json'])))
                except (TypeError, ValueError, json.JSONDecodeError):
                    existing_clipboard.add(str(row['content_json']))
            next_sort_order_row = cursor.execute(
                'SELECT COALESCE(MAX(sort_order), -1) AS max_sort_order FROM wi_clipboard'
            ).fetchone()
            next_sort_order = int(next_sort_order_row['max_sort_order']) + 1
            for item in wi_clipboard:
                content_key = _stable_json(item['content'])
                if content_key in existing_clipboard:
                    stats['wi_clipboard']['deduplicated'] += 1
                    continue
                content_json = json.dumps(item['content'], ensure_ascii=False)
                cursor.execute(
                    'INSERT INTO wi_clipboard (content_json, sort_order, created_at) VALUES (?, ?, ?)',
                    (content_json, next_sort_order, item['created_at']),
                )
                existing_clipboard.add(content_key)
                stats['wi_clipboard']['imported'] += 1
                next_sort_order += 1

            clipboard_rows = cursor.execute(
                'SELECT id FROM wi_clipboard ORDER BY sort_order ASC, id ASC'
            ).fetchall()
            for index, row in enumerate(clipboard_rows):
                cursor.execute(
                    'UPDATE wi_clipboard SET sort_order = ? WHERE id = ?',
                    (index, row['id']),
                )

            existing_history = {
                (row['scope_key'], row['entry_uid'], row['snapshot_hash'])
                for row in cursor.execute(
                    'SELECT scope_key, entry_uid, snapshot_hash FROM wi_entry_history'
                ).fetchall()
            }
            for item in wi_entry_history:
                key = (item['scope_key'], item['entry_uid'], item['snapshot_hash'])
                if key in existing_history:
                    stats['wi_entry_history']['deduplicated'] += 1
                    continue
                cursor.execute(
                    '''
                    INSERT INTO wi_entry_history (scope_key, entry_uid, snapshot_json, snapshot_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        item['scope_key'],
                        item['entry_uid'],
                        item['snapshot_json'],
                        item['snapshot_hash'],
                        item['created_at'],
                    ),
                )
                existing_history.add(key)
                stats['wi_entry_history']['imported'] += 1

            history_limit = get_history_limit()
            history_groups = cursor.execute(
                '''
                SELECT scope_key, entry_uid
                FROM wi_entry_history
                GROUP BY scope_key, entry_uid
                '''
            ).fetchall()
            for group in history_groups:
                overflow = cursor.execute(
                    '''
                    SELECT id
                    FROM wi_entry_history
                    WHERE scope_key = ? AND entry_uid = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT -1 OFFSET ?
                    ''',
                    (group['scope_key'], group['entry_uid'], history_limit),
                ).fetchall()
                if not overflow:
                    continue
                stats['wi_entry_history']['trimmed'] += len(overflow)
                cursor.executemany(
                    'DELETE FROM wi_entry_history WHERE id = ?',
                    [(row['id'],) for row in overflow],
                )

            conn.commit()

        applied_favorite_changes = []
        try:
            for change in favorite_changes:
                card_id = change['card_id']
                source_file_path = self._resolve_card_source_path(card_id)
                change['source_path'] = source_file_path
                applied_favorite_changes.append(change)
                if ctx.cache:
                    ctx.cache.toggle_favorite_update(card_id, change['new_value'])
                sync_card_index_jobs(
                    card_id=card_id,
                    source_path=source_file_path,
                    favorite_changed=True,
                )
                _apply_card_index_increment_now(card_id, source_file_path)
        except Exception:
            self._restore_db_only_state(rollback_snapshot)
            self._restore_favorite_changes(favorite_changes, applied_favorite_changes)
            raise

        return {
            'source_name': source_name,
            'stats': stats,
        }

    def _load_backup_payload(self, source_path):
        try:
            with open(source_path, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError('备份文件必须是合法 JSON') from exc

        if not isinstance(payload, dict):
            raise ValueError('备份文件必须是合法 JSON 对象')

        if payload.get('schema_version') != 1:
            raise ValueError('不支持的 schema_version')

        data = payload.get('data')
        if not isinstance(data, dict):
            raise ValueError('data 字段格式无效')
        return payload

    def _validate_favorites(self, items):
        if not isinstance(items, list):
            raise ValueError('favorites 必须是数组')
        validated = []
        for item in items:
            if not isinstance(item, dict) or 'card_id' not in item or 'is_favorite' not in item:
                raise ValueError('favorites 缺少必填字段')
            if not isinstance(item['is_favorite'], bool):
                raise ValueError('favorites.is_favorite 必须是布尔值')
            validated.append(
                {
                    'card_id': str(item['card_id']).strip(),
                    'is_favorite': item['is_favorite'],
                }
            )
        return validated

    def _validate_clipboard(self, items):
        if not isinstance(items, list):
            raise ValueError('wi_clipboard 必须是数组')
        validated = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('wi_clipboard 缺少必填字段')
            required = {'content', 'sort_order', 'created_at'}
            if not required.issubset(item.keys()):
                raise ValueError('wi_clipboard 缺少必填字段')
            validated.append(
                {
                    'content': item['content'],
                    'sort_order': int(item['sort_order']),
                    'created_at': float(item['created_at']),
                }
            )
        return validated

    def _validate_history(self, items):
        if not isinstance(items, list):
            raise ValueError('wi_entry_history 必须是数组')
        validated = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('wi_entry_history 缺少必填字段')
            required = {'scope_key', 'entry_uid', 'snapshot_json', 'snapshot_hash', 'created_at'}
            if not required.issubset(item.keys()):
                raise ValueError('wi_entry_history 缺少必填字段')
            validated.append(
                {
                    'scope_key': str(item['scope_key']),
                    'entry_uid': str(item['entry_uid']),
                    'snapshot_json': str(item['snapshot_json']),
                    'snapshot_hash': str(item['snapshot_hash']),
                    'created_at': float(item['created_at']),
                }
            )
        return validated

    def _resolve_card_source_path(self, card_id):
        return os.path.join(CARDS_FOLDER, str(card_id or '').replace('/', os.sep))

    def _snapshot_db_only_state(self):
        snapshot = {
            'favorites': [],
            'wi_clipboard': [],
            'wi_entry_history': [],
        }

        with sqlite3.connect(DEFAULT_DB_PATH, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            snapshot['favorites'] = [
                {
                    'card_id': row['id'],
                    'is_favorite': 1 if row['is_favorite'] else 0,
                }
                for row in conn.execute('SELECT id, is_favorite FROM card_metadata ORDER BY id ASC').fetchall()
            ]
            snapshot['wi_clipboard'] = [
                {
                    'content_json': row['content_json'],
                    'sort_order': row['sort_order'],
                    'created_at': row['created_at'],
                }
                for row in conn.execute(
                    'SELECT content_json, sort_order, created_at FROM wi_clipboard ORDER BY sort_order ASC, id ASC'
                ).fetchall()
            ]
            snapshot['wi_entry_history'] = [
                {
                    'scope_key': row['scope_key'],
                    'entry_uid': row['entry_uid'],
                    'snapshot_json': row['snapshot_json'],
                    'snapshot_hash': row['snapshot_hash'],
                    'created_at': row['created_at'],
                }
                for row in conn.execute(
                    '''
                    SELECT scope_key, entry_uid, snapshot_json, snapshot_hash, created_at
                    FROM wi_entry_history
                    ORDER BY created_at ASC, id ASC
                    '''
                ).fetchall()
            ]

        return snapshot

    def _restore_db_only_state(self, snapshot):
        if not snapshot:
            return

        with sqlite3.connect(DEFAULT_DB_PATH, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute('BEGIN')

            cursor.execute('DELETE FROM wi_clipboard')
            cursor.execute('DELETE FROM wi_entry_history')
            for favorite in snapshot.get('favorites', []):
                cursor.execute(
                    'UPDATE card_metadata SET is_favorite = ? WHERE id = ?',
                    (favorite['is_favorite'], favorite['card_id']),
                )
            for row in snapshot.get('wi_clipboard', []):
                cursor.execute(
                    'INSERT INTO wi_clipboard (content_json, sort_order, created_at) VALUES (?, ?, ?)',
                    (row['content_json'], row['sort_order'], row['created_at']),
                )
            for row in snapshot.get('wi_entry_history', []):
                cursor.execute(
                    '''
                    INSERT INTO wi_entry_history (scope_key, entry_uid, snapshot_json, snapshot_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        row['scope_key'],
                        row['entry_uid'],
                        row['snapshot_json'],
                        row['snapshot_hash'],
                        row['created_at'],
                    ),
                )

            conn.commit()

    def _restore_favorite_changes(self, favorite_changes, applied_favorite_changes):
        if not favorite_changes:
            return

        with sqlite3.connect(DEFAULT_DB_PATH, timeout=30) as conn:
            cursor = conn.cursor()
            for change in favorite_changes:
                cursor.execute(
                    'UPDATE card_metadata SET is_favorite = ? WHERE id = ?',
                    (1 if change['old_value'] else 0, change['card_id']),
                )
            conn.commit()

        for change in favorite_changes:
            if ctx.cache:
                try:
                    ctx.cache.toggle_favorite_update(change['card_id'], change['old_value'])
                except Exception:
                    logger.warning('Restore favorite cache state failed for %s', change['card_id'])

        for change in reversed(applied_favorite_changes):
            try:
                sync_card_index_jobs(
                    card_id=change['card_id'],
                    source_path=change.get('source_path', ''),
                    favorite_changed=True,
                )
                _apply_card_index_increment_now(change['card_id'], change.get('source_path', ''))
            except Exception:
                logger.warning('Restore favorite index state failed for %s', change['card_id'])
