/**
 * static/js/components/cardAdvancedFilter.js
 * 角色卡高级筛选抽屉组件
 */

export default function cardAdvancedFilter() {
  return {
    get showCardAdvancedFilterDrawer() {
      return this.$store.global.showCardAdvancedFilterDrawer;
    },

    get cardAdvancedFilterDraft() {
      if (!this.$store.global.cardAdvancedFilterDraft) {
        this.$store.global.openCardAdvancedFilterDrawer();
      }
      return this.$store.global.cardAdvancedFilterDraft;
    },

    get draft() {
      return this.cardAdvancedFilterDraft;
    },

    get isCardsMode() {
      return this.$store.global.currentMode === "cards";
    },

    get tagIncludeCount() {
      return Array.isArray(this.$store.global.viewState.filterTags)
        ? this.$store.global.viewState.filterTags.length
        : 0;
    },

    get tagExcludeCount() {
      return Array.isArray(this.$store.global.viewState.excludedTags)
        ? this.$store.global.viewState.excludedTags.length
        : 0;
    },

    get tagSummary() {
      if (!this.tagIncludeCount && !this.tagExcludeCount) {
        return "当前未设置标签条件";
      }

      const summaryParts = [];

      if (this.tagIncludeCount) {
        summaryParts.push(`包含 ${this.tagIncludeCount} 个标签`);
      }

      if (this.tagExcludeCount) {
        summaryParts.push(`排除 ${this.tagExcludeCount} 个标签`);
      }

      return summaryParts.join("，");
    },

    requestClose() {
      this.$store.global.closeCardAdvancedFilterDrawer();
    },

    clearDraft() {
      this.$store.global.clearCardAdvancedFilterDraft();
    },

    clearTagFilters() {
      this.$store.global.clearCardAdvancedFilterItem("tags");
    },

    applyFilters() {
      const result = this.$store.global.applyCardAdvancedFilterDraft();
      if (result && result.success === false && result.error) {
        alert(result.error);
      }
    },

    openTagFilterEditor() {
      this.$store.global.closeCardAdvancedFilterDrawer();
      window.dispatchEvent(new CustomEvent("open-tag-filter-modal"));
    },
  };
}
