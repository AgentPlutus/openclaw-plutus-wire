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

function reviewCard(card) {
  const node = document.createElement("article");
  node.className = "brief-card";

  const header = document.createElement("div");
  header.className = "card-header";
  const title = document.createElement("h3");
  title.textContent = card.title || "Untitled signal";
  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `Score ${card.score || 0}`;
  header.append(title, score);

  const summary = document.createElement("p");
  summary.textContent = card.summary || "No summary available.";

  const why = document.createElement("p");
  why.className = "meta";
  why.textContent = card.why_it_matters || "";

  const provenance = document.createElement("div");
  provenance.className = "provenance";
  for (const item of card.source_provenance || []) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${item.source} · ${item.sighting_count}`;
    provenance.append(pill);
  }

  const evidence = document.createElement("div");
  evidence.className = "evidence";
  for (const item of (card.evidence || []).slice(0, 3)) {
    const row = document.createElement("a");
    row.href = item.url || "#";
    row.target = "_blank";
    row.rel = "noreferrer";
    row.textContent = `${item.author || "unknown"} · ${item.posted_at || "unknown"}`;
    evidence.append(row);
  }

  node.append(header, summary, why, provenance, evidence);
  return node;
}

async function main() {
  const config = await readJson("/data/config.json");
  const manifest = await readJson("/data/latest-manifest.json");
  const dbStatus = await readJson("/data/db-status.json");
  const cards = await readJson("/data/latest-cards.json");
  const cloud = await readJson("/data/latest-cloud-manifest.json");

  const status = document.getElementById("runtime-status");
  const updatedAt = document.getElementById("updated-at");
  const sources = document.getElementById("sources");
  const lastRun = document.getElementById("last-run");
  const dbStatusNode = document.getElementById("db-status");
  const cardsNode = document.getElementById("cards");
  const cloudNode = document.getElementById("cloud-status");

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

  if (dbStatus.counts) {
    dbStatusNode.textContent = `posts ${dbStatus.counts.posts}, sightings ${dbStatus.counts.sightings}, checkpoints ${dbStatus.counts.checkpoints}, runtime ${dbStatus.counts.source_runtime || 0}`;
  } else {
    dbStatusNode.textContent = "No SQLite status loaded yet.";
  }

  if (cards.cards && cards.cards.length) {
    cardsNode.replaceChildren(...cards.cards.map(reviewCard));
  } else {
    cardsNode.textContent = "No review cards yet. Run scripts/plutus_wire_process.py after an ingest.";
  }

  if (cloud.manifest_id) {
    cloudNode.textContent = `${cloud.mode}: ${cloud.upload_status} · ${cloud.manifest_id}`;
  } else {
    cloudNode.textContent = "Cloud handoff is off unless explicitly enabled.";
  }
}

main().catch((error) => {
  document.getElementById("runtime-status").textContent = "Status error";
  document.getElementById("updated-at").textContent = error.message || String(error);
});
