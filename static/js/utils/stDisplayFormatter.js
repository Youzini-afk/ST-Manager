const DISALLOWED_RENDER_TAGS = new Set([
    'script',
    'iframe',
    'object',
    'embed',
    'frame',
    'frameset',
    'meta',
    'base',
]);

const CLASS_PRESERVE_PREFIXES = ['fa-', 'note-'];
const CLASS_PRESERVE_EXACT = new Set(['monospace']);
const MEDIA_TAGS = new Set(['img', 'video', 'audio', 'source', 'track']);
let domPurifyHooksInstalled = false;


function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


function renderMarkdown(text) {
    if (typeof showdown !== 'undefined' && typeof showdown.Converter === 'function') {
        const converter = new showdown.Converter({
            emoji: true,
            literalMidWordUnderscores: true,
            parseImgDimensions: true,
            tables: true,
            underline: true,
            simpleLineBreaks: true,
            strikethrough: true,
            disableForced4SpacesIndentedSublists: true,
        });
        return converter.makeHtml(String(text || ''));
    }

    if (typeof marked === 'undefined') {
        return `<div>${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
    }

    marked.setOptions({ breaks: true });
    return marked.parse(String(text || ''));
}


function wrapQuotedTextOutsideCode(text) {
    return String(text || '').replace(
        /<style>[\s\S]*?<\/style>|```[\s\S]*?```|~~~[\s\S]*?~~~|``[\s\S]*?``|`[\s\S]*?`|(".*?")|(\u201C.*?\u201D)|(\u00AB.*?\u00BB)|(\u300C.*?\u300D)|(\u300E.*?\u300F)|(\uFF02.*?\uFF02)/gim,
        (match, p1, p2, p3, p4, p5, p6) => {
            if (p1) return `<q>"${p1.slice(1, -1)}"</q>`;
            if (p2) return `<q>“${p2.slice(1, -1)}”</q>`;
            if (p3) return `<q>«${p3.slice(1, -1)}»</q>`;
            if (p4) return `<q>「${p4.slice(1, -1)}」</q>`;
            if (p5) return `<q>『${p5.slice(1, -1)}』</q>`;
            if (p6) return `<q>＂${p6.slice(1, -1)}＂</q>`;
            return match;
        },
    );
}


function preprocessDisplayText(text) {
    let output = String(text || '');
    if (!output.trim()) return '';

    output = output
        .replace(/<([^>]+)>/g, (_match, contents) => `<${String(contents || '').replace(/"/g, '\ufffe')}>`);
    output = wrapQuotedTextOutsideCode(output);
    output = output.replace(/\ufffe/g, '"');
    output = output.replaceAll('\\begin{align*}', '$$');
    output = output.replaceAll('\\end{align*}', '$$');
    return output;
}


function stripLeadingSpeakerPrefix(text, speakerName = '') {
    const name = String(speakerName || '').trim();
    if (!name) return String(text || '');

    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(text || '').replace(new RegExp(`(^|\\n)${escaped}:`, 'g'), '$1');
}


function escapeReasoningMarkers(text, markers = []) {
    let output = String(text || '');
    markers.forEach((marker) => {
        const value = String(marker || '').trim();
        if (!value) return;
        if (output.includes(value)) {
            output = output.replace(value, escapeHtml(value));
        }
    });
    return output;
}


function encodeAngleTags(text) {
    return String(text || '').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}


function stripPromptBias(text, promptBias = '') {
    const content = String(text || '');
    const bias = String(promptBias || '');
    if (!bias || !content.startsWith(bias)) {
        return content;
    }
    return content.slice(bias.length);
}


function encodeStyleTags(html) {
    return String(html || '').replace(/<style\b[^>]*>([\s\S]*?)<\/style>/gi, (_match, cssText) => {
        return `<custom-style>${encodeURIComponent(String(cssText || ''))}</custom-style>`;
    });
}


function preserveInlineHtmlBlocks(text) {
    const placeholders = [];
    let index = 0;
    const source = String(text || '');
    const codeRegex = /```[\s\S]*?```|~~~[\s\S]*?~~~|``[\s\S]*?``|`[^`]*`/gim;
    const htmlRegex = /<(style|details|summary|div|section|article|main|table|thead|tbody|tr|td|th|img|blockquote)\b[\s\S]*?(?:<\/\1>|\/>)/gi;

    const replaceHtmlBlocks = (segment) => String(segment || '').replace(htmlRegex, (match) => {
        const token = `STHTMLBLOCKTOKEN${index}TOKEN`;
        placeholders.push({ token, value: match });
        index += 1;
        return token;
    });

    let protectedText = '';
    let lastIndex = 0;
    let match;

    while ((match = codeRegex.exec(source)) !== null) {
        protectedText += replaceHtmlBlocks(source.slice(lastIndex, match.index));
        protectedText += match[0];
        lastIndex = match.index + match[0].length;
    }

    protectedText += replaceHtmlBlocks(source.slice(lastIndex));
    return { protectedText, placeholders };
}


function restoreInlineHtmlBlocks(text, placeholders = []) {
    let output = String(text || '');
    placeholders.forEach(({ token, value }) => {
        output = output.split(token).join(value);
    });
    return output;
}


function postProcessMarkdownHtml(html) {
    let output = String(html || '');
    output = output.replace(/<code(.*)>[\s\S]*?<\/code>/g, (match) => match.replace(/\n/gm, '\u0000'));
    output = output.replace(/\u0000/g, '\n');
    output = output.trim();
    output = output.replace(/<code(.*)>[\s\S]*?<\/code>/g, (match) => match.replace(/&amp;/g, '&'));
    return output;
}


function installDomPurifyHooks() {
    if (domPurifyHooksInstalled || typeof DOMPurify === 'undefined' || typeof DOMPurify.addHook !== 'function') {
        return;
    }

    domPurifyHooksInstalled = true;

    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
        if (node && 'target' in node) {
            node.setAttribute('target', '_blank');
            node.setAttribute('rel', 'noopener');
        }
    });

    DOMPurify.addHook('uponSanitizeAttribute', (node, data, config) => {
        if (!config || !config.MESSAGE_SANITIZE) {
            return;
        }

        if (data.attrName === 'class' && data.attrValue) {
            data.attrValue = data.attrValue
                .split(' ')
                .filter(Boolean)
                .map((token) => {
                    if (CLASS_PRESERVE_EXACT.has(token) || CLASS_PRESERVE_PREFIXES.some(prefix => token.startsWith(prefix))) {
                        return token;
                    }
                    return token.startsWith('custom-') ? token : `custom-${token}`;
                })
                .join(' ');
        }
    });

    DOMPurify.addHook('uponSanitizeElement', (node, _data, config) => {
        if (!config || !config.MESSAGE_SANITIZE) {
            return;
        }

        if (typeof HTMLUnknownElement !== 'undefined' && node instanceof HTMLUnknownElement) {
            node.innerHTML = node.innerHTML.trim();

            const candidates = [];
            const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const textNode = walker.currentNode;
                if (!(textNode instanceof Text) || !textNode.data.includes('\n')) continue;
                if (textNode.parentElement && textNode.parentElement.closest('pre')) continue;
                candidates.push(textNode);
            }

            for (const textNode of candidates) {
                const parts = textNode.data.split('\n');
                const fragment = document.createDocumentFragment();
                parts.forEach((part, index) => {
                    if (part.length) {
                        fragment.appendChild(document.createTextNode(part));
                    }
                    if (index < parts.length - 1) {
                        fragment.appendChild(document.createElement('br'));
                    }
                });
                textNode.replaceWith(fragment);
            }
        }
    });
}


function sanitizeRenderedHtml(html) {
    if (typeof DOMPurify !== 'undefined' && typeof DOMPurify.sanitize === 'function') {
        installDomPurifyHooks();
        return DOMPurify.sanitize(String(html || ''), {
            RETURN_DOM: false,
            RETURN_DOM_FRAGMENT: false,
            RETURN_TRUSTED_TYPE: false,
            ADD_TAGS: ['custom-style'],
            MESSAGE_SANITIZE: true,
        });
    }

    const template = document.createElement('template');
    template.innerHTML = String(html || '');

    const queue = Array.from(template.content.children);
    while (queue.length > 0) {
        const element = queue.shift();
        if (!(element instanceof Element)) continue;

        if (DISALLOWED_RENDER_TAGS.has(element.tagName.toLowerCase())) {
            element.remove();
            continue;
        }

        if (MEDIA_TAGS.has(element.tagName.toLowerCase()) && ['http:', 'https:'].some(prefix => String(element.getAttribute('src') || '').startsWith(prefix))) {
            element.remove();
            continue;
        }

        Array.from(element.attributes).forEach((attribute) => {
            const name = String(attribute.name || '').toLowerCase();
            const value = String(attribute.value || '');

            if (name === 'class') {
                const nextClassName = value
                    .split(/\s+/)
                    .filter(Boolean)
                    .map((token) => {
                        if (CLASS_PRESERVE_EXACT.has(token) || CLASS_PRESERVE_PREFIXES.some(prefix => token.startsWith(prefix))) {
                            return token;
                        }
                        if (token.startsWith('custom-')) {
                            return token;
                        }
                        return `custom-${token}`;
                    })
                    .join(' ');

                if (nextClassName) {
                    element.setAttribute(attribute.name, nextClassName);
                } else {
                    element.removeAttribute(attribute.name);
                }
                return;
            }

            if (name.startsWith('on')) {
                element.removeAttribute(attribute.name);
                return;
            }

            if (['href', 'src', 'xlink:href', 'formaction'].includes(name) && /^\s*javascript:/i.test(value)) {
                element.setAttribute(attribute.name, '#');
            }
        });

        if (element.tagName.toLowerCase() === 'a' && element.getAttribute('target') === '_blank') {
            element.setAttribute('rel', 'noopener');
        }

        queue.push(...Array.from(element.children));
    }

    return template.innerHTML;
}


function splitSelectors(selectorText) {
    const selectors = [];
    let current = '';
    let depth = 0;

    for (const char of String(selectorText || '')) {
        if (char === '(' || char === '[') {
            depth += 1;
        } else if ((char === ')' || char === ']') && depth > 0) {
            depth -= 1;
        }

        if (char === ',' && depth === 0) {
            selectors.push(current.trim());
            current = '';
            continue;
        }

        current += char;
    }

    if (current.trim()) {
        selectors.push(current.trim());
    }

    return selectors;
}


function sanitizeSimpleSelector(selector) {
    return String(selector || '')
        .split(/\s+/)
        .map((part) => part.replace(/\.([\w-]+)/g, (match, className) => {
            if (className.startsWith('custom-')) {
                return match;
            }
            return `.custom-${className}`;
        }))
        .join(' ');
}


function sanitizeSelector(selector) {
    const pseudoClasses = ['has', 'not', 'where', 'is', 'matches', 'any'];
    const pseudoRegex = new RegExp(`:(${pseudoClasses.join('|')})\\(([^)]+)\\)`, 'g');

    const nestedSanitized = String(selector || '').replace(pseudoRegex, (_match, pseudoClass, content) => {
        return `:${pseudoClass}(${sanitizeSimpleSelector(content)})`;
    });

    return sanitizeSimpleSelector(nestedSanitized);
}


function scopeSingleSelector(selector, scopeSelector) {
    let normalized = sanitizeSelector(selector).trim();
    if (!normalized) {
        return scopeSelector;
    }

    if (normalized.includes(scopeSelector)) {
        return normalized;
    }

    return `${scopeSelector} ${normalized}`;
}


function scopeCssRule(rule, scopeSelector) {
    if (!rule) return '';

    const supportsRuleType = typeof CSSRule !== 'undefined' && typeof CSSRule.SUPPORTS_RULE === 'number'
        ? CSSRule.SUPPORTS_RULE
        : -1;
    const mediaRuleType = typeof CSSRule !== 'undefined' && typeof CSSRule.MEDIA_RULE === 'number'
        ? CSSRule.MEDIA_RULE
        : 4;
    const styleRuleType = typeof CSSRule !== 'undefined' && typeof CSSRule.STYLE_RULE === 'number'
        ? CSSRule.STYLE_RULE
        : 1;
    const importRuleType = typeof CSSRule !== 'undefined' && typeof CSSRule.IMPORT_RULE === 'number'
        ? CSSRule.IMPORT_RULE
        : 3;

    switch (rule.type) {
        case styleRuleType: {
            const selectors = splitSelectors(rule.selectorText)
                .map(selector => scopeSingleSelector(selector, scopeSelector))
                .join(', ');
            return `${selectors} { ${rule.style.cssText} }`;
        }
        case mediaRuleType: {
            const nested = Array.from(rule.cssRules || [])
                .map(item => scopeCssRule(item, scopeSelector))
                .filter(Boolean)
                .join('\n');
            return nested ? `@media ${rule.conditionText} {\n${nested}\n}` : '';
        }
        case supportsRuleType: {
            const nested = Array.from(rule.cssRules || [])
                .map(item => scopeCssRule(item, scopeSelector))
                .filter(Boolean)
                .join('\n');
            return nested ? `@supports ${rule.conditionText} {\n${nested}\n}` : '';
        }
        case importRuleType:
            return '';
        default:
            return rule.cssText || '';
    }
}


function naiveScopeCssText(cssText, scopeSelector) {
    return String(cssText || '')
        .split('}')
        .map((chunk) => {
            const [rawSelectors, rawBody] = chunk.split('{');
            if (!rawSelectors || !rawBody) return '';
            const selectors = splitSelectors(rawSelectors)
                .map(selector => scopeSingleSelector(selector, scopeSelector))
                .join(', ');
            return `${selectors} { ${rawBody.trim()} }`;
        })
        .filter(Boolean)
        .join('\n');
}


function scopeCssText(cssText, scopeSelector) {
    const source = String(cssText || '').trim();
    if (!source) return '';

    try {
        const doc = document.implementation.createHTMLDocument('');
        const style = doc.createElement('style');
        style.textContent = source;
        doc.head.appendChild(style);
        const sheet = style.sheet;
        const cssRules = sheet ? Array.from(sheet.cssRules || []) : [];
        if (!cssRules.length) {
            return naiveScopeCssText(source, scopeSelector);
        }
        return cssRules.map(rule => scopeCssRule(rule, scopeSelector)).filter(Boolean).join('\n');
    } catch {
        return naiveScopeCssText(source, scopeSelector);
    }
}


function decodeScopedStyleTags(html, scopeSelector) {
    const template = document.createElement('template');
    template.innerHTML = String(html || '');

    Array.from(template.content.querySelectorAll('custom-style')).forEach((node) => {
        const encoded = node.textContent || '';
        let decoded = '';
        try {
            decoded = decodeURIComponent(encoded);
        } catch {
            decoded = encoded;
        }

        const scopedCss = scopeCssText(decoded, scopeSelector);
        if (!scopedCss.trim()) {
            node.remove();
            return;
        }

        const style = document.createElement('style');
        style.textContent = scopedCss;
        node.replaceWith(style);
    });

    return template.innerHTML;
}


export function formatScopedDisplayedHtml(source, options = {}) {
    const text = String(source || '');
    if (!text.trim()) {
        return '<span class="chat-render-empty">空内容</span>';
    }

    const scopeClass = String(options.scopeClass || 'stm-reader-scope');
    const scopeSelector = `.${scopeClass}`;
    const renderMode = options.renderMode === 'plain' ? 'plain' : 'markdown';
    const speakerName = String(options.speakerName || '');
    const stripSpeakerPrefix = options.stripSpeakerPrefix === true;
    const encodeTags = options.encodeTags === true;
    const promptBias = String(options.promptBias || '');
    const hidePromptBias = options.hidePromptBias === true;
    const reasoningMarkers = Array.isArray(options.reasoningMarkers) ? options.reasoningMarkers : [];

    let preparedText = text;

    if (hidePromptBias) {
        preparedText = stripPromptBias(preparedText, promptBias);
    }

    preparedText = escapeReasoningMarkers(preparedText, reasoningMarkers);

    if (encodeTags) {
        preparedText = encodeAngleTags(preparedText);
    }

    preparedText = renderMode === 'markdown'
        ? preprocessDisplayText(preparedText)
        : preparedText;

    const finalText = stripSpeakerPrefix
        ? stripLeadingSpeakerPrefix(preparedText, speakerName)
        : preparedText;

    const renderedHtml = renderMode === 'markdown'
        ? (() => {
            const { protectedText, placeholders } = preserveInlineHtmlBlocks(finalText);
            const html = renderMarkdown(protectedText);
            return postProcessMarkdownHtml(restoreInlineHtmlBlocks(html, placeholders));
        })()
        : `<div>${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;

    const encodedStyles = encodeStyleTags(renderedHtml);
    const sanitizedHtml = sanitizeRenderedHtml(encodedStyles);
    return decodeScopedStyleTags(sanitizedHtml, scopeSelector);
}
