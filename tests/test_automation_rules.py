import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.automation.engine import AutomationEngine
from core.services import automation_service


def _make_ruleset(field, value, *, case_sensitive=False, action_type='add_tag', action_value='matched'):
    return {
        'rules': [
            {
                'name': f'rule_for_{field}',
                'enabled': True,
                'groups': [
                    {
                        'logic': 'AND',
                        'conditions': [
                            {
                                'field': field,
                                'operator': 'contains',
                                'value': value,
                                'case_sensitive': case_sensitive,
                            }
                        ],
                    }
                ],
                'actions': [{'type': action_type, 'value': action_value}],
            }
        ]
    }


def test_automation_engine_contains_ignores_case_when_case_sensitive_false():
    engine = AutomationEngine()
    card_data = {
        'extensions': {
            'regex_scripts': [
                {'scriptName': 'RegexOne', 'findRegex': 'Foo.*Bar'},
            ]
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('regex_content', 'foo', case_sensitive=False),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == [{'type': 'add_tag', 'value': 'matched'}]


def test_automation_engine_contains_respects_case_when_case_sensitive_true():
    engine = AutomationEngine()
    card_data = {
        'extensions': {
            'regex_scripts': [
                {'scriptName': 'RegexOne', 'findRegex': 'Foo.*Bar'},
            ]
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('regex_content', 'foo', case_sensitive=True),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == []


def test_automation_engine_wi_name_matches_title_only_entries():
    engine = AutomationEngine()
    card_data = {
        'character_book': {
            'entries': [
                {'title': 'OnlyTitle', 'content': 'LoreBeta'},
            ]
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('wi_name', 'Only', case_sensitive=False),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == [{'type': 'add_tag', 'value': 'matched'}]


def test_auto_run_rules_on_card_loads_deep_fields_from_card_file(tmp_path, monkeypatch):
    cards_root = tmp_path / 'cards'
    card_path = cards_root / 'folder' / 'demo.json'
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text('{}', encoding='utf-8')

    ruleset = _make_ruleset('wi_content', 'Lore', case_sensitive=False)
    captured = {}

    fake_cache = SimpleNamespace(
        id_map={
            'folder/demo.json': {
                'id': 'folder/demo.json',
                'filename': 'demo.json',
                'char_name': 'Demo',
                'tags': [],
            }
        },
        bundle_map={},
    )

    monkeypatch.setattr(automation_service, 'CARDS_FOLDER', str(cards_root), raising=False)
    monkeypatch.setattr(
        automation_service,
        'extract_card_info',
        lambda path: {
            'data': {
                'character_book': {
                    'entries': [
                        {'comment': 'EntryTitle', 'content': 'LoreBeta'},
                    ]
                }
            }
        },
        raising=False,
    )
    monkeypatch.setattr(
        automation_service,
        'load_config',
        lambda: {
            'active_automation_ruleset': 'ruleset-1',
            'automation_slash_is_tag_separator': False,
        },
    )
    monkeypatch.setattr(automation_service.rule_manager, 'get_ruleset', lambda ruleset_id: ruleset)
    monkeypatch.setattr(automation_service.ctx, 'cache', fake_cache, raising=False)
    monkeypatch.setattr(automation_service, 'load_ui_data', lambda: {})
    monkeypatch.setattr(automation_service, 'resolve_ui_key', lambda card_id: card_id)

    def _fake_apply_plan(card_id, plan, ui_data):
        captured['card_id'] = card_id
        captured['plan'] = plan
        return {
            'moved_to': None,
            'tags_added': list(plan.get('add_tags', [])),
            'tags_removed': [],
            'fav_changed': False,
            'name_sync': None,
            'forum_tags_fetched': None,
            'final_id': card_id,
        }

    monkeypatch.setattr(automation_service.executor, 'apply_plan', _fake_apply_plan)

    result = automation_service.auto_run_rules_on_card('folder/demo.json')

    assert result is not None
    assert result['run'] is True
    assert captured['card_id'] == 'folder/demo.json'
    assert captured['plan']['add_tags'] == {'matched'}


def test_automation_engine_reads_st_helper_dict_structure():
    engine = AutomationEngine()
    card_data = {
        'extensions': {
            'tavern_helper': {
                'scripts': [
                    {'name': 'ScriptDict', 'content': 'console.log("dict")'},
                ],
                'variables': {},
            }
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('st_script_content', 'dict', case_sensitive=False),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == [{'type': 'add_tag', 'value': 'matched'}]


def test_automation_engine_reads_st_helper_list_structure():
    engine = AutomationEngine()
    card_data = {
        'extensions': {
            'tavern_helper': [
                ['scripts', [
                    {'name': 'ScriptList', 'content': 'console.log("list")'},
                ]],
                ['variables', {}],
            ]
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('st_script_content', 'list', case_sensitive=False),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == [{'type': 'add_tag', 'value': 'matched'}]


def test_automation_engine_reads_st_helper_legacy_structure():
    engine = AutomationEngine()
    card_data = {
        'extensions': {
            'TavernHelper_scripts': [
                {
                    'type': 'script',
                    'value': {'name': 'ScriptLegacy', 'content': 'console.log("legacy")'},
                }
            ]
        }
    }

    plan = engine.evaluate(
        card_data,
        _make_ruleset('st_script_content', 'legacy', case_sensitive=False),
        match_if_no_conditions=True,
    )

    assert plan['actions'] == [{'type': 'add_tag', 'value': 'matched'}]
