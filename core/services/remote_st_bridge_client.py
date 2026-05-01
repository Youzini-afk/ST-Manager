import base64
import hashlib
from typing import Any, Dict, Optional

from core.config import load_config
from core.services.st_auth import build_st_http_client


BRIDGE_BASE_PATH = '/api/plugins/authority/st-manager'
DEFAULT_CHUNK_SIZE = 1024 * 1024


class RemoteSTBridgeError(Exception):
    """Raised when the Authority ST-Manager bridge rejects or corrupts a transfer."""


class RemoteSTBridgeClient:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        bridge_key: str = '',
        http_client=None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout: int = 60,
    ):
        self.config = config or load_config()
        self.bridge_key = bridge_key or self.config.get('remote_bridge_key', '') or ''
        self.chunk_size = int(chunk_size or DEFAULT_CHUNK_SIZE)
        self.timeout = timeout
        self.http_client = http_client or build_st_http_client(
            self.config,
            st_url=self.config.get('st_url'),
            timeout=timeout,
        )

    def _headers(self) -> Dict[str, str]:
        headers = {'X-ST-Manager-Key': self.bridge_key}
        if self.bridge_key:
            headers['Authorization'] = f'Bearer {self.bridge_key}'
        return headers

    def _raise_for_response(self, response, action: str):
        if getattr(response, 'ok', False):
            return
        status = getattr(response, 'status_code', 'unknown')
        text = getattr(response, 'text', '')
        raise RemoteSTBridgeError(f'{action} failed ({status}): {text}')

    def _json(self, response, action: str) -> Dict[str, Any]:
        self._raise_for_response(response, action)
        try:
            payload = response.json()
        except Exception as exc:
            raise RemoteSTBridgeError(f'{action} returned invalid JSON') from exc
        if not isinstance(payload, dict):
            raise RemoteSTBridgeError(f'{action} returned unexpected payload')
        return payload

    def _get(self, path: str, action: str) -> Dict[str, Any]:
        response = self.http_client.get(path, headers=self._headers(), timeout=self.timeout)
        return self._json(response, action)

    def _post(self, path: str, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        response = self.http_client.post(path, json=payload, headers=self._headers(), timeout=self.timeout)
        return self._json(response, action)

    def probe(self) -> Dict[str, Any]:
        return self._get(f'{BRIDGE_BASE_PATH}/bridge/probe', 'bridge probe')

    def manifest(self, resource_type: str) -> Dict[str, Any]:
        return self._get(f'{BRIDGE_BASE_PATH}/resources/{resource_type}/manifest', 'resource manifest')

    def download_file(
        self,
        resource_type: str,
        path: str,
        *,
        expected_sha256: Optional[str] = None,
    ) -> bytes:
        offset = 0
        parts = []
        remote_sha256 = None

        while True:
            payload = self._post(
                f'{BRIDGE_BASE_PATH}/resources/{resource_type}/file/read',
                {'path': path, 'offset': offset, 'limit': self.chunk_size},
                'file read',
            )
            chunk = base64.b64decode(payload.get('data_base64') or '')
            parts.append(chunk)
            bytes_read = int(payload.get('bytes_read') or len(chunk))
            if bytes_read != len(chunk):
                raise RemoteSTBridgeError(f'chunk size mismatch for {path} at offset {offset}')
            offset += len(chunk)
            remote_sha256 = payload.get('sha256') or remote_sha256
            if payload.get('eof'):
                break

            if not chunk:
                raise RemoteSTBridgeError(f'file read stalled for {path} at offset {offset}')

        data = b''.join(parts)
        actual_sha256 = hashlib.sha256(data).hexdigest()
        expected = expected_sha256 or remote_sha256
        if expected and actual_sha256 != expected:
            raise RemoteSTBridgeError(
                f'sha256 mismatch for {path}: expected {expected}, got {actual_sha256}'
            )
        if remote_sha256 and actual_sha256 != remote_sha256:
            raise RemoteSTBridgeError(
                f'sha256 mismatch for {path}: remote {remote_sha256}, got {actual_sha256}'
            )
        return data

    def upload_file(
        self,
        resource_type: str,
        path: str,
        data: bytes,
        *,
        overwrite_mode: str = 'skip_existing',
    ) -> Dict[str, Any]:
        digest = hashlib.sha256(data).hexdigest()
        init_payload = self._post(
            f'{BRIDGE_BASE_PATH}/resources/{resource_type}/file/write-init',
            {
                'path': path,
                'size': len(data),
                'sha256': digest,
                'overwrite_mode': overwrite_mode,
            },
            'file write init',
        )
        upload_id = init_payload.get('upload_id')
        if not upload_id:
            raise RemoteSTBridgeError(f'file write init did not return upload_id for {path}')

        offset = 0
        while offset < len(data):
            chunk = data[offset: offset + self.chunk_size]
            self._post(
                f'{BRIDGE_BASE_PATH}/resources/{resource_type}/file/write-chunk',
                {
                    'upload_id': upload_id,
                    'offset': offset,
                    'data_base64': base64.b64encode(chunk).decode('ascii'),
                },
                'file write chunk',
            )
            offset += len(chunk)

        return self._post(
            f'{BRIDGE_BASE_PATH}/resources/{resource_type}/file/write-commit',
            {'upload_id': upload_id},
            'file write commit',
        )
