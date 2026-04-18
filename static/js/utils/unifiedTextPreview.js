import { formatScopedDisplayedHtml } from "./stDisplayFormatter.js";

const READER_REGEX_PLACEMENT = {
  MD_DISPLAY: 0,
  USER_INPUT: 1,
  AI_OUTPUT: 2,
  SLASH_COMMAND: 3,
  WORLD_INFO: 5,
  REASONING: 6,
};

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeReaderDepthMode(mode) {
  switch (String(mode || "").trim()) {
    case "anchor_abs":
      return "anchor_abs";
    case "anchor_backward":
      return "anchor_backward";
    case "anchor_relative":
      return "anchor_relative";
    default:
      return "";
  }
}

function normalizeRegexRuleSource(source) {
  switch (String(source || "").trim()) {
    case "card":
      return "card";
    case "preset":
    case "preset_import":
    case "st_preset":
    case "st_preset_import":
      return "preset_import";
    case "regex":
    case "regex_file":
    case "regex_import":
    case "regex_script":
      return "regex_import";
    case "manual":
    case "handwritten":
      return "manual";
    case "chat":
    case "draft":
    case "local":
    case "builtin":
    case "legacy_chat":
      return "chat";
    default:
      return "unknown";
  }
}

function normalizeDisplayRule(rule, index = 0) {
  const source = rule && typeof rule === "object" ? rule : {};
  const normalizeNullableNumber = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };

  return {
    id: source.id || `display_rule_${Date.now()}_${index}`,
    scriptName:
      String(source.scriptName || source.name || `规则 ${index + 1}`).trim() ||
      `规则 ${index + 1}`,
    findRegex: String(source.findRegex || "").trim(),
    replaceString: String(source.replaceString || ""),
    substituteRegex: Number(source.substituteRegex || 0),
    trimStrings: Array.isArray(source.trimStrings)
      ? source.trimStrings.map((item) => String(item))
      : [],
    disabled: Boolean(source.disabled),
    promptOnly: Boolean(source.promptOnly),
    markdownOnly: Boolean(source.markdownOnly),
    runOnEdit: source.runOnEdit !== false,
    minDepth: normalizeNullableNumber(source.minDepth),
    maxDepth: normalizeNullableNumber(source.maxDepth),
    readerDepthMode: normalizeReaderDepthMode(
      source.readerDepthMode || source.reader_depth_mode,
    ),
    readerMinDepth: normalizeNullableNumber(
      source.readerMinDepth ?? source.reader_min_depth,
    ),
    readerMaxDepth: normalizeNullableNumber(
      source.readerMaxDepth ?? source.reader_max_depth,
    ),
    placement: Array.isArray(source.placement) ? source.placement : [],
    expanded: Boolean(source.expanded),
    deleted: Boolean(source.deleted),
    overrideKey: String(source.overrideKey || source.override_key || "").trim(),
    source: normalizeRegexRuleSource(source.source),
  };
}

function stripCommonIndent(text) {
  const source = String(text || "").replace(/\r\n/g, "\n");
  const lines = source.split("\n");

  while (lines.length && !lines[0].trim()) {
    lines.shift();
  }
  while (lines.length && !lines[lines.length - 1].trim()) {
    lines.pop();
  }

  const indents = lines
    .filter((line) => line.trim())
    .map((line) => {
      const match = line.match(/^\s*/);
      return match ? match[0].length : 0;
    });

  const minIndent = indents.length ? Math.min(...indents) : 0;
  return lines
    .map((line) => line.slice(minIndent))
    .join("\n")
    .trim();
}

function parseDisplayRuleRegex(findRegex) {
  const source = String(findRegex || "").trim();
  if (!source) return null;

  const wrapped = source.match(/^\/([\s\S]+)\/([dgimsuvy]*)$/);
  if (wrapped) {
    return new RegExp(wrapped[1], wrapped[2]);
  }

  return new RegExp(source, "g");
}

function sanitizeRegexMacroValue(value) {
  return String(value ?? "").replaceAll(
    /[\n\r\t\v\f\0.^$*+?{}[\]\\/|()]/gs,
    (token) => {
      switch (token) {
        case "\n":
          return "\\n";
        case "\r":
          return "\\r";
        case "\t":
          return "\\t";
        case "\v":
          return "\\v";
        case "\f":
          return "\\f";
        case "\0":
          return "\\0";
        default:
          return `\\${token}`;
      }
    },
  );
}

