// PackSmart front-end: talks to the Flask JSON API and draws the page.
const $ = (id) => document.getElementById(id);
let state = { trip: {}, items: [], categories: [] };
let editingId = null;
let lastResult = null;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method, headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error((data.errors || ["Request failed."]).join("\n"));
  return data;
}

function showError(msg) {
  const box = $("errors");
  box.textContent = msg || "";
  box.hidden = !msg;
}

// Run an API call, refresh the page on success, show errors on failure.
async function act(fn) {
  try { showError(""); await fn(); } catch (e) { showError(e.message); }
}

function setState(s) {
  state = s;
  $("trip-name").value = s.trip.name || "";
  $("trip-limit").value = s.trip.limit ?? "";
  $("i-category").innerHTML = s.categories.map((c) => `<option>${esc(c)}</option>`).join("");
  renderItems();
}

function renderItems() {
  const total = state.items.reduce((a, i) => a + i.weight, 0);
  const ess = state.items.filter((i) => i.essential).reduce((a, i) => a + i.weight, 0);
  const limit = state.trip.limit;
  $("k-limit").textContent = limit ? `${limit} kg` : "–";
  $("k-items").textContent = state.items.length;
  $("k-weight").textContent = `${total.toFixed(2)} kg`;
  $("k-ess").textContent = `${ess.toFixed(2)} kg`;

  const sum = $("summary");
  sum.className = "hint";
  if (limit && ess > limit) {
    sum.textContent = `Essentials (${ess.toFixed(2)} kg) exceed the ${limit} kg limit. Raise the limit or unmark an essential.`;
    sum.className = "hint warn";
  } else if (limit && total <= limit) {
    sum.textContent = "Everything fits within the limit already.";
  } else if (limit) {
    sum.textContent = `${(total - limit).toFixed(2)} kg over the limit, so some items will be left behind.`;
  } else {
    sum.textContent = "Save a trip with a weight limit to get started.";
  }

  $("items-body").innerHTML = state.items.length
    ? state.items.map((i) => (i.id === editingId ? editRow(i) : viewRow(i))).join("")
    : `<tr><td colspan="6" class="hint">No items yet. Add one above or load the sample data.</td></tr>`;
}

const pill = (p) => `<span class="pill ${p >= 8 ? "hi" : p <= 3 ? "lo" : ""}">${p}</span>`;

// A normal, read-only table row.
function viewRow(i) {
  return `<tr><td><strong>${esc(i.name)}</strong></td><td class="num">${i.weight} kg</td>
    <td><span class="chip">${esc(i.category)}</span></td><td>${pill(i.priority)}</td>
    <td>${i.essential ? '<span class="tag">Essential</span>' : '<span class="hint">Optional</span>'}</td>
    <td class="num"><button class="btn" data-edit="${i.id}">Edit</button><button class="btn danger" data-del="${i.id}">Remove</button></td></tr>`;
}

// The same row turned into input fields, so the item is edited in place.
function editRow(i) {
  const options = state.categories.map((c) => `<option ${c === i.category ? "selected" : ""}>${esc(c)}</option>`).join("");
  return `<tr class="editing" data-row="${i.id}">
    <td><input data-f="name" value="${esc(i.name)}" maxlength="60" aria-label="Name"></td>
    <td class="num"><input data-f="weight" type="number" step="0.01" min="0.001" value="${i.weight}" aria-label="Weight in kg"></td>
    <td><select data-f="category" aria-label="Category">${options}</select></td>
    <td><input data-f="priority" type="number" min="1" max="10" step="1" value="${i.priority}" aria-label="Priority"></td>
    <td><label class="check"><input data-f="essential" type="checkbox" ${i.essential ? "checked" : ""}> Essential</label></td>
    <td class="num"><button class="btn primary" data-save="${i.id}">Save</button><button class="btn" data-cancel="1">Cancel</button></td></tr>`;
}

function saveRow(id) {
  const row = document.querySelector(`tr[data-row="${id}"]`);
  const f = (name) => row.querySelector(`[data-f="${name}"]`);
  const body = {
    name: f("name").value, weight: f("weight").value, category: f("category").value,
    priority: f("priority").value, essential: f("essential").checked,
  };
  act(async () => {
    setState(await api(`/api/items/${id}`, "PUT", body));  // setState re-draws the table
    editingId = null;
    renderItems();
  });
}

function cancelEdit() {
  editingId = null;
  showError("");
  renderItems();
}

// ---- trip + sample/clear buttons
$("trip-form").addEventListener("submit", (e) => {
  e.preventDefault();
  act(async () => setState(await api("/api/trip", "POST",
    { name: $("trip-name").value, limit: $("trip-limit").value })));
});
$("btn-sample").onclick = () => act(async () => { editingId = null; setState(await api("/api/sample", "POST")); resetItemForm(); $("results").hidden = true; });
$("btn-clear").onclick = () => {
  if (confirm("Remove the trip and all items?")) act(async () => { editingId = null; setState(await api("/api/clear", "POST")); resetItemForm(); $("results").hidden = true; });
};

