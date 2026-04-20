import logging
import os
import tempfile

from flask import Blueprint, jsonify, request, send_file

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
        try:
            os.remove(temp_path)
        except OSError:
            pass


@bp.route('/update-variant', methods=['POST'])
def update_variant():
    payload = request.get_json(silent=True) or {}
    package_id = str(payload.get('package_id') or '').strip()
    variant_id = str(payload.get('variant_id') or '').strip()
    platform = str(payload.get('platform') or '').strip().lower()
    if not package_id or not variant_id:
        return _error('缺少 package_id 或 variant_id')
    if platform not in ('pc', 'mobile', 'dual'):
        return _error('无效的端类型')

    try:
        item = get_beautify_service().update_variant(package_id, variant_id, platform)
        return jsonify({'success': True, 'item': item})
    except ValueError as exc:
        return _error(str(exc))


@bp.route('/delete-package', methods=['POST'])
def delete_package():
    payload = request.get_json(silent=True) or {}
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
