const { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } = window.APP_CONFIG;
const client = supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);

let allEvents = [];
let prefs = new Map();
let currentTab = "visible";
let currentUser = null;

const el = id =>
  document.getElementById(id);


/* ======================================================
   OUTILS
   ====================================================== */

function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function eventDate(ev) {
  return new Date(ev.start);
}

function eventDates(ev) {
  if (
    Array.isArray(ev.sessions) &&
    ev.sessions.length
  ) {
    return ev.sessions
      .map(value => new Date(value))
      .filter(
        date =>
          !Number.isNaN(
            date.getTime()
          )
      );
  }

  const date =
    new Date(ev.start);

  return Number.isNaN(
    date.getTime()
  )
    ? []
    : [date];
}

function formatDate(iso) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }
  ).format(
    new Date(iso)
  );
}

function formatShortDate(iso) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      day: "numeric",
      month: "short"
    }
  ).format(
    new Date(iso)
  );
}

function formatEventTiming(ev) {
  const sessions =
    Array.isArray(ev.sessions)
      ? ev.sessions
      : [];

  if (sessions.length === 0) {
    return formatDate(
      ev.start
    );
  }

  if (sessions.length === 1) {
    return formatDate(
      sessions[0]
    );
  }

  const sorted =
    [...sessions].sort(
      (a, b) =>
        new Date(a) -
        new Date(b)
    );

  const first =
    sorted[0];

  const last =
    sorted[
      sorted.length - 1
    ];

  return (
    `${sorted.length} séances · ` +
    `du ${formatShortDate(first)} ` +
    `au ${formatShortDate(last)}`
  );
}


/* ======================================================
   MÉDIATHÈQUES
   ====================================================== */

function isMediathequeEvent(ev) {
  const text =
    normalize(
      [
        ev.source,
        ev.venue
      ].join(" ")
    );

  return text.includes(
    "mediathe"
  );
}


/* ======================================================
   PÉRIODE
   ====================================================== */

function selectedPeriodDays() {
  if (
    el("period7")?.checked
  ) {
    return 7;
  }

  if (
    el("period30")?.checked
  ) {
    return 30;
  }

  return null;
}

function matchesSelectedPeriod(ev) {
  const days =
    selectedPeriodDays();

  if (!days) {
    return true;
  }

  const dates =
    eventDates(ev);

  if (!dates.length) {
    return false;
  }

  const start =
    new Date();

  start.setHours(
    0,
    0,
    0,
    0
  );

  const end =
    new Date(start);

  end.setDate(
    end.getDate() + days
  );

  return dates.some(
    date =>
      date >= start &&
      date < end
  );
}

function setupPeriodCheckboxes() {
  const period7 =
    el("period7");

  const period30 =
    el("period30");

  period7?.addEventListener(
    "change",
    () => {
      if (
        period7.checked &&
        period30
      ) {
        period30.checked =
          false;
      }

      render();
    }
  );

  period30?.addEventListener(
    "change",
    () => {
      if (
        period30.checked &&
        period7
      ) {
        period7.checked =
          false;
      }

      render();
    }
  );
}


/* ======================================================
   ÉVÉNEMENTS FUTURS
   ====================================================== */

function hasFutureSession(ev) {
  const limit =
    new Date(
      Date.now() -
      24 * 3600 * 1000
    );

  return eventDates(ev)
    .some(
      date =>
        date >= limit
    );
}


/* ======================================================
   PRÉFÉRENCES
   ====================================================== */

function getPref(id) {
  return prefs.get(id) || {
    hidden: false,
    favorite: false,
    reserved: false
  };
}


/* ======================================================
   FILTRE CATÉGORIES
   ====================================================== */

function selectedValues(
  containerId
) {
  return new Set(
    [
      ...document.querySelectorAll(
        `#${containerId} input[type="checkbox"]:checked`
      )
    ].map(
      input =>
        input.value
    )
  );
}

function buildCheckboxes(
  containerId,
  values
) {
  const container =
    el(containerId);

  if (!container) {
    return;
  }

  container.innerHTML = "";

  [
    ...new Set(
      values.filter(Boolean)
    )
  ]
    .sort(
      (a, b) =>
        a.localeCompare(
          b,
          "fr"
        )
    )
    .forEach(value => {
      const label =
        document.createElement(
          "label"
        );

      label.className =
        "filter-check";

      const input =
        document.createElement(
          "input"
        );

      input.type =
        "checkbox";

      input.value =
        value;

      input.addEventListener(
        "change",
        render
      );

      const text =
        document.createElement(
          "span"
        );

      text.textContent =
        value;

      label.appendChild(
        input
      );

      label.appendChild(
        text
      );

      container.appendChild(
        label
      );
    });
}


/* ======================================================
   CHARGEMENT DES ÉVÉNEMENTS
   ====================================================== */

