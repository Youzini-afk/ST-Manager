"""Preset detail model helpers."""

import copy
import os

from core.utils.source_revision import build_file_source_revision


PRESET_KIND_LABELS = {
    'textgen': '文本生成预设',
    'instruct': '指令模板',
    'context': '上下文模板',
    'sysprompt': '系统提示词',
    'reasoning': '思维链模板',
}

GENERIC_READER_FAMILY_LABEL = '通用预设'
PROMPT_MANAGER_READER_FAMILY_LABEL = 'Prompt Manager 预设'

LONG_TEXT_EDITOR_KEYS = {
    'content',
    'story_string',
    'example_separator',
    'chat_start',
    'prefix',
    'suffix',
    'separator',
    'negative_prompt',
    'json_schema',
    'grammar',
    'input_sequence',
    'output_sequence',
    'system_sequence',
    'first_output_sequence',
    'last_output_sequence',
    'activation_regex',
}

SELECT_EDITOR_OPTIONS = {
    'names_behavior': ['none', 'force', 'always'],
    'insertion_position': ['before', 'after'],
    'injection_role': ['system', 'user', 'assistant'],
}


COMMON_FIELD_KEYS = {
    'name',
    'title',
    'description',
    'note',
    'extensions',
    'prompts',
    'prompt_order',
}


FIELD_ALIAS_MAP = {}

READER_COMMON_FIELD_DEFS = [
    {'key': 'name', 'label': '名称'},
    {'key': 'title', 'label': '标题'},
    {'key': 'description', 'label': '描述'},
    {'key': 'note', 'label': '备注'},
]

GENERIC_READER_GROUP_LABELS = {
    'scalar_fields': '基础字段',
    'structured_objects': '结构化对象',
    'prompts': '消息模板',
    'extensions': '扩展设置',
}

PROMPT_MANAGER_READER_GROUP_LABELS = {
    'prompts': 'Prompt 条目',
    'scalar_fields': '基础字段',
    'structured_objects': '结构化对象',
    'extensions': '扩展设置',
}

PROMPT_INJECTION_POSITION_LABELS = {
    0: '相对位置',
    1: 'In-Chat 注入',
}


