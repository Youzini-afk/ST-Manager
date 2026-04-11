from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_preset_detail_reader_js_exposes_reader_view_state_and_helpers_contracts():
    source = read_project_file('static/js/components/presetDetailReader.js')

    assert 'activeGroup:' in source
    assert 'activeItemId:' in source
    assert 'searchTerm:' in source
    assert 'uiFilter:' in source
    assert 'showRightPanel:' in source
    assert 'showMobileSidebar:' in source

    assert 'get readerView() {' in source
    assert 'get readerGroups() {' in source
    assert 'get readerItems() {' in source
    assert 'get filteredItems() {' in source
    assert 'get activeItem() {' in source
    assert 'get readerStats() {' in source

    assert 'selectGroup(groupId) {' in source
    assert 'selectItem(itemId) {' in source
    assert 'getItemValuePreview(item) {' in source
    assert 'getItemBadge(item) {' in source
    assert 'formatItemPayload(item) {' in source


def test_preset_detail_reader_template_uses_reader_view_three_column_layout_contracts():
    source = read_project_file('templates/modals/detail_preset_popup.html')

    assert 'x-model="searchTerm"' in source
    assert '@click="selectGroup(group.id)"' in source
    assert 'x-for="item in filteredItems"' in source
    assert '@click="selectItem(item.id)"' in source
    assert 'x-show="showRightPanel || $store.global.deviceType !== ' in source
    assert 'x-text="activeItem?.title ||' in source
    assert 'readerStats.prompt_count' in source
    assert 'readerStats.unknown_count' in source


def test_preset_detail_reader_prompt_cards_follow_legacy_reader_conventions():
    source = read_project_file('templates/modals/detail_preset_popup.html')

    assert "x-text=\"getPromptDisplayTitle(item)\"" in source
    assert 'x-text="item.id"' not in source
    assert "x-text=\"getPromptIcon(item)\"" in source
    assert "x-text=\"getPromptRoleLabel(item)\"" in source
    assert "x-text=\"isPromptEnabled(item) ? 'ON' : 'OFF'\"" in source
    assert '系统自动注入的内容位置占位符' in source


def test_preset_detail_reader_js_exposes_legacy_prompt_display_helpers():
    source = read_project_file('static/js/components/presetDetailReader.js')

    assert 'getPromptDisplayTitle(item) {' in source
    assert 'isPromptEnabled(item) {' in source
    assert 'isPromptMarker(item) {' in source
    assert 'getPromptIcon(item) {' in source
    assert 'getPromptRoleLabel(item) {' in source


def test_preset_detail_reader_flow_keeps_full_content_in_right_panel_only():
    source = read_project_file('templates/modals/detail_preset_popup.html')

    assert 'line-clamp-3' in source or 'line-clamp-4' in source
    assert 'Summary' not in source
    assert 'Prompt Detail' in source
    assert 'x-text="activeItem.payload?.content || \'\'"' in source
