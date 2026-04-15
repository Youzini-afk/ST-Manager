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


def test_preset_detail_returns_source_revision_but_not_display_only_metadata(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'textgen-main.json',
        {
            'name': 'Textgen Main',
            'temp': 0.95,
            'top_p': 0.9,
            'top_k': 40,
            'repetition_penalty': 1.1,
            'json_schema': '{"type":"object"}',
            'extensions': {'regex_scripts': []},
            'custom_flag': True,
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::textgen-main.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['preset']['preset_kind'] == 'textgen'
    assert payload['preset']['source_revision']
    assert payload['preset']['sections']['sampling'][0]['key'] == 'temp'
    assert 'capabilities' not in payload['preset']
    assert 'has_unknown_fields' not in payload['preset']
    assert 'unknown_fields' not in payload['preset']


def test_preset_detail_identifies_sysprompt_by_shape_when_folder_missing(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'prompt.json',
        {
            'name': 'Sys Prompt',
            'content': '你是助手',
            'post_history': True,
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::prompt.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['preset']['preset_kind'] == 'sysprompt'
    assert payload['preset']['preset_kind_label'] == '系统提示词'
    assert payload['preset']['sections']['prompt'][0]['key'] == 'content'


def test_preset_detail_identifies_instruct_context_and_reasoning(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'instruct.json',
        {
            'name': 'Instruct',
            'input_sequence': 'User:',
            'output_sequence': 'Assistant:',
            'system_sequence': 'System:',
        },
    )
    _write_json(
        presets_dir / 'context.json',
        {
            'name': 'Context',
            'story_string': '{{char}}',
            'chat_start': '###',
        },
    )
    _write_json(
        presets_dir / 'reasoning.json',
        {
            'name': 'Reasoning',
            'prefix': '<think>',
            'suffix': '</think>',
            'separator': '\n',
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    instruct = client.get('/api/presets/detail/global::instruct.json').get_json()['preset']
    context = client.get('/api/presets/detail/global::context.json').get_json()['preset']
    reasoning = client.get('/api/presets/detail/global::reasoning.json').get_json()['preset']

    assert instruct['preset_kind'] == 'instruct'
    assert 'sequences' in instruct['sections']
    assert context['preset_kind'] == 'context'
    assert 'story' in context['sections']
    assert reasoning['preset_kind'] == 'reasoning'
    assert 'template' in reasoning['sections']


def test_preset_detail_reader_view_uses_prompt_manager_family_for_prompt_presets(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'openai-chat.json',
        {
            'name': 'OpenAI Chat',
            'temperature': 0.8,
            'prompts': [
                {
                    'identifier': 'main',
                    'name': 'Main Prompt',
                    'role': 'system',
                    'content': '你是助手',
                    'system_prompt': True,
                },
                {
                    'identifier': 'worldInfoAfter',
                    'name': 'World Info (after)',
                    'system_prompt': True,
                    'marker': True,
                },
                {
                    'identifier': 'summary',
                    'name': 'Summary',
                    'role': 'assistant',
                    'content': '总结要点',
                },
            ],
            'prompt_order': ['summary', 'main'],
            'extensions': {'memory': {'enabled': True}},
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::openai-chat.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    reader_view = preset['reader_view']
    prompt_items = [item for item in reader_view['items'] if item['type'] == 'prompt']

    assert reader_view['family'] == 'prompt_manager'
    assert reader_view['family_label'] == 'Prompt Manager 预设'
    assert [group['id'] for group in reader_view['groups']][0] == 'prompts'
    assert 'prompt_order' not in [group['id'] for group in reader_view['groups']]
    assert [item['payload']['identifier'] for item in prompt_items] == ['summary', 'main', 'worldInfoAfter']
    assert prompt_items[0]['editor']['kind'] == 'prompt-manager-item'
    assert prompt_items[0]['reorderable'] is True
    assert prompt_items[0]['prompt_meta']['identifier'] == 'summary'
    assert prompt_items[0]['prompt_meta']['is_enabled'] is True
    assert prompt_items[0]['prompt_meta']['content_editable'] is True
    assert prompt_items[0]['prompt_meta']['uses_prompt_order'] is True
    assert prompt_items[0]['prompt_meta']['order_index'] == 0
    assert prompt_items[0]['prompt_meta']['is_orphan'] is False
    assert '启用' in prompt_items[0]['summary']
    assert '相对位置' in prompt_items[0]['summary']
    assert prompt_items[2]['prompt_meta']['is_marker'] is True
    assert prompt_items[2]['content_editable'] is False
    assert prompt_items[2]['prompt_meta']['content_editable'] is False
    assert prompt_items[2]['prompt_meta']['is_orphan'] is True
    assert '预留字段' in prompt_items[2]['summary']


def test_preset_detail_reader_view_reads_enabled_state_from_nested_st_prompt_order(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'st-openai.json',
        {
            'name': 'ST OpenAI',
            'prompts': [
                {
                    'identifier': 'main',
                    'name': 'Main Prompt',
                    'role': 'system',
                    'content': '你是助手',
                    'system_prompt': True,
                },
                {
                    'identifier': 'worldInfoBefore',
                    'name': 'World Info (before)',
                    'system_prompt': True,
                    'marker': True,
                },
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

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::st-openai.json')

    assert res.status_code == 200
    payload = res.get_json()
    prompt_items = [item for item in payload['preset']['reader_view']['items'] if item['type'] == 'prompt']

    assert [item['payload']['identifier'] for item in prompt_items] == ['worldInfoBefore', 'main']
    assert prompt_items[0]['prompt_meta']['is_enabled'] is False
    assert prompt_items[0]['prompt_meta']['uses_prompt_order'] is True
    assert prompt_items[0]['content_editable'] is False
    assert '禁用' in prompt_items[0]['summary']


def test_preset_detail_reader_view_uses_prompt_enabled_state_for_simple_prompt_order(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'simple-openai.json',
        {
            'name': 'Simple OpenAI',
            'prompts': [
                {
                    'identifier': 'main',
                    'name': 'Main Prompt',
                    'role': 'system',
                    'content': '你是助手',
                    'enabled': False,
                },
                {
                    'identifier': 'summary',
                    'name': 'Summary',
                    'role': 'assistant',
                    'content': '总结要点',
                    'enabled': True,
                },
            ],
            'prompt_order': ['main', 'summary'],
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::simple-openai.json')

    assert res.status_code == 200
    payload = res.get_json()
    prompt_items = [item for item in payload['preset']['reader_view']['items'] if item['type'] == 'prompt']

    assert [item['payload']['identifier'] for item in prompt_items] == ['main', 'summary']
    assert prompt_items[0]['prompt_meta']['uses_prompt_order'] is True
    assert prompt_items[0]['prompt_meta']['is_enabled'] is False
    assert '禁用' in prompt_items[0]['summary']


def test_preset_detail_reader_view_handles_malformed_prompt_position_values(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'bad-position.json',
        {
            'name': 'Bad Position',
            'prompts': [
                {
                    'identifier': 'main',
                    'name': 'Main Prompt',
                    'role': 'system',
                    'content': '你是助手',
                    'injection_position': 'oops',
                    'injection_depth': 'NaN',
                },
            ],
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::bad-position.json')

    assert res.status_code == 200
    payload = res.get_json()
    prompt_items = [item for item in payload['preset']['reader_view']['items'] if item['type'] == 'prompt']

    assert len(prompt_items) == 1
    assert '相对位置' in prompt_items[0]['summary']


def test_preset_detail_handles_non_dict_json_root(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(presets_dir / 'list-root.json', ['bad', 'root'])

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::list-root.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    assert preset['name'] == 'list-root'
    assert preset['extensions'] == {}
    assert preset['reader_view']['family'] == 'generic'
    assert preset['reader_view']['items'] == []


def test_preset_detail_reader_view_has_generic_fallback(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'malformed.json',
        {
            'name': 'Malformed',
            'prompt_order': 'not-a-list',
            'prompts': {'main': 'bad-shape'},
            'custom_flag': 'x',
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::malformed.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    assert 'reader_view' in preset
    reader_view = preset['reader_view']
    assert reader_view['family'] == 'generic'
    assert reader_view['family_label'] == '通用预设'
    assert reader_view['groups']
    assert reader_view['stats']['prompt_count'] == 0

    group_ids = [group['id'] for group in reader_view['groups']]
    assert 'structured_objects' in group_ids
    assert 'scalar_fields' in group_ids
    assert 'unknown_fields' not in group_ids

    assert all('id' in item and 'title' in item and 'payload' in item for item in reader_view['items'])


def test_preset_detail_reader_items_expose_scalar_editor_metadata(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'textgen.json',
        {
            'name': 'Textgen',
            'temp': 0.8,
            'top_p': 0.92,
            'do_sample': True,
            'negative_prompt': 'avoid repetition',
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::textgen.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    items = preset['reader_view']['items']

    temp_items = [item for item in items if item['group'] == 'scalar_fields' and item['payload']['key'] == 'temp']
    do_sample_items = [
        item for item in items if item['group'] == 'scalar_fields' and item['payload']['key'] == 'do_sample'
    ]
    negative_prompt_items = [
        item
        for item in items
        if item['group'] == 'scalar_fields' and item['payload']['key'] == 'negative_prompt'
    ]

    assert len(temp_items) == 1
    assert len(do_sample_items) == 1
    assert len(negative_prompt_items) == 1

    temp_item = temp_items[0]
    do_sample_item = do_sample_items[0]
    negative_prompt_item = negative_prompt_items[0]

    assert temp_item['editable'] is True
    assert temp_item['source_key'] == 'temp'
    assert temp_item['value_path'] == 'temp'
    assert temp_item['editor']['kind'] == 'number'

    assert do_sample_item['editor']['kind'] == 'boolean'
    assert negative_prompt_item['editor']['kind'] == 'textarea'


def test_preset_detail_reader_items_expose_logit_bias_editor_metadata(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'textgen-bias.json',
        {
            'name': 'Textgen Bias',
            'temp': 0.8,
            'logit_bias': [
                {'text': 'forbidden', 'value': -10},
            ],
        },
    )

    monkeypatch.setattr(presets_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {'presets_dir': str(presets_dir), 'resources_dir': str(tmp_path / 'resources')},
    )

    client = _make_test_app().test_client()
    res = client.get('/api/presets/detail/global::textgen-bias.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    items = preset['reader_view']['items']

    bias_items = [
        item for item in items if item['group'] == 'structured_objects' and item['payload']['key'] == 'logit_bias'
    ]

    assert len(bias_items) == 1

    bias_item = bias_items[0]

    assert bias_item['editable'] is True
    assert bias_item['source_key'] == 'logit_bias'
    assert bias_item['value_path'] == 'logit_bias'
    assert bias_item['editor']['kind'] == 'key-value-list'
