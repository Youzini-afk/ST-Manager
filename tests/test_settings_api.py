import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import system as system_api
from core.config import build_default_config


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(system_api.bp)
    return app


def test_build_default_config_includes_profile_specific_preset_directories():
    cfg = build_default_config()

    assert cfg['st_openai_preset_dir'] == ''
    assert cfg['st_textgen_preset_dir'] == ''
    assert cfg['st_instruct_preset_dir'] == ''
    assert cfg['st_context_preset_dir'] == ''
    assert cfg['st_sysprompt_dir'] == ''
    assert cfg['st_reasoning_dir'] == ''


def test_get_settings_returns_profile_specific_preset_directories(monkeypatch):
    monkeypatch.setattr(
        system_api,
        'load_config',
        lambda: {
            'cards_dir': 'cards',
            'world_info_dir': 'worlds',
            'chats_dir': 'chats',
            'presets_dir': 'presets',
            'quick_replies_dir': 'quick',
            'default_sort': 'date_desc',
            'show_header_sort': True,
            'st_openai_preset_dir': 'st/openai',
            'st_textgen_preset_dir': 'st/textgen',
            'st_instruct_preset_dir': 'st/instruct',
            'st_context_preset_dir': 'st/context',
            'st_sysprompt_dir': 'st/sysprompt',
            'st_reasoning_dir': 'st/reasoning',
        },
    )

    client = _make_test_app().test_client()
    res = client.get('/api/get_settings')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['st_openai_preset_dir'] == 'st/openai'
    assert payload['st_textgen_preset_dir'] == 'st/textgen'
    assert payload['st_instruct_preset_dir'] == 'st/instruct'
    assert payload['st_context_preset_dir'] == 'st/context'
    assert payload['st_sysprompt_dir'] == 'st/sysprompt'
    assert payload['st_reasoning_dir'] == 'st/reasoning'