function substituteDisplayRuleMacros(
  text,
  macroContext = {},
  sanitizer = null,
) {
  const source = String(text ?? "");
  const context =
    macroContext && typeof macroContext === "object" ? macroContext : {};

  return source.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, (match, rawKey) => {
    const key = String(rawKey || "")
      .trim()
      .toLowerCase();
    const value = Object.prototype.hasOwnProperty.call(context, key)
      ? context[key]
      : Object.prototype.hasOwnProperty.call(context, rawKey)
        ? context[rawKey]
        : match;
    const normalized = String(value ?? "");
    return typeof sanitizer === "function" ? sanitizer(normalized) : normalized;
  });
}

function getDisplayRuleRegexSource(rule, options = {}) {
  const normalized = normalizeDisplayRule(rule);
  switch (Number(normalized.substituteRegex || 0)) {
    case 1:
      return substituteDisplayRuleMacros(
        normalized.findRegex,
        options.macroContext,
      );
    case 2:
      return substituteDisplayRuleMacros(
        normalized.findRegex,
        options.macroContext,
        sanitizeRegexMacroValue,
      );
    default:
      return normalized.findRegex;
  }
}

function getReaderDisplayRuleOrderBucket(rule, index = 0) {
  const normalized = normalizeDisplayRule(rule, index);
  const pattern = String(normalized.findRegex || "").toLowerCase();
  const replace = String(normalized.replaceString || "");
  const actionTag = `<${"行动选项"}>`;

  if (pattern.includes("think")) {
    return -100;
  }

  if (
    pattern.includes(actionTag) &&
    pattern.includes("statusplaceholderimpl")
  ) {
    return -60;
  }

  if (
    pattern.includes("summary") ||
    pattern.includes("statusplaceholderimpl") ||
    pattern.includes("now_plot") ||
    pattern.includes("updatevariable") ||
    pattern.includes("<update>")
  ) {
    return -50;
  }

  if (
    /<!doctype html|<html[\s>]|```html|```text|<style[\s>]|<script[\s>]/i.test(
      replace,
    )
  ) {
    return 20;
  }

  return 0;
}

function orderReaderDisplayRules(rules = []) {
  return (Array.isArray(rules) ? rules : [])
    .map((rule, index) => ({
      rule,
      index,
      bucket: getReaderDisplayRuleOrderBucket(rule, index),
    }))
    .sort(
      (left, right) => left.bucket - right.bucket || left.index - right.index,
    )
    .map((entry) => entry.rule);
}

function stripReaderControlBlocks(text) {
  let output = String(text || "");

  output = output.replace(/<disclaimer\b[^>]*>[\s\S]*?<\/disclaimer>/gi, "\n");
  output = output.replace(/(?:\n\s*){3,}/g, "\n\n");

  return output.trim();
}

