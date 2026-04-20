import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'static/js/components/beautifyPreviewDocument.js'


def run_preview_document_check(script_body: str) -> None:
    node_script = textwrap.dedent(
        f'''
        import {{ pathToFileURL }} from 'node:url';
        const module = await import(pathToFileURL({json.dumps(str(MODULE_PATH.resolve()))}).href);
        {textwrap.dedent(script_body)}
        '''
    )
    result = subprocess.run(
        ['node', '--input-type=module', '-e', node_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_build_beautify_preview_document_loads_pc_vendored_st_assets_without_mobile_stylesheet():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({
          platform: 'pc',
          theme: { custom_css: 'body { color: red; }' },
          wallpaperUrl: '/api/beautify/preview-asset/packages/pkg_demo/wallpapers/demo.webp',
        });

        if (!html.includes('/static/vendor/sillytavern/style.css')) throw new Error('missing vendored ST style.css');
        if (html.includes('/static/vendor/sillytavern/css/mobile-styles.css')) throw new Error('pc preview should not load mobile stylesheet');
        if (html.includes('st-preview-base.css')) throw new Error('old preview base css should not load');
        if (!html.includes('body { color: red; }')) throw new Error('missing custom css');
        if (!html.includes('id="top-settings-holder"')) throw new Error('missing ST top settings holder');
        if (!html.includes('id="chat"')) throw new Error('missing ST chat');
        if (!html.includes('id="send_form"')) throw new Error('missing ST send form');
        '''
    )


def test_build_beautify_preview_document_loads_mobile_stylesheet_only_for_mobile_preview():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({
          platform: 'mobile',
          theme: { custom_css: 'body { color: red; }' },
          wallpaperUrl: '/api/beautify/preview-asset/packages/pkg_demo/wallpapers/demo.webp',
        });

        if (!html.includes('/static/vendor/sillytavern/style.css')) throw new Error('missing vendored ST style.css');
        if (!html.includes('/static/vendor/sillytavern/css/mobile-styles.css')) throw new Error('missing vendored ST mobile stylesheet');
        '''
    )


def test_build_beautify_preview_document_preserves_theme_variables_and_platform_markers():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({
          theme: {
            main_text_color: '#f8fafc',
            italics_text_color: '#c084fc',
            underline_text_color: '#22d3ee',
            quote_text_color: '#f59e0b',
            blur_tint_color: 'rgba(15, 23, 42, 0.48)',
            chat_tint_color: 'rgba(15, 23, 42, 0.52)',
            user_mes_blur_tint_color: 'rgba(59, 130, 246, 0.22)',
            bot_mes_blur_tint_color: 'rgba(15, 23, 42, 0.58)',
            shadow_color: 'rgba(15, 23, 42, 0.35)',
            border_color: 'rgba(148, 163, 184, 0.24)',
            font_scale: 1.1,
            blur_strength: 12,
            shadow_width: 3,
            chat_width: 55,
            timer_enabled: false,
            timestamps_enabled: false,
            message_token_count_enabled: false,
            mesIDDisplay_enabled: false,
            hideChatAvatars_enabled: true,
            avatar_style: 3,
            chat_display: 1,
            compact_input_area: true,
          },
          wallpaperUrl: '/api/beautify/preview-asset/demo.png',
          platform: 'mobile',
        });

        for (const token of [
          '--SmartThemeBodyColor:#f8fafc',
          '--SmartThemeEmColor:#c084fc',
          '--SmartThemeUnderlineColor:#22d3ee',
          '--SmartThemeQuoteColor:#f59e0b',
          '--SmartThemeBlurTintColor:rgba(15, 23, 42, 0.48)',
          '--SmartThemeChatTintColor:rgba(15, 23, 42, 0.52)',
          '--SmartThemeUserMesBlurTintColor:rgba(59, 130, 246, 0.22)',
          '--SmartThemeBotMesBlurTintColor:rgba(15, 23, 42, 0.58)',
          '--SmartThemeShadowColor:rgba(15, 23, 42, 0.35)',
          '--SmartThemeBorderColor:rgba(148, 163, 184, 0.24)',
          '--fontScale:1.1',
          '--blurStrength:12px',
          '--shadowWidth:3px',
          '--SmartThemeBlurStrength:var(--blurStrength)',
          '--mainFontSize:calc(var(--fontScale) * 16px)',
          '--sheldWidth:55vw',
          '--wallpaperUrl:url("/api/beautify/preview-asset/demo.png")',
          '<title>Beautify Native ST Preview</title>',
          '<body data-st-preview-platform="mobile" class="no-timer no-timestamps no-tokenCount no-mesIDDisplay hideChatAvatars rounded-avatars bubblechat">',
          '<div id="send_form" class="no-connection compact">',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_theme_vars_normalizes_and_clamps_theme_inputs():
    run_preview_document_check(
        '''
        const vars = module.buildBeautifyPreviewThemeVars({
          font_scale: 'bad-value',
          blur_strength: -4,
          shadow_width: -2,
          chat_width: 300,
        }, '');

        if (vars['--fontScale'] !== '1') throw new Error(`expected normalized fontScale, got ${vars['--fontScale']}`);
        if (vars['--blurStrength'] !== '0px') throw new Error(`expected clamped blurStrength, got ${vars['--blurStrength']}`);
        if (vars['--shadowWidth'] !== '0px') throw new Error(`expected clamped shadowWidth, got ${vars['--shadowWidth']}`);
        if (vars['--SmartThemeBlurStrength'] !== 'var(--blurStrength)') throw new Error(`expected derived SmartThemeBlurStrength, got ${vars['--SmartThemeBlurStrength']}`);
        if (vars['--sheldWidth'] !== '100vw') throw new Error(`expected clamped sheldWidth, got ${vars['--sheldWidth']}`);
        '''
    )


def test_build_beautify_preview_document_escapes_css_sensitive_content():
    run_preview_document_check(
        r'''
        const wallpaper = String.raw`https://example.com/a") ;background:red;/*\\unsafe`;
        const escapedCustomClose = String.raw`<\/style><script>window.BAD=1</script>`;
        const escapedThemeValue = String.raw`--SmartThemeBodyColor:<\/style><script>window.BAD_THEME=1</script><style>;`;
        const escapedWallpaperSuffix = String.raw`/*\\\\unsafe")`;
        const html = module.buildBeautifyPreviewDocument({
          theme: {
            custom_css: 'body::before{content:"</style><script>window.BAD=1</script>";}',
            main_text_color: '</style><script>window.BAD_THEME=1</script><style>',
          },
          wallpaperUrl: wallpaper,
          platform: 'mobile',
        });

        if (html.includes('</style><script>window.BAD=1</script>')) throw new Error('custom css escaped unsafely');
        if (html.includes('</style><script>window.BAD_THEME=1</script><style>')) throw new Error('theme variable escaped unsafely');
        if (!html.includes(escapedCustomClose)) throw new Error('custom css escape marker missing');
        if (!html.includes(escapedThemeValue)) throw new Error('theme variable escape marker missing');

        const wallpaperUrlValue = module.buildBeautifyPreviewThemeVars({}, wallpaper)['--wallpaperUrl'];
        if (!html.includes(`--wallpaperUrl:${wallpaperUrlValue}`)) throw new Error('wallpaper css variable missing');
        if (!wallpaperUrlValue.includes('\\"')) throw new Error('wallpaper quote was not escaped');
        if (!wallpaperUrlValue.endsWith(escapedWallpaperSuffix)) throw new Error('wallpaper backslash was not escaped');
        '''
    )


def test_build_beautify_preview_sample_markup_contains_minimal_st_surfaces():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'id="top-bar"',
          'id="top-settings-holder"',
          'id="left-nav-panel"',
          'id="AdvancedFormatting"',
          'id="character_popup"',
          'id="sheld"',
          'id="sheldheader"',
          'id="chat"',
          'class="mesAvatarWrapper"',
          'class="mes_buttons"',
          'class="mes_reasoning_summary"',
          'id="form_sheld"',
          'id="send_form"',
          'id="send_textarea"',
          'id="send_but"',
          'data-panel-target="settings"',
          'data-panel-target="formatting"',
          'data-panel-target="character"',
          'data-panel-surface="settings"',
          'data-panel-surface="formatting"',
          'data-panel-surface="character"',
          'data-panel-shell="settings"',
          'data-panel-shell="formatting"',
          'data-panel-shell="character"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const sheldIndex = html.indexOf('id="sheld"');
        const sheldHeaderIndex = html.indexOf('id="sheldheader"');
        const chatIndex = html.indexOf('id="chat"');
        const formSheldIndex = html.indexOf('id="form_sheld"');

        if (!(sheldIndex < sheldHeaderIndex && sheldHeaderIndex < chatIndex && chatIndex < formSheldIndex)) {
          throw new Error('preview #sheld should contain #sheldheader before #chat and #form_sheld');
        }

        for (const token of [
          'id="sheldheader" class="fa-solid fa-grip drag-grabber"',
          '<div id="sheld">',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        if (html.indexOf('id="chat"') > html.indexOf('id="form_sheld"')) {
          throw new Error('chat should render before the send form shell');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_send_form_scaffolding():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'id="dialogue_del_mes"',
          'id="dialogue_del_mes_ok"',
          'id="dialogue_del_mes_cancel"',
          'id="file_form" class="wide100p displayNone"',
          'id="file_form_input" type="file" multiple hidden',
          'id="embed_file_input" type="file" multiple hidden',
          'class="file_attached"',
          'class="file_name"',
          'class="file_size"',
          'id="file_form_reset" type="reset" class="menu_button"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const formSheldIndex = html.indexOf('id="form_sheld"');
        const dialogueIndex = html.indexOf('id="dialogue_del_mes"');
        const sendFormIndex = html.indexOf('id="send_form"');
        const fileFormIndex = html.indexOf('id="file_form"');
        const nonQrIndex = html.indexOf('id="nonQRFormItems"');

        if (!(formSheldIndex < dialogueIndex && dialogueIndex < sendFormIndex && sendFormIndex < fileFormIndex && fileFormIndex < nonQrIndex)) {
          throw new Error('preview send-form scaffold should match ST ordering under #form_sheld');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_right_send_form_actions():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'id="rightSendForm" class="alignContentCenter"',
          'id="stscript_continue" title="Continue script execution" class="stscript_btn stscript_continue"',
          'id="stscript_pause" title="Pause script execution" class="stscript_btn stscript_pause"',
          'id="stscript_stop" title="Abort script execution" class="stscript_btn stscript_stop"',
          'id="mes_stop" title="Abort request" class="mes_stop"',
          'id="mes_impersonate" class="fa-solid fa-user-secret interactable displayNone"',
          'id="mes_continue" class="fa-fw fa-solid fa-arrow-right interactable displayNone"',
          'id="send_but" class="fa-solid fa-paper-plane interactable displayNone"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const rightSendFormIndex = html.indexOf('id="rightSendForm"');
        const continueScriptIndex = html.indexOf('id="stscript_continue"');
        const pauseScriptIndex = html.indexOf('id="stscript_pause"');
        const stopScriptIndex = html.indexOf('id="stscript_stop"');
        const mesStopIndex = html.indexOf('id="mes_stop"');
        const impersonateIndex = html.indexOf('id="mes_impersonate"');
        const continueIndex = html.indexOf('id="mes_continue"');
        const sendButIndex = html.indexOf('id="send_but"');

        if (!(rightSendFormIndex < continueScriptIndex && continueScriptIndex < pauseScriptIndex && pauseScriptIndex < stopScriptIndex && stopScriptIndex < mesStopIndex && mesStopIndex < impersonateIndex && impersonateIndex < continueIndex && continueIndex < sendButIndex)) {
          throw new Error('preview right send-form actions should follow ST ordering');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_send_form_and_textarea_attributes():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'id="send_form" class="no-connection"',
          'id="send_textarea" name="text" class="mdHotkeys"',
          'data-i18n="[no_connection_text]Not connected to API!;[connected_text]Type a message, or /? for help"',
          'placeholder="Not connected to API!"',
          'no_connection_text="Not connected to API!"',
          'connected_text="Type a message, or /? for help"',
          'autocomplete="off"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_message_edit_controls():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'class="mes_edit_buttons"',
          'class="mes_edit_done menu_button fa-solid fa-check"',
          'class="mes_edit_copy menu_button fa-solid fa-copy"',
          'class="mes_edit_add_reasoning menu_button fa-solid fa-lightbulb"',
          'class="mes_edit_delete menu_button fa-solid fa-trash-can"',
          'class="mes_edit_up menu_button fa-solid fa-chevron-up"',
          'class="mes_edit_down menu_button fa-solid fa-chevron-down"',
          'class="mes_edit_cancel menu_button fa-solid fa-xmark"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const editButtonsIndex = html.indexOf('class="mes_edit_buttons"');
        const doneIndex = html.indexOf('class="mes_edit_done menu_button fa-solid fa-check"');
        const copyIndex = html.indexOf('class="mes_edit_copy menu_button fa-solid fa-copy"');
        const reasoningIndex = html.indexOf('class="mes_edit_add_reasoning menu_button fa-solid fa-lightbulb"');
        const deleteIndex = html.indexOf('class="mes_edit_delete menu_button fa-solid fa-trash-can"');
        const upIndex = html.indexOf('class="mes_edit_up menu_button fa-solid fa-chevron-up"');
        const downIndex = html.indexOf('class="mes_edit_down menu_button fa-solid fa-chevron-down"');
        const cancelIndex = html.indexOf('class="mes_edit_cancel menu_button fa-solid fa-xmark"');

        if (!(editButtonsIndex < doneIndex && doneIndex < copyIndex && copyIndex < reasoningIndex && reasoningIndex < deleteIndex && deleteIndex < upIndex && upIndex < downIndex && downIndex < cancelIndex)) {
          throw new Error('preview message edit controls should follow ST ordering');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_reasoning_controls():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'class="mes_reasoning_actions flex-container"',
          'class="mes_reasoning_edit_done menu_button edit_button fa-solid fa-check"',
          'class="mes_reasoning_delete menu_button edit_button fa-solid fa-trash-can"',
          'class="mes_reasoning_edit_cancel menu_button edit_button fa-solid fa-xmark"',
          'class="mes_reasoning_close_all mes_button fa-solid fa-minimize"',
          'class="mes_reasoning_copy mes_button fa-solid fa-copy"',
          'class="mes_reasoning_edit mes_button fa-solid fa-pencil"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const actionsIndex = html.indexOf('class="mes_reasoning_actions flex-container"');
        const doneIndex = html.indexOf('class="mes_reasoning_edit_done menu_button edit_button fa-solid fa-check"');
        const deleteIndex = html.indexOf('class="mes_reasoning_delete menu_button edit_button fa-solid fa-trash-can"');
        const cancelIndex = html.indexOf('class="mes_reasoning_edit_cancel menu_button edit_button fa-solid fa-xmark"');
        const closeAllIndex = html.indexOf('class="mes_reasoning_close_all mes_button fa-solid fa-minimize"');
        const copyIndex = html.indexOf('class="mes_reasoning_copy mes_button fa-solid fa-copy"');
        const editIndex = html.indexOf('class="mes_reasoning_edit mes_button fa-solid fa-pencil"');

        if (!(actionsIndex < doneIndex && doneIndex < deleteIndex && deleteIndex < cancelIndex && cancelIndex < closeAllIndex && closeAllIndex < copyIndex && copyIndex < editIndex)) {
          throw new Error('preview reasoning controls should follow ST ordering');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_extra_message_actions():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'class="extraMesButtons"',
          'class="mes_button mes_translate fa-solid fa-language"',
          'class="mes_button sd_message_gen fa-solid fa-paintbrush"',
          'class="mes_button mes_narrate fa-solid fa-bullhorn"',
          'class="mes_button mes_prompt fa-solid fa-square-poll-horizontal"',
          'class="mes_button mes_hide fa-solid fa-eye"',
          'class="mes_button mes_unhide fa-solid fa-eye-slash"',
          'class="mes_button mes_media_gallery fa-solid fa-photo-film"',
          'class="mes_button mes_media_list fa-solid fa-table-cells-large"',
          'class="mes_button mes_embed fa-solid fa-paperclip"',
          'class="mes_button mes_swipe_picker fa-solid fa-bookmark"',
          'class="mes_button mes_create_bookmark fa-regular fa-solid fa-flag-checkered"',
          'class="mes_button mes_create_branch fa-regular fa-code-branch"',
          'class="mes_button mes_copy fa-solid fa-copy"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }

        const extraIndex = html.indexOf('class="extraMesButtons"');
        const translateIndex = html.indexOf('class="mes_button mes_translate fa-solid fa-language"');
        const imageIndex = html.indexOf('class="mes_button sd_message_gen fa-solid fa-paintbrush"');
        const narrateIndex = html.indexOf('class="mes_button mes_narrate fa-solid fa-bullhorn"');
        const promptIndex = html.indexOf('class="mes_button mes_prompt fa-solid fa-square-poll-horizontal"');
        const hideIndex = html.indexOf('class="mes_button mes_hide fa-solid fa-eye"');
        const unhideIndex = html.indexOf('class="mes_button mes_unhide fa-solid fa-eye-slash"');
        const galleryIndex = html.indexOf('class="mes_button mes_media_gallery fa-solid fa-photo-film"');
        const listIndex = html.indexOf('class="mes_button mes_media_list fa-solid fa-table-cells-large"');
        const embedIndex = html.indexOf('class="mes_button mes_embed fa-solid fa-paperclip"');
        const swipeIndex = html.indexOf('class="mes_button mes_swipe_picker fa-solid fa-bookmark"');
        const bookmarkIndex = html.indexOf('class="mes_button mes_create_bookmark fa-regular fa-solid fa-flag-checkered"');
        const branchIndex = html.indexOf('class="mes_button mes_create_branch fa-regular fa-code-branch"');
        const copyIndex = html.indexOf('class="mes_button mes_copy fa-solid fa-copy"');

        if (!(extraIndex < translateIndex && translateIndex < imageIndex && imageIndex < narrateIndex && narrateIndex < promptIndex && promptIndex < hideIndex && hideIndex < unhideIndex && unhideIndex < galleryIndex && galleryIndex < listIndex && listIndex < embedIndex && embedIndex < swipeIndex && swipeIndex < bookmarkIndex && bookmarkIndex < branchIndex && branchIndex < copyIndex)) {
          throw new Error('preview extra message actions should follow ST ordering');
        }
        '''
    )


def test_build_beautify_preview_sample_markup_preserves_st_default_hidden_message_actions():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'class="mes_button mes_prompt fa-solid fa-square-poll-horizontal"',
          'title="Prompt" style="display: none;"',
          'class="mes_button mes_swipe_picker fa-solid fa-bookmark"',
          'title="Jump to swipe history" style="display: none;"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_sample_markup_contains_st_character_result_info_attributes():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewSampleMarkup('pc');

        for (const token of [
          'id="result_info" class="flex-container" style="display: none;"',
          'id="result_info_text" title="Token counts may be inaccurate and provided just for reference."',
          'data-i18n="[title]Token counts may be inaccurate and provided just for reference."',
          'id="result_info_total_tokens" title="Total tokens"',
          'data-i18n="[title]Total tokens"',
          '<span data-i18n="Calculating...">Calculating...</span>',
          '<small title="Permanent tokens" data-i18n="[title]Permanent tokens">',
          'id="chartokenwarning" class="right_menu_button fa-solid fa-triangle-exclamation" href="https://docs.sillytavern.app/usage/core-concepts/characterdesign/#character-tokens" target="_blank" title="About Token &#39;Limits&#39;"',
          'data-i18n="[title]About Token &#39;Limits&#39;"',
          'class="fa-solid fa-ranking-star right_menu_button rm_stats_button" title="Click for stats!"',
          'data-i18n="[title]Click for stats!"',
          'id="hideCharPanelAvatarButton" class="fa-solid fa-eye right_menu_button" title="Toggle character info panel"',
          'data-i18n="[title]Toggle character info panel"',
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_document_wires_panel_toggle_script_and_default_state():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({ platform: 'pc' });

        for (const token of [
          'data-active-panel="none"',
          'root.dataset.activePanel',
          'button.dataset.panelTarget',
          'aria-pressed',
          "panel.classList.toggle('openDrawer', isActive);",
          "panel.classList.toggle('closedDrawer', !isActive);",
          "shell.classList.toggle('openDrawer', isActive);",
          "drawer.classList.toggle('open', isActive);",
          "drawer.dispatchEvent(new CustomEvent('inline-drawer-toggle', { bubbles: true }));",
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_document_scrolls_chat_to_bottom_on_load():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({ platform: 'pc' });
        for (const token of [
          "const chat = document.querySelector('#chat');",
          'chat.scrollTop = chat.scrollHeight;',
          'window.requestAnimationFrame(scrollChatToBottom);',
          "window.addEventListener('load', scrollChatToBottom);",
        ]) {
          if (!html.includes(token)) throw new Error(`missing token: ${token}`);
        }
        '''
    )


def test_build_beautify_preview_document_does_not_leave_unmatched_topbar_panel_targets():
    run_preview_document_check(
        '''
        const html = module.buildBeautifyPreviewDocument({ platform: 'pc' });
        if (html.includes('data-panel-target="api"')) throw new Error('preview should not expose unmatched api panel target');
        if (html.includes('data-panel-shell="api"')) throw new Error('unexpected api panel shell');
        if (html.includes('data-panel-surface="api"')) throw new Error('unexpected api panel surface');
        '''
    )


def test_build_beautify_preview_document_hides_top_settings_holder_in_default_preview_state():
    source = (ROOT / 'static/js/components/beautifyPreviewDocument.js').read_text(encoding='utf-8')

    assert '#top-settings-holder {' in source
    top_settings_block = source.split('#top-settings-holder {', 1)[1].split('}', 1)[0]
    assert 'display: none;' in top_settings_block


def test_vendored_sillytavern_style_css_uses_local_down_arrow_asset():
    style_css = (ROOT / 'static/vendor/sillytavern/style.css').read_text(encoding='utf-8')

    assert "background-image: url('/img/down-arrow.svg');" not in style_css
    assert "background-image: url('../img/down-arrow.svg');" in style_css


def test_render_iframe_template_does_not_force_fixed_and_sticky_positions_to_absolute():
    source = (ROOT / 'static/js/runtime/renderIframeTemplate.js').read_text(encoding='utf-8')

    assert '[style*="position: fixed"]' not in source
    assert '[style*="position:fixed"]' not in source
    assert '[style*="position: sticky"]' not in source
    assert '[style*="position:sticky"]' not in source
    assert 'position: absolute !important;' not in source
