/**
 * static/js/components/batchTagModal.js
 * 批量标签操作组件
 */

import { batchUpdateTags } from '../api/system.js';

export default function batchTagModal() {
    return {
        // === 本地状态 ===
        showBatchTagModal: false,
        batchTagPickerSearch: "",
        
        // 输入框状态
        batchTagInputAdd: "",
        batchTagInputRemove: "",
        
        // 批量选择器状态 (从池中选)
        batchSelectedTags: [],

        // 分类筛选与显示
        batchCategoryFilterInclude: [],
        batchCategoryFilterExclude: [],
        mixedCategoryView: true,
        
        // 目标卡片 IDs
        targetIds: [],

        init() {
            // 监听打开事件
            window.addEventListener('open-batch-tag-modal', (e) => {
                // e.detail.ids 来自 Header 发出的事件
                this.targetIds = e.detail && e.detail.ids ? e.detail.ids : [];
                
                if (this.targetIds.length === 0) {
                    // 如果事件没传，尝试直接读 Store (容错)
                    this.targetIds = this.$store.global.viewState.selectedIds || [];
                }

                if (this.targetIds.length === 0) {
                    alert("未选择任何卡片");
                    return;
                }

                // 重置表单
                this.batchTagInputAdd = "";
                this.batchTagInputRemove = "";
                this.batchTagPickerSearch = "";
                this.batchSelectedTags = [];
                this.batchCategoryFilterInclude = [];
                this.batchCategoryFilterExclude = [];
                this.mixedCategoryView = true;
                this.showBatchTagModal = true;
            });
        },

        // === 计算属性：过滤标签池 ===
        get filteredBatchTagPool() {
            const pool = this.$store.global.globalTagsPool || [];
            if (!this.batchTagPickerSearch) return pool;
            return pool.filter(t => t.toLowerCase().includes(this.batchTagPickerSearch.toLowerCase()));
        },

        get batchBaseTagGroups() {
            const store = this.$store?.global;
            if (!store || typeof store.groupTagsByTaxonomy !== 'function') return [];
            return store.groupTagsByTaxonomy(this.filteredBatchTagPool || []);
        },

        get batchFilterCategoryNames() {
            return (this.batchBaseTagGroups || []).map(group => group.category);
        },

        get batchFilteredTagGroups() {
            const includeSet = new Set(this.batchCategoryFilterInclude || []);
            const excludeSet = new Set(this.batchCategoryFilterExclude || []);
            const groups = this.batchBaseTagGroups || [];

            return groups.filter((group) => {
                const category = String(group.category || '').trim();
                if (!category) return false;
                if (excludeSet.has(category)) return false;
                if (includeSet.size > 0 && !includeSet.has(category)) return false;
                return true;
            });
        },

        get batchFilteredMixedTagPool() {
            const includeSet = new Set(this.batchCategoryFilterInclude || []);
            const excludeSet = new Set(this.batchCategoryFilterExclude || []);
            const pool = this.filteredBatchTagPool || [];

            if (includeSet.size === 0 && excludeSet.size === 0) {
                return pool;
            }

            return pool.filter((tag) => {
                const category = this.getTagCategory(tag);
                if (excludeSet.has(category)) return false;
                if (includeSet.size > 0 && !includeSet.has(category)) return false;
                return true;
            });
        },

        get batchVisibleTagCount() {
            if (this.mixedCategoryView) return this.batchFilteredMixedTagPool.length;
            return this.batchFilteredTagGroups.reduce((acc, group) => acc + (group.tags || []).length, 0);
        },

        get isBatchCategoryFilterAllMixed() {
            return this.mixedCategoryView
                && this.batchCategoryFilterInclude.length === 0
                && this.batchCategoryFilterExclude.length === 0;
        },

        // === 选择器操作 ===

        getTagChipStyle(tag) {
            return this.$store.global.getTagChipStyle(tag);
        },

        getTagCategory(tag) {
            return this.$store.global.getTagCategory(tag);
        },

        getCategoryColor(category) {
            return this.$store.global.getCategoryColor(category);
        },

        getBatchCategoryFilterState(category) {
            if (this.batchCategoryFilterInclude.includes(category)) return 'included';
            if (this.batchCategoryFilterExclude.includes(category)) return 'excluded';
            return 'none';
        },

        toggleBatchCategoryFilter(category, event = null) {
            const name = String(category || '').trim();
            if (!name) return;

            const forceExclude = !!(event && event.shiftKey);
            const include = [...(this.batchCategoryFilterInclude || [])];
            const exclude = [...(this.batchCategoryFilterExclude || [])];

            const inInclude = include.indexOf(name);
            const inExclude = exclude.indexOf(name);

            if (forceExclude) {
                if (inInclude > -1) include.splice(inInclude, 1);
                if (inExclude === -1) exclude.push(name);
            } else if (inInclude > -1) {
                include.splice(inInclude, 1);
                if (inExclude === -1) exclude.push(name);
            } else if (inExclude > -1) {
                exclude.splice(inExclude, 1);
            } else {
                include.push(name);
            }

            this.batchCategoryFilterInclude = include;
            this.batchCategoryFilterExclude = exclude;
        },

        showAllBatchCategoriesMixed() {
            this.batchCategoryFilterInclude = [];
            this.batchCategoryFilterExclude = [];
            this.mixedCategoryView = true;
        },

        toggleBatchCategoryView() {
            this.mixedCategoryView = !this.mixedCategoryView;
        },

        toggleBatchSelectTag(tag) {
            const i = this.batchSelectedTags.indexOf(tag);
            if (i > -1) this.batchSelectedTags.splice(i, 1);
            else this.batchSelectedTags.push(tag);
        },

        // === 执行批量操作 ===

        // 1. 添加 (从输入框或选择器)
        // 注意：HTML 中通常有两个入口，一个是输入框回车调用 batchAddTag，一个是“应用选择”调用 applyBatchAddTags
        
        batchAddTag(tag) {
            const val = (tag || this.batchTagInputAdd || "").trim();
            if (!val) return;
            
            this._performBatchUpdate([val], [], "add", { triggerMerge: true });
        },

        applyBatchAddTags() {
            if (this.batchSelectedTags.length === 0) return alert("未选择任何标签");
            this._performBatchUpdate(this.batchSelectedTags, [], "add-select");
        },

        // 2. 移除
        batchRemoveTag(tag) {
            const val = (tag || this.batchTagInputRemove || "").trim();
            if (!val) return;
            
            this._performBatchUpdate([], [val], "remove");
        },

        applyBatchRemoveTags() {
            if (this.batchSelectedTags.length === 0) return alert("未选择任何标签");
            this._performBatchUpdate([], this.batchSelectedTags, "remove-select");
        },

        // 内部统一执行函数
        _performBatchUpdate(addList, removeList, mode, options = {}) {
            if (this.targetIds.length === 0) {
                alert("未选择任何卡片");
                return;
            }

            batchUpdateTags({
                card_ids: this.targetIds,
                add: addList,
                remove: removeList,
                trigger_merge: !!options.triggerMerge
            })
            .then(res => {
                if (res.success) {
                    let message = "成功更新 " + res.updated + " 张卡片";
                    const merge = res.tag_merge || {};
                    if (merge.cards) {
                        message += `\n全局标签合并已应用到 ${merge.cards} 张卡片`;
                    }
                    alert(message);
                    
                    // 清理状态
                    if (mode === "add") this.batchTagInputAdd = "";
                    if (mode === "remove") this.batchTagInputRemove = "";
                    if (mode.includes("select")) this.batchSelectedTags = [];
                    
                    // 刷新列表
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                    this.showBatchTagModal = false;
                } else {
                    alert(res.msg);
                }
            });
        }
    }
}
