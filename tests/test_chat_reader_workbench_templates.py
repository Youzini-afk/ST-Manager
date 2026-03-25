from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def extract_css_block(css_source, selector):
    selector_start = css_source.index(selector)
    block_start = css_source.index('{', selector_start)
    block_end = css_source.index('}', block_start)
    return css_source[block_start + 1:block_end]


def extract_exact_css_block(css_source, selector):
    match = re.search(rf'(^|\n)\s*{re.escape(selector)}\s*\{{', css_source)
    if not match:
        raise ValueError(f'Exact selector not found: {selector}')

    selector_start = match.start()
    block_start = css_source.index('{', selector_start)
    block_end = css_source.index('}', block_start)
    return css_source[block_start + 1:block_end]


def extract_media_block(css_source, media_query):
    media_start = css_source.index(media_query)
    block_start = css_source.index('{', media_start)
    depth = 1
    index = block_start + 1

    while depth > 0:
        current_char = css_source[index]

        if current_char == '{':
            depth += 1
        elif current_char == '}':
            depth -= 1

        index += 1

    return css_source[block_start + 1:index - 1]


def extract_chat_reader_shell(template_source):
    shell_start = template_source.index('<div class="chat-reader-modal chat-reader-modal--fullscreen" role="dialog" aria-modal="true" aria-label="聊天阅读器">')
    settings_overlay_start = template_source.index('<div x-show="readerViewSettingsOpen"')
    return template_source[shell_start:settings_overlay_start]


def test_header_template_does_not_expose_runtime_inspector_controls():
    header_template = read_project_file('templates/components/header.html')

    assert 'openRuntimeInspector' not in header_template
    assert 'open-runtime-inspector' not in header_template
    assert '运行时检查器' not in header_template
    assert 'title="运行时检查器"' not in header_template
    assert '<div class="menu-label">运行时</div>' not in header_template


def test_index_template_does_not_include_runtime_inspector_modal():
    index_template = read_project_file('templates/index.html')

    assert 'runtime_inspector.html' not in index_template
    assert 'runtime_inspector' not in index_template


def test_app_js_does_not_import_or_register_runtime_inspector():
    app_source = read_project_file('static/js/app.js')

    assert 'runtimeInspector' not in app_source
    assert 'runtimeInspector.js' not in app_source


def test_header_component_does_not_wire_runtime_inspector_events():
    header_source = read_project_file('static/js/components/header.js')

    assert 'openRuntimeInspector' not in header_source
    assert 'open-runtime-inspector' not in header_source


def test_advanced_editor_no_longer_listens_for_runtime_inspector_bridge_events():
    advanced_editor_source = read_project_file('static/js/components/advancedEditor.js')

    assert 'runtime-inspector-control' not in advanced_editor_source
    assert 'focus-script-runtime-owner' not in advanced_editor_source


def test_chat_reader_css_defines_workbench_theme_tokens():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    reader_overlay_block = extract_css_block(chat_reader_css, '.chat-reader-overlay')
    light_mode_overlay_block = extract_css_block(chat_reader_css, 'html.light-mode .chat-reader-overlay')

    required_tokens = [
        '--chat-reader-accent-soft',
        '--chat-reader-accent-strong',
        '--chat-reader-accent-border',
        '--chat-reader-accent-text',
        '--chat-reader-surface-raised',
        '--chat-reader-surface-selected',
        '--chat-reader-danger-soft',
        '--chat-reader-focus-ring',
    ]

    derived_token_prefixes = [
        '--chat-reader-accent-soft:',
        '--chat-reader-accent-strong:',
        '--chat-reader-accent-border:',
        '--chat-reader-accent-text:',
        '--chat-reader-surface-raised:',
        '--chat-reader-surface-selected:',
        '--chat-reader-focus-ring:',
    ]

    for token in required_tokens:
        assert token in chat_reader_css
        assert token in reader_overlay_block
        assert token in light_mode_overlay_block

    for block in (reader_overlay_block, light_mode_overlay_block):
        for line in block.splitlines():
            stripped_line = line.strip()

            if any(stripped_line.startswith(prefix) for prefix in derived_token_prefixes):
                assert '#' not in stripped_line