SECTION_DEFINITIONS = {
    'textgen': {
        'sampling': [
            {'key': 'temp', 'aliases': ['temperature'], 'label': '温度'},
            {'key': 'top_p', 'aliases': [], 'label': 'Top P'},
            {'key': 'top_k', 'aliases': [], 'label': 'Top K'},
            {'key': 'top_a', 'aliases': [], 'label': 'Top A'},
            {'key': 'min_p', 'aliases': [], 'label': 'Min P'},
            {'key': 'typical_p', 'aliases': ['typical'], 'label': 'Typical P'},
            {'key': 'tfs', 'aliases': [], 'label': 'TFS'},
            {'key': 'temperature_last', 'aliases': [], 'label': 'Temperature Last'},
        ],
        'penalties': [
            {'key': 'repetition_penalty', 'aliases': ['rep_pen'], 'label': '重复惩罚'},
            {'key': 'repetition_penalty_range', 'aliases': [], 'label': '重复范围'},
            {'key': 'repetition_penalty_decay', 'aliases': [], 'label': '重复衰减'},
            {'key': 'frequency_penalty', 'aliases': ['freq_pen'], 'label': '频率惩罚'},
            {'key': 'presence_penalty', 'aliases': ['pres_pen'], 'label': '存在惩罚'},
            {'key': 'no_repeat_ngram_size', 'aliases': [], 'label': 'No Repeat Ngram'},
        ],
        'length_and_output': [
            {'key': 'max_tokens', 'aliases': ['openai_max_tokens', 'max_length'], 'label': '最大生成长度'},
            {'key': 'min_length', 'aliases': [], 'label': '最小长度'},
            {'key': 'num_beams', 'aliases': [], 'label': 'Beam 数'},
            {'key': 'length_penalty', 'aliases': [], 'label': 'Length Penalty'},
            {'key': 'do_sample', 'aliases': [], 'label': 'Do Sample'},
            {'key': 'early_stopping', 'aliases': [], 'label': 'Early Stopping'},
        ],
        'dynamic_temperature': [
            {'key': 'dynamic_temperature', 'aliases': [], 'label': '动态温度'},
            {'key': 'dynatemp_low', 'aliases': [], 'label': '动态温度下限'},
            {'key': 'dynatemp_high', 'aliases': [], 'label': '动态温度上限'},
        ],
        'mirostat': [
            {'key': 'mirostat_mode', 'aliases': [], 'label': 'Mirostat 模式'},
            {'key': 'mirostat_tau', 'aliases': [], 'label': 'Mirostat Tau'},
            {'key': 'mirostat_eta', 'aliases': [], 'label': 'Mirostat Eta'},
        ],
        'guidance': [
            {'key': 'guidance_scale', 'aliases': [], 'label': 'Guidance Scale'},
            {'key': 'negative_prompt', 'aliases': [], 'label': 'Negative Prompt'},
        ],
        'formatting': [
            {'key': 'stream_openai', 'aliases': [], 'label': '流式输出'},
            {'key': 'wrap_in_quotes', 'aliases': [], 'label': '包裹引号'},
            {'key': 'show_thoughts', 'aliases': [], 'label': '显示思维链'},
        ],
        'schema_and_grammar': [
            {'key': 'json_schema', 'aliases': [], 'label': 'JSON Schema'},
            {'key': 'grammar', 'aliases': [], 'label': 'Grammar'},
        ],
        'bans_and_bias': [
            {'key': 'banned_tokens', 'aliases': [], 'label': '禁词'},
            {'key': 'logit_bias', 'aliases': [], 'label': 'Logit Bias'},
        ],
        'sampler_ordering': [
            {'key': 'sampler_order', 'aliases': [], 'label': 'Sampler Order'},
            {'key': 'samplers', 'aliases': [], 'label': 'Sampler Priority'},
        ],
    },
    'instruct': {
        'sequences': [
            {'key': 'input_sequence', 'aliases': [], 'label': '输入序列'},
            {'key': 'output_sequence', 'aliases': [], 'label': '输出序列'},
            {'key': 'system_sequence', 'aliases': [], 'label': '系统序列'},
            {'key': 'first_output_sequence', 'aliases': [], 'label': '首输出序列'},
            {'key': 'last_output_sequence', 'aliases': [], 'label': '尾输出序列'},
            {'key': 'stop_sequence', 'aliases': ['stop_sequences'], 'label': '停止序列'},
        ],
        'wrapping_and_behavior': [
            {'key': 'wrap', 'aliases': [], 'label': '包装与宏'},
            {'key': 'macro', 'aliases': [], 'label': '宏'},
            {'key': 'names_behavior', 'aliases': [], 'label': '名称行为'},
            {'key': 'skip_examples', 'aliases': [], 'label': '跳过示例'},
        ],
        'activation': [
            {'key': 'activation_regex', 'aliases': [], 'label': '激活正则'},
        ],
        'compatibility': [
            {'key': 'system_same_as_user', 'aliases': [], 'label': 'system same as user'},
            {'key': 'last_system_sequence', 'aliases': [], 'label': '尾系统序列'},
            {'key': 'system_sequence_prefix', 'aliases': [], 'label': '系统前缀'},
            {'key': 'sequences_as_stop_strings', 'aliases': [], 'label': '序列作为停止词'},
        ],
    },
    'context': {
        'story': [
            {'key': 'story_string', 'aliases': [], 'label': 'Story String'},
            {'key': 'example_separator', 'aliases': [], 'label': 'Example Separator'},
            {'key': 'chat_start', 'aliases': [], 'label': 'Chat Start'},
        ],
        'separator_and_chat': [
            {'key': 'use_stop_strings', 'aliases': [], 'label': '使用 Stop Strings'},
            {'key': 'names_as_stop_strings', 'aliases': [], 'label': '名称作为 Stop Strings'},
        ],
        'insertion_behavior': [
            {'key': 'injection_depth', 'aliases': ['depth'], 'label': '插入深度'},
            {'key': 'insertion_position', 'aliases': ['position'], 'label': '插入位置'},
            {'key': 'injection_role', 'aliases': ['role'], 'label': '插入角色'},
        ],
        'formatting_behavior': [
            {'key': 'always_force_name2', 'aliases': [], 'label': 'always_force_name2'},
            {'key': 'trim_sentences', 'aliases': [], 'label': 'trim_sentences'},
            {'key': 'single_line', 'aliases': [], 'label': 'single_line'},
        ],
        'compatibility': [
            {'key': 'conversation_separator', 'aliases': [], 'label': '兼容分隔符'},
        ],
    },
    'sysprompt': {
        'prompt': [
            {'key': 'content', 'aliases': [], 'label': '主提示词内容'},
        ],
        'placement': [
            {'key': 'post_history', 'aliases': [], 'label': '后置到历史后'},
        ],
    },
    'reasoning': {
        'template': [
            {'key': 'prefix', 'aliases': [], 'label': '前缀'},
            {'key': 'suffix', 'aliases': [], 'label': '后缀'},
            {'key': 'separator', 'aliases': [], 'label': '分隔符'},
        ],
        'runtime_notes': [
            {'key': 'note', 'aliases': [], 'label': '运行态说明'},
        ],
    },
}

