import hashlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services.remote_st_bridge_client import RemoteSTBridgeClient, RemoteSTBridgeError


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code
        self.content = b'1'
        self.text = str(self._payload)
        self.ok = status_code < 400

    def json(self):
        return self._payload


class FakeHTTPClient:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.calls = []

    def get(self, path, **kwargs):
        self.calls.append(('get', path, kwargs))
        return FakeResponse({'files': []})

    def post(self, path, json=None, **kwargs):
        self.calls.append(('post', path, json, kwargs))
        if path.endswith('/file/read'):
            return FakeResponse(self.chunks.pop(0))
        return FakeResponse({'ok': True})


def test_client_sends_bridge_key_and_downloads_verified_chunks():
    payload = b'hello'
    digest = hashlib.sha256(payload).hexdigest()
    fake_http = FakeHTTPClient([
        {
            'path': 'Ava.png',
            'offset': 0,
            'bytes_read': 2,
            'size': 5,
            'sha256': digest,
            'eof': False,
            'data_base64': 'aGU=',
        },
        {
            'path': 'Ava.png',
            'offset': 2,
            'bytes_read': 3,
            'size': 5,
            'sha256': digest,
            'eof': True,
            'data_base64': 'bGxv',
        },
    ])
    client = RemoteSTBridgeClient({'st_url': 'http://st.example'}, bridge_key='secret', http_client=fake_http, chunk_size=2)

    assert client.download_file('characters', 'Ava.png', expected_sha256=digest) == payload
    assert all(call[-1]['headers']['Authorization'] == 'Bearer secret' for call in fake_http.calls)
    assert fake_http.calls[0][1] == '/api/plugins/authority/st-manager/resources/characters/file/read'


def test_client_rejects_checksum_mismatch():
    fake_http = FakeHTTPClient([
        {
            'path': 'Ava.png',
            'offset': 0,
            'bytes_read': 3,
            'size': 3,
            'sha256': '0' * 64,
            'eof': True,
            'data_base64': 'YmFk',
        },
    ])
    client = RemoteSTBridgeClient({'st_url': 'http://st.example'}, bridge_key='secret', http_client=fake_http)

    try:
        client.download_file('characters', 'Ava.png', expected_sha256='0' * 64)
    except RemoteSTBridgeError as exc:
        assert 'sha256 mismatch' in str(exc)
    else:
        raise AssertionError('expected checksum mismatch')
