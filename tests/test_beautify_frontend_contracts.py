import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def assert_contains_any(text, variants):
    assert any(variant in text for variant in variants), f'Missing expected variants: {variants}'


def run_beautify_preview_frame_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/components/beautifyPreviewFrame.js'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
            source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function beautifyPreviewFrame()', 'function beautifyPreviewFrame()');

        const stubs = `
        const buildBeautifyPreviewAssetUrl = (value) => String(value || '');
        const clearIsolatedHtml = (host, options = {{}}) => {{
          if (!host.__events) host.__events = [];
          host.__events.push({{ type: 'clear', options }});
          host.innerHTML = '';
        }};
        const renderIsolatedHtml = (host, options = {{}}) => {{
          if (!host.__events) host.__events = [];
          host.__events.push({{ type: 'render', options }});
          host.innerHTML = String(options.htmlPayload || '');
        }};
        const buildBeautifyPreviewDocument = (options = {{}}) => JSON.stringify(options);
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source + '\\nexport default beautifyPreviewFrame;'),
        );

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


def run_beautify_grid_runtime_check(script_body):
    source_path = PROJECT_ROOT / 'static/js/components/beautifyGrid.js'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function beautifyGrid()', 'function beautifyGrid()');

        const stubs = `
        const getGridStub = (name, fallback) => (...args) => {{
          const fn = globalThis.__gridStubs?.[name];
          return typeof fn === 'function' ? fn(...args) : fallback(...args);
        }};
        const buildBeautifyPreviewAssetUrl = getGridStub('buildBeautifyPreviewAssetUrl', (value) => String(value || ''));
        const deleteBeautifyPackage = getGridStub('deleteBeautifyPackage', async () => ({{ success: true }}));
        const getBeautifySettings = getGridStub('getBeautifySettings', async () => ({{ success: true, item: null }}));
        const getBeautifyPackage = getGridStub('getBeautifyPackage', async () => ({{ success: true, item: null }}));
        const importBeautifyScreenshot = getGridStub('importBeautifyScreenshot', async () => ({{ success: true, screenshot: {{ id: '' }} }}));
        const importBeautifyTheme = getGridStub('importBeautifyTheme', async () => ({{ success: true, package: {{ id: '' }} }}));
        const importBeautifyPackageAvatar = getGridStub('importBeautifyPackageAvatar', async () => ({{ success: true, item: {{}} }}));
        const importGlobalBeautifyAvatar = getGridStub('importGlobalBeautifyAvatar', async () => ({{ success: true, item: null }}));
        const importGlobalBeautifyWallpaper = getGridStub('importGlobalBeautifyWallpaper', async () => ({{ success: true, item: null }}));
        const importBeautifyWallpaper = getGridStub('importBeautifyWallpaper', async () => ({{ success: true, wallpaper: {{ id: '' }} }}));
        const listBeautifyPackages = getGridStub('listBeautifyPackages', async () => ({{ success: true, items: [] }}));
        const updateBeautifyPackageIdentities = getGridStub('updateBeautifyPackageIdentities', async () => ({{ success: true, item: {{}} }}));
        const updateBeautifySettings = getGridStub('updateBeautifySettings', async () => ({{ success: true, item: null }}));
        const updateBeautifyVariant = getGridStub('updateBeautifyVariant', async () => ({{ success: true, item: null }}));
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source + '\\nexport default beautifyGrid;'),
        );

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


def test_index_template_lifts_beautify_scope_to_main_container_above_shared_includes():
    template = read_project_file('templates/index.html')

    main_container_index = template.index('<div class="main-container" x-data="beautifyGrid">')
    sidebar_index = template.index('{% include "components/sidebar.html" %}')
    beautify_grid_index = template.index('{% include "components/grid_beautify.html" %}')

    assert main_container_index < sidebar_index < beautify_grid_index


