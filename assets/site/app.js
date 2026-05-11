async function readJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) return {};
  return response.json();
}

function sourceCard(name, entry) {
  const node = document.createElement("div");
  node.className = "source";

  const title = document.createElement("strong");
  title.textContent = entry.label || name;

  const pill = document.createElement("span");
  pill.className = entry.enabled ? "pill on" : "pill";
  pill.textContent = entry.enabled ? "Enabled" : "Off";

  const meta = document.createElement("div");
  meta.className = "meta";
  const parts = [
    `source: ${name}`,
    `detected: ${entry.detected ? "yes" : "no"}`,
    `support: ${entry.support || "unknown"}`,
  ];
  if (entry.requires_handle) parts.push(`handle: ${entry.handle || "not set"}`);
  for (const part of parts) {
    const row = document.createElement("div");
    const code = document.createElement("code");
    code.textContent = part;
    row.append(code);
    meta.append(row);
  }

  node.append(title, pill, meta);
  return node;
}

async function main() {
  const config = await readJson("/data/config.json");
  const manifest = await readJson("/data/latest-manifest.json");

  const status = document.getElementById("runtime-status");
  const updatedAt = document.getElementById("updated-at");
  const sources = document.getElementById("sources");
  const lastRun = document.getElementById("last-run");

  if (config.version) {
    status.textContent = "Local config loaded";
    updatedAt.textContent = `Updated ${config.updated_at || "unknown"}`;
    sources.replaceChildren(
      ...Object.entries(config.sources || {}).map(([name, entry]) => sourceCard(name, entry)),
    );
  } else {
    status.textContent = "No config";
    updatedAt.textContent = "Run scripts/plutus_wire_setup.py to create local config.";
    sources.textContent = "No configured sources.";
  }

  if (manifest.run_id) {
    const ok = (manifest.sources || []).filter((source) => source.status === "ok").length;
    lastRun.textContent = `${manifest.run_id}: ${ok}/${(manifest.sources || []).length} sources ok`;
  } else {
    lastRun.textContent = "No run manifest loaded yet.";
  }
}

main().catch((error) => {
  document.getElementById("runtime-status").textContent = "Status error";
  document.getElementById("updated-at").textContent = error.message || String(error);
});
