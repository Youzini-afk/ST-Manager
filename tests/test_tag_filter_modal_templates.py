from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_tag_filter_template_adds_mobile_shell_and_tabs():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert 'tag-filter-mobile-shell' in template_source
    assert 'x-show="$store.global.deviceType === \'mobile\'"' in template_source
    assert 'tag-filter-mobile-topbar' in template_source
    assert 'tag-filter-mobile-tabs' in template_source
    assert "@click=\"switchMobileTagTab('filter')\"" in template_source
    assert "@click=\"switchMobileTagTab('sort')\"" in template_source
    assert "@click=\"switchMobileTagTab('delete')\"" in template_source
    assert "@click=\"switchMobileTagTab('category')\"" in template_source


def test_tag_filter_js_defines_mobile_active_tab_and_switch_helper():
    source = read_project_file('static/js/components/tagFilterModal.js')

    assert "mobileActiveTab: 'filter'" in source
    assert 'switchMobileTagTab(tab) {' in source
    assert 'syncMobileTabState(tab) {' in source


def test_tag_filter_js_keeps_mobile_tab_when_sync_rejects_switch():
    source = read_project_file('static/js/components/tagFilterModal.js')

    assert 'const changed = this.syncMobileTabState(tab);' in source
    assert 'if (changed === false) return;' in source
    assert 'this.mobileActiveTab = tab;' in source
    assert 'this.toggleSortMode();' not in source.split('syncMobileTabState(tab) {', 1)[1].split('init() {', 1)[0]


def test_tag_filter_template_mobile_tabs_expose_accessibility_state():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert 'aria-selected' in template_source
    assert 'role="tablist"' in template_source
    assert 'role="tab"' in template_source


def test_tag_filter_template_adds_mobile_mode_specific_panels_and_bottom_bar_markers():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert 'tag-filter-mobile-panel tag-filter-mobile-panel--filter' in template_source
    assert 'tag-filter-mobile-panel tag-filter-mobile-panel--delete' in template_source
    assert 'tag-filter-mobile-panel tag-filter-mobile-panel--category' in template_source
    assert 'tag-filter-mobile-bottombar' in template_source
    assert 'tag-filter-mobile-category-manager' in template_source


def test_tag_filter_template_mobile_panels_bind_to_mode_specific_state_contract():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert "x-show=\"$store.global.deviceType === 'mobile' && mobileActiveTab === 'filter'\"" in template_source
    assert "x-show=\"$store.global.deviceType === 'mobile' && mobileActiveTab === 'delete'\"" in template_source
    assert "x-show=\"$store.global.deviceType === 'mobile' && mobileActiveTab === 'category'\"" in template_source
    assert "x-show=\"$store.global.deviceType === 'mobile' && showCategoryManager && mobileActiveTab === 'category'\"" in template_source


def test_tag_filter_template_gates_legacy_control_surface_to_non_mobile_only():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert "x-show=\"$store.global.deviceType !== 'mobile'\"" in template_source
    assert "x-show=\"$store.global.deviceType !== 'mobile' && isSortMode\"" in template_source
    assert "x-show=\"$store.global.deviceType !== 'mobile' && customOrderEnabled && !isSortMode\"" in template_source
    assert "x-show=\"$store.global.deviceType !== 'mobile' && !isSortMode\"" in template_source
    assert "x-show=\"$store.global.deviceType !== 'mobile' && showCategoryMode && !isSortMode\"" in template_source
    assert "x-show=\"$store.global.deviceType !== 'mobile' && showCategoryManager && !isSortMode\"" in template_source
    assert 'class="tag-cloud-container custom-scrollbar"' in template_source


