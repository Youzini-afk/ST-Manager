import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_PRESET_FILENAMES = (
    'Ny-Gemini-1.3.9-pro_Sigon.json',
    '双人成行 V3.5 光头强—PrismFox.json',
)


def _resolve_workspace_root():
    for candidate in (ROOT, *ROOT.parents):
        sample_dir = candidate / 'data' / 'library' / 'presets'
        if all((sample_dir / filename).exists() for filename in SAMPLE_PRESET_FILENAMES):
            return candidate
    return ROOT


WORKSPACE_ROOT = _resolve_workspace_root()


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
        },
    )


def _configure_workspace_samples(monkeypatch):
    monkeypatch.setattr(presets_api, 'BASE_DIR', str(WORKSPACE_ROOT))
    monkeypatch.setattr(
        presets_api,
        'load_config',
        lambda: {
            'presets_dir': 'data/library/presets',
            'resources_dir': 'data/assets/card_assets',
            'st_openai_preset_dir': '',
        },
    )


def test_sample_gemini_preset_is_detected_as_openai_profile(monkeypatch):
    _configure_workspace_samples(monkeypatch)
    client = _make_test_app().test_client()

    res = client.get('/api/presets/detail/global::Ny-Gemini-1.3.9-pro_Sigon.json')

    assert res.status_code == 200
    preset = res.get_json()['preset']
    assert preset['editor_profile']['id'] == 'st_chat_completion_preset'
    assert preset['preset_kind'] == 'openai'
    assert preset['reader_view']['family'] == 'prompt_manager'


def test_sample_prismfox_preset_is_detected_as_openai_profile(monkeypatch):
    _configure_workspace_samples(monkeypatch)
    client = _make_test_app().test_client()

    res = client.get('/api/presets/detail/global::双人成行 V3.5 光头强—PrismFox.json')

    assert res.status_code == 200
    preset = res.get_json()['preset']
    assert preset['editor_profile']['id'] == 'st_chat_completion_preset'
    assert preset['preset_kind'] == 'openai'
    assert preset['reader_view']['family'] == 'prompt_manager'


def test_openai_profile_round_trip_preserves_reasoning_and_connection_fields(monkeypatch, tmp_path):
    presets_dir = tmp_path / 'presets'
    preset_file = presets_dir / 'round-trip.json'
    _write_json(
        preset_file,
        {
            'name': 'Round Trip',
            'chat_completion_source': 'custom',
            'custom_url': 'https://example.test/v1',
            'proxy_password': 'secret',
            'openai_max_context': 8192,
            'openai_max_tokens': 1200,
            'stream_openai': True,
            'reasoning_effort': 'medium',
            'prompts': [{'identifier': 'main', 'role': 'system', 'content': 'hello'}],
            'prompt_order': ['main'],
        },
    )

    _configure(monkeypatch, tmp_path, presets_dir)
    client = _make_test_app().test_client()

    detail = client.get('/api/presets/detail/global::round-trip.json').get_json()['preset']
    assert detail['preset_kind'] == 'openai'
    assert detail['editor_profile']['id'] == 'st_chat_completion_preset'
    revision = detail['source_revision']

    save_res = client.post(
        '/api/presets/save',
        json={
            'preset_id': detail['id'],
            'preset_kind': 'openai',
            'save_mode': 'overwrite',
            'source_revision': revision,
            'content': {
                'name': 'Round Trip',
                'chat_completion_source': 'custom',
                'custom_url': 'https://example.test/v2',
                'proxy_password': 'secret-2',
                'openai_max_tokens': 1400,
                'stream_openai': False,
                'reasoning_effort': 'high',
                'openai_max_context': 8192,
                'prompts': [{'identifier': 'main', 'role': 'system', 'content': 'hello'}],
                'prompt_order': ['main'],
            },
        },
    )

    assert save_res.status_code == 200
    reloaded = client.get('/api/presets/detail/global::round-trip.json').get_json()['preset']
    payload = json.loads(preset_file.read_text(encoding='utf-8'))

    assert reloaded['editor_profile']['id'] == 'st_chat_completion_preset'
    assert reloaded['preset_kind'] == 'openai'
    assert reloaded['raw_data']['custom_url'] == 'https://example.test/v2'
    assert reloaded['raw_data']['proxy_password'] == 'secret-2'
    assert reloaded['raw_data']['stream_openai'] is False
    assert reloaded['raw_data']['reasoning_effort'] == 'high'
    assert payload['custom_url'] == 'https://example.test/v2'
    assert payload['proxy_password'] == 'secret-2'
    assert payload['reasoning_effort'] == 'high'
