/* ApplyTrack frontend — vanilla JS, no build step, no framework.
   Talks to the FastAPI backend on the same origin (/api/...). */

const $ = (id) => document.getElementById(id);
const STATUSES = ["Applied", "OA/Assessment", "Interview", "Offer", "Rejected"];

let allApps = [];          // last full list from the server (for the pipeline chips)
let activeStatus = "";     // pipeline chip filter

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* keep default */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function daysUntil(isoDate) {
  if (!isoDate) return null;
  const ms = new Date(isoDate + "T00:00:00") - new Date(new Date().toDateString());
  return Math.round(ms / 86400000);
}

/* ---------- dashboard ---------- */

async function loadStats() {
  const stats = await api("/api/stats");
  $("statTotal").textContent = stats.total;
  $("statResponse").textContent = `${Math.round(stats.response_rate * 100)}%`;
  $("statInterviews").textContent = stats.by_status["Interview"] ?? 0;
  $("statOffers").textContent = stats.by_status["Offer"] ?? 0;
  $("statUpcoming").textContent = stats.upcoming_count;

  const pipe = $("pipeline");
  pipe.innerHTML = [`<button class="pipe-chip ${!activeStatus ? "active" : ""}" data-status="">All (${stats.total})</button>`]
    .concat(STATUSES.map((s) =>
      `<button class="pipe-chip ${activeStatus === s ? "active" : ""}" data-status="${esc(s)}">${esc(s)} (${stats.by_status[s] ?? 0})</button>`))
    .join("");
  pipe.querySelectorAll(".pipe-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeStatus = chip.dataset.status;
      $("statusFilter").value = activeStatus;
      loadStats(); loadApps();
    });
  });

  const list = $("upcomingList");
  if (!stats.upcoming_deadlines.length) {
    list.innerHTML = `<li class="muted">No deadlines in the next 7 days. 🎉</li>`;
  } else {
    list.innerHTML = stats.upcoming_deadlines.map((a) => {
      const d = daysUntil(a.deadline);
      const label = d === 0 ? "today" : d === 1 ? "tomorrow" : `in ${d} days`;
      return `<li><strong>${esc(a.company)}</strong> — ${esc(a.role)}
        <span class="due-soon">due ${label} (${esc(a.deadline)})</span></li>`;
    }).join("");
  }
}

/* ---------- table ---------- */

async function loadApps() {
  const params = new URLSearchParams();
  const status = $("statusFilter").value || activeStatus;
  if (status) params.set("status", status);
  if ($("termFilter").value) params.set("term", $("termFilter").value);
  if ($("searchInput").value.trim()) params.set("q", $("searchInput").value.trim());
  params.set("sort", $("sortSelect").value);

  const apps = await api(`/api/applications?${params}`);
  allApps = apps;
  const body = $("appsBody");
  $("emptyState").hidden = apps.length > 0;
  if (!apps.length) { body.innerHTML = ""; return; }

  body.innerHTML = apps.map((a) => {
    const due = daysUntil(a.deadline);
    const deadlineCell = a.deadline
      ? `${esc(a.deadline)}${due !== null && due <= 7 ? ` <span class="due-soon">(${due < 0 ? "overdue" : due === 0 ? "today" : due + "d"})</span>` : ""}`
      : "—";
    return `<tr>
      <td><strong>${esc(a.company)}</strong>
        ${a.link ? `<span class="sub"><a href="${esc(a.link)}" target="_blank" rel="noopener">posting ↗</a></span>` : ""}
        ${a.req_id ? `<span class="sub">Req ${esc(a.req_id)}</span>` : ""}</td>
      <td>${esc(a.role)}</td>
      <td>${esc(a.location || "—")}</td>
      <td>${esc(a.term || "—")}</td>
      <td>${esc(a.date_applied || "—")}</td>
      <td>${deadlineCell}</td>
      <td>${esc(a.pay || "—")}</td>
      <td><span class="badge badge-${esc(a.status)}">${esc(a.status)}</span></td>
      <td><div class="row-actions">
        <button class="btn btn-small" data-edit="${a.id}">Edit</button>
        <button class="btn btn-small" data-outreach="${a.id}">Outreach (${a.outreach_count})</button>
        <button class="btn btn-small" data-delete="${a.id}">Delete</button>
      </div></td>
    </tr>`;
  }).join("");

  body.querySelectorAll("[data-edit]").forEach((b) =>
    b.addEventListener("click", () => openEditModal(Number(b.dataset.edit))));
  body.querySelectorAll("[data-delete]").forEach((b) =>
    b.addEventListener("click", () => deleteApp(Number(b.dataset.delete))));
  body.querySelectorAll("[data-outreach]").forEach((b) =>
    b.addEventListener("click", () => openOutreachModal(Number(b.dataset.outreach))));
}

async function refresh() { await loadStats(); await loadApps(); }

/* ---------- add / edit ---------- */

function openAddModal() {
  $("modalTitle").textContent = "Add Application";
  $("appForm").reset();
  $("fieldId").value = "";
  $("fieldDateApplied").value = new Date().toISOString().slice(0, 10);
  $("formError").hidden = true;
  $("appModal").hidden = false;
  $("fieldCompany").focus();
}

function openEditModal(id) {
  const a = allApps.find((x) => x.id === id);
  if (!a) return;
  $("modalTitle").textContent = `Edit — ${a.company}`;
  $("fieldId").value = a.id;
  $("fieldCompany").value = a.company;
  $("fieldRole").value = a.role;
  $("fieldLocation").value = a.location || "";
  $("fieldTerm").value = a.term || "";
  $("fieldReqId").value = a.req_id || "";
  $("fieldPay").value = a.pay || "";
  $("fieldDateApplied").value = a.date_applied || "";
  $("fieldDeadline").value = a.deadline || "";
  $("fieldStatus").value = a.status;
  $("fieldLink").value = a.link || "";
  $("fieldNotes").value = a.notes || "";
  $("formError").hidden = true;
  $("appModal").hidden = false;
}

