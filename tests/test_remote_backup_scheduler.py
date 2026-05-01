import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.remote_backup_scheduler import RemoteBackupScheduleStore, RemoteBackupScheduler


def test_schedule_store_normalizes_values_and_computes_next_run(tmp_path):
    store = RemoteBackupScheduleStore(base_dir=tmp_path / 'remote_backups')
    now = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)

    saved = store.save({
        'enabled': True,
        'interval_minutes': 45,
        'retention_limit': 2,
        'resource_types': ['characters', 'worlds', 'bad'],
    }, now=now)

    assert saved['enabled'] is True
    assert saved['interval_minutes'] == 45
    assert saved['retention_limit'] == 2
    assert saved['resource_types'] == ['characters', 'worlds']
    assert saved['next_run_at'] == '2026-05-01T10:45:00Z'


def test_scheduler_runs_due_backup_once_and_advances_schedule(tmp_path):
    calls = []
    now = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    store = RemoteBackupScheduleStore(base_dir=tmp_path / 'remote_backups')
    store.save({
        'enabled': True,
        'interval_minutes': 10,
        'resource_types': ['characters'],
        'next_run_at': (now - timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
    }, now=now)

    class FakeBackupService:
        def create_backup(self, **kwargs):
            calls.append(kwargs)
            return {'backup_id': 'scheduled-001', 'total_files': 1}

    scheduler = RemoteBackupScheduler(
        schedule_store=store,
        backup_service_factory=lambda: FakeBackupService(),
        retention_callback=lambda _limit: None,
    )

    result = scheduler.run_due_once(now=now)
    schedule = store.load()

    assert result['backup_id'] == 'scheduled-001'
    assert calls == [{'resource_types': ['characters'], 'description': 'scheduled remote backup'}]
    assert schedule['last_run_at'] == '2026-05-01T10:00:00Z'
    assert schedule['next_run_at'] == '2026-05-01T10:10:00Z'
