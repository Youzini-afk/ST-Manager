"""
Cross-platform path helpers.

These helpers treat Windows-style absolute paths (e.g. ``D:/data/...`` or
``D:\\data\\...``) as absolute even when the code is running on POSIX, so that
config values and source paths produced by SillyTavern on Windows can be
classified and matched without accidentally being resolved relative to the
POSIX current working directory.
"""

import os


def _has_windows_drive(path: str) -> bool:
    """Check whether path starts with a Windows-style drive letter."""
    if not isinstance(path, str) or len(path) < 2:
        return False
    return path[0].isalpha() and path[1] == ':'


def _is_windows_abs_path(path: str) -> bool:
    """Check whether path looks like an absolute Windows drive path."""
    if not isinstance(path, str):
        return False
    stripped = path.lstrip()
    return _has_windows_drive(stripped) and len(stripped) >= 3 and stripped[2] in ('\\', '/')


def _collapse_path_parts(value: str) -> list[str]:
    """Split a forward-slash path and collapse '.' / '..' components."""
    parts = value.split('/')
    collapsed: list[str] = []
    for part in parts:
        if part == '' or part == '.':
            continue
        if part == '..':
            if collapsed and collapsed[-1] != '..':
                collapsed.pop()
            else:
                collapsed.append('..')
        else:
            collapsed.append(part)
    return collapsed


def _normalize_windows_path_keep_drive_case(path: str) -> str:
    """
    Normalize a Windows-style path to forward slashes and collapse '.' / '..'.
    The drive letter case is preserved.  Used for runtime path comparisons that
    must not add the POSIX cwd prefix.
    """
    value = str(path or '').strip().replace('\\', '/')
    if not value:
        return ''

    drive = ''
    if _has_windows_drive(value):
        drive = value[:2]
        value = value[2:]

    collapsed = _collapse_path_parts(value)
    if not collapsed:
        return f'{drive}/' if drive else ''
    return f'{drive}/' + '/'.join(collapsed)


def _normalize_storage_path_key(path: str) -> str:
    """
    Normalize a path into a stable, case-insensitive lookup key.
    Backslashes become forward slashes, '.' / '..' are collapsed, and the whole
    path is lowercased so that Windows paths from SillyTavern match consistently.
    """
    return _normalize_windows_path_keep_drive_case(path).lower()


def _resolve_abs_without_cwd(path: str) -> str:
    """
    Return an absolute path string without adding the POSIX cwd prefix to a
    Windows absolute path.  POSIX absolute paths and relative paths still go
    through os.path.normpath.
    """
    value = str(path or '').strip()
    if not value or value == '.':
        return ''
    if _is_windows_abs_path(value):
        return _normalize_windows_path_keep_drive_case(value)
    return os.path.normpath(value)


def _runtime_relpath(path: str, base: str) -> str:
    """
    Compute a relative path from base to path using normalized, case-insensitive
    keys for containment while preserving the original normalized case in the
    returned relative path. Works for Windows-style absolute paths on POSIX.
    """
    norm_path = _normalize_windows_path_keep_drive_case(path)
    norm_base = _normalize_windows_path_keep_drive_case(base)
    if not norm_path or not norm_base:
        return ''
    lc_path = norm_path.lower()
    lc_base = norm_base.lower()
    if lc_path == lc_base:
        return ''
    if not lc_path.startswith(lc_base + '/'):
        return ''
    return norm_path[len(norm_base) + 1:]


def _is_under_runtime_dir(path: str, base: str) -> bool:
    """Check whether path is under base, supporting Windows paths on POSIX."""
    norm_path = _normalize_storage_path_key(path)
    norm_base = _normalize_storage_path_key(base)
    if not norm_path or not norm_base:
        return False
    return norm_path == norm_base or norm_path.startswith(norm_base + '/')


def _join_preserve_style(root: str, *parts: str) -> str:
    """
    Join path parts while preserving the separator style of root.
    Windows absolute roots use backslashes; everything else uses os.path.join.
    """
    root = str(root or '').rstrip('\\/')
    rel = '/'.join(str(part or '').strip('\\/').replace('\\', '/') for part in parts)
    if not root:
        return rel.replace('/', os.sep)
    if not rel:
        return root
    if _is_windows_abs_path(root):
        root_win = root.replace('/', '\\').rstrip('\\')
        return f"{root_win}\\{rel.replace('/', '\\')}"
    return os.path.normpath(os.path.join(root, rel.replace('/', os.sep)))
