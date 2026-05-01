async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  return response.json();
}

export function getRemoteBackupConfig() {
  return requestJson("/api/remote_backups/config");
}

export function saveRemoteBackupConfig(config) {
  return requestJson("/api/remote_backups/config", {
    method: "POST",
    body: JSON.stringify(config || {}),
  });
}

export function probeRemoteBackup() {
  return requestJson("/api/remote_backups/probe", { method: "POST" });
}

export function startRemoteBackup(payload = {}) {
  return requestJson("/api/remote_backups/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listRemoteBackups() {
  return requestJson("/api/remote_backups/list");
}

export function getRemoteBackupDetail(backupId) {
  return requestJson(`/api/remote_backups/detail?backup_id=${encodeURIComponent(backupId)}`);
}

export function restoreRemoteBackupPreview(payload = {}) {
  return requestJson("/api/remote_backups/restore-preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function restoreRemoteBackup(payload = {}) {
  return requestJson("/api/remote_backups/restore", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRemoteBackupSchedule() {
  return requestJson("/api/remote_backups/schedule");
}

export function getRemoteBackupControl() {
  return requestJson("/api/remote_backups/control");
}

export function rotateRemoteBackupControlKey() {
  return requestJson("/api/remote_backups/control-key/rotate", { method: "POST" });
}

export function saveRemoteBackupSchedule(schedule) {
  return requestJson("/api/remote_backups/schedule", {
    method: "POST",
    body: JSON.stringify(schedule || {}),
  });
}