def test_sidebar_template_hosts_beautify_toolbar_filters_and_package_list_contract():
    sidebar_template = read_project_file('templates/components/sidebar.html')
    theme_change_handlers = (
        '@change="handleThemeFiles($event.target.files); $event.target.value = \'\'"',
        '@change="handleThemeFiles($event.target.files); $event.target.value = \"\""',
    )
    wallpaper_change_handlers = (
        '@change="handleWallpaperFiles($event.target.files); $event.target.value = \'\'"',
        '@change="handleWallpaperFiles($event.target.files); $event.target.value = \"\""',
    )

    assert "currentMode === 'beautify' && visibleSidebar" in sidebar_template
    assert 'beautify-sidebar-panel' in sidebar_template
    assert 'class="flex-1 flex flex-col overflow-hidden bg-[var(--bg-panel)] beautify-sidebar-panel beautify-sidebar-pane"' in sidebar_template
    assert 'beautify-toolbar' in sidebar_template
    assert 'beautify-package-list custom-scrollbar' in sidebar_template
    assert 'x-model.debounce.200ms="beautifySearch"' in sidebar_template
    assert 'x-model="platformFilter"' in sidebar_template
    assert 'x-model="installFilter"' not in sidebar_template
    assert '@click="fetchPackages()"' in sidebar_template
    assert any(handler in sidebar_template for handler in theme_change_handlers)
    assert any(handler in sidebar_template for handler in wallpaper_change_handlers)
    assert 'filteredPackages' in sidebar_template
    assert '@click="selectPackage(item.id)"' in sidebar_template
    assert 'selectedPackageId === item.id' in sidebar_template
    assert 'beautify-status-pill' not in sidebar_template
    assert 'item.install_state' not in sidebar_template
    assert '当前应用中' not in sidebar_template
    assert '已安装' not in sidebar_template
    assert '未安装' not in sidebar_template


def test_app_js_registers_beautify_runtime_components():
    app_js = read_project_file('static/js/app.js')

    assert_contains_any(app_js, ('import beautifyGrid from "./components/beautifyGrid.js";', "import beautifyGrid from './components/beautifyGrid.js';"))
    assert_contains_any(app_js, ('import beautifyPreviewFrame from "./components/beautifyPreviewFrame.js";', "import beautifyPreviewFrame from './components/beautifyPreviewFrame.js';"))
    assert_contains_any(app_js, ('Alpine.data("beautifyGrid", beautifyGrid);', "Alpine.data('beautifyGrid', beautifyGrid);"))
    assert_contains_any(app_js, ('Alpine.data("beautifyPreviewFrame", beautifyPreviewFrame);', "Alpine.data('beautifyPreviewFrame', beautifyPreviewFrame);"))


def test_beautify_api_exports_core_runtime_helpers():
    beautify_api = read_project_file('static/js/api/beautify.js')

    expected_exports = (
        'listBeautifyPackages',
        'getBeautifyPackage',
        'importBeautifyTheme',
        'importBeautifyWallpaper',
        'updateBeautifyVariant',
        'deleteBeautifyPackage',
        'buildBeautifyPreviewAssetUrl',
    )

    for export_name in expected_exports:
        assert_contains_any(
            beautify_api,
            (
                f'export async function {export_name}(',
                f'export function {export_name}(',
            ),
        )


def test_beautify_api_exports_settings_and_screenshot_helpers():
    beautify_api = read_project_file('static/js/api/beautify.js')

    expected_exports = (
        'getBeautifySettings',
        'updateBeautifySettings',
        'importGlobalBeautifyWallpaper',
        'importGlobalBeautifyAvatar',
        'importBeautifyScreenshot',
        'updateBeautifyPackageIdentities',
        'importBeautifyPackageAvatar',
    )

    for export_name in expected_exports:
        assert_contains_any(
            beautify_api,
            (
                f'export async function {export_name}(',
                f'export function {export_name}(',
            ),
        )

    assert '/api/beautify/settings' in beautify_api
    assert '/api/beautify/update-settings' in beautify_api
    assert '/api/beautify/import-global-wallpaper' in beautify_api
    assert '/api/beautify/import-global-avatar' in beautify_api
    assert '/api/beautify/import-screenshot' in beautify_api
    assert '/api/beautify/update-package-identities' in beautify_api
    assert '/api/beautify/import-package-avatar' in beautify_api

    assert beautify_api.count('headers: { "Content-Type": "application/json" }') >= 2
    assert 'formData.append("package_id", packageId);' in beautify_api
    assert 'formData.append("target", target);' in beautify_api


def test_beautify_api_removes_install_and_apply_client_exports():
    beautify_api = read_project_file('static/js/api/beautify.js')

    assert 'export async function installBeautifyVariant(' not in beautify_api
    assert 'export async function applyBeautifyVariant(' not in beautify_api


def test_native_st_vendor_assets_are_present_with_attribution():
    vendor_root = PROJECT_ROOT / 'static/vendor/sillytavern'

    assert (vendor_root / 'LICENSE').exists()
    assert (vendor_root / 'SOURCE.md').exists()
    assert (vendor_root / 'style.css').exists()
    assert (vendor_root / 'css/mobile-styles.css').exists()


def test_native_st_vendor_popup_css_uses_vendored_dialog_polyfill_path():
    popup_css = read_project_file('static/vendor/sillytavern/css/popup.css')

    assert "@import url('/lib/dialog-polyfill.css');" not in popup_css
    assert '../lib/dialog-polyfill.css' in popup_css