def test_tag_filter_js_sync_mobile_tab_state_resets_mode_specific_mobile_state():
    source = read_project_file('static/js/components/tagFilterModal.js')
    section = source.split('syncMobileTabState(tab) {', 1)[1].split('init() {', 1)[0]

    assert "['filter', 'sort', 'delete', 'category'].includes(tab)" in section
    assert "if (previousTab === 'delete' && tab !== 'delete')" in section
    assert 'this.selectedTagsForDeletion = [];' in section
    assert "if (previousTab === 'category' && tab !== 'category')" in section
    assert 'this.selectedCategoryTags = [];' in section
    assert "this.categoryDraftName = '';" in section
    assert "this.categoryDraftColor = '#64748b';" in section
    assert 'this.categoryDraftOpacity = 16;' in section
    assert 'this.showCategoryManager = false;' in section


def test_tag_filter_js_sync_mobile_tab_state_clears_search_on_sort_entry_and_preserves_sort_guard():
    source = read_project_file('static/js/components/tagFilterModal.js')
    section = source.split('syncMobileTabState(tab) {', 1)[1].split('init() {', 1)[0]

    assert "if (tab === 'sort')" in section
    assert "this.tagSearchQuery = '';" in section
    assert 'this.cancelSortMode()' in section
    assert 'if (this.isSortMode && this.isSortDirty)' in source
    assert '当前排序尚未保存，关闭后将丢失改动。确定关闭吗？' in source
    assert '当前排序尚未保存，确定放弃改动吗？' in source


def test_tag_filter_js_modal_close_resets_mobile_and_mode_specific_state_contract():
    source = read_project_file('static/js/components/tagFilterModal.js')
    request_close_section = source.split('requestCloseModal() {', 1)[1].split('toggleFilterTag(tag, event = null) {', 1)[0]

    assert 'resetModalStateAfterClose()' in source
    assert 'this.resetModalStateAfterClose();' in request_close_section


def test_tag_filter_js_close_reset_helper_covers_task2_contract():
    source = read_project_file('static/js/components/tagFilterModal.js')
    reset_section = source.split('resetModalStateAfterClose() {', 1)[1].split('requestCloseModal() {', 1)[0]

    assert 'this.selectedTagsForDeletion = [];' in reset_section
    assert 'this.selectedCategoryTags = [];' in reset_section
    assert "this.categoryDraftName = '';" in reset_section
    assert "this.categoryDraftColor = '#64748b';" in reset_section
    assert 'this.categoryDraftOpacity = 16;' in reset_section
    assert 'this.showCategoryManager = false;' in reset_section
    assert "this.mobileActiveTab = 'filter';" in reset_section


def test_tag_filter_template_keeps_desktop_drag_sort_and_adds_mobile_reorder_rows():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert 'tag-filter-mobile-sort-row' in template_source
    assert '@click="moveSortTagUp(tag)"' in template_source
    assert '@click="moveSortTagDown(tag)"' in template_source
    assert 'draggable="true"' in template_source
    assert '@dragstart="onSortDragStart($event, tag)"' in template_source


def test_tag_filter_template_mobile_sort_controls_live_under_mobile_sort_panel_contract():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert "x-show=\"$store.global.deviceType === 'mobile' && mobileActiveTab === 'sort'\"" in template_source
    assert 'class="tag-filter-mobile-panel tag-filter-mobile-panel--sort"' in template_source
    assert '上移' in template_source
    assert '下移' in template_source


def test_tag_filter_template_mobile_sort_bottom_bar_exposes_save_action():
    template_source = read_project_file('templates/modals/tag_filter.html')
    mobile_shell_section = template_source.split('<div x-show="$store.global.deviceType === \'mobile\'" class="tag-filter-mobile-shell">', 1)[1].split('<div x-show="$store.global.deviceType !== \'mobile\'">', 1)[0]

    assert 'class="tag-filter-mobile-bottombar"' in mobile_shell_section
    assert '@click="saveSortMode()"' in mobile_shell_section
    assert "x-show=\"mobileActiveTab === 'sort' && isSortMode\"" in mobile_shell_section
    assert '保存排序' in mobile_shell_section


