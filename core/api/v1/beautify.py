import logging
import os
import tempfile

from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from core.services.beautify_service import BeautifyService


logger = logging.getLogger(__name__)
bp = Blueprint('beautify', __name__, url_prefix='/api/beautify')


_service = None


def get_beautify_service():
    global _service
    if _service is None:
        _service = BeautifyService()
    return _service


def _error(message, status=400):
    return jsonify({'success': False, 'error': message}), status


def _save_upload_to_temp(upload):
    suffix = os.path.splitext(upload.filename or '')[1]
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    upload.save(temp_path)
    return temp_path


def _remove_temp_file(temp_path):
    try:
        os.remove(temp_path)
    except OSError:
        pass


def _extract_settings_update_payload(payload):
    source = payload if isinstance(payload, dict) else {}
    extracted = {
        'clear_wallpaper': source.get('clear_wallpaper') is True,
        'clear_character_avatar': source.get('clear_character_avatar') is True,
        'clear_user_avatar': source.get('clear_user_avatar') is True,
    }
    if 'character_name' in source:
        extracted['character_name'] = source.get('character_name')
    if 'user_name' in source:
        extracted['user_name'] = source.get('user_name')
    return extracted


def _extract_package_identity_update_payload(payload):
    source = payload if isinstance(payload, dict) else {}
    extracted = {
        'clear_character_avatar': source.get('clear_character_avatar') is True,
        'clear_user_avatar': source.get('clear_user_avatar') is True,
    }
    if 'character_name' in source:
        extracted['character_name'] = source.get('character_name')
    if 'user_name' in source:
        extracted['user_name'] = source.get('user_name')
    return extracted


def _reject_unsupported_keys(payload, allowed_keys):
    extra_keys = set(payload.keys()) - set(allowed_keys)
    if extra_keys:
        raise ValueError('请求体包含不支持的字段')


def _get_json_object_payload():
    try:
        payload = request.get_json(silent=False)
    except (BadRequest, UnsupportedMediaType):
        return None, _error('请求体必须是 JSON 对象')

    if not isinstance(payload, dict):
        return None, _error('请求体必须是 JSON 对象')
    return payload, None


@bp.route('/list', methods=['GET'])
def list_beautify_packages():
    service = get_beautify_service()
    return jsonify({'success': True, 'items': service.list_packages()})


@bp.route('/<package_id>', methods=['GET'])
def get_beautify_package(package_id):
    service = get_beautify_service()
    package = service.get_package(package_id)
    if not package:
        return _error('美化包不存在', status=404)
    return jsonify({'success': True, 'item': package})


@bp.route('/settings', methods=['GET'])
def get_beautify_settings():
    settings = get_beautify_service().get_global_settings()
    return jsonify({'success': True, 'item': settings})


@bp.route('/update-settings', methods=['POST'])
def update_beautify_settings():
    payload, error_response = _get_json_object_payload()
    if error_response:
        return error_response
    try:
        _reject_unsupported_keys(
            payload,
            {'character_name', 'user_name', 'clear_wallpaper', 'clear_character_avatar', 'clear_user_avatar'},
        )
        settings = get_beautify_service().update_global_settings(_extract_settings_update_payload(payload))
        return jsonify({'success': True, 'item': settings})
    except ValueError as exc:
        return _error(str(exc))


