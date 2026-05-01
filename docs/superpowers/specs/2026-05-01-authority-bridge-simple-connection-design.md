# Authority Bridge Simple Connection Design

Date: 2026-05-01

## Context

ST-Manager's remote backup bridge currently talks to Authority through `/api/plugins/authority/st-manager/*`, but the ST-Manager client still reuses the normal SillyTavern HTTP auth stack. That makes users configure ST URL plus Basic/Auth, Web Login, or Basic + Web Login before they can use a bridge that already has its own Bridge Key.

For Zeabur/server deployments, this is too much friction. The preferred user flow should be:

```text
Authority/ST URL + Bridge Key
```

The key detail is on the Authority side: current bridge routes call `getUserContext(req)` before entering `StManagerBridgeService`, so they still require a SillyTavern login session. Key-only mode must let the Bridge Key resolve a bound ST user directory without requiring ST-Manager to perform ST login.

## Goals

- Add a first-class ST-Manager remote connection mode named `Authority Bridge`.
- In `Authority Bridge` mode, ST-Manager only requires:
  - Authority/ST service URL
  - Bridge Key
  - optional proxy
  - resource type switches
- Keep the existing ST auth mode as a compatibility/advanced option.
- Let Authority bridge routes serve key-only requests by resolving a user snapshot bound when the key was generated.
- Preserve all existing Bridge Key protections, resource type switches, path safety checks, chunking, sha256 validation, and atomic restore semantics.

## Non-Goals

- Do not remove ST Basic/Web login support.
- Do not make the Bridge Key auto-create itself remotely; generation remains an admin action inside Authority/SillyTavern.
- Do not expose raw key material after generation.
- Do not change resource manifest/file transfer payload formats.
- Do not back up Authority app data in this pass.

## User Experience

ST-Manager remote backup config gets a connection mode selector:

- `Authority Bridge (recommended)`
- `SillyTavern API login (advanced)`

When `Authority Bridge` is selected, the visible fields are:

- `Authority/ST URL`
- `Bridge Key`
- `Proxy` (optional)
- enabled resource types
- chunk size/advanced transfer settings if already exposed

When `SillyTavern API login` is selected, the existing ST URL + Basic/Web fields remain available.

Probe copy should explain that `Authority/ST URL` is the SillyTavern root URL where Authority is installed. ST-Manager will append:

```text
/api/plugins/authority/st-manager
```

## Authority Design

### Bridge State

Extend `StManagerBridgeState` with a bound user snapshot:

```ts
bound_user?: {
  handle: string;
  isAdmin: boolean;
  rootDir: string;
  directories: RequestUser['directories'];
};
```

When an admin calls `/st-manager/bridge/admin/config` to enable or rotate the key, Authority stores the current admin user's handle and directory map into `bound_user`. This snapshot is enough for the resource locator to resolve characters, chats, worlds, presets, Regex, QuickReplies, and settings paths without a live ST login session.

### Key-Only Route Resolution

For non-admin bridge routes:

- If `req.user` exists, keep current behavior.
- If `req.user` is absent, extract and validate the Bridge Key.
- If the key is valid and `bound_user` exists, use that bound user snapshot.
- If the key is valid but no `bound_user` exists, return a clear 401/403 telling the user to rotate/regenerate the key in Authority.
- If the key is missing/invalid, return the existing unauthorized error.

Admin config remains login/admin-only.

Affected routes:

- `GET /st-manager/bridge/probe`
- `GET /st-manager/resources/:type/manifest`
- `POST /st-manager/resources/:type/file/read`
- `POST /st-manager/resources/:type/file/write-init`
- `POST /st-manager/resources/:type/file/write-chunk`
- `POST /st-manager/resources/:type/file/write-commit`

### Security

- Bridge disabled still rejects all key-only access.
- Key hash comparison remains server-side only.
- `bound_user` should never include the raw Bridge Key.
- `getPublicConfig` can return non-secret binding info:
  - `bound_user_handle`
  - `key_fingerprint`
  - `key_masked`
