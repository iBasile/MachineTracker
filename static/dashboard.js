const socket = io();
const $ = id => document.getElementById(id);
function showScan(data) {
  $("empty").hidden = true; $("scan").hidden = false;
  $("scan-name").textContent = data.habit?.nom || `Tag inconnu (${data.epc})`;
  $("scan-meta").textContent = data.habit ? `${data.habit.type} · ${data.habit.couleur} · lavage à ${data.habit.temperature} °C` : "En attente d’enregistrement";
}
function renderHistory(items) { $("history").innerHTML = items.map(item => `<div class="history-row"><span>${item.nom || item.epc}</span><span class="muted">${new Date(item.detected_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span></div>`).join("") || '<p class="muted">Aucune détection.</p>'; }
function renderSuggestions(items) {
  $("suggestions").innerHTML = items.length ? items.map(item => `
    <article class="suggestion">
      <strong>${item.count} article${item.count > 1 ? "s" : ""} · ${item.temperature} °C · ${item.matiere}</strong>
      <span>${item.couleur}</span>
      ${item.instructions.length ? `<small>⚠ ${item.instructions.join(" · ")}</small>` : ""}
      <small>${item.habits.map(h => h.nom).join(", ")}</small>
    </article>`).join("") : '<p class="muted">Le panier est vide.</p>';
}
async function load() { const state = await (await fetch("/api/state")).json(); $("total").textContent = state.total; $("present").textContent = state.present; renderHistory(state.history); renderSuggestions(state.suggestions); }
socket.on("connect", () => { $("connection").textContent = "Connecté"; $("dot").classList.add("on"); });
socket.on("disconnect", () => { $("connection").textContent = "Déconnecté"; $("dot").classList.remove("on"); });
socket.on("scan", showScan); socket.on("habit_updated", load); socket.on("habit_deleted", load); socket.on("basket_updated", load);
$("empty-basket").onclick = async () => { if (confirm("Marquer tous les habits comme retirés du panier ?")) { await fetch("/api/laundry/empty", {method: "POST"}); load(); } };
load();