@bp.route('/import-theme', methods=['POST'])
def import_theme():
    upload = request.files.get('file')
    if not upload or not (upload.filename or '').lower().endswith('.json'):
        return _error('请上传 theme JSON 文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        service = get_beautify_service()
        result = service.import_theme(
            temp_path,
            package_id=str(request.form.get('package_id') or '').strip() or None,
            platform=str(request.form.get('platform') or '').strip() or None,
            source_name=upload.filename,
        )
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


@bp.route('/import-wallpaper', methods=['POST'])
def import_wallpaper():
    package_id = str(request.form.get('package_id') or '').strip()
    variant_id = str(request.form.get('variant_id') or '').strip()
    upload = request.files.get('file')
    if not package_id or not variant_id:
        return _error('缺少 package_id 或 variant_id')
    if not upload:
        return _error('请上传壁纸文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        service = get_beautify_service()
        result = service.import_wallpaper(package_id, variant_id, temp_path, source_name=upload.filename)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        _remove_temp_file(temp_path)


@bp.route('/import-global-wallpaper', methods=['POST'])
def import_global_wallpaper():
    upload = request.files.get('file')
    if not upload:
        return _error('请上传壁纸文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        result = get_beautify_service().import_global_wallpaper(temp_path, source_name=upload.filename)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        _remove_temp_file(temp_path)


@bp.route('/import-global-avatar', methods=['POST'])
def import_global_avatar():
    target = str(request.form.get('target') or '').strip()
    upload = request.files.get('file')
    if not target:
        return _error('缺少 target')
    if target not in ('character', 'user'):
        return _error('无效的头像目标')
    if not upload:
        return _error('请上传头像文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        result = get_beautify_service().import_global_avatar(target, temp_path, source_name=upload.filename)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        _remove_temp_file(temp_path)


@bp.route('/import-screenshot', methods=['POST'])
def import_screenshot():
    package_id = str(request.form.get('package_id') or '').strip()
    upload = request.files.get('file')
    if not package_id:
        return _error('缺少 package_id')
    if not upload:
        return _error('请上传截图文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        result = get_beautify_service().import_screenshot(package_id, temp_path, source_name=upload.filename)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        _remove_temp_file(temp_path)


@bp.route('/update-package-identities', methods=['POST'])
def update_package_identities():
    payload, error_response = _get_json_object_payload()
    if error_response:
        return error_response
    package_id = str(payload.get('package_id') or '').strip()
    if not package_id:
        return _error('缺少 package_id')

    try:
        _reject_unsupported_keys(
            payload,
            {'package_id', 'character_name', 'user_name', 'clear_character_avatar', 'clear_user_avatar'},
        )
        item = get_beautify_service().update_package_identities(
            package_id,
            _extract_package_identity_update_payload(payload),
        )
        return jsonify({'success': True, 'item': item})
    except ValueError as exc:
        return _error(str(exc))


@bp.route('/import-package-avatar', methods=['POST'])
def import_package_avatar():
    package_id = str(request.form.get('package_id') or '').strip()
    target = str(request.form.get('target') or '').strip()
    upload = request.files.get('file')
    if not package_id or not target:
        return _error('缺少 package_id 或 target')
    if target not in ('character', 'user'):
        return _error('无效的头像目标')
    if not upload:
        return _error('请上传头像文件')

    temp_path = _save_upload_to_temp(upload)
    try:
        result = get_beautify_service().import_package_avatar(
            package_id,
            target,
            temp_path,
            source_name=upload.filename,
        )
        return jsonify({'success': True, **result})
    except ValueError as exc:
        return _error(str(exc))
    finally:
        _remove_temp_file(temp_path)


@bp.route('/update-variant', methods=['POST'])
def update_variant():
    payload, error_response = _get_json_object_payload()
    if error_response:
        return error_response
    package_id = str(payload.get('package_id') or '').strip()
    variant_id = str(payload.get('variant_id') or '').strip()
    platform = str(payload.get('platform') or '').strip().lower()
    selected_wallpaper_id = str(payload.get('selected_wallpaper_id') or '').strip()
    if not package_id or not variant_id:
        return _error('缺少 package_id 或 variant_id')
    if platform and platform not in ('pc', 'mobile', 'dual'):
        return _error('无效的端类型')
    if not platform and 'selected_wallpaper_id' not in payload:
        return _error('缺少更新内容')

    try:
        item = get_beautify_service().update_variant(
            package_id,
            variant_id,
            platform=platform or None,
            selected_wallpaper_id=selected_wallpaper_id,
        )
        return jsonify({'success': True, 'item': item})
    except ValueError as exc:
        return _error(str(exc))


@bp.route('/delete-package', methods=['POST'])
def delete_package():
    payload, error_response = _get_json_object_payload()
    if error_response:
        return error_response
    package_id = str(payload.get('package_id') or '').strip()
    if not package_id:
        return _error('缺少 package_id')

    deleted = get_beautify_service().delete_package(package_id)
    if not deleted:
        return _error('美化包不存在', status=404)
    return jsonify({'success': True})


@bp.route('/preview-asset/<path:subpath>', methods=['GET'])
def preview_asset(subpath):
    asset_path = get_beautify_service().get_preview_asset_path(subpath)
    if not asset_path:
        return _error('资源不存在', status=404)
    return send_file(asset_path)
