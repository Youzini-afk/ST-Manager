import { mergePresetVersions } from '../api/presets.js';

export default function presetVersionMergeModal() {
  return {
    showModal: false,
    items: [],
    flattenedItems: [],
    _selectedTargetId: '',
    _familyName: '',
    isFamilyNameDirty: false,
    isSubmitting: false,

    get selectedTargetId() {
      return this._selectedTargetId;
    },

    set selectedTargetId(value) {
      this._selectedTargetId = value || '';
      if (this.isFamilyNameDirty) return;
      this._familyName = this.selectedTargetItem?.family_name || this.selectedTargetItem?.name || '';
    },

    get familyName() {
      return this._familyName;
    },

    set familyName(value) {
      this._familyName = value || '';
      if (!this.showModal) return;
      const selectedName = this.selectedTargetItem?.family_name || this.selectedTargetItem?.name || '';
      this.isFamilyNameDirty = this._familyName !== selectedName;
    },

    get previewVersions() {
      return this.flattenedItems;
    },

    get selectedTargetItem() {
      return this.flattenedItems.find((item) => item.id === this.selectedTargetId) || null;
    },

    init() {
      window.addEventListener('open-preset-version-merge', (event) => {
        this.open(event.detail || {});
      });
    },

    open(payload = {}) {
      this.items = Array.isArray(payload.items) ? payload.items.slice() : [];
      this.flattenedItems = this.items.flatMap((item) => {
        if (item?.entry_type === 'family' && Array.isArray(item.versions)) {
          return item.versions.map((version) => ({
            id: version.id,
            name: version.name || version.filename || version.id,
            family_name: item.name || version.family_name || version.name || version.filename || version.id,
            version_label:
              version?.preset_version?.version_label ||
              String(version.filename || version.name || version.id).replace(/\.json$/i, ''),
          }));
        }
        return [{
          id: item.id,
          name: item.name || item.filename || item.id,
          family_name: item.family_name || item.name || item.filename || item.id,
          version_label: String(item.filename || item.name || item.id).replace(/\.json$/i, ''),
        }];
      });
      this.selectedTargetId = this.flattenedItems[0]?.id || '';
      this.isFamilyNameDirty = false;
      this.familyName = this.selectedTargetItem?.family_name || this.selectedTargetItem?.name || '';
      this.showModal = true;
    },

    close() {
      this.showModal = false;
      this.items = [];
      this.flattenedItems = [];
      this.selectedTargetId = '';
      this.familyName = '';
      this.isFamilyNameDirty = false;
      this.isSubmitting = false;
    },

    async confirmMerge() {
      if (!this.selectedTargetId || this.flattenedItems.length < 2 || this.isSubmitting) return;
      this.isSubmitting = true;
      try {
        const res = await mergePresetVersions({
          target_preset_id: this.selectedTargetId,
          source_preset_ids: this.flattenedItems.map((item) => item.id),
          family_name: this.familyName || this.selectedTargetItem?.family_name || this.selectedTargetItem?.name || 'Preset Family',
        });
        if (!res?.success) {
          this.$store.global.showToast(res?.msg || '合并失败', 'error');
          return;
        }
        this.$store.global.showToast('已合并为多版本预设');
        window.dispatchEvent(new CustomEvent('refresh-preset-list'));
        window.dispatchEvent(new CustomEvent('open-preset-reader', { detail: res.preset }));
        this.close();
      } catch (error) {
        this.$store.global.showToast(error?.message || '合并失败', 'error');
      } finally {
        this.isSubmitting = false;
      }
    },
  };
}
