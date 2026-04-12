/**
 * static/js/components/presetEditor.js
 * 预设全屏编辑器
 */

import { createAutoSaver } from "../utils/autoSave.js";
import { createSnapshot as apiCreateSnapshot } from "../api/system.js";
import {
  getPresetDetail,
  getPresetDefaultPreview,
  savePreset,
  savePresetExtensions as apiSavePresetExtensions,
} from "../api/presets.js";
import { estimateTokens, formatDate } from "../utils/format.js";
import {
  clearActiveRuntimeContext,
  setActiveRuntimeContext,
} from "../runtime/runtimeContext.js";

const PRESET_DRAFT_PREFIX = "st-manager:preset-draft:";

const SECTION_LABELS = {
  basic: "基础信息",
  sampling: "采样参数",
  penalties: "惩罚参数",
  length_and_output: "长度与终止",
  dynamic_temperature: "动态温度",
  mirostat: "Mirostat",
  guidance: "引导与负面提示",
  formatting: "格式与运行开关",
  schema_and_grammar: "Schema / Grammar",
  bans_and_bias: "禁词与 Bias",
  sampler_ordering: "采样顺序",
  sequences: "输入输出序列",
  wrapping_and_behavior: "包装与行为",
  activation: "激活规则",
  compatibility: "兼容字段",
  story: "故事模板",
  separator_and_chat: "分隔与聊天",
  insertion_behavior: "插入行为",
  formatting_behavior: "格式行为",
  prompt: "提示词内容",
  placement: "插入位置",
  template: "模板字段",
  runtime_notes: "运行说明",
  extensions: "扩展配置",
  raw: "原始 JSON",
  snapshots: "快照历史",
};

const LONG_TEXT_FIELDS = new Set([
  "content",
  "story_string",
  "example_separator",
  "chat_start",
  "prefix",
  "suffix",
  "separator",
  "negative_prompt",
  "json_schema",
  "grammar",
  "input_sequence",
  "output_sequence",
  "system_sequence",
  "first_output_sequence",
  "last_output_sequence",
  "stop_sequence",
  "activation_regex",
]);

function deepClone(value) {
  return JSON.parse(JSON.stringify(value ?? null));
}

