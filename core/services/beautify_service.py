import copy
import hashlib
import json
import logging
import os
import shutil
import time
from typing import Callable, Dict, Optional

from PIL import Image
from PIL import UnidentifiedImageError

from core.config import get_beautify_folder
from core.data.ui_store import get_beautify_library, load_ui_data, save_ui_data, set_beautify_library


logger = logging.getLogger(__name__)


class BeautifyService:
    def __init__(
        self,
        library_root: Optional[str] = None,
        ui_data_loader: Optional[Callable[[], Dict]] = None,
        ui_data_saver: Optional[Callable[[Dict], bool]] = None,
    ):
        self.library_root = os.path.abspath(library_root or get_beautify_folder())
        self._ui_data_loader = ui_data_loader or load_ui_data
        self._ui_data_saver = ui_data_saver or save_ui_data
        os.makedirs(self.library_root, exist_ok=True)

    def _project_root_for_library(self):
        normalized = self.library_root.replace('\\', '/').rstrip('/')
        suffix = '/data/library/beautify'
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
        return os.path.dirname(os.path.dirname(os.path.dirname(self.library_root)))

    def _load_ui_data(self):
        data = self._ui_data_loader() or {}
        if not isinstance(data, dict):
            return {}
        return data

    def _save_library(self, ui_data: Dict, library_payload: Dict):
        changed = set_beautify_library(ui_data, library_payload)
        if changed:
            self._ui_data_saver(copy.deepcopy(ui_data))
        return changed

    def load_library(self):
        return get_beautify_library(self._load_ui_data())

    def get_global_settings(self):
        return copy.deepcopy(self.load_library().get('global_settings', {}))

    def list_packages(self):
        library = self.load_library()
        packages = []
        for package_info in library.get('packages', {}).values():
            variants = list(package_info.get('variants', {}).values())
            wallpapers = list(package_info.get('wallpapers', {}).values())
            screenshots = list(package_info.get('screenshots', {}).values())
            packages.append(
                {
                    'id': package_info['id'],
                    'name': package_info.get('name') or package_info['id'],
                    'author': package_info.get('author', ''),
                    'variant_count': len(variants),
                    'wallpaper_count': len(wallpapers),
                    'screenshot_count': len(screenshots),
                    'platforms': sorted({variant.get('platform', 'dual') for variant in variants}),
                    'updated_at': package_info.get('updated_at', 0),
                    'wallpaper_previews': [wallpaper.get('file', '') for wallpaper in wallpapers[:3]],
                }
            )
        return sorted(packages, key=lambda item: (-(item.get('updated_at') or 0), item['name'].lower()))

    def get_package(self, package_id: str):
        library = self.load_library()
        package = library.get('packages', {}).get(str(package_id or '').strip())
        if not package:
            return None

        result = copy.deepcopy(package)
        for variant_id, variant in result.get('variants', {}).items():
            variant['theme_data'] = self._load_theme_data(variant.get('theme_file', ''))
            result['variants'][variant_id] = variant
        return result

    def import_theme(self, source_path: str, package_id: Optional[str] = None, platform: Optional[str] = None, source_name: Optional[str] = None):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError('主题文件不存在')

        theme_payload = self._load_theme_payload(source_path)
        source_hint = source_name or source_path
        guessed_platform, needs_review = self.guess_platform(source_hint, theme_payload.get('name', ''), package_name='')
        resolved_platform = self._normalize_platform(platform) or guessed_platform
        if platform:
            needs_review = False

        ui_data = self._load_ui_data()
        library = get_beautify_library(ui_data)
        packages = dict(library.get('packages', {}))

        package_name = str(theme_payload.get('name') or '').strip() or PathLike.basename_without_ext(source_hint) or '未命名主题'
        resolved_package_id = str(package_id or '').strip() or self._build_package_id(package_name, packages)
        package_info = copy.deepcopy(packages.get(resolved_package_id) or self._build_empty_package(resolved_package_id, package_name))
        package_info['name'] = package_info.get('name') or package_name

        existing_variant = self._find_variant_by_platform(package_info, resolved_platform)
        variant_id = existing_variant['id'] if existing_variant else f'var_{resolved_platform}_{self._short_hash(source_path + str(time.time()))}'
        themes_dir = os.path.join(self.library_root, 'packages', resolved_package_id, 'themes')
        os.makedirs(themes_dir, exist_ok=True)

        target_file = os.path.join(themes_dir, f'{resolved_platform}.json')
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(theme_payload, f, ensure_ascii=False, indent=2)

        preview_accuracy = 'approx' if self._theme_has_custom_css(theme_payload) else ('approx' if resolved_platform in ('pc', 'mobile') else 'base')
        relative_theme_file = os.path.relpath(target_file, self._project_root_for_library()).replace('\\', '/')
        package_info['variants'][variant_id] = {
            'id': variant_id,
            'platform': resolved_platform,
            'theme_name': str(theme_payload.get('name') or package_info['name']).strip(),
            'theme_file': relative_theme_file,
            'wallpaper_ids': list((existing_variant or {}).get('wallpaper_ids', [])),
            'preview_hint': {
                'needs_platform_review': needs_review,
                'preview_accuracy': preview_accuracy,
            },
        }
        package_info['cover_variant_id'] = package_info.get('cover_variant_id') or variant_id
        now = int(time.time())
        package_info['updated_at'] = now
        if not package_info.get('created_at'):
            package_info['created_at'] = now
        packages[resolved_package_id] = package_info
        library['packages'] = packages
        self._save_library(ui_data, library)

        return {
            'package': copy.deepcopy(package_info),
            'variant': copy.deepcopy(package_info['variants'][variant_id]),
            'theme': theme_payload,
        }

    def update_variant(self, package_id: str, variant_id: str, platform: str):
        resolved_platform = self._normalize_platform(platform)
        if not resolved_platform:
            raise ValueError('无效的端类型')

        ui_data = self._load_ui_data()
        library, package_info, variant = self._load_package_variant(ui_data, package_id, variant_id)
        if variant.get('platform') != resolved_platform:
            conflict = self._find_variant_by_platform(package_info, resolved_platform)
            if conflict and conflict.get('id') != variant_id:
                raise ValueError('目标端类型已存在，请先调整或替换现有变体')

            old_theme_path = self._resolve_project_relative_path(variant.get('theme_file', ''))
            new_theme_path = os.path.join(self.library_root, 'packages', package_info['id'], 'themes', f'{resolved_platform}.json')
            os.makedirs(os.path.dirname(new_theme_path), exist_ok=True)
            if old_theme_path and os.path.exists(old_theme_path) and os.path.abspath(old_theme_path) != os.path.abspath(new_theme_path):
                if os.path.exists(new_theme_path):
                    os.remove(new_theme_path)
                shutil.move(old_theme_path, new_theme_path)
            variant['platform'] = resolved_platform
            variant['theme_file'] = os.path.relpath(new_theme_path, self._project_root_for_library()).replace('\\', '/')

        preview_hint = copy.deepcopy(variant.get('preview_hint') or {})
        preview_hint['needs_platform_review'] = False
        variant['preview_hint'] = preview_hint

        package_info['variants'][variant_id] = variant
        package_info['updated_at'] = int(time.time())
        library['packages'][package_info['id']] = package_info
        self._save_library(ui_data, library)
        return copy.deepcopy(variant)

    def import_wallpaper(self, package_id: str, variant_id: str, source_path: str, source_name: Optional[str] = None):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError('壁纸文件不存在')

        ui_data = self._load_ui_data()
        library, package_info, variant = self._load_package_variant(ui_data, package_id, variant_id)

        wallpapers_dir = os.path.join(self.library_root, 'packages', package_info['id'], 'wallpapers')
        try:
            wallpaper = self._copy_asset_file(wallpapers_dir, source_path, source_name=source_name)
        except ValueError as exc:
            raise ValueError('壁纸文件无效') from exc

        wallpaper_id = f'wp_{self._short_hash(wallpaper["file"] + str(time.time()))}'
        package_info['wallpapers'][wallpaper_id] = {
            'id': wallpaper_id,
            'variant_id': variant_id,
            'file': wallpaper['file'],
            'filename': wallpaper['filename'],
            'width': wallpaper['width'],
            'height': wallpaper['height'],
            'mtime': wallpaper['mtime'],
        }

        wallpaper_ids = list(variant.get('wallpaper_ids', []))
        wallpaper_ids.append(wallpaper_id)
        variant['wallpaper_ids'] = wallpaper_ids
        package_info['variants'][variant_id] = variant
        package_info['updated_at'] = int(time.time())
        library['packages'][package_info['id']] = package_info
        self._save_library(ui_data, library)

        return {
            'package': copy.deepcopy(package_info),
            'variant': copy.deepcopy(variant),
            'wallpaper': copy.deepcopy(package_info['wallpapers'][wallpaper_id]),
        }

    def update_global_settings(self, payload: Optional[Dict] = None):
        ui_data = self._load_ui_data()
        library = get_beautify_library(ui_data)
        global_settings = copy.deepcopy(library.get('global_settings') or {})
        identities = copy.deepcopy(global_settings.get('identities') or {})
        source = payload if isinstance(payload, dict) else {}

        if source.get('clear_wallpaper') is True:
            self._remove_asset_file((global_settings.get('wallpaper') or {}).get('file', ''))
            global_settings['wallpaper'] = {}

        for key in ('character', 'user'):
            current_identity = copy.deepcopy(identities.get(key) or {})
            name_key = f'{key}_name'
            if name_key in source:
                current_identity['name'] = str(source.get(name_key) or '').strip()

            if source.get(f'clear_{key}_avatar') is True:
                self._remove_asset_file(current_identity.get('avatar_file', ''))
                current_identity['avatar_file'] = ''

            identities[key] = current_identity

        global_settings['identities'] = identities
        library['global_settings'] = global_settings
        self._save_library(ui_data, library)
        return copy.deepcopy(get_beautify_library(ui_data).get('global_settings', {}))

    def import_global_wallpaper(self, source_path: str, source_name: Optional[str] = None):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError('壁纸文件不存在')

        ui_data = self._load_ui_data()
        library = get_beautify_library(ui_data)
        global_settings = copy.deepcopy(library.get('global_settings') or {})
        wallpapers_dir = os.path.join(self.library_root, 'global', 'wallpapers')
        try:
            wallpaper = self._copy_asset_to_slot(wallpapers_dir, 'wallpaper', source_path, source_name=source_name)
        except ValueError as exc:
            raise ValueError('壁纸文件无效') from exc

        global_settings['wallpaper'] = wallpaper
        library['global_settings'] = global_settings
        self._save_library(ui_data, library)
        return {'wallpaper': copy.deepcopy(wallpaper)}

    def import_global_avatar(self, target: str, source_path: str, source_name: Optional[str] = None):
        return {'identity': self._import_identity_avatar(None, target, source_path, source_name=source_name)}

    def import_screenshot(self, package_id: str, source_path: str, source_name: Optional[str] = None):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError('截图文件不存在')

        ui_data = self._load_ui_data()
        library, package_info = self._load_package(ui_data, package_id)
        screenshots_dir = os.path.join(self.library_root, 'packages', package_info['id'], 'screenshots')
        try:
            screenshot = self._copy_asset_file(screenshots_dir, source_path, source_name=source_name)
        except ValueError as exc:
            raise ValueError('截图文件无效') from exc
        screenshot_id = f'shot_{self._short_hash(screenshot["file"] + str(time.time()))}'
        screenshot['id'] = screenshot_id

        screenshots = copy.deepcopy(package_info.get('screenshots') or {})
        screenshots[screenshot_id] = screenshot
        package_info['screenshots'] = screenshots
        package_info['updated_at'] = int(time.time())
        library['packages'][package_info['id']] = package_info
        self._save_library(ui_data, library)
        return {'package': copy.deepcopy(package_info), 'screenshot': copy.deepcopy(screenshot)}

    def update_package_identities(self, package_id: str, identities_payload: Optional[Dict] = None):
        ui_data = self._load_ui_data()
        library, package_info = self._load_package(ui_data, package_id)
        identity_overrides = copy.deepcopy(package_info.get('identity_overrides') or {})
        source = identities_payload if isinstance(identities_payload, dict) else {}

        for key in ('character', 'user'):
            current_identity = copy.deepcopy(identity_overrides.get(key) or {})
            name_key = f'{key}_name'
            if name_key in source:
                current_identity['name'] = str(source.get(name_key) or '').strip()

            if source.get(f'clear_{key}_avatar') is True:
                self._remove_asset_file(current_identity.get('avatar_file', ''))
                current_identity['avatar_file'] = ''

            identity_overrides[key] = current_identity

        package_info['identity_overrides'] = identity_overrides
        package_info['updated_at'] = int(time.time())
        library['packages'][package_info['id']] = package_info
        self._save_library(ui_data, library)
        return copy.deepcopy(package_info)

    def import_package_avatar(self, package_id: str, target: str, source_path: str, source_name: Optional[str] = None):
        return {
            'identity': self._import_identity_avatar(package_id, target, source_path, source_name=source_name)
        }

    def delete_package(self, package_id: str):
        ui_data = self._load_ui_data()
        library = get_beautify_library(ui_data)
        resolved_package_id = str(package_id or '').strip()
        packages = dict(library.get('packages', {}))
        if resolved_package_id not in packages:
            return False

        del packages[resolved_package_id]
        library['packages'] = packages

        package_dir = os.path.join(self.library_root, 'packages', resolved_package_id)
        if os.path.isdir(package_dir):
            shutil.rmtree(package_dir)

        self._save_library(ui_data, library)
        return True

    def get_preview_asset_path(self, subpath: str):
        normalized = str(subpath or '').replace('\\', '/').strip().lstrip('/')
        if not normalized or '..' in normalized.split('/'):
            return None

        candidate = os.path.abspath(os.path.join(self.library_root, normalized.replace('/', os.sep)))
        if os.path.commonpath([candidate, self.library_root]) != self.library_root:
            return None
        if not os.path.exists(candidate) or not os.path.isfile(candidate):
            return None
        return candidate

    def guess_platform(self, source_path: str, theme_name: str = '', package_name: str = ''):
        tokens = ' '.join(
            [
                os.path.basename(source_path or ''),
                str(theme_name or ''),
                str(package_name or ''),
            ]
        ).lower()
        if any(keyword in tokens for keyword in ('mobile', '移动', '手机')):
            return 'mobile', False
        if any(keyword in tokens for keyword in ('pc', '电脑', '桌面')):
            return 'pc', False
        if any(keyword in tokens for keyword in ('dual', '双端', '通用')):
            return 'dual', False
        return 'dual', True

    def _load_theme_payload(self, source_path: str):
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError('主题 JSON 无法解析') from exc

        if not isinstance(payload, dict):
            raise ValueError('主题 JSON 格式无效')

        if not payload.get('name'):
            raise ValueError('主题缺少 name 字段')

        if not any(key in payload for key in ('main_text_color', 'chat_tint_color', 'custom_css', 'font_scale')):
            raise ValueError('文件不是有效的 ST theme JSON')

        return payload

    def _normalize_platform(self, platform: Optional[str]):
        value = str(platform or '').strip().lower()
        if value in ('pc', 'mobile', 'dual'):
            return value
        return ''

    def _build_empty_package(self, package_id: str, package_name: str):
        return {
            'id': package_id,
            'name': package_name,
            'author': '',
            'tags': [],
            'notes': '',
            'cover_variant_id': '',
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'screenshots': {},
            'identity_overrides': {},
            'variants': {},
            'wallpapers': {},
        }

    def _build_package_id(self, package_name: str, existing_packages: Dict):
        base = self._slugify(package_name) or 'theme'
        candidate = f'pkg_{base}'
        if candidate not in existing_packages:
            return candidate
        suffix = self._short_hash(package_name + str(time.time()))
        return f'{candidate}_{suffix}'

    def _slugify(self, value: str):
        normalized = []
        for char in str(value or '').strip().lower():
            if char.isascii() and char.isalnum():
                normalized.append(char)
            elif char in (' ', '-', '_'):
                normalized.append('_')
        slug = ''.join(normalized).strip('_')
        while '__' in slug:
            slug = slug.replace('__', '_')
        return slug

    def _short_hash(self, value: str):
        return hashlib.md5(value.encode('utf-8')).hexdigest()[:8]

    def _theme_has_custom_css(self, payload: Dict):
        return bool(str(payload.get('custom_css') or '').strip())

    def _resolve_project_relative_path(self, relative_path: str):
        if not relative_path:
            return ''
        return os.path.join(self._project_root_for_library(), relative_path.replace('/', os.sep))

    def _load_package_variant(self, ui_data: Dict, package_id: str, variant_id: str):
        library, package_info = self._load_package(ui_data, package_id)
        resolved_variant_id = str(variant_id or '').strip()

        variant = copy.deepcopy(package_info.get('variants', {}).get(resolved_variant_id))
        if not variant:
            raise ValueError('变体不存在')

        return library, package_info, variant

    def _load_package(self, ui_data: Dict, package_id: str):
        library = get_beautify_library(ui_data)
        resolved_package_id = str(package_id or '').strip()
        package_info = copy.deepcopy(library.get('packages', {}).get(resolved_package_id))
        if not package_info:
            raise ValueError('美化包不存在')
        return library, package_info

    def _build_unique_filename(self, target_dir: str, filename: str):
        sanitized_name = os.path.basename(str(filename or '').replace('\\', '/'))
        base_name, ext = os.path.splitext(sanitized_name)
        safe_base = base_name.strip() or 'wallpaper'
        safe_ext = ext or '.png'
        candidate = f'{safe_base}{safe_ext}'
        if not os.path.exists(os.path.join(target_dir, candidate)):
            return candidate

        index = 1
        while True:
            candidate = f'{safe_base}-{index}{safe_ext}'
            if not os.path.exists(os.path.join(target_dir, candidate)):
                return candidate
            index += 1

    def _find_variant_by_platform(self, package_info: Dict, platform: str):
        for variant in (package_info.get('variants') or {}).values():
            if variant.get('platform') == platform:
                return copy.deepcopy(variant)
        return None

    def _normalize_identity_target(self, target: str):
        resolved_target = str(target or '').strip().lower()
        if resolved_target not in ('character', 'user'):
            raise ValueError('无效的身份类型')
        return resolved_target

    def _copy_asset_to_slot(self, target_dir: str, slot_name: str, source_path: str, source_name: Optional[str] = None):
        original_name = source_name or os.path.basename(source_path)
        _, ext = os.path.splitext(original_name or '')
        slot_filename = f'{slot_name}{ext or ".png"}'
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, slot_filename)
        temp_file = os.path.join(target_dir, f'__incoming__{slot_filename}')
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass
        shutil.copy2(source_path, temp_file)

        try:
            with Image.open(temp_file) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            self._remove_asset_file(os.path.relpath(temp_file, self._project_root_for_library()).replace('\\', '/'))
            raise ValueError('图片文件无效') from exc

        self._remove_slot_files(target_dir, slot_name, keep_filename=slot_filename)
        try:
            os.replace(temp_file, target_file)
        except OSError as exc:
            self._remove_asset_file(os.path.relpath(temp_file, self._project_root_for_library()).replace('\\', '/'))
            raise ValueError('图片文件无效') from exc

        return {
            'file': os.path.relpath(target_file, self._project_root_for_library()).replace('\\', '/'),
            'filename': slot_filename,
            'width': width,
            'height': height,
            'mtime': int(os.path.getmtime(target_file)),
        }

    def _remove_slot_files(self, target_dir: str, slot_name: str, keep_filename: str = ''):
        if not os.path.isdir(target_dir):
            return

        prefix = f'{slot_name}.'
        keep_name = str(keep_filename or '').strip().lower()
        for entry in os.listdir(target_dir):
            normalized = entry.lower()
            if not normalized.startswith(prefix):
                continue
            if keep_name and normalized == keep_name:
                continue
            try:
                os.remove(os.path.join(target_dir, entry))
            except OSError:
                continue

    def _remove_asset_file(self, relative_path: str):
        path = self._resolve_project_relative_path(relative_path)
        if not path or not os.path.isfile(path):
            return
        try:
            if os.path.commonpath([os.path.abspath(path), self.library_root]) != self.library_root:
                return
        except ValueError:
            return
        try:
            os.remove(path)
        except OSError:
            return

    def _copy_asset_file(self, target_dir: str, source_path: str, source_name: Optional[str] = None):
        os.makedirs(target_dir, exist_ok=True)
        original_name = source_name or os.path.basename(source_path)
        target_name = self._build_unique_filename(target_dir, original_name)
        target_file = os.path.join(target_dir, target_name)
        shutil.copy2(source_path, target_file)

        try:
            with Image.open(target_file) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            self._remove_asset_file(os.path.relpath(target_file, self._project_root_for_library()).replace('\\', '/'))
            raise ValueError('图片文件无效') from exc

        return {
            'file': os.path.relpath(target_file, self._project_root_for_library()).replace('\\', '/'),
            'filename': target_name,
            'width': width,
            'height': height,
            'mtime': int(os.path.getmtime(target_file)),
        }

    def _import_identity_avatar(self, package_id: Optional[str], target: str, source_path: str, source_name: Optional[str] = None):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError('头像文件不存在')

        resolved_target = self._normalize_identity_target(target)
        ui_data = self._load_ui_data()
        library = get_beautify_library(ui_data)

        if package_id is None:
            global_settings = copy.deepcopy(library.get('global_settings') or {})
            identities = copy.deepcopy(global_settings.get('identities') or {})
            identity = copy.deepcopy(identities.get(resolved_target) or {})
            avatars_dir = os.path.join(self.library_root, 'global', 'avatars')
            try:
                identity['avatar_file'] = self._copy_asset_to_slot(
                    avatars_dir,
                    resolved_target,
                    source_path,
                    source_name=source_name,
                )['file']
            except ValueError as exc:
                raise ValueError('头像文件无效') from exc
            identities[resolved_target] = identity
            global_settings['identities'] = identities
            library['global_settings'] = global_settings
        else:
            library, package_info = self._load_package(ui_data, package_id)
            identity_overrides = copy.deepcopy(package_info.get('identity_overrides') or {})
            identity = copy.deepcopy(identity_overrides.get(resolved_target) or {})
            avatars_dir = os.path.join(self.library_root, 'packages', package_info['id'], 'avatars')
            try:
                identity['avatar_file'] = self._copy_asset_to_slot(
                    avatars_dir,
                    resolved_target,
                    source_path,
                    source_name=source_name,
                )['file']
            except ValueError as exc:
                raise ValueError('头像文件无效') from exc
            identity_overrides[resolved_target] = identity
            package_info['identity_overrides'] = identity_overrides
            package_info['updated_at'] = int(time.time())
            library['packages'][package_info['id']] = package_info

        self._save_library(ui_data, library)
        if package_id is None:
            return copy.deepcopy(get_beautify_library(ui_data).get('global_settings', {}).get('identities', {}).get(resolved_target, {}))
        return copy.deepcopy(get_beautify_library(ui_data).get('packages', {}).get(str(package_id).strip(), {}).get('identity_overrides', {}).get(resolved_target, {}))

    def _load_theme_data(self, theme_file: str):
        path = self._resolve_project_relative_path(theme_file)
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f'读取美化主题失败: {e}')
            return {}


class PathLike:
    @staticmethod
    def basename_without_ext(path: str):
        return os.path.splitext(os.path.basename(path or ''))[0].strip()
