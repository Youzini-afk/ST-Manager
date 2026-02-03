"""
ST Manager API v2 - 备份与同步接口

为前端插件提供备份、恢复、同步等功能的 REST API
"""

import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from core.config import load_config
from core.services.backup_service import backup_service
from core.context import ctx

logger = logging.getLogger(__name__)

bp = Blueprint('api_v2', __name__, url_prefix='/api/v2')


# ============ 健康检查 ============

@bp.route('/health', methods=['GET', 'POST'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat()
    })


# ============ 统计接口 ============

@bp.route('/stats', methods=['GET'])
def get_stats():
    """
    获取资源统计信息
    
    返回:
    {
        "characters": 42,
        "worldbooks": 10,
        "presets": 5,
        "regexScripts": 3
    }
    """
    try:
        stats = {
            'characters': 0,
            'worldbooks': 0,
            'presets': 0,
            'regexScripts': 0
        }
        
        # 从缓存获取角色卡数量
        if ctx.cache and ctx.cache.cards:
            stats['characters'] = len(ctx.cache.cards)
        
        # 世界书、预设、正则脚本使用文件系统统计
        config = load_config()
        
        # 获取项目根目录（用于处理相对路径）
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        def resolve_path(path):
            """将相对路径转为绝对路径"""
            if not path:
                return ''
            if os.path.isabs(path):
                return path
            return os.path.join(base_dir, path)
        
        # 世界书数量
        world_info_dir = resolve_path(config.get('world_info_dir', ''))
        if world_info_dir and os.path.isdir(world_info_dir):
            wi_files = [f for f in os.listdir(world_info_dir) if f.endswith('.json')]
            stats['worldbooks'] = len(wi_files)
        
        # 预设数量
        presets_dir = resolve_path(config.get('presets_dir', ''))
        if presets_dir and os.path.isdir(presets_dir):
            preset_files = [f for f in os.listdir(presets_dir) if f.endswith('.json')]
            stats['presets'] = len(preset_files)
        
        # 正则脚本数量
        regex_dir = resolve_path(config.get('regex_dir', ''))
        if regex_dir and os.path.isdir(regex_dir):
            regex_files = [f for f in os.listdir(regex_dir) if f.endswith('.json')]
            stats['regexScripts'] = len(regex_files)
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'characters': 0,
            'worldbooks': 0,
            'presets': 0,
            'regexScripts': 0
        }), 500


# ============ 正则脚本接口 ============

@bp.route('/regex/list', methods=['GET'])
def list_regex_scripts():
    """
    获取正则脚本列表
    
    返回:
    {
        "success": true,
        "items": [
            {"name": "script1.json", "enabled": true, ...},
            ...
        ]
    }
    """
    try:
        config = load_config()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        regex_dir = config.get('regex_dir', '')
        if regex_dir and not os.path.isabs(regex_dir):
            regex_dir = os.path.join(base_dir, regex_dir)
        
        items = []
        if regex_dir and os.path.isdir(regex_dir):
            for f in os.listdir(regex_dir):
                if not f.endswith('.json'):
                    continue
                full_path = os.path.join(regex_dir, f)
                if not os.path.isfile(full_path):
                    continue
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    
                    # 可能是单个脚本或脚本数组
                    if isinstance(data, list):
                        for script in data:
                            items.append({
                                'id': script.get('id', f),
                                'name': script.get('scriptName', f.replace('.json', '')),
                                'enabled': script.get('disabled', False) == False,
                                'findRegex': script.get('findRegex', ''),
                                'replaceString': script.get('replaceString', ''),
                                'filename': f
                            })
                    else:
                        items.append({
                            'id': data.get('id', f),
                            'name': data.get('scriptName', f.replace('.json', '')),
                            'enabled': data.get('disabled', False) == False,
                            'findRegex': data.get('findRegex', ''),
                            'replaceString': data.get('replaceString', ''),
                            'filename': f
                        })
                except Exception as parse_err:
                    logger.warning(f"解析正则脚本失败 {f}: {parse_err}")
                    items.append({
                        'id': f,
                        'name': f.replace('.json', ''),
                        'enabled': False,
                        'filename': f,
                        'error': str(parse_err)
                    })
        
        return jsonify({
            'success': True,
            'items': items,
            'count': len(items)
        })
    except Exception as e:
        logger.error(f"获取正则脚本列表失败: {e}")
        return jsonify({
            'success': False,
            'items': [],
            'error': str(e)
        }), 500


# ============ 备份相关接口 ============

@bp.route('/backup/trigger', methods=['POST'])
def trigger_backup():
    """
    触发手动备份
    
    请求体:
    {
        "resources": ["characters", "worldbooks", ...],  // 可选，默认全部
        "path": "E:/Backups/ST-Data",  // 可选，使用配置中的路径
        "incremental": true  // 可选，是否增量备份
    }
    """
    try:
        data = request.get_json() or {}
        resources = data.get('resources')
        backup_path = data.get('path')
        incremental = data.get('incremental', False)
        
        result = backup_service.trigger_backup(
            resources=resources,
            backup_path=backup_path,
            incremental=incremental
        )
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"触发备份失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/backup/list', methods=['GET'])
def list_backups():
    """获取备份列表"""
    try:
        backups = backup_service.list_backups()
        return jsonify(backups)
    except Exception as e:
        logger.error(f"获取备份列表失败: {e}")
        return jsonify([]), 500


