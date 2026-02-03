"""
备份服务模块

提供定期备份、手动备份、恢复等功能
支持跨目录备份（不限于酒馆内部）
"""

import os
import json
import shutil
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from core.config import load_config

logger = logging.getLogger(__name__)


class BackupService:
    """备份服务"""
    
    # 资源类型与配置键的映射
    RESOURCE_CONFIG_KEYS = {
        'characters': 'cards_dir',
        'worldbooks': 'world_info_dir',
        'presets': 'presets_dir',
        'regexes': 'regex_dir',
        'scripts': 'scripts_dir',
        'quickreplies': 'quick_replies_dir',
    }
    
    def __init__(self):
        self._lock = threading.Lock()
        self._scheduler = None
        self._change_tracker: Dict[str, Dict[str, int]] = {}  # {type: {id: timestamp}}
        self._schedule_config: Dict[str, Any] = {
            'enabled': False,
            'type': 'disabled',
            'hour': 3,
            'dayOfWeek': 0,
            'retentionDays': 30,
        }
        self._load_schedule_config()
    
    def _load_schedule_config(self):
        """从配置加载备份计划"""
        try:
            config = load_config()
            backup_config = config.get('backup', {})
            self._schedule_config.update({
                'enabled': backup_config.get('enabled', False),
                'type': backup_config.get('schedule', 'disabled'),
                'hour': backup_config.get('hour', 3),
                'dayOfWeek': backup_config.get('day_of_week', 0),
                'retentionDays': backup_config.get('retention_days', 30),
            })
        except Exception as e:
            logger.error(f"加载备份配置失败: {e}")
    
    def _get_st_data_path(self) -> str:
        """获取酒馆数据目录"""
        config = load_config()
        st_path = config.get('st_data_path', '')
        if not st_path:
            # 尝试从 cards_dir 推断 (data/default-user/characters -> data/default-user)
            cards_dir = config.get('cards_dir', '')
            if cards_dir:
                # 如果是相对路径，转为绝对路径
                if not os.path.isabs(cards_dir):
                    from core.config import BASE_DIR
                    cards_dir = os.path.join(BASE_DIR, cards_dir)
                # 从 characters 目录向上两级得到 data/default-user
                st_path = str(Path(cards_dir).parent)
        return st_path
    
    def _get_backup_path(self) -> str:
        """获取备份目录"""
        config = load_config()
        backup_config = config.get('backup', {})
        backup_path = backup_config.get('path', '')
        if not backup_path:
            # 默认在项目根目录的 data/backups
            backup_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data', 'backups'
            )
        return backup_path
    
    def trigger_backup(
        self,
        resources: Optional[List[str]] = None,
        backup_path: Optional[str] = None,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """
        触发手动备份
        
        Args:
            resources: 要备份的资源类型列表，None 表示全部
            backup_path: 备份目标路径，None 使用配置的路径
            incremental: 是否增量备份
            
        Returns:
            备份结果字典
        """
        with self._lock:
            try:
                config = load_config()
                from core.config import BASE_DIR
                
                def resolve_path(path):
                    """将相对路径转为绝对路径"""
                    if not path:
                        return ''
                    if os.path.isabs(path):
                        return path
                    return os.path.join(BASE_DIR, path)
                
                # 确定备份目录
                target_root = backup_path or self._get_backup_path()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = os.path.join(target_root, timestamp)
                
                # 创建备份目录
                os.makedirs(backup_dir, exist_ok=True)
                
                # 确定要备份的资源
                if resources is None:
                    resources = list(self.RESOURCE_CONFIG_KEYS.keys())
                
                total_files = 0
                total_size = 0
                backed_up_resources = []
                
                for res_type in resources:
                    if res_type not in self.RESOURCE_CONFIG_KEYS:
                        logger.warning(f"未知资源类型: {res_type}")
                        continue
                    
                    # 从配置获取目录路径
                    config_key = self.RESOURCE_CONFIG_KEYS[res_type]
                    source_dir = resolve_path(config.get(config_key, ''))
                    target_dir = os.path.join(backup_dir, res_type)
                    
                    if not os.path.exists(source_dir):
                        logger.warning(f"源目录不存在: {source_dir}")
                        continue
                    
                    if incremental:
                        # 增量备份：只复制变更的文件
                        files, size = self._incremental_copy(
                            source_dir, target_dir, res_type
                        )
                    else:
                        # 全量备份
                        files, size = self._full_copy(source_dir, target_dir)
                    
                    total_files += files
                    total_size += size
                    backed_up_resources.append(res_type)
                
                # 保存备份元数据
                metadata = {
                    'id': timestamp,
                    'timestamp': datetime.now().isoformat(),
                    'resources': backed_up_resources,
                    'fileCount': total_files,
                    'sizeMb': total_size / (1024 * 1024),
                    'incremental': incremental,
                    'path': backup_dir,
                }
                
                metadata_path = os.path.join(backup_dir, 'metadata.json')
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                
                logger.info(f"备份完成: {backup_dir}, {total_files} 文件, {total_size / 1024 / 1024:.2f} MB")
                
                # 清理过期备份
                self._cleanup_old_backups(target_root)
                
                return {
                    'success': True,
                    'backupId': timestamp,
                    'path': backup_dir,
                    'timestamp': metadata['timestamp'],
                    'fileCount': total_files,
                    'sizeMb': metadata['sizeMb'],
                }
                
            except Exception as e:
                logger.error(f"备份失败: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def _full_copy(self, source: str, target: str) -> tuple:
        """全量复制目录"""
        if os.path.exists(target):
            shutil.rmtree(target)
        
        shutil.copytree(source, target)
        
        # 统计文件数和大小
        total_files = 0
        total_size = 0
        for root, dirs, files in os.walk(target):
            for f in files:
                total_files += 1
                total_size += os.path.getsize(os.path.join(root, f))
        
        return total_files, total_size
    
    def _incremental_copy(self, source: str, target: str, res_type: str) -> tuple:
        """增量复制目录"""
        os.makedirs(target, exist_ok=True)
        
        # 获取该类型的变更记录
        changes = self._change_tracker.get(res_type, {})
        last_backup_time = self._get_last_backup_time()
        
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(source):
            rel_root = os.path.relpath(root, source)
            
            for f in files:
                src_file = os.path.join(root, f)
                mtime = os.path.getmtime(src_file)
                
                # 检查文件是否在上次备份后修改
                should_copy = False
                
                if last_backup_time is None:
                    should_copy = True
                elif mtime > last_backup_time:
                    should_copy = True
                elif f in changes:
                    should_copy = True
                
                if should_copy:
                    dst_dir = os.path.join(target, rel_root) if rel_root != '.' else target
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_file = os.path.join(dst_dir, f)
                    shutil.copy2(src_file, dst_file)
                    total_files += 1
                    total_size += os.path.getsize(src_file)
        
        return total_files, total_size
    
    def _get_last_backup_time(self) -> Optional[float]:
        """获取上次备份时间"""
        backups = self.list_backups()
        if backups:
            try:
                last_timestamp = backups[0]['timestamp']
                dt = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
        return None
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """获取备份列表"""
        backup_root = self._get_backup_path()
        backups = []
        
        if not os.path.exists(backup_root):
            return backups
        
        for name in os.listdir(backup_root):
            backup_dir = os.path.join(backup_root, name)
            if not os.path.isdir(backup_dir):
                continue
            
            metadata_path = os.path.join(backup_dir, 'metadata.json')
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        backups.append(metadata)
                except Exception as e:
                    logger.error(f"读取备份元数据失败 {metadata_path}: {e}")
            else:
                # 没有元数据的旧备份
                backups.append({
                    'id': name,
                    'timestamp': name,
                    'path': backup_dir,
                    'resources': [],
                    'fileCount': 0,
                    'sizeMb': 0,
                })
        
        # 按时间倒序排列
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return backups
    
    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """从备份恢复"""
        try:
            backup_root = self._get_backup_path()
            backup_dir = os.path.join(backup_root, backup_id)
            
            if not os.path.exists(backup_dir):
                return {
                    'success': False,
                    'message': f'备份不存在: {backup_id}'
                }
            
            config = load_config()
            from core.config import BASE_DIR
            
            def resolve_path(path):
                """将相对路径转为绝对路径"""
                if not path:
                    return ''
                if os.path.isabs(path):
                    return path
                return os.path.join(BASE_DIR, path)
            
            # 读取元数据
            metadata_path = os.path.join(backup_dir, 'metadata.json')
            resources = list(self.RESOURCE_CONFIG_KEYS.keys())
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    resources = metadata.get('resources', resources)
            
            # 恢复每种资源
            restored = []
            for res_type in resources:
                source_dir = os.path.join(backup_dir, res_type)
                if not os.path.exists(source_dir):
                    continue
                
                # 从配置获取目标目录
                config_key = self.RESOURCE_CONFIG_KEYS.get(res_type)
                if not config_key:
                    continue
                target_dir = resolve_path(config.get(config_key, ''))
                if not target_dir:
                    continue
                
                # 备份当前数据（防止意外）
                if os.path.exists(target_dir):
                    temp_backup = target_dir + '.restore_backup'
                    if os.path.exists(temp_backup):
                        shutil.rmtree(temp_backup)
                    shutil.move(target_dir, temp_backup)
                
                # 恢复数据
                shutil.copytree(source_dir, target_dir)
                
                # 删除临时备份
                temp_backup = target_dir + '.restore_backup'
                if os.path.exists(temp_backup):
                    shutil.rmtree(temp_backup)
                
                restored.append(res_type)
            
            logger.info(f"恢复完成: {backup_id}, 资源: {restored}")
            
            return {
                'success': True,
                'message': f'已恢复 {len(restored)} 类资源',
                'restored': restored
            }
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """删除备份"""
        try:
            backup_root = self._get_backup_path()
            backup_dir = os.path.join(backup_root, backup_id)
            
            if not os.path.exists(backup_dir):
                return {
                    'success': False,
                    'message': f'备份不存在: {backup_id}'
                }
            
            shutil.rmtree(backup_dir)
            logger.info(f"已删除备份: {backup_id}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _cleanup_old_backups(self, backup_root: str):
        """清理过期备份"""
        retention_days = self._schedule_config.get('retentionDays', 30)
        if retention_days <= 0:
            return
        
        cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
        
        for name in os.listdir(backup_root):
            backup_dir = os.path.join(backup_root, name)
            if not os.path.isdir(backup_dir):
                continue
            
            # 检查备份时间
            metadata_path = os.path.join(backup_dir, 'metadata.json')
            try:
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        timestamp_str = metadata.get('timestamp', '')
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if dt.timestamp() < cutoff_time:
                            shutil.rmtree(backup_dir)
                            logger.info(f"清理过期备份: {name}")
                else:
                    # 使用目录修改时间
                    mtime = os.path.getmtime(backup_dir)
                    if mtime < cutoff_time:
                        shutil.rmtree(backup_dir)
                        logger.info(f"清理过期备份: {name}")
            except Exception as e:
                logger.error(f"清理备份失败 {name}: {e}")
    
    def get_schedule(self) -> Dict[str, Any]:
        """获取备份计划"""
        return self._schedule_config.copy()
    
    def set_schedule(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """设置备份计划"""
        try:
            self._schedule_config.update(config)
            
            # 保存到配置文件
            full_config = load_config()
            full_config['backup'] = {
                'enabled': config.get('enabled', False),
                'schedule': config.get('type', 'disabled'),
                'hour': config.get('hour', 3),
                'day_of_week': config.get('dayOfWeek', 0),
                'retention_days': config.get('retentionDays', 30),
                'path': full_config.get('backup', {}).get('path', self._get_backup_path()),
            }
            
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config.json'
            )
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, ensure_ascii=False, indent=4)
            
            # TODO: 更新调度器
            self._update_scheduler()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"设置备份计划失败: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _update_scheduler(self):
        """更新定时任务调度器"""
        # TODO: 使用 APScheduler 实现定时备份
        pass
    
    def track_change(self, resource_type: str, resource_id: str, timestamp: Optional[int] = None):
        """追踪资源变更"""
        if resource_type not in self._change_tracker:
            self._change_tracker[resource_type] = {}
        
        self._change_tracker[resource_type][resource_id] = timestamp or int(datetime.now().timestamp() * 1000)
    
    def start_scheduler(self):
        """启动定时备份调度器"""
        if not self._schedule_config.get('enabled'):
            return
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self._scheduler = BackgroundScheduler(daemon=True)
            
            schedule_type = self._schedule_config.get('type', 'disabled')
            hour = self._schedule_config.get('hour', 3)
            
            if schedule_type == 'daily':
                trigger = CronTrigger(hour=hour)
            elif schedule_type == 'weekly':
                day_of_week = self._schedule_config.get('dayOfWeek', 0)
                days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
                trigger = CronTrigger(day_of_week=days[day_of_week], hour=hour)
            else:
                return
            
            self._scheduler.add_job(
                self.trigger_backup,
                trigger,
                id='scheduled_backup',
                replace_existing=True
            )
            
            self._scheduler.start()
            logger.info(f"定时备份已启动: {schedule_type} at {hour}:00")
            
        except ImportError:
            logger.warning("APScheduler 未安装，定时备份不可用。请运行: pip install apscheduler")
        except Exception as e:
            logger.error(f"启动定时备份失败: {e}")
    
    def stop_scheduler(self):
        """停止定时备份调度器"""
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None
            logger.info("定时备份已停止")


# 单例实例
backup_service = BackupService()
