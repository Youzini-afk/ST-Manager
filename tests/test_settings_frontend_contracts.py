import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def run_state_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/state.js'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');

        const stubs = `
        const getServerStatus = async () => ({{}});
        const getSettings = async () => ({{}});
        const saveSettings = async () => ({{ success: true }});
        const performSystemAction = async () => ({{ success: true }});
        const triggerScan = async () => ({{ success: true }});
        const updateCssVariable = () => {{}};
        const applyFont = () => {{}};
        const getIsolatedCategories = async () => ({{ isolated_categories: {{ paths: [] }} }});
        const saveIsolatedCategoriesRequest = async () => ({{ success: true, isolated_categories: {{ paths: [] }} }});
        globalThis.window = {{
          innerWidth: 1280,
          innerHeight: 720,
          addEventListener() {{}},
          removeEventListener() {{}},
          dispatchEvent() {{}},
          visualViewport: null,
        }};
        globalThis.document = {{
          documentElement: {{
            classList: {{ add() {{}}, remove() {{}} }},
          }},
        }};
        globalThis.localStorage = {{
          getItem() {{ return null; }},
          setItem() {{}},
          removeItem() {{}},
        }};
        globalThis.CustomEvent = class CustomEvent {{
          constructor(type, options = {{}}) {{
            this.type = type;
            this.detail = options.detail;
          }}
        }};
        globalThis.alert = () => {{}};
        globalThis.confirm = () => true;
        globalThis.Alpine = {{
          _stores: new Map(),
          store(name, value) {{
            if (arguments.length === 1) return this._stores.get(name);
            this._stores.set(name, value);
            return value;
          }},
        }};
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source),
        );
        module.initState();
        const store = globalThis.Alpine.store('global');

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


def run_settings_modal_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/components/settingsModal.js'
    stub_source = textwrap.dedent(
        """
        const uploadBackground = (...args) => {
          const fn = globalThis.__uploadBackgroundStub;
          return typeof fn === 'function' ? fn(...args) : Promise.resolve({ success: true, url: '/uploaded/default.png' });
        };
        const openTrash = async () => ({ success: true });
        const emptyTrash = async () => ({ success: true });
        const performSystemAction = async () => ({ success: true });
        const triggerScan = async () => ({ success: true });
        const updateCssVariable = () => {};
        const applyFontDom = () => {};
        globalThis.alert = () => {};
        globalThis.confirm = () => true;
        globalThis.FormData = class FormData {
          constructor() {
            this.entries = [];
          }
          append(key, value) {
            this.entries.push([key, value]);
          }
            };
        """
    )
    module_suffix = '\nexport default settingsModal;'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function settingsModal()', 'function settingsModal()');

        const uploadResults = globalThis.__uploadResults = [];
        const backgroundUpdates = globalThis.__backgroundUpdates = [];

        const module = await import(
          'data:text/javascript,' + encodeURIComponent({json.dumps(stub_source)} + source + {json.dumps(module_suffix)}),
        );
        const component = module.default();

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


def run_shared_wallpaper_picker_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/components/sharedWallpaperPicker.js'
    stub_source = textwrap.dedent(
        """
        const importSharedWallpaper = (...args) => {
          const fn = globalThis.__importSharedWallpaperStub;
          const formData = args[0];
          const selectionTarget = args[1] || 'manager';
          if (formData && typeof formData.append === 'function') {
            formData.append('selection_target', selectionTarget);
          }
          return typeof fn === 'function' ? fn(formData, selectionTarget) : Promise.resolve({ success: true, item: null, items: [] });
        };
        const selectSharedWallpaper = (...args) => {
          const fn = globalThis.__selectSharedWallpaperStub;
          return typeof fn === 'function' ? fn(...args) : Promise.resolve({ success: true, selected_id: args[0]?.wallpaper_id || '' });
        };
        globalThis.alert = () => {};
        globalThis.FormData = class FormData {
          constructor() {
            this.entries = [];
          }
          append(key, value) {
            this.entries.push([key, value]);
          }
        };
        """
    )
    module_suffix = '\nexport default sharedWallpaperPicker;'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function sharedWallpaperPicker(options = {{}})', 'function sharedWallpaperPicker(options = {{}})');

        const module = await import(
          'data:text/javascript,' + encodeURIComponent({json.dumps(stub_source)} + source + {json.dumps(module_suffix)}),
        );
        const component = module.default();

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


def test_state_settings_form_includes_profile_specific_preset_directories():
    source = read_project_file('static/js/state.js')

    assert 'st_openai_preset_dir:' in source
    assert 'st_textgen_preset_dir:' in source
    assert 'st_instruct_preset_dir:' in source
    assert 'st_context_preset_dir:' in source
    assert 'st_sysprompt_dir:' in source
    assert 'st_reasoning_dir:' in source


def test_settings_template_exposes_profile_specific_preset_directory_inputs():
    source = read_project_file('templates/modals/settings.html')

    assert 'x-model="settingsForm.st_openai_preset_dir"' in source
    assert 'x-model="settingsForm.st_textgen_preset_dir"' in source
    assert 'x-model="settingsForm.st_instruct_preset_dir"' in source
    assert 'x-model="settingsForm.st_context_preset_dir"' in source
    assert 'x-model="settingsForm.st_sysprompt_dir"' in source
    assert 'x-model="settingsForm.st_reasoning_dir"' in source


def test_settings_template_keeps_background_controls_visible_for_selected_manager_wallpaper():
    source = read_project_file('templates/modals/settings.html')

    assert 'x-show="settingsForm.bg_url || settingsForm.manager_wallpaper_id"' in source


def test_settings_template_exposes_shared_wallpaper_picker_ui():
    source = read_project_file('templates/modals/settings.html')

    assert 'x-data="sharedWallpaperPicker({' in source
    assert "sourceFilter: 'all'" in source
    assert '@shared-wallpaper-selected.window="applySharedWallpaperSelection($event.detail)"' in source
    assert "setSourceFilter('builtin')" in source
    assert "setSourceFilter('imported')" in source
    assert "setSourceFilter('beautify')" in source
    assert 'sharedWallpaperPreviewUrl(item.file)' in source
    assert 'background-image:url(' in source
    assert "x-text=\"item.source_type || 'imported'\"" in source


def test_resource_api_exposes_shared_wallpaper_import_and_select_helpers():
    source = read_project_file('static/js/api/resource.js')

    assert "export async function importSharedWallpaper(formData, selectionTarget = 'manager')" in source
    assert "fetch('/api/shared-wallpapers/import'" in source
    assert "formData.append('selection_target', selectionTarget)" in source
    assert 'export async function selectSharedWallpaper(payload)' in source
    assert "fetch('/api/shared-wallpapers/select'" in source
    assert "selection_target: payload.selection_target || 'manager'" in source


def test_resolve_manager_background_url_prefers_selected_shared_wallpaper():
    run_state_runtime_check(
        """
        store.settingsForm.bg_url = '/legacy/background.png';
        store.settingsForm.manager_wallpaper_id = 'builtin:space/stars.png';
        store.sharedWallpapers = [
          {
            id: 'builtin:space/stars.png',
            file: 'static/assets/wallpapers/builtin/space/stars.png',
          },
        ];

        const resolved = store.resolveManagerBackgroundUrl();
        if (resolved !== '/api/beautify/preview-asset/static/assets/wallpapers/builtin/space/stars.png') {
          throw new Error(`expected shared wallpaper url, got: ${resolved}`);
        }
        """
    )


def test_resolve_manager_background_url_uses_servable_route_for_imported_shared_wallpaper():
    run_state_runtime_check(
        """
        store.settingsForm.bg_url = '/legacy/background.png';
        store.settingsForm.manager_wallpaper_id = 'imported:demo';
        store.sharedWallpapers = [
          {
            id: 'imported:demo',
            file: 'data/library/wallpapers/imported/demo.png',
          },
        ];

        const resolved = store.resolveManagerBackgroundUrl();
        if (resolved !== '/api/beautify/preview-asset/data/library/wallpapers/imported/demo.png') {
          throw new Error(`expected servable shared wallpaper route, got: ${resolved}`);
        }
        """
    )


def test_resolve_manager_background_url_falls_back_to_legacy_bg_url_when_selected_item_missing():
    run_state_runtime_check(
        """
        store.settingsForm.bg_url = '/legacy/background.png';
        store.settingsForm.manager_wallpaper_id = 'missing-id';
        store.sharedWallpapers = [
          {
            id: 'builtin:space/stars.png',
            file: 'static/assets/wallpapers/builtin/space/stars.png',
          },
        ];

        const resolved = store.resolveManagerBackgroundUrl();
        if (resolved !== '/legacy/background.png') {
          throw new Error(`expected legacy background fallback, got: ${resolved}`);
        }
        """
    )


def test_settings_modal_legacy_background_input_clears_manager_wallpaper_selection():
    run_settings_modal_runtime_check(
        """
        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: 'builtin:space/stars.png',
              bg_url: '/legacy/background.png',
            },
            resolveManagerBackgroundUrl() {
              return this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              backgroundUpdates.push(url);
            },
          },
        };

        component.applyBackgroundUrlInput();

        if (component.$store.global.settingsForm.manager_wallpaper_id !== '') {
          throw new Error('expected applyBackgroundUrlInput() to clear manager_wallpaper_id');
        }
        if (backgroundUpdates.length !== 1 || backgroundUpdates[0] !== '/legacy/background.png') {
          throw new Error(`unexpected background updates: ${JSON.stringify(backgroundUpdates)}`);
        }
        """
    )


def test_settings_modal_upload_flow_clears_manager_wallpaper_selection():
    run_settings_modal_runtime_check(
        """
        globalThis.__uploadBackgroundStub = async () => ({ success: true, url: '/uploaded/new-background.png' });

        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: 'builtin:space/stars.png',
              bg_url: '',
            },
            resolveManagerBackgroundUrl() {
              return this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              backgroundUpdates.push(url);
            },
          },
        };

        const button = { innerText: 'Upload' };
        const event = {
          target: {
            files: [{ size: 1024, name: 'wallpaper.png' }],
            previousElementSibling: button,
            value: 'filled',
          },
        };

        await component.handleBackgroundUpload(event);

        if (component.$store.global.settingsForm.manager_wallpaper_id !== '') {
          throw new Error('expected handleBackgroundUpload() to clear manager_wallpaper_id');
        }
        if (component.$store.global.settingsForm.bg_url !== '/uploaded/new-background.png') {
          throw new Error(`unexpected uploaded bg_url: ${component.$store.global.settingsForm.bg_url}`);
        }
        if (backgroundUpdates.length !== 1 || backgroundUpdates[0] !== '/uploaded/new-background.png') {
          throw new Error(`unexpected background updates: ${JSON.stringify(backgroundUpdates)}`);
        }
        if (event.target.value !== '') {
          throw new Error('expected upload input value to reset after upload');
        }
        if (button.innerText !== 'Upload') {
          throw new Error(`expected button text restore, got: ${button.innerText}`);
        }
        """
    )


def test_shared_wallpaper_picker_groups_sources_for_settings_usage():
    run_shared_wallpaper_picker_runtime_check(
        """
        component.$store = {
          global: {
            sharedWallpapers: [
              { id: 'builtin:a', source_type: 'builtin' },
              { id: 'imported:b', source_type: 'imported' },
              { id: 'beautify:c', source_type: 'package_embedded' },
            ],
          },
        };

        const grouped = component.groupedWallpapers;
        if (grouped.builtin.length !== 1 || grouped.imported.length !== 1 || grouped.beautify.length !== 1) {
          throw new Error(`unexpected grouped wallpapers: ${JSON.stringify(grouped)}`);
        }

        component.setSourceFilter('beautify');
        const filtered = component.filteredWallpapers;
        if (filtered.length !== 1 || filtered[0].id !== 'beautify:c') {
          throw new Error(`unexpected filtered wallpapers: ${JSON.stringify(filtered)}`);
        }
        """
    )


def test_shared_wallpaper_picker_exposes_preview_asset_url_helper():
    run_shared_wallpaper_picker_runtime_check(
        """
        const resolvedBuiltin = component.sharedWallpaperPreviewUrl('static/assets/wallpapers/builtin/space/stars.png');
        if (resolvedBuiltin !== '/api/beautify/preview-asset/static/assets/wallpapers/builtin/space/stars.png') {
          throw new Error(`unexpected builtin preview url: ${resolvedBuiltin}`);
        }

        const resolvedImported = component.sharedWallpaperPreviewUrl('data/library/wallpapers/imported/demo.png');
        if (resolvedImported !== '/api/beautify/preview-asset/data/library/wallpapers/imported/demo.png') {
          throw new Error(`unexpected imported preview url: ${resolvedImported}`);
        }
      """
    )


def test_shared_wallpaper_picker_selection_updates_manager_wallpaper_context():
    run_shared_wallpaper_picker_runtime_check(
        """
        const selectCalls = [];
        const dispatched = [];
        globalThis.window = {
          dispatchEvent(event) {
            dispatched.push(event);
          },
        };
        globalThis.CustomEvent = class CustomEvent {
          constructor(type, options = {}) {
            this.type = type;
            this.detail = options.detail;
          }
        };
        globalThis.__selectSharedWallpaperStub = async (payload) => {
          selectCalls.push(payload);
          return ({
          success: true,
          wallpaper: {
            id: payload.wallpaper_id,
            file: 'static/assets/wallpapers/builtin/space/stars.png',
            source_type: 'builtin',
          },
          });
        };

        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: '',
              bg_url: '/legacy/background.png',
            },
            sharedWallpapers: [],
            resolveManagerBackgroundUrl() {
              const item = this.sharedWallpapers.find((entry) => entry.id === this.settingsForm.manager_wallpaper_id);
              return item ? `/${item.file}` : this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              globalThis.__selectedBackgroundUrl = url;
            },
          },
        };

        await component.selectWallpaper({ id: 'builtin:space/stars.png' });

        if (selectCalls.length !== 1 || selectCalls[0].selection_target !== 'manager') {
          throw new Error(`unexpected select payloads: ${JSON.stringify(selectCalls)}`);
        }

        if (component.$store.global.settingsForm.manager_wallpaper_id !== 'builtin:space/stars.png') {
          throw new Error(`unexpected selected wallpaper id: ${component.$store.global.settingsForm.manager_wallpaper_id}`);
        }
        if (component.$store.global.settingsForm.bg_url !== '') {
          throw new Error(`expected bg_url cleared, got: ${component.$store.global.settingsForm.bg_url}`);
        }
        if (globalThis.__selectedBackgroundUrl !== '/static/assets/wallpapers/builtin/space/stars.png') {
          throw new Error(`unexpected background url: ${globalThis.__selectedBackgroundUrl}`);
        }
        if (!dispatched.some((event) => event.type === 'shared-wallpaper-selected' && event.detail?.wallpaper?.id === 'builtin:space/stars.png')) {
          throw new Error(`expected shared-wallpaper-selected event, got: ${JSON.stringify(dispatched)}`);
        }
        """
    )


def test_shared_wallpaper_picker_import_merges_single_item_into_existing_list():
    run_shared_wallpaper_picker_runtime_check(
        """
        const importCalls = [];
        const dispatched = [];
        globalThis.window = {
          dispatchEvent(event) {
            dispatched.push(event);
          },
        };
        globalThis.CustomEvent = class CustomEvent {
          constructor(type, options = {}) {
            this.type = type;
            this.detail = options.detail;
          }
        };
        globalThis.__importSharedWallpaperStub = async (formData, selectionTarget) => {
          importCalls.push({ entries: formData.entries, selectionTarget });
          return {
            success: true,
            item: {
              id: 'imported:new-wallpaper.png',
              file: 'data/library/wallpapers/imported/new-wallpaper.png',
              source_type: 'imported',
            },
          };
        };

        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: '',
              bg_url: '/legacy/background.png',
            },
            sharedWallpapers: [
              {
                id: 'builtin:space/stars.png',
                file: 'static/assets/wallpapers/builtin/space/stars.png',
                source_type: 'builtin',
              },
            ],
            resolveManagerBackgroundUrl() {
              const item = this.sharedWallpapers.find((entry) => entry.id === this.settingsForm.manager_wallpaper_id);
              return item ? `/${item.file}` : this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              globalThis.__importedBackgroundUrl = url;
            },
          },
        };

        await component.handleImport({
          target: {
            files: [{ name: 'new-wallpaper.png' }],
            value: 'filled',
          },
        });

        if (importCalls.length !== 1) {
          throw new Error(`expected one import call, got: ${JSON.stringify(importCalls)}`);
        }
        if (importCalls[0].selectionTarget !== 'manager') {
          throw new Error(`expected manager selectionTarget, got: ${JSON.stringify(importCalls)}`);
        }
        const entries = importCalls[0].entries;
        if (!entries.some(([key, value]) => key === 'selection_target' && value === 'manager')) {
          throw new Error(`expected selection_target append, got: ${JSON.stringify(entries)}`);
        }
        const ids = component.$store.global.sharedWallpapers.map((item) => item.id).sort();
        if (ids.length !== 2 || ids[0] !== 'builtin:space/stars.png' || ids[1] !== 'imported:new-wallpaper.png') {
          throw new Error(`unexpected merged wallpaper ids: ${JSON.stringify(ids)}`);
        }
        if (component.$store.global.settingsForm.manager_wallpaper_id !== 'imported:new-wallpaper.png') {
          throw new Error(`expected imported wallpaper selected immediately, got: ${component.$store.global.settingsForm.manager_wallpaper_id}`);
        }
        if (component.$store.global.settingsForm.bg_url !== '') {
          throw new Error(`expected bg_url cleared after import, got: ${component.$store.global.settingsForm.bg_url}`);
        }
        if (globalThis.__importedBackgroundUrl !== '/data/library/wallpapers/imported/new-wallpaper.png') {
          throw new Error(`unexpected imported background url: ${globalThis.__importedBackgroundUrl}`);
        }
        if (!dispatched.some((event) => event.type === 'shared-wallpaper-selected' && event.detail?.wallpaper?.id === 'imported:new-wallpaper.png')) {
          throw new Error(`expected import to dispatch shared-wallpaper-selected, got: ${JSON.stringify(dispatched)}`);
        }
        """
    )


def test_shared_wallpaper_picker_selection_updates_preview_wallpaper_context():
    run_shared_wallpaper_picker_runtime_check(
        """
        const selectCalls = [];
        globalThis.__selectSharedWallpaperStub = async (payload) => {
          selectCalls.push(payload);
          return ({
            success: true,
            wallpaper: {
              id: payload.wallpaper_id,
              file: 'data/library/wallpapers/imported/preview.png',
              source_type: 'imported',
            },
          });
        };

        const previewComponent = module.default({ selectionTarget: 'preview' });
        previewComponent.$store = {
          global: {
            beautifyGlobalSettings: {
              preview_wallpaper_id: '',
              wallpaper: null,
            },
            sharedWallpapers: [],
          },
        };

        await previewComponent.selectWallpaper({ id: 'imported:preview' });

        if (selectCalls.length !== 1 || selectCalls[0].selection_target !== 'preview') {
          throw new Error(`unexpected preview select payloads: ${JSON.stringify(selectCalls)}`);
        }
        if (previewComponent.$store.global.beautifyGlobalSettings.preview_wallpaper_id !== 'imported:preview') {
          throw new Error(`expected preview wallpaper id update, got: ${previewComponent.$store.global.beautifyGlobalSettings.preview_wallpaper_id}`);
        }
        if (previewComponent.$store.global.beautifyGlobalSettings.wallpaper?.id !== 'imported:preview') {
          throw new Error(`expected preview wallpaper object update, got: ${JSON.stringify(previewComponent.$store.global.beautifyGlobalSettings.wallpaper)}`);
        }
      """
    )


def test_settings_modal_applies_shared_wallpaper_selection_detail():
    run_settings_modal_runtime_check(
        """
        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: '',
              bg_url: '/legacy/background.png',
            },
            sharedWallpapers: [
              {
                id: 'builtin:space/stars.png',
                file: 'static/assets/wallpapers/builtin/space/stars.png',
                source: 'builtin',
              },
            ],
            resolveManagerBackgroundUrl() {
              const item = this.sharedWallpapers.find((entry) => entry.id === this.settingsForm.manager_wallpaper_id);
              return item ? `/${item.file}` : this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              backgroundUpdates.push(url);
            },
          },
        };

        component.applySharedWallpaperSelection({
          wallpaper: {
            id: 'builtin:space/stars.png',
            file: 'static/assets/wallpapers/builtin/space/stars.png',
            source: 'builtin',
          },
        });

        if (component.$store.global.settingsForm.manager_wallpaper_id !== 'builtin:space/stars.png') {
          throw new Error('expected applySharedWallpaperSelection() to store selected id');
        }
        if (component.$store.global.settingsForm.bg_url !== '') {
          throw new Error(`expected legacy bg_url cleared, got: ${component.$store.global.settingsForm.bg_url}`);
        }
        if (backgroundUpdates.length !== 1 || backgroundUpdates[0] !== '/static/assets/wallpapers/builtin/space/stars.png') {
          throw new Error(`unexpected background updates: ${JSON.stringify(backgroundUpdates)}`);
        }
        """
    )


def test_settings_modal_ignores_stale_shared_wallpaper_selection_detail_without_clearing_legacy_background():
    run_settings_modal_runtime_check(
        """
        component.$store = {
          global: {
            settingsForm: {
              manager_wallpaper_id: '',
              bg_url: '/legacy/background.png',
            },
            sharedWallpapers: [],
            resolveManagerBackgroundUrl() {
              return this.settingsForm.bg_url || '';
            },
            updateBackgroundImage(url) {
              backgroundUpdates.push(url);
            },
          },
        };

        component.applySharedWallpaperSelection({
          wallpaper: {
            id: '',
            file: 'static/assets/wallpapers/builtin/space/stars.png',
          },
        });

        if (component.$store.global.settingsForm.manager_wallpaper_id !== '') {
          throw new Error('stale selection detail should not set manager_wallpaper_id');
        }
        if (component.$store.global.settingsForm.bg_url !== '/legacy/background.png') {
          throw new Error('stale selection detail should preserve legacy bg_url');
        }
        if (backgroundUpdates.length !== 0) {
          throw new Error(`stale selection detail should not trigger background updates: ${JSON.stringify(backgroundUpdates)}`);
        }
        """
    )
