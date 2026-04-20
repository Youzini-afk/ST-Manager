async function parseJson(res) {
  return res.json();
}

export async function listBeautifyPackages() {
  const res = await fetch("/api/beautify/list");
  return parseJson(res);
}

export async function getBeautifyPackage(packageId) {
  const res = await fetch(`/api/beautify/${encodeURIComponent(packageId)}`);
  return parseJson(res);
}

export async function importBeautifyTheme(file, options = {}) {
  const formData = new FormData();
  formData.append("file", file);
  if (options.package_id) formData.append("package_id", options.package_id);
  if (options.platform) formData.append("platform", options.platform);

  const res = await fetch("/api/beautify/import-theme", {
    method: "POST",
    body: formData,
  });
  return parseJson(res);
}

export async function importBeautifyWallpaper(file, packageId, variantId) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("package_id", packageId);
  formData.append("variant_id", variantId);

  const res = await fetch("/api/beautify/import-wallpaper", {
    method: "POST",
    body: formData,
  });
  return parseJson(res);
}

export async function updateBeautifyVariant(payload) {
  const res = await fetch("/api/beautify/update-variant", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(res);
}

export async function deleteBeautifyPackage(packageId) {
  const res = await fetch("/api/beautify/delete-package", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ package_id: packageId }),
  });
  return parseJson(res);
}

export function buildBeautifyPreviewAssetUrl(relativePath) {
  if (!relativePath) return "";
  const normalized = String(relativePath).replace(
    /^data\/library\/beautify\//,
    "",
  );
  return `/api/beautify/preview-asset/${normalized.split("/").map(encodeURIComponent).join("/")}`;
}