function resolvePreviewBound(value, fallback) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function renderUnifiedDisplayHtmlWithoutDom(source, options = {}) {
  const text = String(source || "");
  if (!text.trim()) {
    return '<span class="chat-render-empty">空内容</span>';
  }

  const renderMode =
    options.isMarkdown === false
      ? "plain"
      : String(options.renderMode || "markdown");

  if (renderMode === "markdown") {
    return `<div class="stm-reader-scope">${escapeHtml(text)}</div>`;
  }

  if (renderMode === "literal") {
    return `<pre><code>${escapeHtml(text)}</code></pre>`;
  }

  return `<div>${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
}

export function applyUnifiedDisplayRules(text, config, options = {}) {
  let content = String(text || "");
  const sourceRules = Array.isArray(config?.displayRules)
    ? config.displayRules
    : [];
  const placement = Number(
    options.placement ?? READER_REGEX_PLACEMENT.AI_OUTPUT,
  );
  const isMarkdown = options.isMarkdown !== false;
  const isPrompt = options.isPrompt === true;
  const isEdit = options.isEdit === true;
  const readerDisplayRules = options.readerDisplayRules === true;
  const ignoreDepthLimits = options.ignoreDepthLimits === true;
  const rules = readerDisplayRules
    ? orderReaderDisplayRules(sourceRules)
    : sourceRules;
  const macroContext =
    options.macroContext && typeof options.macroContext === "object"
      ? options.macroContext
      : {};
  const depth = typeof options.depth === "number" ? options.depth : null;
  const depthInfo =
    options.depthInfo && typeof options.depthInfo === "object"
      ? options.depthInfo
      : {};
  const legacyReaderDepthMode = readerDisplayRules
    ? normalizeReaderDepthMode(options.legacyReaderDepthMode || "")
    : "";
  const normalizeDepthBound = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };
  const resolveReaderDepthValue = (mode) => {
    switch (normalizeReaderDepthMode(mode)) {
      case "anchor_abs":
        return Number.isFinite(depthInfo.anchorAbsDepth)
          ? Number(depthInfo.anchorAbsDepth)
          : null;
      case "anchor_backward":
        return Number.isFinite(depthInfo.anchorBackwardDepth)
          ? Number(depthInfo.anchorBackwardDepth)
          : null;
      case "anchor_relative":
        return Number.isFinite(depthInfo.anchorRelativeDepth)
          ? Number(depthInfo.anchorRelativeDepth)
          : null;
      default:
        return null;
    }
  };

  const filterTrimStrings = (value, trimStrings = []) => {
    let output = String(value ?? "");
    for (const trimString of trimStrings) {
      const needle = substituteDisplayRuleMacros(
        trimString || "",
        macroContext,
      );
      if (!needle) continue;
      output = output.split(needle).join("");
    }
    return output;
  };

  for (const rule of rules) {
    if (!rule || rule.deleted || rule.disabled || !rule.findRegex) continue;
    if (rule.promptOnly && !isPrompt) continue;
    if (!readerDisplayRules) {
      if (
        (rule.markdownOnly && isMarkdown) ||
        (rule.promptOnly && isPrompt) ||
        (!rule.markdownOnly && !rule.promptOnly && !isMarkdown && !isPrompt)
      ) {
        // allowed
      } else {
        continue;
      }
    }
    if (isEdit && rule.runOnEdit === false) continue;
    if (
      Array.isArray(rule.placement) &&
      rule.placement.length > 0 &&
      !rule.placement.includes(placement)
    )
      continue;
    if (!ignoreDepthLimits) {
      const minDepth = normalizeDepthBound(rule.minDepth);
      const maxDepth = normalizeDepthBound(rule.maxDepth);
      const readerDepthMode = normalizeReaderDepthMode(
        rule.readerDepthMode || rule.reader_depth_mode,
      );
      const readerMinDepth = normalizeDepthBound(
        rule.readerMinDepth ?? rule.reader_min_depth,
      );
      const readerMaxDepth = normalizeDepthBound(
        rule.readerMaxDepth ?? rule.reader_max_depth,
      );
      if (
        legacyReaderDepthMode &&
        !readerDepthMode &&
        (minDepth !== null || maxDepth !== null)
      ) {
        const legacyReaderDepth = resolveReaderDepthValue(
          legacyReaderDepthMode,
        );
        if (legacyReaderDepth === null) continue;
        if (minDepth !== null && minDepth >= -1 && legacyReaderDepth < minDepth)
          continue;
        if (maxDepth !== null && maxDepth >= 0 && legacyReaderDepth > maxDepth)
          continue;
      } else if (depth !== null) {
        if (minDepth !== null && minDepth >= -1 && depth < minDepth) continue;
        if (maxDepth !== null && maxDepth >= 0 && depth > maxDepth) continue;
      }
      if (
        readerDepthMode &&
        (readerMinDepth !== null || readerMaxDepth !== null)
      ) {
        const readerDepth = resolveReaderDepthValue(readerDepthMode);
        if (readerDepth === null) continue;
        if (readerMinDepth !== null && readerDepth < readerMinDepth) continue;
        if (readerMaxDepth !== null && readerDepth > readerMaxDepth) continue;
      }
    }
    try {
      const regex = parseDisplayRuleRegex(
        getDisplayRuleRegexSource(rule, { macroContext }),
      );
      if (!regex) continue;
      content = content.replace(regex, (...args) => {
        const replaceString = String(rule.replaceString || "").replace(
          /\{\{match\}\}/gi,
          "$0",
        );
        const lastArg = args[args.length - 1];
        const groups = lastArg && typeof lastArg === "object" ? lastArg : null;
        const captureEndIndex = groups ? args.length - 3 : args.length - 2;
        const captures = args.slice(0, captureEndIndex);

        const replaceWithGroups = replaceString.replaceAll(
          /\$(\d+)|\$<([^>]+)>|\$0/g,
          (token, num, groupName) => {
            if (token === "$0") {
              return filterTrimStrings(captures[0] ?? "", rule.trimStrings);
            }

            if (num) {
              return filterTrimStrings(
                captures[Number(num)] ?? "",
                rule.trimStrings,
              );
            }

            if (groupName) {
              return filterTrimStrings(
                groups?.[groupName] ?? "",
                rule.trimStrings,
              );
            }

            return "";
          },
        );

        return substituteDisplayRuleMacros(replaceWithGroups, macroContext);
      });
    } catch {
      continue;
    }
  }

  return readerDisplayRules ? stripReaderControlBlocks(content) : content;
}

export function buildUnifiedDisplaySource(messageText, config, options = {}) {
  if (!messageText) return "";

  let displayText = String(messageText || "");
  const normalizedPlacement = Number.isFinite(Number(options.placement))
    ? Number(options.placement)
    : READER_REGEX_PLACEMENT.AI_OUTPUT;
  const macroContext =
    options.macroContext && typeof options.macroContext === "object"
      ? options.macroContext
      : {};
  const depth = typeof options.depth === "number" ? options.depth : null;
  const depthInfo =
    options.depthInfo && typeof options.depthInfo === "object"
      ? options.depthInfo
      : null;

  displayText = displayText.replace(
    /以下是用户的本轮输入[\s\S]*?<\/本轮用户输入>/g,
    "",
  );
  const strippedDisplayText = stripCommonIndent(displayText);

  return applyUnifiedDisplayRules(strippedDisplayText, config, {
    ...options,
    placement: normalizedPlacement,
    isMarkdown: true,
    readerDisplayRules: true,
    macroContext,
    depth,
    depthInfo,
  });
}

export function renderUnifiedDisplayHtml(source, options = {}) {
  if (typeof document === "undefined") {
    return renderUnifiedDisplayHtmlWithoutDom(source, options);
  }

  const renderMode =
    options.renderMode || (options.isMarkdown === false ? "plain" : "markdown");
  return formatScopedDisplayedHtml(source, {
    scopeClass: String(options.scopeClass || "stm-reader-scope"),
    renderMode,
    speakerName: options.speakerName,
    stripSpeakerPrefix: options.stripSpeakerPrefix,
    encodeTags: options.encodeTags,
    promptBias: options.promptBias,
    hidePromptBias: options.hidePromptBias,
    reasoningMarkers: options.reasoningMarkers,
    blockMedia: options.blockMedia,
  });
}

export function buildUnifiedPreviewParts(content, options = {}) {
  const rawContent = String(content || "");
  const trimmedContent = rawContent.trim();
  if (!trimmedContent) {
    return [];
  }

  const htmlFragmentRegex =
    /^\s*<(?:div|style|details|section|article|main|link|table|script|iframe|svg|html|body|head|canvas)/i;
  const codeBlockRegex = /```(?:html|xml|text|js|css|json)?\s*([\s\S]*?)```/gi;
  const looksLikeHtmlPayload = (text) => {
    const block = String(text || "");
    return (
      block.includes("<!DOCTYPE") ||
      block.includes("<html") ||
      block.includes("<script") ||
      block.includes("export default") ||
      (block.includes("<div") && block.includes("<style"))
    );
  };

  let htmlPayload = "";
  let markdownCommentary = "";
  let match;
  let foundPayload = false;

  while ((match = codeBlockRegex.exec(rawContent)) !== null) {
    const blockContent = String(match[1] || "");
    if (!looksLikeHtmlPayload(blockContent)) {
      continue;
    }

    htmlPayload = blockContent;
    markdownCommentary = rawContent.replace(match[0], "");
    foundPayload = true;
    break;
  }

  if (!foundPayload) {
    if (
      htmlFragmentRegex.test(trimmedContent) ||
      rawContent.includes("<!DOCTYPE") ||
      rawContent.includes("<html") ||
      rawContent.includes("<script")
    ) {
      htmlPayload = rawContent;
      markdownCommentary = "";
    } else {
      markdownCommentary = rawContent;
    }
  }

  const cleanedCommentary = markdownCommentary
    .replace(/<open>|<\/open>/gi, "")
    .trim();
  const cleanedPayload = htmlPayload.replace(/<open>|<\/open>/gi, "").trim();

  const parts = [];
  if (cleanedCommentary) {
    parts.push({
      type: "markdown",
      text: cleanedCommentary,
    });
  }

  if (cleanedPayload) {
    parts.push({
      type: "app-stage",
      text: cleanedPayload,
      minHeight: resolvePreviewBound(options.minHeight, 260),
      maxHeight: resolvePreviewBound(options.maxHeight, 3200),
    });
  }

  if (!parts.length) {
    parts.push({
      type: "markdown",
      text: trimmedContent,
    });
  }

  return parts;
}
