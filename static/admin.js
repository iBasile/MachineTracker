const $ = id => document.getElementById(id);
let habits = [];
const fields = ["epc","nom","type","couleur","temperature","matiere","proprietaire","date_dernier_lavage","instructions"];

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {"Content-Type": "application/json"}, ...options});
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body?.error || "Une erreur est survenue.");
  return body;
}
function render() {
  $("count").textContent = `${habits.length} habit${habits.length > 1 ? "s" : ""}`;
  $("habit-list").innerHTML = habits.length ? habits.map(h => `
    <div class="habit-row"><div class="details"><strong>${escapeHtml(h.nom)}</strong>
      <small>${escapeHtml(h.type)} · ${escapeHtml(h.couleur)} · ${h.temperature} °C · ${escapeHtml(h.proprietaire)}</small>
      ${h.present ? '<div class="present">Détecté récemment</div>' : ""}</div>
      <button onclick="editHabit(${h.id})">Modifier</button><button onclick="removeHabit(${h.id})">Supprimer</button></div>`).join("") :
      '<p class="muted">Aucun habit enregistré.</p>';
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c])); }
async function load() { habits = await api("/api/habits"); render(); }
window.editHabit = id => { const h = habits.find(item => item.id === id); $("habit-id").value = h.id; fields.forEach(f => $(f).value = h[f] ?? ""); $("form-title").textContent = "Modifier un habit"; window.scrollTo({top: 0, behavior: "smooth"}); };
window.removeHabit = async id => { if (!confirm("Supprimer cet habit ?")) return; await api(`/api/habits/${id}`, {method:"DELETE"}); await load(); };
$("habit-form").onsubmit = async event => { event.preventDefault(); $("form-error").textContent = ""; const data = Object.fromEntries(fields.map(f => [f, $(f).value])); const id = $("habit-id").value; try { await api(id ? `/api/habits/${id}` : "/api/habits", {method: id ? "PUT" : "POST", body: JSON.stringify(data)}); reset(); await load(); } catch (error) { $("form-error").textContent = error.message; } };
function reset() { $("habit-form").reset(); $("habit-id").value = ""; $("form-title").textContent = "Ajouter un habit"; }
$("cancel").onclick = reset;
$("add-mode").onclick = async () => { const state = await api("/api/state"); const enabled = !state.add_mode; await api("/api/add-mode", {method:"POST",body:JSON.stringify({enabled})}); $("mode-message").hidden = !enabled; $("add-mode").textContent = enabled ? "Quitter le mode ajout" : "+ Ajout"; };
const socket = io();
socket.on("tag_detected", data => { $("epc").value = data.epc; $("mode-message").textContent = `Tag détecté : ${data.epc}. Complétez les informations.`; $("mode-message").hidden = false; });
load().catch(error => $("form-error").textContent = error.message);
