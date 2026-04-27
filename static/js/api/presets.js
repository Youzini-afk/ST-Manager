/**
 * static/js/api/presets.js
 * 预设详情与编辑 API
 */

const presetSendToStInFlightIds = new Set();

export async function getPresetDetail(presetId) {
  const res = await fetch(
    `/api/presets/detail/${encodeURIComponent(presetId)}`,
  );
  return res.json();
}

export async function savePreset(payload) {
  const res = await fetch("/api/presets/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function savePresetExtensions(payload) {
  const res = await fetch("/api/presets/save-extensions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function setDefaultPresetVersion(payload) {
  const res = await fetch("/api/presets/version/set-default", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function sendPresetToSillyTavern(payload) {
  const res = await fetch("/api/presets/send_to_st", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return res.json();
}

export function isPresetSendToStPending(presetId) {
  const key = String(presetId || "").trim();
  return !!key && presetSendToStInFlightIds.has(key);
}

export function setPresetSendToStPending(presetId, sending) {
  const key = String(presetId || "").trim();
  if (!key) return;
  if (sending) {
    presetSendToStInFlightIds.add(key);
    return;
  }
  presetSendToStInFlightIds.delete(key);
}
