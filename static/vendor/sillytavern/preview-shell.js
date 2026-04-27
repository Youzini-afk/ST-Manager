// Vendor-derived preview shell assembled from static/vendor/sillytavern/index.html.
// Shell-defining DOM stays aligned with the vendored snapshot; preview code only
// hydrates chat content and the three supported drawer bodies.

export function buildVendorFirstPreviewShell({
  activeSceneId = 'daily',
  settingsDrawerContentMarkup = '',
  formattingDrawerContentMarkup = '',
  characterDrawerContentMarkup = '',
  chatMarkup = '',
  sendFormClassNames = 'no-connection',
} = {}) {
  const sendFormClassAttr = String(sendFormClassNames || '').trim();
  const sendFormClasses = sendFormClassAttr
    ? ` class="${sendFormClassAttr}"`
    : '';

  return `
    <!-- vendor-derived-shell: static/vendor/sillytavern/index.html -->
    <div class="st-preview-root" data-active-panel="none" data-active-scene="${activeSceneId}">
      <div id="bg1"></div>
      <div class="st-preview-shell">
        <div id="top-bar"></div>
        <div id="top-settings-holder">
          <div id="ai-config-button" class="drawer closedDrawer">
            <div class="drawer-toggle drawer-header" data-panel-target="settings">
              <div id="leftNavDrawerIcon" class="drawer-icon fa-solid fa-sliders fa-fw closedIcon" title="AI Response Configuration"></div>
            </div>
            <div id="left-nav-panel" class="drawer-content fillLeft closedDrawer" data-panel-surface="settings">
              <div id="left-nav-panelheader" class="fa-solid fa-grip drag-grabber"></div>
              <div id="lm_button_panel_pin_div" title="Locked = AI Configuration panel will stay open">
                <input type="checkbox" id="lm_button_panel_pin" />
                <label for="lm_button_panel_pin">
                  <div class="unchecked fa-solid fa-unlock right_menu_button"></div>
                  <div class="checked fa-solid fa-lock right_menu_button"></div>
                </label>
              </div>
              <div class="scrollableInner">${settingsDrawerContentMarkup}</div>
            </div>
          </div>

          <div id="sys-settings-button" class="drawer closedDrawer">
            <div class="drawer-toggle drawer-header">
              <div id="API-status-top" class="drawer-icon fa-solid fa-plug-circle-exclamation fa-fw closedIcon" title="API Connections" no_connection_text="No connection..."></div>
            </div>
            <div id="rm_api_block" class="drawer-content closedDrawer">
              <h3 class="margin0" id="title_api">API</h3>
            </div>
          </div>

          <div id="advanced-formatting-button" class="drawer closedDrawer">
            <div class="drawer-toggle" data-panel-target="formatting">
              <div class="drawer-icon fa-solid fa-font fa-fw closedIcon" title="AI Response Formatting"></div>
            </div>
            <div id="AdvancedFormatting" class="drawer-content closedDrawer" data-panel-surface="formatting">
              <div class="scrollableInner">${formattingDrawerContentMarkup}</div>
            </div>
          </div>

          <div id="WI-SP-button" class="drawer closedDrawer">
            <div class="drawer-toggle drawer-header">
              <div id="WIDrawerIcon" class="drawer-icon fa-solid fa-book-atlas fa-fw closedIcon" title="World Info"></div>
            </div>
            <div id="WorldInfo" class="drawer-content closedDrawer">
              <h3 class="margin0">World Info</h3>
            </div>
          </div>

          <div id="user-settings-button" class="drawer closedDrawer">
            <div class="drawer-toggle">
              <div class="drawer-icon fa-solid fa-user-cog fa-fw closedIcon" title="User Settings"></div>
            </div>
            <div id="user-settings-block" class="drawer-content closedDrawer">
              <h3 class="margin0">User Settings</h3>
            </div>
          </div>

          <div id="backgrounds-button" class="drawer closedDrawer">
            <div id="backgrounds-drawer-toggle" class="drawer-toggle drawer-header" title="Change Background Image">
              <div class="drawer-icon fa-solid fa-panorama fa-fw closedIcon"></div>
            </div>
            <div id="Backgrounds" class="drawer-content closedDrawer"></div>
          </div>

          <div id="extensions-settings-button" class="drawer closedDrawer">
            <div class="drawer-toggle">
              <div class="drawer-icon fa-solid fa-cubes fa-fw closedIcon" title="Extensions"></div>
            </div>
            <div id="rm_extensions_block" class="drawer-content closedDrawer">
              <h3 class="margin0">Extensions</h3>
            </div>
          </div>

          <div id="persona-management-button" class="drawer closedDrawer">
            <div class="drawer-toggle">
              <div class="drawer-icon fa-solid fa-face-smile fa-fw closedIcon" title="Persona Management"></div>
            </div>
            <div id="PersonaManagement" class="drawer-content closedDrawer">
              <h3 class="margin0">Persona Management</h3>
            </div>
          </div>

          <div id="rightNavHolder" class="drawer closedDrawer">
            <div id="unimportantYes" class="drawer-toggle drawer-header" data-panel-target="character">
              <div id="rightNavDrawerIcon" class="drawer-icon fa-solid fa-address-card fa-fw closedIcon" title="Character Management"></div>
            </div>
            <nav id="right-nav-panel" class="drawer-content closedDrawer fillRight" data-panel-surface="character">
              <div id="right-nav-panelheader" class="fa-solid fa-grip drag-grabber"></div>
              <div id="CharListButtonAndHotSwaps" class="flex-container flexnowrap">
                <div class="flexFlowColumn flex-container">
                  <div id="rm_button_panel_pin_div" class="alignitemsflexstart" title="Locked = Character Management panel will stay open">
                    <input type="checkbox" id="rm_button_panel_pin" />
                    <label for="rm_button_panel_pin">
                      <div class="fa-solid unchecked fa-unlock right_menu_button"></div>
                      <div class="fa-solid checked fa-lock right_menu_button"></div>
                    </label>
                  </div>
                </div>
              </div>
              <div class="scrollableInner">${characterDrawerContentMarkup}</div>
            </nav>
          </div>
        </div>

        <div id="sheld">
          <div id="sheldheader" class="fa-solid fa-grip drag-grabber"></div>
          <div id="chat">${chatMarkup}</div>
          <div id="form_sheld">
            <div id="dialogue_del_mes">
              <div id="dialogue_del_mes_ok" class="menu_button">Delete</div>
              <div id="dialogue_del_mes_cancel" class="menu_button">Cancel</div>
            </div>
            <div id="send_form"${sendFormClasses}>
              <form id="file_form" class="wide100p displayNone">
                <div class="file_attached">
                  <input id="file_form_input" type="file" multiple hidden />
                  <input id="embed_file_input" type="file" multiple hidden />
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
                  <div id="options_button" class="fa-solid fa-bars interactable"></div>
                  <div id="extensionsMenuButton" class="fa-solid fa-magic-wand-sparkles interactable" title="Extensions"></div>
                </div>
                <textarea id="send_textarea" name="text" class="mdHotkeys" placeholder="Not connected to API!" no_connection_text="Not connected to API!" connected_text="Type a message, or /? for help" autocomplete="off"></textarea>
                <div id="rightSendForm" class="alignContentCenter">
                  <div id="stscript_continue" title="Continue script execution" class="stscript_btn stscript_continue"><i class="fa-solid fa-play"></i></div>
                  <div id="stscript_pause" title="Pause script execution" class="stscript_btn stscript_pause"><i class="fa-solid fa-pause"></i></div>
                  <div id="stscript_stop" title="Abort script execution" class="stscript_btn stscript_stop"><i class="fa-solid fa-stop"></i></div>
                  <div id="mes_stop" title="Abort request" class="mes_stop"><i class="fa-solid fa-circle-stop"></i></div>
                  <div id="mes_impersonate" class="fa-solid fa-user-secret interactable displayNone" title="Ask AI to write your message for you" tabindex="0"></div>
                  <div id="mes_continue" class="fa-fw fa-solid fa-arrow-right interactable displayNone" title="Continue the last message"></div>
                  <div id="send_but" class="fa-solid fa-paper-plane interactable" title="Send a message"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}
