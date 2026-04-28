import {
    CHARACTER_DRAWER_VENDOR_MARKUP,
    FORMATTING_DRAWER_VENDOR_MARKUP,
    SETTINGS_DRAWER_VENDOR_MARKUP,
} from '../../vendor/sillytavern/preview-drawers.js';


function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


function replaceTextareaValue(markup, id, value) {
    const escapedValue = escapeHtml(value);
    const pattern = new RegExp(`(<textarea[^>]*id="${id}"[^>]*>)([\\s\\S]*?)(</textarea>)`);
    return markup.replace(pattern, `$1${escapedValue}$3`);
}


function addAttributesToOpeningTag(markup, selector, attributes) {
    const pattern = new RegExp(`(<[^>]*${selector}[^>]*)(>)`);
    return markup.replace(pattern, (_, openingTagStart, tagEnd) => {
        for (const [name, value] of Object.entries(attributes)) {
            const attributePattern = new RegExp(`\\s${name}="[^"]*"`);
            if (attributePattern.test(openingTagStart)) {
                openingTagStart = openingTagStart.replace(attributePattern, ` ${name}="${escapeHtml(value)}"`);
                continue;
            }

            const classMatch = openingTagStart.match(/ class="[^"]*"/);
            if (classMatch) {
                openingTagStart = openingTagStart.replace(classMatch[0], `${classMatch[0]} ${name}="${escapeHtml(value)}"`);
                continue;
            }

            openingTagStart += ` ${name}="${escapeHtml(value)}"`;
        }

        return `${openingTagStart}${tagEnd}`;
    });
}


function replaceBetween(markup, startToken, endToken, content) {
    const startIndex = markup.indexOf(startToken);
    if (startIndex === -1) {
        return markup;
    }

    const contentStartIndex = startIndex + startToken.length;
    const endIndex = markup.indexOf(endToken, contentStartIndex);
    if (endIndex === -1) {
        return markup;
    }

    return `${markup.slice(0, contentStartIndex)}${content}${markup.slice(endIndex)}`;
}


export function buildSettingsDrawerPreviewMarkupFromVendor({ theme = {}, vendorMarkup = SETTINGS_DRAWER_VENDOR_MARKUP } = {}) {
    void theme;

    let markup = vendorMarkup;

    markup = addAttributesToOpeningTag(markup, 'id="ai_module_block_novel"', { style: 'display: none;' });
    markup = addAttributesToOpeningTag(markup, 'id="prompt_cost_block"', { style: 'display: none;' });

    for (const selector of [
        'data-preset-manager-import="kobold"',
        'data-preset-manager-export="kobold"',
        'data-preset-manager-delete="kobold"',
        'data-preset-manager-update="kobold"',
        'data-preset-manager-rename="kobold"',
        'data-preset-manager-new="kobold"',
        'data-preset-manager-restore="kobold"',
    ]) {
        markup = addAttributesToOpeningTag(markup, selector, { 'data-preview-disabled': 'true' });
    }

    return markup;
}


export function buildFormattingDrawerPreviewMarkupFromVendor({
    scenePromptContent = '',
    vendorMarkup = FORMATTING_DRAWER_VENDOR_MARKUP,
} = {}) {
    let markup = vendorMarkup;

    markup = replaceTextareaValue(markup, 'context_story_string', scenePromptContent);
    markup = addAttributesToOpeningTag(markup, 'id="af_master_import"', { 'data-preview-disabled': 'true' });
    markup = addAttributesToOpeningTag(markup, 'id="af_master_export"', { 'data-preview-disabled': 'true' });

    return markup;
}


export function buildCharacterDrawerPreviewMarkupFromVendor({
    identities = {},
    detail = {},
    vendorMarkup = CHARACTER_DRAWER_VENDOR_MARKUP,
} = {}) {
    const avatarSrc = identities.character?.avatarSrc || '';
    const packageName = detail.packageName || '';
    const name = identities.character?.name || packageName || 'Preview Character';
    const description = detail.description || '';

    let markup = vendorMarkup;

    const cardMarkup = `
                            <div class="flex-container wide100pLess70px character_select_container">
                                <div class="character_select" chid="preview-character" data-preview-character="primary">
                                    <div class="avatar"><img src="${escapeHtml(avatarSrc)}" alt="${escapeHtml(name)}"></div>
                                    <div class="character_name_block">
                                        <span class="ch_name">${escapeHtml(name)}</span>
                                        <span class="character_version">${escapeHtml(packageName)}</span>
                                        <span class="ch_description">${escapeHtml(description)}</span>
                                    </div>
                                </div>
                            </div>`;
    markup = replaceBetween(markup, '<div id="rm_print_characters_block" class="flexFlowColumn">', '</div>', cardMarkup);

    markup = addAttributesToOpeningTag(markup, 'id="rm_button_search"', { 'data-preview-action': 'toggle-search' });
    markup = addAttributesToOpeningTag(markup, 'id="charListGridToggle"', { 'data-preview-action': 'toggle-grid' });

    for (const selector of [
        'id="rm_button_create"',
        'id="character_import_button"',
        'id="external_import_button"',
        'id="rm_button_group_chats"',
        'id="create_button_label"',
        'id="export_button"',
        'id="delete_button"',
        'id="bulkEditButton"',
        'id="bulkSelectAllButton"',
        'id="bulkDeleteButton"',
    ]) {
        markup = addAttributesToOpeningTag(markup, selector, { 'data-preview-disabled': 'true' });
    }

    markup = addAttributesToOpeningTag(markup, 'id="rm_ch_create_block"', { style: 'display: none;' });
    markup = addAttributesToOpeningTag(markup, 'id="rm_group_chats_block"', { style: 'display: none;' });
    markup = addAttributesToOpeningTag(markup, 'id="rm_character_import"', { style: 'display: none;' });
    markup = addAttributesToOpeningTag(markup, 'id="rm_characters_block"', { style: 'display: block;' });

    return markup;
}