async function saveApp(event) {
  event.preventDefault();
  const payload = {
    company: $("fieldCompany").value.trim(),
    role: $("fieldRole").value.trim(),
    location: $("fieldLocation").value.trim() || null,
    term: $("fieldTerm").value.trim() || null,
    req_id: $("fieldReqId").value.trim() || null,
    pay: $("fieldPay").value.trim() || null,
    date_applied: $("fieldDateApplied").value || null,
    deadline: $("fieldDeadline").value || null,
    status: $("fieldStatus").value,
    link: $("fieldLink").value.trim() || null,
    notes: $("fieldNotes").value.trim() || null,
  };
  try {
    const id = $("fieldId").value;
    if (id) await api(`/api/applications/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    else await api("/api/applications", { method: "POST", body: JSON.stringify(payload) });
    $("appModal").hidden = true;
    await refresh();
  } catch (err) {
    const box = $("formError");
    box.textContent = `Could not save: ${err.message}`;
    box.hidden = false;
  }
}

async function deleteApp(id) {
  const a = allApps.find((x) => x.id === id);
  if (!confirm(`Delete the ${a ? a.company + " — " + a.role : "application"}? This also deletes its outreach log.`)) return;
  await api(`/api/applications/${id}`, { method: "DELETE" });
  await refresh();
}

/* ---------- outreach ---------- */

async function openOutreachModal(appId) {
  const a = allApps.find((x) => x.id === appId);
  if (!a) return;
  $("outreachTitle").textContent = `Outreach — ${a.company} (${a.role})`;
  $("outreachAppId").value = appId;
  $("outreachDate").value = new Date().toISOString().slice(0, 10);
  $("outreachError").hidden = true;
  await renderOutreach(appId);
  $("outreachModal").hidden = false;
}

async function renderOutreach(appId) {
  const entries = await api(`/api/applications/${appId}/outreach`);
  $("outreachList").innerHTML = entries.length
    ? entries.map((e) => `<li><span><strong>${esc(e.contact_name)}</strong> — ${esc(e.channel)}
        <span class="meta">${esc(e.date)}${e.notes ? " · " + esc(e.notes) : ""}</span></span>
        <button class="btn btn-small" data-del-outreach="${e.id}">✕</button></li>`).join("")
    : `<li class="muted">No outreach logged yet for this application.</li>`;
  $("outreachList").querySelectorAll("[data-del-outreach]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api(`/api/outreach/${b.dataset.delOutreach}`, { method: "DELETE" });
      await renderOutreach(appId); await refresh();
    }));
}

async function saveOutreach(event) {
  event.preventDefault();
  const appId = $("outreachAppId").value;
  try {
    await api(`/api/applications/${appId}/outreach`, {
      method: "POST",
      body: JSON.stringify({
        contact_name: $("outreachName").value.trim(),
        date: $("outreachDate").value || null,
        channel: $("outreachChannel").value,
        notes: $("outreachNotes").value.trim() || null,
      }),
    });
    $("outreachForm").reset();
    $("outreachDate").value = new Date().toISOString().slice(0, 10);
    await renderOutreach(Number(appId)); await refresh();
  } catch (err) {
    const box = $("outreachError");
    box.textContent = `Could not save: ${err.message}`;
    box.hidden = false;
  }
}

/* ---------- import / export / clear ---------- */

async function exportCsv() {
  const res = await fetch("/api/export/csv");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "applytrack.csv"; a.click();
  URL.revokeObjectURL(url);
}

async function importCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/import/csv", { method: "POST", body: form });
  const result = await res.json();
  alert(`Import done: ${result.imported} imported, ${result.skipped} skipped.` +
    (result.errors?.length ? `\n${result.errors.slice(0, 5).join("\n")}` : ""));
  await refresh();
}

/* ---------- wiring ---------- */

$("addBtn").addEventListener("click", openAddModal);
$("cancelBtn").addEventListener("click", () => { $("appModal").hidden = true; });
$("appForm").addEventListener("submit", saveApp);
$("appModal").addEventListener("click", (e) => { if (e.target === $("appModal")) $("appModal").hidden = true; });
$("outreachCloseBtn").addEventListener("click", () => { $("outreachModal").hidden = true; });
$("outreachModal").addEventListener("click", (e) => { if (e.target === $("outreachModal")) $("outreachModal").hidden = true; });
$("outreachForm").addEventListener("submit", saveOutreach);
$("exportBtn").addEventListener("click", exportCsv);
$("importInput").addEventListener("change", (e) => {
  if (e.target.files[0]) importCsv(e.target.files[0]);
  e.target.value = "";
});
$("clearBtn").addEventListener("click", async () => {
  if (!confirm("Delete ALL applications and outreach history? This cannot be undone.")) return;
  await api("/api/applications", { method: "DELETE" });
  await refresh();
});
["searchInput", "statusFilter", "termFilter", "sortSelect"].forEach((id) => {
  const el = $(id);
  el.addEventListener(id === "searchInput" ? "input" : "change", () => {
    if (id === "statusFilter") activeStatus = el.value;
    loadApps();
  });
});

refresh().then(() => {
  // Show the sample-data banner only when the seeded companies are present.
  const seeded = ["Texas Instruments", "Firefly Aerospace"];
  if (allApps.some((a) => seeded.includes(a.company))) $("sampleBanner").hidden = false;
}).catch((err) => {
  $("appsBody").innerHTML = `<tr><td colspan="9" class="error">Failed to load: ${esc(err.message)}</td></tr>`;
});
