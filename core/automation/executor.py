import logging
from core.services.card_service import (
    move_card_internal,
    modify_card_attributes_internal,
    resolve_ui_key,
    sync_card_names_internal,
)
from core.automation.forum_tag_fetcher import get_tag_fetcher, TagProcessor
from core.data.ui_store import load_ui_data
from core.context import ctx
from core.config import load_config
from core.services.tag_management_service import build_governance_feedback, build_known_tag_set, filter_governed_tags

logger = logging.getLogger(__name__)

class AutomationExecutor:
    def apply_plan(self, card_id, plan, ui_data=None):
        """
        执行计划
        plan 结构:
        {
            'move': 'Target/Path' or None,
            'add_tags': set(),
            'remove_tags': set(),
            'favorite': bool/None,
            'set_char_name_from_filename': bool,
            'set_wi_name_from_filename': bool,
            'set_filename_from_char_name': bool,
            'set_filename_from_wi_name': bool,
        }
        返回: 执行结果摘要
        """
        result = {
            "moved_to": None,
            "tags_added": [],
            "tags_removed": [],
            "fav_changed": False,
            "name_sync": None,
            "forum_tags_fetched": None  # 论坛标签抓取结果
        }
        
        current_id = card_id
        
        # 0. 执行论坛标签抓取 (如果配置了)
        forum_tags_config = plan.get('fetch_forum_tags')
        if forum_tags_config:
            # 如果没有传入ui_data，则加载
            if ui_data is None:
                ui_data = load_ui_data()
            fetch_result = self._fetch_forum_tags(current_id, forum_tags_config, ui_data)
            result["forum_tags_fetched"] = fetch_result
            # 如果成功抓取到标签，添加到add_tags中
            if fetch_result and fetch_result.get('success') and fetch_result.get('tags'):
                if 'add_tags' not in plan:
                    plan['add_tags'] = set()
                plan['add_tags'].update(fetch_result['tags'])
        
        # 1. 执行属性修改 (标签、收藏)
        # 这些操作不改变 ID，先执行
        add_tags = list(plan.get('add_tags', []))
        remove_tags = list(plan.get('remove_tags', []))
        fav = plan.get('favorite')
        
        if add_tags or remove_tags or fav is not None:
            success = modify_card_attributes_internal(current_id, add_tags, remove_tags, fav)
            if success:
                result["tags_added"] = add_tags
                result["tags_removed"] = remove_tags
                if fav is not None: result["fav_changed"] = True

        # 1.5 同步名称/文件名（可能改变 ID）
        sync_flags = {
            'set_char_name_from_filename': bool(plan.get('set_char_name_from_filename')),
            'set_wi_name_from_filename': bool(plan.get('set_wi_name_from_filename')),
            'set_filename_from_char_name': bool(plan.get('set_filename_from_char_name')),
            'set_filename_from_wi_name': bool(plan.get('set_filename_from_wi_name')),
            'desired_filename_base': None,
            'desired_filename_template': plan.get('rename_file_by_template'),
            'ui_data': ui_data,
        }
        if any([
            sync_flags['set_char_name_from_filename'],
            sync_flags['set_wi_name_from_filename'],
            sync_flags['set_filename_from_char_name'],
            sync_flags['set_filename_from_wi_name'],
            bool(sync_flags['desired_filename_template']),
        ]):
            ok, new_id, msg, sync_details = sync_card_names_internal(current_id, **sync_flags)
            sync_result = dict(sync_details or {})
            sync_result['success'] = bool(ok)
            sync_result['msg'] = msg
            sync_result['new_id'] = new_id
            result['name_sync'] = sync_result

            if ok:
                current_id = new_id
            else:
                logger.warning(f"Automation name sync failed for {card_id}: {msg}")
                result["final_id"] = current_id
                return result

        # 2. 执行移动 (最后执行，因为会改变 ID)
        target_folder = plan.get('move')
        if target_folder is not None:
            # 如果目标是当前目录，跳过
            # 这需要调用者判断，或者 move_card_internal 会处理
            success, new_id, msg = move_card_internal(current_id, target_folder)
            if success:
                current_id = new_id
                result["moved_to"] = target_folder
            else:
                logger.warning(f"Automation move failed for {card_id}: {msg}")

        result["final_id"] = current_id
        return result
    
    def _fetch_forum_tags(self, card_id, config, ui_data=None):
        """
        从论坛URL抓取标签
        URL从ui_data.json中的link字段获取（用户在界面中设置的超链接）

        config 结构: {
            'exclude_tags': ['其他'],  # 要排除的标签
            'replace_rules': {'其他': '杂项'},  # 替换规则
            'merge_mode': 'merge'  # 'merge' 合并, 'replace' 替换
        }
        """
        try:
            # 获取卡片数据
            card_data = None
            if ctx.cache and card_id in ctx.cache.id_map:
                card_data = ctx.cache.id_map[card_id]

            if not card_data:
                logger.error(f"无法获取卡片数据: {card_id}")
                return {'success': False, 'error': '无法获取卡片数据', 'tags': []}

            # 从ui_data获取URL（用户设置的超链接）
            if ui_data is None:
                ui_data = load_ui_data()

            # 获取ui_key（可能是card_id或bundle_dir）
            ui_key = resolve_ui_key(card_id)
            url = None

            if ui_key and ui_key in ui_data:
                entry = ui_data[ui_key]
                # 从ui_data entry中获取link字段
                url = entry.get('link', '').strip()

            if not url:
                logger.warning(f"卡片 {card_id} (ui_key: {ui_key}) 未配置超链接")
                return {'success': False, 'error': '未配置超链接，请在卡片详情中设置来源链接', 'tags': []}

            # 抓取标签
            fetcher = get_tag_fetcher()
            fetch_result = fetcher.fetch_tags(url)

            if not fetch_result['success']:
                logger.warning(f"抓取标签失败: {fetch_result['error']}")
                return fetch_result

            # 处理标签
            cfg = load_config()
            slash_as_separator = bool(cfg.get('automation_slash_is_tag_separator', False))
            processor = TagProcessor(
                exclude_tags=config.get('exclude_tags', []),
                replace_rules=config.get('replace_rules', {}),
                slash_as_separator=slash_as_separator
            )

            processed_tags = processor.process(fetch_result['tags'])
            governed = filter_governed_tags(
                processed_tags,
                ui_data=ui_data,
                known_tags=build_known_tag_set(ui_data=ui_data),
            )
            accepted_tags = governed['accepted']

            # 根据合并模式处理
            merge_mode = config.get('merge_mode', 'merge')
            existing_tags = card_data.get('tags', [])
            final_tags = processor.merge_tags(existing_tags, accepted_tags, merge_mode)

            result = {
                'success': True,
                'tags': final_tags,
                'original_tags': fetch_result['tags'],
                'processed_tags': processed_tags,
                'governed_tags': accepted_tags,
                'title': fetch_result.get('title'),
                'merge_mode': merge_mode
            }
            result.update(build_governance_feedback(governed))
            return result

        except Exception as e:
            logger.error(f"抓取论坛标签时出错: {e}")
            return {'success': False, 'error': str(e), 'tags': []}
