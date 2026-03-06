/**
 * static/js/components/tagFilterModal.js
 * 标签管理模态框 (查看全库标签/删除标签)
 */

import { deleteTags } from '../api/system.js';
import { getTagOrder } from '../api/system.js';
import { saveTagOrder } from '../api/system.js';
import { saveTagTaxonomy } from '../api/system.js';

export default function tagFilterModal() {
    return {
        // === 本地状态 ===
        showTagFilterModal: false,
        tagSearchQuery: '',
        customOrderEnabled: false,
        _syncClosing: false,

        // 排序模式（仅全量标签库）
        isSortMode: false,
        sortWorkingTags: [],
        sortOriginalTags: [],
        dragTag: null,
        dragOverTag: null,
        
        // 删除模式状态
        isDeleteMode: false,
        selectedTagsForDeletion: [],
        showCategoryMode: false,
        selectedCategoryTags: [],
        categoryDraftName: '',
        categoryDraftColor: '#64748b',
        categoryDraftOpacity: 16,
        showCategoryManager: false,
        categoryManagerDraftName: '',
        categoryManagerDraftColor: '#64748b',
        categoryManagerDraftOpacity: 16,
        categoryFilterInclude: [],
        categoryFilterExclude: [],
        mixedCategoryView: true,

        get sidebarTagsPool() {
            return this.$store.global.sidebarTagsPool || [];
        },

        get globalTagsPool() {
            return this.$store.global.globalTagsPool || [];
        },

        // 获取过滤后的标签池 (搜索用)
        get filteredTagsPool() {
            const query = this.tagSearchQuery || '';
            const pool = this.sidebarTagsPool || []; // 使用侧边栏专用池
            if (!query) return pool;
            return pool.filter(t => t.toLowerCase().includes(query.toLowerCase()));
        },

        get baseTagGroups() {
            return this.$store.global.groupTagsByTaxonomy(this.filteredTagsPool || []);
        },

        get filteredTagGroups() {
            const includeSet = new Set(this.categoryFilterInclude || []);
            const excludeSet = new Set(this.categoryFilterExclude || []);
            const groups = this.baseTagGroups || [];

            return groups.filter((group) => {
                const category = String(group.category || '').trim();
                if (!category) return false;
                if (excludeSet.has(category)) return false;
                if (includeSet.size > 0 && !includeSet.has(category)) return false;
                return true;
            });
        },

        get filteredMixedTagsPool() {
            const includeSet = new Set(this.categoryFilterInclude || []);
            const excludeSet = new Set(this.categoryFilterExclude || []);
            const pool = this.filteredTagsPool || [];

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

        get filteredVisibleTagCount() {
            if (this.isSortMode) return this.sortModeTagsPool.length;
            if (this.mixedCategoryView) return this.filteredMixedTagsPool.length;
            return this.filteredTagGroups.reduce((acc, group) => acc + (group.tags || []).length, 0);
        },

        get isCategoryFilterAllMixed() {
            return this.mixedCategoryView
                && this.categoryFilterInclude.length === 0
                && this.categoryFilterExclude.length === 0;
        },

        get filterCategoryNames() {
            return (this.baseTagGroups || []).map(group => group.category);
        },

        get availableCategoryNames() {
            const taxonomy = this.$store.global.tagTaxonomy || {};
            const categories = taxonomy.categories || {};
            const order = Array.isArray(taxonomy.category_order) ? taxonomy.category_order : [];

            const names = [];
            const seen = new Set();

            order.forEach((rawName) => {
                const name = String(rawName || '').trim();
                if (!name || seen.has(name) || !categories[name]) return;
                seen.add(name);
                names.push(name);
            });

            Object.keys(categories)
                .sort((a, b) => a.localeCompare(b, 'zh-CN', { sensitivity: 'base' }))
                .forEach((name) => {
                    if (seen.has(name)) return;
                    seen.add(name);
                    names.push(name);
                });

            return names;
        },

        get canSaveCategoryBatch() {
            return this.showCategoryMode
                && this.selectedCategoryTags.length > 0
                && String(this.categoryDraftName || '').trim().length > 0;
        },

        get categorySelectionCount() {
            return this.selectedCategoryTags.length;
        },

        get categoryManagerItems() {
            const taxonomy = this.$store.global.tagTaxonomy || {};
            const defaultCategory = String(taxonomy.default_category || '未分类').trim() || '未分类';

            const counts = {};
            const groups = this.$store.global.groupTagsByTaxonomy(this.globalTagsPool || []);
            groups.forEach((group) => {
                counts[group.category] = (group.tags || []).length;
            });

            return this.availableCategoryNames.map((name, index) => ({
                name,
                index,
                color: this.getCategoryColor(name),
                opacity: this.getCategoryOpacity(name),
                count: counts[name] || 0,
                isDefault: name === defaultCategory,
            }));
        },

        get sortModeTagsPool() {
            return this.sortWorkingTags || [];
        },

        get isSortDirty() {
            const a = this.sortWorkingTags || [];
            const b = this.sortOriginalTags || [];
            if (a.length !== b.length) return true;
            for (let i = 0; i < a.length; i += 1) {
                if (a[i] !== b[i]) return true;
            }
            return false;
        },

        get filterTags() { return this.$store.global.viewState.filterTags; },
        set filterTags(val) { this.$store.global.viewState.filterTags = val; },

        init() {
            this.$watch('$store.global.showTagFilterModal', (val) => {
                if (this._syncClosing) return;

                if (val) {
                    this.showTagFilterModal = true;
                    this.loadTagOrderMeta();
                    return;
                }

                this.showTagFilterModal = val;
                if (!val) {
                    if (this.isSortMode && this.isSortDirty) {
                        const ok = confirm('当前排序尚未保存，关闭后将丢失改动。确定关闭吗？');
                        if (!ok) {
                            this.$store.global.showTagFilterModal = true;
                            this.showTagFilterModal = true;
                            return;
                        }
                    }
                    this.isDeleteMode = false;
                    this.isSortMode = false;
                    this.selectedTagsForDeletion = [];
                    this.showCategoryMode = false;
                    this.selectedCategoryTags = [];
                    this.categoryDraftName = '';
                    this.categoryDraftColor = '#64748b';
                    this.categoryDraftOpacity = 16;
                    this.showCategoryManager = false;
                    this.categoryManagerDraftName = '';
                    this.categoryManagerDraftColor = '#64748b';
                    this.categoryManagerDraftOpacity = 16;
                    this.categoryFilterInclude = [];
                    this.categoryFilterExclude = [];
                    this.mixedCategoryView = true;
                    this.sortWorkingTags = [];
                    this.sortOriginalTags = [];
                    this.dragTag = null;
                    this.dragOverTag = null;
                }
            });
            
            // 双向绑定：组件关闭时更新 store
            this.$watch('showTagFilterModal', (val) => {
                this.$store.global.showTagFilterModal = val;
            });

            window.addEventListener('open-tag-filter-modal', () => {
                this.showTagFilterModal = true;
                this.$store.global.showTagFilterModal = true;
                this.loadTagOrderMeta();
            });

            this.$watch('$store.global.tagTaxonomy.updated_at', () => {
                this.sanitizeCategoryFilterState();
            });
        },

        loadTagOrderMeta() {
            getTagOrder()
                .then((res) => {
                    if (!res || !res.success) return;
                    this.customOrderEnabled = !!res.enabled;
                })
                .catch(() => {});
        },

        requestCloseModal() {
            if (this.isSortMode && this.isSortDirty) {
                const ok = confirm('当前排序尚未保存，关闭后将丢失改动。确定关闭吗？');
                if (!ok) return;
            }

            this._syncClosing = true;
            this.showTagFilterModal = false;
            this.$store.global.showTagFilterModal = false;
            this._syncClosing = false;
        },

        toggleFilterTag(tag, event = null) {
            this.$store.global.toggleFilterTag(tag, {
                forceExclude: !!(event && event.shiftKey)
            });
        },

        getTagChipStyle(tag) {
            return this.$store.global.getTagChipStyle(tag);
        },

        getTagCategory(tag) {
            return this.$store.global.getTagCategory(tag);
        },

        getCategoryColor(category) {
            return this.$store.global.getCategoryColor(category);
        },

        getCategoryOpacity(category) {
            return this.$store.global.getCategoryOpacity(category);
        },

        normalizeOpacity(value, fallback = 16) {
            const fallbackNum = Number.isFinite(Number(fallback)) ? Number(fallback) : 16;
            const raw = Number(value);
            if (!Number.isFinite(raw)) return Math.max(0, Math.min(100, Math.round(fallbackNum)));
            return Math.max(0, Math.min(100, Math.round(raw)));
        },

        getCategoryFilterState(category) {
            if (this.categoryFilterInclude.includes(category)) return 'included';
            if (this.categoryFilterExclude.includes(category)) return 'excluded';
            return 'none';
        },

        toggleCategoryFilter(category, event = null) {
            const name = String(category || '').trim();
            if (!name) return;

            const forceExclude = !!(event && event.shiftKey);
            const include = [...(this.categoryFilterInclude || [])];
            const exclude = [...(this.categoryFilterExclude || [])];

            const inInclude = include.indexOf(name);
            const inExclude = exclude.indexOf(name);

            this.mixedCategoryView = false;

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

            this.categoryFilterInclude = include;
            this.categoryFilterExclude = exclude;
        },

        showAllCategoriesMixed() {
            this.categoryFilterInclude = [];
            this.categoryFilterExclude = [];
            this.mixedCategoryView = true;
        },

        sanitizeCategoryFilterState() {
            const valid = new Set(this.availableCategoryNames || []);
            this.categoryFilterInclude = (this.categoryFilterInclude || []).filter(name => valid.has(name));
            this.categoryFilterExclude = (this.categoryFilterExclude || []).filter(name => valid.has(name));
        },

        buildTaxonomyPayload() {
            const current = this.$store.global.tagTaxonomy || {};
            const defaultCategory = String(current.default_category || '未分类').trim() || '未分类';
            const categories = current.categories && typeof current.categories === 'object' ? { ...current.categories } : {};
            const categoryOrder = Array.isArray(current.category_order) ? [...current.category_order] : [];
            const tagToCategory = current.tag_to_category && typeof current.tag_to_category === 'object'
                ? { ...current.tag_to_category }
                : {};

            if (!categories[defaultCategory]) {
                categories[defaultCategory] = { color: '#64748b', opacity: 16 };
            }

            if (!categoryOrder.includes(defaultCategory)) {
                categoryOrder.unshift(defaultCategory);
            }

            return {
                default_category: defaultCategory,
                category_order: categoryOrder,
                categories,
                tag_to_category: tagToCategory,
            };
        },

        saveTaxonomy(taxonomy, successMsg = '') {
            return saveTagTaxonomy({ taxonomy })
                .then((res) => {
                    if (!res || !res.success) {
                        alert('保存标签分类失败: ' + ((res && res.msg) || '未知错误'));
                        return null;
                    }

                    this.$store.global.setTagTaxonomy(res.taxonomy || taxonomy);
                    this.sanitizeCategoryFilterState();
                    if (successMsg) {
                        this.$store.global.showToast(successMsg, 1800);
                    }
                    return res.taxonomy || taxonomy;
                })
                .catch((err) => {
                    alert('保存标签分类失败: ' + err);
                    return null;
                });
        },

        toggleCategoryManager() {
            this.showCategoryManager = !this.showCategoryManager;
        },

        addCategoryFromManager() {
            const name = String(this.categoryManagerDraftName || '').trim();
            if (!name) {
                alert('请输入分类名称');
                return;
            }

            const color = String(this.categoryManagerDraftColor || '').trim() || '#64748b';
            const opacity = this.normalizeOpacity(this.categoryManagerDraftOpacity, 16);
            const taxonomy = this.buildTaxonomyPayload();
            const exists = !!taxonomy.categories[name];

            taxonomy.categories[name] = {
                ...(taxonomy.categories[name] || {}),
                color,
                opacity,
            };

            if (!taxonomy.category_order.includes(name)) {
                taxonomy.category_order.push(name);
            }

            this.saveTaxonomy(taxonomy, exists ? `✅ 已更新分类「${name}」颜色` : `✅ 已新增分类「${name}」`)
                .then((saved) => {
                    if (!saved) return;
                    this.categoryManagerDraftName = '';
                });
        },

        renameCategory(categoryName) {
            const oldName = String(categoryName || '').trim();
            if (!oldName) return;

            const nextNameRaw = prompt('请输入新的分类名称', oldName);
            if (nextNameRaw === null) return;

            const newName = String(nextNameRaw || '').trim();
            if (!newName || newName === oldName) return;

            const taxonomy = this.buildTaxonomyPayload();
            if (!taxonomy.categories[oldName]) return;

            const targetExists = !!taxonomy.categories[newName];
            if (targetExists) {
                const okMerge = confirm(`分类「${newName}」已存在，是否将「${oldName}」合并到它？`);
                if (!okMerge) return;
            }

            if (!targetExists) {
                taxonomy.categories[newName] = { ...taxonomy.categories[oldName] };
            }
            delete taxonomy.categories[oldName];

            taxonomy.category_order = taxonomy.category_order.map(name => (name === oldName ? newName : name));
            taxonomy.category_order = [...new Set(taxonomy.category_order.filter(Boolean))];

            Object.keys(taxonomy.tag_to_category).forEach((tag) => {
                if (taxonomy.tag_to_category[tag] === oldName) {
                    taxonomy.tag_to_category[tag] = newName;
                }
            });

            if (taxonomy.default_category === oldName) {
                taxonomy.default_category = newName;
            }

            this.saveTaxonomy(taxonomy, `✅ 已重命名分类「${oldName}」`);
        },

        deleteCategory(categoryName) {
            const name = String(categoryName || '').trim();
            if (!name) return;

            const taxonomy = this.buildTaxonomyPayload();
            const defaultCategory = String(taxonomy.default_category || '未分类').trim() || '未分类';

            if (name === defaultCategory) {
                alert('默认分类无法删除，请先将其他分类设为默认');
                return;
            }

            const ok = confirm(`确定删除分类「${name}」吗？该分类下标签将迁移到「${defaultCategory}」。`);
            if (!ok) return;

            delete taxonomy.categories[name];
            taxonomy.category_order = taxonomy.category_order.filter(item => item !== name);

            Object.keys(taxonomy.tag_to_category).forEach((tag) => {
                if (taxonomy.tag_to_category[tag] === name) {
                    taxonomy.tag_to_category[tag] = defaultCategory;
                }
            });

            this.saveTaxonomy(taxonomy, `✅ 已删除分类「${name}」`);
        },

        setDefaultCategory(categoryName) {
            const name = String(categoryName || '').trim();
            if (!name) return;

            const taxonomy = this.buildTaxonomyPayload();
            if (!taxonomy.categories[name]) return;

            taxonomy.default_category = name;
            taxonomy.category_order = [name, ...taxonomy.category_order.filter(item => item !== name)];
            this.saveTaxonomy(taxonomy, `✅ 已将「${name}」设为默认分类`);
        },

        setCategoryColor(categoryName, color) {
            const name = String(categoryName || '').trim();
            if (!name) return;

            const taxonomy = this.buildTaxonomyPayload();
            if (!taxonomy.categories[name]) return;

            taxonomy.categories[name] = {
                ...taxonomy.categories[name],
                color: String(color || '').trim() || '#64748b',
            };

            this.saveTaxonomy(taxonomy);
        },

        setCategoryOpacity(categoryName, opacity) {
            const name = String(categoryName || '').trim();
            if (!name) return;

            const taxonomy = this.buildTaxonomyPayload();
            if (!taxonomy.categories[name]) return;

            taxonomy.categories[name] = {
                ...taxonomy.categories[name],
                opacity: this.normalizeOpacity(opacity, 16),
            };

            this.saveTaxonomy(taxonomy);
        },

        moveCategory(categoryName, direction) {
            const name = String(categoryName || '').trim();
            if (!name) return;

            const taxonomy = this.buildTaxonomyPayload();
            const order = [...taxonomy.category_order];
            const index = order.indexOf(name);
            if (index < 0) return;

            const nextIndex = index + (direction < 0 ? -1 : 1);
            if (nextIndex < 0 || nextIndex >= order.length) return;

            const target = order[nextIndex];
            order[nextIndex] = name;
            order[index] = target;
            taxonomy.category_order = order;

            this.saveTaxonomy(taxonomy);
        },

        toggleCategoryMode() {
            if (this.isSortMode) {
                alert('排序模式下无法编辑分类，请先退出排序模式');
                return;
            }

            if (this.isDeleteMode) {
                alert('删除模式下无法编辑分类，请先退出删除模式');
                return;
            }

            this.showCategoryMode = !this.showCategoryMode;
            if (!this.showCategoryMode) {
                this.selectedCategoryTags = [];
                this.categoryDraftName = '';
                this.categoryDraftColor = '#64748b';
                this.categoryDraftOpacity = 16;
                return;
            }

            this.tagSearchQuery = '';
        },

        toggleTagSelectionForCategory(tag) {
            const index = this.selectedCategoryTags.indexOf(tag);
            if (index > -1) {
                this.selectedCategoryTags.splice(index, 1);
                return;
            }
            this.selectedCategoryTags.push(tag);
        },

        setCategoryDraft(categoryName) {
            const name = String(categoryName || '').trim();
            if (!name) return;
            this.categoryDraftName = name;
            this.categoryDraftColor = this.getCategoryColor(name);
            this.categoryDraftOpacity = this.getCategoryOpacity(name);
        },

        saveCategoryBatch() {
            if (!this.canSaveCategoryBatch) {
                alert('请先选择标签并填写分类名');
                return;
            }

            const categoryName = String(this.categoryDraftName || '').trim();
            const categoryColor = String(this.categoryDraftColor || '').trim() || '#64748b';
            const categoryOpacity = this.normalizeOpacity(this.categoryDraftOpacity, 16);
            const tags = [...new Set((this.selectedCategoryTags || []).map(t => String(t || '').trim()).filter(Boolean))];
            if (tags.length === 0) {
                alert('请先选择要设置分类的标签');
                return;
            }

            const taxonomy = this.buildTaxonomyPayload();

            if (!taxonomy.categories[categoryName]) {
                taxonomy.categories[categoryName] = {
                    color: categoryColor,
                    opacity: categoryOpacity,
                };
            } else {
                taxonomy.categories[categoryName] = {
                    ...taxonomy.categories[categoryName],
                    color: categoryColor,
                    opacity: categoryOpacity,
                };
            }

            if (!taxonomy.category_order.includes(categoryName)) {
                taxonomy.category_order.push(categoryName);
            }

            tags.forEach((tag) => {
                taxonomy.tag_to_category[tag] = categoryName;
            });

            this.saveTaxonomy(taxonomy, `✅ 已为 ${tags.length} 个标签设置分类`)
                .then((saved) => {
                    if (!saved) return;
                    this.selectedCategoryTags = [];
                });
        },

        toggleSortMode() {
            if (this.isDeleteMode) {
                alert('删除模式下无法排序，请先退出删除模式');
                return;
            }

            if (this.isSortMode) {
                this.cancelSortMode();
                return;
            }

            this.isSortMode = true;
            this.tagSearchQuery = '';
            this.sortWorkingTags = [...(this.globalTagsPool || [])];
            this.sortOriginalTags = [...this.sortWorkingTags];
            this.dragTag = null;
            this.dragOverTag = null;
        },

        cancelSortMode() {
            if (this.isSortDirty) {
                const ok = confirm('当前排序尚未保存，确定放弃改动吗？');
                if (!ok) return;
            }
            this.isSortMode = false;
            this.sortWorkingTags = [];
            this.sortOriginalTags = [];
            this.dragTag = null;
            this.dragOverTag = null;
        },

        onSortDragStart(e, tag) {
            if (!this.isSortMode) return;
            this.dragTag = tag;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', tag);
        },

        onSortDragOver(e, tag) {
            if (!this.isSortMode) return;
            e.preventDefault();
            this.dragOverTag = tag;
        },

        onSortDrop(e, targetTag) {
            if (!this.isSortMode) return;
            e.preventDefault();
            const sourceTag = this.dragTag || e.dataTransfer.getData('text/plain');
            if (!sourceTag || !targetTag || sourceTag === targetTag) return;

            const list = [...this.sortWorkingTags];
            const from = list.indexOf(sourceTag);
            const to = list.indexOf(targetTag);
            if (from < 0 || to < 0) return;

            list.splice(from, 1);
            const targetIndex = list.indexOf(targetTag);
            list.splice(targetIndex, 0, sourceTag);
            this.sortWorkingTags = list;
            this.dragOverTag = null;
        },

        onSortDragEnd() {
            this.dragTag = null;
            this.dragOverTag = null;
        },

        saveSortMode() {
            if (!this.isSortMode) return;

            const nextOrder = [...this.sortWorkingTags];
            saveTagOrder({ order: nextOrder, enabled: true })
                .then((res) => {
                    if (!res.success) {
                        alert('保存排序失败: ' + (res.msg || '未知错误'));
                        return;
                    }

                    this.$store.global.globalTagsPool = [...nextOrder];

                    const sidebarSet = new Set(this.$store.global.sidebarTagsPool || []);
                    const orderedSidebar = nextOrder.filter(t => sidebarSet.has(t));
                    this.$store.global.sidebarTagsPool = orderedSidebar;
                    this.$store.global.allTagsPool = orderedSidebar;
                    this.$store.global.rebuildTagGroups();
                    this.customOrderEnabled = true;
                    this.sortOriginalTags = [...nextOrder];

                    this.$store.global.showToast('✅ 标签顺序已保存', 1800);
                    this.cancelSortMode();
                })
                .catch((err) => {
                    alert('保存排序失败: ' + err);
                });
        },

        clearCustomOrder() {
            if (this.isSortMode && this.isSortDirty) {
                const ok = confirm('当前排序尚未保存，清除自定义排序会丢失这些改动。确定继续吗？');
                if (!ok) return;
            }

            if (!confirm('确定清除自定义标签排序并恢复字符排序吗？')) return;

            saveTagOrder({ order: [], enabled: false })
                .then((res) => {
                    if (!res.success) {
                        alert('清除自定义排序失败: ' + (res.msg || '未知错误'));
                        return;
                    }

                    this.customOrderEnabled = false;
                    this.isSortMode = false;
                    this.sortWorkingTags = [];
                    this.sortOriginalTags = [];
                    this.dragTag = null;
                    this.dragOverTag = null;

                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                    this.$store.global.showToast('✅ 已恢复字符排序', 1800);
                })
                .catch((err) => {
                    alert('清除自定义排序失败: ' + err);
                });
        },

        // === 删除模式逻辑 ===

        toggleDeleteMode() {
            if (this.isSortMode) {
                alert('排序模式下无法删除，请先取消排序');
                return;
            }

            if (this.showCategoryMode) {
                alert('分类编辑模式下无法删除，请先退出分类编辑');
                return;
            }

            this.isDeleteMode = !this.isDeleteMode;
            if (!this.isDeleteMode) {
                this.selectedTagsForDeletion = []; // 退出时清空
            }
        },

        toggleTagSelectionForDeletion(tag) {
            const index = this.selectedTagsForDeletion.indexOf(tag);
            if (index > -1) {
                this.selectedTagsForDeletion.splice(index, 1);
            } else {
                this.selectedTagsForDeletion.push(tag);
            }
        },

        // 从当前视图的卡片中移除选中的标签
        deleteFilterTags() {
            // 合并包含和排除的标签
            const includeTags = this.$store.global.viewState.filterTags;
            const excludeTags = this.$store.global.viewState.excludedTags;

            // 合并并去重
            const tags = [...new Set([...includeTags, ...excludeTags])];
            
            if (!tags || tags.length === 0) {
                alert("请先选择要删除的标签");
                return;
            }
            
            // 派发事件给 CardGrid 处理（因为只有 CardGrid 知道当前显示了哪些卡片 ID）
            window.dispatchEvent(new CustomEvent('req-batch-remove-current-tags', {
                detail: { tags: [...tags] }
            }));
        },

        deleteSelectedTags() {
            if (this.selectedTagsForDeletion.length === 0) {
                alert("请先选择要删除的标签");
                return;
            }
            
            const tagsToDelete = this.selectedTagsForDeletion.join(', ');
            
            // 获取当前分类 (从全局状态)
            const currentCategory = this.$store.global.viewState.filterCategory;
            const scopeText = currentCategory ? `"${currentCategory}" 分类下` : "所有";
            
            const confirmMsg = `⚠️ 警告：确定要从【${scopeText}】的角色卡中移除以下标签吗？\n\n${tagsToDelete}\n\n此操作不可撤销！`;
            
            if (!confirm(confirmMsg)) return;
            
            deleteTags({ 
                tags: this.selectedTagsForDeletion,
                category: currentCategory 
            })
            .then(res => {
                if (res.success) {
                    alert(`成功删除 ${res.total_tags_deleted} 个标签，更新了 ${res.updated_cards} 张卡片`);
                    
                    // 1. 更新全局标签池
                    const globalPool = this.$store.global.globalTagsPool || [];
                    const sidebarPool = this.$store.global.sidebarTagsPool || [];
                    
                    this.$store.global.globalTagsPool = globalPool.filter(t => !this.selectedTagsForDeletion.includes(t));
                    this.$store.global.sidebarTagsPool = sidebarPool.filter(t => !this.selectedTagsForDeletion.includes(t));
                    this.$store.global.allTagsPool = this.$store.global.sidebarTagsPool;
                    this.$store.global.rebuildTagGroups();

                    // 2. 更新 Layout 中的筛选标签 (如果正好删除了当前正在筛选的标签)
                    // 需要访问 Layout 状态，这里通过事件通知
                    // 其实 Layout 可以自己监听 refresh-card-list 并重新校验 tags，这里简单触发刷新即可
                    
                    // 3. 清空选择
                    this.selectedTagsForDeletion = [];
                    this.isDeleteMode = false;
                    
                    // 4. 刷新列表
                    window.dispatchEvent(new CustomEvent('refresh-card-list'));
                } else {
                    alert("删除失败: " + res.msg);
                }
            })
            .catch(err => {
                alert("网络错误: " + err);
            });
        }
    }
}
