"""Preset editor profile payload helpers."""

import copy


CHAT_COMPLETION_PROFILE_ID = 'st_chat_completion_preset'
TEXTGEN_PROFILE_ID = 'st_textgen_preset'
INSTRUCT_PROFILE_ID = 'st_instruct_template'
CONTEXT_PROFILE_ID = 'st_context_template'
SYSPROMPT_PROFILE_ID = 'st_sysprompt_template'
REASONING_PROFILE_ID = 'st_reasoning_template'
GENERIC_PROFILE_ID = 'generic_json'


CHAT_COMPLETION_MARKER_FIELDS = {
    'openai_max_context',
    'openai_max_tokens',
    'stream_openai',
    'show_thoughts',
    'reasoning_effort',
    'verbosity',
    'wi_format',
    'scenario_format',
    'personality_format',
}

TEXTGEN_MARKER_FIELDS = {
    'temp',
    'rep_pen',
    'freq_pen',
    'pres_pen',
    'streaming',
    'dynatemp',
    'min_temp',
    'max_temp',
    'sampler_order',
}

CHAT_COMPLETION_STRONG_MARKERS = {
    'openai_max_context',
    'openai_max_tokens',
    'stream_openai',
    'show_thoughts',
    'reasoning_effort',
}

TEXTGEN_STRONG_MARKERS = {
    'rep_pen',
    'streaming',
    'dynatemp',
    'min_temp',
    'max_temp',
    'sampler_order',
}

TEXTGEN_ALIAS_OVERLAP_MARKERS = {
    'temp',
    'temperature',
    'freq_pen',
    'pres_pen',
}

ALLOWED_PASSTHROUGH_SAVE_KEYS = {
    'name',
    'title',
    'description',
    'note',
    'extensions',
}


def _field(
    canonical_key,
    storage_keys,
    *,
    section,
    label,
    control,
    description='',
    min_value=None,
    max_value=None,
    step=None,
    default=None,
    options=None,
    preset_bound=True,
    preserve_existing_key=True,
    visibility_rule='core_or_present',
    reader_style=None,
):
    payload = {
        'canonical_key': canonical_key,
        'storage_keys': list(storage_keys),
        'section': section,
        'label': label,
        'control': control,
        'description': description,
        'preset_bound': preset_bound,
        'preserve_existing_key': preserve_existing_key,
        'visibility_rule': visibility_rule,
        'reader_style': reader_style or control,
    }
    if min_value is not None:
        payload['min'] = min_value
    if max_value is not None:
        payload['max'] = max_value
    if step is not None:
        payload['step'] = step
    if default is not None:
        payload['default'] = default
    if options is not None:
        payload['options'] = list(options)
    return payload


CHAT_COMPLETION_SECTIONS = [
    {'id': 'output_and_reasoning', 'label': '输出与推理', 'description': '上下文、回复长度、流式与推理配置'},
    {'id': 'core_sampling', 'label': '核心采样', 'description': '温度、Top P、Top K 与相关采样参数'},
    {'id': 'penalties', 'label': '惩罚', 'description': '频率、存在与重复惩罚'},
    {'id': 'prompt_manager', 'label': 'Prompt Manager', 'description': 'Prompt 顺序、启用状态与正文编辑'},
    {'id': 'formatting_and_templates', 'label': '格式与模板', 'description': '格式化提示词与模板字段'},
    {'id': 'extensions_and_advanced', 'label': '扩展与高级', 'description': '扩展、bias、seed 与附加高级参数'},
]


TEXTGEN_SECTIONS = [
    {'id': 'length_and_output', 'label': '长度与输出', 'description': '输出长度、流式与输出行为'},
    {'id': 'core_sampling', 'label': '核心采样', 'description': '温度、Top P、Top K 等核心采样参数'},
    {'id': 'penalties', 'label': '惩罚', 'description': '重复、频率、存在和 ngram 惩罚'},
    {'id': 'dynamic_temperature', 'label': '动态温度', 'description': '动态温度开关与上下限'},
    {'id': 'mirostat_and_advanced', 'label': 'Mirostat 与高级采样', 'description': 'Mirostat、beam、CFG 等高级参数'},
    {'id': 'constraints_and_control', 'label': '约束与控制', 'description': '负面提示、grammar、schema 和 token 限制'},
    {'id': 'sampler_ordering', 'label': '采样器排序', 'description': '采样器顺序与优先级'},
    {'id': 'prompt_manager', 'label': 'Prompt Manager', 'description': 'Prompt 顺序、启用状态与正文编辑'},
]


