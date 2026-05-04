import base64
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.config import SYSTEM_DIR
from core.services.remote_backup_service import (
    REMOTE_BACKUP_RESOURCE_TYPES,
    RemoteBackupError,
    _safe_backup_file,
    normalize_remote_relative_path,
    now_iso,
)
from core.services.remote_backup_storage import read_backup_entry_bytes


UPLOADS_DIRNAME = '_incoming_uploads'
MAX_CHUNK_READ_BYTES = 16 * 1024 * 1024


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_types(values: Optional[Iterable[Any]]) -> List[str]:
    if values is None:
        selected = list(REMOTE_BACKUP_RESOURCE_TYPES)
    elif isinstance(values, (str, bytes)):
        selected = [values]
    else:
        try:
            selected = list(values)
        except TypeError as exc:
            raise RemoteBackupError('resource_types must be a list') from exc
    result = []
    for item in selected:
        resource_type = str(item)
        if resource_type not in REMOTE_BACKUP_RESOURCE_TYPES:
            raise RemoteBackupError(f'unknown resource_type: {resource_type}')
        if resource_type not in result:
            result.append(resource_type)
    return result


def _validate_sha256(value: Any) -> str:
    digest = str(value or '').strip().lower()
    if len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
        raise RemoteBackupError('invalid sha256')
    return digest