def test_beautify_grid_removes_install_and_apply_selection_methods():
    grid_source = read_project_file('static/js/components/beautifyGrid.js')

    assert 'async installCurrentSelection()' not in grid_source
    assert 'async applyCurrentSelection()' not in grid_source
    assert 'function filterPackages(items, search, platformFilter, installFilter)' not in grid_source
    assert 'get installFilter()' not in grid_source
    assert 'set installFilter(val)' not in grid_source
    assert 'item.install_state' not in grid_source
    assert 'beautifyInstallFilter' not in grid_source


def test_beautify_grid_platform_selector_does_not_optimistically_mutate_active_variant_platform():
    template = read_project_file('templates/components/grid_beautify.html')

    assert 'x-model="activeVariant.platform"' not in template
    assert "x-model='activeVariant.platform'" not in template
    assert '@change="updateCurrentVariantPlatform($event.target.value)"' in template or "@change='updateCurrentVariantPlatform($event.target.value)'" in template
    assert ':value="activeVariant?.platform || \"pc\""' in template or ":value='activeVariant?.platform || \"pc\"'" in template or ':value="activeVariant?.platform || \'pc\'"' in template


def test_beautify_grid_source_tracks_workspace_screenshot_and_settings_methods():
    grid_source = read_project_file('static/js/components/beautifyGrid.js')

    for token in (
        'get workspace()',
        'set workspace(val)',
        'get stageMode()',
        'set stageMode(val)',
        'get screenshotOptions()',
        'get activeScreenshot()',
        'async fetchGlobalSettings()',
        'async handleScreenshotFiles(fileList)',
        'async saveGlobalSettings()',
        'async savePackageIdentityOverrides()',
        'async handleGlobalWallpaperFiles(fileList)',
        'async handleGlobalAvatarFile(target, fileList)',
        'async handlePackageAvatarFile(target, fileList)',
        'async clearGlobalWallpaper()',
        'async clearGlobalCharacterAvatar()',
        'async clearGlobalUserAvatar()',
        'async clearPackageCharacterAvatar()',
        'async clearPackageUserAvatar()',
        'switchBeautifyWorkspace(workspace)',
        'setStageMode(mode)',
        'selectScreenshot(screenshotId)',
    ):
        assert token in grid_source


def test_beautify_grid_exposes_beautify_workspace_alias_for_templates():
    grid_source = read_project_file('static/js/components/beautifyGrid.js')

    assert 'get beautifyWorkspace()' in grid_source
    assert 'set beautifyWorkspace(val)' in grid_source


def test_beautify_grid_switching_to_settings_workspace_refetches_global_settings():
    run_beautify_grid_runtime_check(
        '''
        let settingsFetches = 0;
        globalThis.__gridStubs = {
          getBeautifySettings: async () => {
            settingsFetches += 1;
            return {
              success: true,
              item: {
                identities: {
                  character: { name: '全局角色', avatar_file: '' },
                  user: { name: '全局用户', avatar_file: '' },
                },
              },
            };
          },
        };

        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'packages',
            showToast: () => {},
          },
        };

        component.switchBeautifyWorkspace('settings');
        await Promise.resolve();

        if (settingsFetches !== 1) {
          throw new Error(`expected one settings refetch, got ${settingsFetches}`);
        }
        '''
    )


def test_beautify_grid_preserves_existing_screenshot_selection_when_importing_more_images():
    run_beautify_grid_runtime_check(
        '''
        let imported = 0;
        globalThis.__gridStubs = {
          importBeautifyScreenshot: async () => {
            imported += 1;
            return { success: true, screenshot: { id: `shot_new_${imported}` } };
          },
          getBeautifyPackage: async () => ({
            success: true,
            item: {
              id: 'pkg_demo',
              variants: {},
              wallpapers: {},
              screenshots: {
                shot_existing: { id: 'shot_existing', file: 'existing.png' },
                shot_new_1: { id: 'shot_new_1', file: 'new-1.png' },
                shot_new_2: { id: 'shot_new_2', file: 'new-2.png' },
              },
              identity_overrides: {},
            },
          }),
        };

        const component = module.default();
        component.$store = {
          global: {
            beautifySelectedPackageId: 'pkg_demo',
            beautifySelectedScreenshotId: 'shot_existing',
            showToast: () => {},
          },
        };

        await component.handleScreenshotFiles([{ name: 'one.png' }, { name: 'two.png' }]);

        if (component.$store.global.beautifySelectedScreenshotId !== 'shot_existing') {
          throw new Error(`expected existing screenshot selection to be preserved, got ${component.$store.global.beautifySelectedScreenshotId}`);
        }
        '''
    )


