import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.api.v1.st_sync import _export_global_regex
from core.config import BASE_DIR, load_config
from core.services.cache_service import invalidate_wi_list_cache
from core.services.remote_backup_service import normalize_remote_relative_path
from core.services.scan_service import request_scan


RESOURCE_TARGET_CONFIG = {
    'characters': ('cards_dir', 'data/library/characters'),
    'chats': ('chats_dir', 'data/library/chats'),
    'worlds': ('world_info_dir', 'data/library/lorebooks'),
    'presets': ('presets_dir', 'data/library/presets'),
    'regex': ('regex_dir', 'data/library/extensions/regex'),
    'quick_replies': ('quick_replies_dir', 'data/library/extensions/quick-replies'),
}


def _resolve_library_dir(config: Dict[str, Any], resource_type: str) -> Path:
    key, default = RESOURCE_TARGET_CONFIG[resource_type]
    raw = str(config.get(key) or default)
    if os.path.isabs(raw):
        return Path(raw)
    return Path(BASE_DIR) / raw


def _copy_file(source: Path, target_root: Path, relative_path: str) -> str:
    normalized = normalize_remote_relative_path(relative_path)
    target = target_root.joinpath(*normalized.split('/'))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def _entries_for(manifest: Dict[str, Any], resource_type: str) -> Iterable[Dict[str, Any]]:
    resources = manifest.get('resources') or {}
    entries = resources.get(resource_type) or []
    return entries if isinstance(entries, list) else []


class RemoteLibraryIngestService:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or load_config()

    def ingest_backup(self, backup_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        backup_dir = Path(backup_dir)
        result = {
            'copied': 0,
            'failed': 0,
            'files': [],
            'global_regex': {'success': 0, 'failed': 0, 'files': []},
            'refreshed': [],
        }

        touched_types: List[str] = []
        resources = manifest.get('resources') or {}
        for resource_type in resources.keys():
            if resource_type not in RESOURCE_TARGET_CONFIG:
                continue
            target_root = _resolve_library_dir(self.config, resource_type)
            target_root.mkdir(parents=True, exist_ok=True)

            for entry in _entries_for(manifest, resource_type):
                relative_path = entry.get('relative_path') or entry.get('path')
                if not relative_path:
                    continue
                normalized = normalize_remote_relative_path(relative_path)
                source = backup_dir / 'resources' / resource_type / Path(*normalized.split('/'))
                if not source.is_file():
                    result['failed'] += 1
                    continue

                try:
                    if (
                        resource_type == 'regex'
                        and (
                            entry.get('kind') == 'settings_regex_bundle'
                            or entry.get('source') == 'settings'
                            or normalized == 'settings.regex.json'
                        )
                    ):
                        global_result = _export_global_regex(str(source), str(target_root))
                        result['global_regex']['success'] += global_result.get('success', 0)
                        result['global_regex']['failed'] += global_result.get('failed', 0)
                        result['global_regex']['files'].extend(global_result.get('files') or [])
                        if global_result.get('success'):
                            touched_types.append(resource_type)
                        continue

                    copied_path = _copy_file(source, target_root, normalized)
                    result['copied'] += 1
                    result['files'].append(copied_path)
                    touched_types.append(resource_type)
                except Exception:
                    result['failed'] += 1

        if 'characters' in touched_types:
            request_scan(reason='remote_backup')
            result['refreshed'].append('characters')
        if 'worlds' in touched_types:
            invalidate_wi_list_cache()
            result['refreshed'].append('worlds')
        if 'chats' in touched_types:
            result['refreshed'].append('chats')

        return result
