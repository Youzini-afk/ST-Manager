from core.automation.constants import (
    ACT_ADD_TAG,
    ACT_RENAME_FILE_BY_TEMPLATE,
    ACT_SET_FILENAME_FROM_CHAR_NAME,
    ACT_SET_FILENAME_FROM_WI_NAME,
    ACT_SPLIT_CATEGORY_TO_TAGS,
    TRIGGER_CONTEXT_ALLOWED_ACTIONS,
    TRIGGER_CONTEXT_AUTO_IMPORT,
    TRIGGER_CONTEXT_CARD_UPDATE,
    TRIGGER_CONTEXT_LINK_UPDATE,
    TRIGGER_CONTEXT_MANUAL_RUN,
    TRIGGER_CONTEXT_TAG_EDIT,
)


def _empty_observability():
    return {
        'category_tag_expansions': [],
        'suppressed_filename_action_conflicts': [],
        'noop_rename_reasons': [],
    }


def _normalize_category_segments(category):
    category_text = str(category or '').replace('\\', '/')
    return [segment.strip() for segment in category_text.split('/') if segment.strip()]


def _normalize_excluded_segments(raw_value):
    values = raw_value if isinstance(raw_value, list) else []
    normalized = []
    seen = set()

    for value in values:
        text = str(value or '').strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)

    return normalized, seen


def _expand_split_category_action(action, card_snapshot):
    action_value = action.get('value')
    config = action_value if isinstance(action_value, dict) else {}
    excluded_segments, excluded_lookup = _normalize_excluded_segments(config.get('exclude_segments'))
    source_category = str((card_snapshot or {}).get('category') or '')
    derived_tags = []

    for segment in _normalize_category_segments(source_category):
        if segment.lower() in excluded_lookup:
            continue
        if segment in derived_tags:
            continue
        derived_tags.append(segment)

    expansion = {
        'source_category': source_category,
        'derived_tags': derived_tags,
        'excluded_segments': excluded_segments,
    }
    expanded_actions = [{'type': ACT_ADD_TAG, 'value': tag} for tag in derived_tags]
    return expanded_actions, expansion


_FILENAME_ACTION_PRIORITY = {
    ACT_RENAME_FILE_BY_TEMPLATE: 3,
    ACT_SET_FILENAME_FROM_CHAR_NAME: 2,
    ACT_SET_FILENAME_FROM_WI_NAME: 1,
}


def _select_effective_filename_action(actions):
    filename_actions = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        action_type = action.get('type')
        if action_type in _FILENAME_ACTION_PRIORITY:
            filename_actions.append(dict(action))

    if not filename_actions:
        return None, []

    winner = max(
        enumerate(filename_actions),
        key=lambda item: (_FILENAME_ACTION_PRIORITY[item[1].get('type', '')], -item[0]),
    )[1]
    winner_priority = _FILENAME_ACTION_PRIORITY.get(winner.get('type'), 0)
    suppressed = []

    for action in filename_actions:
        if action is winner:
            continue
        suppressed_type = action.get('type')
        suppressed_priority = _FILENAME_ACTION_PRIORITY.get(suppressed_type, 0)
        suppressed.append({
            'reason': 'same_priority_filename_action'
            if suppressed_priority == winner_priority else 'lower_priority_filename_action',
            'winner': winner.get('type'),
            'suppressed': suppressed_type,
        })

    suppressed.sort(
        key=lambda item: (
            _FILENAME_ACTION_PRIORITY.get(item['suppressed'], 0),
            item['reason'] == 'same_priority_filename_action',
        ),
        reverse=True,
    )
    return winner, suppressed


def normalize_actions_for_context(actions, trigger_context, card_snapshot=None):
    """Filter raw automation actions by trigger context and return a normalized shell."""
    allowed_actions = TRIGGER_CONTEXT_ALLOWED_ACTIONS.get(trigger_context, set())
    filtered_actions = []
    observability = _empty_observability()
    derived_add_tags = set()
    derived_remove_tags = set()
    filename_candidates = []

    for action in actions or []:
        if not isinstance(action, dict):
            continue
        action_type = action.get('type')
        if action_type not in allowed_actions:
            continue

        action_copy = dict(action)
        if action_type == ACT_SPLIT_CATEGORY_TO_TAGS:
            expanded_actions, expansion = _expand_split_category_action(action_copy, card_snapshot)
            observability['category_tag_expansions'].append(expansion)
            for expanded_action in expanded_actions:
                filtered_actions.append(expanded_action)
                derived_add_tags.add(expanded_action['value'])
            continue

        if action_type == ACT_ADD_TAG:
            if 'value' in action_copy:
                derived_add_tags.add(action_copy['value'])
            filtered_actions.append(action_copy)
            continue

        if action_type in {
            ACT_RENAME_FILE_BY_TEMPLATE,
            ACT_SET_FILENAME_FROM_CHAR_NAME,
            ACT_SET_FILENAME_FROM_WI_NAME,
        }:
            filename_candidates.append(action_copy)
            continue

        filtered_actions.append(action_copy)

    filename_action, suppressed = _select_effective_filename_action(filename_candidates)
    if filename_action:
        filtered_actions.append(filename_action)
    observability['suppressed_filename_action_conflicts'].extend(suppressed)

    return {
        'trigger_context': trigger_context,
        'actions': filtered_actions,
        'derived': {
            'add_tags': derived_add_tags,
            'remove_tags': derived_remove_tags,
        },
        'observability': observability,
    }


__all__ = [
    'TRIGGER_CONTEXT_AUTO_IMPORT',
    'TRIGGER_CONTEXT_CARD_UPDATE',
    'TRIGGER_CONTEXT_LINK_UPDATE',
    'TRIGGER_CONTEXT_MANUAL_RUN',
    'TRIGGER_CONTEXT_TAG_EDIT',
    'normalize_actions_for_context',
]