@bp.route('/backup/restore', methods=['POST'])
def restore_backup():
    """
    从备份恢复
    
    请求体:
    {
        "backupId": "20240101_120000"
    }
    """
    try:
        data = request.get_json() or {}
        backup_id = data.get('backupId')
        
        if not backup_id:
            return jsonify({
                'success': False,
                'message': '缺少 backupId 参数'
            }), 400
        
        result = backup_service.restore_backup(backup_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/backup/delete', methods=['DELETE'])
def delete_backup():
    """
    删除备份
    
    请求体:
    {
        "backupId": "20240101_120000"
    }
    """
    try:
        data = request.get_json() or {}
        backup_id = data.get('backupId')
        
        if not backup_id:
            return jsonify({
                'success': False,
                'message': '缺少 backupId 参数'
            }), 400
        
        result = backup_service.delete_backup(backup_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/backup/schedule', methods=['GET'])
def get_backup_schedule():
    """获取备份计划"""
    try:
        schedule = backup_service.get_schedule()
        return jsonify(schedule)
    except Exception as e:
        logger.error(f"获取备份计划失败: {e}")
        return jsonify({
            'enabled': False,
            'type': 'disabled',
            'hour': 3,
            'retentionDays': 30
        })


@bp.route('/backup/schedule', methods=['POST'])
def set_backup_schedule():
    """
    设置备份计划
    
    请求体:
    {
        "enabled": true,
        "type": "daily" | "weekly",
        "hour": 3,
        "dayOfWeek": 0,  // 0=周日, 仅 weekly 时使用
        "retentionDays": 30
    }
    """
    try:
        data = request.get_json() or {}
        result = backup_service.set_schedule(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"设置备份计划失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============ 配置相关接口 ============

@bp.route('/config', methods=['GET'])
def get_config():
    """获取插件配置"""
    try:
        config = load_config()
        # 过滤敏感信息
        safe_config = {
            'st_data_path': config.get('st_data_path', ''),
            'backup': config.get('backup', {}),
            'auto_sync': config.get('auto_sync', True),
            'track_changes': config.get('track_changes', True),
            'sync_interval': config.get('sync_interval', 60),
            'page_size': config.get('page_size', 50),
            'show_thumbnails': config.get('show_thumbnails', True),
            'compact_mode': config.get('compact_mode', False),
        }
        return jsonify(safe_config)
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({}), 500


@bp.route('/config', methods=['POST'])
def update_config():
    """更新插件配置"""
    try:
        data = request.get_json() or {}
        
        # 加载现有配置
        config = load_config()
        
        # 更新允许的字段
        allowed_fields = [
            'st_data_path', 'backup', 'auto_sync', 'track_changes',
            'sync_interval', 'page_size', 'show_thumbnails', 'compact_mode'
        ]
        
        for field in allowed_fields:
            if field in data:
                config[field] = data[field]
        
        # 保存配置
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============ 同步相关接口 ============

@bp.route('/sync/to-st', methods=['POST'])
def sync_to_st():
    """
    同步资源到酒馆
    
    请求体:
    {
        "type": "character" | "worldbook" | "preset" | "regex",
        "id": "资源ID"
    }
    """
    try:
        data = request.get_json() or {}
        resource_type = data.get('type')
        resource_id = data.get('id')
        
        if not resource_type or not resource_id:
            return jsonify({
                'success': False,
                'message': '缺少 type 或 id 参数'
            }), 400
        
        # TODO: 实现具体的同步逻辑
        # 从本地数据库/缓存复制到酒馆目录
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"同步到酒馆失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/sync/from-st', methods=['POST'])
def sync_from_st():
    """
    从酒馆同步资源
    
    请求体:
    {
        "type": "character" | "worldbook" | "preset" | "regex" | "all"
    }
    """
    try:
        data = request.get_json() or {}
        resource_type = data.get('type', 'all')
        
        # TODO: 实现具体的同步逻辑
        # 从酒馆目录读取并更新本地缓存
        
        return jsonify({
            'success': True,
            'count': 0  # 同步的资源数量
        })
    except Exception as e:
        logger.error(f"从酒馆同步失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============ 变更追踪接口 ============

@bp.route('/track-change', methods=['POST'])
def track_change():
    """
    追踪资源变更（用于增量备份）
    
    请求体:
    {
        "type": "character",
        "id": "资源ID",
        "timestamp": 1704067200000
    }
    """
    try:
        data = request.get_json() or {}
        resource_type = data.get('type')
        resource_id = data.get('id')
        timestamp = data.get('timestamp')
        
        if not resource_type or not resource_id:
            return jsonify({
                'success': False,
                'message': '缺少 type 或 id 参数'
            }), 400
        
        # 记录变更
        backup_service.track_change(resource_type, resource_id, timestamp)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"追踪变更失败: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
