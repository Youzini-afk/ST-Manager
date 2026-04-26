/**
 * static/js/api/presets.js
 * 预设详情与编辑 API
 */

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