- Directory values should not be exposed in public config beyond existing probe behavior.
- Rotating the key refreshes the bound user snapshot to the currently logged-in admin user.

## ST-Manager Design

### Config Model

Remote backup config adds:

```json
{
  "remote_connection_mode": "authority_bridge"
}
```

Supported values:

- `authority_bridge`
- `st_auth`

Default for new configs: `authority_bridge`.

Existing configs without this field keep working. If a saved config has Basic/Web credentials, ST-Manager may infer `st_auth` for compatibility in the UI, but the service layer should tolerate either mode explicitly.

### HTTP Client

`RemoteSTBridgeClient` chooses transport based on `remote_connection_mode`:

- `authority_bridge`: use a lightweight requests-based client with base URL, optional proxy, timeout, and Bridge Key headers. It must not call ST Basic/Web login endpoints and must not require CSRF cookies.
- `st_auth`: keep using existing `STHTTPClient` behavior.

Both transports expose the same minimal methods used by `RemoteSTBridgeClient`:

- `get(path, headers, timeout)`
- `post(path, json, headers, timeout)`

Bridge Key headers stay unchanged:

```http
Authorization: Bearer <key>
X-ST-Manager-Key: <key>
```

### API and UI

`/api/remote_backups/config` accepts and returns public config with `remote_connection_mode`.

The UI should:

- Default new remote backup setup to `Authority Bridge`.
- Hide ST auth username/password fields when mode is `authority_bridge`.
- Keep Bridge Key masked after save.
- Label the old path as `SillyTavern API login (advanced)`.
- Show probe errors in mode-aware language.

## Data Flow

1. User enables bridge in Authority while logged in as an admin.
2. Authority stores key hash/fingerprint and `bound_user`.
3. User copies the one-time Bridge Key into ST-Manager.
4. ST-Manager saves `remote_connection_mode=authority_bridge`, `st_url`, and masked private key.
5. Probe uses URL + Bridge Key only.
6. Authority validates key and uses `bound_user` to enumerate/read/write resources.
7. Backup and restore continue to use manifest-relative paths and chunked transfer.

## Error Handling

- Missing Bridge Key: ST-Manager blocks probe/start with a clear local validation error.
- Invalid Bridge Key: Authority returns 401; ST-Manager reports "Bridge Key invalid".
- Bridge disabled: Authority returns 403; ST-Manager reports "Bridge disabled in Authority".
- No bound user: Authority returns clear error; ST-Manager tells user to rotate/regenerate the key while logged in.
- URL points at ST without updated Authority: probe returns 404/unsupported; ST-Manager reports that key-only mode requires an updated Authority plugin.
- Optional proxy failures should still be reported as connection errors.

## Compatibility

- Old remote backup configs continue to work in `st_auth` mode.
- Existing Authority bridge state without `bound_user` still works for logged-in ST requests.
- Existing generated keys can be used after an admin saves/rotates config once to bind a user snapshot.
- Resource manifests and backup snapshot formats do not change.

## Test Plan

Authority tests:

- Admin config stores `bound_user` when enabling/rotating key.
- Public config returns bound handle but no key hash/raw key/directories.
- Key-only probe succeeds with valid key and bound user.
- Key-only manifest/read/write/commit succeed with valid key and bound user.
- Key-only requests fail when bridge disabled, key invalid, or bound user missing.
- Logged-in route behavior still works.
- Resource locator keeps path traversal/symlink protections.

ST-Manager tests:

- Config save/load supports `remote_connection_mode` and still masks Bridge Key.
- New config defaults to `authority_bridge`.
- `RemoteSTBridgeClient` in `authority_bridge` mode sends Bridge Key headers and does not instantiate/call `STHTTPClient`.
- `RemoteSTBridgeClient` in `st_auth` mode still uses `STHTTPClient`.
- Probe/start/backup/restore continue to pass with both modes.
- UI contract hides ST auth fields for Authority mode and keeps advanced ST login fields for `st_auth`.
- Error formatting distinguishes invalid key, disabled bridge, and unsupported old Authority.
