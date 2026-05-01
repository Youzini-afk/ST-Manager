# Authority + ST-Manager Bidirectional Remote Backup Implementation Plan

## Goal

Build a complete remote backup workflow where ST-Manager can manually or periodically back up and restore SillyTavern resources, and Authority inside SillyTavern can remotely trigger the same ST-Manager backup and restore operations.

## Architecture

ST-Manager remains the backup execution center and immutable backup source of truth. Authority provides the SillyTavern-side resource bridge and a thin control surface that calls ST-Manager. Data can move both ways between ST and ST-Manager, while backup history, scheduling, logs, and retention live in ST-Manager.

## Current State

- Authority exposes `/api/plugins/authority/st-manager/*` bridge APIs for probe, manifest, chunked read, and chunked write.
- Authority has an admin UI for enabling the Bridge and generating the Bridge Key.
- ST-Manager has backend remote backup APIs:
  - `GET/POST /api/remote_backups/config`
  - `POST /api/remote_backups/probe`
  - `POST /api/remote_backups/start`
  - `GET /api/remote_backups/list`
  - `GET /api/remote_backups/detail`
  - `POST /api/remote_backups/restore-preview`
  - `POST /api/remote_backups/restore`
- ST-Manager does not yet have a complete manual backup/restore UI.
- ST-Manager does not yet have remote backup scheduling.
- Authority cannot yet call ST-Manager to start a backup or restore.

## Target Model

```text
Authority UI
  -> ST-Manager Control API
      -> ST-Manager RemoteBackupService
          -> Authority Bridge API
              -> SillyTavern files
          -> ST-Manager data/system/remote_backups/<backup_id>
          -> ST-Manager data/library/*
```

ST-Manager is responsible for:

- Creating immutable backup snapshots.
- Listing backup history.
- Restoring backups to SillyTavern.
- Running scheduled backups.
- Applying retention limits.
- Holding audit logs.

Authority is responsible for:

- Detecting the active SillyTavern user's resource directories.
- Reading and writing resource files safely inside the ST process.
- Providing an in-ST UI that can trigger ST-Manager operations through a Control Key.

## Security Model

Two separate secrets are required:

- **Authority Bridge Key:** ST-Manager uses this to read/write SillyTavern resources through Authority.
- **ST-Manager Control Key:** Authority uses this to start/list/restore ST-Manager remote backups.

Rules:

- Neither project returns stored key plaintext after save.
- Key plaintext is returned only when generated or rotated.
- ST-Manager machine control endpoints require the Control Key.
- Destructive restore overwrite requires explicit `overwrite=true` and UI confirmation.
- v1 exposes no remote delete operation for SillyTavern resources.

## ST-Manager Work

### Phase 1: Manual Remote Backup UI

- Add `static/js/api/remoteBackups.js` with wrappers for config, probe, start, list, detail, restore preview, and restore.
- Add `static/js/components/remoteBackupPanel.js`.
- Add `templates/modals/remote_backups.html`.
- Register the component in `static/js/app.js`.
- Add a header or settings entry point.
- Add contract tests proving the UI includes manual backup, list, preview, restore, and overwrite confirmation controls.

### Phase 2: Job State And Scheduling

- Add `core/services/remote_backup_jobs.py`.
- Add `core/services/remote_backup_scheduler.py`.
- Add schedule APIs under `/api/remote_backups/schedule`.
- Add job APIs under `/api/remote_backups/jobs`.
- Prevent overlapping backup/restore jobs.
- Persist recent job state under `data/system/remote_backups/jobs.json`.
- Add retention for local backup directories only.

### Phase 3: Control Key

- Add `core/services/remote_backup_control_auth.py`.
- Add `GET /api/remote_backups/control`.
- Add `POST /api/remote_backups/control`.
- Add `POST /api/remote_backups/control-key/rotate`.
- Require `X-ST-Manager-Control-Key` for machine calls from Authority.
- Keep normal browser UI access working.

## Authority Work

### Phase 4: Authority Calls ST-Manager

- Add `packages/server-plugin/src/services/st-manager-control-service.ts`.
- Add `/api/plugins/authority/st-manager/control/*` routes.
- Add `packages/sdk-extension/src/security-center/st-manager-control.ts`.
- Add a Security Center control panel below the existing ST-Manager Bridge panel.
- Hide saved ST-Manager Control Key plaintext.
- Support test connection, start backup, list backups, restore preview, and restore.

### Phase 5: Pairing Flow

- Authority sends current ST URL, Bridge Key, and selected resource types to ST-Manager.
- ST-Manager saves the remote backup config and returns a probe result.
- If Authority no longer has Bridge Key plaintext, the UI asks the admin to rotate the Bridge Key before pairing.

## Verification Commands

ST-Manager:

```powershell
pytest tests/test_remote_backups_api.py -q
pytest tests/test_remote_backup_service.py -q
pytest tests/test_remote_backup_scheduler.py -q
pytest tests/test_remote_backup_frontend_contracts.py -q
pytest -q
git diff --check
```

Authority:

```powershell
npx vitest run packages/server-plugin/src/services/st-manager-control-service.test.ts packages/sdk-extension/src/security-center/st-manager-control.test.ts
npm run typecheck
npx vitest run
npm run build --workspace @stdo/server-plugin
npm run build --workspace @stdo/sdk-extension
node ./scripts/installable.mjs sync
npm run check:installable
git diff --check
```

## Delivery Criteria

- ST-Manager can run a manual backup from UI.
- ST-Manager can restore a selected backup from UI after preview.
- ST-Manager can run scheduled backups.
- Authority can trigger ST-Manager backup/restore from the SillyTavern-side panel.
- Both projects hide stored key plaintext.
- Tests cover backend services, API routes, and frontend contracts.
