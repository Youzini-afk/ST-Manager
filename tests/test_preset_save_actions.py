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
        'name': 'Recovered',
        'temp': 0.8,
        'extensions': {'regex_scripts': []},
    }