def test_beautify_grid_activates_first_imported_screenshot_when_none_was_selected():
    run_beautify_grid_runtime_check(
        '''
        let imported = 0;
        globalThis.__gridStubs = {
          importBeautifyScreenshot: async () => {
            imported += 1;
            return { success: true, screenshot: { id: `shot_new_${imported}` } };
          },
          getBeautifyPackage: async () => ({
            success: true,
            item: {
              id: 'pkg_demo',
              variants: {},
              wallpapers: {},
              screenshots: {
                shot_old: { id: 'shot_old', file: 'old.png' },
                shot_new_1: { id: 'shot_new_1', file: 'new-1.png' },
                shot_new_2: { id: 'shot_new_2', file: 'new-2.png' },
              },
              identity_overrides: {},
            },
          }),
        };

        const component = module.default();
        component.$store = {
          global: {
            beautifySelectedPackageId: 'pkg_demo',
            beautifySelectedScreenshotId: '',
            showToast: () => {},
          },
        };

        await component.handleScreenshotFiles([{ name: 'one.png' }, { name: 'two.png' }]);

        if (component.$store.global.beautifySelectedScreenshotId !== 'shot_new_1') {
          throw new Error(`expected first imported screenshot to become active, got ${component.$store.global.beautifySelectedScreenshotId}`);
        }
        '''
    )


def test_beautify_grid_preserves_global_name_drafts_during_avatar_uploads():
    run_beautify_grid_runtime_check(
        '''
        globalThis.__gridStubs = {
          importGlobalBeautifyAvatar: async () => ({
            success: true,
            item: {
              identities: {
                character: { name: '已保存角色', avatar_file: 'character.png' },
                user: { name: '已保存用户', avatar_file: '' },
              },
            },
          }),
        };

        const component = module.default();
        component.$store = { global: { showToast: () => {} } };
        component.globalCharacterName = '草稿角色';
        component.globalUserName = '草稿用户';

        await component.handleGlobalAvatarFile('character', [{ name: 'avatar.png' }]);

        if (component.globalCharacterName !== '草稿角色' || component.globalUserName !== '草稿用户') {
          throw new Error('global draft names should survive avatar uploads');
        }
        '''
    )


def test_beautify_grid_preserves_package_name_drafts_during_avatar_uploads():
    run_beautify_grid_runtime_check(
        '''
        globalThis.__gridStubs = {
          importBeautifyPackageAvatar: async () => ({
            success: true,
            item: {
              avatar_file: 'character.png',
            },
          }),
          getBeautifyPackage: async () => ({
            success: true,
            item: {
              id: 'pkg_demo',
              variants: {},
              wallpapers: {},
              screenshots: {},
              identity_overrides: {
                character: { name: '已保存角色', avatar_file: 'character.png' },
                user: { name: '已保存用户', avatar_file: '' },
              },
            },
          }),
        };

        const component = module.default();
        component.$store = {
          global: {
            beautifySelectedPackageId: 'pkg_demo',
            beautifySelectedScreenshotId: '',
            showToast: () => {},
          },
        };
        component.packageCharacterName = '草稿角色';
        component.packageUserName = '草稿用户';

        await component.handlePackageAvatarFile('character', [{ name: 'avatar.png' }]);

        if (component.packageCharacterName !== '草稿角色' || component.packageUserName !== '草稿用户') {
          throw new Error('package draft names should survive avatar uploads');
        }
        '''
    )


def test_state_js_keeps_beautify_store_keys():
    state_js = read_project_file('static/js/state.js')

    expected_keys = (
        'beautifyList',
        'beautifySearch',
        'beautifyPlatformFilter',
        'beautifySelectedPackageId',
        'beautifySelectedVariantId',
        'beautifySelectedWallpaperId',
        'beautifyPreviewDevice',
        'beautifyActiveDetail',
        'beautifyActiveVariant',
        'beautifyActiveWallpaper',
    )

    for key in expected_keys:
        assert_contains_any(state_js, (f'{key}:', f'"{key}":', f"'{key}':"))

    assert 'beautifyInstallFilter' not in state_js


def test_state_js_keeps_extended_beautify_store_keys():
    state_js = read_project_file('static/js/state.js')

    assert 'beautifyWorkspace: "packages"' in state_js
    assert 'beautifySelectedScreenshotId: ""' in state_js
    assert 'beautifyStageMode: "preview"' in state_js
    assert 'beautifyGlobalSettings: null' in state_js