def test_chat_reader_icon_buttons_define_focus_visible_state():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-icon-button:focus-visible' in chat_reader_css
    assert 'outline: 2px solid var(--chat-reader-focus-ring)' in chat_reader_css
    assert 'outline-offset: 2px' in chat_reader_css


def test_chat_reader_template_contains_workbench_regions():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    shell = extract_chat_reader_shell(reader_template)

    shell_pattern = re.compile(
        r'<div class="chat-reader-header" :class=".*?readerResponsiveMode.*?">.*?'
        r'<div class="chat-reader-body" :style="readerBodyGridStyle">.*?'
        r'<aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar".*?>.*?'
        r'<main class="chat-reader-center custom-scrollbar" :style="readerCenterPaneStyle" @scroll.passive="handleReaderScroll\(\)">.*?'
        r'<aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar" :style="readerRightPaneStyle">',
        re.DOTALL,
    )

    assert shell_pattern.search(shell)
    assert shell.count('<aside ') == 2
    assert shell.index('class="chat-reader-header"') < shell.index('class="chat-reader-body"')
    assert '<div class="chat-reader-body" :style="readerBodyGridStyle">' in shell
    assert '<aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar"' in shell
    assert '\n            </aside>\n\n            <main class="chat-reader-center custom-scrollbar" :style="readerCenterPaneStyle" @scroll.passive="handleReaderScroll()">' in shell
    assert '\n            </main>\n\n            <aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar" :style="readerRightPaneStyle">' in shell


def test_chat_reader_template_groups_desktop_workbench_controls():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-context' in reader_template
    assert 'chat-reader-header-primary' in reader_template
    assert 'chat-reader-header-secondary' in reader_template
    assert 'chat-reader-panel-group' in reader_template
    assert 'chat-reader-danger-zone' in reader_template
    assert 'chat-reader-icon-button' in reader_template


def test_chat_reader_template_includes_mobile_drawer_segments():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'readerMobilePanel' in reader_template
    assert "readerMobilePanel === 'tools'" in reader_template
    assert "readerMobilePanel === 'search'" in reader_template
    assert "readerMobilePanel === 'navigator'" in reader_template


def test_chat_grid_tracks_mobile_reader_panel_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'readerMobilePanel' in chat_grid_source


def test_chat_grid_reconciles_reader_panel_state_on_device_type_changes():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'reconcileReaderPanelsForDeviceType' in chat_grid_source
    assert "this.$watch('$store.global.deviceType'" in chat_grid_source
    assert 'this.reconcileReaderPanelsForDeviceType();' in chat_grid_source
    assert "if (responsiveMode === 'mobile')" in chat_grid_source
    assert "if (responsiveMode === 'tablet')" in chat_grid_source
    assert "this.readerMobilePanel = this.readerShowLeftPanel ? 'tools' : (this.readerRightTab === 'floors' ? 'navigator' : 'search');" in chat_grid_source
    assert "this.readerShowLeftPanel = this.readerMobilePanel === 'tools';" in chat_grid_source
    assert "this.readerShowRightPanel = true;" in chat_grid_source


def test_chat_reader_template_keeps_all_nested_modal_entry_points():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    for entry_point in (
        'readerViewSettingsOpen',
        'regexConfigOpen',
        'editingFloor',
        'bindPickerOpen',
    ):
        assert entry_point in reader_template


def test_chat_reader_template_exposes_reader_status_and_accessibility_hooks():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'role="dialog"' in reader_template
    assert 'aria-modal="true"' in reader_template
    assert 'aria-label="聊天阅读器"' in reader_template
    assert 'role="status"' in reader_template
    assert 'aria-live="polite"' in reader_template
    assert 'role="alert"' in reader_template
    assert 'aria-live="assertive"' in reader_template
    assert 'aria-label="关闭工具栏"' in reader_template
    assert ':aria-label="readerMobilePanelCloseLabel"' in reader_template
    assert 'aria-label="关闭聊天阅读器"' in reader_template
    assert ":aria-label=\"isBookmarked(message.floor) ? '取消收藏楼层' : '收藏楼层'\"" in reader_template
    assert '危险操作 · 删除会直接移除当前聊天记录' in reader_template
    assert 'role="note"' in reader_template
    assert 'readerShellStatusText' in reader_template
    assert 'readerSaveFeedbackTone' in reader_template
    assert "readerMobilePanelCloseLabel" in reader_template
    assert ':aria-label="readerMobilePanelCloseLabel"' in reader_template
    assert ':title="readerMobilePanelCloseLabel"' in reader_template
    assert '@keydown.escape.window.prevent="readerViewSettingsOpen = false"' in reader_template
    assert '@keydown.escape.window.prevent="closeRegexConfig()"' in reader_template
    assert '@keydown.escape.window.prevent="closeFloorEditor()"' in reader_template
    assert '@keydown.escape.window.prevent="closeBindPicker()"' in reader_template


