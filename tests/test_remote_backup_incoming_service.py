import base64
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.remote_backup_incoming_service import RemoteBackupIncomingService


def test_incoming_authority_push_creates_snapshot_and_reads_chunks(tmp_path):
    service = RemoteBackupIncomingService(base_dir=tmp_path / 'remote_backups')
    data = b'card-png-data'
    digest = hashlib.sha256(data).hexdigest()

    started = service.start_backup({
        'backup_id': 'push-001',
        'resource_types': ['characters'],
        'description': 'authority push',
        'source': 'authority_control',
    })
    init = service.write_file_init({
        'backup_id': 'push-001',
        'resource_type': 'characters',
        'relative_path': 'Ava.png',
        'size': len(data),
        'sha256': digest,
        'metadata': {
            'kind': 'file',
            'source': 'root/characters',
            'mtime': 123,
        },
    })

    service.write_file_chunk({
        'upload_id': init['upload_id'],
        'offset': 0,
        'data_base64': base64.b64encode(data[:4]).decode('ascii'),
    })
    service.write_file_chunk({
        'upload_id': init['upload_id'],
        'offset': 4,
        'data_base64': base64.b64encode(data[4:]).decode('ascii'),
    })
    committed = service.write_file_commit({'upload_id': init['upload_id']})
    completed = service.complete_backup('push-001', ingest=False)

    backup_dir = tmp_path / 'remote_backups' / 'push-001'
    manifest = json.loads((backup_dir / 'manifest.json').read_text(encoding='utf-8'))

    assert started['backup_id'] == 'push-001'
    assert committed['relative_path'] == 'Ava.png'
    assert completed['backup_id'] == 'push-001'
    assert manifest['source'] == 'authority_control'
    assert manifest['counts'] == {'characters': 1}
    assert manifest['total_files'] == 1
    assert manifest['resources']['characters'][0]['sha256'] == digest
    assert (backup_dir / 'resources' / 'characters' / 'Ava.png').read_bytes() == data

    first_chunk = service.read_backup_file({
        'backup_id': 'push-001',
        'resource_type': 'characters',
        'path': 'Ava.png',
        'offset': 0,
        'limit': 4,
    })
    assert first_chunk['bytes_read'] == 4
    assert first_chunk['eof'] is False
    assert base64.b64decode(first_chunk['data_base64']) == data[:4]
