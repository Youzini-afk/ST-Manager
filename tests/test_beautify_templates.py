import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_sidebar_template_places_beautify_last_in_second_resource_row():
    template = read_project_file('templates/components/sidebar.html')

    presets_index = template.index("switchMode('presets')")
    regex_index = template.index("switchMode('regex')")
    scripts_index = template.index("switchMode('scripts')")
    quick_replies_index = template.index("switchMode('quick_replies')")
    beautify_index = template.index("switchMode('beautify')")

    assert presets_index < regex_index < scripts_index < quick_replies_index < beautify_index
    assert '美化' in template[beautify_index: beautify_index + 120]


def test_sidebar_template_keeps_live_beautify_sidebar_panel_hook():
    template = read_project_file('templates/components/sidebar.html')

    assert 'beautify-sidebar-panel' in template


def test_sidebar_template_adds_beautify_workspace_switcher_and_screenshot_import():
    template = read_project_file('templates/components/sidebar.html')

    assert 'beautifyWorkspace' in template
    assert 'switchBeautifyWorkspace(' in template
    assert '导入截图' in template
    assert 'handleScreenshotFiles($event.target.files)' in template
    assert ':disabled="!selectedPackageId"' in template or ":disabled='!selectedPackageId'" in template


def test_index_template_includes_dedicated_beautify_grid_view():
    template = read_project_file('templates/index.html')
    assert '{% include "components/grid_beautify.html" %}' in template
    assert '<div class="main-container" x-data="beautifyGrid">' in template


def test_index_template_lifts_beautify_scope_above_sidebar_and_grid_includes():
    template = read_project_file('templates/index.html')

    main_container_index = template.index('<div class="main-container" x-data="beautifyGrid">')
    sidebar_index = template.index('{% include "components/sidebar.html" %}')
    beautify_grid_index = template.index('{% include "components/grid_beautify.html" %}')

    assert main_container_index < sidebar_index < beautify_grid_index


def test_beautify_grid_template_keeps_stage_only_markup_and_controls():
    template = read_project_file('templates/components/grid_beautify.html')

    assert '$store.global.currentMode === \"beautify\"' in template or "$store.global.currentMode === 'beautify'" in template
    assert 'beautify-layout' in template
    assert 'beautify-stage-pane' in template
    assert 'beautify-sidebar-pane' not in template
    assert 'x-data="beautifyGrid"' not in template
    assert 'selectedVariantPlatform === \'pc\'' in template or 'selectedVariantPlatform === "pc"' in template
    assert 'selectedVariantPlatform === \'mobile\'' in template or 'selectedVariantPlatform === "mobile"' in template


def test_beautify_grid_template_supports_screenshot_stage_and_global_settings_form():
    template = read_project_file('templates/components/grid_beautify.html')

    assert 'stageMode === "preview"' in template or "stageMode === 'preview'" in template
    assert 'stageMode === "screenshot"' in template or "stageMode === 'screenshot'" in template
    assert '全局壁纸' in template
    assert '角色默认资料' in template
    assert '用户默认资料' in template
    assert '角色与用户覆盖' in template
    assert '截图查看' in template
    assert 'activeScreenshot' in template
    assert 'beautifyWorkspace === "settings"' in template or "beautifyWorkspace === 'settings'" in template


def test_beautify_grid_template_adds_screenshot_picker_package_identity_bindings_and_avatar_actions():
    template = read_project_file('templates/components/grid_beautify.html')

    assert 'x-for="screenshot in screenshotOptions"' in template or "x-for='screenshot in screenshotOptions'" in template
    assert '@click="selectScreenshot(screenshot.id)"' in template or "@click='selectScreenshot(screenshot.id)'" in template
    assert 'x-model="packageCharacterName"' in template or "x-model='packageCharacterName'" in template
    assert 'x-model="packageUserName"' in template or "x-model='packageUserName'" in template
    assert "handlePackageAvatarFile('character', $event.target.files)" in template or 'handlePackageAvatarFile("character", $event.target.files)' in template
    assert "handlePackageAvatarFile('user', $event.target.files)" in template or 'handlePackageAvatarFile("user", $event.target.files)' in template
    assert '@click="clearPackageCharacterAvatar()"' in template or "@click='clearPackageCharacterAvatar()'" in template
    assert '@click="clearPackageUserAvatar()"' in template or "@click='clearPackageUserAvatar()'" in template
    assert '未设置，将使用全局默认角色资料' in template
    assert '未设置，将使用全局默认用户资料' in template
    assert '当前角色头像已覆盖全局设置' in template
    assert '当前用户头像已覆盖全局设置' in template


def test_beautify_grid_template_settings_workspace_keeps_global_preview_surface():
    template = read_project_file('templates/components/grid_beautify.html')

    assert '全局默认预览' in template
    assert '不会带入当前包的主题与覆盖' in template


def test_beautify_grid_template_disables_preview_only_controls_in_screenshot_mode():
    template = read_project_file('templates/components/grid_beautify.html')

    assert ":disabled=\"stageMode === 'screenshot' || !hasPcVariant\"" in template or ':disabled="stageMode === \"screenshot\" || !hasPcVariant"' in template
    assert ":disabled=\"stageMode === 'screenshot' || !hasMobileVariant\"" in template or ':disabled="stageMode === \"screenshot\" || !hasMobileVariant"' in template
    assert ":disabled=\"stageMode === 'screenshot' || !hasDualVariant\"" in template or ':disabled="stageMode === \"screenshot\" || !hasDualVariant"' in template
    assert ":disabled=\"stageMode === 'screenshot' || wallpaperOptions.length === 0\"" in template or ':disabled="stageMode === \"screenshot\" || wallpaperOptions.length === 0"' in template


