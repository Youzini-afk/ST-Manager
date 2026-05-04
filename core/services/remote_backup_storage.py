import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict


class RemoteBackupStorageError(Exception):
    pass


def normalize_remote_relative_path(path: str) -> str:
    if not isinstance(path, str):
        raise RemoteBackupStorageError('illegal relative_path: expected string')
    raw = path.strip()
    if not raw:
        raise RemoteBackupStorageError('illegal relative_path: empty')
    if '\\' in raw:
        raise RemoteBackupStorageError(f'illegal relative_path: {path}')
    if raw.startswith('/'):
        raise RemoteBackupStorageError(f'illegal relative_path: {path}')
    if re.match(r'^[A-Za-z]:', raw):
        raise RemoteBackupStorageError(f'illegal relative_path: {path}')

    posix_path = PurePosixPath(raw)
    parts = posix_path.parts
    if not parts or any(part in ('', '.', '..') for part in parts):
        raise RemoteBackupStorageError(f'illegal relative_path: {path}')
    normalized = '/'.join(parts)
    if normalized.startswith('../') or normalized == '..':
        raise RemoteBackupStorageError(f'illegal relative_path: {path}')
    return normalized


def safe_backup_file(root: Path, resource_type: str, relative_path: str) -> Path:
    normalized = normalize_remote_relative_path(relative_path)
    target = root / 'resources' / resource_type / Path(*normalized.split('/'))
    base = (root / 'resources' / resource_type).resolve()
    resolved = target.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise RemoteBackupStorageError(f'illegal relative_path: {relative_path}') from exc
    return target


def resolve_backup_entry_path(
    backup_dir: Path,
    resource_type: str,
    entry: Dict[str, Any],
) -> Path:
    relative_path = entry.get('relative_path') or entry.get('path')
    if not relative_path:
        raise RemoteBackupStorageError('backup entry missing relative_path')
    return safe_backup_file(Path(backup_dir), resource_type, normalize_remote_relative_path(str(relative_path)))


def read_backup_entry_bytes(
    backup_dir: Path,
    resource_type: str,
    entry: Dict[str, Any],
) -> bytes:
    path = resolve_backup_entry_path(backup_dir, resource_type, entry)
    if not path.is_file():
        relative_path = entry.get('relative_path') or entry.get('path') or ''
        raise RemoteBackupStorageError(f'backup file not found: {resource_type}/{relative_path}')
    return path.read_bytes()
