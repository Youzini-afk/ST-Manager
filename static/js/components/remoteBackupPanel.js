import {
  getRemoteBackupConfig,
  getRemoteBackupDetail,
  getRemoteBackupControl,
  getRemoteBackupSchedule,
  listRemoteBackups,
  probeRemoteBackup,
  restoreRemoteBackup,
  restoreRemoteBackupPreview,
  rotateRemoteBackupControlKey,
  saveRemoteBackupConfig,
  saveRemoteBackupSchedule,
  startRemoteBackup,
} from "../api/remoteBackups.js";

const RESOURCE_TYPES = ["characters", "chats", "worlds", "presets", "regex", "quick_replies"];

export default function remoteBackupPanel() {
  return {
    showRemoteBackupModal: false,
    loading: false,
    busy: false,
    error: "",
    config: {},
    control: {},
    generatedControlKey: "",
    schedule: {
      enabled: false,
      interval_minutes: 1440,
      retention_limit: 10,
      resource_types: [...RESOURCE_TYPES],
    },
    probe: null,
    backups: [],
    selectedBackup: null,
    restorePreview: null,
    overwrite: false,
    selectedResourceTypes: [...RESOURCE_TYPES],

    init() {
      window.addEventListener("open-remote-backup-modal", () => {
        this.open();
      });
    },

    async open() {
      this.showRemoteBackupModal = true;
      await this.refreshAll();
    },

    close() {
      this.showRemoteBackupModal = false;
    },

    async refreshAll() {
      this.loading = true;
      this.error = "";
      try {
        const [config, schedule, backups] = await Promise.all([
          getRemoteBackupConfig(),
          getRemoteBackupSchedule(),
          listRemoteBackups(),
        ]);
        this.config = config.config || {};
        this.schedule = { ...this.schedule, ...(schedule.schedule || {}) };
        this.selectedResourceTypes = [...(this.schedule.resource_types || RESOURCE_TYPES)];
        this.backups = backups.backups || [];
        const control = await getRemoteBackupControl();
        this.control = control.control || {};
      } catch (error) {
        this.error = String(error);
      } finally {
        this.loading = false;
      }
    },

    async saveConfig() {
      this.busy = true;
      try {
        const result = await saveRemoteBackupConfig(this.config);
        if (!result.success) throw new Error(result.error || "保存远程备份配置失败");
        this.config = result.config || {};
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async saveSchedule() {
      this.busy = true;
      try {
        const result = await saveRemoteBackupSchedule({
          ...this.schedule,
          resource_types: this.selectedResourceTypes,
        });
        if (!result.success) throw new Error(result.error || "保存定时备份配置失败");
        this.schedule = result.schedule || this.schedule;
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async rotateControlKey() {
      this.busy = true;
      try {
        const result = await rotateRemoteBackupControlKey();
        if (!result.success) throw new Error(result.error || "生成 Control Key 失败");
        this.control = result.control || {};
        this.generatedControlKey = this.control.control_key || "";
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async testConnection() {
      this.busy = true;
      try {
        const result = await probeRemoteBackup();
        if (!result.success) throw new Error(result.error || "连接测试失败");
        this.probe = result.probe;
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async startBackup() {
      this.busy = true;
      try {
        const result = await startRemoteBackup({
          resource_types: this.selectedResourceTypes,
          description: "manual remote backup",
          ingest: true,
        });
        if (!result.success) throw new Error(result.error || "远程备份失败");
        await this.refreshBackups();
        this.selectedBackup = result.backup || null;
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async refreshBackups() {
      const result = await listRemoteBackups();
      if (!result.success) throw new Error(result.error || "加载备份列表失败");
      this.backups = result.backups || [];
    },

    async selectBackup(backup) {
      this.restorePreview = null;
      const backupId = backup?.backup_id || backup;
      if (!backupId) return;
      const result = await getRemoteBackupDetail(backupId);
      if (!result.success) throw new Error(result.error || "加载备份详情失败");
      this.selectedBackup = result.backup;
    },

    async previewRestore() {
      if (!this.selectedBackup?.backup_id) return;
      this.busy = true;
      try {
        const result = await restoreRemoteBackupPreview({
          backup_id: this.selectedBackup.backup_id,
          resource_types: this.selectedResourceTypes,
        });
        if (!result.success) throw new Error(result.error || "恢复预览失败");
        this.restorePreview = result.preview;
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },

    async restoreSelectedBackup() {
      if (!this.selectedBackup?.backup_id) return;
      const warning = this.overwrite
        ? "允许覆盖已有文件。确定要恢复到酒馆吗？"
        : "默认跳过酒馆中已存在的文件。确定要恢复到酒馆吗？";
      if (!confirm(warning)) return;
      this.busy = true;
      try {
        const result = await restoreRemoteBackup({
          backup_id: this.selectedBackup.backup_id,
          resource_types: this.selectedResourceTypes,
          overwrite: this.overwrite,
        });
        if (!result.success) throw new Error(result.error || "恢复失败");
        this.restorePreview = result.restore;
      } catch (error) {
        alert(String(error));
      } finally {
        this.busy = false;
      }
    },
  };
}
