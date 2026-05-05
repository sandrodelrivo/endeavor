/**
 * Structure Manager main app logic.
 * Talks to the FastAPI backend, populates the sidebar and info panel,
 * and delegates 3-D rendering to viewer.js.
 */

import { renderStructure, clearViewer } from "./viewer.js";

// ── State ──────────────────────────────────────────────────
let allStructures = [];       // raw list from /api/structures
let selectedId    = null;     // currently selected resource_id
let selectedPiece = null;     // currently shown NBT piece

// ── DOM refs ───────────────────────────────────────────────
const listEl        = document.getElementById("structure-list");
const searchEl      = document.getElementById("search");
const filterSource  = document.getElementById("filter-source");
const filterEntity  = document.getElementById("filter-entity");
const filterDisabled= document.getElementById("filter-disabled");
const statsBar      = document.getElementById("stats-bar");
const spawnToggle   = document.getElementById("spawn-toggle");
const infoContent   = document.getElementById("info-content");
const infoPlaceholder=document.getElementById("info-placeholder");
const infoName      = document.getElementById("info-name");
const infoMeta      = document.getElementById("info-meta");
const entityList    = document.getElementById("entity-list");
const entityCount   = document.getElementById("entity-count");
const entityNone    = document.getElementById("entity-none");
const piecesList    = document.getElementById("pieces-list");
const pieceCount    = document.getElementById("piece-count");
const piecesNone    = document.getElementById("pieces-none");
const pieceSelect   = document.getElementById("piece-select");
const viewerPlaceholder = document.getElementById("viewer-placeholder");
const viewerInfo    = document.getElementById("viewer-info");

// ── Helpers ────────────────────────────────────────────────

function showLoading(msg = "Working…") {
  let el = document.getElementById("loading-overlay");
  if (!el) {
    el = document.createElement("div");
    el.id = "loading-overlay";
    el.innerHTML = `<div class="spinner"></div><span></span>`;
    document.body.appendChild(el);
  }
  el.querySelector("span").textContent = msg;
  el.classList.remove("hidden");
}

