# Authority Bridge Simple Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let ST-Manager remote backups connect to Authority with only an Authority/ST URL and Bridge Key, while preserving the older SillyTavern API login mode.

**Architecture:** Authority stores a bound user snapshot when an admin enables or rotates the ST-Manager bridge key, then non-admin bridge routes can resolve that bound user from a valid Bridge Key even when `req.user` is absent. ST-Manager adds `remote_connection_mode`, defaults to `authority_bridge`, and uses a lightweight requests transport in that mode instead of the SillyTavern Basic/Web login client.

**Tech Stack:** TypeScript/Vitest in `ST-Delegation-of-authority`; Python/Flask/pytest in `ST-Manager`.

---

## File Structure

Authority project (`E:\cursor_project\ST-Delegation of authority\ST-Delegation-of-authority`):

- Modify `packages/server-plugin/src/services/st-manager-bridge-service.ts`: add bound user snapshot state, public binding metadata, key-only user resolution helpers.
- Modify `packages/server-plugin/src/routes.ts`: use a key-aware bridge user resolver for non-admin `/st-manager/*` routes.
- Modify `packages/server-plugin/src/services/st-manager-bridge-service.test.ts`: service-level tests for binding and key-only user resolution.
- Modify `packages/server-plugin/src/routes.test.ts`: route-level test that a key-only probe works without `req.user`.

ST-Manager project (`E:\cursor_project\ST-Delegation of authority\ST-Manager`):

- Modify `core/services/remote_st_bridge_client.py`: add lightweight Authority Bridge transport and mode selection.
- Modify `core/services/remote_backup_service.py`: save/publicize `remote_connection_mode`, default to `authority_bridge`, and validate missing bridge key.
- Modify `tests/test_remote_st_bridge_client.py`: transport mode tests.
- Modify `tests/test_remote_backups_api.py`: config/API tests for the new mode.
- Modify `tests/test_remote_backup_service.py`: backup service validation/compatibility tests.
- Modify `static/js/state.js`, `templates/modals/settings.html`: UI state and simplified Authority Bridge mode controls if remote backup config is surfaced there.
- Add/modify a frontend contract test if a visible UI branch changes.

---

### Task 1: Authority Bridge Bound User State

**Files:**
- Modify: `packages/server-plugin/src/services/st-manager-bridge-service.ts`
- Modify: `packages/server-plugin/src/services/st-manager-bridge-service.test.ts`

- [ ] **Step 1: Write failing service tests**

Add tests that expect `updateAdminConfig()` to bind the admin user, expose only `bound_user_handle`, and resolve a key-only user:

```ts
it('binds the current admin user when enabling or rotating the bridge key', () => {
    const updated = service.updateAdminConfig(user(), { enabled: true, rotate_key: true });

    expect(updated.bridge_key).toMatch(/^stmb_/);
    expect(updated.bound_user_handle).toBe('alice');
    expect(JSON.stringify(updated)).not.toContain(userRoot);
    expect(JSON.stringify(updated)).not.toContain('key_hash');

    const resolved = service.resolveAuthorizedUser(undefined, {
        authorization: `Bearer ${updated.bridge_key}`,
    });

    expect(resolved.handle).toBe('alice');
    expect(resolved.rootDir).toBe(userRoot);
});
```

Add a failure case for valid key without `bound_user`:

```ts
it('requires a bound user for key-only bridge access', () => {
    const updated = service.updateAdminConfig(user(), { enabled: true, rotate_key: true });
    fs.writeFileSync(path.join(tempDir, 'bridge-state.json'), JSON.stringify({
        enabled: true,
        key_hash: crypto.createHash('sha256').update(updated.bridge_key).digest('hex'),
        key_fingerprint: 'legacy',
    }));

    expect(() => service.resolveAuthorizedUser(undefined, {
        authorization: `Bearer ${updated.bridge_key}`,
    })).toThrow(/Bridge key is not bound/);
});
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
npx vitest run packages/server-plugin/src/services/st-manager-bridge-service.test.ts
```

Expected: FAIL because `bound_user_handle` and `resolveAuthorizedUser` do not exist.

- [ ] **Step 3: Implement minimal service changes**

In `StManagerBridgeState`, add:

```ts
bound_user?: UserContext;
```

In `updateAdminConfig()`, when enabling, rotating, or generating the first key, store:

```ts
next.bound_user = {
    handle: user.handle,
    isAdmin: user.isAdmin,
    rootDir: user.rootDir,
    directories: user.directories,
};
```

In `getPublicConfig()`, add:

```ts
bound_user_handle: state.bound_user?.handle || null,
```

Export or add a public method:

