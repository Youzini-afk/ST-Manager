"""Preset version metadata helpers."""

import copy
import os
import uuid


MANAGER_METADATA_KEY = 'x_st_manager'
DEFAULT_VERSION_ORDER = 100


def generate_preset_family_id() -> str:
    return uuid.uuid4().hex


def extract_preset_version_meta(raw_data, *, fallback_name='', fallback_filename=''):
    manager_meta = raw_data.get(MANAGER_METADATA_KEY)
    if not isinstance(manager_meta, dict):
        return {
            'family_id': '',
            'family_name': fallback_name,
            'version_label': _build_fallback_version_label(fallback_filename),
            'version_order': DEFAULT_VERSION_ORDER,
            'is_default_version': False,
            'is_versioned': False,
        }

    family_id = _safe_text(manager_meta.get('preset_family_id'))
    family_name = _safe_text(manager_meta.get('preset_family_name')) or fallback_name
    version_label = (
        _safe_text(manager_meta.get('preset_version_label'))
        or _build_fallback_version_label(fallback_filename)
    )
    version_order = _safe_int(manager_meta.get('preset_version_order'), DEFAULT_VERSION_ORDER)
    is_default_version = bool(manager_meta.get('preset_is_default_version'))

    return {
        'family_id': family_id,
        'family_name': family_name,
        'version_label': version_label,
        'version_order': version_order,
        'is_default_version': is_default_version,
        'is_versioned': bool(family_id),
    }


def upsert_preset_version_meta(
    raw_data,
    *,
    family_id,
    family_name,
    version_label,
    version_order=DEFAULT_VERSION_ORDER,
    is_default_version=False,
):
    updated = copy.deepcopy(raw_data)
    manager_meta = updated.get(MANAGER_METADATA_KEY)
    if not isinstance(manager_meta, dict):
        manager_meta = {}
    else:
        manager_meta = copy.deepcopy(manager_meta)

    manager_meta.update(
        {
            'preset_family_id': family_id,
            'preset_family_name': family_name,
            'preset_version_label': version_label,
            'preset_version_order': version_order,
            'preset_is_default_version': bool(is_default_version),
        }
    )
    updated[MANAGER_METADATA_KEY] = manager_meta
    return updated


def build_family_entry_id(source_type: str, root_scope_key: str, family_id: str) -> str:
    return f'{source_type}::{root_scope_key}::{family_id}'


def group_preset_list_items(source_items):
    grouped_items = []
    family_groups = {}

    for item in source_items:
        item_copy = copy.deepcopy(item)
        version_meta = item_copy.get('preset_version') or {}
        if not version_meta.get('is_versioned') or not version_meta.get('family_id'):
            item_copy['entry_type'] = 'single'
            grouped_items.append(item_copy)
            continue

        source_type = item_copy.get('source_type') or item_copy.get('type') or ''
        root_scope_key = item_copy.get('root_scope_key') or ''
        family_id = version_meta.get('family_id') or ''
        group_key = (source_type, root_scope_key, family_id)
        family_groups.setdefault(group_key, []).append(item_copy)

    for (source_type, root_scope_key, family_id), versions in family_groups.items():
        sorted_versions = sorted(versions, key=_version_sort_key)
        default_version = sorted_versions[0]
        default_meta = default_version.get('preset_version') or {}
        family_entry = {
            'id': build_family_entry_id(source_type, root_scope_key, family_id),
            'entry_type': 'family',
            'name': default_meta.get('family_name') or default_version.get('name') or '',
            'family_id': family_id,
            'family_name': default_meta.get('family_name') or default_version.get('name') or '',
            'default_version_id': default_version.get('id'),
            'default_version_label': default_meta.get('version_label') or '',
            'version_count': len(sorted_versions),
            'versions': sorted_versions,
            'mtime': max(_coerce_mtime(version.get('mtime')) for version in sorted_versions),
            'source_type': source_type,
            'root_scope_key': root_scope_key,
            'display_category': default_version.get('display_category', ''),
            'physical_category': default_version.get('physical_category', ''),
            'category_mode': default_version.get('category_mode', ''),
            'category_override': default_version.get('category_override', ''),
            'owner_card_id': default_version.get('owner_card_id', ''),
            'owner_card_name': default_version.get('owner_card_name', ''),
            'owner_card_category': default_version.get('owner_card_category', ''),
            'display_categories': sorted({
                str(version.get('display_category') or '').strip()
                for version in sorted_versions
                if str(version.get('display_category') or '').strip()
            }),
        }
        grouped_items.append(family_entry)

    return sorted(grouped_items, key=lambda item: _coerce_mtime(item.get('mtime')), reverse=True)


def ensure_unique_version_labels(labels):
    reserved = set()
    seen = {}
    unique_labels = []

    for label in labels:
        normalized = str(label or '').strip()
        if normalized not in reserved:
            unique_labels.append(normalized)
            reserved.add(normalized)
            seen[normalized] = max(seen.get(normalized, 0), 1)
            continue

        next_index = seen.get(normalized, 1) + 1
        candidate = f'{normalized} ({next_index})'
        while candidate in reserved:
            next_index += 1
            candidate = f'{normalized} ({next_index})'

        seen[normalized] = next_index
        reserved.add(candidate)
        unique_labels.append(candidate)

    return unique_labels


def iter_entry_version_members(entry):
    if not isinstance(entry, dict):
        return []
    if entry.get('entry_type') == 'family':
        return list(entry.get('versions') or [])
    return [entry]


def build_merge_version_plan(*, target_entry, source_entries, family_name):
    members = []
    for entry in [target_entry, *(source_entries or [])]:
        members.extend(copy.deepcopy(iter_entry_version_members(entry)))

    version_labels = []
    for member in members:
        version_meta = member.get('preset_version') or {}
        version_labels.append(version_meta.get('version_label') or '')

    unique_labels = ensure_unique_version_labels(version_labels)
    family_id = (target_entry.get('family_id') or '').strip()
    family_name = str(family_name or '').strip()
    default_version_id = str(target_entry.get('default_version_id') or '').strip()

    planned_members = []
    for index, member in enumerate(members, start=1):
        version_meta = copy.deepcopy(member.get('preset_version') or {})
        version_meta.update(
            {
                'family_id': family_id,
                'family_name': family_name,
                'version_label': unique_labels[index - 1],
                'version_order': index * 10,
                'is_default_version': str(member.get('id') or '').strip() == default_version_id,
                'is_versioned': True,
            }
        )
        member['preset_version'] = version_meta
        planned_members.append(member)

    return {
        'family_id': family_id,
        'family_name': family_name,
        'default_version_id': default_version_id,
        'members': planned_members,
    }


def _build_fallback_version_label(fallback_filename):
    filename = os.path.basename(fallback_filename or '')
    stem, _ = os.path.splitext(filename)
    return stem


def _safe_text(value):
    if isinstance(value, str):
        return value.strip()
    return ''


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_mtime(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _version_sort_key(item):
    version_meta = item.get('preset_version') or {}
    return (
        0 if version_meta.get('is_default_version') else 1,
        _safe_int(version_meta.get('version_order'), DEFAULT_VERSION_ORDER),
        -_coerce_mtime(item.get('mtime')),
        item.get('filename') or '',
    )