def test_header_js_binds_beautify_search_and_mobile_upload_mode():
    header_js = read_project_file('static/js/components/header.js')

    assert_contains_any(header_js, ('"beautify"', "'beautify'"))
    assert_contains_any(header_js, ('get beautifySearch()', 'get beautifySearch ()'))
    assert_contains_any(header_js, ('return this.$store.global.beautifySearch;', 'return this.$store.global.beautifySearch || "";', "return this.$store.global.beautifySearch || '';"))
    assert_contains_any(header_js, ('set beautifySearch(val)', 'set beautifySearch (val)'))
    assert 'this.$store.global.beautifySearch = val;' in header_js
    assert_contains_any(header_js, ('new CustomEvent("request-mobile-upload")', "new CustomEvent('request-mobile-upload')"))


def test_layout_or_sidebar_keeps_beautify_mode_refresh_and_upload_routing():
    layout_js = read_project_file('static/js/components/layout.js')
    sidebar_js = read_project_file('static/js/components/sidebar.js')

    assert_contains_any(layout_js, ('mode !== "beautify"', "mode !== 'beautify'"))
    assert_contains_any(layout_js, ('mode === "beautify"', "mode === 'beautify'"))
    assert_contains_any(layout_js, ('new CustomEvent("refresh-beautify-list")', "new CustomEvent('refresh-beautify-list')"))

    assert_contains_any(sidebar_js, ('const mode = this.currentMode;',))
    assert_contains_any(sidebar_js, ('mode === "beautify"', "mode === 'beautify'"))
    assert_contains_any(sidebar_js, ('window.stUploadBeautifyThemeFiles(files);',))
    assert_contains_any(sidebar_js, ('window.dispatchEvent(new CustomEvent("refresh-beautify-list"));', "window.dispatchEvent(new CustomEvent('refresh-beautify-list'));"))


def test_beautify_preview_document_module_exports_document_builder_contract():
    module_source = read_project_file('static/js/components/beautifyPreviewDocument.js')

    assert 'export function buildBeautifyPreviewDocument(' in module_source
    assert 'export function buildBeautifyPreviewThemeVars(' in module_source
    assert 'export function buildBeautifyPreviewSampleMarkup(' in module_source
    assert 'function buildPreviewBehaviorScript(' in module_source


def test_beautify_preview_frame_uses_render_isolated_html_and_preview_document_builder():
    source = read_project_file('static/js/components/beautifyPreviewFrame.js')

    assert 'renderIsolatedHtml' in source
    assert 'clearIsolatedHtml' in source
    assert 'buildBeautifyPreviewDocument' in source
    assert 'buildBeautifyPreviewAssetUrl' in source
    assert 'customCssMarkup()' not in source
    assert 'function resolvePreviewRenderMinHeight(platform)' in source
    assert 'return platform === "mobile" ? 420 : 520;' in source or "return platform === 'mobile' ? 420 : 520;" in source
    assert 'minHeight: resolvePreviewRenderMinHeight(state.platform),' in source
    assert 'maxHeight:' not in source


def test_beautify_preview_frame_prefers_package_assets_then_global_settings():
    run_beautify_preview_frame_runtime_check(
        '''
        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'packages',
            beautifyPreviewDevice: 'pc',
            beautifyActiveDetail: {
              identity_overrides: {
                character: { name: '包角色', avatar_file: 'data/library/beautify/packages/pkg_demo/avatars/character.png' },
                user: { name: '', avatar_file: '' },
              },
            },
            beautifyActiveVariant: { theme_data: { name: 'Demo' } },
            beautifyActiveWallpaper: null,
            beautifyGlobalSettings: {
              wallpaper: { file: 'data/library/beautify/global/wallpapers/wallpaper.png' },
              identities: {
                character: { name: '全局角色', avatar_file: 'data/library/beautify/global/avatars/character.png' },
                user: { name: '全局用户', avatar_file: 'data/library/beautify/global/avatars/user.png' },
              },
            },
          },
        };

        const state = component.resolvePreviewState();
        if (state.wallpaperUrl !== 'data/library/beautify/global/wallpapers/wallpaper.png') throw new Error('missing global wallpaper fallback');
        if (state.identities.character.name !== '包角色') throw new Error('package override should win');
        if (state.identities.user.name !== '全局用户') throw new Error('global user fallback should win');
        '''
    )


