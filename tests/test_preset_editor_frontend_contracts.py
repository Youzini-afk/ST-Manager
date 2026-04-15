import json
import re
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def run_preset_editor_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/components/presetEditor.js'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function presetEditor()', 'function presetEditor()');

        const stubs = `
        const createAutoSaver = () => ({{ stop() {{}}, initBaseline() {{}}, start() {{}} }});
        const apiCreateSnapshot = async () => ({{ success: true }});
        const getPresetDetail = async () => ({{ success: true, preset: {{}} }});
        const savePreset = async () => ({{ success: true }});
        const apiSavePresetExtensions = async () => ({{ success: true }});
        const estimateTokens = () => 0;
        const formatDate = (value) => value;
        const clearActiveRuntimeContext = () => {{}};
        const setActiveRuntimeContext = () => {{}};
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source + '\\nexport default presetEditor;'),
        );
        const editor = module.default();

        {textwrap.dedent(script_body)}
        """
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_preset_editor_js_exposes_reader_item_workspace_state():
    source = read_project_file('static/js/components/presetEditor.js')

    assert 'activeGroup:' in source
    assert 'activeItemId:' in source
    assert 'searchTerm:' in source
    assert 'uiFilter:' in source
    assert 'showMobileSidebar:' in source
    assert 'showRightPanel:' in source
    assert 'get editorView() {' in source
    assert 'get filteredItems() {' in source
    assert 'get activeItem() {' in source
    assert 'getByPath(path) {' in source
    assert 'setByPath(path, value) {' in source


def test_preset_editor_js_exposes_complex_editor_handlers():
    source = read_project_file('static/js/components/presetEditor.js')

    assert 'updatePromptItem(index, key, value) {' not in source
    assert 'addPromptItem() {' not in source
    assert 'removePromptItem(index) {' not in source
    assert 'moveListItem(path, fromIndex, toIndex) {' in source
    assert 'addStringListItem(path) {' in source
    assert 'updateStringListItem(path, index, value) {' in source
    assert 'removeStringListItem(path, index) {' in source
    assert 'updateBiasEntry(index, key, value) {' in source
    assert 'openAdvancedExtensions() {' in source
    assert 'deletePreset() {' in source
    assert 'rawUnknownJsonText' not in source
    assert 'applyRawUnknownJson(text) {' not in source
    assert 'removedUnknownFields' not in source
    assert 'previewRestoreDefault() {' not in source


def test_preset_editor_js_exposes_prompt_workspace_state_and_helpers():
    source = read_project_file('static/js/components/presetEditor.js')

    assert 'activeWorkspace:' in source
    assert 'activePromptId:' in source
    assert 'activeGenericItemId:' in source
    assert 'get isPromptWorkspaceEditor() {' in source
    assert 'get promptItems() {' in source
    assert 'get orderedPromptItems() {' in source
    assert 'get activePromptItem() {' in source
    assert 'get genericWorkspaceItems() {' in source
    assert 'normalizePromptOrder() {' in source
    assert 'syncPromptOrder(nextOrderedPrompts = null) {' in source
    assert 'selectWorkspace(workspaceId) {' in source
    assert 'selectPrompt(promptId) {' in source


def test_preset_editor_template_removes_prompt_and_unknown_raw_editor_sections():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')
    js_source = read_project_file('static/js/components/presetEditor.js')

    assert not re.search(r'<button\s+@click="openRawEditor\(\)"[\s\S]*?>[\s\S]*?查看原始 JSON[\s\S]*?</button>', source)
    assert not re.search(r'<button\s+@click="previewRestoreDefault\(\)"[\s\S]*?>[\s\S]*?恢复默认[\s\S]*?</button>', source)
    assert 'openRawEditor() {' not in js_source
    assert "activeItem?.editor?.kind === 'prompt-item'" not in source
    assert '未知字段检查器' not in source
    assert '高级原始编辑区' not in source
    assert '@click="applyRawUnknownJson(rawUnknownDraft)"' not in source
    assert 'rawUnknownJsonText' not in js_source
    assert 'applyRawUnknownJson(text) {' not in js_source


def test_preset_editor_runtime_rejects_invalid_bias_numbers():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          logit_bias: [{ text: 'blocked', value: -10 }],
        };

        editor.updateBiasEntry(0, 'value', '2.5');
        if (editor.editingData.logit_bias[0].value !== 2.5) {
          throw new Error(`expected numeric bias update, got ${JSON.stringify(editor.editingData.logit_bias[0])}`);
        }

        editor.updateBiasEntry(0, 'value', 'not-a-number');
        if (editor.editingData.logit_bias[0].value !== 0) {
          throw new Error(`expected invalid bias value to fall back to 0, got ${JSON.stringify(editor.editingData.logit_bias[0])}`);
        }
        """
    )


def test_preset_editor_runtime_updates_and_removes_string_list_entries_by_path():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          stop_sequence: ['alpha', 'beta', 'gamma'],
        };

        editor.updateStringListItem('stop_sequence', 1, 'BETA');
        if (JSON.stringify(editor.editingData.stop_sequence) !== JSON.stringify(['alpha', 'BETA', 'gamma'])) {
          throw new Error(`expected string list update by path, got ${JSON.stringify(editor.editingData.stop_sequence)}`);
        }

        editor.removeStringListItem('stop_sequence', 0);
        if (JSON.stringify(editor.editingData.stop_sequence) !== JSON.stringify(['BETA', 'gamma'])) {
          throw new Error(`expected string list removal by path, got ${JSON.stringify(editor.editingData.stop_sequence)}`);
        }
        """
    )


def test_preset_editor_runtime_preserves_prompt_level_enabled_fallback_for_object_and_nested_prompt_order():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt', enabled: false },
            { identifier: 'summary', name: 'Summary', enabled: false },
          ],
          prompt_order: [
            { identifier: 'main' },
            { identifier: 'summary' },
          ],
        };

        const normalized = editor.normalizePromptOrder();
        if (normalized.length !== 2 || normalized.some((entry) => entry.enabled !== null)) {
          throw new Error(`expected object prompt_order entries without enabled to preserve fallback state, got ${JSON.stringify(normalized)}`);
        }

        let ordered = editor.orderedPromptItems.map((item) => ({
          id: item.__identifier,
          enabled: item.__enabled,
        }));
        if (JSON.stringify(ordered) !== JSON.stringify([
          { id: 'main', enabled: false },
          { id: 'summary', enabled: false },
        ])) {
          throw new Error(`expected object prompt_order fallback to preserve prompt enabled state, got ${JSON.stringify(ordered)}`);
        }

        editor.editingData.prompt_order = [
          {
            character_id: 100000,
            order: [
              { identifier: 'summary' },
            ],
          },
        ];

        const nestedNormalized = editor.normalizePromptOrder();
        if (nestedNormalized.length !== 1 || nestedNormalized[0].enabled !== null) {
          throw new Error(`expected nested prompt_order entry without enabled to preserve fallback state, got ${JSON.stringify(nestedNormalized)}`);
        }

        ordered = editor.orderedPromptItems.map((item) => ({
          id: item.__identifier,
          enabled: item.__enabled,
        }));
        if (JSON.stringify(ordered) !== JSON.stringify([
          { id: 'summary', enabled: false },
          { id: 'main', enabled: false },
        ])) {
          throw new Error(`expected nested prompt_order fallback to preserve prompt enabled state, got ${JSON.stringify(ordered)}`);
        }
        """
    )


def test_preset_editor_runtime_non_prompt_presets_keep_generic_workspace_flow():
    run_preset_editor_runtime_check(
        """
        editor.editingPresetFile = {
          reader_view: {
            family: 'generic',
            groups: [
              { id: 'scalar_fields', title: 'Fields' },
            ],
            items: [
              { id: 'field:temperature', group: 'scalar_fields', title: 'Temperature', editable: true },
            ],
            stats: {},
          },
        };
        editor.editingData = { temperature: 0.7 };
        editor.activeItemId = 'field:temperature';

        if (editor.isPromptWorkspaceEditor !== false) {
          throw new Error('expected generic preset to stay out of prompt workspace mode');
        }
        if (editor.genericWorkspaceItems.length !== 1) {
          throw new Error(`expected generic workspace items to come from filteredItems, got ${editor.genericWorkspaceItems.length}`);
        }

        editor.selectWorkspace('scalar_fields');
        if (editor.activeGroup !== 'scalar_fields') {
          throw new Error(`expected generic selectWorkspace to route through group selection, got ${editor.activeGroup}`);
        }
        if (editor.activeGenericItemId !== 'field:temperature') {
          throw new Error(`expected generic item selection to persist, got ${editor.activeGenericItemId}`);
        }
        """
    )


def test_preset_editor_runtime_reorders_prompt_items_and_syncs_simple_prompt_order():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt', role: 'system', content: 'A', marker: false },
            { identifier: 'worldInfoAfter', name: 'World Info (after)', marker: true },
            { identifier: 'summary', name: 'Summary', role: 'assistant', content: 'B', marker: false },
          ],
          prompt_order: ['main', 'summary'],
        };
        editor.activePromptId = 'summary';

        editor.movePromptItem(1, 0);

        const ordered = editor.orderedPromptItems.map((item) => item.__identifier);
        if (JSON.stringify(ordered) !== JSON.stringify(['summary', 'main', 'worldInfoAfter'])) {
          throw new Error(`expected reordered prompts, got ${JSON.stringify(ordered)}`);
        }
        if (editor.editingData.prompts[0].identifier !== 'summary') {
          throw new Error(`expected prompts array reorder, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['summary', 'main', 'worldInfoAfter'])) {
          throw new Error(`expected synced simple prompt_order, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_toggles_nested_prompt_order_enabled_state():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt', role: 'system', content: 'A', marker: false },
            { identifier: 'worldInfoBefore', name: 'World Info (before)', marker: true },
          ],
          prompt_order: [
            {
              character_id: 100000,
              order: [
                { identifier: 'main', enabled: true },
                { identifier: 'worldInfoBefore', enabled: false },
              ],
            },
          ],
        };

        editor.togglePromptEnabled('worldInfoBefore');

        const nestedOrder = editor.editingData.prompt_order[0].order;
        if (nestedOrder[1].enabled !== true) {
          throw new Error(`expected nested enabled toggle, got ${JSON.stringify(nestedOrder)}`);
        }
        """
    )


def test_preset_editor_runtime_blocks_marker_content_updates():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'worldInfoAfter', name: 'World Info (after)', marker: true },
            { identifier: 'main', name: 'Main Prompt', role: 'system', content: 'A', marker: false },
          ],
          prompt_order: ['worldInfoAfter', 'main'],
        };
        editor.activePromptId = 'worldInfoAfter';

        editor.updatePromptField('content', 'should not be written');
        editor.activePromptId = 'main';
        editor.updatePromptField('content', 'updated');

        if ('content' in editor.editingData.prompts[0]) {
          throw new Error(`marker prompt content should stay absent, got ${JSON.stringify(editor.editingData.prompts[0])}`);
        }
        if (editor.editingData.prompts[1].content !== 'updated') {
          throw new Error(`non-marker prompt content should update, got ${JSON.stringify(editor.editingData.prompts[1])}`);
        }
        """
    )


def test_preset_editor_runtime_reorders_prompts_without_identifier_and_keeps_them_in_prompts_array():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { name: 'Unnamed A', content: 'A' },
            { name: 'Unnamed B', content: 'B' },
          ],
        };

        editor.movePromptItem(1, 0);

        if (editor.editingData.prompts.length !== 2) {
          throw new Error(`expected reorder to preserve prompts without identifiers, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (editor.editingData.prompts[0].name !== 'Unnamed B') {
          throw new Error(`expected unnamed prompt reorder to preserve moved item, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (Object.prototype.hasOwnProperty.call(editor.editingData, 'prompt_order')) {
          throw new Error(`expected unnamed prompt reorder to avoid persisting synthetic prompt_order, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_toggles_unnamed_prompt_enabled_without_creating_prompt_order():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { name: 'Unnamed A', enabled: true },
            { name: 'Unnamed B', enabled: true },
          ],
        };

        editor.togglePromptEnabled('prompt_2');

        if (editor.editingData.prompts[1].enabled !== false) {
          throw new Error(`expected unnamed prompt toggle to persist on prompt object, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (Object.prototype.hasOwnProperty.call(editor.editingData, 'prompt_order')) {
          throw new Error(`expected unnamed prompt toggle to avoid persisting synthetic prompt_order, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_preserves_missing_enabled_fields_when_syncing_object_prompt_order():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt', enabled: false },
            { identifier: 'summary', name: 'Summary', enabled: false },
          ],
          prompt_order: [
            { identifier: 'main' },
            { identifier: 'summary' },
          ],
        };

        editor.movePromptItem(1, 0);

        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify([
          { identifier: 'summary' },
          { identifier: 'main' },
        ])) {
          throw new Error(`expected object prompt_order sync to preserve missing enabled fields, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_ignores_reorder_for_unsupported_multi_bucket_nested_prompt_order():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt' },
            { identifier: 'summary', name: 'Summary' },
          ],
          prompt_order: [
            {
              character_id: 100000,
              order: [
                { identifier: 'main', enabled: true },
              ],
            },
            {
              character_id: 100001,
              order: [
                { identifier: 'summary', enabled: false },
              ],
            },
          ],
        };

        const beforePrompts = JSON.stringify(editor.editingData.prompts);
        const beforeOrder = JSON.stringify(editor.editingData.prompt_order);

        editor.movePromptItem(1, 0);

        if (JSON.stringify(editor.editingData.prompts) !== beforePrompts) {
          throw new Error(`expected unsupported multi-bucket reorder to leave prompts unchanged, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== beforeOrder) {
          throw new Error(`expected unsupported multi-bucket reorder to leave prompt_order unchanged, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_renames_prompt_identifier_and_keeps_prompt_order_and_selection_in_sync():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: 'Main Prompt', content: 'A' },
            { identifier: 'summary', name: 'Summary', content: 'B' },
          ],
          prompt_order: ['main', 'summary'],
        };
        editor.activePromptId = 'main';

        editor.updatePromptField('identifier', 'main-renamed');

        if (editor.activePromptId !== 'main-renamed') {
          throw new Error(`expected active prompt selection to follow renamed identifier, got ${editor.activePromptId}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['main-renamed', 'summary'])) {
          throw new Error(`expected prompt_order to stay aligned after identifier rename, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        if (editor.orderedPromptItems[0].__identifier !== 'main-renamed') {
          throw new Error(`expected ordered prompt metadata to use renamed identifier, got ${JSON.stringify(editor.orderedPromptItems.map((item) => item.__identifier))}`);
        }
        """
    )


def test_preset_editor_js_tracks_changed_state_and_safe_nested_path_writes():
    source = read_project_file('static/js/components/presetEditor.js')

    assert 'isItemDirty(item) {' in source
    assert 'return [item.value_path, item.source_key, item.key, item.id].some(' in source
    assert 'if (target[part] === null || typeof target[part] !== "object") {' in source
    assert 'markAllReaderItemsDirty() {' in source
    assert 'this.markAllReaderItemsDirty();' in source


def test_preset_editor_template_uses_three_column_workspace_contracts():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert 'x-model="searchTerm"' in source
    assert '@click="selectGroup(group.id)"' in source
    assert 'x-for="item in filteredItems"' in source
    assert '@click="selectItem(item.id)"' in source
    assert 'x-text="activeItem?.title ||' in source
    assert 'x-show="showRightPanel || $store.global.deviceType !== ' in source
    assert 'x-show="uiFilter ===' in source or 'uiFilter' in source


def test_preset_editor_template_routes_scalar_editors_through_field_helpers():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert ':value="getFieldValue(activeItem) || \'' in source
    assert '@input="setFieldValue(activeItem, $event.target.value)"' in source
    assert ':checked="Boolean(getFieldValue(activeItem))"' in source
    assert '@change="setFieldValue(activeItem, $event.target.checked)"' in source
    assert ':value="getFieldValue(activeItem) ?? 0"' in source
    assert '@input="setFieldValue(activeItem, Number($event.target.value))"' in source
    assert 'x-text="formatValue(getFieldValue(activeItem))"' in source
    assert ':value="getByPath(activeItem.value_path) || \'' not in source
    assert '@input="setByPath(activeItem.value_path, $event.target.value)"' not in source
    assert ':checked="Boolean(getByPath(activeItem.value_path))"' not in source
    assert '@change="setByPath(activeItem.value_path, $event.target.checked)"' not in source
    assert ':value="getByPath(activeItem.value_path) ?? 0"' not in source
    assert '@input="setByPath(activeItem.value_path, Number($event.target.value))"' not in source
    assert 'x-text="formatValue(getByPath(activeItem?.value_path))"' not in source


def test_preset_editor_template_uses_prompt_workspace_layout_contracts():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert 'x-if="isPromptWorkspaceEditor"' in source
    assert 'x-for="(prompt, index) in orderedPromptItems"' in source or 'x-for="prompt in orderedPromptItems"' in source
    assert '@click="selectPrompt(prompt.__identifier)"' in source
    assert '@click.stop="movePromptItem(index, index - 1)"' in source or '@click="movePromptItem(index, index - 1)"' in source
    assert '@click.stop="movePromptItem(index, index + 1)"' in source or '@click="movePromptItem(index, index + 1)"' in source
    assert '@click.stop="togglePromptEnabled(prompt.__identifier)"' in source or '@click="togglePromptEnabled(prompt.__identifier)"' in source
    assert 'x-show="activePromptItem?.marker"' in source or 'activePromptItem?.marker ?' in source
    assert '占位用预留字段，不承载提示词内容' in source


def test_preset_editor_template_exposes_prompt_form_fields_instead_of_prompt_raw_json():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert "updatePromptField('name'" in source
    assert "updatePromptField('role'" in source
    assert "updatePromptField('injection_position'" in source
    assert "updatePromptField('injection_depth'" in source
    assert "updatePromptField('injection_order'" in source
    assert 'updatePromptTriggers(' in source
    assert "item.editor?.kind === 'prompt-item'" not in source
    assert "activeItem?.editor?.kind === 'prompt-item'" not in source


def test_preset_editor_template_keeps_right_info_toggle_mobile_only():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert re.search(
        r'<button\s+@click="showRightPanel = !showRightPanel"\s+class="btn-secondary px-3 py-1.5 text-xs rounded md:hidden"\s*>\s*右侧信息\s*</button>',
        source,
    )
    assert not re.search(
        r'<button\s+@click="showRightPanel = !showRightPanel"\s+class="btn-secondary px-3 py-1.5 text-xs rounded"\s*>\s*右侧信息\s*</button>',
        source,
    )


def test_preset_editor_template_exposes_specialized_editor_sections():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert (
        "item.editor?.kind === 'prompt-item'" not in source
        and "activeItem?.editor?.kind === 'prompt-item'" not in source
    )
    assert (
        "item.editor?.kind === 'sortable-string-list'" in source
        or "activeItem?.editor?.kind === 'sortable-string-list'" in source
    )
    assert (
        "item.editor?.kind === 'string-list'" in source
        or "activeItem?.editor?.kind === 'string-list'" in source
    )
    assert (
        "item.editor?.kind === 'key-value-list'" in source
        or "activeItem?.editor?.kind === 'key-value-list'" in source
    )
    assert '高级原始编辑区' not in source


def test_preset_editor_template_avoids_mixing_x_if_and_x_for_on_specialized_editor_templates():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert "<template x-if=\"item.editor?.kind === 'prompt-item'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'sortable-string-list'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'string-list'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'key-value-list'\" x-for=" not in source
