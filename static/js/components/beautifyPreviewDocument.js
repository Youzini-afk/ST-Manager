function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeCssText(value) {
  return String(value ?? "").replace(/<\/style/gi, "<\\/style");
}

function sanitizePreviewCustomCss(value) {
  return String(value ?? "")
    .replace(
      /@import\s+url\((['"]?)(?:https?:)?\/\/[^)]+\1\)(?:\s+[^;]+)?\s*;?/gi,
      "",
    )
    .replace(/@import\s+(['"])(?:https?:)?\/\/[^;]+\1(?:\s+[^;]+)?\s*;?/gi, "");
}

function buildPreviewContentSecurityPolicy() {
  const localResourceOrigins = [
    "'self'",
    "data:",
    "blob:",
    "http://127.0.0.1:5000",
    "https://127.0.0.1:5000",
  ];
  const imageOrigins = [...localResourceOrigins, "http:", "https:"];

  return [
    "default-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' http://127.0.0.1:5000 https://127.0.0.1:5000",
    `font-src ${localResourceOrigins.join(" ")}`,
    `img-src ${imageOrigins.join(" ")}`,
  ].join("; ");
}

function escapeCssUrl(value) {
  return String(value ?? "")
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/[\r\n\f]/g, " ");
}

function normalizeNumber(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function clampMin(value, minimum) {
  return Math.max(value, minimum);
}

function clampRange(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function buildPreviewBodyClasses(theme = {}) {
  const classes = [];

  if (theme.timer_enabled === false) {
    classes.push("no-timer");
  }

  if (theme.timestamps_enabled === false) {
    classes.push("no-timestamps");
  }

  if (theme.message_token_count_enabled === false) {
    classes.push("no-tokenCount");
  }

  if (theme.mesIDDisplay_enabled === false) {
    classes.push("no-mesIDDisplay");
  }

  if (theme.hideChatAvatars_enabled) {
    classes.push("hideChatAvatars");
  }

  if (Number(theme.avatar_style) === 2) {
    classes.push("square-avatars");
  }

  if (Number(theme.avatar_style) === 3) {
    classes.push("rounded-avatars");
  }

  if (Number(theme.chat_display) === 1) {
    classes.push("bubblechat");
  }

  if (Number(theme.chat_display) === 2) {
    classes.push("documentstyle");
  }

  return classes;
}

const PREVIEW_IDENTITY_ASSET_PATHS = {
  character: "/static/images/beautify-preview/sumian.png",
  user: "/static/images/beautify-preview/lingyan.png",
};

function buildInlineAvatarDataUri({
  label,
  size = 96,
  radius = 24,
  background = "#d8e8c8",
  foreground = "#3c5a2a",
}) {
  const fontSize = Math.max(Math.round(size * 0.3125), 16);
  return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='0 0 ${size} ${size}'%3E%3Crect width='${size}' height='${size}' rx='${radius}' fill='${encodeURIComponent(background)}'/%3E%3Ctext x='50%25' y='55%25' font-size='${fontSize}' text-anchor='middle' fill='${encodeURIComponent(foreground)}' font-family='Arial'%3E${encodeURIComponent(label)}%3C/text%3E%3C/svg%3E`;
}

function resolvePreviewAvatarSrc({
  avatarSrc = "",
  avatarLabel = "",
  size = 96,
}) {
  if (avatarSrc) {
    return avatarSrc;
  }

  return buildInlineAvatarDataUri({
    label: avatarLabel,
    size,
    radius: Math.round(size / 4),
  });
}

function buildPreviewIdentities(identities = {}) {
  const character = identities.character || {};
  const user = identities.user || {};

  return {
    system: {
      name: "SillyTavern System",
      avatarLabel: "ST",
    },
    character: {
      name: character.name || "苏眠",
      avatarSrc: character.avatarSrc || PREVIEW_IDENTITY_ASSET_PATHS.character,
    },
    user: {
      name: user.name || "凌砚",
      avatarSrc: user.avatarSrc || PREVIEW_IDENTITY_ASSET_PATHS.user,
    },
  };
}

function serializeCssVars(vars) {
  return Object.entries(vars)
    .filter(
      ([, value]) => value !== "" && value !== null && value !== undefined,
    )
    .map(([key, value]) => `${key}:${escapeCssText(value)}`)
    .join(";");
}

function buildTopBarAction(label, panelTarget, icon) {
  const iconMap = {
    settings: {
      iconClass: "fa-solid fa-sliders fa-fw",
      iconFallback: "≡",
      id: "leftNavDrawerIcon",
    },
    formatting: {
      iconClass: "fa-solid fa-font fa-fw",
      iconFallback: "Aa",
      id: "formattingDrawerIcon",
    },
    character: {
      iconClass: "fa-solid fa-address-card fa-fw",
      iconFallback: "⋯",
      id: "rightNavDrawerIcon",
    },
  };
  const iconConfig = iconMap[panelTarget] || iconMap.settings;
  return `
    <button
      type="button"
      id="${iconConfig.id}"
      class="drawer-icon closedIcon st-preview-topbar-action ${iconConfig.iconClass}"
      data-panel-target="${escapeHtml(panelTarget)}"
      data-icon-fallback="${escapeHtml(iconConfig.iconFallback)}"
      aria-pressed="false"
      title="${escapeHtml(label)}"
    ></button>
  `;
}

function buildMessageActions() {
  return `
    <div class="mes_buttons">
      <div class="mes_button extraMesButtonsHint fa-solid fa-ellipsis" data-icon-fallback="⋯" title="Message Actions"></div>
      <div class="extraMesButtons">
        <div class="mes_button mes_translate fa-solid fa-language" data-icon-fallback="文" title="Translate message"></div>
        <div class="mes_button sd_message_gen fa-solid fa-paintbrush" data-icon-fallback="刷" title="Generate Image"></div>
        <div class="mes_button mes_narrate fa-solid fa-bullhorn" data-icon-fallback="📣" title="Narrate"></div>
        <div class="mes_button mes_prompt fa-solid fa-square-poll-horizontal" data-icon-fallback="≣" title="Prompt" style="display: none;"></div>
        <div class="mes_button mes_hide fa-solid fa-eye" data-icon-fallback="◐" title="Exclude message from prompts"></div>
        <div class="mes_button mes_unhide fa-solid fa-eye-slash" data-icon-fallback="◑" title="Include message in prompts"></div>
        <div class="mes_button mes_media_gallery fa-solid fa-photo-film" data-icon-fallback="▦" title="Toggle media display style"></div>
        <div class="mes_button mes_media_list fa-solid fa-table-cells-large" data-icon-fallback="☷" title="Toggle media display style"></div>
        <div class="mes_button mes_embed fa-solid fa-paperclip" data-icon-fallback="📎" title="Embed file or image"></div>
        <div class="mes_button mes_swipe_picker fa-solid fa-bookmark" data-icon-fallback="🔖" title="Jump to swipe history" style="display: none;"></div>
        <div class="mes_button mes_create_bookmark fa-regular fa-solid fa-flag-checkered" data-icon-fallback="⚑" title="Create checkpoint"></div>
        <div class="mes_button mes_create_branch fa-regular fa-code-branch" data-icon-fallback="⑂" title="Create branch"></div>
        <div class="mes_button mes_copy fa-solid fa-copy" data-icon-fallback="⧉" title="Copy"></div>
      </div>
      <div class="mes_button mes_bookmark fa-solid fa-flag" data-icon-fallback="⚑" title="Bookmark"></div>
      <div class="mes_button mes_edit fa-solid fa-pencil" data-icon-fallback="✎" title="Edit"></div>
    </div>
    <div class="mes_edit_buttons">
      <div class="mes_edit_done menu_button fa-solid fa-check" data-icon-fallback="✓" title="Confirm"></div>
      <div class="mes_edit_copy menu_button fa-solid fa-copy" data-icon-fallback="⧉" title="Copy this message"></div>
      <div class="mes_edit_add_reasoning menu_button fa-solid fa-lightbulb" data-icon-fallback="💡" title="Add a reasoning block"></div>
      <div class="mes_edit_delete menu_button fa-solid fa-trash-can" data-icon-fallback="🗑" title="Delete this message"></div>
      <div class="mes_edit_up menu_button fa-solid fa-chevron-up" data-icon-fallback="↑" title="Move message up"></div>
      <div class="mes_edit_down menu_button fa-solid fa-chevron-down" data-icon-fallback="↓" title="Move message down"></div>
      <div class="mes_edit_cancel menu_button fa-solid fa-xmark" data-icon-fallback="×" title="Cancel"></div>
    </div>
  `;
}

function buildReasoningBlock() {
  return `
    <details class="mes_reasoning_details">
      <summary class="mes_reasoning_summary">
        <div class="mes_reasoning_header_block flex-container">
          <div class="mes_reasoning_header flex-container">
            <span class="mes_reasoning_header_title">Thought for some time</span>
            <div class="mes_reasoning_arrow">^</div>
          </div>
        </div>
        <div class="mes_reasoning_actions flex-container">
          <div class="mes_reasoning_edit_done menu_button edit_button fa-solid fa-check" data-icon-fallback="✓" aria-label="Confirm Edit"></div>
          <div class="mes_reasoning_delete menu_button edit_button fa-solid fa-trash-can" data-icon-fallback="🗑" aria-label="Remove reasoning"></div>
          <div class="mes_reasoning_edit_cancel menu_button edit_button fa-solid fa-xmark" data-icon-fallback="×" aria-label="Cancel edit"></div>
          <div class="mes_reasoning_close_all mes_button fa-solid fa-minimize" data-icon-fallback="▁" aria-label="Collapse all reasoning blocks"></div>
          <div class="mes_reasoning_copy mes_button fa-solid fa-copy" data-icon-fallback="⧉" aria-label="Copy reasoning"></div>
          <div class="mes_reasoning_edit mes_button fa-solid fa-pencil" data-icon-fallback="✎" aria-label="Edit reasoning"></div>
        </div>
      </summary>
      <div class="mes_reasoning">${escapeHtml("🌿 梧桐絮语：这条预览消息保留了思维链容器，便于主题命中相关选择器。")}</div>
    </details>
  `;
}

function buildMessage({
  mesId,
  name,
  avatarLabel,
  avatarSrc = "",
  messageHtml,
  timestamp,
  tokenCounter,
  isUser = false,
  isSystem = false,
  includeReasoning = false,
  extraClass = "",
}) {
  const classes = ["mes"];
  if (extraClass) {
    classes.push(extraClass);
  }

  const resolvedAvatarSrc = resolvePreviewAvatarSrc({ avatarSrc, avatarLabel });

  return `
    <div class="${classes.join(" ")}" mesid="${escapeHtml(mesId)}" ch_name="${escapeHtml(name)}" is_user="${isUser ? "true" : "false"}" is_system="${isSystem ? "true" : "false"}" bookmark_link="">
      <div class="for_checkbox"></div><input type="checkbox" class="del_checkbox">
      <div class="mesAvatarWrapper">
        <div class="avatar">
          <img alt="${escapeHtml(name)}" src="${escapeHtml(resolvedAvatarSrc)}">
        </div>
        <div class="mesIDDisplay">#${escapeHtml(mesId)}</div>
        <div class="mes_timer">${escapeHtml(timestamp)}</div>
        <div class="tokenCounterDisplay">${escapeHtml(tokenCounter)}</div>
      </div>
      <div class="swipe_left">&lt;</div>
      <div class="mes_block">
        <div class="ch_name flex-container justifySpaceBetween">
          <div class="flex-container flex1 alignitemscenter">
            <div class="flex-container alignItemsBaseline">
              <span class="name_text">${escapeHtml(name)}</span>
              <i class="mes_ghost fa-solid fa-ghost" data-icon-fallback="👻" title="Ghost"></i>
              <small class="timestamp">${escapeHtml(timestamp)}</small>
            </div>
          </div>
          ${buildMessageActions()}
        </div>
        ${includeReasoning ? buildReasoningBlock() : ""}
        <div class="mes_text">${messageHtml}</div>
        <div class="mes_media_wrapper"></div>
        <div class="mes_file_wrapper"></div>
        <div class="mes_bias"></div>
      </div>
      <div class="flex-container swipeRightBlock flexFlowColumn flexNoGap">
        <div class="swipe_right">></div>
        <div class="swipes-counter">1/1</div>
      </div>
    </div>
  `;
}

const DEFAULT_PREVIEW_SCENE_ID = "daily";

function buildPreviewScenes(normalizedPlatform = "pc") {
  return [
    {
      id: "daily",
      label: "日常陪伴",
      description: "轻松自然的日常聊天",
      messages: [
        {
          role: "system",
          mesId: "1",
          timestamp: "System",
          tokenCounter: "meta",
          extraClass: "smallSysMes",
          messageHtml:
            '<p>当前预览使用内置聊天场景，便于观察主题在真实聊天节奏里的表现。</p><p><a href="#" data-preview-link="disabled">Example link</a></p><hr>',
        },
        {
          role: "character",
          mesId: "2",
          timestamp: "08:14",
          tokenCounter: "318 tok",
          includeReasoning: true,
          messageHtml:
            "<p><strong>粗体</strong>、<em>斜体</em>、<u>下划线</u> 和 <code>inline code</code>。</p><p>你总算忙完啦？先坐下缓一缓，我把灯调暗一点。</p><blockquote>Welcome back. Theme variables now drive this isolated preview.</blockquote>",
        },
        {
          role: "user",
          mesId: "3",
          timestamp: "08:15",
          tokenCounter: "142 tok",
          extraClass: "last_mes",
          messageHtml: `<p>列表、链接和代码块也需要稳定呈现。</p><ul><li>Keep the message shell realistic.</li><li>Make rich text and code samples visible.</li></ul><pre><code>const preview = buildBeautifyPreviewDocument({ platform: '${escapeHtml(normalizedPlatform)}' });</code></pre>`,
        },
      ],
    },
    {
      id: "flirty",
      label: "暧昧互动",
      description: "更柔和的情绪和停顿",
      messages: [
        {
          role: "character",
          mesId: "1",
          timestamp: "22:06",
          tokenCounter: "204 tok",
          messageHtml:
            "<p>你刚刚那句“只看一眼消息”听起来，可不像真的只看一眼。</p>",
        },
        {
          role: "user",
          mesId: "2",
          timestamp: "22:06",
          tokenCounter: "72 tok",
          messageHtml: "<p>被你发现了。我本来只是想确认你睡了没。</p>",
        },
      ],
    },
    {
      id: "lore",
      label: "设定说明",
      description: "长段落和说明性文本",
      messages: [
        {
          role: "user",
          mesId: "1",
          timestamp: "19:24",
          tokenCounter: "104 tok",
          messageHtml: "<p>你之前提过“潮灯湾”，那地方到底是什么样？</p>",
        },
        {
          role: "character",
          mesId: "2",
          timestamp: "19:25",
          tokenCounter: "352 tok",
          messageHtml:
            "<p>港口白天看着安静，到了夜里，栈桥边会亮起成串的冷色灯。</p>",
        },
      ],
    },
    {
      id: "story",
      label: "剧情推进",
      description: "带动作与状态变化的连续片段",
      messages: [
        {
          role: "system",
          mesId: "1",
          timestamp: "System",
          tokenCounter: "meta",
          extraClass: "smallSysMes",
          messageHtml:
            "<p>场景预览：轻量剧情推进，用于观察多轮叙事节奏。</p><hr>",
        },
        {
          role: "character",
          mesId: "2",
          timestamp: "23:11",
          tokenCounter: "180 tok",
          messageHtml:
            "<p>巷口的风把纸灯吹得一晃一晃的，我抬手替你挡了下火。</p>",
        },
      ],
    },
    {
      id: "system",
      label: "系统提示",
      description: "系统通知与规则提醒",
      messages: [
        {
          role: "system",
          mesId: "1",
          timestamp: "System",
          tokenCounter: "meta",
          extraClass: "smallSysMes",
          messageHtml:
            "<p>系统消息、提示条和轻量说明也会通过相同的 ST 消息壳层渲染。</p>",
        },
      ],
    },
  ];
}

function buildPreviewSceneMessage(message, previewIdentities) {
  if (message.role === "system") {
    return buildMessage({
      ...message,
      name: previewIdentities.system.name,
      avatarLabel: previewIdentities.system.avatarLabel,
      isSystem: true,
    });
  }

  if (message.role === "user") {
    return buildMessage({
      ...message,
      name: previewIdentities.user.name,
      avatarLabel: "CL",
      avatarSrc: previewIdentities.user.avatarSrc,
      isUser: true,
    });
  }

  return buildMessage({
    ...message,
    name: previewIdentities.character.name,
    avatarLabel: "QW",
    avatarSrc: previewIdentities.character.avatarSrc,
  });
}

function buildPreviewSceneMessages(scene, previewIdentities) {
  return scene.messages
    .map((message) => buildPreviewSceneMessage(message, previewIdentities))
    .join("");
}

function buildPreviewSceneSwitcher(scenes) {
  return `
    <div class="st-preview-scene-switcher" data-preview-scene-switcher>
      ${scenes
        .map(
          (scene) => `
            <button
              type="button"
              class="st-preview-scene-button${scene.id === DEFAULT_PREVIEW_SCENE_ID ? " is-active" : ""}"
              data-preview-scene-button="${escapeHtml(scene.id)}"
              aria-pressed="${scene.id === DEFAULT_PREVIEW_SCENE_ID ? "true" : "false"}"
            >${escapeHtml(scene.label)}</button>
          `,
        )
        .join("")}
    </div>
  `;
}

function buildPreviewSceneTemplates(scenes, previewIdentities) {
  return `
    <div class="st-preview-scene-templates" hidden>
      ${scenes
        .map(
          (scene) => `
            <template data-preview-scene-template="${escapeHtml(scene.id)}" data-preview-scene-description="${escapeHtml(scene.description || "")}">${buildPreviewSceneMessages(scene, previewIdentities)}</template>
          `,
        )
        .join("")}
    </div>
  `;
}

function buildPreviewBehaviorScript() {
  return `
    (() => {
      const root = document.querySelector('.st-preview-root');
      if (!root) return;
      const buttons = Array.from(document.querySelectorAll('[data-panel-target]'));
      const panels = Array.from(document.querySelectorAll('[data-panel-surface]'));
      const shells = Array.from(document.querySelectorAll('[data-panel-shell]'));
      const drawers = Array.from(document.querySelectorAll('.inline-drawer'));
      const sceneButtons = Array.from(document.querySelectorAll('[data-preview-scene-button]'));
      const chat = document.querySelector('[data-preview-chat-messages]') || document.querySelector('#chat');
      const description = document.querySelector('[data-preview-scene-description]');

      const toggleInlineDrawer = (drawer, expand = true) => {
        const icon = drawer.querySelector(':scope > .inline-drawer-header .inline-drawer-icon');
        const content = drawer.querySelector(':scope > .inline-drawer-content');

        if (!icon || !content) {
          return;
        }

        if (expand) {
          icon.classList.remove('down', 'fa-circle-chevron-down');
          icon.classList.add('up', 'fa-circle-chevron-up');
          content.style.display = 'block';
        } else {
          icon.classList.remove('up', 'fa-circle-chevron-up');
          icon.classList.add('down', 'fa-circle-chevron-down');
          content.style.display = 'none';
        }

        drawer.dispatchEvent(new CustomEvent('inline-drawer-toggle', { bubbles: true }));
      };

      const sync = (activePanel) => {
        root.dataset.activePanel = activePanel;
        buttons.forEach((button) => {
          const active = button.dataset.panelTarget === activePanel;
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
          button.classList.toggle('is-active', active);
          button.classList.toggle('openIcon', active);
          button.classList.toggle('closedIcon', !active);
        });
        panels.forEach((panel) => {
          const isActive = panel.dataset.panelSurface === activePanel;
          panel.classList.toggle('openDrawer', isActive);
          panel.classList.toggle('closedDrawer', !isActive);
          panel.classList.toggle('open', isActive);
        });
        shells.forEach((shell) => {
          const isActive = shell.dataset.panelShell === activePanel;
          shell.classList.toggle('openDrawer', isActive);
          shell.classList.toggle('closedDrawer', !isActive);
          shell.classList.toggle('open', isActive);
        });
        drawers.forEach((drawer) => {
          const isActive = activePanel === 'settings';
          drawer.classList.toggle('open', isActive);
          drawer.classList.toggle('closed', !isActive);
          toggleInlineDrawer(drawer, isActive);
        });
      };

      const bindPreviewLinks = () => {
        document.querySelectorAll('[data-preview-link="disabled"]').forEach((link) => {
          if (link.__stPreviewLinkBound) {
            return;
          }
          link.__stPreviewLinkBound = true;
          link.addEventListener('click', (event) => {
            event.preventDefault();
          });
        });
      };

      const scrollChatToBottom = () => {
        const chat = document.querySelector('#chat');
        if (!chat) {
          return;
        }
        chat.scrollTop = chat.scrollHeight;
      };

      const renderScene = (sceneId) => {
        if (!chat) {
          return;
        }

        const template = document.querySelector('[data-preview-scene-template="' + sceneId + '"]');
        if (!template) {
          return;
        }

        root.dataset.activeScene = sceneId;
        chat.innerHTML = template.innerHTML;

        if (description) {
          description.textContent = template.dataset.previewSceneDescription || '';
        }

        sceneButtons.forEach((button) => {
          const isActive = button.dataset.previewSceneButton === sceneId;
          button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
          button.classList.toggle('is-active', isActive);
        });

        bindPreviewLinks();
        window.requestAnimationFrame(scrollChatToBottom);
      };

      buttons.forEach((button) => {
        button.addEventListener('click', () => {
          const nextPanel = button.dataset.panelTarget || 'none';
          sync(root.dataset.activePanel === nextPanel ? 'none' : nextPanel);
        });
      });

      drawers.forEach((drawer) => {
        const toggle = drawer.querySelector(':scope > .inline-drawer-toggle');
        if (!toggle) return;
        toggle.addEventListener('click', () => {
          const isOpen = drawer.classList.contains('open');
          drawer.classList.toggle('open', !isOpen);
          drawer.classList.toggle('closed', isOpen);
          toggleInlineDrawer(drawer, !isOpen);
        });
      });

      sceneButtons.forEach((button) => {
        button.addEventListener('click', () => {
          renderScene(button.dataset.previewSceneButton);
        });
      });

      sync(root.dataset.activePanel || 'none');
      bindPreviewLinks();
      const chatRoot = document.querySelector('#chat');
      const defaultScene =
        root.dataset.activeScene ||
        root.dataset.defaultScene ||
        ((chatRoot && chatRoot.dataset && chatRoot.dataset.previewDefaultScene) || 'daily');
      renderScene(defaultScene);
      window.requestAnimationFrame(scrollChatToBottom);
      window.addEventListener('load', scrollChatToBottom);
    })();
  `;
}

export function buildBeautifyPreviewThemeVars(theme = {}, wallpaperUrl = "") {
  const fontScale = (() => {
    const normalized = normalizeNumber(theme.font_scale, 1);
    return normalized > 0 ? normalized : 1;
  })();
  const blurStrength = clampMin(normalizeNumber(theme.blur_strength, 10), 0);
  const shadowWidth = clampMin(normalizeNumber(theme.shadow_width, 2), 0);
  const chatWidth = clampRange(normalizeNumber(theme.chat_width, 50), 25, 100);
  const safeWallpaperUrl = wallpaperUrl
    ? `url("${escapeCssUrl(wallpaperUrl)}")`
    : "none";

  return {
    "--SmartThemeBodyColor": theme.main_text_color || "#f8fafc",
    "--SmartThemeEmColor":
      theme.italics_text_color || theme.main_text_color || "#cbd5e1",
    "--SmartThemeUnderlineColor":
      theme.underline_text_color || theme.quote_text_color || "#38bdf8",
    "--SmartThemeQuoteColor": theme.quote_text_color || "#f59e0b",
    "--SmartThemeBlurTintColor":
      theme.blur_tint_color || "rgba(15, 23, 42, 0.48)",
    "--SmartThemeChatTintColor":
      theme.chat_tint_color || "rgba(15, 23, 42, 0.52)",
    "--SmartThemeUserMesBlurTintColor":
      theme.user_mes_blur_tint_color || "rgba(59, 130, 246, 0.22)",
    "--SmartThemeBotMesBlurTintColor":
      theme.bot_mes_blur_tint_color || "rgba(15, 23, 42, 0.58)",
    "--SmartThemeShadowColor": theme.shadow_color || "rgba(15, 23, 42, 0.35)",
    "--SmartThemeBorderColor":
      theme.border_color || "rgba(148, 163, 184, 0.24)",
    "--fontScale": String(fontScale),
    "--blurStrength": `${blurStrength}px`,
    "--shadowWidth": `${shadowWidth}px`,
    "--SmartThemeBlurStrength": "var(--blurStrength)",
    "--mainFontSize": "calc(var(--fontScale) * 16px)",
    "--sheldWidth": `${chatWidth}vw`,
    "--wallpaperUrl": safeWallpaperUrl,
  };
}

export function buildBeautifyPreviewSampleMarkup(
  platform = "pc",
  theme = {},
  identities = {},
) {
  const normalizedPlatform = platform === "mobile" ? "mobile" : "pc";
  const previewIdentities = buildPreviewIdentities(identities);
  const previewScenes = buildPreviewScenes(normalizedPlatform);
  const defaultPreviewScene =
    previewScenes.find((scene) => scene.id === DEFAULT_PREVIEW_SCENE_ID) ||
    previewScenes[0];
  const sendFormClasses = ["no-connection"];

  if (theme.compact_input_area) {
    sendFormClasses.push("compact");
  }

  const sendFormClassAttr = sendFormClasses.length
    ? ` class="${sendFormClasses.join(" ")}"`
    : "";
  const noConnectionText = "Not connected to API!";
  const connectedText = "Type a message, or /? for help";
  const topSettingsMarkup = `
    <div id="top-settings-holder">
      <div class="drawer st-preview-topbar-drawer">
        <div id="ai-config-button" class="left-drawer">
        ${buildTopBarAction("AI Response Configuration", "settings")}
        ${buildTopBarAction("AI Response Formatting", "formatting")}
        ${buildTopBarAction("Character Management", "character")}
        </div>
      </div>
      <div class="drawer-content fillLeft closedDrawer left-drawer" id="left-nav-panel" data-panel-shell="settings">
        <div id="left-nav-panelheader" class="fa-solid fa-grip drag-grabber"></div>
        <div class="scrollableInner">
          <div class="drawer-content st-preview-drawer-panel st-preview-settings-drawer" style="display:none !important"></div>
          <div class="st-preview-panel-body st-preview-drawer-panel st-preview-settings-drawer" data-panel-surface="settings">
            <div id="lm_button_panel_pin_div" title="Locked = AI Configuration panel will stay open">
              <div class="right_menu_button"></div>
              <div class="unchecked fa-solid fa-unlock right_menu_button"></div>
              <div class="checked fa-solid fa-lock right_menu_button"></div>
            </div>
            <div id="clickSlidersTips" class="toggle-description">Click slider numbers to input manually.</div>
            <a class="topRightInset" href="#"></a>
            <span class="note-link-span"></span>
            <a class="topRightInset notes-link" href="#" title="Documentation on sampling parameters.">
              <span class="note-link-span fa-solid fa-circle-question"></span>
            </a>
            <div class="inline-drawer-header">
              <span class="standoutHeader">Preview Settings</span>
              <span>Panel</span>
            </div>
            <div class="options-content" id="table_drawer_content">
              <div class="margin0 title_restorable standoutHeader">
                <strong><span>Chat Completion Presets</span></strong>
                <div class="flex-container gap3px">
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-file-import"></i></div>
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-file-export"></i></div>
                </div>
              </div>
              <div class="flex-container flexNoGap">
                <select id="settings_preset" class="flex1 text_pole"><option>Default</option></select>
                <div class="flex-container marginLeft5 gap3px">
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-save"></i></div>
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-pencil"></i></div>
                </div>
              </div>
              <div class="range-block-title title_restorable">
                <span>Secondary Preset Block</span>
              </div>
              <div class="flex-container flexNoGap">
                <select id="settings_preset_openai" class="flex1 text_pole"><option>Chat Completion</option></select>
                <div class="flex-container marginLeft5 gap3px">
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-file-circle-plus"></i></div>
                  <div class="menu_button menu_button_icon"><i class="fa-fw fa-solid fa-recycle"></i></div>
                </div>
              </div>
              <label class="checkbox_label"><input type="checkbox" checked><span>Stream responses</span></label>
              <div class="neutral_warning">For preview only: these controls mirror ST-like form surfaces.</div>
              <div class="online_status">
                <div class="online_status_indicator"></div>
                <div class="online_status_text">Connected</div>
              </div>
              <div class="range-block-title openai_restorable">
                <span>World Info format template</span>
                <div id="wi_format_restore" class="right_menu_button"><div class="fa-solid fa-clock-rotate-left"></div></div>
              </div>
              <div class="wide100p">
                <textarea id="wi_format_textarea" class="text_pole textarea_compact" rows="3">{{wi}}</textarea>
              </div>
              <div class="inline-drawer wide100p">
                <div class="inline-drawer-toggle inline-drawer-header">
                  <div class="inline-drawer-icon down"></div>
                  <b>Quick Prompts Edit</b>
                  <div class="fa-solid fa-circle-chevron-down inline-drawer-icon down"></div>
                </div>
                <div class="inline-drawer-content">
                  <div class="range-block m-t-1">
                    <div class="justifyLeft">Main</div>
                    <div class="wide100p">
                      <textarea id="main_prompt_quick_edit_textarea" class="text_pole textarea_compact" rows="4">{{main}}</textarea>
                    </div>
                  </div>
                </div>
              </div>
              <label class="st-preview-setting-row"><span>Blur Strength</span><input type="range" min="0" max="30" value="10"></label>
              <label class="st-preview-setting-row"><span>Chat Width</span><select><option>Balanced</option></select></label>
              <label class="st-preview-setting-row"><span>Theme Surface</span><input type="text" value="Glass / paper layered shell"></label>
            </div>
          </div>
          <div class="drawer-content fillLeft closedDrawer left-drawer" id="user-settings-drawer"></div>
          <div class="drawer-content fillLeft closedDrawer left-drawer" id="advanced-settings-drawer"></div>
          <div class="drawer-content fillLeft closedDrawer left-drawer" id="extensions-settings-drawer"></div>
        </div>
      </div>
      <div class="drawer-content fillLeft closedDrawer left-drawer" id="advanced-formatting-button" data-panel-shell="formatting">
        <div class="scrollableInner">
          <div class="drawer-content st-preview-drawer-panel st-preview-formatting-drawer" style="display:none !important"></div>
          <div class="st-preview-panel-body st-preview-drawer-panel st-preview-formatting-drawer" id="AdvancedFormatting" data-panel-surface="formatting">
            <div class="flex-container alignItemsBaseline">
              <h3 class="margin0 flex1 flex-container alignItemsBaseline">
                <span class="standoutHeader">Advanced Formatting</span>
                <a class="notes-link" href="#" title="Documentation on advanced formatting.">
                  <span class="note-link-span fa-solid fa-circle-question"></span>
                </a>
              </h3>
              <div class="flex-container">
                <div id="af_master_import" class="menu_button menu_button_icon" title="Import Advanced Formatting settings">
                  <i class="fa-solid fa-file-import"></i>
                  <span>Master Import</span>
                </div>
                <div id="af_master_export" class="menu_button menu_button_icon" title="Export Advanced Formatting settings">
                  <i class="fa-solid fa-file-export"></i>
                  <span>Master Export</span>
                </div>
              </div>
            </div>
            <div id="advanced-formatting-cc-notice" class="info-block warning">
              <i class="fa-solid fa-triangle-exclamation"></i>
              <span>Grayed-out options have no effect when Chat Completion API is used.</span>
            </div>
            <div class="flex-container spaceEvenly">
              <div id="ContextSettings" class="flex-container flexNoGap flexFlowColumn flex1">
                <h4 class="standoutHeader title_restorable" data-cc-null>
                  <div>
                    <span>Context Template</span>
                  </div>
                  <div class="flex-container">
                    <label for="context_derived" class="checkbox_label flex1" title="Derive from Model Metadata, if possible.">
                      <input id="context_derived" type="checkbox" checked style="display:none;">
                      <small><i class="fa-solid fa-bolt menu_button margin0"></i></small>
                    </label>
                  </div>
                </h4>
                <div class="flex-container flexNoGap">
                  <select id="context_presets" class="flex1 text_pole"><option>Default Context</option></select>
                  <div class="flex-container justifyCenter gap3px">
                    <div class="menu_button fa-solid fa-save" title="Update current template"></div>
                    <div class="menu_button fa-solid fa-pencil" title="Rename current template"></div>
                    <div class="menu_button fa-solid fa-file-circle-plus" title="Save template as"></div>
                    <div class="menu_button fa-solid fa-recycle" title="Restore current template"></div>
                  </div>
                </div>
                <div class="wide100p">
                  <label for="context_story_string" class="flex-container justifySpaceBetween alignitemscenter">
                    <small>Story String</small>
                    <i class="editor_maximize fa-solid fa-maximize right_menu_button" title="Expand the editor"></i>
                  </label>
                  <textarea id="context_story_string" class="text_pole textarea_compact" rows="3">{{system}}</textarea>
                </div>
                <div class="flex-container flexFlowColumn">
                  <div id="context_story_string_position_block">
                    <label for="context_story_string_position"><small>Position:</small></label>
                    <select id="context_story_string_position" class="text_pole">
                      <option>Default (top of context)</option>
                    </select>
                  </div>
                  <div id="context_story_string_inject_settings" class="flex-container gap3px">
                    <div class="flex1">
                      <label for="context_story_string_depth"><small>Depth:</small></label>
                      <input type="number" id="context_story_string_depth" class="text_pole" min="0" max="99" value="4">
                    </div>
                    <div class="flex1">
                      <label for="context_story_string_role"><small>Role:</small></label>
                      <select id="context_story_string_role" class="text_pole"><option>System</option></select>
                    </div>
                  </div>
                </div>
                <div class="flex-container gap3px">
                  <div class="flex1">
                    <label for="context_example_separator"><small>Example Separator</small></label>
                    <textarea id="context_example_separator" class="text_pole textarea_compact" rows="2">***</textarea>
                  </div>
                  <div class="flex1">
                    <label for="context_chat_start"><small>Chat Start</small></label>
                    <textarea id="context_chat_start" class="text_pole textarea_compact" rows="2">### Response:</textarea>
                  </div>
                </div>
              </div>
              <div id="InstructSettingsColumn" class="flex-container flexNoGap flexFlowColumn flex1">
                <h4 class="standoutHeader title_restorable justifySpaceBetween">
                  <div class="flex-container">
                    <span>Instruct Template</span>
                  </div>
                  <div class="flex-container gap3px">
                    <label for="instruct_derived" class="checkbox_label flex1" title="Derive from Model Metadata, if possible.">
                      <input id="instruct_derived" type="checkbox" style="display:none;">
                      <small><i class="fa-solid fa-bolt menu_button margin0"></i></small>
                    </label>
                    <label for="instruct_bind_to_context" class="checkbox_label flex1" title="Bind to Context">
                      <input id="instruct_bind_to_context" type="checkbox" style="display:none;">
                      <small><i class="fa-solid fa-link menu_button margin0"></i></small>
                    </label>
                    <label id="instruct_enabled_label" for="instruct_enabled" class="checkbox_label flex1" title="Enable Instruct Mode">
                      <input id="instruct_enabled" type="checkbox" checked style="display:none;">
                      <small><i class="fa-solid fa-power-off menu_button togglable margin0"></i></small>
                    </label>
                  </div>
                </h4>
                <div class="flex-container flexNoGap">
                  <select id="instruct_presets" class="flex1 text_pole"><option>Roleplay Default</option></select>
                  <div class="flex-container justifyCenter gap3px">
                    <div class="menu_button fa-solid fa-save" title="Update current template"></div>
                    <div class="menu_button fa-solid fa-pencil" title="Rename current template"></div>
                    <div class="menu_button fa-solid fa-file-circle-plus" title="Save template as"></div>
                    <div class="menu_button fa-solid fa-recycle" title="Restore current template"></div>
                  </div>
                </div>
                <div>
                  <label for="instruct_activation_regex"><small>Activation Regex</small></label>
                  <input type="text" id="instruct_activation_regex" class="text_pole textarea_compact" placeholder="e.g. /llama(-)?[3|3.1]/i">
                </div>
                <div>
                  <label for="instruct_wrap" class="checkbox_label"><input id="instruct_wrap" type="checkbox" checked><small>Wrap Sequences with Newline</small></label>
                  <label for="instruct_macro" class="checkbox_label"><input id="instruct_macro" type="checkbox" checked><small>Replace Macro in Sequences</small></label>
                  <label for="instruct_sequences_as_stop_strings" class="checkbox_label"><input id="instruct_sequences_as_stop_strings" type="checkbox"><small>Sequences as Stop Strings</small></label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="drawer-content fillRight closedDrawer right-drawer" id="right-nav-panel" data-panel-shell="character">
        <div id="right-nav-panelheader" class="fa-solid fa-grip drag-grabber"></div>
        <div id="CharListButtonAndHotSwaps" class="flex-container flexnowrap">
          <div class="flexFlowColumn flex-container">
            <div id="rm_button_panel_pin_div" class="alignitemsflexstart" title="Locked = Character Management panel will stay open">
              <label for="rm_button_panel_pin">
                <div class="fa-solid unchecked fa-unlock right_menu_button"></div>
                <div class="fa-solid checked fa-lock right_menu_button"></div>
              </label>
            </div>
            <div class="right_menu_button fa-solid fa-list-ul" id="rm_button_characters" title="Select/Create Characters"></div>
          </div>
          <div id="HotSwapWrapper" class="alignitemscenter flex-container margin0auto wide100p">
            <div class="hotswap avatars_inline scroll-reset-container expander"></div>
          </div>
        </div>
        <div id="rm_PinAndTabs">
          <div id="right-nav-panel-tabs">
            <div id="rm_button_selected_ch">
              <h2 class="interactable">${escapeHtml(previewIdentities.character.name)}</h2>
            </div>
            <div id="result_info" class="flex-container" style="display: none;">
              <div id="result_info_text" title="Token counts may be inaccurate and provided just for reference." data-i18n="[title]Token counts may be inaccurate and provided just for reference.">
                <div><strong id="result_info_total_tokens" title="Total tokens" data-i18n="[title]Total tokens"><span data-i18n="Calculating...">Calculating...</span></strong>&nbsp;<span data-i18n="Tokens">Tokens</span></div>
                <div><small title="Permanent tokens" data-i18n="[title]Permanent tokens">(<span id="result_info_permanent_tokens"></span>&nbsp;<span data-i18n="Permanent">Permanent</span>)</small></div>
              </div>
              <a id="chartokenwarning" class="right_menu_button fa-solid fa-triangle-exclamation" href="https://docs.sillytavern.app/usage/core-concepts/characterdesign/#character-tokens" target="_blank" title="About Token &#39;Limits&#39;" data-i18n="[title]About Token &#39;Limits&#39;"></a>
              <i class="fa-solid fa-ranking-star right_menu_button rm_stats_button" title="Click for stats!" data-i18n="[title]Click for stats!"></i>
              <i id="hideCharPanelAvatarButton" class="fa-solid fa-eye right_menu_button" title="Toggle character info panel" data-i18n="[title]Toggle character info panel"></i>
            </div>
          </div>
        </div>
        <div class="scrollableInner">
          <div class="drawer-content st-preview-drawer-panel st-preview-character-panel" style="display:none !important"></div>
          <div class="st-preview-panel-body st-preview-drawer-panel st-preview-character-panel" id="character_popup" data-panel-surface="character">
            <div class="st-preview-character-card">
              <div class="avatar-container selected">
                <div class="avatar"><img alt="${escapeHtml(previewIdentities.character.name)}" src="${escapeHtml(previewIdentities.character.avatarSrc)}"></div>
              </div>
              <div class="st-preview-character-copy">
                <div class="ch_name"><span class="name_text">${escapeHtml(previewIdentities.character.name)}</span></div>
                <div class="flex-container gap3px">
                  <div class="menu_button_icon" title="Favorite"><i class="fa-solid fa-star"></i></div>
                  <div class="menu_button_icon" title="Duplicate"><i class="fa-solid fa-copy"></i></div>
                </div>
                <div class="flex-container alignItemsBaseline">
                  <a class="notes-link" href="#"><span class="note-link-span">?</span></a>
                  <span>Persona metadata preview</span>
                </div>
                <div class="character_select" id="rm_button_selected_ch">
                  <div class="avatar"><img alt="${escapeHtml(previewIdentities.character.name)}" src="${escapeHtml(previewIdentities.character.avatarSrc)}"></div>
                  <div class="character_name_block">
                    <h2>${escapeHtml(previewIdentities.character.name)}</h2>
                    <div class="ch_additional_info">默认演示角色</div>
                  </div>
                </div>
                <div id="rm_print_characters_block">
                  <div class="character_select_container">
                    <div class="avatar-container selected">
                      <div class="avatar"><img alt="${escapeHtml(previewIdentities.character.name)}" src="${escapeHtml(previewIdentities.character.avatarSrc)}"></div>
                      <div class="character_name_block">
                        <div class="ch_name">${escapeHtml(previewIdentities.character.name)}</div>
                        <div class="ch_additional_info">Currently selected</div>
                      </div>
                    </div>
                  </div>
                  <div class="character_select_container">
                    <div class="avatar-container">
                      <div class="avatar"></div>
                      <div class="character_name_block">
                        <div class="ch_name">Nova</div>
                        <div class="ch_additional_info">Alternative preset shell</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="st-preview-character-tags">fantasy · guide · preview persona</div>
                <textarea class="text_pole textarea_compact" rows="2">Character note preview</textarea>
                <p>角色卡快速面板用于暴露更多主题表面，包括头像、名称、标签与简介容器。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
  const chatMarkup = `
    ${buildPreviewSceneSwitcher(previewScenes)}
    <div class="st-preview-scene-description" data-preview-scene-description>${escapeHtml(defaultPreviewScene.description || "")}</div>
    <div id="chat" data-preview-default-scene="${escapeHtml(defaultPreviewScene.id)}">
      <div data-preview-chat-messages>
        ${buildPreviewSceneMessages(defaultPreviewScene, previewIdentities)}
      </div>
    </div>
    ${buildPreviewSceneTemplates(previewScenes, previewIdentities)}
  `;
  const sendFormMarkup = `
    <div id="form_sheld">
      <div id="dialogue_del_mes">
        <div id="dialogue_del_mes_ok" class="menu_button">Delete</div>
        <div id="dialogue_del_mes_cancel" class="menu_button">Cancel</div>
      </div>
      <div id="send_form"${sendFormClassAttr}>
        <form id="file_form" class="wide100p displayNone">
          <div class="file_attached">
            <input id="file_form_input" type="file" multiple hidden>
            <input id="embed_file_input" type="file" multiple hidden>
            <i class="fa-solid fa-file-alt"></i>
            <span class="file_name">File Name</span>
            <span class="file_size">File Size</span>
            <button id="file_form_reset" type="reset" class="menu_button" title="Remove the file">
              <i class="fa fa-times"></i>
            </button>
          </div>
        </form>
        <div id="nonQRFormItems">
          <div id="leftSendForm" class="alignContentCenter">
            <div id="options_button" class="fa-solid fa-bars interactable" data-icon-fallback="≡" aria-label="Options"></div>
          </div>
          <textarea id="send_textarea" name="text" class="mdHotkeys" data-i18n="[no_connection_text]${escapeHtml(noConnectionText)};[connected_text]${escapeHtml(connectedText)}" placeholder="${escapeHtml(noConnectionText)}" no_connection_text="${escapeHtml(noConnectionText)}" connected_text="${escapeHtml(connectedText)}" autocomplete="off"></textarea>
          <div id="rightSendForm" class="alignContentCenter">
            <div id="stscript_continue" title="Continue script execution" class="stscript_btn stscript_continue">
              <i class="fa-solid fa-play"></i>
            </div>
            <div id="stscript_pause" title="Pause script execution" class="stscript_btn stscript_pause">
              <i class="fa-solid fa-pause"></i>
            </div>
            <div id="stscript_stop" title="Abort script execution" class="stscript_btn stscript_stop">
              <i class="fa-solid fa-stop"></i>
            </div>
            <div id="mes_stop" title="Abort request" class="mes_stop">
              <i class="fa-solid fa-circle-stop"></i>
            </div>
            <div id="mes_impersonate" class="fa-solid fa-user-secret interactable displayNone" title="Ask AI to write your message for you" tabindex="0"></div>
            <div id="mes_continue" class="fa-fw fa-solid fa-arrow-right interactable displayNone" title="Continue the last message" data-icon-fallback=">" aria-label="Continue"></div>
            <div id="send_but" class="fa-solid fa-paper-plane interactable displayNone" title="Send a message" data-icon-fallback="➤" aria-label="Send"></div>
          </div>
        </div>
      </div>
    </div>
  `;

  return `
    <div class="st-preview-root" data-platform="${escapeHtml(normalizedPlatform)}" data-active-panel="none">
      <div class="st-preview-wallpaper"></div>
      <div class="st-preview-overlay"></div>
      <div class="st-preview-shell">
        <div id="top-bar"></div>
        ${topSettingsMarkup}
        <div id="sheld">
          <div id="sheldheader" class="fa-solid fa-grip drag-grabber"></div>
          ${chatMarkup}
          ${sendFormMarkup}
        </div>
      </div>
    </div>
  `;
}

export function buildBeautifyPreviewDocument({
  theme = {},
  wallpaperUrl = "",
  platform = "pc",
  identities = {},
} = {}) {
  const normalizedPlatform = platform === "mobile" ? "mobile" : "pc";
  const themeVars = buildBeautifyPreviewThemeVars(theme, wallpaperUrl);
  const bodyClasses = buildPreviewBodyClasses(theme);
  const bodyClassAttr = bodyClasses.length
    ? ` class="${escapeHtml(bodyClasses.join(" "))}"`
    : "";
  const serializedVars = serializeCssVars(themeVars);
  const customCss = escapeCssText(
    sanitizePreviewCustomCss(theme.custom_css || ""),
  );
  const markup = buildBeautifyPreviewSampleMarkup(
    normalizedPlatform,
    theme,
    identities,
  );
  const behaviorScript = buildPreviewBehaviorScript();
  const contentSecurityPolicy = escapeHtml(buildPreviewContentSecurityPolicy());
  const mobileStylesheetMarkup =
    normalizedPlatform === "mobile"
      ? '\n    <link rel="stylesheet" href="/static/vendor/sillytavern/css/mobile-styles.css" />'
      : "";

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, viewport-fit=cover, initial-scale=1" />
    <meta http-equiv="Content-Security-Policy" content="${contentSecurityPolicy}" />
    <title>Beautify Native ST Preview</title>
    <link rel="stylesheet" href="/static/vendor/sillytavern/style.css" />
    ${mobileStylesheetMarkup}
    <style>:root{${serializedVars}}</style>
    <style>
      html, body {
        margin: 0;
        width: 100%;
        height: 100%;
        min-height: 0;
      }

      body {
        position: relative;
        overflow: hidden;
        color: var(--SmartThemeBodyColor);
      }

      .st-preview-root {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        min-height: 0;
        position: relative;
      }

      .st-preview-wallpaper,
      .st-preview-overlay {
        position: absolute;
        inset: 0;
        pointer-events: none;
      }

      .st-preview-wallpaper {
        background-image: var(--wallpaperUrl);
        background-size: cover;
        background-position: center;
      }

      .st-preview-overlay {
        background: linear-gradient(var(--SmartThemeBlurTintColor), var(--SmartThemeBlurTintColor));
      }

      .st-preview-shell {
        position: relative;
        z-index: 1;
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        padding: 20px;
      }

      .st-preview-scene-switcher {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 0 0 12px;
      }

      .st-preview-scene-button {
        border: 1px solid var(--SmartThemeBorderColor);
        background: var(--SmartThemeChatTintColor);
        color: var(--SmartThemeBodyColor);
        border-radius: 999px;
        padding: 6px 12px;
        font: inherit;
        cursor: default;
      }

      .st-preview-scene-button.is-active {
        background: var(--SmartThemeUserMesBlurTintColor);
      }

      #top-bar {
        display: none;
      }

      #top-settings-holder {
        display: none;
      }

      .drawer-content.st-preview-drawer-panel[style*='display:none'] {
        display: none !important;
      }

      .st-preview-panel-body {
        display: none;
      }

      .st-preview-root[data-active-panel='settings'] [data-panel-surface='settings'],
      .st-preview-root[data-active-panel='formatting'] [data-panel-surface='formatting'],
      .st-preview-root[data-active-panel='character'] [data-panel-surface='character'] {
        display: block;
      }

      .st-preview-root[data-active-panel='settings'] [data-panel-shell='settings'],
      .st-preview-root[data-active-panel='formatting'] [data-panel-shell='formatting'],
      .st-preview-root[data-active-panel='character'] [data-panel-shell='character'] {
        display: block;
      }

      .flex-container {
        display: flex;
      }

      .justifySpaceBetween {
        justify-content: space-between;
      }

      .flex1 {
        flex: 1;
      }

      .alignitemscenter,
      .alignContentCenter,
      .alignItemsBaseline {
        align-items: center;
      }

      .alignItemsBaseline {
        align-items: baseline;
      }

      .flexFlowColumn {
        flex-direction: column;
      }

      .flexNoGap {
        gap: 0;
      }
    </style>
    <style>${customCss}</style>
  </head>
  <body data-st-preview-platform="${escapeHtml(normalizedPlatform)}"${bodyClassAttr}>
    ${markup}
    <script>${behaviorScript.replace(/<\/script/gi, "<\\/script")}</script>
  </body>
</html>`;
}
