const { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } = window.APP_CONFIG;
const client = supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

let allEvents = [];
let prefs = new Map();
let currentTab = "visible";
let currentUser = null;

const el = id => document.getElementById(id);

function normalize(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function eventDate(ev) {
  return new Date(ev.start);
}

function isSameLocalDate(a, b) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function matchesPeriod(ev, period) {
  if (period === "all") return true;
  const now = new Date();
  const d = eventDate(ev);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (period === "today") return isSameLocalDate(d, now);

  if (period === "week" || period === "month") {
    const days = period === "week" ? 7 : 30;
    const end = new Date(todayStart);
    end.setDate(end.getDate() + days);
    return d >= todayStart && d < end;
  }

  if (period === "weekend") {
    const day = now.getDay();
    const daysToSaturday = (6 - day + 7) % 7;
    const saturday = new Date(todayStart);
    saturday.setDate(saturday.getDate() + daysToSaturday);
    const monday = new Date(saturday);
    monday.setDate(monday.getDate() + 2);
    return d >= saturday && d < monday;
  }

  return true;
}

function formatDate(iso) {
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(iso));
}

function getPref(id) {
  return prefs.get(id) || { hidden: false, favorite: false };
}

function populateSelect(id, values) {
  const select = el(id);
  const current = select.value;
  [...new Set(values.filter(Boolean))].sort((a,b) => a.localeCompare(b, "fr"))
    .forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
  select.value = current || "all";
}

async function loadEvents() {
  const res = await fetch("events.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Impossible de charger events.json");
  allEvents = (await res.json())
    .filter(ev => ev.start)
    .sort((a,b) => eventDate(a) - eventDate(b));

  populateSelect("category", allEvents.map(e => e.category));
  populateSelect("city", allEvents.map(e => e.city));
}

async function loadSession() {
  const { data } = await client.auth.getSession();
  currentUser = data.session?.user || null;
  updateLoginButton();

  client.auth.onAuthStateChange(async (_event, session) => {
    currentUser = session?.user || null;
    updateLoginButton();
    await loadPrefs();
    render();
  });
}

async function loadPrefs() {
  prefs = new Map();
  if (!currentUser) {
    const local = JSON.parse(localStorage.getItem("agenda-loire-prefs") || "{}");
    Object.entries(local).forEach(([k,v]) => prefs.set(k,v));
    return;
  }

  const { data, error } = await client
    .from("event_preferences")
    .select("event_id, hidden, favorite")
    .eq("user_id", currentUser.id);

  if (error) {
    console.error(error);
    el("status").textContent = "Erreur de synchronisation Supabase.";
    return;
  }

  (data || []).forEach(row => prefs.set(row.event_id, row));
}

async function savePref(eventId, patch) {
  const current = { ...getPref(eventId), ...patch };
  prefs.set(eventId, current);

  if (!currentUser) {
    const obj = Object.fromEntries(prefs.entries());
    localStorage.setItem("agenda-loire-prefs", JSON.stringify(obj));
    render();
    return;
  }

  const { error } = await client.from("event_preferences").upsert({
    user_id: currentUser.id,
    event_id: eventId,
    hidden: !!current.hidden,
    favorite: !!current.favorite,
    updated_at: new Date().toISOString()
  }, { onConflict: "user_id,event_id" });

  if (error) {
    console.error(error);
    el("status").textContent = "Impossible d’enregistrer la préférence.";
  }
  render();
}

function render() {
  const q = normalize(el("search").value);
  const category = el("category").value;
  const city = el("city").value;
  const period = el("period").value;
  const now = new Date();

  const filtered = allEvents.filter(ev => {
    const p = getPref(ev.id);
    if (eventDate(ev) < new Date(now.getTime() - 24*3600*1000)) return false;
    if (currentTab === "visible" && p.hidden) return false;
    if (currentTab === "hidden" && !p.hidden) return false;
    if (currentTab === "favorites" && !p.favorite) return false;
    if (category !== "all" && ev.category !== category) return false;
    if (city !== "all" && ev.city !== city) return false;
    if (!matchesPeriod(ev, period)) return false;

    const haystack = normalize([ev.title, ev.venue, ev.city, ev.description, ev.category].join(" "));
    if (q && !haystack.includes(q)) return false;
    return true;
  });

  el("status").textContent =
    `${filtered.length} événement${filtered.length > 1 ? "s" : ""}` +
    (currentUser ? " · synchronisé avec Supabase" : " · mode local (connecte-toi pour synchroniser)");

  const container = el("events");
  container.innerHTML = "";

  if (!filtered.length) {
    container.innerHTML = `<div class="card">Aucun événement pour ces filtres.</div>`;
    return;
  }

  for (const ev of filtered) {
    const p = getPref(ev.id);
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <div class="card-top">
        <div>
          <h3>${escapeHtml(ev.title)}</h3>
          <div class="meta">${formatDate(ev.start)} · ${escapeHtml(ev.venue || "")}${ev.city ? " · " + escapeHtml(ev.city) : ""}</div>
        </div>
        <span class="badge">${escapeHtml(ev.category || "Culture")}</span>
      </div>
      ${ev.description ? `<div class="description">${escapeHtml(ev.description)}</div>` : ""}
      <div class="actions">
        ${ev.url ? `<a href="${escapeAttr(ev.url)}" target="_blank" rel="noopener">Voir la source</a>` : ""}
        <button data-action="favorite" data-id="${escapeAttr(ev.id)}">${p.favorite ? "★ Retirer favori" : "☆ Favori"}</button>
        <button data-action="hidden" data-id="${escapeAttr(ev.id)}">${p.hidden ? "Réafficher" : "Masquer"}</button>
      </div>
    `;
    container.appendChild(card);
  }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
  }[c]));
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function updateLoginButton() {
  el("loginBtn").textContent = currentUser ? "Déconnexion" : "Connexion";
}

el("events").addEventListener("click", e => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = btn.dataset.id;
  const p = getPref(id);
  if (btn.dataset.action === "favorite") savePref(id, { favorite: !p.favorite });
  if (btn.dataset.action === "hidden") savePref(id, { hidden: !p.hidden });
});

["search","period","category","city"].forEach(id => {
  el(id).addEventListener("input", render);
  el(id).addEventListener("change", render);
});

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    currentTab = btn.dataset.tab;
    render();
  });
});

el("loginBtn").addEventListener("click", async () => {
  if (currentUser) {
    await client.auth.signOut();
    return;
  }
  el("loginDialog").showModal();
});

el("sendMagicLink").addEventListener("click", async e => {
  e.preventDefault();
  const email = el("email").value.trim();
  if (!email) return;
  el("loginMessage").textContent = "Envoi…";
  const { error } = await client.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.href }
  });
  el("loginMessage").textContent = error
    ? "Erreur : " + error.message
    : "Lien envoyé. Vérifie ta boîte mail.";
});

(async function init() {
  try {
    await loadSession();
    await loadPrefs();
    await loadEvents();
    render();
  } catch (err) {
    console.error(err);
    el("status").textContent = "Erreur au chargement : " + err.message;
  }
})();