for _kind_sections in SECTION_DEFINITIONS.values():
    for _field_defs in _kind_sections.values():
        for _field_def in _field_defs:
            FIELD_ALIAS_MAP[_field_def['key']] = [_field_def['key'], *_field_def.get('aliases', [])]


def detect_preset_kind(raw_data, source_folder='', file_path=''):
    folder = str(source_folder or '').replace('\\', '/').lower()
    file_hint = str(file_path or '').replace('\\', '/').lower()
    combined = f'{folder} {file_hint}'

    if 'sysprompt' in combined:
        return 'sysprompt'
    if 'reasoning' in combined:
        return 'reasoning'
    if 'context' in combined:
        return 'context'
    if 'instruct' in combined:
        return 'instruct'
    if 'textgen' in combined:
        return 'textgen'

    data = raw_data if isinstance(raw_data, dict) else {}
    if 'content' in data and 'post_history' in data:
        return 'sysprompt'
    if all(key in data for key in ('prefix', 'suffix', 'separator')):
        return 'reasoning'
    if 'story_string' in data and 'chat_start' in data:
        return 'context'
    if any(key in data for key in ('input_sequence', 'output_sequence', 'system_sequence')):
        return 'instruct'
    return 'textgen'


def _resolve_field(data, field_def):
    candidates = [field_def['key'], *field_def.get('aliases', [])]
    for source_key in candidates:
        if source_key in data:
            return source_key, data.get(source_key)
    return None, None


def build_sections(raw_data, preset_kind):
    data = raw_data if isinstance(raw_data, dict) else {}
    definitions = SECTION_DEFINITIONS.get(preset_kind, {})
    sections = {}
    consumed_keys = set(COMMON_FIELD_KEYS)

    for section_name, field_defs in definitions.items():
        items = []
        for field_def in field_defs:
            source_key, value = _resolve_field(data, field_def)
            if source_key is None:
                continue
            consumed_keys.add(source_key)
            items.append({
                'key': field_def['key'],
                'source_key': source_key,
                'label': field_def['label'],
                'value': value,
            })
        if items:
            sections[section_name] = items

    unknown_fields = sorted(key for key in data.keys() if key not in consumed_keys)
    return sections, unknown_fields


def _build_reader_item(*, item_id, item_type, group, title, payload, summary=''):
    return {
        'id': item_id,
        'type': item_type,
        'group': group,
        'title': title,
        'summary': summary,
        'payload': copy.deepcopy(payload),
    }


def _infer_scalar_editor_kind(key, value):
    if key in SELECT_EDITOR_OPTIONS:
        return 'select'
    if key in LONG_TEXT_EDITOR_KEYS:
        return 'textarea'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 'number'
    return 'text'


def _build_editor_meta(kind, label='', description='', raw_fallback=False, options=None):
    meta = {
        'kind': kind,
        'label': label,
        'description': description,
        'raw_fallback': raw_fallback,
    }
    if options is not None:
        meta['options'] = list(options)
    return meta


def _with_editor_fields(item, *, editable, source_key, value_path, unknown, editor):
    enriched = dict(item)
    enriched['editable'] = editable
    enriched['source_key'] = source_key
    enriched['value_path'] = value_path
    enriched['unknown'] = unknown
    enriched['editor'] = copy.deepcopy(editor)
    return enriched