```ts
resolveAuthorizedUser(user: UserContext | undefined, headers: Record<string, string | string[] | undefined>): UserContext {
    if (user) {
        this.assertAuthorized(headers);
        return user;
    }
    this.assertAuthorized(headers);
    const boundUser = this.readState().bound_user;
    if (!boundUser) {
        throw new AuthorityServiceError('Bridge key is not bound to a user; rotate the key in Authority.', 403, 'unauthorized', 'auth');
    }
    return boundUser;
}
```

- [ ] **Step 4: Run service tests**

Run:

```bash
npx vitest run packages/server-plugin/src/services/st-manager-bridge-service.test.ts
```

Expected: PASS.

---

### Task 2: Authority Key-Only Routes

**Files:**
- Modify: `packages/server-plugin/src/routes.ts`
- Modify: `packages/server-plugin/src/routes.test.ts`

- [ ] **Step 1: Write failing route test**

Add a route test that registers `/st-manager/bridge/probe`, calls it with only headers and no `user`, and expects `stManagerBridge.probe()` to receive the bound user returned by `resolveAuthorizedUser()`:

```ts
it('allows ST-Manager bridge probe with Bridge Key only', async () => {
    const gets = new Map<string, (req: any, res: any) => void | Promise<void>>();
    const router = {
        get(path: string, handler: (req: any, res: any) => void | Promise<void>) {
            gets.set(path, handler);
        },
        post() {
            return undefined;
        },
    };

    const boundUser = {
        handle: 'alice',
        isAdmin: true,
        rootDir: 'C:/users/alice',
        directories: { root: 'C:/users/alice' },
    };
    const runtime = {
        stManagerBridge: {
            resolveAuthorizedUser: vi.fn(() => boundUser),
            probe: vi.fn(() => ({ success: true, user: { handle: 'alice', root: 'C:/users/alice' } })),
        },
        audit: {
            logError: vi.fn().mockResolvedValue(undefined),
        },
    } as unknown as AuthorityRuntime;

    registerRoutes(router, runtime);
    const response = {
        status: vi.fn().mockReturnThis(),
        json: vi.fn(),
        send: vi.fn(),
        setHeader: vi.fn(),
        write: vi.fn(),
        end: vi.fn(),
    };

    await gets.get('/st-manager/bridge/probe')?.({
        headers: { authorization: 'Bearer stmb_key' },
    }, response);

    expect(runtime.stManagerBridge.resolveAuthorizedUser).toHaveBeenCalledWith(undefined, { authorization: 'Bearer stmb_key' });
    expect(runtime.stManagerBridge.probe).toHaveBeenCalledWith(boundUser, { authorization: 'Bearer stmb_key' });
    expect(response.json).toHaveBeenCalledWith(expect.objectContaining({ success: true }));
});
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
npx vitest run packages/server-plugin/src/routes.test.ts
```

Expected: FAIL because the route calls `getUserContext(req)` and throws without `req.user`.

- [ ] **Step 3: Implement key-aware user resolver in routes**

Add helper in `routes.ts`:

```ts
function getOptionalUserContext(req: Parameters<typeof getUserContext>[0]): ReturnType<typeof getUserContext> | undefined {
    return req.user ? getUserContext(req) : undefined;
}

function getStManagerBridgeUser(runtime: AuthorityRuntime, req: Parameters<typeof getUserContext>[0]) {
    return runtime.stManagerBridge.resolveAuthorizedUser(getOptionalUserContext(req), req.headers);
}
```

Use `getStManagerBridgeUser(runtime, req)` for all non-admin `/st-manager/*` routes. Keep `/st-manager/bridge/admin/config` using `getUserContext(req)`.

- [ ] **Step 4: Run Authority targeted tests**

Run:

```bash
npx vitest run packages/server-plugin/src/services/st-manager-bridge-service.test.ts packages/server-plugin/src/routes.test.ts
```

Expected: PASS.

---

### Task 3: ST-Manager Config Mode

**Files:**
- Modify: `core/services/remote_backup_service.py`
- Modify: `tests/test_remote_backups_api.py`

- [ ] **Step 1: Write failing config tests**

Add tests:

```python
def test_config_defaults_to_authority_bridge_mode(tmp_path):
    store = RemoteBackupConfigStore(base_dir=tmp_path / 'remote_backups')

    public = store.public()

    assert public['remote_connection_mode'] == 'authority_bridge'


def test_config_endpoint_persists_connection_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(
        remote_backups_api,
        'RemoteBackupConfigStore',
        lambda: RemoteBackupConfigStore(base_dir=tmp_path / 'remote_backups'),
    )

    response = _make_test_app().test_client().post(
        '/api/remote_backups/config',
        json={
            'st_url': 'https://st.example',
            'remote_connection_mode': 'st_auth',
            'remote_bridge_key': 'secret',
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['config']['remote_connection_mode'] == 'st_auth'
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
pytest tests/test_remote_backups_api.py -q
```

