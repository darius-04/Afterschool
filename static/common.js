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

// Asigura ca pagina e deschisa de un utilizator cu rolul potrivit; altfel inapoi la alegere
async function requireUser(role) {
  const users = await api("/api/users");
  const id = new URLSearchParams(location.search).get("u") || savedUserId();
  const user = users.find((u) => u.id === id && u.role === role);
  if (!user) { location.href = "/"; return null; }
  saveUserId(user.id);
  return user;
}

function startPolling(fn, ms = 5000) {
  fn();
  setInterval(() => { if (!document.hidden) fn(); }, ms);
}