class RemoteBackupIncomingService:
    def __init__(self, *, base_dir: Optional[Path] = None, ingest_service=None):
        self.base_dir = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
        self.uploads_dir = self.base_dir / UPLOADS_DIRNAME
        self.ingest_service = ingest_service

    def start_backup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        backup_id = str(payload.get('backup_id') or self._new_backup_id())
        backup_dir = self._backup_dir(backup_id)
        if backup_dir.exists():
            raise RemoteBackupError(f'backup already exists: {backup_id}')

        selected_types = _resource_types(payload.get('resource_types'))
        backup_dir.mkdir(parents=True, exist_ok=False)
        (backup_dir / 'logs.jsonl').touch()
        manifest = {
            'backup_id': backup_id,
            'created_at': now_iso(),
            'description': str(payload.get('description') or ''),
            'st_url': str(payload.get('st_url') or ''),
            'source': str(payload.get('source') or 'authority_control'),
            'resource_types': selected_types,
            'resources': {resource_type: [] for resource_type in selected_types},
            'counts': {resource_type: 0 for resource_type in selected_types},
            'total_files': 0,
            'total_bytes': 0,
            'status': 'receiving',
        }
        self._write_manifest(backup_dir, manifest)
        self._append_log(backup_dir, {'event': 'started', 'resource_types': selected_types})
        return {
            'backup_id': backup_id,
            'backup_dir': str(backup_dir),
            'manifest_path': str(backup_dir / 'manifest.json'),
            'resource_types': selected_types,
        }

    def write_file_init(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        backup_id = str(payload.get('backup_id') or '')
        resource_type = str(payload.get('resource_type') or '')
        if resource_type not in REMOTE_BACKUP_RESOURCE_TYPES:
            raise RemoteBackupError(f'unknown resource_type: {resource_type}')
        backup_dir = self._backup_dir(backup_id)
        manifest = self._load_manifest(backup_dir)
        if resource_type not in manifest.get('resource_types', []):
            raise RemoteBackupError(f'resource_type not enabled for backup: {resource_type}')

        relative_path = normalize_remote_relative_path(
            str(payload.get('relative_path') or payload.get('path') or '')
        )
        size = int(payload.get('size') if payload.get('size') is not None else -1)
        if size < 0:
            raise RemoteBackupError('invalid transfer size')
        digest = _validate_sha256(payload.get('sha256'))
        _safe_backup_file(backup_dir, resource_type, relative_path)

        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        upload_id = uuid.uuid4().hex
        temp_path = self.uploads_dir / f'{upload_id}.tmp'
        temp_path.write_bytes(b'')
        state = {
            'upload_id': upload_id,
            'backup_id': backup_id,
            'resource_type': resource_type,
            'relative_path': relative_path,
            'size': size,
            'sha256': digest,
            'temp_path': str(temp_path),
            'metadata': payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
        }
        self._write_upload_state(upload_id, state)
        return {'upload_id': upload_id, 'offset': 0}

    def write_file_chunk(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        upload_id = str(payload.get('upload_id') or '')
        state = self._load_upload_state(upload_id)
        temp_path = Path(state['temp_path'])
        offset = int(payload.get('offset') if payload.get('offset') is not None else -1)
        current_size = temp_path.stat().st_size if temp_path.exists() else 0
        if offset != current_size:
            raise RemoteBackupError('invalid transfer offset')

        chunk = base64.b64decode(str(payload.get('data_base64') or ''))
        with temp_path.open('ab') as f:
            f.write(chunk)
        next_offset = temp_path.stat().st_size
        if next_offset > int(state['size']):
            raise RemoteBackupError('transfer exceeds declared size')
        return {'upload_id': upload_id, 'offset': next_offset}

    def write_file_commit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        upload_id = str(payload.get('upload_id') or '')
        state = self._load_upload_state(upload_id)
        temp_path = Path(state['temp_path'])
        expected_size = int(state['size'])
        if temp_path.stat().st_size != expected_size:
            raise RemoteBackupError('transfer size mismatch')
        actual_sha256 = _sha256_file(temp_path)
        if actual_sha256 != state['sha256']:
            raise RemoteBackupError('sha256 mismatch')

        backup_dir = self._backup_dir(str(state['backup_id']))
        resource_type = str(state['resource_type'])
        relative_path = str(state['relative_path'])
        target = _safe_backup_file(backup_dir, resource_type, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        reuse_source = self._find_verified_reuse_source(
            str(state['backup_id']),
            resource_type,
            relative_path,
            expected_size,
            actual_sha256,
        )
        reused = reuse_source is not None
        if reused:
            self._materialize_file(reuse_source, target)
            temp_path.unlink(missing_ok=True)
        else:
            temp_path.replace(target)

        manifest = self._load_manifest(backup_dir)
        metadata = state.get('metadata') if isinstance(state.get('metadata'), dict) else {}
        entry = {
            **metadata,
            'relative_path': relative_path,
            'size': expected_size,
            'sha256': actual_sha256,
        }
        self._upsert_manifest_entry(manifest, resource_type, entry)
        dedup = manifest.setdefault('dedup', {})
        dedup['reused_files'] = int(dedup.get('reused_files') or 0) + (1 if reused else 0)
        dedup['uploaded_files'] = int(dedup.get('uploaded_files') or 0) + (0 if reused else 1)
        self._write_manifest(backup_dir, manifest)
        self._append_log(backup_dir, {
            'event': 'reused' if reused else 'uploaded',
            'resource_type': resource_type,
            'relative_path': relative_path,
            'size': expected_size,
        })

        self._upload_state_path(upload_id).unlink(missing_ok=True)
        return {
            'upload_id': upload_id,
            'backup_id': state['backup_id'],
            'resource_type': resource_type,
            'relative_path': relative_path,
            'size': expected_size,
            'sha256': actual_sha256,
            'reused': reused,
        }

    def complete_backup(self, backup_id: str, *, ingest: bool = True) -> Dict[str, Any]:
        backup_dir = self._backup_dir(backup_id)
        manifest = self._load_manifest(backup_dir)
        manifest['status'] = 'completed'
        manifest['completed_at'] = now_iso()
        self._write_manifest(backup_dir, manifest)
        self._append_log(backup_dir, {'event': 'completed'})

        ingest_result = None
        if ingest:
            ingest_result = self._ingest_service().ingest_backup(backup_dir, manifest)

        return {
            'backup_id': manifest['backup_id'],
            'backup_dir': str(backup_dir),
            'manifest_path': str(backup_dir / 'manifest.json'),
            'total_files': manifest.get('total_files', 0),
            'total_bytes': manifest.get('total_bytes', 0),
            'ingest': ingest_result,
        }

    def read_backup_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        backup_id = str(payload.get('backup_id') or '')
        resource_type = str(payload.get('resource_type') or '')
        if resource_type not in REMOTE_BACKUP_RESOURCE_TYPES:
            raise RemoteBackupError(f'unknown resource_type: {resource_type}')
        relative_path = normalize_remote_relative_path(str(payload.get('path') or payload.get('relative_path') or ''))
        backup_dir = self._backup_dir(backup_id)
        data = read_backup_entry_bytes(backup_dir, resource_type, {'relative_path': relative_path})
        offset = max(0, int(payload.get('offset') or 0))
        limit = int(payload.get('limit') or 1024 * 1024)
        limit = max(1, min(limit, MAX_CHUNK_READ_BYTES))
        chunk = data[offset: offset + limit]
        return {
            'backup_id': backup_id,
            'resource_type': resource_type,
            'path': relative_path,
            'offset': offset,
            'bytes_read': len(chunk),
            'size': len(data),
            'sha256': _sha256(data),
            'eof': offset + len(chunk) >= len(data),
            'data_base64': base64.b64encode(chunk).decode('ascii'),
        }

    def _backup_dir(self, backup_id: str) -> Path:
        safe_id = normalize_remote_relative_path(str(backup_id or ''))
        if '/' in safe_id:
            raise RemoteBackupError(f'illegal backup_id: {backup_id}')
        return self.base_dir / safe_id

    def _new_backup_id(self) -> str:
        return f'{now_iso().replace(":", "").replace("-", "").replace(".", "")}-{uuid.uuid4().hex[:8]}'

    def _iter_reuse_candidates(self, current_backup_id: str, resource_type: str, relative_path: str):
        if not self.base_dir.exists():
            return
        for child in self.base_dir.iterdir():
            if not child.is_dir() or child.name == current_backup_id or child.name.startswith('_'):
                continue
            manifest_path = child / 'manifest.json'
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(manifest, dict) or manifest.get('status') == 'receiving':
                continue
            for entry in manifest.get('resources', {}).get(resource_type, []) or []:
                if not isinstance(entry, dict):
                    continue
                try:
                    candidate_path = normalize_remote_relative_path(entry.get('relative_path') or entry.get('path'))
                except RemoteBackupError:
                    continue
                if candidate_path == relative_path:
                    yield child, entry

    def _find_verified_reuse_source(
        self,
        current_backup_id: str,
        resource_type: str,
        relative_path: str,
        expected_size: int,
        expected_sha256: str,
    ) -> Optional[Path]:
        for backup_dir, entry in self._iter_reuse_candidates(current_backup_id, resource_type, relative_path):
            if entry.get('size') != expected_size or entry.get('sha256') != expected_sha256:
                continue
            source = _safe_backup_file(backup_dir, resource_type, relative_path)
            if not source.is_file():
                continue
            try:
                if source.stat().st_size != expected_size:
                    continue
                if _sha256_file(source) != expected_sha256:
                    continue
            except OSError:
                continue
            return source
        return None

    def _materialize_file(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)

    def _manifest_path(self, backup_dir: Path) -> Path:
        return backup_dir / 'manifest.json'

    def _load_manifest(self, backup_dir: Path) -> Dict[str, Any]:
        path = self._manifest_path(backup_dir)
        if not path.exists():
            raise RemoteBackupError(f'backup not found: {backup_dir.name}')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise RemoteBackupError(f'invalid backup manifest: {backup_dir.name}')
        return data

    def _write_manifest(self, backup_dir: Path, manifest: Dict[str, Any]) -> None:
        tmp = backup_dir / 'manifest.json.tmp'
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self._manifest_path(backup_dir))

    def _upsert_manifest_entry(self, manifest: Dict[str, Any], resource_type: str, entry: Dict[str, Any]) -> None:
        resources = manifest.setdefault('resources', {})
        entries = resources.setdefault(resource_type, [])
        if not isinstance(entries, list):
            entries = []
            resources[resource_type] = entries
        entries[:] = [
            item for item in entries
            if not isinstance(item, dict) or item.get('relative_path') != entry['relative_path']
        ]
        entries.append(entry)
        entries.sort(key=lambda item: str(item.get('relative_path') or ''))

        counts = {}
        total_files = 0
        total_bytes = 0
        for current_type, current_entries in resources.items():
            if not isinstance(current_entries, list):
                continue
            counts[current_type] = len(current_entries)
            total_files += len(current_entries)
            total_bytes += sum(int(item.get('size') or 0) for item in current_entries if isinstance(item, dict))
        manifest['counts'] = counts
        manifest['total_files'] = total_files
        manifest['total_bytes'] = total_bytes

    def _append_log(self, backup_dir: Path, event: Dict[str, Any]) -> None:
        payload = {'ts': now_iso(), **event}
        with (backup_dir / 'logs.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + '\n')

    def _upload_state_path(self, upload_id: str) -> Path:
        if not upload_id or '/' in upload_id or '\\' in upload_id:
            raise RemoteBackupError('invalid upload_id')
        return self.uploads_dir / f'{upload_id}.json'

    def _load_upload_state(self, upload_id: str) -> Dict[str, Any]:
        path = self._upload_state_path(upload_id)
        if not path.exists():
            raise RemoteBackupError('upload not found')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise RemoteBackupError('invalid upload state')
        return data

    def _write_upload_state(self, upload_id: str, state: Dict[str, Any]) -> None:
        path = self._upload_state_path(upload_id)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    def _ingest_service(self):
        if self.ingest_service is not None:
            return self.ingest_service
        from core.services.remote_library_ingest_service import RemoteLibraryIngestService

        self.ingest_service = RemoteLibraryIngestService()
        return self.ingest_service