CHAT_COMPLETION_FIELDS = {
    'openai_max_context': _field(
        'openai_max_context',
        ['openai_max_context'],
        section='output_and_reasoning',
        label='上下文长度',
        control='range_with_number',
        min_value=512,
        max_value={'type': 'dynamic', 'rule': 'chat_completion_context_limit', 'fallback': 4095},
        step=1,
        default=4095,
        reader_style='slider_snapshot',
    ),
    'openai_max_tokens': _field(
        'openai_max_tokens',
        ['openai_max_tokens'],
        section='output_and_reasoning',
        label='最大回复长度',
        control='range_with_number',
        min_value=1,
        max_value=128000,
        step=1,
        default=300,
        reader_style='slider_snapshot',
    ),
    'stream_openai': _field(
        'stream_openai',
        ['stream_openai'],
        section='output_and_reasoning',
        label='流式传输',
        control='checkbox',
        default=False,
    ),
    'show_thoughts': _field(
        'show_thoughts',
        ['show_thoughts'],
        section='output_and_reasoning',
        label='显示思维链',
        control='checkbox',
        default=True,
    ),
    'reasoning_effort': _field(
        'reasoning_effort',
        ['reasoning_effort'],
        section='output_and_reasoning',
        label='推理强度',
        control='select',
        default='auto',
        options=['auto', 'low', 'medium', 'high', 'min', 'max'],
    ),
    'verbosity': _field(
        'verbosity',
        ['verbosity'],
        section='output_and_reasoning',
        label='输出冗长度',
        control='select',
        default='auto',
        options=['auto', 'low', 'medium', 'high'],
        visibility_rule='present_or_core',
    ),
    'temperature': _field(
        'temperature',
        ['temperature', 'temp'],
        section='core_sampling',
        label='温度',
        control='range_with_number',
        min_value=0,
        max_value=2,
        step=0.01,
        default=1,
        reader_style='slider_snapshot',
    ),
    'top_p': _field(
        'top_p',
        ['top_p'],
        section='core_sampling',
        label='Top P',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.01,
        default=1,
        reader_style='slider_snapshot',
    ),
    'top_k': _field(
        'top_k',
        ['top_k'],
        section='core_sampling',
        label='Top K',
        control='range_with_number',
        min_value=0,
        max_value=500,
        step=1,
        default=0,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'top_a': _field(
        'top_a',
        ['top_a'],
        section='core_sampling',
        label='Top A',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        default=0,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'min_p': _field(
        'min_p',
        ['min_p'],
        section='core_sampling',
        label='Min P',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        default=0,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'frequency_penalty': _field(
        'frequency_penalty',
        ['frequency_penalty', 'freq_pen'],
        section='penalties',
        label='频率惩罚',
        control='range_with_number',
        min_value=-2,
        max_value=2,
        step=0.01,
        default=0,
        reader_style='slider_snapshot',
    ),
    'presence_penalty': _field(
        'presence_penalty',
        ['presence_penalty', 'pres_pen'],
        section='penalties',
        label='存在惩罚',
        control='range_with_number',
        min_value=-2,
        max_value=2,
        step=0.01,
        default=0,
        reader_style='slider_snapshot',
    ),
    'repetition_penalty': _field(
        'repetition_penalty',
        ['repetition_penalty', 'rep_pen'],
        section='penalties',
        label='重复惩罚',
        control='range_with_number',
        min_value=1,
        max_value=3,
        step=0.01,
        default=1,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'prompts': _field(
        'prompts',
        ['prompts'],
        section='prompt_manager',
        label='Prompts',
        control='prompt_workspace',
        visibility_rule='core_only',
    ),
    'prompt_order': _field(
        'prompt_order',
        ['prompt_order'],
        section='prompt_manager',
        label='Prompt Order',
        control='prompt_workspace',
        visibility_rule='core_only',
    ),
    'wi_format': _field(
        'wi_format',
        ['wi_format'],
        section='formatting_and_templates',
        label='世界书格式',
        control='textarea',
        visibility_rule='present_or_core',
    ),
    'scenario_format': _field(
        'scenario_format',
        ['scenario_format'],
        section='formatting_and_templates',
        label='场景格式',
        control='textarea',
        visibility_rule='present_or_core',
    ),
    'personality_format': _field(
        'personality_format',
        ['personality_format'],
        section='formatting_and_templates',
        label='人格格式',
        control='textarea',
        visibility_rule='present_or_core',
    ),
    'assistant_prefill': _field(
        'assistant_prefill',
        ['assistant_prefill'],
        section='formatting_and_templates',
        label='Assistant Prefill',
        control='textarea',
        visibility_rule='present_only',
    ),
    'assistant_impersonation': _field(
        'assistant_impersonation',
        ['assistant_impersonation'],
        section='formatting_and_templates',
        label='Assistant Impersonation',
        control='textarea',
        visibility_rule='present_only',
    ),
    'impersonation_prompt': _field(
        'impersonation_prompt',
        ['impersonation_prompt'],
        section='formatting_and_templates',
        label='Impersonation Prompt',
        control='textarea',
        visibility_rule='present_only',
    ),
    'new_chat_prompt': _field(
        'new_chat_prompt',
        ['new_chat_prompt'],
        section='formatting_and_templates',
        label='New Chat Prompt',
        control='textarea',
        visibility_rule='present_or_core',
    ),
    'new_group_chat_prompt': _field(
        'new_group_chat_prompt',
        ['new_group_chat_prompt'],
        section='formatting_and_templates',
        label='New Group Chat Prompt',
        control='textarea',
        visibility_rule='present_only',
    ),
    'new_example_chat_prompt': _field(
        'new_example_chat_prompt',
        ['new_example_chat_prompt'],
        section='formatting_and_templates',
        label='New Example Chat Prompt',
        control='textarea',
        visibility_rule='present_only',
    ),
    'continue_nudge_prompt': _field(
        'continue_nudge_prompt',
        ['continue_nudge_prompt'],
        section='formatting_and_templates',
        label='Continue Nudge Prompt',
        control='textarea',
        visibility_rule='present_or_core',
    ),
    'group_nudge_prompt': _field(
        'group_nudge_prompt',
        ['group_nudge_prompt'],
        section='formatting_and_templates',
        label='Group Nudge Prompt',
        control='textarea',
        visibility_rule='present_only',
    ),
    'extensions': _field(
        'extensions',
        ['extensions'],
        section='extensions_and_advanced',
        label='扩展',
        control='raw_json',
        visibility_rule='present_or_core',
    ),
    'logit_bias': _field(
        'logit_bias',
        ['logit_bias'],
        section='extensions_and_advanced',
        label='Logit Bias',
        control='key_value_list',
        visibility_rule='present_only',
    ),
    'seed': _field(
        'seed',
        ['seed'],
        section='extensions_and_advanced',
        label='Seed',
        control='number',
        min_value=-1,
        max_value=2147483647,
        step=1,
        visibility_rule='present_only',
    ),
    'n': _field(
        'n',
        ['n'],
        section='extensions_and_advanced',
        label='生成分支数',
        control='number',
        min_value=1,
        max_value=32,
        step=1,
        default=1,
        visibility_rule='present_only',
    ),
}


TEXTGEN_FIELDS = {
    'max_length': _field(
        'max_length',
        ['max_length', 'max_tokens', 'openai_max_tokens'],
        section='length_and_output',
        label='最大生成长度',
        control='range_with_number',
        min_value=1,
        max_value=131072,
        step=1,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'min_length': _field(
        'min_length',
        ['min_length'],
        section='length_and_output',
        label='最小长度',
        control='number',
        min_value=0,
        max_value=131072,
        step=1,
        visibility_rule='present_only',
    ),
    'streaming': _field(
        'streaming',
        ['streaming'],
        section='length_and_output',
        label='流式传输',
        control='checkbox',
        default=False,
        visibility_rule='present_or_core',
    ),
    'include_reasoning': _field(
        'include_reasoning',
        ['include_reasoning'],
        section='length_and_output',
        label='输出推理内容',
        control='checkbox',
        visibility_rule='present_only',
    ),
    'temp': _field(
        'temp',
        ['temp', 'temperature'],
        section='core_sampling',
        label='温度',
        control='range_with_number',
        min_value=0,
        max_value=5,
        step=0.01,
        default=1,
        reader_style='slider_snapshot',
    ),
    'top_p': _field(
        'top_p',
        ['top_p'],
        section='core_sampling',
        label='Top P',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.01,
        default=1,
        reader_style='slider_snapshot',
    ),
    'top_k': _field(
        'top_k',
        ['top_k'],
        section='core_sampling',
        label='Top K',
        control='range_with_number',
        min_value=0,
        max_value=500,
        step=1,
        default=0,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'top_a': _field(
        'top_a',
        ['top_a'],
        section='core_sampling',
        label='Top A',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        default=0,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'min_p': _field(
        'min_p',
        ['min_p'],
        section='core_sampling',
        label='Min P',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        default=0,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'typical_p': _field(
        'typical_p',
        ['typical_p', 'typical'],
        section='core_sampling',
        label='Typical P',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'tfs': _field(
        'tfs',
        ['tfs'],
        section='core_sampling',
        label='TFS',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.001,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'rep_pen': _field(
        'rep_pen',
        ['rep_pen', 'repetition_penalty'],
        section='penalties',
        label='重复惩罚',
        control='range_with_number',
        min_value=1,
        max_value=3,
        step=0.01,
        default=1,
        reader_style='slider_snapshot',
    ),
    'freq_pen': _field(
        'freq_pen',
        ['freq_pen', 'frequency_penalty'],
        section='penalties',
        label='频率惩罚',
        control='range_with_number',
        min_value=-2,
        max_value=2,
        step=0.01,
        default=0,
        reader_style='slider_snapshot',
    ),
    'pres_pen': _field(
        'pres_pen',
        ['pres_pen', 'presence_penalty'],
        section='penalties',
        label='存在惩罚',
        control='range_with_number',
        min_value=-2,
        max_value=2,
        step=0.01,
        default=0,
        reader_style='slider_snapshot',
    ),
    'no_repeat_ngram_size': _field(
        'no_repeat_ngram_size',
        ['no_repeat_ngram_size'],
        section='penalties',
        label='No Repeat Ngram',
        control='number',
        min_value=0,
        max_value=64,
        step=1,
        visibility_rule='present_only',
    ),
    'dynatemp': _field(
        'dynatemp',
        ['dynatemp', 'dynamic_temperature'],
        section='dynamic_temperature',
        label='动态温度',
        control='checkbox',
        visibility_rule='present_or_core',
    ),
    'min_temp': _field(
        'min_temp',
        ['min_temp', 'dynatemp_low'],
        section='dynamic_temperature',
        label='动态温度下限',
        control='range_with_number',
        min_value=0,
        max_value=5,
        step=0.01,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'max_temp': _field(
        'max_temp',
        ['max_temp', 'dynatemp_high'],
        section='dynamic_temperature',
        label='动态温度上限',
        control='range_with_number',
        min_value=0,
        max_value=5,
        step=0.01,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'mirostat_mode': _field(
        'mirostat_mode',
        ['mirostat_mode'],
        section='mirostat_and_advanced',
        label='Mirostat 模式',
        control='number',
        min_value=0,
        max_value=2,
        step=1,
        visibility_rule='present_or_core',
    ),
    'mirostat_tau': _field(
        'mirostat_tau',
        ['mirostat_tau'],
        section='mirostat_and_advanced',
        label='Mirostat Tau',
        control='range_with_number',
        min_value=0,
        max_value=10,
        step=0.01,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'mirostat_eta': _field(
        'mirostat_eta',
        ['mirostat_eta'],
        section='mirostat_and_advanced',
        label='Mirostat Eta',
        control='range_with_number',
        min_value=0,
        max_value=1,
        step=0.01,
        visibility_rule='present_or_core',
        reader_style='slider_snapshot',
    ),
    'guidance_scale': _field(
        'guidance_scale',
        ['guidance_scale'],
        section='mirostat_and_advanced',
        label='Guidance Scale',
        control='range_with_number',
        min_value=0,
        max_value=10,
        step=0.01,
        visibility_rule='present_only',
        reader_style='slider_snapshot',
    ),
    'negative_prompt': _field(
        'negative_prompt',
        ['negative_prompt'],
        section='constraints_and_control',
        label='Negative Prompt',
        control='textarea',
        visibility_rule='present_only',
    ),
    'grammar': _field(
        'grammar',
        ['grammar', 'grammar_string'],
        section='constraints_and_control',
        label='Grammar',
        control='textarea',
        visibility_rule='present_only',
    ),
    'json_schema': _field(
        'json_schema',
        ['json_schema'],
        section='constraints_and_control',
        label='JSON Schema',
        control='textarea',
        visibility_rule='present_only',
    ),
    'banned_tokens': _field(
        'banned_tokens',
        ['banned_tokens'],
        section='constraints_and_control',
        label='禁词',
        control='textarea',
        visibility_rule='present_only',
    ),
    'logit_bias': _field(
        'logit_bias',
        ['logit_bias'],
        section='constraints_and_control',
        label='Logit Bias',
        control='key_value_list',
        visibility_rule='present_only',
    ),
    'sampler_order': _field(
        'sampler_order',
        ['sampler_order'],
        section='sampler_ordering',
        label='Sampler Order',
        control='sortable_string_list',
        visibility_rule='present_only',
    ),
    'samplers': _field(
        'samplers',
        ['samplers'],
        section='sampler_ordering',
        label='Sampler Priority',
        control='sortable_string_list',
        visibility_rule='present_only',
    ),
    'prompts': _field(
        'prompts',
        ['prompts'],
        section='prompt_manager',
        label='Prompts',
        control='prompt_workspace',
        visibility_rule='core_only',
    ),
    'prompt_order': _field(
        'prompt_order',
        ['prompt_order'],
        section='prompt_manager',
        label='Prompt Order',
        control='prompt_workspace',
        visibility_rule='core_only',
    ),
}


PROFILE_REGISTRY = {
    CHAT_COMPLETION_PROFILE_ID: {
        'id': CHAT_COMPLETION_PROFILE_ID,
        'label': 'ST 聊天补全预设',
        'family': 'st_mirror',
        'supports_prompt_workspace': True,
        'reader_layout': 'mirrored_sections',
        'save_target': 'st_openai_preset_dir',
        'sections': CHAT_COMPLETION_SECTIONS,
        'fields': CHAT_COMPLETION_FIELDS,
    },
    TEXTGEN_PROFILE_ID: {
        'id': TEXTGEN_PROFILE_ID,
        'label': 'ST 文本生成预设',
        'family': 'st_mirror',
        'supports_prompt_workspace': True,
        'reader_layout': 'mirrored_sections',
        'save_target': 'st_textgen_preset_dir',
        'sections': TEXTGEN_SECTIONS,
        'fields': TEXTGEN_FIELDS,
    },
    INSTRUCT_PROFILE_ID: {
        'id': INSTRUCT_PROFILE_ID,
        'label': 'ST 指令模板',
        'family': 'template',
        'supports_prompt_workspace': False,
        'reader_layout': 'generic',
        'save_target': 'st_instruct_preset_dir',
        'sections': [],
        'fields': {},
    },
    CONTEXT_PROFILE_ID: {
        'id': CONTEXT_PROFILE_ID,
        'label': 'ST 上下文模板',
        'family': 'template',
        'supports_prompt_workspace': False,
        'reader_layout': 'generic',
        'save_target': 'st_context_preset_dir',
        'sections': [],
        'fields': {},
    },
    SYSPROMPT_PROFILE_ID: {
        'id': SYSPROMPT_PROFILE_ID,
        'label': 'ST 系统提示词',
        'family': 'template',
        'supports_prompt_workspace': False,
        'reader_layout': 'generic',
        'save_target': 'st_sysprompt_dir',
        'sections': [],
        'fields': {},
    },
    REASONING_PROFILE_ID: {
        'id': REASONING_PROFILE_ID,
        'label': 'ST 思维链模板',
        'family': 'template',
        'supports_prompt_workspace': False,
        'reader_layout': 'generic',
        'save_target': 'st_reasoning_dir',
        'sections': [],
        'fields': {},
    },
    GENERIC_PROFILE_ID: {
        'id': GENERIC_PROFILE_ID,
        'label': 'Generic JSON',
        'family': 'generic',
        'supports_prompt_workspace': False,
        'reader_layout': 'generic',
        'save_target': 'presets_dir',
        'sections': [],
        'fields': {},
    },
}


def _resolve_source_key(data, storage_keys):
    for storage_key in storage_keys:
        if storage_key in data:
            return storage_key
    return None


def _iter_field_lookup_keys(field_def):
    seen = set()
    for key in [field_def['canonical_key'], *field_def.get('storage_keys', [])]:
        if key in seen:
            continue
        seen.add(key)
        yield key


def _resolve_field_def(profile_def, key):
    for field_def in profile_def.get('fields', {}).values():
        if key in set(_iter_field_lookup_keys(field_def)):
            return field_def
    return None


def _clamp_numeric_value(value, min_value=None, max_value=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value
    if isinstance(min_value, (int, float)):
        value = max(value, min_value)
    if isinstance(max_value, (int, float)):
        value = min(value, max_value)
    return value


def _resolve_dynamic_max_value(max_value, current_value, incoming_value=None):
    if not isinstance(max_value, dict):
        return max_value
    if max_value.get('type') != 'dynamic':
        return None

    fallback = max_value.get('fallback', 4095)
    if isinstance(current_value, (int, float)) and not isinstance(current_value, bool):
        return max(current_value, fallback)
    if isinstance(incoming_value, (int, float)) and not isinstance(incoming_value, bool):
        return max(incoming_value, fallback)
    return fallback


def _score_editor_profile_markers(data):
    textgen_score = 0
    chat_score = 0

    for key in CHAT_COMPLETION_STRONG_MARKERS:
        if key in data:
            chat_score += 2

    for key in TEXTGEN_STRONG_MARKERS:
        if key in data:
            textgen_score += 2

    for key in TEXTGEN_ALIAS_OVERLAP_MARKERS:
        if key in data:
            textgen_score += 1

    if 'top_p' in data:
        textgen_score += 1
        chat_score += 1

    return textgen_score, chat_score


def detect_editor_profile_id(raw_data, preset_kind):
    if preset_kind == 'instruct':
        return INSTRUCT_PROFILE_ID
    if preset_kind == 'context':
        return CONTEXT_PROFILE_ID
    if preset_kind == 'sysprompt':
        return SYSPROMPT_PROFILE_ID
    if preset_kind == 'reasoning':
        return REASONING_PROFILE_ID
    if preset_kind != 'textgen':
        return GENERIC_PROFILE_ID

    data = raw_data if isinstance(raw_data, dict) else {}
    textgen_score, chat_score = _score_editor_profile_markers(data)
    if textgen_score > chat_score and textgen_score > 0:
        return TEXTGEN_PROFILE_ID
    if chat_score > 0:
        return CHAT_COMPLETION_PROFILE_ID
    if any(field in data for field in TEXTGEN_MARKER_FIELDS):
        return TEXTGEN_PROFILE_ID
    if any(field in data for field in CHAT_COMPLETION_MARKER_FIELDS):
        return CHAT_COMPLETION_PROFILE_ID
    return GENERIC_PROFILE_ID


def get_editor_profile_definition(raw_data, preset_kind):
    profile_id = detect_editor_profile_id(raw_data, preset_kind)
    return PROFILE_REGISTRY[profile_id]


def resolve_profile_storage_key(raw_data, preset_kind, incoming_key):
    data = raw_data if isinstance(raw_data, dict) else {}
    field_def = _resolve_field_def(get_editor_profile_definition(data, preset_kind), incoming_key)
    if field_def is None:
        return incoming_key
    return _resolve_source_key(data, field_def.get('storage_keys', [])) or field_def['storage_keys'][0]


def resolve_profile_remove_keys(raw_data, preset_kind, content):
    source_data = raw_data if isinstance(raw_data, dict) else {}
    incoming_content = content if isinstance(content, dict) else {}
    profile_data = dict(source_data)
    profile_data.update(incoming_content)
    profile_def = get_editor_profile_definition(profile_data, preset_kind)
    if not profile_def.get('fields'):
        return []

    remove_keys = set()
    for key in incoming_content.keys():
        field_def = _resolve_field_def(profile_def, key)
        if field_def is None:
            continue

        target_key = _resolve_source_key(source_data, field_def.get('storage_keys', [])) or field_def['storage_keys'][0]
        for lookup_key in _iter_field_lookup_keys(field_def):
            if lookup_key != target_key and lookup_key in source_data:
                remove_keys.add(lookup_key)

    return sorted(remove_keys)


def normalize_preset_content_for_save(raw_data, preset_kind, content):
    source_data = raw_data if isinstance(raw_data, dict) else {}
    normalized = copy.deepcopy(content or {})
    profile_data = dict(source_data)
    if isinstance(normalized, dict):
        profile_data.update(normalized)
    profile_def = get_editor_profile_definition(profile_data, preset_kind)
    if not profile_def.get('fields'):
        return normalized

    filtered = {}

    for key in list(normalized.keys()):
        field_def = _resolve_field_def(profile_def, key)
        if field_def is None:
            if key in ALLOWED_PASSTHROUGH_SAVE_KEYS:
                filtered[key] = copy.deepcopy(normalized[key])
            continue

        value = normalized[key]
        current_key = _resolve_source_key(source_data, field_def.get('storage_keys', []))
        current_value = source_data.get(current_key) if current_key else None

        options = field_def.get('options')
        if isinstance(options, list) and value not in options:
            if current_value in options:
                filtered[key] = current_value
            continue

        filtered[key] = _clamp_numeric_value(
            value,
            min_value=field_def.get('min'),
            max_value=_resolve_dynamic_max_value(
                field_def.get('max'),
                current_value,
                value if not source_data else None,
            ),
        )

    return filtered


def resolve_global_save_dir_config_key(raw_data, preset_kind):
    profile_id = detect_editor_profile_id(raw_data if isinstance(raw_data, dict) else {}, preset_kind)
    return PROFILE_REGISTRY.get(profile_id, PROFILE_REGISTRY[GENERIC_PROFILE_ID]).get('save_target', 'presets_dir')


def build_editor_profile_payload(raw_data, preset_kind):
    data = raw_data if isinstance(raw_data, dict) else {}
    profile_def = get_editor_profile_definition(data, preset_kind)

    fields = {}
    for canonical_key, field_def in profile_def.get('fields', {}).items():
        source_key = _resolve_source_key(data, field_def['storage_keys'])
        if field_def.get('visibility_rule') == 'present_only' and source_key is None:
            continue
        resolved_key = source_key or canonical_key
        field_payload = copy.deepcopy(field_def)
        field_payload['id'] = canonical_key
        field_payload['storage_key'] = resolved_key
        field_payload['source_key'] = source_key
        fields[canonical_key] = field_payload

    return {
        'id': profile_def['id'],
        'label': profile_def['label'],
        'family': profile_def.get('family', 'generic'),
        'supports_prompt_workspace': profile_def.get('supports_prompt_workspace', False),
        'save_target': profile_def.get('save_target', 'presets_dir'),
        'reader_layout': profile_def.get('reader_layout', 'generic'),
        'sections': copy.deepcopy(profile_def.get('sections', [])),
        'fields': fields,
    }
