import json
from pathlib import Path
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]
UNIFIED_PREVIEW_MODULE = ROOT / 'static/js/utils/unifiedTextPreview.js'
MESSAGE_SEGMENT_RENDERER_MODULE = ROOT / 'static/js/runtime/messageSegmentRenderer.js'
DOM_UTILS_MODULE = ROOT / 'static/js/utils/dom.js'


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def get_unified_preview_module_path() -> Path:
    assert UNIFIED_PREVIEW_MODULE.exists(), (
        'expected shared unified preview module at '
        'static/js/utils/unifiedTextPreview.js'
    )
    return UNIFIED_PREVIEW_MODULE.resolve()


def get_message_segment_renderer_module_path() -> Path:
    assert MESSAGE_SEGMENT_RENDERER_MODULE.exists(), (
        'expected message segment renderer module at '
        'static/js/runtime/messageSegmentRenderer.js'
    )
    return MESSAGE_SEGMENT_RENDERER_MODULE.resolve()


def get_dom_utils_module_path() -> Path:
    assert DOM_UTILS_MODULE.exists(), (
        'expected dom utils module at '
        'static/js/utils/dom.js'
    )
    return DOM_UTILS_MODULE.resolve()


def run_unified_preview_runtime_check(script_body: str) -> None:
    source_path = get_unified_preview_module_path()
    node_script = textwrap.dedent(
        f'''
        import {{ pathToFileURL }} from 'node:url';

        const sourcePath = {json.dumps(str(source_path))};
        const module = await import(pathToFileURL(sourcePath).href);

        {textwrap.dedent(script_body)}
        '''
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def run_message_segment_renderer_runtime_check(script_body: str) -> None:
    source_path = get_message_segment_renderer_module_path()
    node_script = textwrap.dedent(
        f'''
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source
          .split('\\n')
          .filter((line) => !line.trim().startsWith('import '))
          .join('\\n');

        const stubs = `
        const renderMarkdown = (text) => 'LEGACY:' + String(text ?? '');
        const clearIsolatedHtml = () => {{}};
        const renderIsolatedHtml = (anchor, options = {{}}) => {{
          anchor.textContent = String(options.htmlPayload || '');
        }};
        class ChatAppStage {{
          attachHost(anchor) {{
            this.anchor = anchor;
          }}
          update(options = {{}}) {{
            if (this.anchor) {{
              this.anchor.textContent = String(options.htmlPayload || '');
            }}
          }}
          destroy() {{}}
        }}
        class BaseNode {{
          constructor() {{
            this.parentElement = null;
            this.childNodes = [];
            this.isConnected = true;
          }}
          appendChild(node) {{
            if (!node) return node;
            node.parentElement = this;
            this.childNodes.push(node);
            return node;
          }}
          replaceWith(node) {{
            if (!this.parentElement) return;
            const siblings = this.parentElement.childNodes;
            const index = siblings.indexOf(this);
            if (index === -1) return;
            node.parentElement = this.parentElement;
            siblings.splice(index, 1, node);
            this.parentElement = null;
          }}
          get textContent() {{
            return this.childNodes.map((child) => child.textContent).join('');
          }}
          set textContent(value) {{
            this.childNodes = [];
            if (value === null || value === undefined || value === '') {{
              return;
            }}
            const textNode = new TextNode(String(value));
            textNode.parentElement = this;
            this.childNodes.push(textNode);
          }}
        }}
        class TextNode extends BaseNode {{
          constructor(text = '') {{
            super();
            this.data = String(text);
          }}
          get textContent() {{
            return this.data;
          }}
          set textContent(value) {{
            this.data = String(value);
          }}
        }}
        class ElementBase extends BaseNode {{
          constructor(tagName = 'div') {{
            super();
            this.tagName = String(tagName || 'div').toUpperCase();
            this.dataset = {{}};
            this.style = {{}};
            this._className = '';
          }}
          get className() {{
            return this._className;
          }}
          set className(value) {{
            this._className = String(value || '');
          }}
          get classList() {{
            return {{
              contains: (token) => this.className.split(/\s+/).filter(Boolean).includes(String(token || '')),
            }};
          }}
          get children() {{
            return this.childNodes.filter((node) => node instanceof ElementBase);
          }}
          get innerHTML() {{
            return this.textContent;
          }}
          set innerHTML(value) {{
            this.textContent = String(value || '');
          }}
          matches(selector) {{
            return String(selector || '')
              .split(',')
              .map((item) => item.trim())
              .filter(Boolean)
              .some((item) => {{
                if (item === 'pre') return this.tagName === 'PRE';
                if (item === 'div.TH-render') return this.tagName === 'DIV' && this.classList.contains('TH-render');
                return false;
              }});
          }}
          querySelectorAll() {{
            return [];
          }}
        }}
        globalThis.Element = ElementBase;
        globalThis.HTMLElement = ElementBase;
        globalThis.Text = TextNode;
        globalThis.document = {{
          body: new ElementBase('body'),
          createElement(tagName) {{
            return new ElementBase(tagName);
          }},
        }};
        globalThis.MutationObserver = class MutationObserver {{
          observe() {{}}
          disconnect() {{}}
        }};
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source),
        );

        {textwrap.dedent(script_body)}
        '''
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def run_dom_utils_runtime_check(script_body: str) -> None:
    source_path = get_dom_utils_module_path()
    node_script = textwrap.dedent(
        f'''
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/import\s*\{{[\s\S]*?\}}\s*from\s*['\"][^'\"]+['\"];?\s*/gm, '');
        source += `
        export function __installDomTestDoubles() {{
          pretextModule = {{
            prepare(text) {{
              return text;
            }},
            layout() {{
              return {{ lineCount: 1, height: 28 }};
            }},
          }};
          renderRuntimeModule = {{
            clearIsolatedHtml() {{}}
          }};
          messageSegmentRendererModule = {{
            mountMessageSegmentHost(host, options = {{}}) {{
              globalThis.__mountedPreview = {{ host, options }};
            }},
          }};
        }}
        `;

        const stubs = `
        const buildUnifiedDisplaySource = (source) => String(source || '');
        const buildUnifiedPreviewParts = (...args) => {{
          globalThis.__buildPartsArgs = args;
          return [{{
            type: 'app-stage',
            text: 'SENTINEL_APP_STAGE',
            minHeight: 111,
            maxHeight: 222,
          }}];
        }};
        const renderUnifiedDisplayHtml = (source) => 'RENDER:' + String(source || '');
        class StyleDeclaration {{
          constructor() {{
            this.map = new Map();
          }}
          setProperty(name, value) {{
            const normalizedName = String(name || '');
            const normalizedValue = String(value || '');
            this.map.set(normalizedName, normalizedValue);
            this[normalizedName] = normalizedValue;
          }}
          getPropertyValue(name) {{
            return this.map.get(String(name || '')) || '';
          }}
        }}
        class ShadowRootStub {{
          constructor(host) {{
            this.host = host;
            this._html = '';
            this._nodes = new Map();
          }}
          set innerHTML(value) {{
            this._html = String(value || '');
            this._nodes.clear();
            if (this._html.includes('mixed-preview-scroll')) {{
              const scroll = new ElementBase('div');
              scroll.className = 'mixed-preview-scroll markdown-body';
              const host = new ElementBase('div');
              host.className = 'mixed-preview-host';
              scroll.appendChild(host);
              this._nodes.set('.mixed-preview-scroll', scroll);
              this._nodes.set('.mixed-preview-host', host);
            }}
          }}
          get innerHTML() {{
            return this._html;
          }}
          querySelector(selector) {{
            return this._nodes.get(String(selector || '')) || null;
          }}
        }}
        class ElementBase {{
          constructor(tagName = 'div') {{
            this.tagName = String(tagName || 'div').toUpperCase();
            this.dataset = {{}};
            this.style = new StyleDeclaration();
            this.childNodes = [];
            this.parentElement = null;
            this.isConnected = true;
            this.className = '';
            this.clientWidth = 640;
            this.shadowRoot = null;
          }}
          appendChild(node) {{
            if (!node) return node;
            node.parentElement = this;
            this.childNodes.push(node);
            return node;
          }}
          attachShadow() {{
            this.shadowRoot = new ShadowRootStub(this);
            return this.shadowRoot;
          }}
          querySelector() {{
            return null;
          }}
          getBoundingClientRect() {{
            return {{ height: 0 }};
          }}
        }}
        globalThis.Element = ElementBase;
        globalThis.HTMLElement = ElementBase;
        globalThis.document = {{
          body: new ElementBase('body'),
          createElement(tagName) {{
            return new ElementBase(tagName);
          }},
        }};
        globalThis.MutationObserver = class MutationObserver {{
          observe() {{}}
          disconnect() {{}}
        }};
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source),
        );

        {textwrap.dedent(script_body)}
        '''
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_unified_preview_module_exports_shared_render_helpers():
    script_body = textwrap.dedent(
        '''
        const expectedExports = [
          'applyUnifiedDisplayRules',
          'buildUnifiedDisplaySource',
          'renderUnifiedDisplayHtml',
          'buildUnifiedPreviewParts',
        ];

        for (const exportName of expectedExports) {
          if (typeof module[exportName] !== 'function') {
            throw new Error(`expected ${exportName} export to be a function`);
          }
        }
        '''
    )

    run_unified_preview_runtime_check(script_body)


def test_unified_preview_parts_keep_markdown_commentary_and_extract_app_stage_payload():
    preview_source = json.dumps(
        'Lead paragraph\n\n```html\n<div class="demo-app">App</div>\n<script>window.boot = true;</script>\n```'
    )
    script_body = textwrap.dedent(
        '''
        const parts = module.buildUnifiedPreviewParts(
          __PREVIEW_SOURCE__,
          {
            minHeight: 180,
            maxHeight: 900,
          },
        );

        if (!Array.isArray(parts) || parts.length !== 2) {
          throw new Error(`expected two unified preview parts, got ${JSON.stringify(parts)}`);
        }

        if (parts[0]?.type !== 'markdown' || !parts[0]?.text.includes('Lead paragraph')) {
          throw new Error(`expected commentary markdown part first, got ${JSON.stringify(parts[0])}`);
        }

        if (parts[1]?.type !== 'app-stage') {
          throw new Error(`expected app-stage payload part second, got ${JSON.stringify(parts[1])}`);
        }

        if (!parts[1]?.text.includes('<div class="demo-app">App</div>')) {
          throw new Error(`expected extracted html payload, got ${JSON.stringify(parts[1])}`);
        }

        if (parts[1]?.minHeight !== 180 || parts[1]?.maxHeight !== 900) {
          throw new Error(`expected preview bounds to survive part assembly, got ${JSON.stringify(parts[1])}`);
        }
        '''
    ).replace('__PREVIEW_SOURCE__', preview_source)

    run_unified_preview_runtime_check(script_body)


def test_unified_display_rules_default_plain_patterns_replace_globally_for_reader_preview():
    script_body = textwrap.dedent(
        '''
        const output = module.applyUnifiedDisplayRules(
          'foo foo',
          {
            displayRules: [{
              findRegex: 'foo',
              replaceString: 'X',
            }],
          },
          {
            readerDisplayRules: true,
            isMarkdown: true,
          },
        );

        if (output !== 'X X') {
          throw new Error(`expected reader preview rules to replace globally, got ${output}`);
        }
        '''
    )

    run_unified_preview_runtime_check(script_body)


def test_unified_display_rules_treat_bare_patterns_as_raw_regex_with_global_flag():
    script_body = textwrap.dedent(
        '''
        const output = module.applyUnifiedDisplayRules(
          'ab ac',
          {
            displayRules: [{
              findRegex: 'a.',
              replaceString: 'X',
            }],
          },
          {
            readerDisplayRules: true,
            isMarkdown: true,
          },
        );

        if (output !== 'X X') {
          throw new Error(`expected bare pattern to behave like raw global regex, got ${output}`);
        }
        '''
    )

    run_unified_preview_runtime_check(script_body)


def test_build_unified_display_source_applies_rules_before_reader_control_block_stripping():
    script_body = textwrap.dedent(
        '''
        const output = module.buildUnifiedDisplaySource(
          'before [[inject-hidden]] after',
          {
            displayRules: [{
              findRegex: '\\\\[\\\\[inject-hidden\\\\]\\\\]',
              replaceString: '<disclaimer>hide me</disclaimer>',
            }],
          },
          {
            readerDisplayRules: true,
            isMarkdown: true,
          },
        );

        if (output.includes('[[inject-hidden]]')) {
          throw new Error(`expected display rules to run before stripping, marker survived: ${output}`);
        }

        if (output.includes('<disclaimer>') || output.includes('hide me')) {
          throw new Error(`expected reader control block content to be stripped after rule application, got ${output}`);
        }

        if (!output.includes('before') || !output.includes('after')) {
          throw new Error(`expected surrounding content to remain after stripping, got ${output}`);
        }
        '''
    )

    run_unified_preview_runtime_check(script_body)


def test_unified_display_html_reuses_reader_formatter_behavior_for_plain_and_markdown_modes():
    plain_source = json.dumps('line 1\nline 2')
    script_body = textwrap.dedent(
        '''
        const plainHtml = module.renderUnifiedDisplayHtml(__PLAIN_SOURCE__, {
          isMarkdown: false,
        });

        const markdownHtml = module.renderUnifiedDisplayHtml('**bold**', {
          isMarkdown: true,
        });

        if (typeof plainHtml !== 'string' || !plainHtml.trim()) {
          throw new Error(`expected plain render html string, got ${JSON.stringify(plainHtml)}`);
        }

        if (typeof markdownHtml !== 'string' || !markdownHtml.trim()) {
          throw new Error(`expected markdown render html string, got ${JSON.stringify(markdownHtml)}`);
        }

        if (plainHtml === markdownHtml) {
          throw new Error('expected plain and markdown render modes to produce distinct html output');
        }
        '''
    ).replace('__PLAIN_SOURCE__', plain_source)

    run_unified_preview_runtime_check(script_body)


def test_message_segment_renderer_uses_supplied_render_html_for_markdown_parts():
    script_body = textwrap.dedent(
        '''
        const host = document.createElement('div');

        module.mountMessageSegmentHost(host, {
          source: 'alpha',
          parts: [{ type: 'markdown', text: 'alpha' }],
          renderHtml: (text) => 'UNIFIED:' + String(text || ''),
        });

        if (!host.textContent.includes('UNIFIED:alpha')) {
          throw new Error(`expected markdown chunk to use supplied unified html renderer, got ${host.textContent}`);
        }

        if (host.textContent.includes('LEGACY:alpha')) {
          throw new Error(`expected legacy markdown renderer to be bypassed, got ${host.textContent}`);
        }
        '''
    )

    run_message_segment_renderer_runtime_check(script_body)


def test_dom_unified_preview_host_defers_frontend_detection_until_after_render():
    preview_source = json.dumps(
        '```text\n<!DOCTYPE html>\n<html><head><title>Preview</title></head><body><div id="app"></div></body></html>\n```'
    )
    script_body = textwrap.dedent(
        '''
        module.__installDomTestDoubles();

        const host = document.createElement('div');
        module.renderUnifiedPreviewHost(host, __PREVIEW_SOURCE__, {
          runtimeOwner: 'preview-test',
          runtimeLabel: 'Preview Test',
          scroll: true,
          minHeight: 200,
          maxHeight: 0,
        });
        await Promise.resolve();

        if (globalThis.__buildPartsArgs) {
          throw new Error('expected preview host to defer runtime candidate detection until after render');
        }

        const mount = globalThis.__mountedPreview;
        if (!mount || typeof mount.options?.classifyFrontendText !== 'function') {
          throw new Error(`expected preview host to mount with a frontend classifier, got ${JSON.stringify(mount)}`);
        }

        if (Array.isArray(mount.options.parts) && mount.options.parts.length > 0) {
          throw new Error(`expected preview host to avoid precomputed preview parts, got ${JSON.stringify(mount.options.parts)}`);
        }
        '''
    ).replace('__PREVIEW_SOURCE__', preview_source)

    run_dom_utils_runtime_check(script_body)


def test_dom_unified_preview_host_classifier_promotes_full_document_html_to_app_stage():
    script_body = textwrap.dedent(
        '''
        module.__installDomTestDoubles();

        const host = document.createElement('div');
        module.renderUnifiedPreviewHost(host, 'plain preview', {
          runtimeOwner: 'preview-test',
          runtimeLabel: 'Preview Test',
          scroll: true,
        });
        await Promise.resolve();

        const classify = globalThis.__mountedPreview?.options?.classifyFrontendText;
        if (typeof classify !== 'function') {
          throw new Error('expected preview host to expose classifyFrontendText to the segment renderer');
        }

        const classification = classify('<!DOCTYPE html><html><head><title>App</title></head><body><div id="app"></div></body></html>');
        if (!classification || classification.type !== 'app-stage') {
          throw new Error(`expected full-document html to classify as app-stage, got ${JSON.stringify(classification)}`);
        }
        '''
    )

    run_dom_utils_runtime_check(script_body)


def test_dom_unified_preview_host_passes_reader_formatter_to_message_segment_renderer():
    source = read_project_file('static/js/utils/dom.js')
    mount_block = source.split('module.mountMessageSegmentHost(host, {', 1)[1].split('});', 1)[0]

    assert 'renderHtml' in mount_block
    assert 'renderHtmlSignature' in mount_block
    assert 'const renderHtml = (text) => renderUnifiedDisplayHtml(text, renderOptions);' in source
