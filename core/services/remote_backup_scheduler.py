import json
import logging
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from core.config import SYSTEM_DIR
from core.services.remote_backup_service import REMOTE_BACKUP_RESOURCE_TYPES, RemoteBackupService


logger = logging.getLogger(__name__)

SCHEDULE_FILENAME = 'schedule.json'

_SCHEDULER_THREAD = None
_SCHEDULER_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = str(value).replace('Z', '+00:00')
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resource_types(values: Optional[Iterable[str]] = None):
    if not values:
        return list(REMOTE_BACKUP_RESOURCE_TYPES)
    result = []
    for item in values:
        value = str(item)
        if value in REMOTE_BACKUP_RESOURCE_TYPES and value not in result:
            result.append(value)
    return result or list(REMOTE_BACKUP_RESOURCE_TYPES)


def _normalize_interval(value: Any) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = 1440
    return max(1, min(interval, 60 * 24 * 30))


def _normalize_retention(value: Any) -> int:
    try:
        retention = int(value)
    except (TypeError, ValueError):
        retention = 10
    return max(1, min(retention, 500))


class RemoteBackupScheduleStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
        self.path = self.base_dir / SCHEDULE_FILENAME

    def defaults(self) -> Dict[str, Any]:
        return {
            'enabled': False,
            'interval_minutes': 1440,
            'retention_limit': 10,
            'resource_types': list(REMOTE_BACKUP_RESOURCE_TYPES),
            'last_run_at': '',
            'next_run_at': '',
        }

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.defaults()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
        return self._normalize(data if isinstance(data, dict) else {})

    def save(self, payload: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
        current = self.load()
        merged = {**current, **(payload or {})}
        normalized = self._normalize(merged, now=now or _now(), prefer_payload_next='next_run_at' in (payload or {}))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
        return normalized

    def mark_run(self, *, now: Optional[datetime] = None) -> Dict[str, Any]:
        current = self.load()
        current['last_run_at'] = _format_dt(now or _now())
        current['next_run_at'] = _format_dt((now or _now()) + timedelta(minutes=current['interval_minutes']))
        return self.save(current, now=now or _now())

    def _normalize(self, data: Dict[str, Any], *, now: Optional[datetime] = None, prefer_payload_next: bool = True) -> Dict[str, Any]:
        base = self.defaults()
        base.update(data)
        interval = _normalize_interval(base.get('interval_minutes'))
        next_dt = _parse_dt(base.get('next_run_at')) if prefer_payload_next else None
        if bool(base.get('enabled')) and next_dt is None:
            next_dt = (now or _now()) + timedelta(minutes=interval)
        return {
            'enabled': bool(base.get('enabled')),
            'interval_minutes': interval,
            'retention_limit': _normalize_retention(base.get('retention_limit')),
            'resource_types': _resource_types(base.get('resource_types')),
            'last_run_at': _format_dt(_parse_dt(base.get('last_run_at'))) if _parse_dt(base.get('last_run_at')) else '',
            'next_run_at': _format_dt(next_dt) if next_dt else '',
        }


class RemoteBackupScheduler:
    def __init__(
        self,
        *,
        schedule_store: Optional[RemoteBackupScheduleStore] = None,
        backup_service_factory=None,
        retention_callback=None,
    ):
        self.schedule_store = schedule_store or RemoteBackupScheduleStore()
        self.backup_service_factory = backup_service_factory or RemoteBackupService
        self.retention_callback = retention_callback or prune_remote_backups

    def run_due_once(self, *, now: Optional[datetime] = None):
        now = now or _now()
        schedule = self.schedule_store.load()
        if not schedule.get('enabled'):
            return None
        next_run = _parse_dt(schedule.get('next_run_at'))
        if next_run and now < next_run:
            return None

        service = self.backup_service_factory()
        result = service.create_backup(
            resource_types=schedule.get('resource_types'),
            description='scheduled remote backup',
        )
        self.schedule_store.mark_run(now=now)
        self.retention_callback(schedule.get('retention_limit', 10))
        return result

    def serve_forever(self, *, sleep_seconds: int = 30):
        while True:
            try:
                self.run_due_once()
            except Exception as exc:
                logger.exception('Scheduled remote backup failed: %s', exc)
            time.sleep(sleep_seconds)


def prune_remote_backups(retention_limit: int, *, base_dir: Optional[Path] = None):
    base = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
    if not base.exists():
        return []
    backups = []
    for child in base.iterdir():
        if child.is_dir() and (child / 'manifest.json').exists():
            try:
                manifest = json.loads((child / 'manifest.json').read_text(encoding='utf-8'))
            except Exception:
                manifest = {}
            backups.append((manifest.get('created_at', ''), child))
    backups.sort(key=lambda item: item[0], reverse=True)
    removed = []
    for _created_at, path in backups[max(1, int(retention_limit)):]:
        shutil.rmtree(path, ignore_errors=True)
        removed.append(str(path))
    return removed


def start_remote_backup_scheduler():
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            return _SCHEDULER_THREAD
        scheduler = RemoteBackupScheduler()
        _SCHEDULER_THREAD = threading.Thread(target=scheduler.serve_forever, name='remote-backup-scheduler', daemon=True)
        _SCHEDULER_THREAD.start()
        return _SCHEDULER_THREAD