def _build_scalar_reader_item(group, key, value, title=''):
    editor_kind = _infer_scalar_editor_kind(key, value)
    editor_options = SELECT_EDITOR_OPTIONS.get(key)
    return _with_editor_fields(
        _build_reader_item(
        item_id=f'{group}:{key}',
        item_type='field',
        group=group,
        title=title or key,
        summary=str(value),
        payload={'key': key, 'value': copy.deepcopy(value)},
        ),
        editable=True,
        source_key=key,
        value_path=key,
        unknown=False,
        editor=_build_editor_meta(editor_kind, label=title or key, options=editor_options),
    )


def _build_structured_reader_item(group, key, value, title=''):
    value_type = type(value).__name__
    if key == 'logit_bias':
        editor_kind = 'key-value-list'
    elif key in {'prompt_order', 'sampler_order', 'samplers'}:
        editor_kind = 'sortable-string-list'
    elif key == 'stop_sequence':
        editor_kind = 'string-list'
    else:
        editor_kind = 'raw-json'
    return _with_editor_fields(
        _build_reader_item(
        item_id=f'{group}:{key}',
        item_type='structured',
        group=group,
        title=title or key,
        summary=value_type,
        payload={'key': key, 'value': copy.deepcopy(value)},
        ),
        editable=editor_kind != 'raw-json',
        source_key=key,
        value_path=key,
        unknown=False,
        editor=_build_editor_meta(editor_kind, label=title or key, raw_fallback=True),
    )


def _build_prompt_reader_items(data):
    items = []
    for index, prompt in enumerate(data.get('prompts') or []):
        if not isinstance(prompt, dict):
            continue
        identifier = str(prompt.get('identifier') or f'prompt_{index + 1}')
        title = str(prompt.get('name') or identifier)
        role = str(prompt.get('role') or '').strip()
        enabled = prompt.get('enabled', True) is not False
        summary_parts = [role or 'prompt', 'enabled' if enabled else 'disabled']
        if prompt.get('marker'):
            summary_parts.append('marker')
        summary = ' · '.join(summary_parts)
        items.append(
            _with_editor_fields(
                _build_reader_item(
                    item_id=f'prompt:{identifier}',
                    item_type='prompt',
                    group='prompts',
                    title=title,
                    summary=summary,
                    payload=copy.deepcopy(prompt),
                ),
                editable=False,
                source_key='prompts',
                value_path=f'prompts[{index}]',
                unknown=False,
                editor=_build_editor_meta('raw-json', label='消息模板', raw_fallback=True),
            )
        )
    return items


def _is_prompt_workspace_candidate(data):
    prompts = data.get('prompts')
    return isinstance(prompts, list) and any(isinstance(prompt, dict) for prompt in prompts)


def _normalize_prompt_order_entries(prompt_order):
    if not isinstance(prompt_order, list):
        return []

    if prompt_order and all(isinstance(entry, str) for entry in prompt_order):
        return [
            {'identifier': str(entry).strip(), 'enabled': None}
            for entry in prompt_order
            if str(entry).strip()
        ]

    if prompt_order and all(isinstance(entry, dict) and 'identifier' in entry for entry in prompt_order):
        return [
            {
                'identifier': str(entry.get('identifier') or '').strip(),
                'enabled': entry.get('enabled', True) is not False,
            }
            for entry in prompt_order
            if str(entry.get('identifier') or '').strip()
        ]

    for bucket in prompt_order:
        if not isinstance(bucket, dict) or not isinstance(bucket.get('order'), list):
            continue
        return [
            {
                'identifier': str(entry.get('identifier') or '').strip(),
                'enabled': entry.get('enabled', True) is not False,
            }
            for entry in bucket['order']
            if isinstance(entry, dict) and str(entry.get('identifier') or '').strip()
        ]

    return []


def _prompt_position_label(prompt):
    try:
        position = int(prompt.get('injection_position', 0) or 0)
    except (TypeError, ValueError):
        position = 0

    if position == 1:
        try:
            depth = int(prompt.get('injection_depth', 4) or 4)
        except (TypeError, ValueError):
            depth = 4
        return f'In-Chat @ {depth}'
    return PROMPT_INJECTION_POSITION_LABELS.get(position, '相对位置')