async function loadEvents() {
  const response =
    await fetch(
      "events.json",
      {
        cache: "no-store"
      }
    );

  if (!response.ok) {
    throw new Error(
      "Impossible de charger events.json"
    );
  }

  allEvents =
    (await response.json())
      .filter(
        ev =>
          ev.start &&
          !isMediathequeEvent(ev)
      )
      .sort(
        (a, b) =>
          eventDate(a) -
          eventDate(b)
      );

  buildCheckboxes(
    "categoryFilters",
    allEvents.map(
      event =>
        event.category
    )
  );
}


/* ======================================================
   CONNEXION
   ====================================================== */

async function loadSession() {
  const { data } =
    await client.auth
      .getSession();

  currentUser =
    data.session?.user ||
    null;

  updateLoginButton();

  client.auth
    .onAuthStateChange(
      async (
        _event,
        session
      ) => {
        currentUser =
          session?.user ||
          null;

        updateLoginButton();

        await loadPrefs();

        render();
      }
    );
}

async function loadPrefs() {
  prefs =
    new Map();

  if (!currentUser) {
    const local =
      JSON.parse(
        localStorage.getItem(
          "agenda-loire-prefs"
        ) || "{}"
      );

    Object.entries(local)
      .forEach(
        ([key, value]) => {
          prefs.set(
            key,
            {
              hidden:
                !!value.hidden,

              favorite:
                !!value.favorite,

              reserved:
                !!value.reserved
            }
          );
        }
      );

    return;
  }

  const {
    data,
    error
  } =
    await client
      .from(
        "event_preferences"
      )
      .select(
        "event_id, hidden, favorite, reserved"
      )
      .eq(
        "user_id",
        currentUser.id
      );

  if (error) {
    console.error(
      error
    );

    el("status").textContent =
      "Erreur de synchronisation Supabase.";

    return;
  }

  (data || [])
    .forEach(row => {
      prefs.set(
        row.event_id,
        {
          hidden:
            !!row.hidden,

          favorite:
            !!row.favorite,

          reserved:
            !!row.reserved
        }
      );
    });
}

async function savePref(
  eventId,
  patch
) {
  const current = {
    ...getPref(eventId),
    ...patch
  };

  prefs.set(
    eventId,
    current
  );

  if (!currentUser) {
    localStorage.setItem(
      "agenda-loire-prefs",
      JSON.stringify(
        Object.fromEntries(
          prefs.entries()
        )
      )
    );

    render();
    return;
  }

  const { error } =
    await client
      .from(
        "event_preferences"
      )
      .upsert(
        {
          user_id:
            currentUser.id,

          event_id:
            eventId,

          hidden:
            !!current.hidden,

          favorite:
            !!current.favorite,

          reserved:
            !!current.reserved,

          updated_at:
            new Date()
              .toISOString()
        },
        {
          onConflict:
            "user_id,event_id"
        }
      );

  if (error) {
    console.error(
      error
    );

    el("status").textContent =
      "Impossible d’enregistrer la préférence.";
  }

  render();
}


/* ======================================================
   AFFICHAGE
   ====================================================== */

function themeClass(category) {
  return (
    "theme-" +
    normalize(
      category ||
      "culture"
    ).replace(
      /\s+/g,
      "-"
    )
  );
}

function render() {
  const q =
    normalize(
      el("search")
        .value
    );

  const selectedCategories =
    selectedValues(
      "categoryFilters"
    );

  const filtered =
    allEvents.filter(
      ev => {
        const p =
          getPref(ev.id);

        if (
          !hasFutureSession(ev)
        ) {
          return false;
        }

        if (
          currentTab ===
            "visible" &&
          p.hidden
        ) {
          return false;
        }

        if (
          currentTab ===
            "favorites" &&
          !p.favorite
        ) {
          return false;
        }

        if (
          currentTab ===
            "reserved" &&
          !p.reserved
        ) {
          return false;
        }

        if (
          currentTab ===
            "hidden" &&
          !p.hidden
        ) {
          return false;
        }

        if (
          selectedCategories
            .size > 0 &&
          !selectedCategories
            .has(
              ev.category
            )
        ) {
          return false;
        }

        if (
          !matchesSelectedPeriod(
            ev
          )
        ) {
          return false;
        }

        const haystack =
          normalize(
            [
              ev.title,
              ev.venue,
              ev.city,
              ev.description,
              ev.category,
              ev.source
            ].join(" ")
          );

        if (
          q &&
          !haystack.includes(q)
        ) {
          return false;
        }

        return true;
      }
    );

  el("status")
    .textContent =
      `${filtered.length} événement${
        filtered.length > 1
          ? "s"
          : ""
      }` +
      (
        currentUser
          ? " · synchronisé avec Supabase"
          : " · mode local (connecte-toi pour synchroniser)"
      );

  const container =
    el("events");

  container.innerHTML =
    "";

  if (
    !filtered.length
  ) {
    container.innerHTML =
      `<div class="card">Aucun événement pour ces filtres.</div>`;

    return;
  }

  for (
    const ev
    of filtered
  ) {
    const p =
      getPref(ev.id);

    const card =
      document.createElement(
        "article"
      );

    card.className =
      "card";

    card.innerHTML = `
      <div class="event-row">
        <div class="event-content">
          <span class="theme-badge ${themeClass(ev.category)}">
            ${escapeHtml(ev.category || "Culture")}
          </span>

          <span class="event-title">
            ${escapeHtml(ev.title)}
          </span>

          <span class="event-separator">·</span>

          <span class="event-meta">
            ${escapeHtml(formatEventTiming(ev))}
          </span>

          <span class="event-separator">·</span>

          <span class="event-meta">
            ${escapeHtml(ev.venue || "")}
            ${ev.city ? " · " + escapeHtml(ev.city) : ""}
          </span>
        </div>

        <div class="actions">
          ${
            ev.url
              ? `<a
                   href="${escapeAttr(ev.url)}"
                   target="_blank"
                   rel="noopener"
                 >Source</a>`
              : ""
          }

          <button
            data-action="favorite"
            data-id="${escapeAttr(ev.id)}"
          >
            ${p.favorite ? "★ Favori" : "☆ Favori"}
          </button>

          <button
            data-action="reserved"
            data-id="${escapeAttr(ev.id)}"
          >
            ${p.reserved ? "✓ Réservé" : "○ Réservé"}
          </button>

          <button
            data-action="hidden"
            data-id="${escapeAttr(ev.id)}"
          >
            ${p.hidden ? "Réafficher" : "Masquer"}
          </button>
        </div>
      </div>
    `;

    container.appendChild(
      card
    );
  }
}


