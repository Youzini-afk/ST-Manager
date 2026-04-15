/**
 * static/js/components/presetEditor.js
 * 预设全屏编辑器
 */

import { createAutoSaver } from "../utils/autoSave.js";
import { createSnapshot as apiCreateSnapshot } from "../api/system.js";
import {
  getPresetDetail,
  savePreset,
  savePresetExtensions as apiSavePresetExtensions,
} from "../api/presets.js";
import { estimateTokens, formatDate } from "../utils/format.js";
import {
  clearActiveRuntimeContext,
  setActiveRuntimeContext,
} from "../runtime/runtimeContext.js";

const PRESET_DRAFT_PREFIX = "st-manager:preset-draft:";

const PROMPT_TRIGGER_OPTIONS = ["normal", "continue", "impersonate", "quiet"];

const PROMPT_POSITION_OPTIONS = [
  { value: 0, label: "相对位置" },
  { value: 1, label: "In-Chat 注入" },
];

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
    activeWorkspace: "all",
    activeGroup: "all",
    activePromptId: "",
    activeGenericItemId: "",
    activeItemId: "",
    searchTerm: "",
    uiFilter: "all",
    showMobileSidebar: false,
    showRightPanel: true,
    dirtyPaths: {},
    editingPresetFile: null,
    editingData: null,
    baseDataJson: "",
    draftState: { savedAt: "", restored: false },
    sectionLabels: SECTION_LABELS,
    promptTriggerOptions: PROMPT_TRIGGER_OPTIONS,
    promptPositionOptions: PROMPT_POSITION_OPTIONS,
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
          family: "generic",
          family_label: "通用预设",
          groups: [],
          items: [],
          stats: {},
        }
      );
    },

    get isPromptWorkspaceEditor() {
      return this.editorView.family === "prompt_manager";
    },

    get promptItems() {
      if (!Array.isArray(this.editingData?.prompts)) return [];
      return this.editingData.prompts
        .map((prompt, index) => {
          if (!prompt || typeof prompt !== "object") {
            return null;
          }
          return {
            ...prompt,
            __prompt_index: index,
          };
        })
        .filter(Boolean);
    },

    normalizePromptOrder() {
      const promptOrder = this.editingData?.prompt_order;
      if (!Array.isArray(promptOrder)) return [];

      if (
        promptOrder.length &&
        promptOrder.every((entry) => typeof entry === "string")
      ) {
        return promptOrder
          .map((identifier, index) => ({
            identifier: String(identifier || "").trim(),
            enabled: null,
            order_index: index,
          }))
          .filter((entry) => entry.identifier);
      }

      if (
        promptOrder.length &&
        promptOrder.every(
          (entry) =>
            entry && typeof entry === "object" && "identifier" in entry,
        )
      ) {
        return promptOrder
          .map((entry, index) => ({
            identifier: String(entry.identifier || "").trim(),
            enabled: typeof entry.enabled === "boolean" ? entry.enabled : null,
            order_index: index,
          }))
          .filter((entry) => entry.identifier);
      }

      const nestedBucket = promptOrder.find(
        (entry) =>
          entry && typeof entry === "object" && Array.isArray(entry.order),
      );
      if (!nestedBucket) return [];

      return nestedBucket.order
        .map((entry, index) => ({
          identifier: String(entry?.identifier || "").trim(),
          enabled: typeof entry?.enabled === "boolean" ? entry.enabled : null,
          order_index: index,
        }))
        .filter((entry) => entry.identifier);
    },

    hasUnsupportedNestedPromptOrder() {
      const promptOrder = Array.isArray(this.editingData?.prompt_order)
        ? this.editingData.prompt_order
        : [];
      const nestedBucketCount = promptOrder.filter(
        (entry) =>
          entry && typeof entry === "object" && Array.isArray(entry.order),
      ).length;
      return nestedBucketCount > 1;
    },

    get orderedPromptItems() {
      const prompts = this.promptItems.map((prompt, index) => ({
        ...prompt,
        __prompt_index: Number(prompt.__prompt_index ?? index),
        __raw_identifier: String(prompt.identifier || "").trim(),
        __identifier:
          String(prompt.identifier || `prompt_${index + 1}`).trim() ||
          `prompt_${index + 1}`,
      }));
      const promptMap = new Map(
        prompts.map((prompt) => [prompt.__identifier, prompt]),
      );
      const orderEntries = this.normalizePromptOrder();

      const ordered = orderEntries
        .map((entry) => {
          const prompt = promptMap.get(entry.identifier);
          if (!prompt) return null;
          promptMap.delete(entry.identifier);
          return {
            ...prompt,
            __enabled:
              typeof entry.enabled === "boolean"
                ? entry.enabled
                : prompt.enabled !== false,
            __order_index: entry.order_index,
            __is_orphan: false,
          };
        })
        .filter(Boolean);

      const orphaned = [...promptMap.values()].map((prompt, index) => ({
        ...prompt,
        __enabled: prompt.enabled !== false,
        __order_index: ordered.length + index,
        __is_orphan: true,
      }));

      return [...ordered, ...orphaned];
    },

    get activePromptItem() {
      return (
        this.orderedPromptItems.find(
          (prompt) => prompt.__identifier === this.activePromptId,
        ) ||
        this.orderedPromptItems[0] ||
        null
      );
    },

    get genericWorkspaceItems() {
      if (!this.isPromptWorkspaceEditor) {
        return this.filteredItems;
      }

      const workspace = this.activeWorkspace;
      if (!workspace || workspace === "prompts") {
        return [];
      }

      return (this.editorView.items || []).filter(
        (item) => item.group === workspace,
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
        if (this.uiFilter === "longtext" && item.editor?.kind !== "textarea") {
          return false;
        }
        if (
          this.uiFilter === "collections" &&
          !["sortable-string-list", "string-list", "key-value-list"].includes(
            item.editor?.kind,
          )
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
      const activeItemId =
        this.isPromptWorkspaceEditor && this.activeWorkspace !== "prompts"
          ? this.activeGenericItemId || this.activeItemId
          : this.activeItemId;
      return (
        this.filteredItems.find((item) => item.id === activeItemId) ||
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

    syncPromptOrder(nextOrderedPrompts = null) {
      if (!this.editingData) return;
      if (this.hasUnsupportedNestedPromptOrder()) return;

      const orderedPrompts = Array.isArray(nextOrderedPrompts)
        ? nextOrderedPrompts
        : this.orderedPromptItems;
      const canPersistOrder = orderedPrompts.every((prompt) =>
        String(prompt?.__raw_identifier || "").trim(),
      );
      const currentPromptOrder = Array.isArray(this.editingData.prompt_order)
        ? this.editingData.prompt_order
        : [];

      if (!canPersistOrder) {
        if (
          Object.prototype.hasOwnProperty.call(this.editingData, "prompt_order")
        ) {
          delete this.editingData.prompt_order;
          this.dirtyPaths.prompt_order = true;
        }
        return;
      }

      if (
        currentPromptOrder.some(
          (entry) =>
            entry && typeof entry === "object" && Array.isArray(entry.order),
        )
      ) {
        const nextBuckets = [...currentPromptOrder];
        const bucketIndex = nextBuckets.findIndex(
          (entry) =>
            entry && typeof entry === "object" && Array.isArray(entry.order),
        );
        if (bucketIndex !== -1) {
          const existingOrderEntries = new Map(
            (Array.isArray(nextBuckets[bucketIndex].order)
              ? nextBuckets[bucketIndex].order
              : []
            )
              .filter((entry) => entry && typeof entry === "object")
              .map((entry) => [String(entry.identifier || "").trim(), entry]),
          );
          nextBuckets[bucketIndex] = {
            ...nextBuckets[bucketIndex],
            order: orderedPrompts.map((prompt) => {
              const existing =
                existingOrderEntries.get(
                  prompt.__raw_identifier || prompt.__identifier,
                ) ||
                existingOrderEntries.get(prompt.__identifier) ||
                null;
              const nextEntry = {
                ...(existing || {}),
                identifier: prompt.__raw_identifier || prompt.__identifier,
              };
              if (
                existing &&
                Object.prototype.hasOwnProperty.call(existing, "enabled")
              ) {
                nextEntry.enabled = prompt.__enabled !== false;
              } else {
                delete nextEntry.enabled;
              }
              return nextEntry;
            }),
          };
          this.setByPath("prompt_order", nextBuckets);
          return;
        }
      }

      if (
        currentPromptOrder.length &&
        currentPromptOrder.every(
          (entry) =>
            entry && typeof entry === "object" && "identifier" in entry,
        )
      ) {
        const existingEntries = new Map(
          currentPromptOrder
            .filter((entry) => entry && typeof entry === "object")
            .map((entry) => [String(entry.identifier || "").trim(), entry]),
        );

        this.setByPath(
          "prompt_order",
          orderedPrompts.map((prompt) => {
            const existing =
              existingEntries.get(
                prompt.__raw_identifier || prompt.__identifier,
              ) ||
              existingEntries.get(prompt.__identifier) ||
              null;
            const nextEntry = {
              ...(existing || {}),
              identifier: prompt.__raw_identifier || prompt.__identifier,
            };
            if (
              existing &&
              Object.prototype.hasOwnProperty.call(existing, "enabled")
            ) {
              nextEntry.enabled = prompt.__enabled !== false;
            } else {
              delete nextEntry.enabled;
            }
            return nextEntry;
          }),
        );
        return;
      }

      this.setByPath(
        "prompt_order",
        orderedPrompts.map((prompt) => prompt.__identifier),
      );
    },

    getPromptArrayWithMeta() {
      return this.orderedPromptItems;
    },

    replacePromptOrder(nextOrderedPrompts) {
      if (!this.editingData || !Array.isArray(nextOrderedPrompts)) return;
      if (this.hasUnsupportedNestedPromptOrder()) return;

      const reordered = nextOrderedPrompts
        .map((entry) => {
          const promptIndex = Number(entry?.__prompt_index);
          if (!Number.isInteger(promptIndex)) {
            return null;
          }
          return this.promptItems.find(
            (prompt) => Number(prompt.__prompt_index) === promptIndex,
          );
        })
        .filter(Boolean)
        .map((prompt) => {
          const nextPrompt = { ...prompt };
          delete nextPrompt.__prompt_index;
          return nextPrompt;
        });

      this.setByPath("prompts", reordered);
      const enriched = nextOrderedPrompts.map((entry) => ({
        ...entry,
        __enabled: entry.__enabled !== false,
      }));
      this.syncPromptOrder(enriched);
    },

    movePromptItem(fromIndex, toIndex) {
      const orderedPrompts = [...this.getPromptArrayWithMeta()];
      if (
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= orderedPrompts.length ||
        toIndex >= orderedPrompts.length ||
        fromIndex === toIndex
      ) {
        return;
      }

      const [prompt] = orderedPrompts.splice(fromIndex, 1);
      orderedPrompts.splice(toIndex, 0, prompt);
      this.replacePromptOrder(orderedPrompts);
      this.activePromptId = prompt?.__identifier || this.activePromptId;
    },

    togglePromptEnabled(identifier) {
      const promptId = String(identifier || "");
      if (!promptId || !this.editingData) return;
      if (this.hasUnsupportedNestedPromptOrder()) return;

      const orderedPrompts = this.orderedPromptItems.map((prompt) => {
        if (prompt.__identifier !== promptId) {
          return prompt;
        }
        return {
          ...prompt,
          __enabled: prompt.__enabled === false,
        };
      });

      if (
        Array.isArray(this.editingData.prompt_order) &&
        this.editingData.prompt_order.some(
          (entry) =>
            entry && typeof entry === "object" && Array.isArray(entry.order),
        )
      ) {
        this.syncPromptOrder(orderedPrompts);
        return;
      }

      const prompts = Array.isArray(this.editingData.prompts)
        ? [...this.editingData.prompts]
        : [];
      const activeEntry = orderedPrompts.find(
        (entry) => entry.__identifier === promptId,
      );
      const promptIndex = Number(activeEntry?.__prompt_index);
      if (promptIndex !== -1) {
        prompts[promptIndex] = {
          ...prompts[promptIndex],
          enabled: activeEntry?.__enabled !== false,
        };
        this.setByPath("prompts", prompts);
      }

      this.syncPromptOrder(orderedPrompts);
    },

    updatePromptField(key, value) {
      const active = this.activePromptItem;
      if (!active || !this.editingData) return;

      const previousIdentifier = active.__identifier;
      const promptIndex = Number(active.__prompt_index);
      const prompts = Array.isArray(this.editingData.prompts)
        ? [...this.editingData.prompts]
        : [];
      if (!prompts[promptIndex] || typeof prompts[promptIndex] !== "object") {
        return;
      }
      if (key === "content" && prompts[promptIndex].marker) {
        return;
      }

      const nextPrompt = {
        ...prompts[promptIndex],
        [key]: value,
      };
      if (key === "injection_position") {
        nextPrompt[key] = Number(value);
      }
      if (key === "injection_depth" || key === "injection_order") {
        nextPrompt[key] = Number(value);
      }

      prompts[promptIndex] = nextPrompt;
      this.setByPath("prompts", prompts);

      if (key === "identifier") {
        const nextIdentifier = String(nextPrompt.identifier || "").trim();
        this.activePromptId = nextIdentifier || this.activePromptId;

        if (Array.isArray(this.editingData.prompt_order)) {
          const nextPromptOrder = this.editingData.prompt_order.map((entry) => {
            if (typeof entry === "string") {
              return entry === previousIdentifier ? nextIdentifier : entry;
            }
            if (entry && typeof entry === "object" && "identifier" in entry) {
              if (
                String(entry.identifier || "").trim() === previousIdentifier
              ) {
                return {
                  ...entry,
                  identifier: nextIdentifier,
                };
              }
              return entry;
            }
            if (
              entry &&
              typeof entry === "object" &&
              Array.isArray(entry.order)
            ) {
              return {
                ...entry,
                order: entry.order.map((orderEntry) => {
                  if (
                    orderEntry &&
                    typeof orderEntry === "object" &&
                    String(orderEntry.identifier || "").trim() ===
                      previousIdentifier
                  ) {
                    return {
                      ...orderEntry,
                      identifier: nextIdentifier,
                    };
                  }
                  return orderEntry;
                }),
              };
            }
            return entry;
          });
          this.setByPath("prompt_order", nextPromptOrder);
        }
      }
    },

    updatePromptTriggers(selectedValues) {
      const active = this.activePromptItem;
      if (!active || !this.editingData) return;

      const promptIndex = Number(active.__prompt_index);
      const prompts = Array.isArray(this.editingData.prompts)
        ? [...this.editingData.prompts]
        : [];
      if (!prompts[promptIndex] || typeof prompts[promptIndex] !== "object") {
        return;
      }

      prompts[promptIndex] = {
        ...prompts[promptIndex],
        injection_trigger: Array.from(selectedValues || [])
          .map((entry) => String(entry || "").trim())
          .filter(Boolean),
      };
      this.setByPath("prompts", prompts);
    },

    isPromptContentEditable(prompt) {
      return Boolean(prompt && !prompt.marker);
    },

    selectGroup(groupId) {
      const previousItemId = this.activeItemId;
      this.activeGroup = groupId || "all";
      const matchingItem = this.filteredItems.find(
        (item) => item.id === previousItemId,
      );
      if (matchingItem) {
        this.activeItemId = matchingItem.id;
        this.activeGenericItemId = matchingItem.id;
        return;
      }

      const first = this.filteredItems[0];
      if (first) {
        this.activeItemId = first.id;
        this.activeGenericItemId = first.id;
      }
    },

    selectWorkspace(workspaceId) {
      this.activeWorkspace =
        workspaceId || (this.isPromptWorkspaceEditor ? "prompts" : "all");
      if (!this.isPromptWorkspaceEditor) {
        this.selectGroup(this.activeWorkspace);
        return;
      }

      if (this.activeWorkspace === "prompts") {
        this.activePromptId =
          this.activePromptItem?.__identifier ||
          this.orderedPromptItems[0]?.__identifier ||
          "";
        return;
      }

      this.activeGroup = this.activeWorkspace;
      const firstItem = this.genericWorkspaceItems[0] || null;
      this.activeGenericItemId = firstItem?.id || "";
      this.activeItemId = firstItem?.id || "";
    },

    selectItem(itemId) {
      this.activeItemId = itemId || "";
      this.activeGenericItemId = itemId || "";
    },

    selectPrompt(promptId) {
      this.activeWorkspace = "prompts";
      this.activePromptId = String(promptId || "");
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

    async openPresetEditor({ presetId, activeNav = "basic" } = {}) {
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
        this.activeWorkspace = this.isPromptWorkspaceEditor ? "prompts" : "all";
        this.searchTerm = "";
        this.uiFilter = "all";
        this.activeGroup = "all";
        this.activePromptId = this.orderedPromptItems[0]?.__identifier || "";
        this.activeGenericItemId = "";
        this.activeItemId = "";
        this.showMobileSidebar = false;
        this.showRightPanel = true;
        this.dirtyPaths = {};
        this.selectGroup("all");
        this.showPresetEditor = true;
        this.draftState = { savedAt: "", restored: false };
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
      this.activeWorkspace = "all";
      this.activePromptId = "";
      this.activeGenericItemId = "";
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
  };
}
