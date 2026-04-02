/**
 * static/js/components/presetGrid.js
 * 预设网格组件 - 对齐 extensionGrid.js 风格
 */
export default function presetGrid() {
    return {
        items: [],
        isLoading: false,
        dragOver: false,
        selectedPreset: null,
        showDetailModal: false,

        // 新三栏阅览界面状态
        activePresetDetail: null,
        showPresetDetailModal: false,
        activePresetItem: null,
        activePresetItemType: null,
        uiPresetFilter: null,
        showMobileSidebar: false,
        get selectedIds() { return this.$store.global.viewState.selectedIds; },
        set selectedIds(val) { this.$store.global.viewState.selectedIds = val; return true; },
        get lastSelectedId() { return this.$store.global.viewState.lastSelectedId; },
        set lastSelectedId(val) { this.$store.global.viewState.lastSelectedId = val; return true; },
        get draggedCards() { return this.$store.global.viewState.draggedCards; },
        set draggedCards(val) { this.$store.global.viewState.draggedCards = val; return true; },

        get filterType() { return this.$store.global.presetFilterType || 'all'; },
        get filterCategory() { return this.$store.global.presetFilterCategory || ''; },

        get presetUploadHintText() {
            if (this.isGlobalCategoryContext()) {
                return `将存入全局分类 ${this.filterCategory}`;
            }
            if (this.filterType !== 'all' && this.filterType !== 'global') {
                return '当前不在全局分类上下文，上传到全局目录需要明确确认';
            }
            return '将存入全局预设目录';
        },

        isGlobalCategoryContext() {
            if (!this.filterCategory) return false;
            const capabilities = this.$store.global.presetFolderCapabilities || {};
            const selected = capabilities[this.filterCategory] || {};
            return (this.filterType === 'global' || this.filterType === 'all') && selected.has_physical_folder;
        },

        getMovablePresetCategories() {
            const capabilities = this.$store.global.presetFolderCapabilities || {};
            return (this.$store.global.presetAllFolders || []).filter(path => capabilities[path]?.has_physical_folder);
        },

        getPresetSourceBadge(item) {
            const source_type = item?.source_type || item?.type;
            if (source_type === 'global') return 'GLOBAL / 物理分类';
            if (item?.category_mode === 'override') return 'RESOURCE / 已覆盖管理器分类';
            return 'RESOURCE / 跟随角色卡';
        },

        getPresetOwnerName(item) {
            return item?.owner_card_name || item?.source_folder || '';
        },

        getPresetOwnerId(item) {
            return item?.owner_card_id || '';
        },

        getPresetItemById(id) {
            return (this.items || []).find(item => item.id === id) || null;
        },

        selectedPresetItems() {
            return this.selectedIds
                .map(id => this.getPresetItemById(id))
                .filter(Boolean);
        },

        canSelectPresetItem(item) {
            return !!item;
        },

        isPresetMovable(item) {
            return !!item && (item.source_type || item.type) === 'global';
        },

        canDeletePresetSelection() {
            const items = this.selectedPresetItems();
            return items.length > 0 && items.every(item => this.canSelectPresetItem(item));
        },

        canMovePresetSelection() {
            const items = this.selectedPresetItems();
            return items.length > 0 && items.every(item => this.isPresetMovable(item));
        },

        toggleSelection(item) {
            if (!this.canSelectPresetItem(item)) return;

            let ids = [...this.selectedIds];
            if (ids.includes(item.id)) {
                ids = ids.filter(id => id !== item.id);
            } else {
                ids.push(item.id);
                this.lastSelectedId = item.id;
            }
            this.selectedIds = ids;
        },

        handlePresetClick(e, item) {
            if (e.ctrlKey || e.metaKey) {
                this.toggleSelection(item);
                return;
            }

            if (e.shiftKey && this.lastSelectedId) {
                const selectableItems = this.items || [];
                const startIdx = selectableItems.findIndex(currentItem => currentItem.id === this.lastSelectedId);
                const endIdx = selectableItems.findIndex(currentItem => currentItem.id === item.id);

                if (startIdx !== -1 && endIdx !== -1) {
                    const min = Math.min(startIdx, endIdx);
                    const max = Math.max(startIdx, endIdx);
                    const rangeIds = selectableItems.slice(min, max + 1).map(currentItem => currentItem.id);
                    const currentSet = new Set(this.selectedIds);
                    rangeIds.forEach(id => currentSet.add(id));
                    this.selectedIds = Array.from(currentSet);
                }
                return;
            }

            this.openPresetDetail(item);
        },

        dragStart(e, item) {
            if (!this.canSelectPresetItem(item)) {
                e.preventDefault();
                return;
            }

            const ids = this.selectedIds.includes(item.id)
                ? [...this.selectedIds]
                : Array.of(item.id, ...this.selectedIds);

            const selectedItems = ids
                .map(id => this.getPresetItemById(id))
                .filter(Boolean);

            if (selectedItems.length === 0 || !selectedItems.every(currentItem => this.isPresetMovable(currentItem))) {
                e.preventDefault();
                alert('当前选中的预设包含资源绑定项，不能移动分类');
                return;
            }

            if (!this.selectedIds.includes(item.id)) {
                this.selectedIds = ids;
            }

            this.draggedCards = ids;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('application/x-st-preset', JSON.stringify(ids));
            e.dataTransfer.setData('text/plain', item.id);

            const cardElement = e.target.closest('[data-preset-id]');
            if (cardElement) {
                requestAnimationFrame(() => {
                    cardElement.classList.add('drag-source');
                });

                const cleanup = () => {
                    cardElement.classList.remove('drag-source');
                    window.dispatchEvent(new CustomEvent('global-drag-end'));
                };

                e.target.addEventListener('dragend', cleanup, { once: true });
            }
        },

        locatePresetOwnerCard(item) {
            const owner_card_id = this.getPresetOwnerId(item);
            if (!owner_card_id) return;
            window.dispatchEvent(new CustomEvent('jump-to-card-wi', { detail: owner_card_id }));
        },

        init() {
            // 监听模式切换
            this.$watch('$store.global.currentMode', (val) => {
                if (val === 'presets') {
                    this.fetchItems();
                }
            });

            // 监听侧边栏筛选变化
            this.$watch('$store.global.presetFilterType', () => {
                if (this.$store.global.currentMode === 'presets') {
                    this.fetchItems();
                }
            });

            this.$watch('$store.global.presetFilterCategory', () => {
                if (this.$store.global.currentMode === 'presets') {
                    this.fetchItems();
                }
            });

            // 监听搜索关键词变化
            this.$watch('$store.global.presetSearch', () => {
                if (this.$store.global.currentMode === 'presets') {
                    this.fetchItems();
                }
            });

            window.addEventListener('refresh-preset-list', () => {
                if (this.$store.global.currentMode === 'presets') {
                    this.fetchItems();
                }
            });

            window.addEventListener('delete-selected-presets', () => {
                this.deleteSelectedPresets();
            });

            window.addEventListener('move-selected-presets', (e) => {
                this.moveSelectedPresets(e.detail?.target_category || '');
            });

            // 初始加载
            if (this.$store.global.currentMode === 'presets') {
                this.fetchItems();
            }

            // presetDetailReader.js 会处理 open-preset-reader 事件
            // 本组件只负责触发事件，不监听

            // 提供给移动端/外部（如 Sidebar 导入按钮）复用的全局上传入口
            window.stUploadPresetFiles = (files) => {
                this._uploadPresetsFiles(files);
            };
        },

        async _uploadPresetsFiles(files) {
            const list = files || [];
            if (!list || list.length === 0) return;

            const buildFormData = (allowGlobalFallback = false) => {
                const formData = new FormData();
                for (let i = 0; i < list.length; i++) {
                formData.append('files', list[i]);
                }
                formData.append('source_context', this.filterType);
                formData.append('target_category', this.isGlobalCategoryContext() ? this.filterCategory : '');
                if (allowGlobalFallback) {
                    formData.append('allow_global_fallback', 'true');
                }
                return formData;
            };

            this.isLoading = true;
            try {
                const resp = await fetch('/api/presets/upload', {
                    method: 'POST',
                    body: buildFormData()
                });
                let res = await resp.json();
                if (res?.requires_global_fallback_confirmation) {
                    if (!confirm('当前不在全局分类上下文。确认继续上传到全局根目录吗？')) {
                        this.isLoading = false;
                        return;
                    }
                    const retryResp = await fetch('/api/presets/upload', {
                        method: 'POST',
                        body: buildFormData(true)
                    });
                    res = await retryResp.json();
                }
                if (res.success) {
                    this.$store.global.showToast(res.msg);
                    this.fetchItems();
                } else {
                    this.$store.global.showToast(res.msg, 'error');
                }
            } catch (e) {
                this.$store.global.showToast('上传失败', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        fetchItems() {
            this.isLoading = true;
            const filterType = this.$store.global.presetFilterType || 'all';
            const search = this.$store.global.presetSearch || '';
            const category = this.$store.global.presetFilterCategory || '';

            let url = `/api/presets/list?filter_type=${filterType}`;
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            if (category) {
                url += `&category=${encodeURIComponent(category)}`;
            }

            fetch(url)
                .then(res => res.json())
                .then(res => {
                    this.items = res.items || [];
                    this.$store.global.presetList = this.items;
                    this.$store.global.presetAllFolders = res.all_folders || [];
                    this.$store.global.presetCategoryCounts = res.category_counts || {};
                    this.$store.global.presetFolderCapabilities = res.folder_capabilities || {};
                    this.isLoading = false;
                })
                .catch((err) => {
                    console.error('Failed to fetch presets:', err);
                    this.isLoading = false;
                });
        },

        async handleDrop(e) {
            this.dragOver = false;
            const files = e.dataTransfer.files;
            if (!files.length) return;
            this._uploadPresetsFiles(files);
        },

        getCategoryModeHint(item) {
            if (item?.category_mode === 'override') return '已更新管理器分类，未移动实际文件';
            if (item?.category_mode === 'inherited') return '跟随角色卡';
            return '';
        },

        getPresetSourceHint(item) {
            if ((item?.source_type || item?.type) === 'global') {
                return 'GLOBAL / 物理分类';
            }
            if (item?.category_mode === 'override') {
                return 'RESOURCE / 已覆盖管理器分类';
            }
            return 'RESOURCE / 跟随角色卡';
        },

        async openPreset(item) {
            // 获取详情并打开编辑器
            this.isLoading = true;
            try {
                const resp = await fetch(`/api/presets/detail/${encodeURIComponent(item.id)}`);
                const res = await resp.json();

                if (res.success) {
                    this.selectedPreset = res.preset;
                    this.showDetailModal = true;
                } else {
                    this.$store.global.showToast(res.msg || '获取详情失败', 'error');
                }
            } catch (e) {
                this.$store.global.showToast('获取详情失败', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        closeDetailModal() {
            this.showDetailModal = false;
            this.selectedPreset = null;
        },

        // 新三栏阅览界面方法
        openPresetDetail(item) {
            // 触发事件让 presetDetailReader.js 处理详情显示
            window.dispatchEvent(new CustomEvent('open-preset-reader', {
                detail: item
            }));
        },

        closePresetDetailModal() {
            this.showPresetDetailModal = false;
            this.activePresetDetail = null;
            this.activePresetItem = null;
            this.activePresetItemType = null;
            this.uiPresetFilter = null;
        },

        selectPresetItem(item, type, shouldScroll = false) {
            this.activePresetItem = item;
            this.activePresetItemType = type;

            if (shouldScroll && item) {
                this.$nextTick(() => {
                    const domId = type === 'prompt' ? `preset-prompt-${item.key}` : `preset-regex-${item.key || 'unknown'}`;
                    if (item.key) {
                        const el = document.getElementById(`preset-prompt-${item.key}`);
                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                });
            }
        },

        get filteredPresetItems() {
            if (!this.activePresetDetail) return [];
            const prompts = this.activePresetDetail.prompts || [];
            
            if (this.uiPresetFilter === 'enabled') return prompts.filter(p => p.enabled);
            if (this.uiPresetFilter === 'disabled') return prompts.filter(p => !p.enabled);
            
            return prompts;
        },

        get totalPresetItems() {
            if (!this.activePresetDetail) return [];
            // 只返回prompts，不再混合regexes
            return this.activePresetDetail.prompts || [];
        },

        // 打开高级扩展编辑器（正则脚本 + ST脚本）
        openAdvancedExtensions() {
            if (!this.activePresetDetail) return;
            
            // 准备extensions数据结构
            const extensions = this.activePresetDetail.extensions || {};
            const regex_scripts = extensions.regex_scripts || [];
            const tavern_helper = extensions.tavern_helper || { scripts: [] };
            
            // 构造editingData，与角色卡详情页保持一致
            const editingData = {
                extensions: {
                    regex_scripts: regex_scripts,
                    tavern_helper: tavern_helper
                }
            };
            
            // 触发高级编辑器事件
            window.dispatchEvent(new CustomEvent('open-advanced-editor', {
                detail: editingData
            }));
            
            // 监听保存事件，将修改后的extensions保存回预设
            const saveHandler = (e) => {
                if (e.detail && e.detail.extensions) {
                    this.savePresetExtensions(e.detail.extensions);
                }
                window.removeEventListener('advanced-editor-save', saveHandler);
            };
            window.addEventListener('advanced-editor-save', saveHandler);
        },

        // 保存extensions到预设文件
        async savePresetExtensions(extensions) {
            if (!this.activePresetDetail) return;
            
            try {
                const resp = await fetch('/api/presets/save-extensions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: this.activePresetDetail.id,
                        extensions: extensions
                    })
                });
                
                const res = await resp.json();
                if (res.success) {
                    this.$store.global.showToast('扩展已保存');
                    // 刷新详情
                    this.openPresetDetail({ id: this.activePresetDetail.id });
                } else {
                    this.$store.global.showToast(res.msg || '保存失败', 'error');
                }
            } catch (e) {
                console.error('Failed to save preset extensions:', e);
                this.$store.global.showToast('保存失败', 'error');
            }
        },

        createSnapshot(type) {
            // 触发快照功能
            window.dispatchEvent(new CustomEvent('create-snapshot', {
                detail: { type, path: this.activePresetDetail?.path }
            }));
        },

        openRollback() {
            // 触发回滚界面
            window.dispatchEvent(new CustomEvent('open-rollback', {
                detail: { path: this.activePresetDetail?.path }
            }));
        },

        openBackupFolder(type) {
            // 打开备份文件夹
            window.dispatchEvent(new CustomEvent('open-backup-folder', {
                detail: { type }
            }));
        },

        deleteCurrentPreset() {
            if (!this.activePresetDetail) return;
            if (!confirm(`确定要删除预设 "${this.activePresetDetail.name}" 吗？`)) {
                return;
            }

            fetch('/api/presets/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: this.activePresetDetail.id })
            })
                .then(res => res.json())
                .then(res => {
                    if (res.success) {
                        this.$store.global.showToast(res.msg);
                        this.closePresetDetailModal();
                        this.fetchItems();
                    } else {
                        this.$store.global.showToast(res.msg, 'error');
                    }
                })
                .catch(() => {
                    this.$store.global.showToast('删除失败', 'error');
                });
        },

        editPresetRawFromDetail() {
            if (!this.activePresetDetail) return;

            window.dispatchEvent(new CustomEvent('open-script-file-editor', {
                detail: {
                    fileData: this.activePresetDetail.raw_data,
                    filePath: this.activePresetDetail.path,
                    type: 'preset'
                }
            }));

            this.closePresetDetailModal();
        },

        async deletePreset(item, e) {
            e.stopPropagation();

            if (!confirm(`确定要删除预设 "${item.name}" 吗？`)) {
                return;
            }

            try {
                const resp = await fetch('/api/presets/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: item.id })
                });
                const res = await resp.json();

                if (res.success) {
                    this.$store.global.showToast(res.msg);
                    this.fetchItems();
                } else {
                    this.$store.global.showToast(res.msg, 'error');
                }
            } catch (e) {
                this.$store.global.showToast('删除失败', 'error');
            }
        },

        async deleteSelectedPresets() {
            if (!this.canDeletePresetSelection()) return;

            const items = this.selectedPresetItems();
            const count = items.length;
            if (!confirm(`确定要删除选中的 ${count} 个预设吗？`)) return;

            for (const item of items) {
                const resp = await fetch('/api/presets/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: item.id })
                });
                const res = await resp.json();
                if (!res?.success) {
                    this.$store.global.showToast(res?.msg || '删除失败', 'error');
                    return;
                }
            }

            this.$store.global.showToast(`🗑️ 已删除 ${count} 个预设`);
            this.selectedIds = [];
            this.fetchItems();
        },

        async moveSelectedPresets(targetCategory = this.filterCategory || '') {
            if (!this.canMovePresetSelection()) {
                alert('当前选中的预设包含资源绑定项，不能移动分类');
                return;
            }

            const items = this.selectedPresetItems();
            const count = items.length;
            const label = targetCategory || '根目录';
            if (!confirm(`移动 ${count} 个预设到 "${label}"?`)) return;

            for (const item of items) {
                const resp = await fetch('/api/presets/category/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: item.id,
                        source_type: item.source_type || item.type,
                        file_path: item.path,
                        target_category: targetCategory,
                    })
                });
                const res = await resp.json();
                if (!res?.success) {
                    alert(res?.msg || '移动失败');
                    return;
                }
            }

            this.$store.global.showToast(`✅ 已移动 ${count} 个预设`);
            this.selectedIds = [];
            this.fetchItems();
        },

        editPresetRaw() {
            if (!this.selectedPreset) return;

            // 触发高级编辑器
            window.dispatchEvent(new CustomEvent('open-script-file-editor', {
                detail: {
                    fileData: this.selectedPreset.raw_data,
                    filePath: this.selectedPreset.path,
                    type: 'preset'
                }
            }));

            this.closeDetailModal();
        },

        formatDate(ts) {
            if (!ts) return '-';
            return new Date(ts * 1000).toLocaleString();
        },

        formatSize(bytes) {
            if (!bytes) return '-';
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1024 / 1024).toFixed(1) + ' MB';
        },

        formatParam(val) {
            if (val === null || val === undefined) return '-';
            if (typeof val === 'number') {
                return Number.isInteger(val) ? val : val.toFixed(2);
            }
            return val;
        },

        formatPromptContent(val) {
            if (val === null || val === undefined) return '';
            if (typeof val === 'string') return val;
            try {
                return JSON.stringify(val, null, 2);
            } catch (e) {
                return String(val);
            }
        },

        pickPromptContent(prompt) {
            const candidates = [
                'content', 'prompt', 'text', 'value', 'system_prompt', 'system',
                'message', 'injection', 'body', 'template'
            ];
            for (const key of candidates) {
                if (prompt && Object.prototype.hasOwnProperty.call(prompt, key)) {
                    const val = prompt[key];
                    if (val !== null && val !== undefined && val !== '') {
                        return val;
                    }
                }
            }
            return '';
        },

        collectPromptMeta(prompt) {
            const meta = [];
            const pushMeta = (label, value) => {
                if (value === null || value === undefined || value === '') return;
                meta.push(`${label}: ${value}`);
            };

            if (!prompt || typeof prompt !== 'object') return meta;

            pushMeta('role', prompt.role);
            pushMeta('type', prompt.type || prompt.kind || prompt.mode);
            pushMeta('position', prompt.position || prompt.insertion_position || prompt.insert_position);
            pushMeta('depth', prompt.depth);
            pushMeta('priority', prompt.priority);
            pushMeta('order', prompt.order);

            return meta;
        },

        normalizePrompts(list) {
            if (!Array.isArray(list)) return [];

            return list.map((prompt, idx) => {
                const defaultName = `Prompt ${idx + 1}`;

                if (prompt === null || prompt === undefined) {
                    return {
                        key: `prompt-${idx}`,
                        name: defaultName,
                        content: '',
                        enabled: true,
                        meta: [],
                        isReference: true
                    };
                }

                if (typeof prompt === 'string' || typeof prompt === 'number') {
                    return {
                        key: `prompt-${idx}-${prompt}`,
                        name: String(prompt),
                        content: '',
                        enabled: true,
                        meta: [],
                        isReference: true
                    };
                }

                if (typeof prompt !== 'object') {
                    return {
                        key: `prompt-${idx}`,
                        name: String(prompt),
                        content: '',
                        enabled: true,
                        meta: [],
                        isReference: true
                    };
                }

                const name = prompt.name || prompt.title || prompt.id || prompt.identifier || prompt.key || prompt.role || defaultName;
                const contentRaw = this.pickPromptContent(prompt);
                const content = this.formatPromptContent(contentRaw);
                const toBool = (val) => {
                    if (typeof val === 'boolean') return val;
                    if (typeof val === 'number') return val !== 0;
                    if (typeof val === 'string') {
                        const lowered = val.toLowerCase();
                        if (['false', '0', 'no', 'off', 'disabled'].includes(lowered)) return false;
                        if (['true', '1', 'yes', 'on', 'enabled'].includes(lowered)) return true;
                        return Boolean(val);
                    }
                    return Boolean(val);
                };

                const enabledRaw = prompt.enabled ?? prompt.isEnabled ?? prompt.active ?? prompt.isActive;
                const disabledRaw = prompt.disabled ?? prompt.isDisabled;

                let enabled = true;
                if (disabledRaw !== undefined && disabledRaw !== null) {
                    enabled = !toBool(disabledRaw);
                } else if (enabledRaw !== undefined && enabledRaw !== null && !(typeof enabledRaw === 'string' && enabledRaw.trim() === '')) {
                    enabled = toBool(enabledRaw);
                }

                return {
                    key: prompt.id || prompt.identifier || prompt.name || `prompt-${idx}`,
                    name,
                    content,
                    enabled,
                    meta: this.collectPromptMeta(prompt),
                    isReference: !content
                };
            });
        }
    }
}