def test_beautify_preview_frame_prefers_selected_package_wallpaper_over_global_fallback():
    run_beautify_preview_frame_runtime_check(
        '''
        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'packages',
            beautifyPreviewDevice: 'pc',
            beautifyActiveDetail: { identity_overrides: {} },
            beautifyActiveVariant: { theme_data: { name: 'Demo' } },
            beautifyActiveWallpaper: {
              file: 'data/library/beautify/packages/pkg_demo/wallpapers/package.png',
            },
            beautifyGlobalSettings: {
              wallpaper: { file: 'data/library/beautify/global/wallpapers/global.png' },
              identities: {
                character: { name: '全局角色', avatar_file: '' },
                user: { name: '全局用户', avatar_file: '' },
              },
            },
          },
        };

        const state = component.resolvePreviewState();
        if (state.wallpaperUrl !== 'data/library/beautify/packages/pkg_demo/wallpapers/package.png') {
          throw new Error('selected package wallpaper should win');
        }
        '''
    )


def test_beautify_preview_frame_uses_global_only_preview_in_settings_workspace():
    run_beautify_preview_frame_runtime_check(
        '''
        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'settings',
            beautifyPreviewDevice: 'mobile',
            beautifyActiveDetail: {
              identity_overrides: {
                character: { name: '包角色', avatar_file: 'data/library/beautify/packages/pkg_demo/avatars/character.png' },
                user: { name: '包用户', avatar_file: 'data/library/beautify/packages/pkg_demo/avatars/user.png' },
              },
            },
            beautifyActiveVariant: { theme_data: { name: 'Package Theme' } },
            beautifyActiveWallpaper: {
              file: 'data/library/beautify/packages/pkg_demo/wallpapers/package.png',
            },
            beautifyGlobalSettings: {
              wallpaper: { file: 'data/library/beautify/global/wallpapers/global.png' },
              identities: {
                character: { name: '全局角色', avatar_file: 'data/library/beautify/global/avatars/character.png' },
                user: { name: '全局用户', avatar_file: 'data/library/beautify/global/avatars/user.png' },
              },
            },
          },
        };

        const state = component.resolvePreviewState();
        if (state.platform !== 'mobile') throw new Error('settings workspace should still respect preview shell mode');
        if (state.theme.name) throw new Error('settings workspace should ignore package theme data');
        if (state.wallpaperUrl !== 'data/library/beautify/global/wallpapers/global.png') throw new Error('settings workspace should use global wallpaper');
        if (state.identities.character.name !== '全局角色') throw new Error('settings workspace should ignore package character override');
        if (state.identities.user.name !== '全局用户') throw new Error('settings workspace should ignore package user override');
        '''
    )


