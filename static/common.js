// Cod comun pentru toate paginile
const STATE_LABEL = {
  WAITING: "Așteptat",
  ON_BUS: "În autobuz",
  AT_AFTERSCHOOL: "La afterschool",
  LEFT: "Plecat acasă",
};
const STATE_ICON = { WAITING: "🕐", ON_BUS: "🚌", AT_AFTERSCHOOL: "🏫", LEFT: "🏠" };
const EVENT_LABEL = {
  BUS_BOARD: "A urcat în autobuz",
  AFTERSCHOOL_ARRIVE: "A ajuns la afterschool",
  DEPARTURE: "A plecat de la afterschool",
};
const ROLE_PAGE = { parent: "/parinte", driver: "/sofer", teacher: "/profesor" };
const ROLE_LABEL = { parent: "părinte", driver: "șofer", teacher: "profesor" };

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Eroare ${res.status}`);
  return data;
}

let toastTimer;
function toast(msg, kind = "ok") {
  const el = $("toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), kind === "ok" ? 3000 : 6000);
}

function confBadge(c) {
  if (c === "confirmed") return '<span class="badge b-confirmed">Confirmat</span>';
  if (c === "declined") return '<span class="badge b-declined">Nu vine</span>';
  return '<span class="badge b-none">Neconfirmat</span>';
}
const stateBadge = (s) => `<span class="badge s-${s}">${STATE_LABEL[s]}</span>`;

// "Login" simulat: utilizatorul ales e tinut in localStorage (prototip, fara parola)
function savedUserId() {
  try { return localStorage.getItem("userId"); } catch { return null; }
}
function saveUserId(id) {
  try { localStorage.setItem("userId", id); } catch {}
}

const ROLE_TITLE = { parent: "Părinte", driver: "Șofer", teacher: "Profesor" };
const ROLE_ICON = { parent: "👪", driver: "🚌", teacher: "🏫" };
const pageFor = (u) => `${ROLE_PAGE[u.role]}?u=${encodeURIComponent(u.id)}`;

// Verifica utilizatorul curent. role = rolul cerut de pagina (null = orice rol).
// Rol gresit -> ecran "Acces interzis" (pagina nu se incarca deloc).
async function requireUser(role) {
  const users = await api("/api/users");
  const id = new URLSearchParams(location.search).get("u") || savedUserId();
  const user = users.find((u) => u.id === id);
  if (!user) { location.href = "/"; return null; }
  saveUserId(user.id);
  if (role && user.role !== role) { showForbidden(user, role, users); return null; }
  mountRoleSwitcher(user, users);
  return user;
}

function showForbidden(user, role, users) {
  document.body.innerHTML = `
    <div class="forbidden"><div class="forbidden-card">
      <div class="big">⛔</div><h1>Acces interzis</h1>
      <p>Ești conectat ca <b>${esc(user.name)}</b> (${ROLE_LABEL[user.role]}).</p>
      <p>Pagina aceasta e doar pentru rolul <b>${ROLE_LABEL[role]}</b>.</p>
      <div class="actions">
        <a class="btn" href="${pageFor(user)}">Mergi la pagina mea</a>
        <span id="roleSwitch"></span>
      </div>
    </div></div>`;
  mountRoleSwitcher(user, users);
}

// Butonul "Rolul meu" din bara de sus: alegi alt utilizator -> se deschide doar pagina rolului lui
function mountRoleSwitcher(me, users) {
  const host = $("roleSwitch");
  if (!host) return;
  host.innerHTML = `<button class="role-btn" type="button" title="Schimbă rolul">
      ${ROLE_ICON[me.role]} ${esc(me.name)} · <b>${ROLE_LABEL[me.role]}</b> ▾</button>`;
  host.querySelector("button").onclick = () => openRoleModal(me, users);
}

function openRoleModal(me, users) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-label="Alege rolul">
      <div class="row-between"><h2>Alege rolul</h2><button class="secondary small" data-close>✕</button></div>
      <p class="muted">Se deschide doar pagina rolului ales. Prototip: fără parolă.</p>
      ${["parent", "driver", "teacher"].map((role) => `
        <div class="modal-group">${ROLE_ICON[role]} ${ROLE_TITLE[role]}</div>
        ${users.filter((u) => u.role === role).map((u) => `
          <button class="modal-user ${u.id === me.id ? "current" : ""}" data-id="${esc(u.id)}">
            ${esc(u.name)}${u.id === me.id ? ' <span class="badge b-confirmed">acum</span>' : ""}
          </button>`).join("")}`).join("")}
           <div class="modal-footer">
        <a href="/permisiuni?u=${encodeURIComponent(me.id)}">🔐 Testează permisiunile rolului curent</a>
        <button class="secondary small" type="button" data-reset>↺ Reset date demo</button>
      </div>
    </div>`;
  const close = () => overlay.remove();
  overlay.onclick = (e) => { if (e.target === overlay || e.target.hasAttribute("data-close")) close(); };
  overlay.querySelectorAll(".modal-user").forEach((b) => b.onclick = () => {
    const u = users.find((x) => x.id === b.dataset.id);
    saveUserId(u.id);
    location.href = location.pathname === "/permisiuni" ? `/permisiuni?u=${encodeURIComponent(u.id)}` : pageFor(u);
  });
   overlay.querySelector("[data-reset]").onclick = resetDemoData;
  document.body.appendChild(overlay);
}

// Reface datele de test (seed)
async function resetDemoData() {
  if (!confirm("Refaci datele de test?\n\nSe șterg toate confirmările și scanările și se pun înapoi datele inițiale.")) return;
  const res = await fetch("/api/dev/reset", { method: "POST" });
  if (res.status === 404) { alert("Reset-ul e dezactivat pe acest server (ENABLE_DEV_RESET=0)."); return; }
  if (!res.ok) { alert(`Reset-ul a eșuat (cod ${res.status}).`); return; }
  try { sessionStorage.setItem("resetDone", "1"); } catch {}
  location.reload();
}

// dupa reincarcare: mesaj ca reset-ul a reusit
document.addEventListener("DOMContentLoaded", () => {
  let done = null;
  try { done = sessionStorage.getItem("resetDone"); sessionStorage.removeItem("resetDone"); } catch {}
  if (done && $("toast")) toast("✔ Datele de test au fost refăcute");
});

function startPolling(fn, ms = 5000) {
  fn();
  setInterval(() => { if (!document.hidden) fn(); }, ms);
}
