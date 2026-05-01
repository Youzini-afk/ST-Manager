import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

from core.config import SYSTEM_DIR, load_config
from core.services.remote_st_bridge_client import RemoteSTBridgeClient


REMOTE_BACKUP_RESOURCE_TYPES = [
    'characters',
    'chats',
    'worlds',
    'presets',
    'regex',
    'quick_replies',
]

REMOTE_CONFIG_FILENAME = 'config.json'
VALID_REMOTE_CONNECTION_MODES = {'authority_bridge', 'st_auth'}


class RemoteBackupError(Exception):
    """Raised for unsafe remote backup manifests or failed backup operations."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def normalize_remote_connection_mode(value: Any) -> str:
    return value if value in VALID_REMOTE_CONNECTION_MODES else 'authority_bridge'


def normalize_remote_relative_path(path: str) -> str:
    if not isinstance(path, str):
        raise RemoteBackupError('illegal relative_path: expected string')
    raw = path.strip()
    if not raw:
        raise RemoteBackupError('illegal relative_path: empty')
    if '\\' in raw:
        raise RemoteBackupError(f'illegal relative_path: {path}')
    if raw.startswith('/'):
        raise RemoteBackupError(f'illegal relative_path: {path}')
    if re.match(r'^[A-Za-z]:', raw):
        raise RemoteBackupError(f'illegal relative_path: {path}')

    posix_path = PurePosixPath(raw)
    parts = posix_path.parts
    if not parts or any(part in ('', '.', '..') for part in parts):
        raise RemoteBackupError(f'illegal relative_path: {path}')
    normalized = '/'.join(parts)
    if normalized.startswith('../') or normalized == '..':
        raise RemoteBackupError(f'illegal relative_path: {path}')
    return normalized


def _safe_backup_file(root: Path, resource_type: str, relative_path: str) -> Path:
    normalized = normalize_remote_relative_path(relative_path)
    target = root / 'resources' / resource_type / Path(*normalized.split('/'))
    base = (root / 'resources' / resource_type).resolve()
    resolved = target.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise RemoteBackupError(f'illegal relative_path: {relative_path}') from exc
    return target


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entries_from_manifest(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    entries = payload.get('files')
    if entries is None:
        entries = payload.get('items')
    return entries if isinstance(entries, list) else []


class RemoteBackupConfigStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
        self.path = self.base_dir / REMOTE_CONFIG_FILENAME

    def load_private(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open('r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load_private()
        next_config = dict(current)
        for key in [
            'st_url',
            'remote_connection_mode',
            'st_auth_type',
            'st_basic_username',
            'st_basic_password',
            'st_web_username',
            'st_web_password',
            'st_proxy',
            'remote_bridge_key',
            'enabled_resource_types',
            'chunk_size',
        ]:
            if key in payload:
                next_config[key] = payload[key]
        next_config['remote_connection_mode'] = normalize_remote_connection_mode(
            next_config.get('remote_connection_mode')
        )
        if 'bridge_key' in payload:
            next_config['remote_bridge_key'] = payload['bridge_key']

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open('w', encoding='utf-8') as f:
            json.dump(next_config, f, ensure_ascii=False, indent=2)
        return self.public(next_config)

    def public(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = dict(config if config is not None else self.load_private())
        key = config.pop('remote_bridge_key', '') or config.pop('bridge_key', '')
        config['remote_connection_mode'] = normalize_remote_connection_mode(config.get('remote_connection_mode'))
        config['bridge_key_masked'] = self._mask_key(key)
        config['bridge_key_fingerprint'] = hashlib.sha256(key.encode('utf-8')).hexdigest()[:12] if key else ''
        return config

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key:
            return ''
        if len(key) <= 8:
            return '****'
        return f'{key[:4]}...{key[-4:]}'


class RemoteBackupService:
    def __init__(
        self,
        *,
        base_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
        remote_client_factory=None,
        ingest_service=None,
    ):
        self.base_dir = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
        if config is None:
            merged_config = dict(load_config())
            merged_config.update(RemoteBackupConfigStore(self.base_dir).load_private())
            self.config = merged_config
        else:
            self.config = config
        self.remote_client_factory = remote_client_factory
        self.ingest_service = ingest_service

    def _backup_dir(self, backup_id: str) -> Path:
        safe_id = normalize_remote_relative_path(backup_id)
        if '/' in safe_id:
            raise RemoteBackupError(f'illegal backup_id: {backup_id}')
        return self.base_dir / safe_id

    def _new_backup_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        return f'{stamp}-{uuid.uuid4().hex[:8]}'

    def _create_client(self):
        mode = normalize_remote_connection_mode(self.config.get('remote_connection_mode'))
        bridge_key = self.config.get('remote_bridge_key') or self.config.get('bridge_key') or ''
        if mode == 'authority_bridge' and not bridge_key:
            raise RemoteBackupError('Bridge Key is required for Authority Bridge mode')
        if self.remote_client_factory:
            return self.remote_client_factory(self.config, bridge_key)
        return RemoteSTBridgeClient(self.config, bridge_key=bridge_key)

    def probe(self) -> Dict[str, Any]:
        return self._create_client().probe()

    def _resource_types(self, requested: Optional[Iterable[str]]) -> List[str]:
        if requested:
            values = [str(item) for item in requested]
        else:
            values = self.config.get('enabled_resource_types') or REMOTE_BACKUP_RESOURCE_TYPES
        result = []
        for resource_type in values:
            if resource_type not in REMOTE_BACKUP_RESOURCE_TYPES:
                raise RemoteBackupError(f'unknown resource_type: {resource_type}')
            if resource_type not in result:
                result.append(resource_type)
        return result

    def _append_log(self, logs_path: Path, event: Dict[str, Any]):
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'ts': now_iso(), **event}
        with logs_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + '\n')

    def create_backup(
        self,
        *,
        resource_types: Optional[Iterable[str]] = None,
        backup_id: Optional[str] = None,
        description: str = '',
        ingest: bool = True,
    ) -> Dict[str, Any]:
        selected_types = self._resource_types(resource_types)
        backup_id = backup_id or self._new_backup_id()
        backup_dir = self._backup_dir(backup_id)
        if backup_dir.exists():
            raise RemoteBackupError(f'backup already exists: {backup_id}')
        backup_dir.mkdir(parents=True, exist_ok=False)
        logs_path = backup_dir / 'logs.jsonl'
        logs_path.touch()
        client = self._create_client()

        manifest = {
            'backup_id': backup_id,
            'created_at': now_iso(),
            'description': description,
            'st_url': self.config.get('st_url', ''),
            'resource_types': selected_types,
            'resources': {},
            'counts': {},
        }

        total_files = 0
        total_bytes = 0
        for resource_type in selected_types:
            remote_manifest = client.manifest(resource_type)
            entries = []
            for entry in _entries_from_manifest(remote_manifest):
                relative_path = normalize_remote_relative_path(entry.get('relative_path') or entry.get('path'))
                expected_sha256 = entry.get('sha256')
                data = client.download_file(resource_type, relative_path, expected_sha256=expected_sha256)
                actual_sha256 = _sha256(data)
                if expected_sha256 and actual_sha256 != expected_sha256:
                    raise RemoteBackupError(
                        f'sha256 mismatch for {resource_type}/{relative_path}: expected {expected_sha256}, got {actual_sha256}'
                    )

                target = _safe_backup_file(backup_dir, resource_type, relative_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

                saved_entry = dict(entry)
                saved_entry['relative_path'] = relative_path
                saved_entry['size'] = len(data)
                saved_entry['sha256'] = actual_sha256
                entries.append(saved_entry)
                total_files += 1
                total_bytes += len(data)
                self._append_log(
                    logs_path,
                    {
                        'event': 'downloaded',
                        'resource_type': resource_type,
                        'relative_path': relative_path,
                        'size': len(data),
                    },
                )

            manifest['resources'][resource_type] = entries
            manifest['counts'][resource_type] = len(entries)

        manifest['total_files'] = total_files
        manifest['total_bytes'] = total_bytes
        manifest_path = backup_dir / 'manifest.json'
        with manifest_path.open('w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        ingest_result = None
        if ingest:
            ingest_result = self._ingest_service().ingest_backup(backup_dir, manifest)

        return {
            'backup_id': backup_id,
            'backup_dir': str(backup_dir),
            'manifest_path': str(manifest_path),
            'total_files': total_files,
            'total_bytes': total_bytes,
            'ingest': ingest_result,
        }

    def _ingest_service(self):
        if self.ingest_service is not None:
            return self.ingest_service
        from core.services.remote_library_ingest_service import RemoteLibraryIngestService

        self.ingest_service = RemoteLibraryIngestService(self.config)
        return self.ingest_service

    def _load_manifest(self, backup_id: str) -> Dict[str, Any]:
        path = self._backup_dir(backup_id) / 'manifest.json'
        if not path.exists():
            raise RemoteBackupError(f'backup not found: {backup_id}')
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise RemoteBackupError(f'invalid backup manifest: {backup_id}')
        return data

    def list_backups(self) -> List[Dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        results = []
        for child in self.base_dir.iterdir():
            if not child.is_dir():
                continue
            manifest_path = child / 'manifest.json'
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except Exception:
                continue
            results.append({
                'backup_id': manifest.get('backup_id') or child.name,
                'created_at': manifest.get('created_at', ''),
                'total_files': manifest.get('total_files', 0),
                'total_bytes': manifest.get('total_bytes', 0),
                'resource_types': manifest.get('resource_types') or [],
            })
        results.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        return results

    def get_backup_detail(self, backup_id: str) -> Dict[str, Any]:
        return self._load_manifest(backup_id)

    def restore_preview(
        self,
        backup_id: str,
        *,
        resource_types: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        backup_manifest = self._load_manifest(backup_id)
        selected_types = self._resource_types(resource_types or backup_manifest.get('resource_types'))
        client = self._create_client()
        preview = {'backup_id': backup_id, 'items': [], 'create': 0, 'overwrite': 0, 'same': 0}

        for resource_type in selected_types:
            remote_entries = {
                normalize_remote_relative_path(entry.get('relative_path') or entry.get('path')): entry
                for entry in _entries_from_manifest(client.manifest(resource_type))
                if entry.get('relative_path') or entry.get('path')
            }
            for entry in backup_manifest.get('resources', {}).get(resource_type, []) or []:
                relative_path = normalize_remote_relative_path(entry.get('relative_path') or entry.get('path'))
                remote_entry = remote_entries.get(relative_path)
                same = bool(remote_entry and remote_entry.get('sha256') == entry.get('sha256'))
                action = 'same' if same else ('overwrite' if remote_entry else 'create')
                preview[action] += 1
                preview['items'].append({
                    'resource_type': resource_type,
                    'relative_path': relative_path,
                    'exists_remote': bool(remote_entry),
                    'same_sha256': same,
                    'action': action,
                })
        return preview

    def restore_backup(
        self,
        backup_id: str,
        *,
        overwrite: bool = False,
        resource_types: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        backup_manifest = self._load_manifest(backup_id)
        selected_types = self._resource_types(resource_types or backup_manifest.get('resource_types'))
        backup_dir = self._backup_dir(backup_id)
        client = self._create_client()
        result = {'backup_id': backup_id, 'uploaded': 0, 'skipped': 0, 'failed': 0, 'items': []}

        for resource_type in selected_types:
            remote_entries = {
                normalize_remote_relative_path(entry.get('relative_path') or entry.get('path')): entry
                for entry in _entries_from_manifest(client.manifest(resource_type))
                if entry.get('relative_path') or entry.get('path')
            }
            for entry in backup_manifest.get('resources', {}).get(resource_type, []) or []:
                relative_path = normalize_remote_relative_path(entry.get('relative_path') or entry.get('path'))
                source = _safe_backup_file(backup_dir, resource_type, relative_path)
                if not source.is_file():
                    result['failed'] += 1
                    result['items'].append({
                        'resource_type': resource_type,
                        'relative_path': relative_path,
                        'status': 'missing_backup_file',
                    })
                    continue
                if relative_path in remote_entries and not overwrite:
                    result['skipped'] += 1
                    result['items'].append({
                        'resource_type': resource_type,
                        'relative_path': relative_path,
                        'status': 'skipped_existing',
                    })
                    continue

                data = source.read_bytes()
                client.upload_file(
                    resource_type,
                    relative_path,
                    data,
                    overwrite_mode='overwrite' if overwrite else 'skip_existing',
                )
                result['uploaded'] += 1
                result['items'].append({
                    'resource_type': resource_type,
                    'relative_path': relative_path,
                    'status': 'uploaded',
                })

        return result