/* ======================================================
   ÉCHAPPEMENT
   ====================================================== */

function escapeHtml(value) {
  return String(
    value || ""
  ).replace(
    /[&<>"']/g,
    char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[char])
  );
}

function escapeAttr(value) {
  return escapeHtml(
    value
  );
}


/* ======================================================
   ACTIONS
   ====================================================== */

function updateLoginButton() {
  el("loginBtn")
    .textContent =
      currentUser
        ? "Déconnexion"
        : "Connexion";
}

el("events")
  .addEventListener(
    "click",
    event => {
      const button =
        event.target.closest(
          "button[data-action]"
        );

      if (!button) {
        return;
      }

      const id =
        button.dataset.id;

      const p =
        getPref(id);

      if (
        button.dataset.action ===
        "favorite"
      ) {
        savePref(
          id,
          {
            favorite:
              !p.favorite
          }
        );
      }

      if (
        button.dataset.action ===
        "reserved"
      ) {
        savePref(
          id,
          {
            reserved:
              !p.reserved
          }
        );
      }

      if (
        button.dataset.action ===
        "hidden"
      ) {
        savePref(
          id,
          {
            hidden:
              !p.hidden
          }
        );
      }
    }
  );

el("search")
  .addEventListener(
    "input",
    render
  );

setupPeriodCheckboxes();

document
  .querySelectorAll(
    ".filter-clear"
  )
  .forEach(button => {
    button.addEventListener(
      "click",
      () => {
        const container =
          el(
            button.dataset.clear
          );

        container
          .querySelectorAll(
            'input[type="checkbox"]'
          )
          .forEach(
            input => {
              input.checked =
                false;
            }
          );

        render();
      }
    );
  });

document
  .querySelectorAll(
    ".tab"
  )
  .forEach(button => {
    button.addEventListener(
      "click",
      () => {
        document
          .querySelectorAll(
            ".tab"
          )
          .forEach(
            tab =>
              tab.classList
                .remove(
                  "active"
                )
          );

        button.classList
          .add(
            "active"
          );

        currentTab =
          button.dataset.tab;

        render();
      }
    );
  });

el("loginBtn")
  .addEventListener(
    "click",
    async () => {
      if (
        currentUser
      ) {
        await client.auth
          .signOut();

        return;
      }

      el("loginDialog")
        .showModal();
    }
  );

el("sendMagicLink")
  .addEventListener(
    "click",
    async event => {
      event.preventDefault();

      const email =
        el("email")
          .value
          .trim();

      if (!email) {
        return;
      }

      el("loginMessage")
        .textContent =
          "Envoi…";

      const { error } =
        await client.auth
          .signInWithOtp(
            {
              email,
              options: {
                emailRedirectTo:
                  window.location
                    .href
              }
            }
          );

      el("loginMessage")
        .textContent =
          error
            ? "Erreur : " +
              error.message
            : "Lien envoyé. Vérifie ta boîte mail.";
    }
  );


/* ======================================================
   INITIALISATION
   ====================================================== */

(async function init() {
  try {
    await loadSession();
    await loadPrefs();
    await loadEvents();

    render();

  } catch (error) {
    console.error(
      error
    );

    el("status")
      .textContent =
        "Erreur au chargement : " +
        error.message;
  }
})();
