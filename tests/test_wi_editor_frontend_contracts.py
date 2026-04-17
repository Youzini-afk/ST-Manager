from pathlib import Path
import re
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def extract_js_function_block(source: str, signature: str) -> str:
    start = source.index(signature)
    brace_start = source.index('{', start)
    depth = 1
    index = brace_start + 1
    while depth > 0:
        char = source[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        index += 1
    return source[start:index]


def run_js(script: str) -> None:
    subprocess.run(
        ['node', '-e', script],
        cwd=ROOT,
        check=True,
        text=True,
    )


def test_wi_editor_runtime_maps_position_and_role_to_unique_select_values():
    source = read_project_file('static/js/components/wiEditor.js')
    get_block = extract_js_function_block(source, 'getEditorPositionSelectValue(entry) {')
    update_block = extract_js_function_block(source, 'updateEditorPositionFromSelect(entry, rawValue) {')

    script = textwrap.dedent(
        f'''
        const component = {{
          {get_block}
          ,
          {update_block}
        }};

        if (component.getEditorPositionSelectValue({{ position: 4, role: 0 }}) !== '4:0') {{
          throw new Error('expected system at-depth select value');
        }}
        if (component.getEditorPositionSelectValue({{ position: 4, role: 1 }}) !== '4:1') {{
          throw new Error('expected user at-depth select value');
        }}
        if (component.getEditorPositionSelectValue({{ position: 4, role: 2 }}) !== '4:2') {{
          throw new Error('expected assistant at-depth select value');
        }}
        if (component.getEditorPositionSelectValue({{ position: 4, role: 99 }}) !== '4:0') {{
          throw new Error('expected invalid role to fall back to system');
        }}

        const depthEntry = {{ position: 1, role: null }};
        component.updateEditorPositionFromSelect(depthEntry, '4:2');
        if (depthEntry.position !== 4 || depthEntry.role !== 2) {{
          throw new Error('expected at-depth assistant writeback');
        }}

        component.updateEditorPositionFromSelect(depthEntry, '3');
        if (depthEntry.position !== 3 || depthEntry.role !== null) {{
          throw new Error('expected non-depth selection to clear role');
        }}
        '''
    )

    run_js(script)


def test_wi_editor_runtime_preserves_non_depth_positions_and_defaults_invalid_position():
    source = read_project_file('static/js/components/wiEditor.js')
    get_block = extract_js_function_block(source, 'getEditorPositionSelectValue(entry) {')
    update_block = extract_js_function_block(source, 'updateEditorPositionFromSelect(entry, rawValue) {')

    script = textwrap.dedent(
        f'''
        const component = {{
          {get_block},
          {update_block}
        }};

        if (component.getEditorPositionSelectValue({{ position: 6, role: 2 }}) !== '6') {{
          throw new Error('expected non-depth position passthrough');
        }}

        const entry = {{ position: 4, role: 2 }};
        component.updateEditorPositionFromSelect(entry, 'bad-value');
        if (entry.position !== 1 || entry.role !== null) {{
          throw new Error('expected invalid select value to fall back to position 1 and clear role');
        }}
        '''
    )

    run_js(script)


def test_wi_editor_logic_select_matches_sillytavern_value_semantics():
    template = read_project_file('templates/modals/detail_wi_fullscreen.html')
    match = re.search(
        r'<select[^>]*x-model\.number="activeEditorEntry\.selectiveLogic"[^>]*>(.*?)</select>',
        template,
        re.S,
    )

    assert match, 'logic select should exist in fullscreen editor template'

    options = [
        (value, label.strip())
        for value, label in re.findall(r'<option\s+value="([^"]+)">(.*?)</option>', match.group(1), re.S)
    ]

    assert [value for value, _ in options] == ['0', '3', '1', '2']

    labels = {value: label for value, label in options}
    assert 'AND ANY' in labels['0']
    assert 'AND ALL' in labels['3']
    assert 'NOT ALL' in labels['1']
    assert 'NOT ANY' in labels['2']


def test_normalize_wi_entry_preserves_delay_until_recursion_boolean_and_numeric_semantics():
    source = read_project_file('static/js/utils/data.js')
    normalize_block = extract_js_function_block(
        source,
        'export function normalizeWiEntry(entry, index = 0) {',
    ).replace('export ', '', 1)

    script = textwrap.dedent(
        f'''
        {normalize_block}

        const asTrue = normalizeWiEntry({{ delayUntilRecursion: true }}, 0);
        if (asTrue.delayUntilRecursion !== true) {{
          throw new Error(`expected boolean true, got ${{String(asTrue.delayUntilRecursion)}}`);
        }}

        const asFalse = normalizeWiEntry({{ delayUntilRecursion: false }}, 0);
        if (asFalse.delayUntilRecursion !== false) {{
          throw new Error(`expected boolean false, got ${{String(asFalse.delayUntilRecursion)}}`);
        }}

        const asNumber = normalizeWiEntry({{ delayUntilRecursion: 3 }}, 0);
        if (asNumber.delayUntilRecursion !== 3) {{
          throw new Error(`expected numeric level 3, got ${{String(asNumber.delayUntilRecursion)}}`);
        }}
        '''
    )

    run_js(script)


def test_wi_editor_template_uses_delay_until_recursion_helpers_instead_of_numeric_x_model():
    template = read_project_file('templates/modals/detail_wi_fullscreen.html')

    assert 'x-model.number="activeEditorEntry.delayUntilRecursion"' not in template
    assert 'getDelayUntilRecursionEnabled(activeEditorEntry)' in template
    assert 'setDelayUntilRecursionEnabled(activeEditorEntry, $event.target.checked)' in template
    assert 'getDelayUntilRecursionLevel(activeEditorEntry)' in template
    assert 'setDelayUntilRecursionLevel(activeEditorEntry, $event.target.value)' in template


def test_wi_editor_runtime_delay_until_recursion_helpers_follow_st_semantics():
    source = read_project_file('static/js/components/wiEditor.js')
    get_enabled_block = extract_js_function_block(
        source,
        'getDelayUntilRecursionEnabled(entry) {',
    )
    get_level_block = extract_js_function_block(
        source,
        'getDelayUntilRecursionLevel(entry) {',
    )
    set_enabled_block = extract_js_function_block(
        source,
        'setDelayUntilRecursionEnabled(entry, enabled) {',
    )
    set_level_block = extract_js_function_block(
        source,
        'setDelayUntilRecursionLevel(entry, rawValue) {',
    )

    script = textwrap.dedent(
        f'''
        const component = {{
          {get_enabled_block},
          {get_level_block},
          {set_enabled_block},
          {set_level_block}
        }};

        const enabledOnly = {{ delayUntilRecursion: false }};
        if (component.getDelayUntilRecursionEnabled(enabledOnly) !== false) {{
          throw new Error('expected disabled state to read as false');
        }}

        component.setDelayUntilRecursionEnabled(enabledOnly, true);
        if (enabledOnly.delayUntilRecursion !== true) {{
          throw new Error(`expected enabling without level to produce boolean true, got ${{String(enabledOnly.delayUntilRecursion)}}`);
        }}
        if (component.getDelayUntilRecursionLevel(enabledOnly) !== '') {{
          throw new Error('expected boolean-only recursion delay to show blank level');
        }}

        component.setDelayUntilRecursionLevel(enabledOnly, '3');
        if (enabledOnly.delayUntilRecursion !== 3) {{
          throw new Error(`expected typed level to produce number 3, got ${{String(enabledOnly.delayUntilRecursion)}}`);
        }}
        if (component.getDelayUntilRecursionLevel(enabledOnly) !== 3) {{
          throw new Error('expected numeric recursion delay level to round-trip');
        }}

        const preLeveled = {{ delayUntilRecursion: 2 }};
        component.setDelayUntilRecursionEnabled(preLeveled, true);
        if (preLeveled.delayUntilRecursion !== 2) {{
          throw new Error('expected enabling to preserve an existing numeric level');
        }}

        component.setDelayUntilRecursionLevel(enabledOnly, '');
        if (enabledOnly.delayUntilRecursion !== true) {{
          throw new Error(`expected blank level to fall back to boolean true, got ${{String(enabledOnly.delayUntilRecursion)}}`);
        }}

        component.setDelayUntilRecursionEnabled(enabledOnly, false);
        if (enabledOnly.delayUntilRecursion !== false) {{
          throw new Error(`expected disabling to produce boolean false, got ${{String(enabledOnly.delayUntilRecursion)}}`);
        }}
      '''
    )

    run_js(script)
