import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_remote_backup_frontend_api_exposes_manual_and_restore_calls():
    source = _read('static/js/api/remoteBackups.js')

    assert '/api/remote_backups/start' in source
    assert '/api/remote_backups/list' in source
    assert '/api/remote_backups/restore-preview' in source
    assert '/api/remote_backups/restore' in source
    assert '/api/remote_backups/schedule' in source
    assert '/api/remote_backups/control-key/rotate' in source


def test_remote_backup_panel_is_registered_and_available_from_header():
    app_source = _read('static/js/app.js')
    header_template = _read('templates/components/header.html')
    index_template = _read('templates/index.html')

    assert 'remoteBackupPanel' in app_source
    assert 'open-remote-backup-modal' in header_template
    assert 'modals/remote_backups.html' in index_template


def test_remote_backup_modal_contains_backup_restore_and_schedule_controls():
    template = _read('templates/modals/remote_backups.html')

    assert 'x-data="remoteBackupPanel"' in template
    assert '立即备份' in template
    assert '恢复预览' in template
    assert '恢复到酒馆' in template
    assert '允许覆盖已有文件' in template
    assert '定时备份' in template
    assert 'ST-Manager Control Key' in template
    assert '生成 / 轮换 Key' in template
    assert 'ST-Manager 主动拉取' in template
    assert '酒馆侧主动推送不需要填写这里' in template