def test_tag_filter_template_gates_shared_drag_sort_branch_to_desktop_only():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert '<template x-if="$store.global.deviceType !== \'mobile\' && isSortMode">' in template_source
    shared_sort_section = template_source.split('<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-cloud-container custom-scrollbar">', 1)[1]
    assert '<template x-if="$store.global.deviceType !== \'mobile\' && isSortMode">' in shared_sort_section
    assert '<template x-if="isSortMode">' not in shared_sort_section
    assert 'draggable="true"' in template_source
    assert '@dragstart="onSortDragStart($event, tag)"' in template_source


def test_tag_filter_js_defines_shared_sort_reorder_helpers():
    source = read_project_file('static/js/components/tagFilterModal.js')

    assert 'moveSortTag(tag, delta) {' in source
    assert 'moveSortTagUp(tag) {' in source
    assert 'moveSortTagDown(tag) {' in source
    assert 'return this.moveSortTag(tag, -1);' in source
    assert 'return this.moveSortTag(tag, 1);' in source


def test_tag_filter_js_shared_sort_reorder_helper_has_guardrails():
    source = read_project_file('static/js/components/tagFilterModal.js')
    section = source.split('moveSortTag(tag, delta) {', 1)[1].split('onSortDragStart(event, tag) {', 1)[0]

    assert 'const tags = [...(this.sortWorkingTags || [])];' in section
    assert 'if (!this.isSortMode || !tag || !Number.isFinite(delta)) return false;' in section
    assert 'const currentIndex = tags.indexOf(tag);' in section
    assert 'const targetIndex = currentIndex + delta;' in section
    assert 'if (currentIndex === -1 || targetIndex < 0 || targetIndex >= tags.length) return false;' in section
    assert 'tags.splice(currentIndex, 1);' in section
    assert 'tags.splice(targetIndex, 0, tag);' in section
    assert 'this.sortWorkingTags = tags;' in section


def test_tag_filter_js_keeps_cancelable_sort_leave_paths_after_mobile_reorder_addition():
    source = read_project_file('static/js/components/tagFilterModal.js')

    assert 'if (previousTab === \'sort\' && tab !== \'sort\' && this.isSortMode)' in source
    assert 'this.cancelSortMode();' in source
    assert 'if (this.isSortMode) return false;' in source
    assert '当前排序尚未保存，关闭后将丢失改动。确定关闭吗？' in source
    assert '当前排序尚未保存，确定放弃改动吗？' in source


def test_tag_filter_mobile_css_fullscreen_shell_contract():
    source = read_project_file('static/css/modules/modal-tools.css')
    mobile_section = source.split('@media (max-width: 768px) {', 1)[1]

    assert '.tag-modal-container {' in mobile_section
    assert 'width: 100vw' in mobile_section
    assert 'height: 100vh' in mobile_section
    assert 'height: 100dvh' in mobile_section
    assert 'min-height: 100dvh' in mobile_section


def test_tag_filter_mobile_css_has_single_main_scroll_region_and_stable_rails():
    source = read_project_file('static/css/modules/modal-tools.css')
    mobile_section = source.split('@media (max-width: 768px) {', 1)[1]

    assert '.tag-filter-mobile-tabs {' in mobile_section
    assert '.tag-filter-mobile-main {' in mobile_section
    assert 'overflow-y: auto' in mobile_section
    assert 'overscroll-behavior: contain' in mobile_section
    assert '-webkit-overflow-scrolling: touch' in mobile_section
    assert '.tag-filter-mobile-topbar {' in mobile_section
    assert '.tag-filter-mobile-bottombar {' in mobile_section
    assert 'flex-shrink: 0' in mobile_section


def test_tag_filter_mobile_css_includes_touch_target_and_sort_row_hooks():
    source = read_project_file('static/css/modules/modal-tools.css')
    mobile_section = source.split('@media (max-width: 768px) {', 1)[1]

    assert '.tag-filter-mobile-tabs button {' in mobile_section
    assert 'min-height: 44px' in mobile_section
    assert '.tag-filter-mobile-utility {' in mobile_section
    assert '.tag-filter-mobile-sort-row {' in mobile_section
    assert 'padding-bottom: calc(env(safe-area-inset-bottom, 0px) + ' in mobile_section


