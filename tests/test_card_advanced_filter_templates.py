from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def compact_whitespace(value):
    return ' '.join(value.split())


def test_header_template_replaces_card_inline_filters_with_advanced_filter_button():
    header_template = read_project_file('templates/components/header.html')

    assert 'class="header-advanced-filter-btn"' in header_template
    assert '@click="openCardAdvancedFilter()"' in header_template
    assert 'x-text="cardAdvancedFilterCount"' in header_template
    assert 'class="search-scope-inline"' not in header_template
    assert 'class="search-sort-group"' not in header_template


def test_header_js_exposes_drawer_opener_and_limits_favorite_button_to_chats():
    header_source = read_project_file('static/js/components/header.js')

    assert 'get cardAdvancedFilterCount() {' in header_source
    assert 'openCardAdvancedFilter() {' in header_source
    assert "return this.currentMode === 'chats';" in header_source


def test_index_template_includes_card_advanced_filter_drawer_and_app_registers_component():
    index_template = read_project_file('templates/index.html')
    app_source = read_project_file('static/js/app.js')

    assert '{% include "modals/card_advanced_filter.html" %}' in index_template
    assert "import cardAdvancedFilter from './components/cardAdvancedFilter.js';" in app_source
    assert "Alpine.data('cardAdvancedFilter', cardAdvancedFilter);" in app_source


def test_state_js_defines_advanced_filter_applied_state_draft_and_summary_helpers():
    state_source = read_project_file('static/js/state.js')

    assert "importDateFrom: ''" in state_source
    assert "importDateTo: ''" in state_source
    assert "modifiedDateFrom: ''" in state_source
    assert "modifiedDateTo: ''" in state_source
    assert "tokenMin: ''" in state_source
    assert "tokenMax: ''" in state_source
    assert 'showCardAdvancedFilterDrawer: false,' in state_source
    assert 'cardAdvancedFilterDraft: null,' in state_source
    assert 'openCardAdvancedFilterDrawer() {' in state_source
    assert 'applyCardAdvancedFilterDraft() {' in state_source
    assert 'getCardAdvancedFilterSummaryItems() {' in state_source
    assert 'clearAllCardAdvancedFilters() {' in state_source


def test_card_grid_source_sends_advanced_filter_params_and_debounces_filter_watches():
    card_grid_source = read_project_file('static/js/components/cardGrid.js')

    assert "'$store.global.viewState.importDateFrom'" in card_grid_source
    assert "'$store.global.viewState.modifiedDateTo'" in card_grid_source
    assert "'$store.global.viewState.tokenMax'" in card_grid_source
    assert "import_date_from: vs.importDateFrom || ''" in card_grid_source
    assert "modified_date_to: vs.modifiedDateTo || ''" in card_grid_source
    assert "token_min: vs.tokenMin === '' ? '' : String(vs.tokenMin)" in card_grid_source
    assert "token_max: vs.tokenMax === '' ? '' : String(vs.tokenMax)" in card_grid_source
    assert "this.scheduleFetchCards('filters');" in card_grid_source


def test_grid_cards_template_renders_filter_summary_bar():
    grid_template = read_project_file('templates/components/grid_cards.html')

    assert 'class="card-filter-summary-bar"' in grid_template
    assert 'x-for="item in $store.global.getCardAdvancedFilterSummaryItems()"' in grid_template
    assert '@click="$store.global.clearAllCardAdvancedFilters()"' in grid_template
    assert '@click.stop="$store.global.clearCardAdvancedFilterItem(item.key)"' in grid_template


def test_card_advanced_filter_template_exposes_sections_and_footer_actions():
    drawer_template = read_project_file('templates/modals/card_advanced_filter.html')
    drawer_component = read_project_file('static/js/components/cardAdvancedFilter.js')
    compact = compact_whitespace(drawer_template)

    assert 'x-data="cardAdvancedFilter"' in drawer_template
    assert 'class="card-advanced-filter-drawer"' in drawer_template
    assert '>基础筛选<' in compact
    assert '>时间筛选<' in compact
    assert '>数值筛选<' in compact
    assert '>标签条件<' in compact
    assert '@click="clearDraft()"' in drawer_template
    assert '@click="applyFilters()"' in drawer_template
    assert '@click="openTagFilterEditor()"' in drawer_template
    assert 'x-text="tagSummary"' in drawer_template
    assert 'get tagSummary() {' in drawer_component


def test_mobile_menu_replaces_card_specific_filter_controls_with_advanced_filter_entry():
    header_template = read_project_file('templates/components/header.html')
    mobile_menu = header_template.split('<!-- 移动端：展开菜单 -->', 1)[1]

    assert '高级筛选' in mobile_menu
    assert '@click="openCardAdvancedFilter(); closeMobileMenu()"' in mobile_menu
    assert '搜索范围' not in mobile_menu
    assert '当前列表排序' not in mobile_menu
    assert '包含子目录' not in mobile_menu


def test_layout_css_styles_filter_button_summary_bar_and_drawer_shell():
    css_source = read_project_file('static/css/modules/layout.css')

    assert '.header-advanced-filter-btn {' in css_source
    assert '.card-filter-summary-bar {' in css_source
    assert '.card-filter-summary-chip {' in css_source
    assert '.card-advanced-filter-overlay {' in css_source
    assert '.card-advanced-filter-drawer {' in css_source
    assert '.mobile-advanced-filter-entry {' in css_source
