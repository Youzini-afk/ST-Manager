/**
 * static/js/components/wiGrid.js
 * 世界书网格组件
 */

import { listWorldInfo, uploadWorldInfo, createWorldInfo } from '../api/wi.js';

export default function wiGrid() {
    return {
        activeCategoryItemId: null,

        // === Store 代理 ===
        get wiList() { return this.$store.global.wiList; },
        set wiList(val) { this.$store.global.wiList = val; },
        get wiCurrentPage() { return this.$store.global.wiCurrentPage; },
        set wiCurrentPage(val) { this.$store.global.wiCurrentPage = val; },
        get wiTotalItems() { return this.$store.global.wiTotalItems; },
        set wiTotalItems(val) { this.$store.global.wiTotalItems = val; },
        get wiTotalPages() { return this.$store.global.wiTotalPages; },
        set wiTotalPages(val) { this.$store.global.wiTotalPages = val; },
        get wiSearchQuery() { return this.$store.global.wiSearchQuery; },
        set wiSearchQuery(val) { this.$store.global.wiSearchQuery = val; },
        get wiFilterType() { return this.$store.global.wiFilterType; },
        set wiFilterType(val) { this.$store.global.wiFilterType = val; },
        get wiFilterCategory() { return this.$store.global.wiFilterCategory || ''; },

        get wiUploadHintText() {
            if (this.isGlobalCategoryContext()) {
                return `将添加到全局分类 ${this.wiFilterCategory}`;
            }
            if (this.wiFilterType !== 'all' && this.wiFilterType !== 'global') {
                return '当前不在全局分类上下文，上传到全局目录需要明确确认';
            }
            return '将添加到全局目录 (Global)';
        },

        isGlobalCategoryContext() {
            if (!this.wiFilterCategory) return false;
            const capabilities = this.$store.global.wiFolderCapabilities || {};
            const selected = capabilities[this.wiFilterCategory] || {};
            return (this.wiFilterType === 'global' || this.wiFilterType === 'all') && selected.has_physical_folder;
        },

        // 拖拽状态
        dragOverWi: false,

        buildWorldInfoUploadFormData(files, { allowGlobalFallback = false } = {}) {
            const formData = new FormData();
            let hasJson = false;

            for (let i = 0; i < files.length; i++) {
                if (files[i].name.toLowerCase().endsWith('.json')) {
                    formData.append('files', files[i]);
                    hasJson = true;
                }
            }

            if (!hasJson) {
                return null;
            }

            const source_context = this.wiFilterType;
            const target_category = this.isGlobalCategoryContext() ? this.wiFilterCategory : '';
            formData.append('source_context', source_context);
            formData.append('target_category', target_category);
            if (allowGlobalFallback) {
                formData.append('allow_global_fallback', 'true');
            }
            return formData;
        },

        getCategoryModeHint(item) {
            if ((item?.source_type || item?.type) === 'embedded') return '内嵌世界书跟随角色卡分类';
            if (item?.category_mode === 'override') return '已更新管理器分类，未移动实际文件';
            if (item?.category_mode === 'inherited') return '跟随角色卡';
            return '';
        },

        getEmbeddedMoveRejectedMessage() {
            return '请移动所属角色卡来调整内嵌世界书分类';
        },

        getWorldInfoSourceBadge(item) {
            const source_type = item?.source_type || item?.type;
            if (source_type === 'global') return 'GLOBAL';
            if (source_type === 'resource') return 'RESOURCE';
            return 'EMBEDDED';
        },

        getWorldInfoOwnerName(item) {
            return item?.owner_card_name || item?.card_name || '';
        },

        getWorldInfoOwnerId(item) {
            return item?.owner_card_id || item?.card_id || '';
        },

        locateWorldInfoOwnerCard(item) {
            const owner_card_id = this.getWorldInfoOwnerId(item);
            if (!owner_card_id) return;
            this.jumpToCardFromWi(owner_card_id);
            this.hideWorldInfoCategoryActions();
        },

        getMovableWorldInfoCategories() {
            const capabilities = this.$store.global.wiFolderCapabilities || {};
            return (this.$store.global.wiAllFolders || []).filter(path => capabilities[path]?.has_physical_folder);
        },

        showWorldInfoCategoryActions(item, event) {
            event.stopPropagation();
            this.activeCategoryItemId = this.activeCategoryItemId === item.id ? null : item.id;
        },

        hideWorldInfoCategoryActions() {
            this.activeCategoryItemId = null;
        },

        async moveWorldInfoToCategory(item) {
            const source_type = item?.source_type || item?.type;
            if (source_type === 'embedded') {
                alert(this.getEmbeddedMoveRejectedMessage());
                this.hideWorldInfoCategoryActions();
                return;
            }

            const choices = ['根目录'].concat(this.getMovableWorldInfoCategories());
            const current = item?.display_category || '根目录';
            const actionLabel = source_type === 'resource' ? '设置管理器分类' : '移动到分类';
            const selected = prompt(`${actionLabel}（可选：${choices.join(', ')}）`, current);
            if (selected === null) return;

            const target_category = String(selected).trim() === '根目录' ? '' : String(selected).trim();
            const resp = await fetch('/api/world_info/category/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_type,
                    file_path: item.path,
                    target_category,
                })
            });
            const res = await resp.json();
            if (res?.success) {
                this.$store.global.showToast(res.msg);
                this.fetchWorldInfoList();
                this.hideWorldInfoCategoryActions();
                return;
            }
            alert(res?.msg || '移动失败');
        },

        async resetWorldInfoCategory(item) {
            const source_type = item?.source_type || item?.type;
            const resp = await fetch('/api/world_info/category/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_type,
                    file_path: item.path,
                })
            });
            const res = await resp.json();
            if (res?.success) {
                this.$store.global.showToast(res.msg);
                this.fetchWorldInfoList();
                this.hideWorldInfoCategoryActions();
                return;
            }
            alert(res?.msg || '恢复失败');
        },

        init() {
            // === 监听 Store 变化自动刷新 ===
            this.$watch('$store.global.wiSearchQuery', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            this.$watch('$store.global.wiFilterType', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            this.$watch('$store.global.wiFilterCategory', () => {
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            // 监听刷新事件
            window.addEventListener('refresh-wi-list', (e) => {
                if (e.detail && e.detail.resetPage) this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            // 监听搜索框输入
            window.addEventListener('wi-search-changed', (e) => {
                this.wiSearchQuery = e.detail;
                this.wiCurrentPage = 1;
                this.fetchWorldInfoList();
            });

            // 提供给外部（例如侧边栏导入按钮）复用的全局上传入口
            window.stUploadWorldInfoFiles = (files) => {
                // 使用当前 wiGrid 实例来处理上传，保证行为与拖拽一致
                this._uploadWorldInfoInternal(files);
            };

            // 新建世界书（由 Header / Sidebar 触发）
            window.addEventListener('create-worldinfo', () => {
                this.createNewWorldInfo();
            });
        },

        // === 数据加载 ===
        fetchWorldInfoList() {
            if (Alpine.store('global').serverStatus.status !== 'ready') return;

            Alpine.store('global').isLoading = true;

            const pageSize = Alpine.store('global').settingsForm.items_per_page_wi || 20;

            const params = {
                search: this.wiSearchQuery,
                type: this.wiFilterType,
                category: this.wiFilterCategory,
                page: this.wiCurrentPage,
                page_size: pageSize
            };

            listWorldInfo(params)
                .then(res => {
                    Alpine.store('global').isLoading = false;
                    if (res.success) {
                        // 更新 Store 中的列表
                        this.wiList = res.items;
                        this.$store.global.wiAllFolders = res.all_folders || [];
                        this.$store.global.wiCategoryCounts = res.category_counts || {};
                        this.$store.global.wiFolderCapabilities = res.folder_capabilities || {};

                        this.wiTotalItems = res.total || 0;
                        this.wiTotalPages = Math.ceil(this.wiTotalItems / pageSize) || 1;
                    }
                })
                .catch(() => Alpine.store('global').isLoading = false);
        },

        changeWiPage(p) {
            if (p >= 1 && p <= this.wiTotalPages) {
                this.wiCurrentPage = p;
                const el = document.getElementById('wi-scroll-area');
                if (el) el.scrollTop = 0;
                this.fetchWorldInfoList();
            }
        },

        // === 交互逻辑 ===

        // 打开详情 (Popup 弹窗)
        openWiDetail(item) {
            // 派发事件，由 detail_wi_popup 组件监听并显示
            window.dispatchEvent(new CustomEvent('open-wi-detail-modal', { detail: item }));
        },

        // 打开编辑器 (全屏)
        openWorldInfoEditor(item) {
            window.dispatchEvent(new CustomEvent('open-wi-editor', { detail: item }));
        },

        // 新建全局世界书（使用 ST 兼容格式）
        async createNewWorldInfo() {
            const name = prompt('请输入新世界书名称:', 'New World Info');
            if (name === null) return;

            const finalName = String(name || '').trim();
            if (!finalName) {
                alert('世界书名称不能为空');
                return;
            }

            this.$store.global.isLoading = true;
            try {
                const target_category = this.isGlobalCategoryContext() ? this.wiFilterCategory : '';
                const res = await createWorldInfo({ name: finalName, target_category });
                this.$store.global.isLoading = false;
                if (!res || !res.success) {
                    alert(`创建失败: ${(res && res.msg) ? res.msg : '未知错误'}`);
                    return;
                }

                if (this.$store?.global?.showToast) {
                    this.$store.global.showToast('✅ 已创建世界书（ST 兼容格式）', 1800);
                }

                // 刷新列表并定位到新建条目
                window.dispatchEvent(new CustomEvent('refresh-wi-list', { detail: { resetPage: true } }));
                if (res.item) {
                    // 稍作延迟，避免和列表刷新动画冲突
                    setTimeout(() => {
                        this.openWorldInfoEditor(res.item);
                    }, 60);
                }
            } catch (err) {
                this.$store.global.isLoading = false;
                alert(`创建失败: ${err}`);
            }
        },

        // 从详情页进入编辑器
        // 注意：此函数通常在详情页模态框内调用，传递 item 参数
        enterWiEditorFromDetail(item) {
            // 1. 关闭详情弹窗
            window.dispatchEvent(new CustomEvent('close-wi-detail-modal'));

            // 2. 打开全屏编辑器
            // 使用 setTimeout 确保弹窗关闭动画不冲突（可选）
            setTimeout(() => {
                this.openWorldInfoEditor(item);
            }, 50);
        },

        // 跳转到关联角色卡
        jumpToCardFromWi(cardId) {
            window.dispatchEvent(new CustomEvent('jump-to-card-wi', { detail: cardId }));
        },

        // === 文件上传 ===

        // 核心世界书上传逻辑封装，供拖拽和按钮导入复用
        _uploadWorldInfoInternal(files) {
            if (!files || files.length === 0) return;

            const formData = this.buildWorldInfoUploadFormData(files);

            if (!formData) {
                alert("请选择 .json 格式的世界书文件");
                return;
            }

            this.$store.global.isLoading = true;
            uploadWorldInfo(formData)
                .then(res => {
                    if (res?.requires_global_fallback_confirmation) {
                        if (confirm('当前不在全局分类上下文。确认继续上传到全局根目录吗？')) {
                            const fallbackFormData = this.buildWorldInfoUploadFormData(files, { allowGlobalFallback: true });
                            return uploadWorldInfo(fallbackFormData);
                        }
                        return res;
                    }
                    return res;
                })
                .then(res => {
                    this.$store.global.isLoading = false;
                    if (!res) return;
                    if (res.success) {
                        this.$store.global.showToast(res.msg);
                        // 如果当前不在 global 视图，提示切换
                        const currentType = this.$store.global.wiFilterType;
                        if (currentType !== 'all' && currentType !== 'global') {
                            if (confirm("上传成功（已存入全局目录）。是否切换到全局视图查看？")) {
                                this.$store.global.wiFilterType = 'global';
                                window.dispatchEvent(new CustomEvent('refresh-wi-list', { detail: { resetPage: true } }));
                            } else {
                                this.fetchWorldInfoList();
                            }
                        } else {
                            this.fetchWorldInfoList();
                        }
                    } else {
                        alert("上传失败: " + res.msg);
                    }
                })
                .catch(err => {
                    this.$store.global.isLoading = false;
                    alert("网络错误: " + err);
                });
        },

        handleWiFilesDrop(e) {
            this.dragOverWi = false;
            const files = e.dataTransfer.files;
            this._uploadWorldInfoInternal(files);
        }
    }
}
