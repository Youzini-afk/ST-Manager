# SillyTavern Vendor Source

- Upstream project: SillyTavern
- Upstream local source used for sync: `D:\Workspace\SillyTavern`
- License: AGPL-3.0
- Purpose: beautify native ST preview only

## Copied Paths

- `LICENSE`
- `public/style.css`
- `public/css/animations.css`
- `public/css/popup.css`
- `public/css/popup-safari-fix.css`
- `public/css/promptmanager.css`
- `public/css/loader.css`
- `public/css/character-group-overlay.css`
- `public/css/file-form.css`
- `public/css/logprobs.css`
- `public/css/accounts.css`
- `public/css/tags.css`
- `public/css/scrollable-button.css`
- `public/css/welcome.css`
- `public/css/data-maid.css`
- `public/css/secrets.css`
- `public/css/backgrounds.css`
- `public/css/chat-backups.css`
- `public/css/mobile-styles.css`
- `public/lib/dialog-polyfill.css`
- `public/favicon.ico`
- `public/img/down-arrow.svg`
- `public/img/times-circle.svg`

## Local Notes

- Files in this directory are vendored upstream assets unless explicitly marked otherwise.
- Project-authored preview glue should live outside copied upstream files whenever possible.
- The baseline includes `style.css` top-level imports plus directly referenced nested CSS and image assets needed for a self-contained preview runtime.
