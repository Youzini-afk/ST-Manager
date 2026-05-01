import logging

from flask import Blueprint, jsonify, request

from core.services.remote_backup_service import (
    RemoteBackupConfigStore,
    RemoteBackupError,
    RemoteBackupService,
)


logger = logging.getLogger(__name__)

bp = Blueprint('remote_backups', __name__, url_prefix='/api/remote_backups')


def _json_payload():
    return request.get_json(silent=True) or {}


def _service():
    return RemoteBackupService()


def _error_response(error, status=500):
    logger.exception('Remote backup API error: %s', error)
    return jsonify({'success': False, 'error': str(error)}), status


@bp.route('/config', methods=['GET', 'POST'])
def config():
    store = RemoteBackupConfigStore()
    if request.method == 'GET':
        return jsonify({'success': True, 'config': store.public()})

    payload = _json_payload()
    try:
        public_config = store.save(payload)
        return jsonify({'success': True, 'config': public_config})
    except Exception as exc:
        return _error_response(exc)


@bp.route('/probe', methods=['POST'])
def probe():
    try:
        return jsonify({'success': True, 'probe': _service().probe()})
    except RemoteBackupError as exc:
        return _error_response(exc, 400)
    except Exception as exc:
        return _error_response(exc)


@bp.route('/start', methods=['POST'])
def start():
    payload = _json_payload()
    try:
        result = _service().create_backup(
            resource_types=payload.get('resource_types'),
            backup_id=payload.get('backup_id'),
            description=payload.get('description') or '',
            ingest=payload.get('ingest', True),
        )
        return jsonify({'success': True, 'backup': result})
    except RemoteBackupError as exc:
        return _error_response(exc, 400)
    except Exception as exc:
        return _error_response(exc)


@bp.route('/list', methods=['GET'])
def list_backups():
    try:
        return jsonify({'success': True, 'backups': _service().list_backups()})
    except Exception as exc:
        return _error_response(exc)


@bp.route('/detail', methods=['GET'])
@bp.route('/detail/<backup_id>', methods=['GET'])
def detail(backup_id=None):
    backup_id = backup_id or request.args.get('backup_id')
    if not backup_id:
        return jsonify({'success': False, 'error': 'backup_id is required'}), 400
    try:
        return jsonify({'success': True, 'backup': _service().get_backup_detail(backup_id)})
    except RemoteBackupError as exc:
        return _error_response(exc, 404)
    except Exception as exc:
        return _error_response(exc)


@bp.route('/restore-preview', methods=['POST'])
def restore_preview():
    payload = _json_payload()
    backup_id = payload.get('backup_id')
    if not backup_id:
        return jsonify({'success': False, 'error': 'backup_id is required'}), 400
    try:
        preview = _service().restore_preview(
            backup_id,
            resource_types=payload.get('resource_types'),
        )
        return jsonify({'success': True, 'preview': preview})
    except RemoteBackupError as exc:
        return _error_response(exc, 400)
    except Exception as exc:
        return _error_response(exc)


@bp.route('/restore', methods=['POST'])
def restore():
    payload = _json_payload()
    backup_id = payload.get('backup_id')
    if not backup_id:
        return jsonify({'success': False, 'error': 'backup_id is required'}), 400
    try:
        result = _service().restore_backup(
            backup_id,
            overwrite=bool(payload.get('overwrite')),
            resource_types=payload.get('resource_types'),
        )
        return jsonify({'success': True, 'restore': result})
    except RemoteBackupError as exc:
        return _error_response(exc, 400)
    except Exception as exc:
        return _error_response(exc)
