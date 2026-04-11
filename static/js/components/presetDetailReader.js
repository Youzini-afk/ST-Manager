/**
 * static/js/components/presetDetailReader.js
 * 预设详情阅读器组件
 */

import {
  getPresetDefaultPreview,
  getPresetDetail,
  savePresetExtensions as apiSavePresetExtensions,
} from '../api/presets.js';
import {
  clearActiveRuntimeContext,
  setActiveRuntimeContext,
} from '../runtime/runtimeContext.js';
import { downloadFileFromApi } from '../utils/download.js';
import { formatDate } from '../utils/format.js';

const UI_FILTERS = [
  { id: 'all', label: '全部' },
  { id: 'prompt', label: 'Prompt' },
  { id: 'structured', label: '结构化' },
  { id: 'extension', label: '扩展' },
  { id: 'unknown', label: '未知' },
];

const TYPE_LABELS = {
  prompt: 'Prompt',
  prompt_order: '顺序',
  extension: '扩展',
  field: '字段',
  structured: '结构化',
};

const GROUP_FALLBACK_LABELS = {
  meta: '元信息',
  prompt_items: 'Prompts',
  prompt_order: 'Prompt 顺序',
  extensions: '扩展',
  scalar_fields: '基础字段',
  structured_objects: '结构化对象',
  unknown_fields: '未知字段',
};

function normalizeText(value) {
  return String(value ?? '').trim().toLowerCase();
}

function isUnknownItem(item) {
  return item?.group === 'unknown_fields' || item?.type === 'unknown_field';
}

const PROMPT_MARKER_KEYS = new Set([
  'worldInfoBefore',
  'worldInfoAfter',
  'charDescription',
  'charPersonality',
  'scenario',
  'chatHistory',
  'dialogueExamples',
  'personaDescription',
]);

const PROMPT_ICON_MAP = {
  worldInfoBefore: '🌍',
  worldInfoAfter: '🌍',
  charDescription: '👤',
  charPersonality: '🧠',
  personaDescription: '🎭',
  scenario: '🏰',
  chatHistory: '🕒',
  dialogueExamples: '💬',
  main: '📜',
  jailbreak: '🔓',
};

const PROMPT_ROLE_LABELS = {
  system: '系统提示词',
  user: '用户提示词',
  assistant: '助手提示词',
};

