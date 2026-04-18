import json
from pathlib import Path
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]


def run_regex_test_bench_runtime_check(script_body: str) -> None:
    source_path = (ROOT / 'static/js/utils/regexTestBench.js').resolve()
    node_script = textwrap.dedent(
        f'''
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        const source = readFileSync(sourcePath, 'utf8');
        const module = await import(
          'data:text/javascript,' + encodeURIComponent(source),
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


def run_advanced_editor_runtime_check(script_body: str) -> None:
    source_path = ROOT / 'static/js/components/advancedEditor.js'
    node_script = textwrap.dedent(
        f"""
        import {{ readFileSync }} from 'node:fs';

        const sourcePath = {json.dumps(str(source_path))};
        let source = readFileSync(sourcePath, 'utf8');
        source = source.replace(/^import[\\s\\S]*?;\\r?\\n/gm, '');
        source = source.replace('export default function advancedEditor()', 'function advancedEditor()');

        const stubs = `
        class ManagerScriptRuntime {{
          constructor(options = {{}}) {{
            this.options = options;
          }}
          mount() {{}}
          stop() {{}}
          updateData() {{}}
          updateButtons() {{}}
          setContext() {{}}
        }}
        const subscribeRuntimeManager = () => () => {{}};
        const updateShadowContent = () => {{}};
        const updateMixedPreviewContent = () => {{}};
        const regexErrorMessage = 'Invalid regular expression: Unterminated group';
        const applyDisplayRules = () => {{
          throw new Error(regexErrorMessage);
        }};
        const runRegexTestBenchScript = () => {{
          throw new Error(regexErrorMessage);
        }};
        `;

        const module = await import(
          'data:text/javascript,' + encodeURIComponent(stubs + source + '\\nexport default advancedEditor;'),
        );
        const component = module.default();

        {textwrap.dedent(script_body)}
        """
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_regex_test_bench_plain_patterns_are_not_global_by_default():
    script_body = textwrap.dedent(
        '''
        const output = module.runRegexTestBenchScript(
          {
            findRegex: 'foo',
            replaceString: 'X',
            trimStrings: [],
            substituteRegex: 0,
          },
          'foo foo',
        );

        if (output !== 'X foo') {
          throw new Error(`expected plain pattern to replace once, got ${output}`);
        }
        '''
    )

    run_regex_test_bench_runtime_check(script_body)


def test_regex_test_bench_ignores_runtime_filter_fields():
    script_body = textwrap.dedent(
        '''
        const output = module.runRegexTestBenchScript(
          {
            findRegex: 'foo',
            replaceString: 'bar',
            trimStrings: [],
            substituteRegex: 0,
            disabled: true,
            markdownOnly: true,
            promptOnly: true,
            runOnEdit: false,
            placement: [1],
            minDepth: 10,
            maxDepth: 0,
          },
          'foo',
        );

        if (output !== 'bar') {
          throw new Error(`expected test bench to ignore runtime filters, got ${output}`);
        }
        '''
    )

    run_regex_test_bench_runtime_check(script_body)


def test_regex_test_bench_expands_groups_match_and_trim_strings():
    script_body = textwrap.dedent(
        '''
        const output = module.runRegexTestBenchScript(
          {
            findRegex: '/^(hello) (?<target>world)$/',
            replaceString: '[$0][$1][$<target>][{{match}}]',
            trimStrings: ['l'],
            substituteRegex: 0,
          },
          'hello world',
        );

        if (output !== '[heo word][heo][world][heo word]') {
          throw new Error(`unexpected replacement output: ${output}`);
        }
        '''
    )

    run_regex_test_bench_runtime_check(script_body)


def test_regex_test_bench_supports_raw_and_escaped_macro_substitution():
    script_body = textwrap.dedent(
        '''
        const rawSource = module.resolveRegexTestBenchFindSource(
          {
            findRegex: '{{needle}}+',
            substituteRegex: 1,
          },
          { needle: 'ab' },
        );
        if (rawSource !== 'ab+') {
          throw new Error(`expected raw macro expansion, got ${rawSource}`);
        }

        const escapedSource = module.resolveRegexTestBenchFindSource(
          {
            findRegex: '{{needle}}+',
            substituteRegex: 2,
          },
          { needle: 'a.b' },
        );
        if (escapedSource !== 'a\\\\.b+') {
          throw new Error(`expected escaped macro expansion, got ${escapedSource}`);
        }

        const output = module.runRegexTestBenchScript(
          {
            findRegex: '{{needle}}',
            replaceString: 'X',
            trimStrings: [],
            substituteRegex: 2,
          },
          'a.b',
          {
            macroContext: {
              needle: 'a.b',
            },
          },
        );

        if (output !== 'X') {
          throw new Error(`expected escaped macro match, got ${output}`);
        }
        '''
    )

    run_regex_test_bench_runtime_check(script_body)


def test_advanced_editor_run_regex_test_formats_regex_errors():
    script_body = textwrap.dedent(
        '''
        component.editingData = {
          extensions: {
            regex_scripts: [{
              findRegex: '/(/',
              replaceString: 'X',
              trimStrings: [],
            }],
          },
        };
        component.activeRegexIndex = 0;
        component.regexTestInput = 'foo';
        component.regexTestResult = '';

        component.runRegexTest();

        if (!component.regexTestResult.startsWith('❌ 正则表达式错误: ')) {
          throw new Error(`missing user-facing error prefix: ${component.regexTestResult}`);
        }

        if (!component.regexTestResult.includes('Invalid regular expression: Unterminated group')) {
          throw new Error(`missing regex error details: ${component.regexTestResult}`);
        }
        '''
    )

    run_advanced_editor_runtime_check(script_body)
