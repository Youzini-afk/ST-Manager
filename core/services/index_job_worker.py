import json
import logging
import sqlite3
import threading
import uuid

from core.config import DEFAULT_DB_PATH
from core.context import ctx
from core.data.index_runtime_store import ensure_index_runtime_schema
from core.services.index_upgrade_service import rebuild_scope_generation


logger = logging.getLogger(__name__)

_worker_start_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DEFAULT_DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    ensure_index_runtime_schema(conn)
    return conn


def enqueue_index_job(job_type: str, entity_id: str = '', source_path: str = '', payload: dict | None = None):
    with _connect() as conn:
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, source_path, payload_json) VALUES (?, ?, ?, ?)',
            (job_type, entity_id, source_path, json.dumps(payload or {}, ensure_ascii=False)),
        )
        pending = conn.execute(
            "SELECT COUNT(*) FROM index_jobs WHERE status = 'pending'"
        ).fetchone()[0]
        conn.commit()
    _set_jobs_state(pending_jobs=int(pending))
    ctx.index_wakeup.set()


def _set_jobs_state(**updates):
    with ctx.index_lock:
        ctx.index_state['jobs'].update(updates)
        if 'pending_jobs' in updates:
            ctx.index_state['pending_jobs'] = updates['pending_jobs']


def _claim_pending_jobs(limit: int = 50):
    claim_token = f'claim:{uuid.uuid4().hex}'

    with _connect() as conn:
        rows = conn.execute(
            "SELECT id FROM index_jobs WHERE status = 'pending' ORDER BY id LIMIT ?",
            (int(limit),),
        ).fetchall()
        job_ids = [int(row['id']) for row in rows]
        if job_ids:
            placeholders = ','.join('?' for _ in job_ids)
            conn.execute(
                f"UPDATE index_jobs SET status = ?, started_at = COALESCE(NULLIF(started_at, 0), strftime('%s', 'now')), error_msg = ? WHERE id IN ({placeholders}) AND status = 'pending'",
                ['running', claim_token, *job_ids],
            )
            conn.commit()
            claimed_rows = conn.execute(
                f'SELECT id, job_type, entity_id, source_path, payload_json FROM index_jobs WHERE status = ? AND error_msg = ? AND id IN ({placeholders}) ORDER BY id',
                ['running', claim_token, *job_ids],
            ).fetchall()
        else:
            claimed_rows = []

        pending = conn.execute(
            "SELECT COUNT(*) FROM index_jobs WHERE status = 'pending'"
        ).fetchone()[0]

    return claimed_rows, int(pending)


def worker_loop():
    while True:
        _set_jobs_state(worker_state='waiting')
        ctx.index_wakeup.wait(30)
        ctx.index_wakeup.clear()

        rows, pending = _claim_pending_jobs(50)
        _set_jobs_state(worker_state='processing' if rows else 'idle', pending_jobs=int(pending))

        for row in rows:
            try:
                payload = json.loads(row['payload_json'] or '{}')
                if row['job_type'] == 'rebuild_scope':
                    rebuild_scope_generation(payload.get('scope') or 'cards', reason='manual_rebuild')
                elif row['job_type'] in ('upsert_card', 'upsert_worldinfo_path', 'upsert_world_embedded', 'upsert_world_owner'):
                    scope = 'cards' if row['job_type'] == 'upsert_card' else 'worldinfo'
                    rebuild_scope_generation(scope, reason='incremental_reconcile')
                else:
                    raise ValueError(f"unsupported index job type: {row['job_type']}")

                with _connect() as conn:
                    conn.execute(
                        'UPDATE index_jobs SET status = ?, started_at = COALESCE(NULLIF(started_at, 0), strftime(\'%s\', "now")), finished_at = strftime(\'%s\', "now"), error_msg = ? WHERE id = ?',
                        ('done', '', row['id']),
                    )
                    conn.commit()
            except Exception as exc:
                logger.warning('Index job failed %s', row['id'], exc_info=True)
                with _connect() as conn:
                    conn.execute(
                        'UPDATE index_jobs SET status = ?, started_at = COALESCE(NULLIF(started_at, 0), strftime(\'%s\', "now")), finished_at = strftime(\'%s\', "now"), error_msg = ? WHERE id = ?',
                        ('failed', str(exc), row['id']),
                    )
                    conn.commit()

        if rows:
            with _connect() as conn:
                pending = conn.execute(
                    "SELECT COUNT(*) FROM index_jobs WHERE status = 'pending'"
                ).fetchone()[0]
            _set_jobs_state(worker_state='idle', pending_jobs=int(pending))


def start_index_job_worker():
    with _worker_start_lock:
        if ctx.index_worker_started:
            return
        ctx.index_worker_started = True
        threading.Thread(target=worker_loop, daemon=True).start()
