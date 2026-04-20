import {
  buildBeautifyPreviewAssetUrl,
  deleteBeautifyPackage,
  getBeautifyPackage,
  importBeautifyTheme,
  importBeautifyWallpaper,
  listBeautifyPackages,
  updateBeautifyVariant,
} from "../api/beautify.js";

function filterPackages(items, search, platformFilter) {
  const keyword = String(search || "")
    .trim()
    .toLowerCase();
  return (items || []).filter((item) => {
    const nameMatch =
      !keyword ||
      String(item.name || "")
        .toLowerCase()
        .includes(keyword);
    const platformMatch =
      platformFilter === "all" ||
      (item.platforms || []).includes(platformFilter);
    return nameMatch && platformMatch;
  });
}

export default function beautifyGrid() {
  return {
    isLoading: false,
    isActionLoading: false,
    importTargetPackageId: "",

    get packages() {
      return this.$store.global.beautifyList || [];
    },

    set packages(val) {
      this.$store.global.beautifyList = Array.isArray(val) ? val : [];
      return true;
    },

    get beautifySearch() {
      return this.$store.global.beautifySearch || "";
    },

    set beautifySearch(val) {
      this.$store.global.beautifySearch = val;
      return true;
    },

    get platformFilter() {
      return this.$store.global.beautifyPlatformFilter || "all";
    },

    set platformFilter(val) {
      this.$store.global.beautifyPlatformFilter = val;
      return true;
    },

    get selectedPackageId() {
      return this.$store.global.beautifySelectedPackageId || "";
    },

    set selectedPackageId(val) {
      this.$store.global.beautifySelectedPackageId = val;
      return true;
    },

    get selectedVariantId() {
      return this.$store.global.beautifySelectedVariantId || "";
    },

    set selectedVariantId(val) {
      this.$store.global.beautifySelectedVariantId = val;
      return true;
    },

    get selectedWallpaperId() {
      return this.$store.global.beautifySelectedWallpaperId || "";
    },

    set selectedWallpaperId(val) {
      this.$store.global.beautifySelectedWallpaperId = val;
      return true;
    },

    get selectedVariantPlatform() {
      return this.$store.global.beautifyPreviewDevice || "pc";
    },

    set selectedVariantPlatform(val) {
      this.$store.global.beautifyPreviewDevice = val;
      return true;
    },

    get activeDetail() {
      return this.$store.global.beautifyActiveDetail || null;
    },

    get activePackage() {
      return this.activeDetail || null;
    },

    get activeVariant() {
      return this.$store.global.beautifyActiveVariant || null;
    },

    get activeWallpaper() {
      return this.$store.global.beautifyActiveWallpaper || null;
    },

    get filteredPackages() {
      return filterPackages(
        this.packages,
        this.beautifySearch,
        this.platformFilter,
      );
    },

    get hasPcVariant() {
      return (
        !!this.findVariantByPlatform("pc") ||
        !!this.findVariantByPlatform("dual")
      );
    },

    get hasMobileVariant() {
      return (
        !!this.findVariantByPlatform("mobile") ||
        !!this.findVariantByPlatform("dual")
      );
    },

    get hasDualVariant() {
      return !!this.findVariantByPlatform("dual");
    },

    get wallpaperOptions() {
      const variant = this.activeVariant;
      const detail = this.activeDetail;
      if (!variant || !detail) return [];
      return (variant.wallpaper_ids || [])
        .map((id) => detail.wallpapers?.[id])
        .filter(Boolean);
    },

    init() {
      this.$watch("$store.global.currentMode", (mode) => {
        if (mode === "beautify") {
          this.fetchPackages();
        }
      });

      this.$watch("$store.global.beautifySearch", () => {
        if (this.$store.global.currentMode === "beautify") {
          this.ensureSelectedPackageStillVisible();
        }
      });

      window.addEventListener("refresh-beautify-list", () => {
        if (this.$store.global.currentMode === "beautify") {
          this.fetchPackages();
        }
      });

      window.stUploadBeautifyThemeFiles = (files) =>
        this.handleThemeFiles(files);
      if (this.$store.global.currentMode === "beautify") {
        this.fetchPackages();
      }
    },

    async fetchPackages() {
      this.isLoading = true;
      try {
        const res = await listBeautifyPackages();
        this.packages = res.items || [];
        if (!this.selectedPackageId && this.packages.length) {
          await this.selectPackage(this.packages[0].id);
        } else if (this.selectedPackageId) {
          await this.selectPackage(this.selectedPackageId, {
            preserveSelection: true,
          });
        }
      } catch (error) {
        this.$store.global.showToast(`加载美化库失败: ${error}`, 3000);
      } finally {
        this.isLoading = false;
      }
    },

    async selectPackage(packageId, options = {}) {
      const targetId = String(packageId || "").trim();
      if (!targetId) return;
      const res = await getBeautifyPackage(targetId);
      if (!res?.success || !res.item) {
        return;
      }

      this.selectedPackageId = targetId;
      this.$store.global.beautifyActiveDetail = res.item;

      const preserveSelection = !!options.preserveSelection;
      let nextVariant = null;
      if (
        preserveSelection &&
        this.selectedVariantId &&
        res.item.variants?.[this.selectedVariantId]
      ) {
        nextVariant = res.item.variants[this.selectedVariantId];
      } else {
        nextVariant = this.resolveDefaultVariant(res.item);
      }

      this.applyActiveVariant(nextVariant);
    },

    resolveDefaultVariant(detail) {
      if (!detail || !detail.variants) return null;
      return (
        this.findVariantByPlatform("pc", detail) ||
        this.findVariantByPlatform("mobile", detail) ||
        this.findVariantByPlatform("dual", detail) ||
        Object.values(detail.variants)[0] ||
        null
      );
    },

    applyActiveVariant(variant) {
      if (!variant) {
        this.$store.global.beautifyActiveVariant = null;
        this.$store.global.beautifyActiveWallpaper = null;
        this.selectedVariantId = "";
        this.selectedWallpaperId = "";
        return;
      }

      this.selectedVariantId = variant.id;
      this.$store.global.beautifyActiveVariant = variant;

      const wallpaper = this.resolveActiveWallpaper(variant);
      this.$store.global.beautifyActiveWallpaper = wallpaper;
      this.selectedWallpaperId = wallpaper?.id || "";

      if (variant.platform === "mobile") {
        this.selectedVariantPlatform = "mobile";
      } else {
        this.selectedVariantPlatform = "pc";
      }
    },

    resolveActiveWallpaper(variant) {
      const detail = this.activeDetail;
      if (!detail || !variant) return null;
      if (
        this.selectedWallpaperId &&
        detail.wallpapers?.[this.selectedWallpaperId]
      ) {
        return detail.wallpapers[this.selectedWallpaperId];
      }
      const nextWallpaperId = (variant.wallpaper_ids || [])[0];
      return nextWallpaperId
        ? detail.wallpapers?.[nextWallpaperId] || null
        : null;
    },

    findVariantByPlatform(platform, detail = this.activeDetail) {
      if (!detail || !detail.variants) return null;
      return (
        Object.values(detail.variants).find(
          (variant) => variant.platform === platform,
        ) || null
      );
    },

    async previewPlatform(platform) {
      const variant = this.findVariantByPlatform(platform);
      if (variant) {
        this.applyActiveVariant(variant);
        return;
      }

      const dualVariant = this.findVariantByPlatform("dual");
      if (dualVariant && (platform === "pc" || platform === "mobile")) {
        this.applyActiveVariant(dualVariant);
        this.selectedVariantPlatform = platform;
      }
    },

    selectWallpaper(wallpaperId) {
      const wallpaper = this.activeDetail?.wallpapers?.[wallpaperId] || null;
      this.$store.global.beautifyActiveWallpaper = wallpaper;
      this.selectedWallpaperId = wallpaper?.id || "";
    },

    cycleWallpaper() {
      const options = this.wallpaperOptions;
      if (!options.length) return;
      const currentIndex = options.findIndex(
        (item) => item.id === this.selectedWallpaperId,
      );
      const next =
        options[(currentIndex + 1 + options.length) % options.length];
      this.selectWallpaper(next.id);
    },

    async handleThemeFiles(fileList) {
      const files = Array.from(fileList || []).filter((file) =>
        String(file.name || "")
          .toLowerCase()
          .endsWith(".json"),
      );
      if (!files.length) {
        this.$store.global.showToast("请选择 theme JSON 文件", 2200);
        return;
      }

      this.isActionLoading = true;
      try {
        let lastPackageId = "";
        for (const file of files) {
          const res = await importBeautifyTheme(file);
          if (!res?.success) {
            throw new Error(res?.error || "导入主题失败");
          }
          lastPackageId = res.package?.id || lastPackageId;
        }
        await this.fetchPackages();
        if (lastPackageId) {
          await this.selectPackage(lastPackageId);
        }
        this.$store.global.showToast(`已导入 ${files.length} 个主题`, 2200);
      } catch (error) {
        this.$store.global.showToast(String(error.message || error), 3200);
      } finally {
        this.isActionLoading = false;
      }
    },

    async handleWallpaperFiles(fileList) {
      const file = Array.from(fileList || [])[0];
      if (!file || !this.selectedPackageId || !this.selectedVariantId) {
        this.$store.global.showToast("请先选择一个变体后再导入壁纸", 2400);
        return;
      }

      this.isActionLoading = true;
      try {
        const res = await importBeautifyWallpaper(
          file,
          this.selectedPackageId,
          this.selectedVariantId,
        );
        if (!res?.success) {
          throw new Error(res?.error || "导入壁纸失败");
        }
        await this.selectPackage(this.selectedPackageId, {
          preserveSelection: true,
        });
        this.selectWallpaper(res.wallpaper?.id || "");
        this.$store.global.showToast("壁纸已导入并绑定到当前变体", 2200);
      } catch (error) {
        this.$store.global.showToast(String(error.message || error), 3200);
      } finally {
        this.isActionLoading = false;
      }
    },

    async updateCurrentVariantPlatform(platform) {
      if (!this.selectedPackageId || !this.selectedVariantId) return;
      this.isActionLoading = true;
      try {
        const res = await updateBeautifyVariant({
          package_id: this.selectedPackageId,
          variant_id: this.selectedVariantId,
          platform,
        });
        if (!res?.success) {
          throw new Error(res?.error || "更新端类型失败");
        }
        await this.selectPackage(this.selectedPackageId, {
          preserveSelection: true,
        });
      } catch (error) {
        this.$store.global.showToast(String(error.message || error), 3200);
      } finally {
        this.isActionLoading = false;
      }
    },

    async removeCurrentPackage() {
      if (!this.selectedPackageId) return;
      if (!confirm("确定删除当前美化包吗？库内主题和壁纸会一起移除。")) return;
      this.isActionLoading = true;
      try {
        const res = await deleteBeautifyPackage(this.selectedPackageId);
        if (!res?.success) {
          throw new Error(res?.error || "删除失败");
        }
        this.selectedPackageId = "";
        this.$store.global.beautifyActiveDetail = null;
        this.$store.global.beautifyActiveVariant = null;
        this.$store.global.beautifyActiveWallpaper = null;
        await this.fetchPackages();
      } catch (error) {
        this.$store.global.showToast(String(error.message || error), 3200);
      } finally {
        this.isActionLoading = false;
      }
    },

    wallpaperPreviewUrl(relativePath) {
      return buildBeautifyPreviewAssetUrl(relativePath);
    },

    supportsPlatform(item, platform) {
      return (
        (item?.platforms || []).includes(platform) ||
        (item?.platforms || []).includes("dual")
      );
    },

    ensureSelectedPackageStillVisible() {
      const stillVisible = this.filteredPackages.some(
        (item) => item.id === this.selectedPackageId,
      );
      if (!stillVisible && this.filteredPackages.length) {
        this.selectPackage(this.filteredPackages[0].id);
      }
    },
  };
}