export default function presetEditor() {
  const autoSaver = createAutoSaver();
  return {
    showPresetEditor: false,
    isLoading: false,
    isSaving: false,
    hasConflict: false,
    conflictRevision: "",
    activeNav: "basic",
    activeGroup: "all",
    activeItemId: "",
    searchTerm: "",
    uiFilter: "all",
    showMobileSidebar: false,
    showRightPanel: true,
    showRawEditor: false,
    removedUnknownFields: [],
    dirtyPaths: {},
    editingPresetFile: null,
    editingData: null,
    baseDataJson: "",
    draftState: { savedAt: "", restored: false },
    restorePreview: null,
    leftNavOpen: true,
    rightPanelOpen: true,
    sectionLabels: SECTION_LABELS,
    formatDate,
    estimateTokens,

    init() {
      window.addEventListener("open-preset-editor", (e) => {
        this.openPresetEditor(e.detail || {});
      });

      window.addEventListener("preset-restore-applied", (e) => {
        const detail = e.detail || {};
        if (!this.showPresetEditor || !this.editingPresetFile) return;
        if (detail.id && detail.id !== this.editingPresetFile.id) return;
        this.reloadFromDisk();
      });

      window.addEventListener("beforeunload", (event) => {
        if (!this.showPresetEditor || !this.isDirty) return;
        event.preventDefault();
        event.returnValue = "当前预设有未保存修改，确定离开吗？";
      });

      window.addEventListener("keydown", (event) => {
        if (!this.showPresetEditor) return;
        if (event.key === "Escape") {
          event.preventDefault();
          this.closeEditor();
          return;
        }
        if (
          (event.ctrlKey || event.metaKey) &&
          String(event.key || "").toLowerCase() === "s"
        ) {
          event.preventDefault();
          this.saveOverwrite();
        }
      });

      this.$watch("showPresetEditor", (visible) => {
        if (!visible) {
          autoSaver.stop();
          this.restorePreview = null;
          this.hasConflict = false;
          this.conflictRevision = "";
          clearActiveRuntimeContext("preset");
        }
      });
    },

    get isDirty() {
      if (!this.editingData) return false;
      return JSON.stringify(this.editingData) !== this.baseDataJson;
    },

    get presetTitle() {
      return (
        this.editingData?.name || this.editingPresetFile?.name || "未命名预设"
      );
    },

    get presetKind() {
      return this.editingPresetFile?.preset_kind || "";
    },

    get editorView() {
      return (
        this.editingPresetFile?.reader_view || {
          groups: [],
          items: [],
          stats: {},
        }
      );
    },

    get filteredItems() {
      const term = String(this.searchTerm || "")
        .trim()
        .toLowerCase();
      return (this.editorView.items || []).filter((item) => {
        if (this.activeGroup !== "all" && item.group !== this.activeGroup) {
          return false;
        }
        if (this.uiFilter === "editable" && !item.editable) return false;
        if (this.uiFilter === "changed" && !this.isItemDirty(item)) {
          return false;
        }
        if (this.uiFilter === "unknown" && !item.unknown) return false;
        if (this.uiFilter === "longtext" && item.editor?.kind !== "textarea") {
          return false;
        }
        if (
          this.uiFilter === "collections" &&
          ![
            "prompt-item",
            "sortable-string-list",
            "string-list",
            "key-value-list",
          ].includes(item.editor?.kind)
        ) {
          return false;
        }
        if (!term) return true;

        const haystack = [
          item.title,
          item.summary,
          item.source_key,
          item.value_path,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(term);
      });
    },

    get activeItem() {
      return (
        this.filteredItems.find((item) => item.id === this.activeItemId) ||
        this.filteredItems[0] ||
        null
      );
    },

    get navSections() {
      const detailSections = this.editingPresetFile?.sections || {};
      const dynamic = Object.keys(detailSections);
      return ["basic", ...dynamic, "extensions", "raw", "snapshots"];
    },

    get visibleSections() {
      return this.editingPresetFile?.sections || {};
    },

    get rawJsonText() {
      if (!this.editingData) return "";
      try {
        return JSON.stringify(this.editingData, null, 2);
      } catch (error) {
        return "{}";
      }
    },

    get unknownFieldList() {
      return this.editingPresetFile?.unknown_fields || [];
    },

    get extensionSummary() {
      const extensions = this.editingData?.extensions || {};
      const regexCount = Array.isArray(extensions.regex_scripts)
        ? extensions.regex_scripts.length
        : 0;
      const scriptCount = Array.isArray(extensions?.tavern_helper?.scripts)
        ? extensions.tavern_helper.scripts.length
        : 0;
      return { regexCount, scriptCount };
    },

    buildDraftKey() {
      return `${PRESET_DRAFT_PREFIX}${this.editingPresetFile?.id || "unknown"}`;
    },

    persistLocalDraft() {
      if (!this.editingData || !this.editingPresetFile) return;
      const payload = {
        saved_at: new Date().toISOString(),
        source_revision: this.editingPresetFile.source_revision || "",
        content: this.editingData,
        removed_unknown_fields: Array.isArray(this.removedUnknownFields)
          ? [...this.removedUnknownFields]
          : [],
      };
      localStorage.setItem(this.buildDraftKey(), JSON.stringify(payload));
      this.draftState.savedAt = payload.saved_at;
    },

    restoreLocalDraft() {
      if (!this.editingPresetFile) return false;
      const raw = localStorage.getItem(this.buildDraftKey());
      if (!raw) return false;
      try {
        const payload = JSON.parse(raw);
        if (payload?.content && confirm("检测到本地草稿，是否恢复到编辑器？")) {
          this.editingData = payload.content;
          this.removedUnknownFields = Array.isArray(
            payload.removed_unknown_fields,
          )
            ? [...payload.removed_unknown_fields]
            : [];
          this.dirtyPaths = {};
          this.markAllReaderItemsDirty();
          this.draftState.savedAt = payload.saved_at || "";
          this.draftState.restored = true;
          return true;
        }
      } catch (error) {
        console.warn("Restore preset draft failed:", error);
      }
      return false;
    },

    clearLocalDraft() {
      if (!this.editingPresetFile) return;
      localStorage.removeItem(this.buildDraftKey());
      this.draftState = { savedAt: "", restored: false };
    },

    isItemDirty(item) {
      if (!item) return false;
      return [item.value_path, item.source_key, item.key, item.id].some(
        (dirtyKey) => Boolean(dirtyKey && this.dirtyPaths[dirtyKey]),
      );
    },

    markAllReaderItemsDirty() {
      (this.editorView.items || []).forEach((item) => {
        [item.value_path, item.source_key, item.key, item.id].forEach(
          (dirtyKey) => {
            if (dirtyKey) {
              this.dirtyPaths[dirtyKey] = true;
            }
          },
        );
      });
    },

    getByPath(path) {
      if (!path || !this.editingData) return undefined;
      const normalized = String(path).replace(/\[(\d+)\]/g, ".$1");
      return normalized
        .split(".")
        .filter(Boolean)
        .reduce((value, part) => {
          if (value === null || value === undefined) return undefined;
          return value[part];
        }, this.editingData);
    },

    setByPath(path, value) {
      if (!path || !this.editingData) return;
      const normalized = String(path).replace(/\[(\d+)\]/g, ".$1");
      const parts = normalized.split(".").filter(Boolean);
      if (!parts.length) return;

      let target = this.editingData;
      for (let index = 0; index < parts.length - 1; index += 1) {
        const part = parts[index];
        const nextPart = parts[index + 1];
        if (target[part] === null || typeof target[part] !== "object") {
          target[part] = /^\d+$/.test(nextPart) ? [] : {};
        }
        target = target[part];
      }

      target[parts[parts.length - 1]] = value;
      this.dirtyPaths[path] = true;
    },

    selectGroup(groupId) {
      const previousItemId = this.activeItemId;
      this.activeGroup = groupId || "all";
      const matchingItem = this.filteredItems.find(
        (item) => item.id === previousItemId,
      );
      if (matchingItem) {
        this.activeItemId = matchingItem.id;
        return;
      }

      const first = this.filteredItems[0];
      if (first) {
        this.activeItemId = first.id;
      }
    },

    selectItem(itemId) {
      this.activeItemId = itemId || "";
    },

    getFieldValue(item) {
      if (!item) return null;
      if (item.value_path) {
        return this.getByPath(item.value_path);
      }
      return this.editingData?.[item.key];
    },

    setFieldValue(item, value) {
      if (!item || !this.editingData) return;
      if (item.value_path) {
        this.setByPath(item.value_path, value);
        return;
      }
      this.editingData[item.key] = value;
      this.dirtyPaths[item.key || item.id] = true;
    },

    updatePromptItem(index, key, value) {
      const prompts = Array.isArray(this.getByPath("prompts"))
        ? [...this.getByPath("prompts")]
        : [];
      const previousIdentifier = prompts[index]?.identifier;
      if (key === "identifier") {
        const nextIdentifier = String(value || "").trim();
        if (!nextIdentifier && previousIdentifier) {
          return;
        }
        const order = Array.isArray(this.getByPath("prompt_order"))
          ? [...this.getByPath("prompt_order")]
          : [];
        const reservedIdentifiers = new Set(
          [...prompts.map((prompt) => prompt?.identifier), ...order]
            .map((identifier) => String(identifier || "").trim())
            .filter(Boolean),
        );
        if (previousIdentifier) {
          reservedIdentifiers.delete(String(previousIdentifier).trim());
        }
        if (nextIdentifier && reservedIdentifiers.has(nextIdentifier)) {
          return;
        }
        value = nextIdentifier;
      }
      if (!prompts[index] || typeof prompts[index] !== "object") {
        prompts[index] = {};
      }
      prompts[index] = { ...prompts[index], [key]: value };
      this.setByPath("prompts", prompts);
      if (key === "identifier") {
        const order = Array.isArray(this.getByPath("prompt_order"))
          ? [...this.getByPath("prompt_order")]
          : [];
        this.setByPath(
          "prompt_order",
          previousIdentifier
            ? order.map((entry) =>
                entry === previousIdentifier ? value : entry,
              )
            : value
              ? [...order, value]
              : order,
        );
      }
    },

    addPromptItem() {
      const prompts = Array.isArray(this.getByPath("prompts"))
        ? [...this.getByPath("prompts")]
        : [];
      const order = Array.isArray(this.getByPath("prompt_order"))
        ? [...this.getByPath("prompt_order")]
        : [];
      const existingIdentifiers = new Set(
        [...prompts.map((prompt) => prompt?.identifier), ...order]
          .map((identifier) => String(identifier || "").trim())
          .filter(Boolean),
      );
      let nextIndex = prompts.length + 1;
      let nextIdentifier = `prompt_${nextIndex}`;
      while (existingIdentifiers.has(nextIdentifier)) {
        nextIndex += 1;
        nextIdentifier = `prompt_${nextIndex}`;
      }
      const nextPrompt = {
        identifier: nextIdentifier,
        name: "",
        role: "system",
        content: "",
        enabled: true,
        marker: false,
      };
      prompts.push(nextPrompt);
      this.setByPath("prompts", prompts);
      this.setByPath("prompt_order", [...order, nextPrompt.identifier]);
    },

    removePromptItem(index) {
      const prompts = Array.isArray(this.getByPath("prompts"))
        ? [...this.getByPath("prompts")]
        : [];
      if (index < 0 || index >= prompts.length) return;
      const [removed] = prompts.splice(index, 1);
      this.setByPath("prompts", prompts);
      const order = Array.isArray(this.getByPath("prompt_order"))
        ? this.getByPath("prompt_order")
        : [];
      if (removed?.identifier) {
        this.setByPath(
          "prompt_order",
          order.filter((value) => value !== removed.identifier),
        );
      }
    },

    moveListItem(path, fromIndex, toIndex) {
      if (!path || fromIndex === toIndex) return;
      const list = Array.isArray(this.getByPath(path))
        ? [...this.getByPath(path)]
        : [];
      if (
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= list.length ||
        toIndex >= list.length
      ) {
        return;
      }
      const [item] = list.splice(fromIndex, 1);
      list.splice(toIndex, 0, item);
      this.setByPath(path, list);
    },

    addStringListItem(path) {
      if (!path) return;
      const list = Array.isArray(this.getByPath(path))
        ? [...this.getByPath(path)]
        : [];
      list.push("");
      this.setByPath(path, list);
    },

    updateStringListItem(path, index, value) {
      if (!path) return;
      const list = Array.isArray(this.getByPath(path))
        ? [...this.getByPath(path)]
        : [];
      if (index < 0 || index >= list.length) return;
      list[index] = value;
      this.setByPath(path, list);
    },

    removeStringListItem(path, index) {
      if (!path) return;
      const list = Array.isArray(this.getByPath(path))
        ? [...this.getByPath(path)]
        : [];
      if (index < 0 || index >= list.length) return;
      list.splice(index, 1);
      this.setByPath(path, list);
    },

    addBiasEntry() {
      const logitBias = Array.isArray(this.getByPath("logit_bias"))
        ? [...this.getByPath("logit_bias")]
        : [];
      logitBias.push({ text: "", value: 0 });
      this.setByPath("logit_bias", logitBias);
    },

    removeBiasEntry(index) {
      const logitBias = Array.isArray(this.getByPath("logit_bias"))
        ? [...this.getByPath("logit_bias")]
        : [];
      if (index < 0 || index >= logitBias.length) return;
      logitBias.splice(index, 1);
      this.setByPath("logit_bias", logitBias);
    },

    updateBiasEntry(index, key, value) {
      const logitBias = Array.isArray(this.getByPath("logit_bias"))
        ? [...this.getByPath("logit_bias")]
        : [];
      if (!logitBias[index] || typeof logitBias[index] !== "object") {
        logitBias[index] = {};
      }
      const nextValue = key === "value" ? Number(value) : value;
      const numericValue = Number(value);
      logitBias[index] = {
        ...logitBias[index],
        [key]:
          key === "value"
            ? Number.isFinite(numericValue)
              ? numericValue
              : 0
            : nextValue,
      };
      this.setByPath("logit_bias", logitBias);
    },

    formatValue(value) {
      if (value === null || value === undefined || value === "") return "-";
      if (typeof value === "boolean") return value ? "是" : "否";
      if (typeof value === "number")
        return Number.isInteger(value)
          ? value
          : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
      if (typeof value === "object") {
        try {
          return JSON.stringify(value, null, 2);
        } catch (error) {
          return String(value);
        }
      }
      return String(value);
    },

    isLongTextField(item) {
      return Boolean(item && LONG_TEXT_FIELDS.has(item.key));
    },

    estimateFieldTokens(item) {
      if (!item) return 0;
      return estimateTokens(String(this.getFieldValue(item) || ""));
    },

    openLargeEditorForItem(item) {
      if (!item || !this.editingData) return;
      window.dispatchEvent(
        new CustomEvent("open-large-editor", {
          detail: {
            field: item.key,
            title: item.label,
            isArray: false,
            index: 0,
            editingData: this.editingData,
          },
        }),
      );
    },

    async openPresetEditor({
      presetId,
      activeNav = "basic",
      restoreDefault = false,
    } = {}) {
      if (!presetId) return;
      this.isLoading = true;
      try {
        const res = await getPresetDetail(presetId);
        if (!res.success) {
          this.$store.global.showToast(res.msg || "打开预设失败", "error");
          return;
        }

        this.editingPresetFile = deepClone(res.preset);
        this.editingData = deepClone(res.preset.raw_data || {});
        this.baseDataJson = JSON.stringify(this.editingData);
        this.activeNav = activeNav || this.navSections[0] || "basic";
        this.searchTerm = "";
        this.uiFilter = "all";
        this.activeGroup = "all";
        this.activeItemId = "";
        this.showMobileSidebar = false;
        this.showRightPanel = true;
        this.showRawEditor = false;
        this.removedUnknownFields = [];
        this.dirtyPaths = {};
        this.selectGroup("all");
        this.showPresetEditor = true;
        this.leftNavOpen = this.$store.global.deviceType !== "mobile";
        this.rightPanelOpen = this.$store.global.deviceType !== "mobile";
        this.draftState = { savedAt: "", restored: false };
        this.restorePreview = null;
        this.hasConflict = false;
        this.conflictRevision = "";

        setActiveRuntimeContext({
          preset: {
            id: this.editingPresetFile.id,
            name: this.editingPresetFile.name,
            type: this.editingPresetFile.type,
            path: this.editingPresetFile.path,
          },
        });

        this.$nextTick(() => {
          this.restoreLocalDraft();
          autoSaver.initBaseline(this.editingData);
          autoSaver.start(
            () => this.editingData,
            () => null,
            async () => {
              this.persistLocalDraft();
            },
          );
          if (restoreDefault) {
            this.previewRestoreDefault();
          }
        });
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("打开预设失败", "error");
      } finally {
        this.isLoading = false;
      }
    },

    async reloadFromDisk() {
      if (!this.editingPresetFile?.id) return;
      const preserveDraft = this.isDirty;
      if (preserveDraft) {
        this.persistLocalDraft();
      }
      await this.openPresetEditor({ presetId: this.editingPresetFile.id });
    },

    closeEditor() {
      if (this.isDirty && !confirm("当前预设有未保存修改，确定关闭吗？")) {
        return;
      }
      if (this.isDirty) {
        this.persistLocalDraft();
      }
      this.showPresetEditor = false;
    },

    async saveOverwrite() {
      if (!this.editingPresetFile || !this.editingData || this.isSaving) return;
      this.isSaving = true;
      this.hasConflict = false;
      this.conflictRevision = "";
      try {
        const res = await savePreset({
          preset_id: this.editingPresetFile.id,
          preset_kind: this.editingPresetFile.preset_kind,
          save_mode: "overwrite",
          source_revision: this.editingPresetFile.source_revision,
          removed_unknown_fields: this.removedUnknownFields,
          content: this.editingData,
        });

        if (!res.success) {
          if (res.current_source_revision) {
            this.hasConflict = true;
            this.conflictRevision = res.current_source_revision;
            this.$store.global.showToast(
              "文件已被外部修改，请重新加载或另存为",
              "error",
            );
            return;
          }
          this.$store.global.showToast(res.msg || "保存失败", "error");
          return;
        }

        this.editingPresetFile = deepClone(
          res.preset || this.editingPresetFile,
        );
        this.editingData = deepClone(
          this.editingPresetFile.raw_data || this.editingData,
        );
        this.baseDataJson = JSON.stringify(this.editingData);
        this.removedUnknownFields = [];
        this.dirtyPaths = {};
        autoSaver.initBaseline(this.editingData);
        this.clearLocalDraft();
        setActiveRuntimeContext({
          preset: {
            id: this.editingPresetFile.id,
            name: this.editingPresetFile.name,
            type: this.editingPresetFile.type,
            path: this.editingPresetFile.path,
          },
        });
        this.$store.global.showToast("预设已保存");
        window.dispatchEvent(new CustomEvent("refresh-preset-list"));
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("保存失败", "error");
      } finally {
        this.isSaving = false;
      }
    },

    async saveAs() {
      if (!this.editingData || this.isSaving) return;
      const name = prompt(
        "请输入新预设名称：",
        this.editingData.name || this.editingPresetFile?.name || "新预设",
      );
      if (!name) return;
      this.isSaving = true;
      try {
        const res = await savePreset({
          preset_kind: this.editingPresetFile?.preset_kind || "",
          save_mode: "save_as",
          name,
          content: { ...this.editingData, name },
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "另存为失败", "error");
          return;
        }
        this.$store.global.showToast("已另存为新预设");
        window.dispatchEvent(new CustomEvent("refresh-preset-list"));
        await this.openPresetEditor({
          presetId: res.preset_id || res.preset?.id,
        });
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("另存为失败", "error");
      } finally {
        this.isSaving = false;
      }
    },

    async renamePreset() {
      if (!this.editingPresetFile || this.isSaving) return;
      const name = prompt(
        "请输入新的预设名称：",
        this.editingData?.name || this.editingPresetFile.name || "",
      );
      if (!name) return;
      this.isSaving = true;
      try {
        const res = await savePreset({
          preset_id: this.editingPresetFile.id,
          save_mode: "rename",
          new_name: name,
          source_revision: this.editingPresetFile.source_revision,
        });
        if (!res.success) {
          if (res.current_source_revision) {
            this.hasConflict = true;
            this.conflictRevision = res.current_source_revision;
          }
          this.$store.global.showToast(res.msg || "重命名失败", "error");
          return;
        }
        this.$store.global.showToast("预设已重命名");
        window.dispatchEvent(new CustomEvent("refresh-preset-list"));
        await this.openPresetEditor({
          presetId: res.preset_id || res.preset?.id,
        });
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("重命名失败", "error");
      } finally {
        this.isSaving = false;
      }
    },

    async deletePreset() {
      if (!this.editingPresetFile || this.isSaving) return;
      if (
        !confirm(
          `确定删除预设“${this.editingPresetFile.name || "未命名预设"}”吗？`,
        )
      )
        return;
      this.isSaving = true;
      try {
        const res = await savePreset({
          preset_id: this.editingPresetFile.id,
          save_mode: "delete",
          source_revision: this.editingPresetFile.source_revision,
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "删除失败", "error");
          return;
        }
        this.$store.global.showToast("预设已删除");
        window.dispatchEvent(new CustomEvent("refresh-preset-list"));
        this.showPresetEditor = false;
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("删除失败", "error");
      } finally {
        this.isSaving = false;
      }
    },

    async previewRestoreDefault() {
      if (!this.editingPresetFile?.capabilities?.can_restore_default) {
        this.$store.global.showToast("当前预设不支持恢复默认", "error");
        return;
      }
      try {
        const res = await getPresetDefaultPreview({
          preset_id: this.editingPresetFile.id,
          preset_kind: this.editingPresetFile.preset_kind,
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "默认模板不存在", "error");
          return;
        }
        this.restorePreview = res;
        if (
          !confirm(
            `已找到默认模板：${res.default_path}\n是否载入到当前编辑器？`,
          )
        ) {
          return;
        }
        this.editingData = deepClone(res.default_content || {});
        this.removedUnknownFields = [];
        this.dirtyPaths = {};
        this.markAllReaderItemsDirty();
        this.$store.global.showToast(
          "已载入默认模板，点击保存后才会覆盖磁盘文件",
        );
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("恢复默认失败", "error");
      }
    },

    openAdvancedExtensions() {
      if (!this.editingData) return;
      const editingData = {
        extensions: this.editingData.extensions || {
          regex_scripts: [],
          tavern_helper: { scripts: [] },
        },
      };
      window.dispatchEvent(
        new CustomEvent("open-advanced-editor", {
          detail: editingData,
        }),
      );
      const saveHandler = async () => {
        window.removeEventListener("advanced-editor-save", saveHandler);
        await this.saveExtensions();
      };
      window.addEventListener("advanced-editor-save", saveHandler);
    },

    async saveExtensions() {
      if (!this.editingPresetFile || !this.editingData) return;
      try {
        const res = await apiSavePresetExtensions({
          id: this.editingPresetFile.id,
          extensions: this.editingData.extensions || {},
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "保存扩展失败", "error");
          return;
        }
        this.$store.global.showToast("扩展已保存");
        await this.reloadFromDisk();
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("保存扩展失败", "error");
      }
    },

    async createSnapshot() {
      if (!this.editingPresetFile || !this.editingData) return;
      try {
        const res = await apiCreateSnapshot({
          id: this.editingPresetFile.id,
          type: "preset",
          file_path:
            this.editingPresetFile.file_path || this.editingPresetFile.path,
          label: "",
          content: this.editingData,
          compact: true,
        });
        if (!res.success) {
          this.$store.global.showToast(res.msg || "快照失败", "error");
          return;
        }
        this.$store.global.showToast("快照已保存");
      } catch (error) {
        console.error(error);
        this.$store.global.showToast("快照失败", "error");
      }
    },

    openRollback() {
      if (!this.editingPresetFile) return;
      window.dispatchEvent(
        new CustomEvent("open-rollback", {
          detail: {
            type: "preset",
            id: this.editingPresetFile.id,
            path:
              this.editingPresetFile.file_path || this.editingPresetFile.path,
            editingData: this.editingData,
            editingPresetFile: this.editingPresetFile,
          },
        }),
      );
    },

    openRawEditor() {
      this.showRawEditor = true;
      this.showRightPanel = true;
      this.activeNav = "raw";
    },

    get rawUnknownJsonText() {
      if (!this.unknownFieldList.length || !this.editingData) return "{}";
      const payload = Object.create(null);
      this.unknownFieldList.forEach((key) => {
        payload[key] = this.editingData?.[key];
      });
      return JSON.stringify(payload, null, 2);
    },

    applyRawUnknownJson(text) {
      try {
        const parsed = JSON.parse(text || "{}");
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
          throw new Error("Raw unknown JSON must be an object");
        }
        this.unknownFieldList.forEach((key) => {
          if (Object.prototype.hasOwnProperty.call(parsed, key)) {
            Object.defineProperty(this.editingData, key, {
              value: parsed[key],
              enumerable: true,
              writable: true,
              configurable: true,
            });
          } else {
            delete this.editingData[key];
          }
          this.dirtyPaths[key] = true;
        });
        this.removedUnknownFields = this.unknownFieldList.filter(
          (key) => !Object.prototype.hasOwnProperty.call(parsed, key),
        );
        this.showRawEditor = false;
        this.$store.global.showToast("高级原始编辑区已应用");
      } catch (error) {
        this.$store.global.showToast("原始 JSON 格式无效", "error");
      }
    },
  };
}