// ---- add-item form (editing happens inside the table)
function resetItemForm() {
  $("item-form").reset();
  $("i-priority").value = 5;
}

$("item-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const body = {
    name: $("i-name").value, weight: $("i-weight").value, category: $("i-category").value,
    priority: $("i-priority").value, essential: $("i-essential").checked,
  };
  act(async () => { setState(await api("/api/items", "POST", body)); resetItemForm(); $("i-name").focus(); });
});

$("items-body").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  if (btn.dataset.edit) {
    showError("");
    editingId = Number(btn.dataset.edit);
    renderItems();
    document.querySelector('tr.editing [data-f="name"]').focus();
  } else if (btn.dataset.save) {
    saveRow(btn.dataset.save);
  } else if (btn.dataset.cancel) {
    cancelEdit();
  } else if (btn.dataset.del) {
    const id = Number(btn.dataset.del);
    act(async () => { if (editingId === id) editingId = null; setState(await api(`/api/items/${id}`, "DELETE")); });
  }
});

// Enter saves and Escape cancels while editing a row.
$("items-body").addEventListener("keydown", (e) => {
  const row = e.target.closest("tr.editing");
  if (!row) return;
  if (e.key === "Enter") { e.preventDefault(); saveRow(row.dataset.row); }
  if (e.key === "Escape") cancelEdit();
});

// ---- optimise and show results
$("btn-optimize").onclick = () => act(async () => {
  lastResult = await api("/api/optimize", "POST");
  renderResults(lastResult);
});

function listTable(rows, showEssential) {
  if (!rows.length) return "<p>None.</p>";
  return `<div class="scroll"><table><thead><tr><th>Item</th><th>Category</th><th class="num">kg</th><th>Priority</th><th>Why</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.name)} ${showEssential && r.essential ? '<span class="tag">Essential</span>' : ""}</td>
      <td><span class="chip">${esc(r.category)}</span></td><td class="num">${r.weight}</td><td><span class="pill">${r.priority}</span></td>
      <td class="reason">${esc(r.reason)}</td></tr>`).join("") + `</tbody></table></div>`;
}

function renderResults(data) {
  const b = data.backtracking;
  $("results").hidden = false;
  $("r-title").textContent = `Packing list: ${state.trip.name}`;
  if (!b.feasible) { $("r-body").innerHTML = `<div class="note">${esc(b.message)}</div>`; return; }

  const pct = Math.min(100, (b.total_weight / b.capacity) * 100);
  $("r-body").innerHTML = `
    <div class="result-card">
      <div class="gauge" title="${pct.toFixed(0)}% full"><span style="width:${pct}%"></span></div>
      <div class="stats">
        <div><strong>${b.total_weight} kg</strong><small>packed of ${b.capacity} kg</small></div>
        <div><strong>${b.remaining} kg</strong><small>capacity remaining</small></div>
        <div><strong>${b.score}/${b.max_score}</strong><small>priority score</small></div>
        <div><strong>${b.packed.length}/${b.packed.length + b.excluded.length}</strong><small>items packed</small></div>
      </div>
      ${b.message ? `<div class="note">${esc(b.message)}</div>` : ""}
      <div class="in"><h3>Pack these (${b.packed.length})</h3>${listTable(b.packed, true)}</div>
      <div class="out"><h3>Leave these behind (${b.excluded.length})</h3>${listTable(b.excluded, false)}</div>
    </div>
    <details class="no-print" open>
      <summary>How the solver reached this list</summary>
      <p class="note">The CSP fixed the essential items, then backtracking search examined ${b.stats.nodes.toLocaleString()} of
      ${b.stats.search_space.toLocaleString()} possible combinations and pruned ${b.stats.pruned.toLocaleString()} branches that could
      not beat the best list found. This list has the highest total priority that fits the limit.</p>
    </details>`;
  $("results").scrollIntoView({ behavior: "smooth" });
}

// ---- download and print
$("btn-print").onclick = () => window.print();
$("btn-download").onclick = () => {
  if (!lastResult) return;
  const b = lastResult.backtracking;
  const line = (r) => `  [${r.essential ? "E" : " "}] ${r.name} - ${r.weight} kg (priority ${r.priority}) - ${r.reason}`;
  const text = [
    `PACKSMART PACKING LIST: ${state.trip.name}`, "",
    `Total weight: ${b.total_weight} kg of ${b.capacity} kg (remaining ${b.remaining} kg)`,
    `Priority score: ${b.score}/${b.max_score}`, "", "PACK:", ...b.packed.map(line), "",
    "LEAVE BEHIND:", ...b.excluded.map(line), "", "[E] = essential",
  ].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  a.download = `packing-list-${state.trip.name.replace(/\W+/g, "-").toLowerCase()}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
};

act(async () => setState(await api("/api/state")));
