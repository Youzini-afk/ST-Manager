import hashlib
import json
import secrets
from pathlib import Path
from typing import Dict, Optional

from core.config import SYSTEM_DIR


CONTROL_FILENAME = 'control.json'


def hash_control_key(key: str) -> str:
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def generate_control_key() -> str:
    return f"stmc_{secrets.token_urlsafe(24)}"


def mask_control_key(key: str) -> str:
    if not key:
        return ''
    if len(key) <= 12:
        return 'stmc...'
    return f"{key[:6]}...{key[-4:]}"


class RemoteBackupControlStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path(SYSTEM_DIR) / 'remote_backups')
        self.path = self.base_dir / CONTROL_FILENAME

    def load_private(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def public(self, state: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        state = dict(state if state is not None else self.load_private())
        return {
            'enabled': bool(state.get('enabled')),
            'control_key_masked': state.get('control_key_masked', ''),
            'control_key_fingerprint': state.get('control_key_fingerprint', ''),
        }

    def save(self, state: Dict[str, str]) -> Dict[str, str]:
        current = self.load_private()
        next_state = {**current, **state}
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.public(next_state)

    def rotate(self) -> Dict[str, str]:
        key = generate_control_key()
        digest = hash_control_key(key)
        state = {
            'enabled': True,
            'control_key_hash': digest,
            'control_key_masked': mask_control_key(key),
            'control_key_fingerprint': digest[:12],
        }
        public = self.save(state)
        return {**public, 'control_key': key}

    def authorize(self, provided_key: str) -> bool:
        state = self.load_private()
        expected = state.get('control_key_hash', '')
        if not state.get('enabled') or not expected or not provided_key:
            return False
        return secrets.compare_digest(hash_control_key(provided_key), expected)


def extract_control_key(headers) -> str:
    direct = headers.get('X-ST-Manager-Control-Key') or headers.get('x-st-manager-control-key')
    if direct:
        return str(direct).strip()
    auth = str(headers.get('Authorization') or headers.get('authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


def is_remote_backup_control_authorized(path: str, headers) -> bool:
    if not str(path or '').startswith('/api/remote_backups/'):
        return False
    return RemoteBackupControlStore().authorize(extract_control_key(headers))
