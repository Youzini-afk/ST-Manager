/**
 * static/js/components/presetDetailReader.js
 * 预设详情阅读器组件
 */

import {
  getPresetDetail,
  savePresetExtensions as apiSavePresetExtensions,
} from "../api/presets.js";
import {
  clearActiveRuntimeContext,
  setActiveRuntimeContext,
} from "../runtime/runtimeContext.js";
import { downloadFileFromApi } from "../utils/download.js";
import { formatDate } from "../utils/format.js";

const UI_FILTERS = [
  { id: "all", label: "全部" },
  { id: "structured", label: "结构化" },
  { id: "extension", label: "扩展" },
];

const PROMPT_UI_FILTERS = [
  { id: "all", label: "全部" },
  { id: "enabled", label: "启用" },
  { id: "disabled", label: "禁用" },
  { id: "marker", label: "预留字段" },
];

const TYPE_LABELS = {
  extension: "扩展",
  field: "字段",
  structured: "结构化",
};

const GROUP_FALLBACK_LABELS = {
  extensions: "扩展",
  scalar_fields: "基础字段",
  structured_objects: "结构化对象",
};

const PROMPT_POSITION_LABELS = {
  0: "相对位置",
  1: "In-Chat 注入",
};

function normalizeText(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

export default function presetDetailReader() {
  return {
    showModal: false,
    isLoading: false,
    activePresetDetail: null,
    activeWorkspace: "all",
    activeGroup: "all",
    activePromptId: "",
    activeItemId: "",
    searchTerm: "",
    uiFilter: "all",
    showRightPanel: true,
    showMobileSidebar: false,

    init() {
      this.showRightPanel = this.$store?.global?.deviceType !== "mobile";
      window.addEventListener("open-preset-reader", (e) => {
        this.openPreset(e.detail || {});
      });
    },

    get readerView() {
      const view = this.activePresetDetail?.reader_view;
      if (view && Array.isArray(view.items)) {
        return {
          family: view.family || "generic",
          family_label: view.family_label || "通用预设",
          groups: Array.isArray(view.groups) ? view.groups : [],
          items: view.items,
          stats: view.stats && typeof view.stats === "object" ? view.stats : {},
        };
      }
      return {
        family: "generic",
        family_label: "通用预设",
        groups: [],
        items: [],
        stats: {
          total_count: 0,
        },
      };
    },

    get readerGroups() {
      const groups = Array.isArray(this.readerView.groups)
        ? this.readerView.groups
        : [];
      return groups.map((group) => ({
        ...group,
        label: group.label || GROUP_FALLBACK_LABELS[group.id] || group.id,
      }));
    },

    get readerItems() {
      return Array.isArray(this.readerView.items) ? this.readerView.items : [];
    },

    get isPromptWorkspaceReader() {
      return this.readerView.family === "prompt_manager";
    },

    get promptItems() {
      return this.readerItems.filter((item) => item.type === "prompt");
    },

    get orderedPromptItems() {
      return [...this.promptItems].sort((left, right) => {
        const leftIndex = Number(
          left.prompt_meta?.order_index ?? Number.MAX_SAFE_INTEGER,
        );
        const rightIndex = Number(
          right.prompt_meta?.order_index ?? Number.MAX_SAFE_INTEGER,
        );
        if (leftIndex !== rightIndex) {
          return leftIndex - rightIndex;
        }
        return String(left.title || "").localeCompare(
          String(right.title || ""),
        );
      });
    },

    get promptFilteredItems() {
      const query = normalizeText(this.searchTerm);
      return this.orderedPromptItems.filter((item) => {
        if (
          this.uiFilter === "enabled" &&
          item.prompt_meta?.is_enabled === false
        ) {
          return false;
        }
        if (
          this.uiFilter === "disabled" &&
          item.prompt_meta?.is_enabled !== false
        ) {
          return false;
        }
        if (this.uiFilter === "marker" && !item.prompt_meta?.is_marker) {
          return false;
        }

        if (!query) {
          return true;
        }

        const haystack = [
          item.title,
          item.summary,
          item.payload?.identifier,
          this.getPromptPreview(item),
          this.getPromptPositionLabel(item),
        ]
          .map(normalizeText)
          .filter(Boolean)
          .join(" ");
        return haystack.includes(query);
      });
    },

    get filteredItems() {
      const query = normalizeText(this.searchTerm);
      return this.readerItems.filter((item) => {
        if (this.activeGroup !== "all" && item.group !== this.activeGroup) {
          return false;
        }

        if (this.uiFilter === "structured" && item.type !== "structured") {
          return false;
        }
        if (this.uiFilter === "extension" && item.type !== "extension") {
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
          this.getItemValuePreview(item),
        ]
          .map(normalizeText)
          .filter(Boolean)
          .join(" ");
        return haystack.includes(query);
      });
    },

    get activeItem() {
      const items = this.filteredItems;
      const current = items.find((item) => item.id === this.activeItemId);
      if (current) {
        return current;
      }

      if (this.activeGroup !== "all" && !items.length && !this.activeItemId) {
        return null;
      }

      const anyCurrent = this.readerItems.find(
        (item) => item.id === this.activeItemId,
      );
      if (anyCurrent && !items.length) {
        return anyCurrent;
      }

      return items[0] || this.readerItems[0] || null;
    },

    get activePromptItem() {
      return (
        this.promptFilteredItems.find(
          (item) => item.id === this.activePromptId,
        ) ||
        this.promptFilteredItems[0] ||
        null
      );
    },

    get activeContextItem() {
      if (this.isPromptWorkspaceReader && this.activeWorkspace === "prompts") {
        return this.activePromptItem;
      }
      return this.activeItem;
    },

    get readerStats() {
      const stats = this.readerView.stats || {};
      return {
        total_count: Number(stats.total_count) || this.readerItems.length,
        visible_count:
          this.isPromptWorkspaceReader && this.activeWorkspace === "prompts"
            ? this.promptFilteredItems.length
            : this.filteredItems.length,
      };
    },

    get uiFilters() {
      if (this.isPromptWorkspaceReader && this.activeWorkspace === "prompts") {
        return PROMPT_UI_FILTERS;
      }
      return UI_FILTERS;
    },

    async openPreset(item) {
      if (!item?.id) return;
      this.isLoading = true;
      this.showModal = true;
      this.showMobileSidebar = false;
      this.showRightPanel = this.$store?.global?.deviceType !== "mobile";
      this.searchTerm = "";
      this.uiFilter = "all";
      this.activeWorkspace = "all";
      this.activeGroup = "all";
      this.activePromptId = "";
      this.activeItemId = "";

      try {
        const res = await getPresetDetail(item.id);
        if (!res.success) {
          this.$store.global.showToast(res.msg || "获取详情失败", "error");
          this.closeModal();
          return;
        }

        this.activePresetDetail = res.preset;
        setActiveRuntimeContext({
          preset: {
            id: res.preset?.id || item.id || "",
            name: res.preset?.name || "",
            type: res.preset?.type || "",
            path: res.preset?.path || "",
          },
        });
        this.initializeReaderState();
      } catch (error) {
        console.error("Failed to load preset detail:", error);
        this.$store.global.showToast("获取详情失败", "error");
        this.closeModal();
      } finally {
        this.isLoading = false;
      }
    },

    initializeReaderState() {
      if (this.isPromptWorkspaceReader) {
        this.activeWorkspace =
          this.readerGroups.find((group) => group.id === "prompts")?.id ||
          this.readerGroups[0]?.id ||
          "prompts";
        this.activePromptId = this.promptFilteredItems[0]?.id || "";
        this.activeGroup = "all";
        this.activeItemId = "";
        if (this.$store?.global?.deviceType !== "mobile") {
          this.showRightPanel = true;
        }
        return;
      }

      const firstGroup = this.readerGroups[0]?.id || "all";
      this.activeGroup = firstGroup;
      const firstItem = this.filteredItems[0] || this.readerItems[0] || null;
      this.activeItemId = firstItem?.id || "";
      if (this.$store?.global?.deviceType !== "mobile") {
        this.showRightPanel = true;
      }
    },

    closeModal() {
      this.showModal = false;
      this.activePresetDetail = null;
      this.activeWorkspace = "all";
      this.activeGroup = "all";
      this.activePromptId = "";
      this.activeItemId = "";
      this.searchTerm = "";
      this.uiFilter = "all";
      this.showRightPanel = this.$store?.global?.deviceType !== "mobile";
      this.showMobileSidebar = false;
      clearActiveRuntimeContext("preset");
    },

    selectGroup(groupId) {
      this.activeGroup = groupId || "all";
      const nextItem = this.filteredItems[0] || this.readerItems[0] || null;
      this.activeItemId = nextItem?.id || "";
      if (this.$store?.global?.deviceType === "mobile") {
        this.showMobileSidebar = false;
      }
    },

    selectWorkspace(workspaceId) {
      this.activeWorkspace = workspaceId || "prompts";
      if (this.activeWorkspace === "prompts") {
        this.activePromptId = this.promptFilteredItems[0]?.id || "";
      } else {
        this.activeGroup = this.activeWorkspace;
        this.activeItemId = this.filteredItems[0]?.id || "";
      }
      this.showRightPanel = true;
      if (this.$store?.global?.deviceType === "mobile") {
        this.showMobileSidebar = false;
      }
    },

    selectItem(itemId) {
      this.activeItemId = itemId || "";
      this.showRightPanel = true;
      if (this.$store?.global?.deviceType === "mobile") {
        this.showMobileSidebar = false;
      }
    },

    selectPrompt(itemId) {
      this.activeWorkspace = "prompts";
      this.activePromptId = itemId || "";
      this.showRightPanel = true;
      if (this.$store?.global?.deviceType === "mobile") {
        this.showMobileSidebar = false;
      }
    },

    getSourceLabel() {
      return this.activePresetDetail?.type === "global"
        ? "全局预设"
        : "资源预设";
    },

    getItemGroupLabel(item) {
      return (
        this.readerGroups.find((group) => group.id === item?.group)?.label ||
        GROUP_FALLBACK_LABELS[item?.group] ||
        item?.group ||
        "未分组"
      );
    },

    getItemValuePreview(item) {
      if (!item) return "-";

      const payload = item.payload || {};
      if (item.type === "extension") {
        return this.formatValue(payload.value);
      }
      if (item.type === "field") {
        return this.formatValue(payload.value);
      }
      if (item.type === "structured") {
        const value = payload.value;
        if (Array.isArray(value)) {
          return `${value.length} 项`;
        }
        if (value && typeof value === "object") {
          return `${Object.keys(value).length} 个键`;
        }
      }

      return item.summary || this.formatValue(payload.value ?? payload);
    },

    getItemFullDetail(item) {
      if (!item) return "-";

      const payload = item.payload || {};
      if (
        item.type === "extension" ||
        item.type === "field" ||
        item.type === "structured"
      ) {
        return this.formatFullValue(payload.value);
      }

      return this.formatFullValue(payload.value ?? payload);
    },

    getItemBadge(item) {
      if (!item) return TYPE_LABELS.field;
      return TYPE_LABELS[item.type] || "条目";
    },

    getPromptPreview(item) {
      if (!item) return "-";
      if (item.prompt_meta?.is_marker) {
        return "占位用预留字段，不承载提示词内容";
      }
      const content = String(item.payload?.content || "").trim();
      return content ? this.formatValue(content) : "暂无提示词内容";
    },

    getPromptPositionLabel(item) {
      const position = Number(item?.payload?.injection_position ?? 0);
      if (position === 1) {
        const rawDepth = Number(item?.payload?.injection_depth ?? 4);
        const depth = Number.isFinite(rawDepth) ? rawDepth : 4;
        return `In-Chat @ ${depth}`;
      }
      return PROMPT_POSITION_LABELS[position] || "相对位置";
    },

    openFullscreenEditor(options = {}) {
      if (!this.activePresetDetail) return;
      window.dispatchEvent(
        new CustomEvent("open-preset-editor", {
          detail: {
            presetId: this.activePresetDetail.id,
            activeNav: options.activeNav || "basic",
          },
        }),
      );
      this.closeModal();
    },

    async exportActivePreset() {
      const detail = this.activePresetDetail;
      if (!detail) return;

      try {
        await downloadFileFromApi({
          url: "/api/presets/export",
          body: { id: detail.id },
          defaultFilename: detail.filename || `${detail.name || "preset"}.json`,
          showToast: this.$store?.global?.showToast,
        });
      } catch (error) {
        this.$store.global.showToast(error.message || "导出失败", "error");
      }
    },

    openAdvancedExtensions() {
      if (!this.activePresetDetail) return;

      const extensions = this.activePresetDetail.extensions || {};
      const editingData = {
        extensions: {
          regex_scripts: Array.isArray(extensions.regex_scripts)
            ? extensions.regex_scripts
            : [],
          tavern_helper: extensions.tavern_helper || { scripts: [] },
        },
      };

      window.dispatchEvent(
        new CustomEvent("open-advanced-editor", {
          detail: editingData,
        }),
      );

      const saveHandler = async (e) => {
        window.removeEventListener("advanced-editor-save", saveHandler);
        const nextExtensions = e?.detail?.extensions || editingData.extensions;
        await this.savePresetExtensions(nextExtensions);
      };
      window.addEventListener("advanced-editor-save", saveHandler);
    },

    async savePresetExtensions(extensions) {
      if (!this.activePresetDetail) return;
      try {
        const res = await apiSavePresetExtensions({
          id: this.activePresetDetail.id,
          extensions,
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "保存失败", "error");
          return;
        }
        this.$store.global.showToast("扩展已保存");
        await this.openPreset({ id: this.activePresetDetail.id });
      } catch (error) {
        console.error("Failed to save preset extensions:", error);
        this.$store.global.showToast("保存失败", "error");
      }
    },

    formatValue(value) {
      if (value === null || value === undefined || value === "") return "-";
      if (typeof value === "boolean") return value ? "是" : "否";
      if (typeof value === "number") {
        return Number.isInteger(value)
          ? String(value)
          : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
      }
      if (typeof value === "object") {
        try {
          const serialized = JSON.stringify(value, null, 2);
          return serialized.length > 240
            ? `${serialized.slice(0, 240)}...`
            : serialized;
        } catch (error) {
          return String(value);
        }
      }
      const text = String(value);
      return text.length > 240 ? `${text.slice(0, 240)}...` : text;
    },

    formatFullValue(value) {
      if (value === null || value === undefined || value === "") return "-";
      if (typeof value === "boolean") return value ? "是" : "否";
      if (typeof value === "number") {
        return Number.isInteger(value)
          ? String(value)
          : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
      }
      if (typeof value === "object") {
        try {
          return JSON.stringify(value, null, 2);
        } catch (error) {
          return String(value);
        }
      }
      return String(value);
    },

    formatDate(ts) {
      return formatDate(ts, { includeYear: true });
    },

    formatSize(bytes) {
      const size = Number(bytes) || 0;
      if (!size) return "0 B";
      if (size < 1024) return `${size} B`;
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
      return `${(size / 1024 / 1024).toFixed(1)} MB`;
    },

    async copyText(value, label = "内容") {
      try {
        await navigator.clipboard.writeText(String(value ?? ""));
        this.$store.global.showToast(`${label}已复制`);
      } catch (error) {
        console.error(error);
        this.$store.global.showToast(`复制${label}失败`, "error");
      }
    },
  };
}
