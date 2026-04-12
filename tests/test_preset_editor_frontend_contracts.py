import json
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
        const getPresetDefaultPreview = async () => ({{ success: true }});
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

    assert 'updatePromptItem(index, key, value) {' in source
    assert 'addPromptItem() {' in source
    assert 'removePromptItem(index) {' in source
    assert 'moveListItem(path, fromIndex, toIndex) {' in source
    assert 'addStringListItem(path) {' in source
    assert 'updateStringListItem(path, index, value) {' in source
    assert 'removeStringListItem(path, index) {' in source
    assert 'updateBiasEntry(index, key, value) {' in source
    assert 'openRawEditor() {' in source


def test_preset_editor_js_collection_handlers_follow_task_5_contracts():
    source = read_project_file('static/js/components/presetEditor.js')

    assert "const prompts = Array.isArray(this.getByPath(\"prompts\"))" in source
    assert 'name: ""' in source
    assert 'enabled: true' in source
    assert 'marker: false' in source
    assert "const order = Array.isArray(this.getByPath(\"prompt_order\"))" in source
    assert 'filter((value) => value !== removed.identifier)' in source
    assert 'addBiasEntry() {' in source
    assert 'removeBiasEntry(index) {' in source


def test_preset_editor_runtime_keeps_prompt_order_consistent():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'prompt_1', name: '', role: 'system', content: '', enabled: true, marker: false },
            { identifier: 'prompt_3', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: ['prompt_1', 'prompt_3'],
          logit_bias: [],
        };

        editor.addPromptItem();
        const addedIdentifier = editor.editingData.prompts[2].identifier;
        if (addedIdentifier !== 'prompt_4') {
          throw new Error(`expected prompt_4, got ${addedIdentifier}`);
        }
        if (editor.editingData.prompt_order[2] !== 'prompt_4') {
          throw new Error(`expected prompt_order to append prompt_4, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }

        editor.updatePromptItem(0, 'identifier', 'intro');
        if (editor.editingData.prompt_order[0] !== 'intro') {
          throw new Error(`expected first prompt_order entry to be intro, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }

        editor.removePromptItem(1);
        if (editor.editingData.prompt_order.includes('prompt_3')) {
          throw new Error(`expected removed prompt identifier to leave prompt_order, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_backfills_prompt_order_and_rejects_invalid_bias_numbers():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: '', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: [],
          logit_bias: [{ text: 'blocked', value: -10 }],
        };

        editor.updatePromptItem(0, 'identifier', 'blank_prompt');
        if (editor.editingData.prompt_order.length !== 1 || editor.editingData.prompt_order[0] !== 'blank_prompt') {
          throw new Error(`expected blank identifier rename to backfill prompt_order, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }

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


def test_preset_editor_runtime_rejects_duplicate_prompt_identifier_renames():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: '', role: 'system', content: '', enabled: true, marker: false },
            { identifier: 'summary', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: ['main', 'summary'],
          logit_bias: [],
        };

        editor.updatePromptItem(1, 'identifier', 'main');
        if (editor.editingData.prompts[1].identifier !== 'summary') {
          throw new Error(`expected duplicate identifier rename to be ignored, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['main', 'summary'])) {
          throw new Error(`expected prompt_order to stay unchanged after duplicate rename, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_rejects_blank_existing_prompt_identifier():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: ['main'],
          logit_bias: [],
        };

        editor.updatePromptItem(0, 'identifier', '');
        if (editor.editingData.prompts[0].identifier !== 'main') {
          throw new Error(`expected blank identifier rename to be ignored, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['main'])) {
          throw new Error(`expected prompt_order to stay unchanged after blank rename, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_avoids_orphaned_prompt_order_identifier_collisions():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'prompt_1', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: ['prompt_1', 'prompt_2'],
          logit_bias: [],
        };

        editor.addPromptItem();
        const addedIdentifier = editor.editingData.prompts[1].identifier;
        if (addedIdentifier !== 'prompt_3') {
          throw new Error(`expected orphaned prompt_order entry to reserve prompt_2, got ${addedIdentifier}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['prompt_1', 'prompt_2', 'prompt_3'])) {
          throw new Error(`expected prompt_order to append unique identifier, got ${JSON.stringify(editor.editingData.prompt_order)}`);
        }
        """
    )


def test_preset_editor_runtime_rejects_rename_to_orphaned_prompt_order_identifier():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          prompts: [
            { identifier: 'main', name: '', role: 'system', content: '', enabled: true, marker: false },
          ],
          prompt_order: ['main', 'orphan'],
          logit_bias: [],
        };

        editor.updatePromptItem(0, 'identifier', 'orphan');
        if (editor.editingData.prompts[0].identifier !== 'main') {
          throw new Error(`expected rename to orphaned prompt_order identifier to be ignored, got ${JSON.stringify(editor.editingData.prompts)}`);
        }
        if (JSON.stringify(editor.editingData.prompt_order) !== JSON.stringify(['main', 'orphan'])) {
          throw new Error(`expected prompt_order to stay unchanged after orphan collision rename, got ${JSON.stringify(editor.editingData.prompt_order)}`);
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


def test_preset_editor_runtime_exposes_and_applies_raw_unknown_json():
    run_preset_editor_runtime_check(
        """
        let lastToast = null;
        editor.$store = {
          global: {
            showToast(message, type = 'info') {
              lastToast = { message, type };
            },
          },
        };
        editor.editingData = {
          temp: 0.7,
          custom_payload: { keep: true },
          custom_flag: false,
        };
        editor.editingPresetFile = { unknown_fields: ['custom_payload', 'custom_flag'] };
        editor.showRawEditor = true;
        editor.dirtyPaths = {};

        const before = editor.rawUnknownJsonText;
        if (!before.includes('custom_payload') || !before.includes('custom_flag')) {
          throw new Error(`expected rawUnknownJsonText to include unknown fields, got ${before}`);
        }

        editor.applyRawUnknownJson(JSON.stringify({ custom_payload: { keep: false }, custom_flag: true }));
        if (editor.editingData.custom_payload.keep !== false || editor.editingData.custom_flag !== true) {
          throw new Error(`expected unknown field JSON to apply into editingData, got ${JSON.stringify(editor.editingData)}`);
        }
        if (!editor.dirtyPaths.custom_payload || !editor.dirtyPaths.custom_flag) {
          throw new Error(`expected unknown field updates to mark dirty paths, got ${JSON.stringify(editor.dirtyPaths)}`);
        }
        if (editor.showRawEditor !== false) {
          throw new Error('expected applyRawUnknownJson to close raw editor');
        }
        if (!lastToast || lastToast.message !== '高级原始编辑区已应用') {
          throw new Error(`expected success toast, got ${JSON.stringify(lastToast)}`);
        }
        """
    )


def test_preset_editor_runtime_rejects_invalid_raw_unknown_json():
    run_preset_editor_runtime_check(
        """
        let lastToast = null;
        editor.$store = {
          global: {
            showToast(message, type = 'info') {
              lastToast = { message, type };
            },
          },
        };
        editor.editingData = { custom_payload: { keep: true } };
        editor.editingPresetFile = { unknown_fields: ['custom_payload'] };
        editor.showRawEditor = true;
        editor.dirtyPaths = {};

        editor.applyRawUnknownJson('{invalid');
        if (editor.editingData.custom_payload.keep !== true) {
          throw new Error(`expected invalid JSON not to mutate editingData, got ${JSON.stringify(editor.editingData)}`);
        }
        if (editor.showRawEditor !== true) {
          throw new Error('expected invalid JSON to keep raw editor open');
        }
        if (Object.keys(editor.dirtyPaths).length !== 0) {
          throw new Error(`expected invalid JSON not to mark dirty paths, got ${JSON.stringify(editor.dirtyPaths)}`);
        }
        if (!lastToast || lastToast.message !== '原始 JSON 格式无效' || lastToast.type !== 'error') {
          throw new Error(`expected invalid JSON error toast, got ${JSON.stringify(lastToast)}`);
        }
        """
    )


def test_preset_editor_runtime_raw_unknown_json_only_mutates_unknown_keys_and_can_delete_them():
    run_preset_editor_runtime_check(
        """
        let lastToast = null;
        editor.$store = {
          global: {
            showToast(message, type = 'info') {
              lastToast = { message, type };
            },
          },
        };
        editor.editingData = {
          name: 'Preset',
          temp: 0.7,
          custom_payload: { keep: true },
          custom_flag: true,
        };
        editor.editingPresetFile = { unknown_fields: ['custom_payload', 'custom_flag'] };
        editor.showRawEditor = true;
        editor.dirtyPaths = {};

        editor.applyRawUnknownJson(JSON.stringify({ custom_payload: { keep: false }, temp: 2.0 }));

        if (editor.editingData.name !== 'Preset' || editor.editingData.temp !== 0.7) {
          throw new Error(`expected raw unknown editor not to mutate known keys, got ${JSON.stringify(editor.editingData)}`);
        }
        if (editor.editingData.custom_payload.keep !== false) {
          throw new Error(`expected unknown payload update to apply, got ${JSON.stringify(editor.editingData)}`);
        }
        if (Object.prototype.hasOwnProperty.call(editor.editingData, 'custom_flag')) {
          throw new Error(`expected omitted unknown key to be deleted, got ${JSON.stringify(editor.editingData)}`);
        }
        if (!editor.dirtyPaths.custom_payload || !editor.dirtyPaths.custom_flag) {
          throw new Error(`expected unknown field subset changes to mark dirty paths, got ${JSON.stringify(editor.dirtyPaths)}`);
        }
        if (!lastToast || lastToast.message !== '高级原始编辑区已应用') {
          throw new Error(`expected success toast, got ${JSON.stringify(lastToast)}`);
        }
        """
    )


def test_preset_editor_runtime_rejects_non_object_raw_unknown_json():
    run_preset_editor_runtime_check(
        """
        let lastToast = null;
        editor.$store = {
          global: {
            showToast(message, type = 'info') {
              lastToast = { message, type };
            },
          },
        };
        editor.editingData = { custom_payload: { keep: true } };
        editor.editingPresetFile = { unknown_fields: ['custom_payload'] };
        editor.showRawEditor = true;
        editor.dirtyPaths = {};

        editor.applyRawUnknownJson('[]');
        if (editor.editingData.custom_payload.keep !== true) {
          throw new Error(`expected non-object JSON not to mutate editingData, got ${JSON.stringify(editor.editingData)}`);
        }
        if (editor.showRawEditor !== true) {
          throw new Error('expected non-object JSON to keep raw editor open');
        }
        if (Object.keys(editor.dirtyPaths).length !== 0) {
          throw new Error(`expected non-object JSON not to mark dirty paths, got ${JSON.stringify(editor.dirtyPaths)}`);
        }
        if (!lastToast || lastToast.message !== '原始 JSON 格式无效' || lastToast.type !== 'error') {
          throw new Error(`expected non-object JSON error toast, got ${JSON.stringify(lastToast)}`);
        }
        """
    )


def test_preset_editor_runtime_handles_proto_unknown_key_without_prototype_mutation():
    run_preset_editor_runtime_check(
        """
        let lastToast = null;
        editor.$store = {
          global: {
            showToast(message, type = 'info') {
              lastToast = { message, type };
            },
          },
        };
        editor.editingData = { name: 'Preset' };
        Object.defineProperty(editor.editingData, '__proto__', {
          value: { keep: true },
          enumerable: true,
          writable: true,
          configurable: true,
        });
        editor.editingPresetFile = { unknown_fields: ['__proto__'] };
        editor.showRawEditor = true;
        editor.dirtyPaths = {};

        const before = editor.rawUnknownJsonText;
        if (!before.includes('__proto__')) {
          throw new Error(`expected rawUnknownJsonText to include __proto__ key, got ${before}`);
        }

        editor.applyRawUnknownJson(JSON.stringify({ ['__proto__']: { keep: false } }));
        if (!Object.prototype.hasOwnProperty.call(editor.editingData, '__proto__')) {
          throw new Error(`expected __proto__ to remain an own data property, got ${JSON.stringify(editor.editingData)}`);
        }
        if (Object.getPrototypeOf(editor.editingData) !== Object.prototype) {
          throw new Error('expected editingData prototype to remain Object.prototype');
        }
        if (editor.editingData['__proto__'].keep !== false) {
          throw new Error(`expected __proto__ payload update to apply, got ${JSON.stringify(editor.editingData['__proto__'])}`);
        }
        if (!lastToast || lastToast.message !== '高级原始编辑区已应用') {
          throw new Error(`expected success toast, got ${JSON.stringify(lastToast)}`);
        }
        """
    )


def test_preset_editor_runtime_tracks_removed_unknown_fields_for_save():
    run_preset_editor_runtime_check(
        """
        editor.editingData = {
          custom_payload: { keep: true },
          custom_flag: true,
        };
        editor.editingPresetFile = { unknown_fields: ['custom_payload', 'custom_flag'] };
        editor.dirtyPaths = {};

        if (Array.isArray(editor.removedUnknownFields) && editor.removedUnknownFields.length !== 0) {
          throw new Error(`expected removedUnknownFields to start empty, got ${JSON.stringify(editor.removedUnknownFields)}`);
        }

        editor.$store = { global: { showToast() {} } };
        editor.applyRawUnknownJson(JSON.stringify({ custom_payload: { keep: false } }));

        if (!Array.isArray(editor.removedUnknownFields) || !editor.removedUnknownFields.includes('custom_flag')) {
          throw new Error(`expected removed unknown keys to be tracked for save, got ${JSON.stringify(editor.removedUnknownFields)}`);
        }
        if (editor.removedUnknownFields.includes('custom_payload')) {
          throw new Error(`expected retained unknown key not to be marked removed, got ${JSON.stringify(editor.removedUnknownFields)}`);
        }
        """
    )


def test_preset_editor_runtime_persists_removed_unknown_fields_in_local_draft_restore():
    run_preset_editor_runtime_check(
        """
        globalThis.localStorage = {
          _data: {},
          setItem(key, value) { this._data[key] = String(value); },
          getItem(key) { return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null; },
          removeItem(key) { delete this._data[key]; },
        };
        globalThis.confirm = () => true;

        editor.editingPresetFile = {
          id: 'global::textgen.json',
          source_revision: 'rev-1',
          unknown_fields: ['custom_payload', 'custom_flag'],
          reader_view: { items: [] },
        };
        editor.editingData = {
          custom_payload: { keep: false },
        };
        editor.dirtyPaths = {};
        editor.removedUnknownFields = ['custom_flag'];

        editor.persistLocalDraft();
        editor.removedUnknownFields = [];
        editor.editingData = { custom_payload: { keep: true }, custom_flag: true };

        const restored = editor.restoreLocalDraft();
        if (restored !== true) {
          throw new Error('expected local draft restore to succeed');
        }
        if (!Array.isArray(editor.removedUnknownFields) || !editor.removedUnknownFields.includes('custom_flag')) {
          throw new Error(`expected removedUnknownFields to survive local draft restore, got ${JSON.stringify(editor.removedUnknownFields)}`);
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


def test_preset_editor_template_exposes_specialized_editor_sections():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert (
        "item.editor?.kind === 'prompt-item'" in source
        or "activeItem?.editor?.kind === 'prompt-item'" in source
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
    assert '高级原始编辑区' in source


def test_preset_editor_template_prompt_editor_uses_top_level_prompts_collection():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert "Array.isArray(getByPath('prompts')) ? getByPath('prompts') : []" in source


def test_preset_editor_template_avoids_mixing_x_if_and_x_for_on_specialized_editor_templates():
    source = read_project_file('templates/modals/detail_preset_fullscreen.html')

    assert "<template x-if=\"item.editor?.kind === 'prompt-item'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'sortable-string-list'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'string-list'\" x-for=" not in source
    assert "<template x-if=\"item.editor?.kind === 'key-value-list'\" x-for=" not in source
