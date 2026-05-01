# ST-Manager Server and Zeabur Deployment Design

Date: 2026-05-01

## Context

ST-Manager is currently friendly to local desktop use and basic Docker Compose use, but it is not yet friendly enough for PaaS/server deployment. The current startup path reads host and port from CLI arguments or `config.json`, stores `config.json` and `data/` under the repository root, starts with Flask's development server, opens a browser on startup, and protects API routes with the login middleware.

Zeabur-style deployment needs a different runtime profile: the app should listen on the platform-provided port, keep mutable state under a mounted persistent volume, expose a lightweight unauthenticated health endpoint, and start through a production WSGI server. Public deployments should make missing authentication very visible without preventing the app from starting.

Relevant platform references:

- Zeabur Flask guide: https://zeabur.com/docs/en-US/guides/python/flask
- Zeabur Dockerfile deployment: https://zeabur.com/docs/en-US/deploy/dockerfile
- Zeabur health checks: https://zeabur.com/docs/en-US/operations/monitoring/health-checks
- Zeabur template in code: https://zeabur.com/docs/en-US/template/template-in-code
- Flask deployment guidance: https://flask.palletsprojects.com/en/stable/deploying/

## Goals

- Keep local `python app.py` behavior familiar.
- Make Docker and Zeabur deployments work without editing `config.json` inside the image.
- Support one mounted persistent data directory, recommended as `/data`.
- Support platform-injected `PORT` while preserving CLI overrides.
- Add a simple health endpoint that does not require login.
- Use a production WSGI server in containers.
- Add Zeabur one-click/template deployment files and documentation.
- Allow public deployment without auth credentials, but warn clearly in logs and UI.

## Non-Goals

- Do not redesign ST-Manager authentication.
- Do not force cloud deployments to fail when auth is missing.
- Do not require SillyTavern to run in the same container or platform project.
- Do not migrate existing user data automatically between arbitrary host paths.
- Do not change the remote backup bridge protocol in this deployment pass.

## Deployment Profiles

### Local Desktop

Default local behavior remains:

- `config.json` lives in the project root unless an override is provided.
- `data/` lives in the project root unless an override is provided.
- Host defaults to `127.0.0.1`.
- Browser auto-open remains enabled for normal desktop runs.
- `python app.py` remains supported.

### Server/PaaS

Server behavior is activated by environment and container signals:

- `PORT` or `STM_SERVER_PROFILE=1` marks the run as server-oriented.
- Containers default to `0.0.0.0`.
- Browser auto-open is disabled by default.
- Logs show a prominent warning when no auth credentials are configured.
- Persistent state can be redirected with `STM_DATA_DIR=/data`.
- `STM_CONFIG_FILE=/data/config.json` can place config beside the persisted data.

## Configuration Precedence

Host and port resolution:

1. CLI `--host` / `--port`
2. Environment: `HOST` / `PORT`
3. `config.json`
4. Built-in defaults

Path resolution:

1. `STM_CONFIG_FILE` controls the active config file path.
2. `STM_DATA_DIR` controls the base data directory.
3. Existing defaults remain `config.json` and `data/` under the repo root.

This preserves existing desktop behavior while letting Zeabur inject `PORT` and mount `/data` without patching generated config files.

## Runtime Data Layout

When `STM_DATA_DIR=/data` and `STM_CONFIG_FILE=/data/config.json` are set, mutable runtime state should live under:

```text
/data/
├── config.json
├── library/
│   ├── characters/
│   ├── chats/
│   ├── lorebooks/
│   ├── presets/
│   └── extensions/
├── assets/
├── system/
│   ├── db/
│   ├── remote_backups/
│   ├── thumbnails/
│   └── trash/
├── temp/
└── .secret_key
```

Generated default config values should be data-root aware. When `STM_DATA_DIR` is active, default library paths should point inside that data directory instead of `data/...` under the app source tree.

## Health Endpoint

Add `GET /healthz`.

Behavior:

- Returns HTTP 200 when the Flask app is able to respond.
- Does not require login.
- Does not perform heavy scans, ST remote calls, or database migrations.
- Returns compact JSON such as `{ "ok": true, "service": "st-manager" }`.

The auth middleware should explicitly exclude `/healthz`. Existing authenticated status endpoints remain unchanged.

## Production Server

Containers should start through a production WSGI server. The preferred Linux container command is Gunicorn:

```bash
gunicorn "core:create_app()" --bind "0.0.0.0:${PORT:-5000}" --workers "${WEB_CONCURRENCY:-1}" --threads "${WEB_THREADS:-8}" --timeout "${WEB_TIMEOUT:-120}"
```

Because ST-Manager starts background services outside `create_app()` today, add a small production entrypoint module that:

- Ensures config and runtime directories exist.
- Starts background services once per process.
- Exposes the Flask app object for Gunicorn.

