import os
import re
from datetime import datetime

from core.data.ui_store import get_import_time
from core.services.card_service import resolve_ui_key
from core.utils.filesystem import sanitize_filename


_PLACEHOLDER_RE = re.compile(r'\{\{\s*(.*?)\s*\}\}')
_FILTER_RE = re.compile(r'^(\w+)(?:\((.*)\))?$')


def _empty_filename_observability():
    return {
        'suppressed_filename_action_conflicts': [],
        'noop_rename_reasons': [],
    }


def _normalize_timestamp(value):
    if isinstance(value, bool):
        return None

    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None

    return ts if ts > 0 else None


def _stringify(value):
    return '' if value is None else str(value)


def _split_filters(expression):
    parts = []
    current = []
    quote = None

    for ch in expression:
        if ch in ('"', "'"):
            if quote == ch:
                quote = None
            elif quote is None:
                quote = ch
        if ch == '|' and quote is None:
            parts.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)

    parts.append(''.join(current).strip())
    return [part for part in parts if part]


def _parse_filter(filter_text):
    match = _FILTER_RE.match(filter_text.strip())
    if not match:
        return filter_text.strip(), []

    name = match.group(1)
    raw_args = (match.group(2) or '').strip()
    if not raw_args:
        return name, []

    args = []
    current = []
    quote = None
    for ch in raw_args:
        if ch in ('"', "'"):
            if quote == ch:
                quote = None
            elif quote is None:
                quote = ch
        if ch == ',' and quote is None:
            args.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)

    args.append(''.join(current).strip())
    cleaned_args = []
    for arg in args:
        if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in ('"', "'"):
            cleaned_args.append(arg[1:-1])
        else:
            cleaned_args.append(arg)
    return name, cleaned_args


def _format_date(value, fmt='%Y-%m-%d'):
    ts = _normalize_timestamp(value)
    if ts is None:
        return ''
    return datetime.fromtimestamp(ts).strftime(fmt)


def _normalize_version_text(value):
    text = _stringify(value).strip()
    if not text:
        return ''

    match = re.search(r'v?\d+(?:\.\d+)*', text, re.IGNORECASE)
    if not match:
        return text

    version = match.group(0)
    return version if version.lower().startswith('v') else f'v{version}'


def build_snapshot_template_fields(card_id, card_obj, ui_data=None):
    card_data = dict(card_obj or {})
    filename = _stringify(card_data.get('filename') or os.path.basename(_stringify(card_id)))
    category = _stringify(card_data.get('category'))
    modified_time = _normalize_timestamp(card_data.get('last_modified'))

    resolved_ui_key = resolve_ui_key(card_id) if card_id else ''
    import_time = get_import_time(ui_data or {}, resolved_ui_key, modified_time)
    import_time = _normalize_timestamp(import_time)
    modified_time = modified_time if modified_time is not None else import_time

    return {
        'filename_stem': os.path.splitext(filename)[0],
        'category': category,
        'import_time': import_time if import_time is not None else '',
        'import_date': _format_date(import_time),
        'modified_time': modified_time if modified_time is not None else '',
        'modified_date': _format_date(modified_time),
    }


def _apply_filter(value, filter_name, args):
    if filter_name == 'default':
        return args[0] if _stringify(value) == '' and args else value
    if filter_name == 'trim':
        return _stringify(value).strip()
    if filter_name == 'limit':
        try:
            length = max(0, int(float(args[0]))) if args else 0
        except (TypeError, ValueError):
            length = 0
        return _stringify(value)[:length]
    if filter_name == 'date':
        return _format_date(value, args[0] if args else '%Y-%m-%d')
    if filter_name == 'version':
        return _normalize_version_text(value)
    return value


def render_template_fields(template, fields):
    template_text = _stringify(template)
    payload = dict(fields or {})

    def _replace(match):
        expression = match.group(1)
        parts = _split_filters(expression)
        if not parts:
            return ''

        field_name = parts[0]
        value = payload.get(field_name)
        for filter_text in parts[1:]:
            filter_name, args = _parse_filter(filter_text)
            value = _apply_filter(value, filter_name, args)
        return _stringify(value)

    return _PLACEHOLDER_RE.sub(_replace, template_text)


def _trim_stem_for_length(stem, max_length, suffix=''):
    stem_text = _stringify(stem)
    if max_length is None:
        return stem_text

    try:
        limit = max(0, int(max_length))
    except (TypeError, ValueError):
        return stem_text

    allowed = max(0, limit - len(_stringify(suffix)))
    return stem_text[:allowed]


def _coerce_safe_stem(stem, max_length, suffix=''):
    trimmed = _trim_stem_for_length(stem, max_length, suffix=suffix)
    safe_stem = sanitize_filename(trimmed)
    return _trim_stem_for_length(safe_stem, max_length, suffix=suffix) or 'undefined'


def _resolve_filename_template_stem(current_stem, template, fallback_template, fields):
    payload = dict(fields or {})
    candidates = [
        render_template_fields(template, payload),
        render_template_fields(fallback_template, payload),
        payload.get('filename_stem'),
        payload.get('char_name'),
        payload.get('card'),
    ]

    for candidate in candidates:
        text = _stringify(candidate).strip()
        if text:
            return text

    return _stringify(current_stem).strip() or 'card'


def build_safe_filename_result(
    current_filename,
    template,
    fields,
    *,
    fallback_template='',
    max_length=None,
    dedupe_index=None,
    suppress_conflict=None,
):
    current_name = _stringify(current_filename) or 'card'
    current_stem, extension = os.path.splitext(current_name)
    observability = _empty_filename_observability()

    if suppress_conflict:
        payload = dict(suppress_conflict)
        payload['current_filename'] = current_name
        observability['suppressed_filename_action_conflicts'].append(payload)
        return {
            'stem': current_stem,
            'filename': current_name,
            'extension': extension,
            'noop': False,
            'suppressed': True,
            'observability': observability,
        }

    dedupe_number = None
    try:
        dedupe_number = int(dedupe_index)
    except (TypeError, ValueError):
        dedupe_number = None

    dedupe_suffix = ''
    if dedupe_number is not None and dedupe_number > 1:
        dedupe_suffix = f'_{dedupe_number}'

    raw_stem = _resolve_filename_template_stem(current_stem, template, fallback_template, fields)
    safe_stem = _coerce_safe_stem(raw_stem, max_length, suffix=dedupe_suffix)
    final_stem = f'{safe_stem}{dedupe_suffix}'
    final_filename = f'{final_stem}{extension}'

    if final_filename == current_name:
        observability['noop_rename_reasons'].append({
            'reason': 'same_stem',
            'current_stem': current_stem,
            'candidate_stem': safe_stem,
        })
        return {
            'stem': current_stem,
            'filename': current_name,
            'extension': extension,
            'noop': True,
            'suppressed': False,
            'observability': observability,
        }

    return {
        'stem': safe_stem,
        'filename': final_filename,
        'extension': extension,
        'noop': False,
        'suppressed': False,
        'observability': observability,
    }


__all__ = [
    'build_snapshot_template_fields',
    'build_safe_filename_result',
    'render_template_fields',
]