def test_tag_filter_template_mobile_shell_exposes_stable_layout_hooks():
    template_source = read_project_file('templates/modals/tag_filter.html')
    mobile_shell_section = template_source.split('<div x-show="$store.global.deviceType === \'mobile\'" class="tag-filter-mobile-shell">', 1)[1].split('<div x-show="$store.global.deviceType !== \'mobile\'">', 1)[0]

    assert 'class="tag-filter-mobile-utility"' in mobile_shell_section
    assert 'class="tag-filter-mobile-main custom-scrollbar"' in mobile_shell_section
    assert 'class="tag-filter-mobile-bottombar"' in mobile_shell_section
    assert 'class="tag-filter-mobile-sort-row"' in mobile_shell_section


def test_tag_filter_template_gates_legacy_shared_cloud_to_desktop_only_after_mobile_shell_split():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert '<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-cloud-container custom-scrollbar">' in template_source
    assert '<div class="tag-cloud-container custom-scrollbar">' not in template_source


def test_tag_filter_mobile_css_applies_touch_targets_to_utility_controls():
    source = read_project_file('static/css/modules/modal-tools.css')
    mobile_section = source.split('@media (max-width: 768px) {', 1)[1]

    assert '.tag-filter-mobile-utility .tag-category-filter-pill,' in mobile_section
    assert '.tag-filter-mobile-utility .tag-category-quick-btn,' in mobile_section
    assert 'min-height: 44px' in mobile_section


def test_tag_filter_template_mobile_category_panel_restores_save_and_existing_category_controls():
    template_source = read_project_file('templates/modals/tag_filter.html')
    mobile_shell_section = template_source.split('<div x-show="$store.global.deviceType === \'mobile\'" class="tag-filter-mobile-shell">', 1)[1].split('<div x-show="$store.global.deviceType !== \'mobile\'">', 1)[0]

    assert "x-show=\"$store.global.deviceType === 'mobile' && mobileActiveTab === 'category'\"" in mobile_shell_section
    assert '@click="saveCategoryBatch()"' in mobile_shell_section
    assert ':disabled="!canSaveCategoryBatch"' in mobile_shell_section
    assert 'class="tag-category-quick-list"' in mobile_shell_section
    assert "x-for=\"name in availableCategoryNames\"" in mobile_shell_section
    assert '@click="setCategoryDraft(name)"' in mobile_shell_section


def test_tag_filter_template_mobile_category_panel_restores_manager_entry_and_surface():
    template_source = read_project_file('templates/modals/tag_filter.html')
    mobile_shell_section = template_source.split('<div x-show="$store.global.deviceType === \'mobile\'" class="tag-filter-mobile-shell">', 1)[1].split('<div x-show="$store.global.deviceType !== \'mobile\'">', 1)[0]

    assert '@click="toggleCategoryManager()"' in mobile_shell_section
    assert "x-text=\"showCategoryManager ? '收起分类管理' : '分类管理'\"" in mobile_shell_section
    assert 'class="tag-filter-mobile-category-manager"' in mobile_shell_section
    assert "x-show=\"$store.global.deviceType === 'mobile' && showCategoryManager && mobileActiveTab === 'category'\"" in mobile_shell_section
    assert 'class="tag-category-manager-list custom-scrollbar"' in mobile_shell_section


def test_tag_filter_template_desktop_workbench_shell_contract():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert 'class="tag-filter-desktop-shell"' in template_source
    assert 'class="tag-filter-desktop-toolbar"' in template_source
    assert 'class="tag-filter-desktop-workbench"' in template_source
    assert 'class="tag-filter-desktop-sidebar"' in template_source
    assert 'class="tag-filter-desktop-main"' in template_source
    assert '<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-filter-desktop-shell">' in template_source