def test_beautify_preview_frame_allows_settings_workspace_preview_without_active_package():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'settings',
            beautifyPreviewDevice: 'pc',
            beautifyActiveDetail: null,
            beautifyActiveVariant: null,
            beautifyActiveWallpaper: null,
            beautifyGlobalSettings: {
              wallpaper: { file: 'data/library/beautify/global/wallpapers/global.png' },
              identities: {
                character: { name: '全局角色', avatar_file: '' },
                user: { name: '全局用户', avatar_file: '' },
              },
            },
          },
        };
        component.$refs = { previewHost: host };
        component.$watch = () => {};
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        if (!host.__events.some((entry) => entry.type === 'render')) {
          throw new Error('settings workspace preview should render without active package detail');
        }
        '''
    )


def test_beautify_preview_frame_re_renders_when_workspace_or_global_settings_change():
    run_beautify_preview_frame_runtime_check(
        '''
        const watchers = new Map();
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyWorkspace: 'packages',
            beautifyPreviewDevice: 'pc',
            beautifyActiveDetail: { id: 'detail-1', identity_overrides: {} },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyGlobalSettings: {
              wallpaper: { file: 'data/library/beautify/global/wallpapers/one.png' },
              identities: {
                character: { name: '角色一', avatar_file: '' },
                user: { name: '用户一', avatar_file: '' },
              },
            },
          },
        };
        component.$refs = { previewHost: host };
        component.$watch = (key, callback) => watchers.set(key, callback);
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        const initialRenderCount = host.__events.filter((entry) => entry.type === 'render').length;
        const workspaceWatcher = watchers.get('$store.global.beautifyWorkspace');
        const settingsWatcher = watchers.get('$store.global.beautifyGlobalSettings');
        if (typeof workspaceWatcher !== 'function') throw new Error('expected workspace watcher');
        if (typeof settingsWatcher !== 'function') throw new Error('expected global settings watcher');

        component.$store.global.beautifyWorkspace = 'settings';
        workspaceWatcher('settings');
        component.$store.global.beautifyGlobalSettings = {
          wallpaper: { file: 'data/library/beautify/global/wallpapers/two.png' },
          identities: {
            character: { name: '角色二', avatar_file: '' },
            user: { name: '用户二', avatar_file: '' },
          },
        };
        settingsWatcher(component.$store.global.beautifyGlobalSettings);

        const renderCount = host.__events.filter((entry) => entry.type === 'render').length;
        if (renderCount < initialRenderCount + 2) {
          throw new Error(`expected rerenders after workspace/global-settings changes, got ${renderCount - initialRenderCount}`);
        }
        '''
    )


def test_beautify_preview_frame_keeps_preview_unloaded_until_user_requests_it():
    source = read_project_file('static/js/components/beautifyPreviewFrame.js')

    assert 'isPreviewLoaded' in source
    assert 'loadPreview()' in source
    assert 'if (!this.isPreviewLoaded) {' in source


def test_beautify_preview_frame_retries_render_after_preview_host_ref_appears():
    source = read_project_file('static/js/components/beautifyPreviewFrame.js')

    assert 'this.$nextTick(() =>' in source
    assert 'this.renderPreview();' in source
    assert_contains_any(source, ('this.$watch("$store.global.beautifyActiveDetail"', "this.$watch('$store.global.beautifyActiveDetail'"))
    assert_contains_any(source, ('this.$watch("$store.global.beautifyActiveVariant"', "this.$watch('$store.global.beautifyActiveVariant'"))
    assert_contains_any(source, ('this.$watch("$store.global.beautifyActiveWallpaper"', "this.$watch('$store.global.beautifyActiveWallpaper'"))
    assert_contains_any(source, ('this.$watch("$store.global.beautifyPreviewDevice"', "this.$watch('$store.global.beautifyPreviewDevice'"))
    assert 'if (!host) {' in source


def test_beautify_preview_frame_clears_runtime_when_active_detail_disappears():
    source = read_project_file('static/js/components/beautifyPreviewFrame.js')

    assert_contains_any(
        source,
        (
            'this.$watch("$store.global.beautifyActiveDetail", (detail) => {',
            "this.$watch('$store.global.beautifyActiveDetail', (detail) => {",
        ),
    )
    assert 'if (!detail) {' in source
    assert 'this.destroy();' in source


def test_beautify_preview_frame_falls_back_to_dom_query_when_alpine_ref_is_unavailable():
    source = read_project_file('static/js/components/beautifyPreviewFrame.js')

    assert 'this.$refs.previewHost' in source
    assert "querySelector('.beautify-preview-host')" in source or 'querySelector(".beautify-preview-host")' in source


def test_beautify_preview_frame_does_not_render_until_load_preview_is_called():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };
        component.$refs = { previewHost: host };
        component.$watch = () => {};
        component.$nextTick = (callback) => callback();

        component.init();

        if (host.__events.some((entry) => entry.type === 'render')) {
          throw new Error('preview should not render before manual activation');
        }

        component.loadPreview();

        if (!host.__events.some((entry) => entry.type === 'render')) {
          throw new Error('preview should render after manual activation');
        }
        '''
    )


def test_beautify_preview_frame_retries_after_load_when_host_is_not_ready_on_first_tick():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };

        let nextTickCount = 0;
        component.$refs = {};
        component.$el = {
          querySelector: () => (nextTickCount >= 2 ? host : null),
        };
        component.$watch = () => {};
        component.$nextTick = (callback) => {
          nextTickCount += 1;
          callback();
        };

        component.init();
        component.loadPreview();

        const renderEvents = host.__events.filter((entry) => entry.type === 'render');
        if (renderEvents.length !== 1) {
          throw new Error(`expected one delayed render after host mount, got ${renderEvents.length}`);
        }
        '''
    )


def test_beautify_preview_frame_retries_on_next_paint_when_host_mounts_after_next_tick_budget_is_exhausted():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };

        let paintReady = false;
        component.$refs = {};
        component.$el = {
          querySelector: () => (paintReady ? host : null),
        };
        globalThis.window = {
          requestAnimationFrame: (callback) => {
            paintReady = true;
            callback();
            return 1;
          },
          setTimeout: (callback) => {
            paintReady = true;
            callback();
            return 1;
          },
        };
        component.$watch = () => {};
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        const renderEvents = host.__events.filter((entry) => entry.type === 'render');
        if (renderEvents.length !== 1) {
          throw new Error(`expected one render after next paint host mount, got ${renderEvents.length}`);
        }
        '''
    )


