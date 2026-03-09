/**
 * static/js/utils/dom.js
 * DOM 操作与渲染工具
 */

const htmlComponentRenderCache = new WeakMap();
let renderRuntimeModule = null;
let renderRuntimeModulePromise = null;

function loadRenderRuntimeModule() {
    if (renderRuntimeModule) {
        return Promise.resolve(renderRuntimeModule);
    }

    if (!renderRuntimeModulePromise) {
        renderRuntimeModulePromise = import('../runtime/renderRuntime.js')
            .then((module) => {
                renderRuntimeModule = module;
                return module;
            })
            .catch((error) => {
                renderRuntimeModulePromise = null;
                console.warn('Failed to load render runtime module:', error);
                throw error;
            });
    }

    return renderRuntimeModulePromise;
}

export function clearInlineIsolatedHtml(el, options = {}) {
    if (!el || !renderRuntimeModule?.clearIsolatedHtml) {
        return;
    }
    renderRuntimeModule.clearIsolatedHtml(el, options);
}

function buildHtmlComponentSignature(content, options = {}) {
    return JSON.stringify({
        content: String(content || ''),
        minHeight: Number.parseInt(options.minHeight, 10) || 0,
        maxHeight: Number.parseInt(options.maxHeight, 10) || 0,
        mode: String(options.mode || 'html-component'),
        assetBase: String(options.assetBase || ''),
    });
}

export function updateCssVariable(name, value) {
    document.documentElement.style.setProperty(name, value);
}

export function applyFont(type) {
    let fontVal = 'ui-sans-serif, system-ui, sans-serif';
    if (type === 'serif') fontVal = 'ui-serif, Georgia, Cambria, "Times New Roman", Times, serif';
    if (type === 'mono') fontVal = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
    updateCssVariable('--app-font-family', fontVal);
}

export function insertAtCursor(textarea, myValue) {
    if (textarea.selectionStart || textarea.selectionStart == '0') {
        var startPos = textarea.selectionStart;
        var endPos = textarea.selectionEnd;
        return textarea.value.substring(0, startPos)
            + myValue
            + textarea.value.substring(endPos, textarea.value.length);
    } else {
        return textarea.value + myValue;
    }
}


function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function renderMarkdown(text) {
    if (!text) return '<span class="text-gray-500 italic">空内容</span>';
    let safeText = String(text);
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true });
        try {
            return marked.parse(safeText);
        } catch (e) {
            console.error("Markdown parse error:", e);
            return safeText;
        }
    }
    return safeText;
}

