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
        lambda: {
            'presets_dir': str(presets_dir),
            'resources_dir': str(tmp_path / 'resources'),
            'st_openai_preset_dir': '',
            'st_textgen_preset_dir': '',
            'st_instruct_preset_dir': '',
            'st_context_preset_dir': '',
            'st_sysprompt_dir': '',
            'st_reasoning_dir': '',
        },
    )


def test_chat_completion_mirror_detail_save_reload_round_trip(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'chat.json'
    _write_json(
        preset_file,
        {
            'name': 'Chat',
            'temperature': 0.7,
            'top_p': 0.9,
            'frequency_penalty': 0.1,
            'presence_penalty': 0.2,
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'reasoning_effort': 'medium',
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)
    client = _make_test_app().test_client()

    detail = client.get('/api/presets/detail/global::chat.json').get_json()['preset']
    assert detail['editor_profile']['id'] == 'st_chat_completion_preset'
    revision = detail['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': 'global::chat.json',
            'preset_kind': 'textgen',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Chat',
                'temperature': 1.25,
                'top_p': 0.75,
                'frequency_penalty': 0.5,
                'presence_penalty': 0.4,
                'openai_max_context': 12288,
                'openai_max_tokens': 1400,
                'stream_openai': False,
                'reasoning_effort': 'high',
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    reloaded = client.get('/api/presets/detail/global::chat.json').get_json()['preset']
    assert reloaded['editor_profile']['id'] == 'st_chat_completion_preset'
    assert reloaded['raw_data']['temperature'] == 1.25
    assert reloaded['raw_data']['top_p'] == 0.75
    assert reloaded['raw_data']['stream_openai'] is False
    assert reloaded['raw_data']['reasoning_effort'] == 'high'


def test_textgen_mirror_detail_save_reload_preserves_alias_storage_key(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'textgen.json'
    _write_json(
        preset_file,
        {
            'name': 'Textgen',
            'temp': 0.7,
            'rep_pen': 1.1,
            'top_p': 0.92,
            'streaming': True,
            'prompts': [{'identifier': 'main', 'content': 'hello'}],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)
    client = _make_test_app().test_client()

    detail = client.get('/api/presets/detail/global::textgen.json').get_json()['preset']
    assert detail['editor_profile']['id'] == 'st_textgen_preset'
    revision = detail['source_revision']

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
                'repetition_penalty': 1.45,
                'top_p': 0.88,
                'streaming': False,
                'prompts': [{'identifier': 'main', 'content': 'hello'}],
            },
        },
    )

    assert save_res.status_code == 200
    payload = json.loads(preset_file.read_text(encoding='utf-8'))
    assert payload['rep_pen'] == 1.45
    assert 'repetition_penalty' not in payload

    reloaded = client.get('/api/presets/detail/global::textgen.json').get_json()['preset']
    assert reloaded['editor_profile']['id'] == 'st_textgen_preset'
    assert reloaded['raw_data']['rep_pen'] == 1.45
    assert reloaded['raw_data']['streaming'] is False
