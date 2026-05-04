import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.remote_backup_scheduler import RemoteBackupScheduleStore, RemoteBackupScheduler, prune_remote_backups


def _write_backup_manifest(base_dir, backup_id, created_at, status=None):
    backup_dir = base_dir / backup_id
    backup_dir.mkdir(parents=True)
    manifest = {'backup_id': backup_id, 'created_at': created_at}
    if status:
        manifest['status'] = status
    (backup_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return backup_dir


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


def test_prune_remote_backups_keeps_newest_completed_backups(tmp_path):
    base_dir = tmp_path / 'remote_backups'
    old_backup = _write_backup_manifest(base_dir, 'old', '2026-05-01T08:00:00Z')
    kept_backup = _write_backup_manifest(base_dir, 'kept', '2026-05-01T09:00:00Z')
    newest_backup = _write_backup_manifest(base_dir, 'newest', '2026-05-01T10:00:00Z')

    removed = prune_remote_backups(2, base_dir=base_dir)

    assert removed == [str(old_backup)]
    assert not old_backup.exists()
    assert kept_backup.exists()
    assert newest_backup.exists()


def test_prune_remote_backups_ignores_internal_and_receiving_dirs(tmp_path):
    base_dir = tmp_path / 'remote_backups'
    internal_dir = base_dir / '_incoming_uploads'
    internal_dir.mkdir(parents=True)
    receiving_backup = _write_backup_manifest(base_dir, 'receiving', '2026-05-01T07:00:00Z', status='receiving')
    completed_backup = _write_backup_manifest(base_dir, 'completed', '2026-05-01T08:00:00Z')
    old_backup = _write_backup_manifest(base_dir, 'old', '2026-05-01T06:00:00Z')

    removed = prune_remote_backups(1, base_dir=base_dir)

    assert removed == [str(old_backup)]
    assert internal_dir.exists()
    assert receiving_backup.exists()
    assert completed_backup.exists()
    assert not old_backup.exists()