Expected: FAIL because `remote_connection_mode` is not present.

- [ ] **Step 3: Implement config persistence**

In `RemoteBackupConfigStore.save()`, include `remote_connection_mode` in the copied keys. Add helper:

```python
VALID_REMOTE_CONNECTION_MODES = {'authority_bridge', 'st_auth'}

def normalize_remote_connection_mode(value):
    return value if value in VALID_REMOTE_CONNECTION_MODES else 'authority_bridge'
```

In `public()`, include:

```python
config['remote_connection_mode'] = normalize_remote_connection_mode(config.get('remote_connection_mode'))
```

In `load_private()` or service merge path, tolerate missing mode by defaulting to `authority_bridge`.

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_remote_backups_api.py -q
```

Expected: PASS.

---

### Task 4: ST-Manager Authority Bridge Transport

**Files:**
- Modify: `core/services/remote_st_bridge_client.py`
- Modify: `tests/test_remote_st_bridge_client.py`

- [ ] **Step 1: Write failing transport tests**

Add tests:

```python
def test_authority_bridge_mode_uses_simple_http_client(monkeypatch):
    created = []

    class FakeSimpleHTTP:
        def __init__(self, config, timeout=60):
            created.append((config, timeout))
        def get(self, path, **kwargs):
            return FakeResponse({'ok': True})

    monkeypatch.setattr('core.services.remote_st_bridge_client.SimpleBridgeHTTPClient', FakeSimpleHTTP)
    monkeypatch.setattr(
        'core.services.remote_st_bridge_client.build_st_http_client',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('STHTTPClient should not be used')),
    )

    client = RemoteSTBridgeClient({
        'st_url': 'https://st.example',
        'remote_connection_mode': 'authority_bridge',
    }, bridge_key='secret')

    assert created
    assert client.probe() == {'ok': True}


def test_st_auth_mode_keeps_existing_st_http_client(monkeypatch):
    fake_http = FakeHTTPClient([])
    monkeypatch.setattr(
        'core.services.remote_st_bridge_client.build_st_http_client',
        lambda config, st_url=None, timeout=60: fake_http,
    )

    client = RemoteSTBridgeClient({
        'st_url': 'https://st.example',
        'remote_connection_mode': 'st_auth',
    }, bridge_key='secret')

    assert client.probe() == {'files': []}
    assert fake_http.calls[0][0] == 'get'
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
pytest tests/test_remote_st_bridge_client.py -q
```

Expected: FAIL because `SimpleBridgeHTTPClient` and mode selection do not exist.

- [ ] **Step 3: Implement lightweight transport**

Add to `remote_st_bridge_client.py`:

```python
import requests
from urllib.parse import urljoin

class SimpleBridgeHTTPClient:
    def __init__(self, config=None, timeout=60):
        self.config = config or load_config()
        self.base_url = (self.config.get('st_url') or 'http://127.0.0.1:8000').rstrip('/')
        self.timeout = timeout
        proxy = (self.config.get('st_proxy', '') or '').strip()
        self.proxies = {'http': proxy or None, 'https': proxy or None}
        self.session = requests.Session()

    def _resolve_url(self, path):
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return urljoin(f'{self.base_url}/', path.lstrip('/'))

    def get(self, path, timeout=None, **kwargs):
        kwargs.setdefault('proxies', self.proxies)
        kwargs.setdefault('timeout', timeout or self.timeout)
        return self.session.get(self._resolve_url(path), **kwargs)

    def post(self, path, json=None, timeout=None, **kwargs):
        kwargs.setdefault('proxies', self.proxies)
        kwargs.setdefault('timeout', timeout or self.timeout)
        return self.session.post(self._resolve_url(path), json=json, **kwargs)
```

In `RemoteSTBridgeClient.__init__`, choose:

```python
mode = self.config.get('remote_connection_mode') or 'authority_bridge'
if http_client:
    self.http_client = http_client
elif mode == 'st_auth':
    self.http_client = build_st_http_client(...)
else:
    self.http_client = SimpleBridgeHTTPClient(self.config, timeout=timeout)
```

- [ ] **Step 4: Run bridge client tests**

Run:

```bash
pytest tests/test_remote_st_bridge_client.py -q
```

Expected: PASS.

---

### Task 5: ST-Manager Backup Validation and UI Contracts

**Files:**
- Modify: `core/services/remote_backup_service.py`
- Modify: `tests/test_remote_backup_service.py`
- Modify: `static/js/state.js`
- Modify: `templates/modals/settings.html`
- Add or modify: `tests/test_server_deploy_frontend_contracts.py` or `tests/test_settings_frontend_contracts.py`

- [ ] **Step 1: Write failing service validation test**

Add:

```python
def test_authority_bridge_mode_requires_bridge_key(tmp_path):
    service = RemoteBackupService(
        base_dir=tmp_path / 'system' / 'remote_backups',
        config={**_config(tmp_path), 'remote_connection_mode': 'authority_bridge', 'remote_bridge_key': ''},
    )

    with pytest.raises(RemoteBackupError, match='Bridge Key is required'):
        service.probe()
