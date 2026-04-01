import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.automation.template_runtime import (
    build_safe_filename_result,
    build_snapshot_template_fields,
    render_template_fields,
)


def test_build_snapshot_template_fields_exposes_shared_snapshot_values():
    card = {
        'id': 'folder/sub/demo.card.json',
        'filename': 'demo.card.json',
        'category': 'folder/sub',
        'last_modified': 1704067200,
    }

    fields = build_snapshot_template_fields('folder/sub/demo.card.json', card, ui_data={})

    assert fields['filename_stem'] == 'demo.card'
    assert fields['category'] == 'folder/sub'
    assert fields['import_time'] == 1704067200.0
    assert fields['import_date'] == '2024-01-01'
    assert fields['modified_time'] == 1704067200.0
    assert fields['modified_date'] == '2024-01-01'


def test_build_snapshot_template_fields_falls_back_import_time_to_mtime():
    card = {
        'id': 'demo.json',
        'filename': 'demo.json',
        'category': '',
        'last_modified': 1704153600,
    }

    fields = build_snapshot_template_fields('demo.json', card, ui_data={})

    assert fields['import_time'] == 1704153600.0
    assert fields['import_date'] == '2024-01-02'
    assert fields['modified_time'] == 1704153600.0
    assert fields['modified_date'] == '2024-01-02'


def test_render_template_supports_snapshot_fields_and_filters():
    fields = {
        'char_name': '  Alice  ',
        'filename_stem': 'card-file',
        'char_version': ' v1.2 (beta) ',
        'import_time': 1704067200,
        'missing': None,
    }

    rendered = render_template_fields(
        '{{char_name}}|{{missing}}|{{char_name|trim}}|{{char_name|trim|limit(3)}}|'
        '{{missing|default("fallback")}}|{{import_time|date("%Y/%m/%d")}}|{{char_version|version}}',
        fields,
    )

    assert rendered == '  Alice  ||Alice|Ali|fallback|2024/01/01|v1.2'


def test_render_template_missing_values_become_empty_strings_instead_of_none():
    rendered = render_template_fields('{{char_name}}-{{unknown}}-{{char_name|default("x")}}', {'char_name': None})

    assert rendered == '--x'


def test_build_safe_filename_result_cleans_illegal_characters_and_preserves_json_extension():
    result = build_safe_filename_result(
        current_filename='Old<Name>.json',
        template='  New:<Name>?*  ',
        fields={},
        max_length=64,
    )

    assert result['stem'] == 'New__Name___'
    assert result['filename'] == 'New__Name___.json'
    assert result['extension'] == '.json'
    assert result['noop'] is False
    assert result['observability'] == {'suppressed_filename_action_conflicts': [], 'noop_rename_reasons': []}


def test_build_safe_filename_result_uses_required_fallback_order():
    result = build_safe_filename_result(
        current_filename='origin.json',
        template='   ',
        fallback_template=' {{missing}} ',
        fields={
            'filename_stem': 'from-file',
            'char_name': 'from-char',
            'card': 'from-card',
        },
        max_length=64,
    )

    assert result['stem'] == 'from-file'
    assert result['filename'] == 'from-file.json'


def test_build_safe_filename_result_detects_noop_when_stem_matches_current_filename():
    result = build_safe_filename_result(
        current_filename='Same Name.png',
        template=' Same Name ',
        fields={},
        max_length=64,
    )

    assert result['filename'] == 'Same Name.png'
    assert result['noop'] is True
    assert result['observability']['noop_rename_reasons'] == [
        {
            'reason': 'same_stem',
            'current_stem': 'Same Name',
            'candidate_stem': 'Same Name',
        }
    ]


def test_build_safe_filename_result_uses_underscore_numeric_dedupe_suffixes():
    result = build_safe_filename_result(
        current_filename='old.json',
        template='Demo Card',
        fields={},
        max_length=64,
        dedupe_index=2,
    )

    assert result['stem'] == 'Demo Card'
    assert result['filename'] == 'Demo Card_2.json'


def test_build_safe_filename_result_same_stem_with_dedupe_suffix_is_not_noop():
    result = build_safe_filename_result(
        current_filename='Same Name.png',
        template=' Same Name ',
        fields={},
        max_length=64,
        dedupe_index=2,
    )

    assert result['stem'] == 'Same Name'
    assert result['filename'] == 'Same Name_2.png'
    assert result['noop'] is False
    assert result['observability']['noop_rename_reasons'] == []


def test_build_safe_filename_result_ignores_invalid_dedupe_index_values():
    result = build_safe_filename_result(
        current_filename='old.json',
        template='Demo Card',
        fields={},
        max_length=64,
        dedupe_index='oops',
    )

    assert result['stem'] == 'Demo Card'
    assert result['filename'] == 'Demo Card.json'
    assert result['noop'] is False


def test_build_safe_filename_result_reserves_length_for_dedupe_suffix():
    result = build_safe_filename_result(
        current_filename='old.json',
        template='abcdefghij',
        fields={},
        max_length=10,
        dedupe_index=2,
    )

    assert result['stem'] == 'abcdefgh'
    assert result['filename'] == 'abcdefgh_2.json'


def test_build_safe_filename_result_avoids_windows_reserved_names():
    result = build_safe_filename_result(
        current_filename='old.json',
        template='con',
        fields={},
        max_length=32,
    )

    assert result['stem'] == '_con'
    assert result['filename'] == '_con.json'


def test_build_safe_filename_result_preserves_png_extension():
    result = build_safe_filename_result(
        current_filename='old.png',
        template='poster',
        fields={},
        max_length=32,
    )

    assert result['filename'] == 'poster.png'
    assert result['extension'] == '.png'


def test_build_safe_filename_result_reports_suppressed_conflict_details():
    result = build_safe_filename_result(
        current_filename='old.json',
        template='next',
        fields={},
        max_length=32,
        suppress_conflict={'reason': 'multiple_rename_actions', 'action_types': ['rename_file_by_template', 'set_filename_from_char_name']},
    )

    assert result['filename'] == 'old.json'
    assert result['suppressed'] is True
    assert result['observability']['suppressed_filename_action_conflicts'] == [
        {
            'reason': 'multiple_rename_actions',
            'action_types': ['rename_file_by_template', 'set_filename_from_char_name'],
            'current_filename': 'old.json',
        }
    ]