function hideLoading() {
  const el = document.getElementById("loading-overlay");
  if (el) el.classList.add("hidden");
}

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const txt = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path}: ${txt}`);
  }
  return res.json();
}

async function apiPost(path) {
  const res = await fetch(path, { method: "POST" });
  if (!res.ok) {
    const txt = await res.text().catch(() => res.statusText);
    throw new Error(`POST ${path}: ${txt}`);
  }
  return res.json();
}

// ── Stats bar ──────────────────────────────────────────────

async function refreshStats() {
  try {
    const s = await api("/api/stats");
    const entityNote = s.entities_ready
      ? `· ${s.with_villager} with villager`
      : `· <em style="color:var(--warn)">scanning entities…</em>`;
    statsBar.innerHTML =
      `${s.total} structures · ${s.enabled} enabled · ${s.disabled} disabled ${entityNote}`;
  } catch (e) {
    statsBar.textContent = "Stats unavailable";
  }
}

// ── Structure list ─────────────────────────────────────────

function buildQuery() {
  const p = new URLSearchParams();
  if (searchEl.value.trim())         p.set("search", searchEl.value.trim());
  if (filterSource.value)            p.set("source", filterSource.value);
  if (filterEntity.value.trim())     p.set("has_entity", filterEntity.value.trim());
  return p.toString();
}

async function loadList() {
  showLoading("Loading structures…");
  try {
    let url = "/api/structures";
    const q = buildQuery();
    if (q) url += "?" + q;
    allStructures = await api(url);

    // Client-side disabled filter (not a server param)
    let visible = allStructures;
    if (filterDisabled.checked) visible = visible.filter(s => !s.enabled);

    renderList(visible);
    refreshStats();
  } catch (e) {
    listEl.innerHTML = `<li style="padding:14px;color:#e05252">${e.message}</li>`;
  } finally {
    hideLoading();
  }
}

function renderList(structures) {
  listEl.innerHTML = "";

  if (structures.length === 0) {
    listEl.innerHTML = `<li style="padding:14px;color:var(--muted)">No structures match.</li>`;
    return;
  }

  for (const s of structures) {
    const li = document.createElement("li");
    li.className = "structure-item" +
      (s.id === selectedId ? " active" : "") +
      (!s.enabled ? " disabled" : "");
    li.dataset.id = s.id;

    const [ns, ...rest] = s.id.split(":");
    const path = rest.join(":");

    const sourceTag = s.source_type === "mod"
      ? `<span class="tag tag-mod">${s.source_label}</span>`
      : `<span class="tag tag-dp">datapack</span>`;

    const warnTag = s.has_villager
      ? `<span class="tag tag-warn">villager</span>`
      : "";

    li.innerHTML = `
      <input type="checkbox" class="item-toggle" ${s.enabled ? "checked" : ""} title="Toggle spawning">
      <span class="item-name"><span class="item-ns">${ns}:</span>${path}</span>
      <span class="item-badges">${sourceTag}${warnTag}</span>
    `;

    // Toggle click (doesn't propagate to row select)
    li.querySelector(".item-toggle").addEventListener("click", async (e) => {
      e.stopPropagation();
      const cb = e.currentTarget;
      const newEnabled = cb.checked;
      await setEnabled(s.id, newEnabled);
    });

    // Row click → select
    li.addEventListener("click", () => selectStructure(s.id));

    listEl.appendChild(li);
  }
}

// ── Enable / disable ────────────────────────────────────────

async function setEnabled(id, enabled) {
  showLoading(enabled ? "Enabling…" : "Disabling…");
  try {
    await apiPost(`/api/structure/set_enabled?id=${encodeURIComponent(id)}&enabled=${enabled}`);
    // Update local data
    const s = allStructures.find(x => x.id === id);
    if (s) s.enabled = enabled;

    // Sync toggle in info panel
    if (id === selectedId) spawnToggle.checked = enabled;

    // Update list item
    const li = listEl.querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (li) {
      li.classList.toggle("disabled", !enabled);
      li.querySelector(".item-toggle").checked = enabled;
    }

    refreshStats();
  } catch (e) {
    alert(`Failed: ${e.message}`);
    // Revert checkbox
    const li = listEl.querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (li) {
      const s = allStructures.find(x => x.id === id);
      if (s) li.querySelector(".item-toggle").checked = s.enabled;
    }
  } finally {
    hideLoading();
  }
}

// ── Info panel ──────────────────────────────────────────────

async function selectStructure(id) {
  if (selectedId === id) return;
  selectedId = id;
  selectedPiece = null;

  // Update active class in list
  listEl.querySelectorAll(".structure-item").forEach(li => {
    li.classList.toggle("active", li.dataset.id === id);
  });

  // Fetch details
  showLoading("Loading details…");
  try {
    const d = await api(`/api/structure/details?id=${encodeURIComponent(id)}`);
    renderInfoPanel(d);
  } catch (e) {
    infoContent.hidden = true;
    infoPlaceholder.hidden = false;
    infoPlaceholder.textContent = `Error: ${e.message}`;
  } finally {
    hideLoading();
  }
}

function renderInfoPanel(d) {
  infoPlaceholder.hidden = true;
  infoContent.hidden = false;

  infoName.textContent = d.id;

  infoMeta.innerHTML = `
    <span class="tag ${d.source_type === 'mod' ? 'tag-mod' : 'tag-dp'}">${d.source_label}</span>
    <span class="muted">${d.structure_type}</span>
  `;

  spawnToggle.checked = d.enabled;

  // Entities
  entityCount.textContent = d.entities.length;
  entityList.innerHTML = "";
  entityNone.hidden = d.entities.length > 0;

  for (const eid of d.entities) {
    const li = document.createElement("li");
    const isVillager = ["minecraft:villager","minecraft:wandering_trader","minecraft:zombie_villager"].includes(eid);
    if (isVillager) li.classList.add("li-warn");
    li.textContent = (isVillager ? "⚠ " : "") + eid;
    li.title = isVillager ? "This entity violates the 'no villagers' rule." : "";
    entityList.appendChild(li);
  }

  // NBT pieces — populate both the info-panel list and the toolbar dropdown
  pieceCount.textContent = d.pieces.length;
  piecesList.innerHTML = "";
  piecesNone.hidden = d.pieces.length > 0;

  // Toolbar dropdown
  pieceSelect.innerHTML = `<option value="">— select piece —</option>`;

  for (const piece of d.pieces) {
    // Info panel list
    const li = document.createElement("li");
    li.textContent = piece;
    li.title = "Click to preview in 3-D viewer";
    li.addEventListener("click", () => loadPiece(piece, li));
    piecesList.appendChild(li);

    // Dropdown
    const opt = document.createElement("option");
    opt.value = piece;
    const short = piece.split(":").pop().split("/").pop();
    opt.textContent = short + " (" + piece.split(":")[0] + ")";
    pieceSelect.appendChild(opt);
  }

  // Auto-load first piece
  if (d.pieces.length > 0) {
    const firstLi = piecesList.firstElementChild;
    loadPiece(d.pieces[0], firstLi);
  } else {
    clearViewer();
    viewerPlaceholder.classList.remove("hidden");
    viewerInfo.textContent = "";
    pieceSelect.value = "";
  }
}

async function loadPiece(pieceId, liEl) {
  if (selectedPiece === pieceId) return;
  selectedPiece = pieceId;

  // Highlight in panel
  piecesList.querySelectorAll("li").forEach(li => li.classList.remove("active-piece"));
  if (liEl) liEl.classList.add("active-piece");
  pieceSelect.value = pieceId;

  viewerPlaceholder.classList.add("hidden");
  showLoading("Loading piece…");
  try {
    const data = await api(
      `/api/structure/render?id=${encodeURIComponent(selectedId)}&piece=${encodeURIComponent(pieceId)}`
    );
    if (data.error) throw new Error(data.error);
    renderStructure(data);
    viewerInfo.textContent = `${data.blocks.length.toLocaleString()} blocks`;
  } catch (e) {
    clearViewer();
    viewerPlaceholder.classList.remove("hidden");
    viewerPlaceholder.querySelector("p").textContent = `Error: ${e.message}`;
    viewerInfo.textContent = "";
  } finally {
    hideLoading();
  }
}

// ── Toolbar piece select ───────────────────────────────────
pieceSelect.addEventListener("change", () => {
  const id = pieceSelect.value;
  if (!id) return;
  const li = Array.from(piecesList.querySelectorAll("li")).find(li => li.textContent === id);
  loadPiece(id, li || null);
});

// ── Info panel spawn toggle ────────────────────────────────
spawnToggle.addEventListener("change", () => {
  if (selectedId) setEnabled(selectedId, spawnToggle.checked);
});

// ── Filter + search events ─────────────────────────────────
let searchTimer;
searchEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadList, 250);
});

filterSource.addEventListener("change", loadList);
filterDisabled.addEventListener("change", loadList);

let entityFilterTimer;
filterEntity.addEventListener("input", () => {
  clearTimeout(entityFilterTimer);
  entityFilterTimer = setTimeout(loadList, 300);
});

// ── Rescan ─────────────────────────────────────────────────
document.getElementById("btn-rescan").addEventListener("click", async () => {
  showLoading("Rescanning all JARs and datapack…");
  try {
    const result = await apiPost("/api/rescan");
    await loadList();
    console.log(`Rescan: ${result.count} structures found.`);
  } catch (e) {
    alert(`Rescan failed: ${e.message}`);
  } finally {
    hideLoading();
  }
});

// ── Disable all visible ────────────────────────────────────
document.getElementById("btn-disable-all").addEventListener("click", async () => {
  const visible = Array.from(listEl.querySelectorAll(".structure-item"))
    .map(li => li.dataset.id)
    .filter(Boolean);

  if (visible.length === 0) return;

  const confirmed = confirm(
    `Disable all ${visible.length} currently visible structures?\n\nThis will write to structurify.json and/or the datapack.`
  );
  if (!confirmed) return;

  showLoading(`Disabling ${visible.length} structures…`);
  for (const id of visible) {
    await apiPost(`/api/structure/set_enabled?id=${encodeURIComponent(id)}&enabled=false`).catch(() => {});
  }
  await loadList();
  hideLoading();
});

// ── Entity-readiness polling ───────────────────────────────

let _pollTimer = null;

async function pollEntityReady() {
  try {
    const s = await api("/api/stats");
    refreshStats();
    if (s.entities_ready) {
      clearInterval(_pollTimer);
      _pollTimer = null;
      // Reload list to show entity counts and villager flags
      await loadList();
    }
  } catch (_) {}
}

// ── Init ───────────────────────────────────────────────────
loadList().then(async () => {
  // Check if entities are already ready; if not, poll every 2s
  try {
    const s = await api("/api/stats");
    if (!s.entities_ready) {
      _pollTimer = setInterval(pollEntityReady, 2000);
    }
  } catch (_) {}
});