def _build_prompt_manager_prompt_items(data):
    indexed_prompts = [
        (index, prompt)
        for index, prompt in enumerate(data.get('prompts') or [])
        if isinstance(prompt, dict)
    ]
    prompt_order_entries = _normalize_prompt_order_entries(data.get('prompt_order'))
    order_lookup = {
        entry['identifier']: {'order_index': index, 'enabled': entry['enabled']}
        for index, entry in enumerate(prompt_order_entries)
    }
    prompt_lookup = {
        str(prompt.get('identifier') or f'prompt_{index + 1}'): (index, prompt)
        for index, prompt in indexed_prompts
    }

    ordered_identifiers = [
        entry['identifier']
        for entry in prompt_order_entries
        if entry['identifier'] in prompt_lookup
    ]
    orphan_identifiers = [
        identifier
        for identifier in prompt_lookup.keys()
        if identifier not in order_lookup
    ]

    items = []
    for order_index, identifier in enumerate([*ordered_identifiers, *orphan_identifiers]):
        prompt_index, prompt = prompt_lookup[identifier]
        prompt_enabled = prompt.get('enabled', True) is not False
        ordered_enabled = order_lookup.get(identifier, {}).get('enabled')
        enabled = prompt_enabled if ordered_enabled is None else ordered_enabled
        is_marker = bool(prompt.get('marker'))
        role = str(prompt.get('role') or '').strip()
        summary_parts = [role or 'prompt', '启用' if enabled else '禁用', _prompt_position_label(prompt)]
        if is_marker:
            summary_parts.append('预留字段')

        item = _with_editor_fields(
            _build_reader_item(
                item_id=f'prompt:{identifier}',
                item_type='prompt',
                group='prompts',
                title=str(prompt.get('name') or identifier),
                summary=' · '.join(summary_parts),
                payload=copy.deepcopy(prompt),
            ),
            editable=True,
            source_key='prompts',
            value_path=f'prompts[{prompt_index}]',
            unknown=False,
            editor=_build_editor_meta('prompt-manager-item', label='Prompt 条目', raw_fallback=True),
        )
        item['reorderable'] = True
        item['content_editable'] = not is_marker
        item['prompt_meta'] = {
            'identifier': identifier,
            'is_marker': is_marker,
            'is_enabled': enabled,
            'content_editable': not is_marker,
            'uses_prompt_order': bool(prompt_order_entries),
            'order_index': order_index,
            'is_orphan': identifier not in order_lookup,
        }
        items.append(item)
    return items

def _build_extension_items(data):
    extensions = data.get('extensions')
    if not isinstance(extensions, dict):
        return []

    items = []
    for key in sorted(extensions.keys()):
        value = extensions.get(key)
        items.append(
            _with_editor_fields(
                _build_reader_item(
                    item_id=f'extensions:{key}',
                    item_type='extension',
                    group='extensions',
                    title=key,
                    summary=type(value).__name__,
                    payload={'key': key, 'value': copy.deepcopy(value)},
                ),
                editable=True,
                source_key='extensions',
                value_path=f'extensions.{key}',
                unknown=False,
                editor=_build_editor_meta('raw-json', label=key, raw_fallback=True),
            )
        )
    return items


def _build_group_defs(group_labels, items):
    counts = {}
    for item in items:
        group = item['group']
        counts[group] = counts.get(group, 0) + 1

    groups = []
    for group_id, label in group_labels.items():
        count = counts.get(group_id, 0)
        if count == 0:
            continue
        groups.append({'id': group_id, 'label': label, 'count': count})
    return groups


def _build_generic_reader_items(data):
    items = []
    for field_def in READER_COMMON_FIELD_DEFS:
        key = field_def['key']
        if key not in data:
            continue
        items.append(_build_scalar_reader_item('scalar_fields', key, data.get(key), field_def['label']))

    for key, value in data.items():
        if key in {'name', 'title', 'description', 'note'}:
            continue
        if key == 'extensions':
            continue
        if key == 'prompts' and isinstance(value, list):
            continue
        if key == 'prompt_order' and isinstance(value, list):
            continue
        if isinstance(value, (dict, list)):
            items.append(_build_structured_reader_item('structured_objects', key, value, key))
        else:
            items.append(_build_scalar_reader_item('scalar_fields', key, value, key))

    items.extend(_build_prompt_reader_items(data))
    items.extend(_build_extension_items(data))
    return items


