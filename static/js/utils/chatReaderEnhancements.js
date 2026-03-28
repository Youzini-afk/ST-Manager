function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


function stripHtml(text) {
    return String(text || '').replace(/<[^>]+>/g, ' ');
}


function normalizeWhitespace(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
}


function buildPreview(text, maxLength = 140) {
    const normalized = normalizeWhitespace(text);
    if (!normalized) return '';
    if (normalized.length <= maxLength) return normalized;
    return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}...`;
}


function pickFirstNonEmpty(candidates) {
    for (const candidate of candidates) {
        if (typeof candidate === 'string' && candidate.trim()) {
            return candidate.trim();
        }
    }
    return '';
}


function collectReasoningCandidates(rawMessage = null, message = null) {
    const raw = rawMessage && typeof rawMessage === 'object' ? rawMessage : {};
    const parsed = message && typeof message === 'object' ? message : {};
    const extra = raw.extra && typeof raw.extra === 'object' ? raw.extra : {};
    const parsedExtra = parsed.extra && typeof parsed.extra === 'object' ? parsed.extra : {};

    return [
        extra.reasoning,
        parsedExtra.reasoning,
        raw.reasoning_content,
        parsed.reasoning_content,
        raw.reasoning,
        parsed.reasoning,
        raw.thinking,
        parsed.thinking,
        raw.thoughts,
        parsed.thoughts,
        raw.cot,
        parsed.cot,
    ];
}


function extractTaggedReasoning(text) {
    const source = String(text || '');
    if (!source) return '';

    const match = source.match(/<(think|thinking)\b[^>]*>([\s\S]*?)<\/\1>/i);
    return match ? String(match[2] || '').trim() : '';
}


function collectBodyCandidates(rawMessage = null, message = null) {
    const raw = rawMessage && typeof rawMessage === 'object' ? rawMessage : {};
    const parsed = message && typeof message === 'object' ? message : {};
    return [
        parsed.content,
        parsed.mes,
        raw.content,
        raw.mes,
        raw.message,
        raw.text,
    ];
}


function countRenderedLines(text) {
    return String(text || '').replace(/\r\n/g, '\n').split('\n').length;
}


function analyzeCodeBlocks(text) {
    const source = String(text || '');
    const matches = [...source.matchAll(/```(?:[\w+-]+)?\s*\n?([\s\S]*?)```/g)];
    const codeBlocks = matches.map(match => String(match[1] || ''));
    const longestLines = codeBlocks.reduce((max, block) => Math.max(max, countRenderedLines(block)), 0);
    return {
        codeBlockCount: codeBlocks.length,
        hasLongCode: longestLines >= 12,
    };
}


function detectRuntimeCandidate(text) {
    return /<(script|style|iframe|canvas|svg)\b|\b(import\s+React|export\s+default|function\s+App\b|document\.|window\.|fetch\()/i.test(String(text || ''));
}


function resolveViewportPreviewLines(options = {}) {
    const width = Number(options.viewportWidth || options.width || 0);
    if (Number.isFinite(width) && width > 0 && width <= 720) {
        return 6;
    }
    return 8;
}


function analyzeRenderedCodeBlock(codeBody) {
    const plainCode = stripHtml(codeBody)
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&');
    const lines = String(plainCode || '').replace(/\r\n/g, '\n').split('\n');
    return {
        plainCode,
        lines,
        totalLines: lines.length,
    };
}


function resolveEffectiveCodePolicy(renderedHtml, metadata, policy) {
    const sourceHtml = String(renderedHtml || '');
    const safeMetadata = metadata && typeof metadata === 'object' ? metadata : {};
    const safePolicy = policy && typeof policy === 'object' ? { ...policy } : {};
    const collapseThreshold = Number(safePolicy.codeCollapseThreshold || 12);
    const hasLongRenderedPre = /<pre><code>[\s\S]*?<\/code><\/pre>/i.test(sourceHtml)
        && sourceHtml.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/gi, (_match, codeBody) => {
            const analysis = analyzeRenderedCodeBlock(codeBody);
            return analysis.totalLines >= collapseThreshold ? '__LONG_PRE__' : '';
        }).includes('__LONG_PRE__');

    if (hasLongRenderedPre && !safeMetadata.hasLongCode) {
        if (safePolicy.codeMode === 'none') {
            safePolicy.codeMode = safePolicy.renderTier === 'simple' ? 'preview' : 'collapse';
        }
        if (Array.isArray(safePolicy.metaFlags) && !safePolicy.metaFlags.includes('code')) {
            safePolicy.metaFlags = [...safePolicy.metaFlags, 'code'];
        }
    }

    return safePolicy;
}


function buildReasoningMarkerLabel(metadata) {
    if (String(metadata?.reasoningState || '') === 'missing') {
        return 'Reasoning missing body';
    }
    return 'Reasoning';
}


function wrapReasoningDisclosure(metadata, policy, options = {}) {
    if (!metadata?.hasReasoning || policy?.reasoningMode === 'none') {
        return '';
    }

    const isMissing = String(metadata.reasoningState || '') === 'missing';
    const shouldOpen = Boolean(policy?.reasoningStartExpanded ?? options.reasoningStartExpanded);
    const summaryLabel = 'Reasoning';

    if (isMissing || policy?.reasoningMode === 'marker') {
        const markerLabel = escapeHtml(buildReasoningMarkerLabel(metadata));
        return [
            '<div class="chat-message-meta-flags">',
            '<span class="chat-message-meta-flag chat-message-meta-flag--reasoning">',
            markerLabel,
            '</span>',
            '</div>',
        ].join('');
    }

    const body = escapeHtml(metadata.reasoningText || '').replace(/\n/g, '<br>');
    if (!body) return '';

    return [
        `<details class="chat-message-reasoning"${shouldOpen ? ' open' : ''}>`,
        `<summary class="chat-message-reasoning-summary">${summaryLabel}</summary>`,
        `<div class="chat-message-reasoning-body">${body}</div>`,
        '</details>',
    ].join('');
}


function buildCodePreviewHtml(renderedHtml, policy) {
    const source = String(renderedHtml || '');
    if (!source || policy?.codeMode !== 'preview') {
        return source;
    }

    return source.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/gi, (match, codeBody) => {
        const analysis = analyzeRenderedCodeBlock(codeBody);
        const lines = analysis.lines;
        const previewLineCount = Math.max(1, Number(policy.codePreviewLines || 6));
        if (lines.length <= previewLineCount) {
            return match;
        }

        const previewText = escapeHtml(lines.slice(0, previewLineCount).join('\n'));
        return [
            '<div class="chat-message-code-collapse chat-message-code-collapse--preview">',
            `<div class="chat-message-code-collapse-toggle">长代码预览 · 前 ${previewLineCount} 行 / 共 ${lines.length} 行</div>`,
            `<pre><code>${previewText}</code></pre>`,
            '</div>',
        ].join('');
    });
}


function collapseLongCodeBlocks(renderedHtml, policy) {
    const source = String(renderedHtml || '');
    if (!source || policy?.codeMode !== 'collapse') {
        return source;
    }

    return source.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/gi, (match, codeBody) => {
        const analysis = analyzeRenderedCodeBlock(codeBody);
        const totalLines = analysis.totalLines;
        if (totalLines < Number(policy.codeCollapseThreshold || 12)) {
            return match;
        }

        return [
            '<details class="chat-message-code-collapse">',
            `<summary class="chat-message-code-collapse-toggle">代码已折叠 · ${totalLines} 行</summary>`,
            match,
            '</details>',
        ].join('');
    });
}


function renderMetaFlags(metadata, policy) {
    const flags = Array.isArray(policy?.metaFlags) ? policy.metaFlags : [];
    if (!flags.length) return '';

    const renderedFlags = [];
    if (flags.includes('reasoning') && metadata?.hasReasoning && policy?.reasoningMode !== 'marker') {
        const label = buildReasoningMarkerLabel(metadata);
        renderedFlags.push(`<span class="chat-message-meta-flag chat-message-meta-flag--reasoning">${escapeHtml(label)}</span>`);
    }
    if (flags.includes('code') && metadata?.hasLongCode) {
        renderedFlags.push('<span class="chat-message-meta-flag chat-message-meta-flag--code">长代码</span>');
    }
    if (flags.includes('runtime') && metadata?.hasRuntimeCandidate) {
        renderedFlags.push('<span class="chat-message-meta-flag chat-message-meta-flag--runtime">运行时片段</span>');
    }
    if (!renderedFlags.length) return '';

    return `<div class="chat-message-meta-flags">${renderedFlags.join('')}</div>`;
}


export function extractReaderEnhancementMetadata(rawMessage = null, message = null) {
    const reasoningCandidates = collectReasoningCandidates(rawMessage, message);
    const reasoningText = pickFirstNonEmpty(reasoningCandidates);
    const taggedReasoning = reasoningText
        ? ''
        : pickFirstNonEmpty(collectBodyCandidates(rawMessage, message).map(extractTaggedReasoning));
    const finalReasoningText = reasoningText || taggedReasoning;
    const hasReasoningMarker = reasoningCandidates.some(candidate => candidate !== undefined && candidate !== null && candidate !== '');
    const hasReasoningFromTags = Boolean(taggedReasoning);
    const hasReasoning = Boolean(finalReasoningText || hasReasoningMarker || hasReasoningFromTags);
    let reasoningState = 'none';
    if (hasReasoning) {
        if (finalReasoningText) {
            reasoningState = 'available';
        } else {
            reasoningState = 'missing';
        }
    }

    const contentSource = pickFirstNonEmpty(collectBodyCandidates(rawMessage, message));
    const codeAnalysis = analyzeCodeBlocks(contentSource);

    return {
        hasReasoning,
        reasoningText: finalReasoningText,
        reasoningPreview: buildPreview(finalReasoningText || '包含 reasoning', 120),
        reasoningState,
        hasLongCode: codeAnalysis.hasLongCode,
        hasRuntimeCandidate: detectRuntimeCandidate(contentSource),
        codeBlockCount: codeAnalysis.codeBlockCount,
    };
}


export function buildReaderEnhancementPolicy(renderTier, metadata, options = {}) {
    const tier = String(renderTier || 'hidden').trim() || 'hidden';
    const sourceMetadata = metadata && typeof metadata === 'object' ? metadata : {};
    const previewLines = resolveViewportPreviewLines(options);
    const collapseThreshold = 12;
    const autoCollapseLongCode = options.autoCollapseLongCode !== false;

    if (tier === 'full') {
        return {
            renderTier: tier,
            reasoningMode: sourceMetadata.hasReasoning ? 'full' : 'none',
            codeMode: sourceMetadata.hasLongCode && autoCollapseLongCode ? 'collapse' : 'full',
            showMetaFlags: false,
            metaFlags: [],
            codePreviewLines: previewLines,
            codeCollapseThreshold: collapseThreshold,
            reasoningStartExpanded: options.reasoningDefaultCollapsed === false,
        };
    }

    if (tier === 'simple') {
        return {
            renderTier: tier,
            reasoningMode: sourceMetadata.hasReasoning ? 'marker' : 'none',
            codeMode: sourceMetadata.hasLongCode ? 'preview' : 'none',
            showMetaFlags: true,
            metaFlags: ['reasoning', 'code', 'runtime'],
            codePreviewLines: Math.min(previewLines, 6),
            codeCollapseThreshold: collapseThreshold,
            reasoningStartExpanded: false,
        };
    }

    if (tier === 'compact') {
        return {
            renderTier: tier,
            reasoningMode: sourceMetadata.hasReasoning ? 'summary' : 'none',
            codeMode: sourceMetadata.hasLongCode ? 'summary' : 'none',
            showMetaFlags: true,
            metaFlags: ['reasoning', 'code'],
            codePreviewLines: Math.min(previewLines, 4),
            codeCollapseThreshold: collapseThreshold,
            reasoningStartExpanded: false,
        };
    }

    return {
        renderTier: tier,
        reasoningMode: 'none',
        codeMode: 'none',
        showMetaFlags: false,
        metaFlags: [],
        codePreviewLines: previewLines,
        codeCollapseThreshold: collapseThreshold,
        reasoningStartExpanded: false,
    };
}


export function decorateReaderRenderedHtml(renderedHtml, metadata, policy, options = {}) {
    const sourceHtml = String(renderedHtml || '');
    const safeMetadata = metadata && typeof metadata === 'object' ? metadata : {};
    const basePolicy = policy && typeof policy === 'object' ? policy : buildReaderEnhancementPolicy('hidden', safeMetadata, options);
    const safePolicy = resolveEffectiveCodePolicy(sourceHtml, safeMetadata, basePolicy);

    const reasoningHtml = wrapReasoningDisclosure(safeMetadata, safePolicy, options);
    const previewedHtml = buildCodePreviewHtml(sourceHtml, safePolicy);
    const codeHtml = collapseLongCodeBlocks(previewedHtml, safePolicy);
    const metaFlagsHtml = renderMetaFlags(safeMetadata, safePolicy);

    return `${reasoningHtml}${metaFlagsHtml}${codeHtml}`;
}
