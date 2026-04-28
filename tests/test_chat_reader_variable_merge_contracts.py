from pathlib import Path
import json
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAT = (
    PROJECT_ROOT
    / 'tests'
    / 'fixtures'
    / 'chat_reader_variable_merge_contracts'
    / 'target_chat_first_message.jsonl'
)


def read_first_raw_message(path: Path):
    with path.open('r', encoding='utf-8') as handle:
        next(handle)
        return json.loads(next(handle))


def test_target_chat_first_message_active_swipe_contains_cancer_knight_name():
    message = read_first_raw_message(TARGET_CHAT)

    assert message['swipe_id'] == 1
    assert message['variables'][0]['stat_data']['人物']['名称'] == ''
    assert message['variables'][1]['stat_data']['人物']['名称'] == '癌骑士'


def test_node_variable_merge_regression_script_passes():
    result = subprocess.run(
        ['node', 'tests/chat_reader_variable_merge_test.mjs'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert 'chat_reader_variable_merge_test: ok' in result.stdout


def test_chat_grid_uses_floor_variable_snapshot_pipeline_for_mvu_context():
    source = (PROJECT_ROOT / 'static' / 'js' / 'components' / 'chatGrid.js').read_text(encoding='utf-8')

    assert 'createFloorVariableSnapshotResolver' in source
    assert 'getActiveMessageVariables' in source
    assert 'resolveReaderFloorVariables(' in source
    assert re.search(
        r'const\s+floorVariables\s*=\s*resolveReaderFloorVariables\(\s*rawMessages,\s*floor,\s*chat,\s*activeCardDetail,\s*\);',
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert 'merged_variables: cloneValue(floorVariables),' in source
    assert 'active_variables: activeVariables,' in source