def test_beautify_preview_frame_uses_timeout_backup_when_frame_retry_callback_never_fires():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };

        let timeoutReady = false;
        component.$refs = {};
        component.$el = {
          querySelector: () => (timeoutReady ? host : null),
        };
        globalThis.window = {
          requestAnimationFrame: () => 1,
          setTimeout: (callback) => {
            timeoutReady = true;
            callback();
            return 1;
          },
        };
        component.$watch = () => {};
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        const renderEvents = host.__events.filter((entry) => entry.type === 'render');
        if (renderEvents.length !== 1) {
          throw new Error(`expected one render after timeout backup, got ${renderEvents.length}`);
        }
        '''
    )


def test_beautify_preview_frame_renders_when_preview_host_is_inserted_after_activation():
    run_beautify_preview_frame_runtime_check(
        '''
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };

        let hostReady = false;
        const observers = [];
        component.$refs = {};
        component.$el = {
          querySelector: () => (hostReady ? host : null),
        };
        globalThis.MutationObserver = class MutationObserver {
          constructor(callback) {
            this.callback = callback;
            observers.push(this);
          }
          observe() {}
          disconnect() {}
        };
        globalThis.window = {
          requestAnimationFrame: () => 1,
          setTimeout: () => 1,
        };
        component.$watch = () => {};
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        hostReady = true;
        for (const observer of observers) {
          observer.callback([{ type: 'childList' }]);
        }

        const renderEvents = host.__events.filter((entry) => entry.type === 'render');
        if (renderEvents.length !== 1) {
          throw new Error(`expected one render after host insertion, got ${renderEvents.length}`);
        }
        '''
    )


def test_beautify_preview_frame_restarts_observer_after_destroy_and_reload():
    run_beautify_preview_frame_runtime_check(
        '''
        const watchers = new Map();
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        const observers = [];
        component.$store = {
          global: {
            beautifyActiveDetail: { id: 'detail-1', identity_overrides: {} },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyGlobalSettings: { identities: {}, wallpaper: {} },
            beautifyWorkspace: 'packages',
            beautifyPreviewDevice: 'pc',
          },
        };
        component.$refs = { previewHost: host };
        component.$el = { querySelector: () => host };
        component.$watch = (key, callback) => watchers.set(key, callback);
        component.$nextTick = (callback) => callback();
        globalThis.MutationObserver = class MutationObserver {
          constructor(callback) {
            this.callback = callback;
            this.disconnected = false;
            observers.push(this);
          }
          observe() {}
          disconnect() { this.disconnected = true; }
        };

        component.init();
        component.loadPreview();

        const detailWatcher = watchers.get('$store.global.beautifyActiveDetail');
        if (typeof detailWatcher !== 'function') throw new Error('expected active detail watcher');

        detailWatcher(null);
        if (!observers[0]?.disconnected) throw new Error('expected first observer to disconnect on destroy');

        component.$store.global.beautifyActiveDetail = { id: 'detail-2', identity_overrides: {} };
        detailWatcher(component.$store.global.beautifyActiveDetail);
        component.loadPreview();

        if (observers.length < 2) throw new Error('expected observer to restart on reload');
        if (observers[1].disconnected) throw new Error('new observer should stay connected after reload');
        '''
    )


def test_beautify_preview_frame_re_renders_when_beautify_mode_becomes_visible_after_hidden_init():
    run_beautify_preview_frame_runtime_check(
        '''
        const watchers = new Map();
        const host = { innerHTML: '', __events: [] };
        const component = module.default();
        component.$store = {
          global: {
            currentMode: 'chat',
            beautifyActiveDetail: { id: 'detail-1' },
            beautifyActiveVariant: { theme_data: {} },
            beautifyActiveWallpaper: {},
            beautifyPreviewDevice: 'pc',
          },
        };
        component.$refs = { previewHost: host };
        component.$watch = (key, callback) => watchers.set(key, callback);
        component.$nextTick = (callback) => callback();

        component.init();
        component.loadPreview();

        const initialRenderCount = host.__events.filter((entry) => entry.type === 'render').length;
        const variantWatcher = watchers.get('$store.global.beautifyActiveVariant');
        if (typeof variantWatcher !== 'function') {
          throw new Error('expected active variant watcher to be registered');
        }

        component.$store.global.beautifyActiveVariant = { theme_data: { custom_css: 'body{color:red;}' } };
        variantWatcher(component.$store.global.beautifyActiveVariant);

        const renderCountAfterVariantChange = host.__events.filter((entry) => entry.type === 'render').length;
        if (renderCountAfterVariantChange !== initialRenderCount + 1) {
          throw new Error(`expected one rerender after active variant change, got ${renderCountAfterVariantChange - initialRenderCount}`);
        }
        '''
    )
