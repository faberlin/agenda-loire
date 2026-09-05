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

function formatShortDate(iso) {
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short"
  }).format(new Date(iso));
}

function formatEventTiming(ev) {
  const sessions = Number(ev.sessions || 1);

  if (sessions <= 1 || !ev.end) {
    return formatDate(ev.start);
  }

  const start = new Date(ev.start);
  const end = new Date(ev.end);

  if (isSameLocalDate(start, end)) {
    return `${sessions} séances · ${formatShortDate(ev.start)}`;
  }

  return `${sessions} séances · du ${formatShortDate(ev.start)} au ${formatShortDate(ev.end)}`;
}

function getPref(id) {
  return prefs.get(id) || { hidden: false, favorite: false, reserved: false };
}

function selectedValues(containerId) {
  return new Set(
    [...document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`)]
      .map(input => input.value)
  );
}

function buildCheckboxes(containerId, values) {
  const container = el(containerId);
  container.innerHTML = "";

  [...new Set(values.filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "fr"))
    .forEach(value => {
      const label = document.createElement("label");
      label.className = "filter-check";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.addEventListener("change", render);

      const text = document.createElement("span");
      text.textContent = value;

      label.appendChild(input);
      label.appendChild(text);
      container.appendChild(label);
    });
}

async function loadEvents() {
  const res = await fetch("events.json", { cache: "no-store" });
  if (!res.ok) throw new Error("Impossible de charger events.json");

  allEvents = (await res.json())
    .filter(ev => ev.start)
    .sort((a, b) => eventDate(a) - eventDate(b));

  buildCheckboxes("categoryFilters", allEvents.map(e => e.category));
  buildCheckboxes("venueFilters", allEvents.map(e => e.venue));
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
    Object.entries(local).forEach(([k, v]) => prefs.set(k, {
      hidden: !!v.hidden,
      favorite: !!v.favorite,
      reserved: !!v.reserved
    }));
    return;
  }

  const { data, error } = await client
    .from("event_preferences")
    .select("event_id, hidden, favorite, reserved")
    .eq("user_id", currentUser.id);

  if (error) {
    console.error(error);
    el("status").textContent = "Erreur de synchronisation Supabase.";
    return;
  }

  (data || []).forEach(row => prefs.set(row.event_id, {
    hidden: !!row.hidden,
    favorite: !!row.favorite,
    reserved: !!row.reserved
  }));
}

async function savePref(eventId, patch) {
  const current = { ...getPref(eventId), ...patch };
  prefs.set(eventId, current);

  if (!currentUser) {
    localStorage.setItem(
      "agenda-loire-prefs",
      JSON.stringify(Object.fromEntries(prefs.entries()))
    );
    render();
    return;
  }

  const { error } = await client
    .from("event_preferences")
    .upsert({
      user_id: currentUser.id,
      event_id: eventId,
      hidden: !!current.hidden,
      favorite: !!current.favorite,
      reserved: !!current.reserved,
      updated_at: new Date().toISOString()
    }, { onConflict: "user_id,event_id" });

  if (error) {
    console.error(error);
    el("status").textContent = "Impossible d’enregistrer la préférence.";
  }

  render();
}

function themeClass(category) {
  return "theme-" + normalize(category || "culture").replace(/\s+/g, "-");
}

function render() {
  const q = normalize(el("search").value);
  const period = el("period").value;
  const selectedCategories = selectedValues("categoryFilters");
  const selectedVenues = selectedValues("venueFilters");
  const now = new Date();

  const filtered = allEvents.filter(ev => {
    const p = getPref(ev.id);

    if (eventDate(ev) < new Date(now.getTime() - 24 * 3600 * 1000)) return false;

    if (currentTab === "visible" && p.hidden) return false;
    if (currentTab === "favorites" && !p.favorite) return false;
    if (currentTab === "reserved" && !p.reserved) return false;
    if (currentTab === "hidden" && !p.hidden) return false;

    if (selectedCategories.size > 0 && !selectedCategories.has(ev.category)) return false;
    if (selectedVenues.size > 0 && !selectedVenues.has(ev.venue)) return false;
    if (!matchesPeriod(ev, period)) return false;

    const haystack = normalize([
      ev.title, ev.venue, ev.city, ev.description, ev.category
    ].join(" "));

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
      <div class="event-row">
        <div class="event-content">
          <span class="theme-badge ${themeClass(ev.category)}">
            ${escapeHtml(ev.category || "Culture")}
          </span>

          <span class="event-title">${escapeHtml(ev.title)}</span>
          <span class="event-separator">·</span>
          <span class="event-meta">${escapeHtml(formatEventTiming(ev))}</span>
          <span class="event-separator">·</span>

          <span class="event-meta">
            ${escapeHtml(ev.venue || "")}${ev.city ? " · " + escapeHtml(ev.city) : ""}
          </span>
        </div>

        <div class="actions">
          ${ev.url ? `<a href="${escapeAttr(ev.url)}" target="_blank" rel="noopener">Source</a>` : ""}
          <button data-action="favorite" data-id="${escapeAttr(ev.id)}">
            ${p.favorite ? "★ Favori" : "☆ Favori"}
          </button>
          <button data-action="reserved" data-id="${escapeAttr(ev.id)}">
            ${p.reserved ? "✓ Réservé" : "○ Réservé"}
          </button>
          <button data-action="hidden" data-id="${escapeAttr(ev.id)}">
            ${p.hidden ? "Réafficher" : "Masquer"}
          </button>
        </div>
      </div>
    `;

    container.appendChild(card);
  }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
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
  if (btn.dataset.action === "reserved") savePref(id, { reserved: !p.reserved });
  if (btn.dataset.action === "hidden") savePref(id, { hidden: !p.hidden });
});

el("search").addEventListener("input", render);
el("period").addEventListener("change", render);

document.querySelectorAll(".filter-clear").forEach(btn => {
  btn.addEventListener("click", () => {
    const container = el(btn.dataset.clear);
    container.querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.checked = false;
    });
    render();
  });
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
