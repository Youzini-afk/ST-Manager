import {
  importSharedWallpaper,
  selectSharedWallpaper,
} from "../api/resource.js";

function normalizeSource(value) {
  const source = String(value || "")
    .trim()
    .toLowerCase();
  if (source === "builtin") return source;
  if (source === "package_embedded") return "beautify";
  return "imported";
}

export default function sharedWallpaperPicker(options = {}) {
  return {
    sourceFilter: options.sourceFilter || "all",

    get wallpapers() {
      const items = this.$store?.global?.sharedWallpapers;
      return Array.isArray(items) ? items : [];
    },

    get groupedWallpapers() {
      return this.wallpapers.reduce(
        (groups, item) => {
          groups[normalizeSource(item?.source_type)].push(item);
          return groups;
        },
        { builtin: [], imported: [], beautify: [] },
      );
    },

    get filteredWallpapers() {
      if (this.sourceFilter === "all") return this.wallpapers;
      return this.wallpapers.filter(
        (item) => normalizeSource(item?.source_type) === this.sourceFilter,
      );
    },

    setSourceFilter(source) {
      this.sourceFilter = source || "all";
    },

    isSelected(item) {
      const selectedId =
        this.$store?.global?.settingsForm?.manager_wallpaper_id || "";
      return String(item?.id || "") === String(selectedId);
    },

    applySelectedWallpaper(wallpaper) {
      const globalStore = this.$store?.global;
      if (!globalStore || !wallpaper?.id) return;

      const current = Array.isArray(globalStore.sharedWallpapers)
        ? globalStore.sharedWallpapers.filter(
            (entry) => entry?.id !== wallpaper.id,
          )
        : [];
      current.push(wallpaper);
      globalStore.sharedWallpapers = current;

      if (globalStore.settingsForm) {
        globalStore.settingsForm.manager_wallpaper_id = wallpaper.id || "";
        globalStore.settingsForm.bg_url = "";
      }

      if (
        typeof globalStore.updateBackgroundImage === "function" &&
        typeof globalStore.resolveManagerBackgroundUrl === "function"
      ) {
        globalStore.updateBackgroundImage(
          globalStore.resolveManagerBackgroundUrl(),
        );
      }

      if (
        typeof window !== "undefined" &&
        typeof window.dispatchEvent === "function" &&
        typeof CustomEvent === "function"
      ) {
        window.dispatchEvent(
          new CustomEvent("shared-wallpaper-selected", {
            detail: { wallpaper },
          }),
        );
      }
    },

    async selectWallpaper(item) {
      const wallpaperId = String(item?.id || "").trim();
      if (!wallpaperId) return null;

      const res = await selectSharedWallpaper({
        wallpaper_id: wallpaperId,
        selection_target: "manager",
      });
      if (!res?.success) {
        alert("选择共享壁纸失败: " + (res?.msg || "unknown"));
        return res;
      }

      const wallpaper = res.wallpaper || item;
      this.applySelectedWallpaper(wallpaper);

      return res;
    },

    async handleImport(event) {
      const file = event?.target?.files?.[0];
      if (!file) return null;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await importSharedWallpaper(formData, "manager");
        if (!res?.success) {
          alert("导入共享壁纸失败: " + (res?.msg || "unknown"));
          return res;
        }

        const item = res.item || null;
        if (item?.id) this.applySelectedWallpaper(item);
        return res;
      } finally {
        event.target.value = "";
      }
    },
  };
}