export default function presetDetailReader() {
  return {
    showModal: false,
    isLoading: false,
    activePresetDetail: null,
    defaultPreviewPath: '',
    defaultPreviewAvailable: false,
    activeGroup: 'all',
    activeItemId: '',
    searchTerm: '',
    uiFilter: 'all',
    showRightPanel: true,
    showMobileSidebar: false,

    init() {
      this.showRightPanel = this.$store?.global?.deviceType !== 'mobile';
      window.addEventListener('open-preset-reader', (e) => {
        this.openPreset(e.detail || {});
      });
    },

    get readerView() {
      const view = this.activePresetDetail?.reader_view;
      if (view && Array.isArray(view.items) && Array.isArray(view.groups)) {
        return view;
      }
      return {
        family: 'generic',
        family_label: '通用预设',
        groups: [],
        items: [],
        stats: {
          prompt_count: 0,
          unknown_count: Array.isArray(this.activePresetDetail?.unknown_fields)
            ? this.activePresetDetail.unknown_fields.length
            : 0,
        },
      };
    },

    get readerGroups() {
      const groups = Array.isArray(this.readerView.groups) ? this.readerView.groups : [];
      return groups.map((group) => ({
        ...group,
        label: group.label || GROUP_FALLBACK_LABELS[group.id] || group.id,
      }));
    },

    get readerItems() {
      return Array.isArray(this.readerView.items) ? this.readerView.items : [];
    },

    get filteredItems() {
      const query = normalizeText(this.searchTerm);
      return this.readerItems.filter((item) => {
        if (this.activeGroup !== 'all' && item.group !== this.activeGroup) {
          return false;
        }

        if (this.uiFilter === 'prompt' && item.type !== 'prompt' && item.type !== 'prompt_order') {
          return false;
        }
        if (this.uiFilter === 'structured' && item.type !== 'structured') {
          return false;
        }
        if (this.uiFilter === 'extension' && item.type !== 'extension') {
          return false;
        }
        if (this.uiFilter === 'unknown' && !isUnknownItem(item)) {
          return false;
        }

        if (!query) {
          return true;
        }

        const haystack = [
          item.title,
          item.summary,
          item.type,
          item.group,
          item.payload?.key,
          item.payload?.identifier,
          item.payload?.role,
          this.getItemValuePreview(item),
        ]
          .map(normalizeText)
          .filter(Boolean)
          .join(' ');
        return haystack.includes(query);
      });
    },

    get activeItem() {
      const items = this.filteredItems;
      const current = items.find((item) => item.id === this.activeItemId);
      if (current) {
        return current;
      }

      const anyCurrent = this.readerItems.find((item) => item.id === this.activeItemId);
      if (anyCurrent && !items.length) {
        return anyCurrent;
      }

      return items[0] || this.readerItems[0] || null;
    },

    get readerStats() {
      const stats = this.readerView.stats || {};
      return {
        prompt_count: Number(stats.prompt_count) || 0,
        unknown_count: Number(stats.unknown_count) || 0,
        total_count: this.readerItems.length,
        visible_count: this.filteredItems.length,
      };
    },

    get uiFilters() {
      return UI_FILTERS;
    },

    async openPreset(item) {
      if (!item?.id) return;
      this.isLoading = true;
      this.showModal = true;
      this.showMobileSidebar = false;
      this.showRightPanel = this.$store?.global?.deviceType !== 'mobile';
      this.searchTerm = '';
      this.uiFilter = 'all';
      this.activeGroup = 'all';
      this.activeItemId = '';

      try {
        const res = await getPresetDetail(item.id);
        if (!res.success) {
          this.$store.global.showToast(res.msg || '获取详情失败', 'error');
          this.closeModal();
          return;
        }

        this.activePresetDetail = res.preset;
        this.defaultPreviewPath = '';
        this.defaultPreviewAvailable = false;
        setActiveRuntimeContext({
          preset: {
            id: res.preset?.id || item.id || '',
            name: res.preset?.name || '',
            type: res.preset?.type || '',
            path: res.preset?.path || '',
          },
        });
        this.initializeReaderState();
        this.loadDefaultPreviewInfo();
      } catch (error) {
        console.error('Failed to load preset detail:', error);
        this.$store.global.showToast('获取详情失败', 'error');
        this.closeModal();
      } finally {
        this.isLoading = false;
      }
    },

    initializeReaderState() {
      const firstGroup = this.readerGroups[0]?.id || 'all';
      this.activeGroup = firstGroup;
      const firstItem = this.filteredItems[0] || this.readerItems[0] || null;
      this.activeItemId = firstItem?.id || '';
      if (this.$store?.global?.deviceType !== 'mobile') {
        this.showRightPanel = true;
      }
    },

    async loadDefaultPreviewInfo() {
      if (!this.activePresetDetail?.capabilities?.can_restore_default) return;
      try {
        const res = await getPresetDefaultPreview({
          preset_id: this.activePresetDetail.id,
          preset_kind: this.activePresetDetail.preset_kind,
        });
        if (res.success) {
          this.defaultPreviewPath = res.default_path || '';
          this.defaultPreviewAvailable = true;
        }
      } catch (error) {
        console.warn('Load preset default preview failed:', error);
      }
    },

    closeModal() {
      this.showModal = false;
      this.activePresetDetail = null;
      this.defaultPreviewPath = '';
      this.defaultPreviewAvailable = false;
      this.activeGroup = 'all';
      this.activeItemId = '';
      this.searchTerm = '';
      this.uiFilter = 'all';
      this.showRightPanel = this.$store?.global?.deviceType !== 'mobile';
      this.showMobileSidebar = false;
      clearActiveRuntimeContext('preset');
    },

    selectGroup(groupId) {
      this.activeGroup = groupId || 'all';
      const nextItem = this.filteredItems[0] || this.readerItems[0] || null;
      this.activeItemId = nextItem?.id || '';
      if (this.$store?.global?.deviceType === 'mobile') {
        this.showMobileSidebar = false;
      }
    },

    selectItem(itemId) {
      this.activeItemId = itemId || '';
      this.showRightPanel = true;
      if (this.$store?.global?.deviceType === 'mobile') {
        this.showMobileSidebar = false;
      }
    },

    getSourceLabel() {
      return this.activePresetDetail?.type === 'global' ? '全局预设' : '资源预设';
    },

    getItemGroupLabel(item) {
      return this.readerGroups.find((group) => group.id === item?.group)?.label || GROUP_FALLBACK_LABELS[item?.group] || item?.group || '未分组';
    },

    getItemValuePreview(item) {
      if (!item) return '-';

      const payload = item.payload || {};
      if (item.type === 'prompt') {
        return this.isPromptMarker(item)
          ? '系统自动注入的内容位置占位符'
          : String(payload.content || '').trim() || '(无内容)';
      }
      if (item.type === 'prompt_order') {
        return `第 ${(Number(payload.index) || 0) + 1} 位: ${payload.identifier || '-'}`;
      }
      if (item.type === 'extension') {
        return this.formatValue(payload.value);
      }
      if (item.type === 'field' || item.type === 'unknown_field') {
        return this.formatValue(payload.value);
      }
      if (item.type === 'structured') {
        const value = payload.value;
        if (Array.isArray(value)) {
          return `${value.length} 项`; 
        }
        if (value && typeof value === 'object') {
          return `${Object.keys(value).length} 个键`;
        }
      }

      return item.summary || this.formatValue(payload.value ?? payload);
    },

    getItemBadge(item) {
      if (!item) return TYPE_LABELS.field;
      if (isUnknownItem(item)) return '未知';
      return TYPE_LABELS[item.type] || '条目';
    },

    getPromptDisplayTitle(item) {
      if (!item || item.type !== 'prompt') return item?.title || '-';
      return item.payload?.name || item.title || item.payload?.identifier || '-';
    },

    isPromptEnabled(item) {
      if (!item || item.type !== 'prompt') return false;
      return item.payload?.enabled !== false;
    },

    isPromptMarker(item) {
      if (!item || item.type !== 'prompt') return false;
      const identifier = String(item.payload?.identifier || '').trim();
      return Boolean(item.payload?.marker) || PROMPT_MARKER_KEYS.has(identifier);
    },

    getPromptIcon(item) {
      const identifier = String(item?.payload?.identifier || '').trim();
      return PROMPT_ICON_MAP[identifier] || '📝';
    },

    getPromptRoleLabel(item) {
      const role = String(item?.payload?.role || '').trim().toLowerCase();
      return PROMPT_ROLE_LABELS[role] || role || '系统提示词';
    },

    formatItemPayload(item) {
      if (!item) return '-';
      const payload = item.payload || {};

      if (item.type === 'prompt') {
        return JSON.stringify(
          {
            identifier: payload.identifier || '',
            role: payload.role || '',
            content: payload.content || '',
          },
          null,
          2,
        );
      }

      if (item.type === 'prompt_order') {
        return JSON.stringify(
          {
            index: payload.index,
            identifier: payload.identifier,
          },
          null,
          2,
        );
      }

      if (item.type === 'field' || item.type === 'unknown_field' || item.type === 'extension' || item.type === 'structured') {
        return JSON.stringify(payload, null, 2);
      }

      return JSON.stringify(item, null, 2);
    },

    openFullscreenEditor(options = {}) {
      if (!this.activePresetDetail) return;
      window.dispatchEvent(
        new CustomEvent('open-preset-editor', {
          detail: {
            presetId: this.activePresetDetail.id,
            activeNav: options.activeNav || 'basic',
            restoreDefault: options.restoreDefault === true,
          },
        }),
      );
      this.closeModal();
    },

    openRawViewer() {
      this.openFullscreenEditor({ activeNav: 'raw' });
    },

    previewRestoreDefault() {
      this.openFullscreenEditor({ restoreDefault: true });
    },

    async exportActivePreset() {
      const detail = this.activePresetDetail;
      if (!detail) return;

      try {
        await downloadFileFromApi({
          url: '/api/presets/export',
          body: { id: detail.id },
          defaultFilename: detail.filename || `${detail.name || 'preset'}.json`,
          showToast: this.$store?.global?.showToast,
        });
      } catch (error) {
        this.$store.global.showToast(error.message || '导出失败', 'error');
      }
    },

    openAdvancedExtensions() {
      if (!this.activePresetDetail) return;

      const extensions = this.activePresetDetail.extensions || {};
      const editingData = {
        extensions: {
          regex_scripts: Array.isArray(extensions.regex_scripts) ? extensions.regex_scripts : [],
          tavern_helper: extensions.tavern_helper || { scripts: [] },
        },
      };

      window.dispatchEvent(
        new CustomEvent('open-advanced-editor', {
          detail: editingData,
        }),
      );

      const saveHandler = async (e) => {
        window.removeEventListener('advanced-editor-save', saveHandler);
        const nextExtensions = e?.detail?.extensions || editingData.extensions;
        await this.savePresetExtensions(nextExtensions);
      };
      window.addEventListener('advanced-editor-save', saveHandler);
    },

    async savePresetExtensions(extensions) {
      if (!this.activePresetDetail) return;
      try {
        const res = await apiSavePresetExtensions({
          id: this.activePresetDetail.id,
          extensions,
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || '保存失败', 'error');
          return;
        }
        this.$store.global.showToast('扩展已保存');
        await this.openPreset({ id: this.activePresetDetail.id });
      } catch (error) {
        console.error('Failed to save preset extensions:', error);
        this.$store.global.showToast('保存失败', 'error');
      }
    },

    formatValue(value) {
      if (value === null || value === undefined || value === '') return '-';
      if (typeof value === 'boolean') return value ? '是' : '否';
      if (typeof value === 'number') {
        return Number.isInteger(value)
          ? String(value)
          : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
      }
      if (typeof value === 'object') {
        try {
          const serialized = JSON.stringify(value, null, 2);
          return serialized.length > 240 ? `${serialized.slice(0, 240)}...` : serialized;
        } catch (error) {
          return String(value);
        }
      }
      const text = String(value);
      return text.length > 240 ? `${text.slice(0, 240)}...` : text;
    },

    formatDate(ts) {
      return formatDate(ts, { includeYear: true });
    },

    formatSize(bytes) {
      const size = Number(bytes) || 0;
      if (!size) return '0 B';
      if (size < 1024) return `${size} B`;
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
      return `${(size / 1024 / 1024).toFixed(1)} MB`;
    },

    async copyText(value, label = '内容') {
      try {
        await navigator.clipboard.writeText(String(value ?? ''));
        this.$store.global.showToast(`${label}已复制`);
      } catch (error) {
        console.error(error);
        this.$store.global.showToast(`复制${label}失败`, 'error');
      }
    },
  };
}