def test_chat_grid_resets_reader_feedback_tone_to_steady_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'setReaderFeedbackTone(tone = \'neutral\')' in chat_grid_source
    assert "if (tone === 'error' || tone === 'danger' || tone === 'success')" in chat_grid_source
    assert "this.readerSaveFeedbackTone = this.replaceStatus || this.regexConfigStatus ? 'neutral' : 'neutral';" not in chat_grid_source
    assert "this.readerSaveFeedbackTone = this.replaceStatus || this.regexConfigStatus ? 'neutral' : 'neutral'" not in chat_grid_source
    assert 'this.setReaderFeedbackTone();' in chat_grid_source


def test_chat_reader_css_defines_distinct_tablet_and_mobile_breakpoints():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '@media (max-width: 1179px)' in chat_reader_css
    assert '@media (max-width: 899px)' in chat_reader_css


def test_chat_reader_template_keeps_header_identity_and_action_groups():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-main' in reader_template
    assert 'chat-reader-header-context' in reader_template
    assert 'chat-reader-header-actions' in reader_template
    assert 'chat-reader-header-tools' in reader_template
    assert 'chat-reader-shell-status-text' in reader_template


def test_chat_reader_css_promotes_shell_status_to_second_header_row():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    header_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header')
    main_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header-main')
    actions_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header-actions')
    shell_status_block = extract_exact_css_block(chat_reader_css, '.chat-reader-shell-status')

    assert 'flex-wrap: wrap' in header_block
    assert 'align-items: stretch' in header_block
    assert 'flex: 1 1 34rem' in main_block
    assert 'min-width: min(100%, 24rem)' in main_block
    assert 'max-width: 100%' in actions_block
    assert 'flex: 1 0 100%' in shell_status_block
    assert 'margin-top: 0' in shell_status_block


def test_chat_reader_css_keeps_tablet_actions_in_single_wrapping_row():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    tablet_block = extract_media_block(chat_reader_css, '@media (max-width: 1179px)')

    tablet_actions_block = extract_exact_css_block(tablet_block, '.chat-reader-header-actions')
    tablet_primary_block = extract_exact_css_block(tablet_block, '.chat-reader-header-primary')
    tablet_tools_block = extract_exact_css_block(tablet_block, '.chat-reader-header-tools')

    assert 'justify-content: flex-start' in tablet_actions_block
    assert 'align-items: center' in tablet_actions_block
    assert 'flex-direction: row' in tablet_primary_block
    assert 'align-items: center' in tablet_primary_block
    assert 'justify-content: flex-start' in tablet_tools_block


