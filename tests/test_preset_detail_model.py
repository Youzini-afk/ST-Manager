import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import presets as presets_api
from core.services import preset_model


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(presets_api.bp)
    return app


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def test_preset_detail_identifies_textgen_and_returns_sections(monkeypatch, tmp_path):
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
    assert payload['preset']['has_unknown_fields'] is True
    assert 'custom_flag' in payload['preset']['unknown_fields']


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


def test_preset_detail_builds_reader_view_for_openai_chat_shape(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    _write_json(
        presets_dir / 'openai-chat.json',
        {
            'name': 'OpenAI Chat',
            'temp': 0.8,
            'prompts': [
                {'identifier': 'main', 'name': 'Main Prompt', 'role': 'system', 'content': '你是助手', 'enabled': True},
                {'identifier': 'summary', 'role': 'system', 'content': '总结要点'},
            ],
            'prompt_order': ['main', 'summary'],
            'extensions': {
                'memory': {'enabled': True},
            },
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
    res = client.get('/api/presets/detail/global::openai-chat.json')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True

    preset = payload['preset']
    assert preset['preset_kind'] == 'textgen'
    reader_view = preset['reader_view']
    assert reader_view['family'] == 'openai_chat'
    assert reader_view['family_label'] == 'OpenAI Chat'
    assert 'groups' in reader_view
    assert 'items' in reader_view
    assert 'stats' in reader_view

    group_ids = [group['id'] for group in reader_view['groups']]
    assert 'prompt_items' in group_ids
    assert 'prompt_order' in group_ids
    assert 'extensions' in group_ids

    prompt_items = [item for item in reader_view['items'] if item['type'] == 'prompt']
    prompt_order_items = [item for item in reader_view['items'] if item['type'] == 'prompt_order']
    extension_items = [item for item in reader_view['items'] if item['group'] == 'extensions']

    assert len(prompt_items) == 2
    assert len(prompt_order_items) == 2
    assert extension_items
    assert reader_view['stats']['prompt_count'] == 2
    assert reader_view['stats']['unknown_count'] == 1

    first_prompt = prompt_items[0]
    assert first_prompt['id']
    assert first_prompt['title'] == 'Main Prompt'
    assert isinstance(first_prompt['summary'], str)
    assert first_prompt['payload']['identifier'] == 'main'

    first_order = prompt_order_items[0]
    assert first_order['payload']['identifier'] == 'main'

    assert 'prompts' not in preset['unknown_fields']
    assert 'prompt_order' not in preset['unknown_fields']
    assert 'extensions' not in preset['unknown_fields']
    assert 'custom_flag' in preset['unknown_fields']


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
    assert reader_view['stats']['unknown_count'] == 1

    group_ids = [group['id'] for group in reader_view['groups']]
    assert 'structured_objects' in group_ids
    assert 'scalar_fields' in group_ids
    assert 'unknown_fields' in group_ids

    assert all('id' in item and 'title' in item and 'payload' in item for item in reader_view['items'])


def test_detect_reader_family_recognizes_openai_chat_variants():
    assert (
        preset_model.detect_reader_family(
            {'prompts': [{'identifier': 'main', 'role': 'system', 'content': 'x'}]},
            'textgen',
        )
        == 'openai_chat'
    )
    assert preset_model.detect_reader_family({'prompt_order': ['main']}, 'textgen') == 'openai_chat'
    assert (
        preset_model.detect_reader_family(
            {'openai_model': 'gpt-4o-mini', 'prompts': [{'identifier': 'main'}]},
            'textgen',
        )
        == 'openai_chat'
    )
    assert (
        preset_model.detect_reader_family(
            {'chat_completion_source': 'openai', 'prompt_order': ['main']},
            'textgen',
        )
        == 'openai_chat'
    )
    assert (
        preset_model.detect_reader_family(
            {'prompts': [{'identifier': 'main'}]},
            'textgen',
            source_folder='presets/openai',
        )
        == 'openai_chat'
    )
    assert (
        preset_model.detect_reader_family(
            {'prompt_order': ['main']},
            'textgen',
            file_path='D:/data/textgen/openai-chat.json',
        )
        == 'openai_chat'
    )


def test_detect_reader_family_keeps_generic_for_malformed_textgen_data():
    assert (
        preset_model.detect_reader_family(
            {'prompts': {'main': 'bad-shape'}, 'prompt_order': 'not-a-list'},
            'textgen',
        )
        == 'generic'
    )
    assert preset_model.detect_reader_family({'prompts': {'main': 'bad-shape'}}, 'textgen') == 'generic'
    assert preset_model.detect_reader_family({'prompt_order': 'not-a-list'}, 'textgen') == 'generic'
    assert (
        preset_model.detect_reader_family(
            {'prompts': [{'identifier': 'main'}], 'prompt_order': 'not-a-list'},
            'textgen',
        )
        == 'generic'
    )
    assert (
        preset_model.detect_reader_family(
            {'prompts': {'main': 'bad-shape'}, 'prompt_order': ['main']},
            'textgen',
        )
        == 'generic'
    )
    assert (
        preset_model.detect_reader_family(
            {'prompts': ['bad-shape', {'identifier': 'main'}]},
            'textgen',
        )
        == 'generic'
    )


def test_detect_reader_family_does_not_upgrade_plain_textgen_from_path_or_vendor_field_only():
    assert preset_model.detect_reader_family({'openai_model': 'gpt-4o-mini', 'temp': 0.8}, 'textgen') == 'generic'
    assert (
        preset_model.detect_reader_family({'temp': 0.8}, 'textgen', source_folder='presets/openai')
        == 'generic'
    )
    assert (
        preset_model.detect_reader_family({'temp': 0.8}, 'textgen', file_path='D:/data/openai/textgen.json')
        == 'generic'
    )