export function updateInlineRenderContent(el, content, options = {}) {
    if (!el) return;

    const rawContent = String(content || '');
    const trimmed = rawContent.trim();
    const mode = options.mode || 'markdown';
    const isolated = Boolean(options.isolated);
    const emptyHtml = options.emptyHtml || '<span class="text-gray-500 italic">空内容</span>';

    if (!trimmed) {
        htmlComponentRenderCache.delete(el);
        clearInlineIsolatedHtml(el);
        if (el.shadowRoot) {
            el.shadowRoot.innerHTML = `<div>${emptyHtml}</div>`;
        } else {
            el.innerHTML = emptyHtml;
        }
        return;
    }

    if (mode === 'html-component') {
        const signature = buildHtmlComponentSignature(rawContent, options);
        if (htmlComponentRenderCache.get(el) === signature) {
            return;
        }
        htmlComponentRenderCache.set(el, signature);
        if (!el.shadowRoot) {
            el.attachShadow({ mode: 'open' });
        }
        updateShadowContent(el, rawContent, options);
        return;
    }

    htmlComponentRenderCache.delete(el);
    clearInlineIsolatedHtml(el);

    const rendered = mode === 'markdown'
        ? renderMarkdown(rawContent)
        : `<div>${escapeHtml(rawContent).replace(/\n/g, '<br>')}</div>`;

    if (isolated && !el.shadowRoot) {
        el.attachShadow({ mode: 'open' });
    }

    if (el.shadowRoot) {
        el.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    color: inherit;
                }
                .inline-render {
                    display: block;
                    color: inherit;
                    min-width: 0;
                    overflow-wrap: anywhere;
                    word-break: break-word;
                }
                .inline-render img {
                    max-width: 100%;
                    height: auto;
                }
                .inline-render pre {
                    white-space: pre-wrap;
                    word-break: break-word;
                }
            </style>
            <div class="inline-render markdown-body">${rendered}</div>
        `;
        return;
    }

    el.innerHTML = rendered;
}

export function updateShadowContent(el, content, options = {}) {
    if (!el.shadowRoot) {
        el.attachShadow({ mode: 'open' });
    }

    const shadow = el.shadowRoot;
    const minHeight = Number.parseInt(options.minHeight, 10);
    const hostMinHeight = Number.isFinite(minHeight) ? `${Math.max(0, minHeight)}px` : '0px';
    const maxHeight = Number.parseInt(options.maxHeight, 10);
    const hostMaxHeight = Number.isFinite(maxHeight) ? `${Math.max(0, maxHeight)}px` : 'none';

    if (content === null || content === undefined) {
        htmlComponentRenderCache.delete(el);
        clearInlineIsolatedHtml(el);
        shadow.innerHTML = '';
        return;
    }

    let rawContent = content || "";
    const trimmedContent = rawContent.trim();

    const htmlFragmentRegex = /^\s*<(?:div|style|details|section|article|main|link|table|script|iframe|svg|html|body|head|canvas)/i;
    let forceHtmlMode = false;

    if (htmlFragmentRegex.test(trimmedContent)) {
        forceHtmlMode = true;
    }

    let htmlPayload = "";
    let markdownCommentary = "";

    const codeBlockRegex = /```(?:html|xml|text|js|css|json)?\s*([\s\S]*?)```/gi;
    let match;
    let foundPayload = false;

    while ((match = codeBlockRegex.exec(rawContent)) !== null) {
        const blockContent = match[1];
        if (blockContent.includes('<!DOCTYPE') ||
            blockContent.includes('<html') ||
            blockContent.includes('<script') ||
            blockContent.includes('export default') ||
            (blockContent.includes('<div') && blockContent.includes('<style'))) {

            htmlPayload = blockContent;
            markdownCommentary = rawContent.replace(match[0], "");
            foundPayload = true;
            break;
        }
    }

    if (!foundPayload) {
        if (forceHtmlMode || rawContent.includes('<!DOCTYPE') || rawContent.includes('<html') || rawContent.includes('<script')) {
            htmlPayload = rawContent;
            markdownCommentary = "";
        } else {
            markdownCommentary = rawContent;
        }
    }

    markdownCommentary = markdownCommentary.replace(/<open>|<\/open>/gi, "").trim();

    const hasPayload = !!htmlPayload;

    if (hasPayload) {
        let renderedMd = "";
        if (markdownCommentary) {
            const looksLikeTrustedHtml = /^\s*<(?:[a-z][\w:-]*|!doctype|!--)/i.test(markdownCommentary);
            if (looksLikeTrustedHtml) {
                renderedMd = markdownCommentary;
            } else if (typeof marked !== 'undefined') {
                renderedMd = marked.parse(markdownCommentary, { breaks: true });
            } else {
                renderedMd = `<p>${markdownCommentary.replace(/\n/g, "<br>")}</p>`;
            }
        }
        loadRenderRuntimeModule()
            .then((module) => {
                module.renderIsolatedHtml(el, {
                    htmlPayload,
                    noteHtml: renderedMd,
                    minHeight: Number.parseInt(options.minHeight, 10),
                    maxHeight: Number.parseInt(options.maxHeight, 10),
                    assetBase: options.assetBase || '',
                });
            })
            .catch(() => {
                shadow.innerHTML = `<div class="scroll-wrapper markdown-body">运行时模块加载失败，无法渲染 HTML 预览。</div>`;
            });
        return;
    }

    clearInlineIsolatedHtml(el);

    const style = `
                <style>
                    :host {
                        display: block;
                        min-height: ${hostMinHeight};
                        max-height: ${hostMaxHeight};
                        width: 100%;
                        overflow: visible;
                        background-color: transparent;
                        color: var(--text-main, #e5e7eb);
                        font-family: ui-sans-serif, system-ui, sans-serif;
                        font-size: 0.9rem;
                        line-height: 1.6;
                    }
                    .scroll-wrapper {
                        min-height: ${hostMinHeight};
                        max-height: ${hostMaxHeight};
                        width: 100%;
                        overflow: visible;
                        padding: 1rem;
                        box-sizing: border-box;
                    }
                    img { max-width: 100%; border-radius: 4px; }
                    a { color: var(--accent-main, #2563eb); }
                    blockquote { border-left: 4px solid var(--accent-main, #2563eb); padding-left: 1em; margin: 1em 0; opacity: 0.8; }
                    /* 代码块样式修复 */
                    pre { background: rgba(0,0,0,0.3); padding: 1em; border-radius: 6px; overflow-x: auto; }
                    code { font-family: monospace; }
                </style>
            `;

    const looksLikeTrustedHtml = /^\s*<(?:[a-z][\w:-]*|!doctype|!--)/i.test(rawContent);

    let renderedHtml = rawContent;
    if (looksLikeTrustedHtml) {
        renderedHtml = rawContent;
    } else if (typeof marked !== 'undefined') {
        renderedHtml = marked.parse(rawContent || "", { breaks: true });
    } else {
        renderedHtml = (rawContent || "").replace(/\n/g, "<br>");
    }

    const htmlWrapper = renderedHtml || '<div style="color: gray; font-style: italic;">空内容</div>';
    shadow.innerHTML = style + `<div class="scroll-wrapper markdown-body">${htmlWrapper}</div>`;
}