def test_chat_reader_css_rebalances_header_rows_at_narrow_widths():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    tablet_block = extract_media_block(chat_reader_css, '@media (max-width: 1179px)')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header-main,\n    .chat-reader-header-actions,\n    .chat-reader-header-context,\n    .chat-reader-header-primary,\n    .chat-reader-header-tools,\n    .chat-reader-header-stats {' not in tablet_block

    header_block = extract_css_block(tablet_block, '.chat-reader-header')
    assert 'flex-wrap: wrap' in header_block
    assert 'align-items: stretch' in header_block
    assert '.chat-grid-toolbar-actions,\n    .chat-reader-header,\n    .chat-reader-header-main {' not in tablet_block

    assert '.chat-reader-title-wrap {' in tablet_block
    assert 'width: 100%' in extract_css_block(tablet_block, '.chat-reader-title-wrap')

    title_block = extract_css_block(tablet_block, '.chat-reader-title')
    assert 'overflow-wrap: break-word' in title_block
    assert 'word-break: keep-all' in title_block

    assert '.chat-reader-header-actions {' in tablet_block
    assert '        width: 100%;' in tablet_block
    assert '        flex-wrap: wrap;' in tablet_block

    assert '.chat-reader-shell-status {' in tablet_block
    assert '        display: flex;' in tablet_block
    assert '        width: 100%;' in tablet_block
    assert '        flex-basis: 100%;' in tablet_block
    assert '        margin-top: 0;' in tablet_block

    assert '.chat-reader-header-main,\n    .chat-reader-header-actions,\n    .chat-reader-header-primary {' in mobile_block
    assert '        width: 100%' in mobile_block
    assert '.chat-reader-header-tools {' in mobile_block
    assert '        flex-direction: row;' in mobile_block
    assert '        justify-content: flex-start' in mobile_block


def test_chat_grid_mobile_reader_panel_state_keeps_one_active_panel():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "this.readerShowLeftPanel = active === 'tools';" in chat_grid_source
    assert "this.readerShowRightPanel = active === 'search' || active === 'navigator';" in chat_grid_source
    assert 'this.readerShowRightPanel = Boolean(active);' not in chat_grid_source


def test_chat_grid_reader_responsive_mode_uses_reactive_device_type_instead_of_window_width():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "const deviceType = this.$store.global.deviceType;" in chat_grid_source
    assert "if (deviceType === 'mobile')" in chat_grid_source
    assert "if (deviceType === 'tablet')" in chat_grid_source
    assert 'window.innerWidth < 900' not in chat_grid_source
    assert 'window.innerWidth < 1180' not in chat_grid_source


def test_chat_grid_reader_body_grid_style_drives_desktop_tablet_and_mobile_layouts_from_panel_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "return 'grid-template-columns: minmax(0, 1fr);';" in chat_grid_source
    assert "return `grid-template-columns: ${leftWidth}px minmax(0, 1fr);`;" in chat_grid_source
    assert "return `grid-template-columns: minmax(0, 1fr) ${rightWidth}px;`;" in chat_grid_source
    assert "return `grid-template-columns: ${leftWidth}px minmax(0, 1fr) ${rightWidth}px;`;" in chat_grid_source


def test_chat_reader_template_assigns_dynamic_grid_columns_to_center_and_right_panes():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert ":style=\"readerCenterPaneStyle\"" in reader_template
    assert ":style=\"readerRightPaneStyle\"" in reader_template
    assert ":style=\"readerLeftPaneStyle\"" in reader_template


def test_chat_reader_css_mobile_drawer_starts_below_header_instead_of_centering_content():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert 'padding: calc(var(--chat-reader-header-height) + 0.55rem) 0.85rem 1rem;' not in mobile_block
    assert 'top: var(--chat-reader-header-height);' in mobile_block
    assert 'padding: 0.85rem 0.85rem 1rem;' in mobile_block


def test_chat_reader_template_moves_mobile_meta_out_of_the_header_shell():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'readerShellStatusLineText' in reader_template
    assert 'x-show="readerResponsiveMode === \'mobile\'"' in reader_template
    assert '聊天概览' in reader_template


def test_chat_reader_css_compacts_mobile_header_for_reading_first_layout():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header {' in mobile_block
    assert 'padding: 0.62rem 0.72rem;' in mobile_block
    assert '.chat-reader-header-main {' in mobile_block
    assert 'flex: 1 1 auto;' in mobile_block
    assert '.chat-reader-header-actions {' in mobile_block
    assert 'align-items: center;' in mobile_block
    assert '.chat-reader-header-tools {' in mobile_block
    assert 'flex-direction: row;' in mobile_block
    assert '.chat-reader-header-secondary {' in mobile_block
    assert 'position: absolute;' in mobile_block


def test_chat_reader_css_mobile_toggle_buttons_use_compact_chip_widths():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-toggle {' in mobile_block
    assert 'width: auto;' in mobile_block
    assert 'min-width: 0;' in mobile_block
    assert '.chat-toolbar-btn--primary.chat-reader-mobile-save {' in mobile_block


def test_chat_reader_template_removes_duplicate_top_stats_and_keeps_single_status_row():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-stats' not in reader_template
    assert 'x-text="readerShellStatusLineText"' in reader_template
    assert 'chat-reader-state-pill' not in reader_template
    assert 'x-text="readerViewportStatusText"' not in reader_template.split('chat-reader-header', 1)[1].split('chat-reader-body', 1)[0]
    assert 'x-text="readerAnchorStatusText"' not in reader_template.split('chat-reader-header', 1)[1].split('chat-reader-body', 1)[0]


def test_chat_grid_exposes_status_line_text_with_message_count_and_anchor_summary():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'get readerShellStatusLineText() {' in chat_grid_source
    assert 'activeChat?.message_count' in chat_grid_source
    assert 'readerAnchorStatusText' in chat_grid_source


def test_chat_reader_css_positions_mobile_close_button_in_header_corner():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header {' in mobile_block
    assert 'position: sticky;' in mobile_block or 'position: sticky' in mobile_block
    assert '.chat-reader-header-secondary {' in mobile_block
    assert 'position: absolute;' in mobile_block
    assert 'top: 0.62rem;' in mobile_block
    assert 'right: 0.72rem;' in mobile_block


def test_chat_grid_tracks_mobile_header_visibility_state_for_scroll_hiding():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'readerMobileHeaderHidden:' in chat_grid_source
    assert 'readerLastScrollTop:' in chat_grid_source
    assert 'readerMobileHeaderHidden = true' in chat_grid_source
    assert 'readerMobileHeaderHidden = false' in chat_grid_source


def test_chat_reader_template_binds_mobile_header_hidden_class():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert "'is-' + readerResponsiveMode + ((readerResponsiveMode === 'mobile' && readerMobileHeaderHidden) ? ' is-mobile-hidden' : '')" in reader_template


def test_chat_reader_template_desktop_header_exposes_independent_tools_search_and_navigator_toggles():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert "@click=\"toggleReaderPanel('left')\">工具</button>" in reader_template
    assert "@click=\"openReaderDesktopPanel('search')\">搜索</button>" in reader_template
    assert "@click=\"openReaderDesktopPanel('navigator')\">导航</button>" in reader_template
    assert "x-show=\"readerResponsiveMode !== 'mobile'\"" in reader_template


def test_chat_grid_reader_desktop_panel_controls_close_only_the_target_panel():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "const isSamePanelOpen = this.readerShowRightPanel && this.readerRightTab === nextTab;" in chat_grid_source
    assert "this.readerShowRightPanel = false;" in chat_grid_source
    assert "this.readerRightTab = nextTab;" in chat_grid_source
    assert 'closeReaderRightPanel() {' in chat_grid_source
    close_right_section = chat_grid_source.split('closeReaderRightPanel() {', 1)[1].split('}', 1)[0]
    assert 'this.readerShowLeftPanel = false;' not in close_right_section


def test_chat_reader_template_right_close_button_uses_desktop_specific_close_logic():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert '@click="closeReaderRightPanel()"' in reader_template
    assert '@click="hideReaderPanels()"' not in reader_template.split('class="chat-reader-right custom-scrollbar"', 1)[1].split('</aside>', 1)[0]


def test_chat_grid_reader_pane_styles_reflow_center_when_left_panel_closes():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "return 'grid-column: 1;';" in chat_grid_source
    assert "return 'grid-column: 2;';" in chat_grid_source
    assert "return 'grid-column: 3;';" in chat_grid_source


def test_chat_reader_template_binds_desktop_pane_visibility_to_inline_display_styles():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert ":style=" in reader_template
    assert ':style="readerLeftPaneStyle"' in reader_template
    assert ':style="readerRightPaneStyle"' in reader_template


def test_chat_grid_reader_mobile_mode_is_not_only_ua_driven():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    layout_source = read_project_file('static/js/components/layout.js')

    assert 'readerResponsiveMode' in chat_grid_source
    assert 'window.innerWidth < 900' in layout_source
    assert 'window.innerWidth < 1180' in layout_source


def test_layout_recomputes_global_device_type_on_window_resize():
    layout_source = read_project_file('static/js/components/layout.js')

    assert "window.addEventListener('resize', () => {" in layout_source
    assert 'this.reDeviceType();' in layout_source