```

- [ ] **Step 2: Write frontend contract test if settings UI is changed**

Assert the template includes `Authority Bridge` mode and hides Basic/Web fields with `remote_connection_mode`:

```python
def test_settings_template_has_authority_bridge_mode():
    source = (ROOT / 'templates' / 'modals' / 'settings.html').read_text(encoding='utf-8')
    state = (ROOT / 'static' / 'js' / 'state.js').read_text(encoding='utf-8')

    assert 'Authority Bridge' in source
    assert 'remote_connection_mode' in source
    assert "settingsForm.remote_connection_mode === 'st_auth'" in source
    assert 'remote_connection_mode: "authority_bridge"' in state
```

- [ ] **Step 3: Run and verify RED**

Run:

```bash
pytest tests/test_remote_backup_service.py tests/test_settings_frontend_contracts.py -q
```

Expected: FAIL until service validation and UI contract are implemented.

- [ ] **Step 4: Implement validation**

In `RemoteBackupService._client()`, before constructing the client:

```python
mode = normalize_remote_connection_mode(self.config.get('remote_connection_mode'))
bridge_key = self.config.get('remote_bridge_key') or self.config.get('bridge_key') or ''
if mode == 'authority_bridge' and not bridge_key:
    raise RemoteBackupError('Bridge Key is required for Authority Bridge mode')
```

- [ ] **Step 5: Implement UI branch**

In `static/js/state.js`, add default:

```js
remote_connection_mode: "authority_bridge",
remote_bridge_key: "",
```

In `templates/modals/settings.html`, add radio controls near the SillyTavern API connection block. Wrap old Basic/Web auth block with:

```html
x-show="settingsForm.remote_connection_mode === 'st_auth'"
```

Show the bridge key field when:

```html
x-show="settingsForm.remote_connection_mode === 'authority_bridge'"
```

If the remote backup UI is not currently visible in settings, implement the contract only for existing config state and API; do not invent a large new screen in this task.

- [ ] **Step 6: Run service/UI tests**

Run:

```bash
pytest tests/test_remote_backup_service.py tests/test_settings_frontend_contracts.py -q
```

Expected: PASS.

---

### Task 6: Cross-Project Verification and Commits

**Files:** all changed files in both repositories.

- [ ] **Step 1: Run Authority targeted verification**

Run in `ST-Delegation-of-authority`:

```bash
npx vitest run packages/server-plugin/src/services/st-manager-bridge-service.test.ts packages/server-plugin/src/routes.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 2: Run ST-Manager targeted verification**

Run in `ST-Manager`:

```bash
pytest tests/test_remote_st_bridge_client.py tests/test_remote_backup_service.py tests/test_remote_backups_api.py tests/test_st_auth_flow.py -q
```

Expected: PASS.

- [ ] **Step 3: Check diffs**

Run in both repositories:

```bash
git diff --stat
git diff --check
git status --short --branch
```

Expected: no whitespace errors; only files listed in this plan changed.

- [ ] **Step 4: Commit Authority**

Run in `ST-Delegation-of-authority`:

```bash
git add packages/server-plugin/src/services/st-manager-bridge-service.ts packages/server-plugin/src/services/st-manager-bridge-service.test.ts packages/server-plugin/src/routes.ts packages/server-plugin/src/routes.test.ts
git commit -m "feat: allow key-only ST Manager bridge access"
```

- [ ] **Step 5: Commit ST-Manager**

Run in `ST-Manager`:

```bash
git add core/services/remote_st_bridge_client.py core/services/remote_backup_service.py tests/test_remote_st_bridge_client.py tests/test_remote_backups_api.py tests/test_remote_backup_service.py static/js/state.js templates/modals/settings.html tests/test_settings_frontend_contracts.py docs/superpowers/plans/2026-05-01-authority-bridge-simple-connection.md
git commit -m "feat: add Authority Bridge remote connection mode"
```

- [ ] **Step 6: Push**

Run:

```bash
git -C "E:/cursor_project/ST-Delegation of authority/ST-Delegation-of-authority" push origin HEAD:dev
git -C "E:/cursor_project/ST-Delegation of authority/ST-Manager" push origin main
```

Expected: Authority updates `origin/dev`, ST-Manager updates `origin/main`.