def test_beautify_grid_template_removes_install_and_apply_actions_and_approximation_copy():
    template = read_project_file('templates/components/grid_beautify.html')

    assert '安装到 ST' not in template
    assert '立即应用' not in template
    assert '当前预览为近似效果' not in template
    assert '安装与立即应用操作' not in template


def test_beautify_grid_template_uses_manual_native_preview_trigger():
    template = read_project_file('templates/components/grid_beautify.html')

    assert '加载原生 ST 预览' in template
    assert 'x-if="!isPreviewLoaded"' in template or "x-if='!isPreviewLoaded'" in template
    assert '@click="loadPreview()"' in template or "@click='loadPreview()'" in template
    assert 'previewHost' in template
    assert 'previewApproximateNoticeVisible' not in template


def test_beautify_grid_template_wraps_package_preview_states_in_single_root():
    template = read_project_file('templates/components/grid_beautify.html')

    assert re.search(
        r'<template x-if="stageMode === [\'"]preview[\'"]">\s*<div class="beautify-preview-stage">',
        template,
    )


def test_beautify_grid_template_keeps_unavailable_device_button_disabled_instead_of_hidden():
    template = read_project_file('templates/components/grid_beautify.html')
    assert '!hasPcVariant' in template
    assert '!hasMobileVariant' in template


def test_beautify_grid_template_uses_isolated_preview_host_instead_of_inline_preview_dom():
    template = read_project_file('templates/components/grid_beautify.html')

    assert 'beautify-preview-host' in template
    assert 'x-ref="previewHost"' in template or "x-ref='previewHost'" in template
    assert 'beautify-preview-frame-shell' in template
    assert 'beautify-preview-chat-window' not in template
    assert 'beautify-preview-inputbar' not in template
    assert 'customCssMarkup()' not in template


def test_beautify_layout_css_uses_shared_sidebar_flex_contract():
    css = read_project_file('static/css/modules/view-beautify.css')
    layout_block = css.split('.beautify-layout {', 1)[1].split('}', 1)[0]
    sidebar_block = css.split('.beautify-sidebar-panel {', 1)[1].split('}', 1)[0]
    stage_block = css.split('.beautify-stage-pane {', 1)[1].split('}', 1)[0]

    assert '.beautify-layout {' in css
    assert 'display: flex;' in layout_block
    assert 'min-width: 0;' in layout_block
    assert 'grid-template-columns' not in layout_block
    assert '.beautify-sidebar-panel {' in css
    assert 'display: flex;' in sidebar_block
    assert 'flex-direction: column;' in sidebar_block
    assert 'min-height: 0;' in sidebar_block
    assert '.beautify-stage-pane {' in css
    assert 'flex: 1;' in stage_block
    assert 'min-width: 0;' in stage_block
    assert 'min-height: 0;' in stage_block
    assert 'overflow-y: auto;' in stage_block
    assert 'overflow-x: hidden;' in stage_block
    assert '.beautify-sidebar-pane {' not in css


def test_beautify_layout_css_styles_isolated_preview_host_shell():
    css = read_project_file('static/css/modules/view-beautify.css')
    unloaded_block = css.split('.beautify-preview-unloaded-card {', 1)[1].split('}', 1)[0]
    frame_shell_block = css.split('.beautify-preview-frame-shell {', 1)[1].split('}', 1)[0]
    preview_host_block = css.split('.beautify-preview-host {', 1)[1].split('}', 1)[0]
    mobile_shell_block = css.split('.beautify-preview-frame-shell.is-mobile {', 1)[1].split('}', 1)[0]

    assert '.beautify-preview-unloaded-card {' in css
    assert 'min-height: 280px;' in unloaded_block
    assert 'justify-content: center;' in unloaded_block
    assert '.beautify-preview-frame-shell {' in css
    assert 'block-size: clamp(' in frame_shell_block
    assert 'overflow: hidden;' in frame_shell_block
    assert '.beautify-preview-host {' in css
    assert 'flex: 1;' in preview_host_block
    assert 'width: 100%;' in preview_host_block
    assert 'height: 100%;' in preview_host_block
    assert 'border: 0;' in preview_host_block
    assert 'background: transparent;' in preview_host_block
    assert '.beautify-preview-frame-shell.is-mobile {' in css
    assert 'max-width: 420px;' in mobile_shell_block
    assert '.beautify-preview-chat-window {' not in css
    assert '.beautify-preview-inputbar {' not in css


def test_beautify_grid_template_mobile_css_drops_grid_area_layout():
    css = read_project_file('static/css/modules/view-beautify.css')

    mobile_block = css.split('@media (max-width: 900px) {', 1)[1]

    assert 'grid-template-areas' not in mobile_block
    assert '.sidebar-mobile .beautify-sidebar-panel {' in mobile_block


def test_beautify_stage_header_actions_keep_delete_button_horizontal():
    css = read_project_file('static/css/modules/view-beautify.css')
    header_actions_block = css.split('.beautify-stage-header-actions {', 1)[1].split('}', 1)[0]
    delete_button_block = css.split('.beautify-stage-header-actions .beautify-soft-btn {', 1)[1].split('}', 1)[0]
    platform_select_block = css.split('.beautify-stage-header-actions .beautify-filter-select {', 1)[1].split('}', 1)[0]

    assert 'flex-wrap: nowrap;' in header_actions_block
    assert 'justify-content: flex-end;' in header_actions_block
    assert 'white-space: nowrap;' in delete_button_block
    assert 'flex: 0 0 auto;' in delete_button_block
    assert 'width: auto;' in platform_select_block
    assert 'flex: 0 1 220px;' in platform_select_block
