import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import presets as presets_api


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(presets_api.bp)
    return app


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _configure(monkeypatch, tmp_path, presets_dir):
    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )


def test_preset_save_overwrite_preserves_unknown_fields(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(
        preset_file,
        {
            'name': 'Textgen',
            'temp': 0.7,
            'top_p': 0.9,
            'custom_flag': {'keep': True},
            'extensions': {'regex_scripts': []},
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::textgen.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::textgen.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {'name': 'Textgen', 'temp': 1.1, 'top_p': 0.92},
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temp'] == 1.1
    assert payload['top_p'] == 0.92
    assert payload['custom_flag'] == {'keep': True}
    assert payload['extensions'] == {'regex_scripts': []}


def test_preset_save_overwrite_preserves_unedited_legacy_scalar_fields_for_generic_prompt_payload(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(
        preset_file,
        {
            'name': 'Textgen',
            'temp': 0.7,
            'rep_pen': 1.1,
            'samplers': ['top_p', 'min_p'],
            'top_a': 0.2,
            'typical_p': 0.9,
            'xtc_threshold': 0.15,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::textgen.json')
    detail_payload = detail_res.get_json()['preset']
    revision = detail_payload['source_revision']

    assert detail_payload['preset_kind'] == 'generic'
    assert detail_payload['reader_view']['family'] == 'generic'
    assert detail_payload['reader_view']['scalar_workspace'] is None

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::textgen.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Textgen',
                'temp': 0.95,
                'rep_pen': 1.4,
                'samplers': ['temperature', 'top_p'],
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temp'] == 0.95
    assert payload['rep_pen'] == 1.4
    assert payload['samplers'] == ['temperature', 'top_p']
    assert payload['top_a'] == 0.2
    assert payload['typical_p'] == 0.9
    assert payload['xtc_threshold'] == 0.15


def test_merge_preset_content_preserves_existing_textgen_alias_key():
    raw_data = {
        'rep_pen': 1.1,
        'temp': 0.7,
        'prompts': [{'identifier': 'main', 'content': 'hello'}],
    }

    merged = presets_api.merge_preset_content(
        raw_data,
        'textgen',
        {
            'repetition_penalty': 1.4,
            'temp': 0.95,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    assert merged['rep_pen'] == 1.4
    assert merged['temp'] == 0.95
    assert 'repetition_penalty' not in merged


def test_merge_preset_content_removes_stale_alias_twin_and_keeps_openai_canonical_key():
    raw_data = {
        'rep_pen': 1.1,
        'repetition_penalty': 1.25,
        'temp': 0.7,
        'prompts': [{'identifier': 'main', 'content': 'hello'}],
    }

    merged = presets_api.merge_preset_content(
        raw_data,
        'textgen',
        {
            'repetition_penalty': 1.4,
            'temp': 0.95,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    assert merged['repetition_penalty'] == 1.4
    assert merged['temp'] == 0.95
    assert 'rep_pen' not in merged


def test_preset_save_overwrite_ignores_removed_unknown_fields_and_preserves_unedited_keys(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(
        preset_file,
        {
            'name': 'Textgen',
            'temp': 0.7,
            'top_p': 0.9,
            'custom_flag': {'keep': True},
            'extensions': {'regex_scripts': []},
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::textgen.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::textgen.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'removed_unknown_fields': ['custom_flag'],
            'content': {'name': 'Textgen', 'temp': 1.1, 'top_p': 0.92},
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temp'] == 1.1
    assert payload['top_p'] == 0.92
    assert payload['custom_flag'] == {'keep': True}
    assert payload['extensions'] == {'regex_scripts': []}


def test_preset_save_overwrite_keeps_st_connection_fields_and_does_not_rewrite_runtime_keys(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'chat-runtime.json'
    _write_json(
        preset_file,
        {
            'name': 'Chat Runtime',
            'temperature': 0.8,
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'api_url': 'https://old.example/api',
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::chat-runtime.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::chat-runtime.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Chat Runtime',
                'temperature': 1.2,
                'openai_max_context': 8192,
                'openai_max_tokens': 1400,
                'stream_openai': False,
                'custom_url': 'https://custom.example/api',
                'reverse_proxy': 'https://proxy.example/api',
                'api_url': 'https://new.example/api',
                'proxy_password': 'secret',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temperature'] == 1.2
    assert payload['openai_max_tokens'] == 1400
    assert payload['stream_openai'] is False
    assert payload['custom_url'] == 'https://custom.example/api'
    assert payload['reverse_proxy'] == 'https://proxy.example/api'
    assert payload['proxy_password'] == 'secret'
    assert payload['api_url'] == 'https://old.example/api'


def test_preset_save_rejects_stale_source_revision(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(preset_file, {'name': 'Textgen', 'temp': 0.7})

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::textgen.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': '1:1',
            'content': {'name': 'Textgen', 'temp': 0.8},
        },
    )

    assert save_res.status_code == 409
    assert 'source_revision' in save_res.get_json()['msg']


def test_preset_save_requires_source_revision_for_overwrite(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(preset_file, {'name': 'Textgen', 'temp': 0.7})

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::textgen.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'content': {'name': 'Textgen', 'temp': 0.8},
        },
    )

    assert save_res.status_code == 409
    assert 'source_revision' in save_res.get_json()['msg']


def test_preset_save_as_creates_new_global_file(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    presets_dir.mkdir(parents=True, exist_ok=True)

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'preset_kind': 'textgen',
            'save_mode': 'save_as',
            'name': '新的文本生成预设',
            'content': {'name': '新的文本生成预设', 'temp': 0.8},
        },
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert (presets_dir / '新的文本生成预设.json').exists()


def test_preset_save_as_explicit_generic_kind_preserves_unknown_keys_and_stays_in_presets_dir(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'generic',
            'name': 'Generic Prompt Payload',
            'content': {
                'name': 'Generic Prompt Payload',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
                'prompt_order': ['main'],
                'custom_flag': {'keep': True},
                'api_url': 'https://generic.example/api',
            },
        },
    )

    assert res.status_code == 200
    response_payload = res.get_json()
    assert response_payload['preset']['preset_kind'] == 'generic'
    assert (presets_dir / 'Generic Prompt Payload.json').exists()
    assert not (openai_dir / 'Generic Prompt Payload.json').exists()

    payload = json.loads((presets_dir / 'Generic Prompt Payload.json').read_text(encoding='utf-8'))
    assert payload['prompts'] == [{'identifier': 'main', 'content': 'hello'}]
    assert payload['prompt_order'] == ['main']
    assert payload['custom_flag'] == {'keep': True}
    assert payload['api_url'] == 'https://generic.example/api'

    detail_res = client.get(f"/api/presets/detail/{response_payload['preset_id']}")
    assert detail_res.status_code == 200
    detail_payload = detail_res.get_json()['preset']
    assert detail_payload['preset_kind'] == 'generic'
    assert detail_payload['reader_view']['family'] == 'generic'
    assert '__st_manager_preset_kind' not in detail_payload['raw_data']
    assert all(item['payload'].get('key') != '__st_manager_preset_kind' for item in detail_payload['reader_view']['items'])


def test_preset_save_as_explicit_openai_kind_stays_openai_for_prompt_only_payload(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'OpenAI Prompt Only',
            'content': {
                'name': 'OpenAI Prompt Only',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    response_payload = res.get_json()
    assert response_payload['preset']['preset_kind'] == 'openai'
    assert (openai_dir / 'OpenAI Prompt Only.json').exists()

    detail_res = client.get(f"/api/presets/detail/{response_payload['preset_id']}")
    assert detail_res.status_code == 200
    detail_payload = detail_res.get_json()['preset']
    assert detail_payload['preset_kind'] == 'openai'
    assert detail_payload['reader_view']['family'] == 'prompt_manager'
    assert '__st_manager_preset_kind' not in detail_payload['raw_data']


def test_preset_save_as_openai_preserves_unknown_and_st_provider_connection_keys(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'OpenAI Connection Extras',
            'content': {
                'name': 'OpenAI Connection Extras',
                'chat_completion_source': 'custom',
                'custom_url': 'https://example.test/v1',
                'reverse_proxy': 'https://proxy.test',
                'proxy_password': 'secret',
                'azure_base_url': 'https://azure.example/openai',
                'azure_api_version': '2024-10-21',
                'vertexai_auth_mode': 'express',
                'vertexai_region': 'us-central1',
                'wrap_in_quotes': False,
                'api_url': 'https://runtime.example/api',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads((openai_dir / 'OpenAI Connection Extras.json').read_text(encoding='utf-8'))
    assert payload['custom_url'] == 'https://example.test/v1'
    assert payload['reverse_proxy'] == 'https://proxy.test'
    assert payload['proxy_password'] == 'secret'
    assert payload['azure_base_url'] == 'https://azure.example/openai'
    assert payload['azure_api_version'] == '2024-10-21'
    assert payload['vertexai_auth_mode'] == 'express'
    assert payload['vertexai_region'] == 'us-central1'
    assert payload['wrap_in_quotes'] is False
    assert 'api_url' not in payload


def test_preset_save_as_does_not_trust_spoofed_managed_kind_marker_from_input(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'invalid-kind',
            'name': 'Spoofed Marker Save',
            'content': {
                'name': 'Spoofed Marker Save',
                '__st_manager_preset_kind': 'openai',
                'custom_flag': {'keep': True},
            },
        },
    )

    assert res.status_code == 200
    payload = res.get_json()['preset']
    assert payload['preset_kind'] == 'generic'
    assert (presets_dir / 'Spoofed Marker Save.json').exists()
    assert not (openai_dir / 'Spoofed Marker Save.json').exists()


def test_legacy_preset_save_does_not_persist_spoofed_managed_kind_marker(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'legacy-save.json'
    presets_dir.mkdir(parents=True, exist_ok=True)

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'id': 'global::legacy-save.json',
            'content': {
                'name': 'Legacy Save',
                '__st_manager_preset_kind': 'openai',
                'custom_flag': {'keep': True},
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert '__st_manager_preset_kind' not in payload


def test_preset_save_as_keeps_st_connection_fields_and_does_not_write_runtime_keys(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'Chat Save As Safe',
            'content': {
                'name': 'Chat Save As Safe',
                'chat_completion_source': 'custom',
                'openai_max_context': 2048,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'custom_url': 'https://custom.example/api',
                'reverse_proxy': 'https://proxy.example/api',
                'api_url': 'https://new.example/api',
                'proxy_password': 'secret',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads((openai_dir / 'Chat Save As Safe.json').read_text(encoding='utf-8'))
    assert payload['openai_max_context'] == 2048
    assert payload['openai_max_tokens'] == 1200
    assert payload['stream_openai'] is True
    assert payload['custom_url'] == 'https://custom.example/api'
    assert payload['reverse_proxy'] == 'https://proxy.example/api'
    assert payload['proxy_password'] == 'secret'
    assert 'api_url' not in payload


def test_preset_save_as_legacy_non_chat_kind_falls_back_to_generic_presets_dir(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'instruct',
            'name': 'Legacy Route Compatibility',
            'content': {
                'name': 'Legacy Route Compatibility',
                'system_prompt': 'Follow the system prompt.',
            },
        },
    )

    assert res.status_code == 200
    assert (presets_dir / 'Legacy Route Compatibility.json').exists()
    assert not (openai_dir / 'Legacy Route Compatibility.json').exists()
    assert res.get_json()['preset']['preset_kind'] == 'generic'


def test_preset_save_as_preserves_large_openai_context_for_new_file(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'Large Context Save As',
            'content': {
                'name': 'Large Context Save As',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads((openai_dir / 'Large Context Save As.json').read_text(encoding='utf-8'))
    assert payload['openai_max_context'] == 8192


def test_preset_save_overwrite_falls_back_from_invalid_preset_kind_to_stored_profile(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'chat-invalid-kind.json'
    _write_json(
        preset_file,
        {
            'name': 'Chat Invalid Kind',
            'temperature': 0.8,
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'api_url': 'https://old.example/api',
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::chat-invalid-kind.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::chat-invalid-kind.json',
            'preset_kind': 'invalid-kind',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Chat Invalid Kind',
                'temperature': 1.2,
                'openai_max_context': 8192,
                'openai_max_tokens': 1400,
                'stream_openai': False,
                'api_url': 'https://new.example/api',
                'proxy_password': 'secret',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temperature'] == 1.2
    assert payload['openai_max_tokens'] == 1400
    assert payload['api_url'] == 'https://old.example/api'
    assert payload['proxy_password'] == 'secret'


def test_preset_save_as_falls_back_from_invalid_preset_kind_to_detected_profile(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'invalid-kind',
            'name': 'Invalid Kind Save As',
            'content': {
                'name': 'Invalid Kind Save As',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'proxy_password': 'secret',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['preset']['preset_kind'] == 'openai'
    saved = json.loads((openai_dir / 'Invalid Kind Save As.json').read_text(encoding='utf-8'))
    assert saved['openai_max_context'] == 8192
    assert saved['proxy_password'] == 'secret'


def test_preset_save_overwrite_keeps_openai_kind_for_sparse_alt_root_when_requested_kind_is_invalid(
    monkeypatch, tmp_path
):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    preset_file = openai_dir / 'Sparse Alt Root.json'
    _write_json(
        preset_file,
        {
            'name': 'Sparse Alt Root',
            'prompts': [{'identifier': 'main', 'content': 'old'}],
        },
    )

    client = _make_test_app().test_client()
    preset_id = 'global-alt::st_openai_preset_dir::Sparse Alt Root.json'
    detail_res = client.get(f'/api/presets/detail/{preset_id}')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['preset']['preset_kind'] == 'openai'
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': preset_id,
            'preset_kind': 'invalid-kind',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Sparse Alt Root',
                'prompts': [{'identifier': 'main', 'content': 'new'}],
            },
        },
    )

    assert save_res.status_code == 200
    response_payload = save_res.get_json()['preset']
    assert response_payload['preset_kind'] == 'openai'
    saved = json.loads(preset_file.read_text(encoding='utf-8'))
    assert saved['prompts'][0]['content'] == 'new'
    assert saved['__st_manager_preset_kind'] == 'openai'


def test_preset_save_overwrite_clamps_chat_completion_fields_and_preserves_valid_enum(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'chat.json'
    _write_json(
        preset_file,
        {
            'name': 'Chat',
            'temperature': 0.8,
            'top_p': 0.9,
            'frequency_penalty': 0.1,
            'presence_penalty': 0.2,
            'reasoning_effort': 'medium',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::chat.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::chat.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Chat',
                'temperature': 9,
                'top_p': 2,
                'frequency_penalty': -9,
                'presence_penalty': 9,
                'reasoning_effort': 'extreme',
                'openai_max_context': 2048,
                'openai_max_tokens': 999999,
                'stream_openai': False,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['temperature'] == 2
    assert payload['top_p'] == 1
    assert payload['frequency_penalty'] == -2
    assert payload['presence_penalty'] == 2
    assert payload['reasoning_effort'] == 'medium'
    assert payload['openai_max_tokens'] == 128000
    assert payload['stream_openai'] is False


def test_preset_save_overwrite_uses_dynamic_context_max_fallback_for_chat_completion(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'chat-context.json'
    _write_json(
        preset_file,
        {
            'name': 'Chat Context',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::chat-context.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::chat-context.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Chat Context',
                'openai_max_context': 999999,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['openai_max_context'] == 8192


def test_preset_save_as_routes_openai_profile_to_configured_directory(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'OpenAI Save As',
            'content': {
                'name': 'OpenAI Save As',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    assert (openai_dir / 'OpenAI Save As.json').exists()
    assert not (presets_dir / 'OpenAI Save As.json').exists()


def test_preset_save_as_falls_back_to_presets_dir_when_openai_directory_missing(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    presets_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': '',
        },
    )

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'Fallback Save As',
            'content': {
                'name': 'Fallback Save As',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert res.status_code == 200
    assert (presets_dir / 'Fallback Save As.json').exists()


def test_merge_preset_content_clamps_dynamic_max_without_existing_value():
    merged = presets_api.merge_preset_content(
        {
            'name': 'Chat Preset',
            'temperature': 0.8,
            'top_p': 0.9,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
        'textgen',
        {
            'name': 'Chat Preset',
            'openai_max_context': 999999,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    assert merged['openai_max_context'] == 4095


def test_merge_preset_content_preserves_unknown_openai_keys_when_profile_resolves_from_shape():
    merged = presets_api.merge_preset_content(
        {},
        'textgen',
        {
            'name': 'Resolved OpenAI Preset',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'azure_base_url': 'https://azure.example/openai',
            'wrap_in_quotes': False,
            'api_url': 'https://runtime.example/api',
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    assert merged['azure_base_url'] == 'https://azure.example/openai'
    assert merged['wrap_in_quotes'] is False
    assert 'api_url' not in merged


def test_preset_save_as_returns_followup_usable_id_for_chat_completion_directory(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    save_res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'Chat Save As Followup',
            'content': {
                'name': 'Chat Save As Followup',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = save_res.get_json()
    preset_id = payload['preset_id']
    assert '..' not in preset_id
    assert preset_id.startswith('global-alt::st_openai_preset_dir::')

    detail_res = client.get(f'/api/presets/detail/{preset_id}')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['preset']['id'] == preset_id


def test_preset_save_as_prefers_explicit_generic_preset_kind_over_shape_detection(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    save_res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'generic',
            'name': 'Explicit Kind Wins',
            'content': {
                'name': 'Explicit Kind Wins',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = save_res.get_json()
    assert payload['preset']['preset_kind'] == 'generic'
    assert payload['preset']['source_folder'] is None


def test_preset_save_as_followup_operations_work_with_alternate_root_ids(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    save_res = client.post(
        '/api/presets/save',
        json={
            'save_mode': 'save_as',
            'preset_kind': 'openai',
            'name': 'Alt Root Flow',
            'content': {
                'name': 'Alt Root Flow',
                'openai_max_context': 8192,
                'openai_max_tokens': 1200,
                'stream_openai': True,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = save_res.get_json()
    preset_id = payload['preset_id']
    assert preset_id.startswith('global-alt::st_openai_preset_dir::')

    detail_res = client.get(f'/api/presets/detail/{preset_id}')
    assert detail_res.status_code == 200
    revision = detail_res.get_json()['preset']['source_revision']

    overwrite_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': preset_id,
            'preset_kind': 'openai',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Alt Root Flow',
                'openai_max_context': 8192,
                'openai_max_tokens': 1600,
                'stream_openai': False,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )
    assert overwrite_res.status_code == 200

    renamed_revision = overwrite_res.get_json()['preset']['source_revision']
    rename_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': preset_id,
            'save_mode': 'rename',
            'new_name': 'Alt Root Flow Renamed',
            'source_revision': renamed_revision,
        },
    )
    assert rename_res.status_code == 200
    renamed_id = rename_res.get_json()['preset_id']

    renamed_detail_res = client.get(f'/api/presets/detail/{renamed_id}')
    assert renamed_detail_res.status_code == 200
    delete_revision = renamed_detail_res.get_json()['preset']['source_revision']
    delete_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': renamed_id,
            'save_mode': 'delete',
            'source_revision': delete_revision,
        },
    )
    assert delete_res.status_code == 200
    assert not (openai_dir / 'Alt Root Flow Renamed.json').exists()


def test_preset_save_as_version_creates_parallel_file_and_upgrades_source_file(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'legacy-openai.json'
    _write_json(
        preset_file,
        {
            'name': 'Legacy OpenAI',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::legacy-openai.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::legacy-openai.json',
            'preset_kind': 'openai',
            'save_mode': 'save_as',
            'create_as_version': True,
            'version_label': 'v2',
            'source_revision': revision,
            'name': 'Legacy OpenAI V2',
            'content': {
                'name': 'Legacy OpenAI V2',
                'openai_max_context': 8192,
                'openai_max_tokens': 1600,
                'stream_openai': False,
                'prompts': [{'identifier': 'main', 'content': 'hello v2'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = save_res.get_json()
    cloned_path = presets_dir / 'Legacy OpenAI V2.json'
    assert cloned_path.exists()
    assert payload['preset_id'] == 'global::Legacy OpenAI V2.json'

    source_payload = json.loads(preset_file.read_text(encoding='utf-8'))
    cloned_payload = json.loads(cloned_path.read_text(encoding='utf-8'))

    source_meta = source_payload['x_st_manager']
    cloned_meta = cloned_payload['x_st_manager']
    assert source_meta['preset_family_id']
    assert cloned_meta['preset_family_id'] == source_meta['preset_family_id']
    assert source_meta['preset_is_default_version'] is True
    assert cloned_meta['preset_is_default_version'] is False
    assert source_meta['preset_version_label'] == 'legacy-openai'
    assert cloned_meta['preset_version_label'] == 'v2'

    cloned_detail = payload['preset']
    assert cloned_detail['family_info']['default_version_id'] == 'global::legacy-openai.json'
    assert cloned_detail['current_version']['version_label'] == 'v2'
    assert cloned_detail['current_version']['is_default_version'] is False


def test_resource_preset_save_as_version_keeps_new_file_in_same_resource_scope(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    resource_dir = tmp_path / 'resources' / 'hero-card' / 'presets'
    resource_file = resource_dir / 'legacy-resource.json'
    _write_json(
        resource_file,
        {
            'name': 'Legacy Resource',
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/resource::hero-card::legacy-resource')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'resource::hero-card::legacy-resource',
            'preset_kind': 'generic',
            'save_mode': 'save_as',
            'create_as_version': True,
            'version_label': 'v2',
            'source_revision': revision,
            'name': 'Legacy Resource V2',
            'content': {
                'name': 'Legacy Resource V2',
                'prompts': [{'identifier': 'main', 'content': 'hello v2'}],
            },
        },
    )

    assert save_res.status_code == 200
    assert (resource_dir / 'Legacy Resource V2.json').exists()
    assert not (presets_dir / 'Legacy Resource V2.json').exists()
    assert save_res.get_json()['preset_id'] == 'resource::hero-card::Legacy Resource V2'


def test_global_alt_openai_preset_save_as_version_keeps_new_file_in_openai_root(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    openai_dir = tmp_path / 'st-openai-presets'
    openai_file = openai_dir / 'legacy-alt.json'
    presets_dir.mkdir(parents=True, exist_ok=True)
    openai_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        openai_file,
        {
            'name': 'Legacy Alt',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': str(openai_dir),
        },
    )

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global-alt::st_openai_preset_dir::legacy-alt.json')
    revision = detail_res.get_json()['preset']['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global-alt::st_openai_preset_dir::legacy-alt.json',
            'preset_kind': 'openai',
            'save_mode': 'save_as',
            'create_as_version': True,
            'version_label': 'v2',
            'source_revision': revision,
            'name': 'Legacy Alt V2',
            'content': {
                'name': 'Legacy Alt V2',
                'openai_max_context': 8192,
                'openai_max_tokens': 1400,
                'stream_openai': False,
                'prompts': [{'identifier': 'main', 'content': 'hello v2'}],
            },
        },
    )

    assert save_res.status_code == 200
    assert (openai_dir / 'Legacy Alt V2.json').exists()
    assert not (presets_dir / 'Legacy Alt V2.json').exists()
    assert save_res.get_json()['preset_id'] == 'global-alt::st_openai_preset_dir::Legacy Alt V2.json'


def test_set_default_preset_version_rewrites_family_flags(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    shared_meta = {
        'preset_family_id': 'family-alpha',
        'preset_family_name': 'Companion Family',
    }
    _write_json(
        presets_dir / 'companion-v1.json',
        {
            'name': 'Companion V1',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v1',
                'preset_version_order': 10,
                'preset_is_default_version': True,
            },
        },
    )
    _write_json(
        presets_dir / 'companion-v2.json',
        {
            'name': 'Companion V2',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v2',
                'preset_version_order': 20,
                'preset_is_default_version': False,
            },
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    res = client.post(
        '/api/presets/version/set-default',
        json={'preset_id': 'global::companion-v2.json'},
    )

    assert res.status_code == 200
    v1_payload = json.loads((presets_dir / 'companion-v1.json').read_text(encoding='utf-8'))
    v2_payload = json.loads((presets_dir / 'companion-v2.json').read_text(encoding='utf-8'))
    assert v1_payload['x_st_manager']['preset_is_default_version'] is False
    assert v2_payload['x_st_manager']['preset_is_default_version'] is True
    assert res.get_json()['preset']['family_info']['default_version_id'] == 'global::companion-v2.json'


def test_preset_delete_promotes_next_version_when_default_is_removed(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    shared_meta = {
        'preset_family_id': 'family-alpha',
        'preset_family_name': 'Companion Family',
    }
    _write_json(
        presets_dir / 'companion-v1.json',
        {
            'name': 'Companion V1',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v1',
                'preset_version_order': 10,
                'preset_is_default_version': True,
            },
        },
    )
    _write_json(
        presets_dir / 'companion-v2.json',
        {
            'name': 'Companion V2',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v2',
                'preset_version_order': 20,
                'preset_is_default_version': False,
            },
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::companion-v1.json')
    revision = detail_res.get_json()['preset']['source_revision']

    delete_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::companion-v1.json',
            'save_mode': 'delete',
            'source_revision': revision,
        },
    )

    assert delete_res.status_code == 200
    assert not (presets_dir / 'companion-v1.json').exists()

    survivor_payload = json.loads((presets_dir / 'companion-v2.json').read_text(encoding='utf-8'))
    assert survivor_payload['x_st_manager']['preset_is_default_version'] is True

    detail_res = client.get('/api/presets/detail/global::companion-v2.json')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['preset']['family_info']['default_version_id'] == 'global::companion-v2.json'


def test_delete_preset_route_promotes_next_version_when_default_is_removed(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    shared_meta = {
        'preset_family_id': 'family-alpha',
        'preset_family_name': 'Companion Family',
    }
    _write_json(
        presets_dir / 'companion-v1.json',
        {
            'name': 'Companion V1',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v1',
                'preset_version_order': 10,
                'preset_is_default_version': True,
            },
        },
    )
    _write_json(
        presets_dir / 'companion-v2.json',
        {
            'name': 'Companion V2',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v2',
                'preset_version_order': 20,
                'preset_is_default_version': False,
            },
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    delete_res = client.post(
        '/api/presets/delete',
        json={
            'id': 'global::companion-v1.json',
        },
    )

    assert delete_res.status_code == 200
    assert not (presets_dir / 'companion-v1.json').exists()

    survivor_payload = json.loads((presets_dir / 'companion-v2.json').read_text(encoding='utf-8'))
    assert survivor_payload['x_st_manager']['preset_is_default_version'] is True

    detail_res = client.get('/api/presets/detail/global::companion-v2.json')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['preset']['family_info']['default_version_id'] == 'global::companion-v2.json'


def test_delete_preset_route_rejects_stale_source_revision_and_keeps_files(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    shared_meta = {
        'preset_family_id': 'family-alpha',
        'preset_family_name': 'Companion Family',
    }
    _write_json(
        presets_dir / 'companion-v1.json',
        {
            'name': 'Companion V1',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v1',
                'preset_version_order': 10,
                'preset_is_default_version': True,
            },
        },
    )
    _write_json(
        presets_dir / 'companion-v2.json',
        {
            'name': 'Companion V2',
            'x_st_manager': {
                **shared_meta,
                'preset_version_label': 'v2',
                'preset_version_order': 20,
                'preset_is_default_version': False,
            },
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    delete_res = client.post(
        '/api/presets/delete',
        json={
            'id': 'global::companion-v1.json',
            'source_revision': '1:1',
        },
    )

    assert delete_res.status_code == 409
    assert 'source_revision' in delete_res.get_json()['msg']
    assert (presets_dir / 'companion-v1.json').exists()
    assert (presets_dir / 'companion-v2.json').exists()

    source_payload = json.loads((presets_dir / 'companion-v1.json').read_text(encoding='utf-8'))
    survivor_payload = json.loads((presets_dir / 'companion-v2.json').read_text(encoding='utf-8'))
    assert source_payload['x_st_manager']['preset_is_default_version'] is True
    assert survivor_payload['x_st_manager']['preset_is_default_version'] is False


def test_preset_rename_updates_filename_and_object_name(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'old-name.json'
    _write_json(preset_file, {'name': 'Old Name', 'temp': 0.7})

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::old-name.json')
    revision = detail_res.get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::old-name.json',
            'save_mode': 'rename',
            'new_name': 'New Name',
            'source_revision': revision,
        },
    )

    assert res.status_code == 200
    assert (presets_dir / 'New Name.json').exists()
    renamed = json.loads((presets_dir / 'New Name.json').read_text(encoding='utf-8'))
    assert renamed['name'] == 'New Name'


def test_preset_delete_requires_revision_and_removes_file(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'delete-me.json'
    _write_json(preset_file, {'name': 'Delete Me', 'temp': 0.7})

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    detail_res = client.get('/api/presets/detail/global::delete-me.json')
    revision = detail_res.get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::delete-me.json',
            'save_mode': 'delete',
            'source_revision': revision,
        },
    )

    assert res.status_code == 200
    assert res.get_json()['success'] is True
    assert preset_file.exists() is False


def test_preset_save_overwrite_persists_prompt_structures(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'openai-chat.json'
    _write_json(
        preset_file,
        {
            'name': 'OpenAI Chat',
            'prompts': [{'identifier': 'main', 'name': 'Main', 'role': 'system', 'content': 'old'}],
            'prompt_order': ['main'],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    revision = client.get('/api/presets/detail/global::openai-chat.json').get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::openai-chat.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'OpenAI Chat',
                'prompts': [{'identifier': 'main', 'name': 'Main', 'role': 'system', 'content': 'new'}],
                'prompt_order': ['main'],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['prompts'][0]['content'] == 'new'
    assert payload['prompt_order'] == ['main']


def test_preset_save_overwrite_persists_logit_bias_list(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'bias.json'
    _write_json(preset_file, {'name': 'Bias', 'logit_bias': []})

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    revision = client.get('/api/presets/detail/global::bias.json').get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::bias.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Bias',
                'logit_bias': [{'text': 'forbidden', 'value': -5}],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['logit_bias'] == [{'text': 'forbidden', 'value': -5}]


def test_preset_save_overwrite_persists_reordered_prompt_workspace_content(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'openai-chat.json'
    _write_json(
        preset_file,
        {
            'name': 'OpenAI Chat',
            'prompts': [
                {'identifier': 'main', 'name': 'Main Prompt', 'role': 'system', 'content': 'old main'},
                {'identifier': 'summary', 'name': 'Summary', 'role': 'assistant', 'content': 'old summary'},
                {'identifier': 'worldInfoAfter', 'name': 'World Info (after)', 'marker': True},
            ],
            'prompt_order': ['main', 'summary'],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    revision = client.get('/api/presets/detail/global::openai-chat.json').get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::openai-chat.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'OpenAI Chat',
                'prompts': [
                    {'identifier': 'summary', 'name': 'Summary', 'role': 'assistant', 'content': 'new summary'},
                    {'identifier': 'main', 'name': 'Main Prompt', 'role': 'system', 'content': 'new main'},
                    {'identifier': 'worldInfoAfter', 'name': 'World Info (after)', 'marker': True},
                ],
                'prompt_order': ['summary', 'main', 'worldInfoAfter'],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert [prompt['identifier'] for prompt in payload['prompts']] == ['summary', 'main', 'worldInfoAfter']
    assert payload['prompt_order'] == ['summary', 'main', 'worldInfoAfter']
    assert payload['prompts'][2]['marker'] is True
    assert 'content' not in payload['prompts'][2]


def test_preset_save_overwrite_preserves_nested_st_prompt_order_when_unedited(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'st-openai.json'
    _write_json(
        preset_file,
        {
            'name': 'ST OpenAI',
            'prompts': [
                {'identifier': 'main', 'name': 'Main Prompt', 'role': 'system', 'content': 'old main'},
                {'identifier': 'worldInfoBefore', 'name': 'World Info (before)', 'marker': True},
            ],
            'prompt_order': [
                {
                    'character_id': 100000,
                    'order': [
                        {'identifier': 'worldInfoBefore', 'enabled': False},
                        {'identifier': 'main', 'enabled': True},
                    ],
                },
            ],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    revision = client.get('/api/presets/detail/global::st-openai.json').get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::st-openai.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'ST OpenAI',
                'prompts': [
                    {'identifier': 'main', 'name': 'Main Prompt', 'role': 'system', 'content': 'new main'},
                    {'identifier': 'worldInfoBefore', 'name': 'World Info (before)', 'marker': True},
                ],
                'prompt_order': [
                    {
                        'character_id': 100000,
                        'order': [
                            {'identifier': 'worldInfoBefore', 'enabled': False},
                            {'identifier': 'main', 'enabled': True},
                        ],
                    },
                ],
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['prompt_order'][0]['order'][0] == {'identifier': 'worldInfoBefore', 'enabled': False}
    assert payload['prompt_order'][0]['order'][1] == {'identifier': 'main', 'enabled': True}
    assert payload['prompts'][0]['content'] == 'new main'


def test_preset_save_overwrite_replaces_malformed_non_dict_root(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'broken.json'
    _write_json(preset_file, ['bad', 'root'])

    _configure(monkeypatch, tmp_path, presets_dir)

    client = _make_test_app().test_client()
    revision = client.get('/api/presets/detail/global::broken.json').get_json()['preset']['source_revision']
    res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::broken.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Recovered',
                'temp': 0.8,
                'extensions': {'regex_scripts': []},
            },
        },
    )

    assert res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload == {
        '__st_manager_preset_kind': 'generic',
        'name': 'Recovered',
        'temp': 0.8,
        'extensions': {'regex_scripts': []},
    }