def _build_prompt_manager_reader_items(data):
    items = []
    for field_def in READER_COMMON_FIELD_DEFS:
        key = field_def['key']
        if key in data:
            items.append(_build_scalar_reader_item('scalar_fields', key, data.get(key), field_def['label']))

    items.extend(_build_prompt_manager_prompt_items(data))

    for key, value in data.items():
        if key in {'name', 'title', 'description', 'note', 'prompts', 'prompt_order', 'extensions'}:
            continue
        if isinstance(value, (dict, list)):
            items.append(_build_structured_reader_item('structured_objects', key, value, key))
        else:
            items.append(_build_scalar_reader_item('scalar_fields', key, value, key))

    items.extend(_build_extension_items(data))
    return items


def build_reader_view(raw_data):
    data = raw_data if isinstance(raw_data, dict) else {}
    if _is_prompt_workspace_candidate(data):
        items = _build_prompt_manager_reader_items(data)
        groups = _build_group_defs(PROMPT_MANAGER_READER_GROUP_LABELS, items)
        prompt_count = len([item for item in items if item['type'] == 'prompt'])

        return {
            'family': 'prompt_manager',
            'family_label': PROMPT_MANAGER_READER_FAMILY_LABEL,
            'groups': groups,
            'items': items,
            'stats': {
                'prompt_count': prompt_count,
                'unknown_count': 0,
            },
        }

    items = _build_generic_reader_items(data)
    groups = _build_group_defs(GENERIC_READER_GROUP_LABELS, items)
    prompt_count = len([item for item in items if item['type'] == 'prompt'])

    return {
        'family': 'generic',
        'family_label': GENERIC_READER_FAMILY_LABEL,
        'groups': groups,
        'items': items,
        'stats': {
            'prompt_count': prompt_count,
            'unknown_count': 0,
        },
    }


def build_preset_detail(*, preset_id, file_path, filename, source_type, source_folder, raw_data, base_dir):
    preset_kind = detect_preset_kind(raw_data, source_folder=source_folder, file_path=file_path)
    sections, _unknown_fields = build_sections(raw_data, preset_kind)
    reader_view = build_reader_view(raw_data)
    data = raw_data if isinstance(raw_data, dict) else {}

    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        mtime = 0
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        file_size = 0

    rel_path = file_path
    try:
        rel_path = os.path.relpath(file_path, base_dir)
    except Exception:
        pass

    return {
        'id': preset_id,
        'name': data.get('name') or data.get('title') or os.path.splitext(filename)[0],
        'filename': filename,
        'path': rel_path,
        'file_path': file_path,
        'source_folder': source_folder,
        'file_size': file_size,
        'mtime': mtime,
        'type': source_type,
        'preset_kind': preset_kind,
        'preset_kind_label': PRESET_KIND_LABELS[preset_kind],
        'source_revision': build_file_source_revision(file_path),
        'is_default_candidate': source_type == 'global',
        'raw_data': copy.deepcopy(raw_data or {}),
        'sections': sections,
        'reader_view': reader_view,
        'extensions': copy.deepcopy(data.get('extensions') or {}),
    }


def merge_preset_content(raw_data, preset_kind, content):
    source_data = raw_data if isinstance(raw_data, dict) else {}
    merged = copy.deepcopy(source_data)
    content = copy.deepcopy(content or {})

    for canonical_key, aliases in FIELD_ALIAS_MAP.items():
        if canonical_key not in content:
            continue
        for alias in aliases[1:]:
            if alias in merged and alias != canonical_key:
                merged.pop(alias, None)
        merged[canonical_key] = content[canonical_key]

    for key, value in content.items():
        if key == 'extensions':
            continue
        merged[key] = value

    if 'extensions' in source_data or 'extensions' in content:
        merged['extensions'] = copy.deepcopy(
            source_data.get('extensions') if 'extensions' not in content else content.get('extensions')
        ) or {}

    return merged
