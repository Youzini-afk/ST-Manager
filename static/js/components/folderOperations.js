/**
 * static/js/components/folderOperations.js
 * 文件夹操作模态框控制器
 */

import { renameFolder, createFolder } from '../api/system.js'; // createSubFolder 实际上也是调用 createFolder

export default function folderOperations() {
    return {
        resourceFolderInput: '',

        get activeFolderMode() {
            return this.folderCreateSubModal.mode
                || this.folderRenameModal.mode
                || this.$store.global.folderModals.createRoot.mode
                || this.$store.global.currentMode;
        },

        // === 1. 代理全局状态 (Getters/Setters) ===
        // 这样 HTML 中的 x-model="folderRenameModal.name" 依然有效，无需修改 HTML 结构
        
        get folderRenameModal() { return this.$store.global.folderModals.rename; },
        get folderCreateSubModal() { return this.$store.global.folderModals.createSub; },
        
        // 兼容 Sidebar 的新建文件夹逻辑
        get showCreateFolder() { return this.$store.global.folderModals.createRoot.visible; },
        set showCreateFolder(val) { this.$store.global.folderModals.createRoot.visible = val; },
        
        get newFolderName() { return this.$store.global.folderModals.createRoot.name; },
        set newFolderName(val) { this.$store.global.folderModals.createRoot.name = val; },
        
        get newFolderParent() { return this.$store.global.folderModals.createRoot.parent; },
        set newFolderParent(val) { this.$store.global.folderModals.createRoot.parent = val; },

        // 获取文件夹列表供下拉框使用
        get allFoldersList() { return this.$store.global.allFoldersList; },

        get folderSelectList() {
            if (this.activeFolderMode === 'worldinfo') {
                return (this.$store.global.wiAllFolders || []).map(path => ({ path }));
            }
            if (this.activeFolderMode === 'presets') {
                return (this.$store.global.presetAllFolders || []).map(path => ({ path }));
            }
            return this.$store.global.allFoldersList;
        },

        get creatableFolderSelectList() {
            if (this.activeFolderMode === 'worldinfo') {
                const caps = this.$store.global.wiFolderCapabilities || {};
                return (this.$store.global.wiAllFolders || [])
                    .filter(path => caps[path]?.can_create_child_folder)
                    .map(path => ({ path }));
            }
            if (this.activeFolderMode === 'presets') {
                const caps = this.$store.global.presetFolderCapabilities || {};
                return (this.$store.global.presetAllFolders || [])
                    .filter(path => caps[path]?.can_create_child_folder)
                    .map(path => ({ path }));
            }
            return this.$store.global.allFoldersList;
        },

        async requestFolderOperation(endpoint, payload) {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return resp.json();
        },

        syncFolderResponse(res, mode = this.activeFolderMode) {
            if (!res?.success) {
                alert((mode === 'cards' ? '操作失败: ' : '') + (res?.msg || 'unknown'));
                return false;
            }

            if (mode === 'worldinfo') {
                this.$store.global.wiAllFolders = res.all_folders || [];
                this.$store.global.wiCategoryCounts = res.category_counts || {};
                this.$store.global.wiFolderCapabilities = res.folder_capabilities || {};
                window.dispatchEvent(new CustomEvent('refresh-wi-list', { detail: { resetPage: false } }));
                return true;
            }

            if (mode === 'presets') {
                this.$store.global.presetAllFolders = res.all_folders || [];
                this.$store.global.presetCategoryCounts = res.category_counts || {};
                this.$store.global.presetFolderCapabilities = res.folder_capabilities || {};
                window.dispatchEvent(new CustomEvent('refresh-preset-list'));
                return true;
            }

            window.dispatchEvent(new CustomEvent('refresh-folder-list'));
            window.dispatchEvent(new CustomEvent('refresh-card-list'));
            return true;
        },

        // === 2. 业务逻辑 ===

        // --- 重命名 ---
        renameFolder() {
            const oldPath = this.folderRenameModal.path;
            const newName = this.folderRenameModal.name.trim();
            const mode = this.folderRenameModal.mode || this.activeFolderMode;
            
            if (!newName) return alert("名称不能为空");
            if (newName === oldPath.split('/').pop()) {
                this.folderRenameModal.visible = false;
                return;
            }
            
            const request = mode === 'worldinfo'
                ? this.requestFolderOperation('/api/world_info/folders/rename', { category: oldPath, new_name: newName })
                : mode === 'presets'
                    ? this.requestFolderOperation('/api/presets/folders/rename', { category: oldPath, new_name: newName })
                    : renameFolder({ old_path: oldPath, new_name: newName });

            Promise.resolve(request)
                .then(res => {
                    if (this.syncFolderResponse(res, mode)) {
                        this.folderRenameModal.visible = false;
                    }
                });
        },

        // --- 新建子文件夹 ---
        createSubFolder() {
            const parent = this.folderCreateSubModal.parentPath;
            const name = this.folderCreateSubModal.name.trim();
            const mode = this.folderCreateSubModal.mode || this.activeFolderMode;
            
            if (!name) return alert("名称不能为空");
            
            const request = mode === 'worldinfo'
                ? this.requestFolderOperation('/api/world_info/folders/create', { parent_category: parent, name })
                : mode === 'presets'
                    ? this.requestFolderOperation('/api/presets/folders/create', { parent_category: parent, name })
                    : createFolder({ name: name, parent: parent });

            Promise.resolve(request)
                .then(res => {
                    if (this.syncFolderResponse(res, mode)) {
                        this.folderCreateSubModal.visible = false;
                    }
                });
        },

        // --- 新建根文件夹 (Sidebar 使用) ---
        createFolder() {
            const name = this.newFolderName.trim();
            const parent = this.newFolderParent;
            const mode = this.$store.global.folderModals.createRoot.mode || this.activeFolderMode;
            
            if (!name) return alert("名称不能为空");

            const request = mode === 'worldinfo'
                ? this.requestFolderOperation('/api/world_info/folders/create', { parent_category: parent, name })
                : mode === 'presets'
                    ? this.requestFolderOperation('/api/presets/folders/create', { parent_category: parent, name })
                    : createFolder({ name: name, parent: parent });

            Promise.resolve(request)
                .then(res => {
                    if (this.syncFolderResponse(res, mode)) {
                        this.showCreateFolder = false;
                        this.newFolderName = '';
                    }
                });
        }
    }
}