Use one worker by default. ST-Manager has file watchers, caches, SQLite, and background jobs; multiple workers can be supported later, but one worker avoids duplicated scanners and writer contention in v1.

## Browser Auto-Open

Browser auto-open should stay on for normal desktop runs and be off for server runs.

Rules:

- `STM_DISABLE_BROWSER_OPEN=1` always disables it.
- `PORT` or `STM_SERVER_PROFILE=1` disables it by default.
- Docker/container detection disables it by default.
- Local `python app.py` without server env keeps the current behavior.

## Public Deployment Warning

If the app is bound to a public/server profile and auth credentials are missing, it should still start but warn clearly.

Warnings:

- Log a multi-line warning during startup.
- Expose a non-secret runtime security status in `/api/status` or a small authenticated config/status payload.
- Show a visible UI warning banner for authenticated/allowed users when auth is disabled in server profile.

Auth detection uses the existing logic: `STM_AUTH_USER` + `STM_AUTH_PASS` or `auth_username` + `auth_password`.

## Docker Changes

Dockerfile should:

- Install the production WSGI dependency.
- Set server-friendly defaults:
  - `HOST=0.0.0.0`
  - `PORT=5000`
  - `STM_SERVER_PROFILE=1`
  - `STM_DATA_DIR=/data`
  - `STM_CONFIG_FILE=/data/config.json`
  - `STM_DISABLE_BROWSER_OPEN=1`
- Expose 5000 for local Docker use.
- Add a healthcheck against `/healthz`.
- Create `/data` as the intended volume path.

Docker Compose should be simplified:

- Remove the separate `init-config` service if startup can safely create config in the mounted data volume.
- Mount `./data:/data`.
- Keep `host.docker.internal` support for local SillyTavern access.
- Document `STM_AUTH_USER`, `STM_AUTH_PASS`, and `STM_SECRET_KEY`.

## Zeabur One-Click Deployment

Add a Zeabur template file that defines:

- One web service built from the repository Dockerfile.
- A persistent volume mounted at `/data`.
- Environment variables:
  - `STM_SERVER_PROFILE=1`
  - `STM_DATA_DIR=/data`
  - `STM_CONFIG_FILE=/data/config.json`
  - `STM_DISABLE_BROWSER_OPEN=1`
  - `STM_AUTH_USER`
  - `STM_AUTH_PASS`
  - `STM_SECRET_KEY`
- Health check path `/healthz`.

Documentation should explain:

- Deploy from GitHub/Zeabur template.
- Set auth credentials before exposing publicly.
- Configure remote SillyTavern URL and Authority Bridge Key from the ST-Manager UI after first login.
- For self-hosted ST, the ST URL must be reachable from Zeabur; `127.0.0.1` from Zeabur means the ST-Manager container, not the user's PC.

## UI Warning

Add a small warning banner in the existing UI shell when:

- Server profile is active.
- ST-Manager auth is disabled.

The banner should be concise and actionable. Suggested text:

```text
公网部署未启用登录保护。请设置 STM_AUTH_USER / STM_AUTH_PASS 或在设置中配置外网访问账号密码。
```

Do not show this warning for normal local desktop runs.

## Error Handling

- Invalid `PORT` falls back to config/default and logs a warning.
- Missing or invalid `STM_DATA_DIR` should try to create the directory and fail loudly only if creation fails.
- Missing auth credentials in server profile logs and displays warnings but does not stop startup.
- `/healthz` should remain available even if auth is enabled or the app is in auth hard-lock mode.

## Compatibility

- Existing `config.json` files remain valid.
- Existing relative library paths continue to resolve relative to the app base directory unless a new data-root-aware config is generated under `STM_DATA_DIR`.
- Existing Docker Compose users can keep using `./data`, but the container path changes to `/data`.
- Existing tests around config bootstrap should be extended rather than replaced.

## Test Plan

Unit and integration tests:

- `resolve_server_settings` honors CLI over env over config.
- `PORT` is parsed as an integer and invalid values are ignored with a warning.
- `STM_CONFIG_FILE` changes config load/save target.
- `STM_DATA_DIR` changes `DATA_DIR`, system directories, and generated runtime directory defaults.
- Startup config generation creates `/data/config.json` with data-root-aware defaults when server env is active.
- Browser auto-open is disabled in Docker/server env and can be explicitly disabled.
- `/healthz` returns 200 without auth.
- `/healthz` still returns 200 when auth is enabled.
- Auth-disabled server profile emits a warning status for UI consumption.
- Docker/Zeabur docs mention persistent volume, `PORT`, `/healthz`, and auth env vars.

Manual checks:

- Local `python app.py` still opens `127.0.0.1:5000`.
- Docker Compose starts and persists data under `./data`.
- Docker container responds on `/healthz`.
- Zeabur deployment starts with platform `PORT` and mounted `/data`.
- Remote backup config and snapshots persist across container restart.
