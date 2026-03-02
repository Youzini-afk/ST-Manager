import re


def split_action_tags(value, slash_as_separator=False):
    """Split automation action tag text into a clean tag list."""
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(split_action_tags(item, slash_as_separator=slash_as_separator))

        dedup = []
        seen = set()
        for tag in out:
            if tag in seen:
                continue
            seen.add(tag)
            dedup.append(tag)
        return dedup

    text = str(value)
    pattern = r'[|/]'
    if not slash_as_separator:
        pattern = r'[|]'

    parts = re.split(pattern, text)
    cleaned = [p.strip() for p in parts if p and p.strip()]

    dedup = []
    seen = set()
    for tag in cleaned:
        if tag in seen:
            continue
        seen.add(tag)
        dedup.append(tag)
    return dedup
