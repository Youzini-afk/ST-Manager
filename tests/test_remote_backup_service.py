import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.remote_backup_service import RemoteBackupError, RemoteBackupService


class FakeRemoteClient:
    def __init__(self):
        self.downloads = []
        self.uploads = []
        self.manifests = {
            'characters': {
                'files': [
                    {
                        'relative_path': 'Ava.png',
                        'kind': 'character_card',
                        'size': 7,
                        'sha256': hashlib.sha256(b'pngdata').hexdigest(),
                    }
                ]
            },
            'worlds': {
                'files': [
                    {
                        'relative_path': 'folder/world_info.json',
                        'kind': 'world_info',
                        'size': 13,
                        'sha256': hashlib.sha256(b'{"entries":{}}').hexdigest(),
                    }
                ]
            },
            'regex': {
                'files': [
                    {
                        'relative_path': 'settings.regex.json',
                        'kind': 'settings_regex_bundle',
                        'size': 72,
                        'sha256': hashlib.sha256(
                            b'{"extension_settings":{"regex":[{"scriptName":"Global","findRegex":"x"}]}}'
                        ).hexdigest(),
                    }
                ]
            },
        }
        self.data = {
            ('characters', 'Ava.png'): b'pngdata',
            ('worlds', 'folder/world_info.json'): b'{"entries":{}}',
            ('regex', 'settings.regex.json'): (
                b'{"extension_settings":{"regex":[{"scriptName":"Global","findRegex":"x"}]}}'
            ),
        }

    def manifest(self, resource_type):
        return self.manifests.get(resource_type, {'files': []})

    def download_file(self, resource_type, path, expected_sha256=None):
        self.downloads.append((resource_type, path, expected_sha256))
        return self.data[(resource_type, path)]

    def upload_file(self, resource_type, path, data, overwrite_mode='skip_existing'):
        self.uploads.append((resource_type, path, data, overwrite_mode))
        return {'success': True, 'path': path}


def _config(tmp_path):
    return {
        'st_url': 'http://st.example',
        'remote_bridge_key': 'secret',
        'cards_dir': str(tmp_path / 'library' / 'characters'),
        'world_info_dir': str(tmp_path / 'library' / 'lorebooks'),
        'chats_dir': str(tmp_path / 'library' / 'chats'),
        'presets_dir': str(tmp_path / 'library' / 'presets'),
        'regex_dir': str(tmp_path / 'library' / 'regex'),
        'quick_replies_dir': str(tmp_path / 'library' / 'quick-replies'),
    }


def test_backup_writes_immutable_snapshot_and_ingests_to_library(tmp_path, monkeypatch):
    remote = FakeRemoteClient()
    scan_reasons = []
    wi_invalidations = []
    monkeypatch.setattr(
        'core.services.remote_library_ingest_service.request_scan',
        lambda reason='remote_backup': scan_reasons.append(reason),
    )
    monkeypatch.setattr(
        'core.services.remote_library_ingest_service.invalidate_wi_list_cache',
        lambda: wi_invalidations.append(True),
    )

    service = RemoteBackupService(
        base_dir=tmp_path / 'system' / 'remote_backups',
        config=_config(tmp_path),
        remote_client_factory=lambda _config, _bridge_key: remote,
    )

    result = service.create_backup(
        resource_types=['characters', 'worlds', 'regex'],
        backup_id='backup-001',
    )

    backup_dir = tmp_path / 'system' / 'remote_backups' / 'backup-001'
    manifest = json.loads((backup_dir / 'manifest.json').read_text(encoding='utf-8'))

    assert result['backup_id'] == 'backup-001'
    assert manifest['resources']['worlds'][0]['relative_path'] == 'folder/world_info.json'
    assert (backup_dir / 'resources' / 'characters' / 'Ava.png').read_bytes() == b'pngdata'
    assert (backup_dir / 'resources' / 'worlds' / 'folder' / 'world_info.json').read_bytes() == b'{"entries":{}}'
    assert (backup_dir / 'logs.jsonl').read_text(encoding='utf-8').strip()
    assert (tmp_path / 'library' / 'characters' / 'Ava.png').read_bytes() == b'pngdata'
    assert (tmp_path / 'library' / 'lorebooks' / 'folder' / 'world_info.json').read_bytes() == b'{"entries":{}}'
    assert (tmp_path / 'library' / 'regex' / 'global__Global.json').exists()
    assert scan_reasons == ['remote_backup']
    assert wi_invalidations == [True]


def test_backup_rejects_illegal_remote_relative_path(tmp_path):
    remote = FakeRemoteClient()
    remote.manifests['characters'] = {
        'files': [
            {
                'relative_path': '../escape.png',
                'size': 4,
                'sha256': hashlib.sha256(b'evil').hexdigest(),
            }
        ]
    }
    service = RemoteBackupService(
        base_dir=tmp_path / 'system' / 'remote_backups',
        config=_config(tmp_path),
        remote_client_factory=lambda _config, _bridge_key: remote,
    )

    with pytest.raises(RemoteBackupError, match='illegal relative_path'):
        service.create_backup(resource_types=['characters'], backup_id='backup-escape')


def test_authority_bridge_mode_requires_bridge_key(tmp_path):
    class FakeProbeClient:
        def probe(self):
            return {'success': True}

    service = RemoteBackupService(
        base_dir=tmp_path / 'system' / 'remote_backups',
        config={**_config(tmp_path), 'remote_connection_mode': 'authority_bridge', 'remote_bridge_key': ''},
        remote_client_factory=lambda _config, _bridge_key: FakeProbeClient(),
    )

    with pytest.raises(RemoteBackupError, match='Bridge Key is required'):
        service.probe()


def test_restore_skips_existing_remote_files_by_default_and_overwrites_explicitly(tmp_path):
    remote = FakeRemoteClient()
    service = RemoteBackupService(
        base_dir=tmp_path / 'system' / 'remote_backups',
        config=_config(tmp_path),
        remote_client_factory=lambda _config, _bridge_key: remote,
    )
    service.create_backup(resource_types=['characters'], backup_id='backup-restore', ingest=False)

    skipped = service.restore_backup('backup-restore')
    overwritten = service.restore_backup('backup-restore', overwrite=True)

    assert skipped['skipped'] == 1
    assert skipped['uploaded'] == 0
    assert overwritten['uploaded'] == 1
    assert remote.uploads == [
        ('characters', 'Ava.png', b'pngdata', 'overwrite'),
    ]
