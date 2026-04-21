import { buildBeautifyPreviewAssetUrl } from "../api/beautify.js";
import {
  clearIsolatedHtml,
  renderIsolatedHtml,
} from "../runtime/renderRuntime.js";
import { buildBeautifyPreviewDocument } from "./beautifyPreviewDocument.js";

function resolvePreviewRenderMinHeight(platform) {
  return platform === "mobile" ? 420 : 520;
}

function resolvePreviewIdentityValue(
  overrideIdentity = {},
  globalIdentity = {},
) {
  return {
    name: overrideIdentity.name || globalIdentity.name || "",
    avatarSrc: overrideIdentity.avatar_file
      ? buildBeautifyPreviewAssetUrl(overrideIdentity.avatar_file)
      : globalIdentity.avatar_file
        ? buildBeautifyPreviewAssetUrl(globalIdentity.avatar_file)
        : "",
  };
}

const MAX_PREVIEW_HOST_RETRIES = 3;

export default function beautifyPreviewFrame() {
  return {
    isPreviewLoaded: false,
    previewHostRetryCount: 0,
    previewHostFrameRetryPending: false,
    previewHostObserver: null,

    get previewHostEl() {
      if (this.$refs?.previewHost) {
        return this.$refs.previewHost;
      }
      return this.$el?.querySelector(".beautify-preview-host") || null;
    },

    get previewShellMode() {
      return this.$store.global.beautifyPreviewDevice || "pc";
    },

    get hasActiveDetail() {
      return Boolean(
        this.$store.global.beautifyActiveDetail ||
        this.$store.global.beautifyWorkspace === "settings",
      );
    },

    init() {
      this.startPreviewHostObserver();
      this.$watch("$store.global.beautifyActiveDetail", (detail) => {
        if (!detail) {
          if (this.$store.global.beautifyWorkspace !== "settings") {
            this.isPreviewLoaded = false;
            this.destroy();
            return;
          }
          if (this.isPreviewLoaded) {
            this.$nextTick(() => this.renderPreview());
          }
          return;
        }
        if (this.isPreviewLoaded) {
          this.$nextTick(() => this.renderPreview());
        }
      });
      this.$watch("$store.global.beautifyActiveVariant", () => {
        if (this.isPreviewLoaded) this.renderPreview();
      });
      this.$watch("$store.global.beautifyActiveWallpaper", () => {
        if (this.isPreviewLoaded) this.renderPreview();
      });
      this.$watch("$store.global.beautifyWorkspace", () => {
        if (this.isPreviewLoaded) this.renderPreview();
      });
      this.$watch("$store.global.beautifyGlobalSettings", () => {
        if (this.isPreviewLoaded) this.renderPreview();
      });
      this.$watch("$store.global.beautifyPreviewDevice", () => {
        if (this.isPreviewLoaded) this.renderPreview();
      });
    },

    startPreviewHostObserver() {
      if (
        this.previewHostObserver ||
        typeof MutationObserver === "undefined" ||
        !this.$el
      ) {
        return;
      }

      this.previewHostObserver = new MutationObserver(() => {
        if (!this.isPreviewLoaded || !this.previewHostEl) {
          return;
        }
        this.renderPreview();
      });

      this.previewHostObserver.observe(this.$el, {
        childList: true,
        subtree: true,
      });
    },

    loadPreview() {
      if (!this.hasActiveDetail) {
        return;
      }
      this.startPreviewHostObserver();
      this.previewHostRetryCount = 0;
      this.previewHostFrameRetryPending = false;
      this.isPreviewLoaded = true;
      this.$nextTick(() => this.renderPreview());
    },

    schedulePreviewHostFrameRetry() {
      if (this.previewHostFrameRetryPending || !this.isPreviewLoaded) {
        return;
      }

      this.previewHostFrameRetryPending = true;

      let finished = false;

      const onFrame = () => {
        if (finished) {
          return;
        }
        finished = true;
        this.previewHostFrameRetryPending = false;
        this.renderPreview();
      };

      if (typeof window !== "undefined") {
        if (typeof window.requestAnimationFrame === "function") {
          window.requestAnimationFrame(onFrame);
          if (typeof window.setTimeout === "function") {
            window.setTimeout(onFrame, 48);
          }
          return;
        }

        if (typeof window.setTimeout === "function") {
          window.setTimeout(onFrame, 16);
          return;
        }
      }

      onFrame();
    },

    resolvePreviewState() {
      const workspace = this.$store.global.beautifyWorkspace || "packages";
      const globalSettings = this.$store.global.beautifyGlobalSettings || {};
      const detail = this.$store.global.beautifyActiveDetail || {};
      const variant = this.$store.global.beautifyActiveVariant || {};
      const wallpaper = this.$store.global.beautifyActiveWallpaper || {};
      const globalWallpaper = globalSettings.wallpaper || {};
      const packageIdentities = detail.identity_overrides || {};
      const globalIdentities = globalSettings.identities || {};
      const useGlobalOnly = workspace === "settings";
      const resolvedWallpaperFile = useGlobalOnly
        ? globalWallpaper.file
        : wallpaper.file || globalWallpaper.file;

      return {
        platform: this.previewShellMode === "mobile" ? "mobile" : "pc",
        theme: useGlobalOnly ? {} : variant.theme_data || {},
        wallpaperUrl: resolvedWallpaperFile
          ? buildBeautifyPreviewAssetUrl(resolvedWallpaperFile)
          : "",
        identities: {
          character: resolvePreviewIdentityValue(
            useGlobalOnly ? {} : packageIdentities.character || {},
            globalIdentities.character || {},
          ),
          user: resolvePreviewIdentityValue(
            useGlobalOnly ? {} : packageIdentities.user || {},
            globalIdentities.user || {},
          ),
        },
      };
    },

    renderPreview() {
      if (!this.isPreviewLoaded) {
        return;
      }

      if (!this.hasActiveDetail) {
        return;
      }

      const host = this.previewHostEl;
      if (!host) {
        if (this.previewHostRetryCount < MAX_PREVIEW_HOST_RETRIES) {
          this.previewHostRetryCount += 1;
          this.$nextTick(() => this.renderPreview());
        } else {
          this.schedulePreviewHostFrameRetry();
        }
        return;
      }

      this.previewHostRetryCount = 0;
      this.previewHostFrameRetryPending = false;

      const state = this.resolvePreviewState();
      const documentHtml = buildBeautifyPreviewDocument(state);

      renderIsolatedHtml(host, {
        htmlPayload: documentHtml,
        minHeight: resolvePreviewRenderMinHeight(state.platform),
        fillHostHeight: true,
      });
    },

    destroy() {
      this.previewHostRetryCount = 0;
      this.previewHostFrameRetryPending = false;
      if (this.previewHostObserver) {
        this.previewHostObserver.disconnect();
        this.previewHostObserver = null;
      }
      const host = this.previewHostEl;
      if (host) {
        clearIsolatedHtml(host, { clearShadow: true });
      }
    },
  };
}