def test_tag_filter_template_desktop_workbench_sections_keep_transition_modes_reachable():
    template_source = read_project_file('templates/modals/tag_filter.html')
    desktop_shell_section = template_source.split('<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-filter-desktop-shell">', 1)[1].split('</div>\n        <div x-show="$store.global.deviceType !== \'mobile\'" class="tag-cloud-container custom-scrollbar">', 1)[0]

    assert 'class="tag-filter-desktop-sidebar"' in desktop_shell_section
    assert 'class="tag-filter-desktop-main"' in desktop_shell_section
    assert '@click="toggleSortMode()"' in desktop_shell_section
    assert '@click="toggleDeleteMode()"' in desktop_shell_section
    assert '@click="toggleCategoryMode()"' in desktop_shell_section
    assert 'x-show="$store.global.deviceType !== \'mobile\' && showCategoryMode && !isSortMode"' in desktop_shell_section
    assert 'x-show="$store.global.deviceType !== \'mobile\' && showCategoryManager && !isSortMode"' in desktop_shell_section


def test_tag_filter_template_desktop_workbench_exposes_governance_and_remember_view_controls_contract():
    template_source = read_project_file('templates/modals/tag_filter.html')
    desktop_shell_section = template_source.split('<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-filter-desktop-shell">', 1)[1].split('</div>\n        <div x-show="$store.global.deviceType !== \'mobile\'" class="tag-cloud-container custom-scrollbar">', 1)[0]

    assert 'x-model="rememberLastTagView"' in desktop_shell_section
    assert 'x-model="lockTagLibrary"' in desktop_shell_section
    assert 'x-model="tagBlacklistInput"' in desktop_shell_section
    assert '@change="saveDesktopWorkbenchPrefs()"' in desktop_shell_section
    assert '@change="saveTagManagementPrefsState()"' in desktop_shell_section
    assert '@blur="saveTagManagementPrefsState()"' in desktop_shell_section


def test_tag_filter_template_category_sort_selector_persists_last_category_choice_contract():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert '<select x-model="selectedCategorySortName" @change="saveDesktopWorkbenchPrefs()" class="form-input"' in template_source


def test_tag_filter_desktop_workbench_shell_css_contract():
    source = read_project_file('static/css/modules/modal-tools.css')

    assert '.tag-filter-desktop-shell {' in source
    assert '.tag-filter-desktop-toolbar {' in source
    assert '.tag-filter-desktop-workbench {' in source
    assert '.tag-filter-desktop-sidebar {' in source
    assert '.tag-filter-desktop-main {' in source


def test_tag_filter_desktop_workbench_sections_css_sizes_sidebar_and_main():
    source = read_project_file('static/css/modules/modal-tools.css')
    desktop_shell_section = source.split('.tag-filter-desktop-shell {', 1)[1].split('@media (max-width: 768px) {', 1)[0]

    assert 'display: flex' in desktop_shell_section
    assert 'flex-direction: column' in desktop_shell_section
    assert 'min-height: 0' in desktop_shell_section
    assert 'grid-template-columns:' in desktop_shell_section
    assert 'minmax(16rem, 20rem)' in desktop_shell_section
    assert 'minmax(0, 1fr)' in desktop_shell_section
    assert 'overflow-y: auto' in desktop_shell_section


def test_tag_filter_desktop_workbench_shell_css_widens_modal_container():
    source = read_project_file('static/css/modules/modal-tools.css')
    modal_container_section = source.split('.tag-modal-container {', 1)[1].split('.tag-cloud-container {', 1)[0]

    assert 'width: min(1120px, 94vw);' in modal_container_section
    assert 'max-width: 94vw;' in modal_container_section


def test_tag_filter_template_desktop_workbench_shell_uses_x_if_branch_isolation():
    template_source = read_project_file('templates/modals/tag_filter.html')

    assert '<template x-if="$store.global.deviceType === \'mobile\'">' in template_source
    assert '<template x-if="$store.global.deviceType !== \'mobile\'">' in template_source
    assert '<div x-show="$store.global.deviceType === \'mobile\'" class="tag-filter-mobile-shell">' in template_source
    assert '<div x-show="$store.global.deviceType !== \'mobile\'" class="tag-filter-desktop-shell">' in template_source
    assert 'class="tag-filter-mobile-shell"' in template_source
    assert 'class="tag-filter-desktop-shell"' in template_source
