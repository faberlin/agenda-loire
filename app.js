const { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } = window.APP_CONFIG;

const client = supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);

let allEvents = [];
let prefs = new Map();
let currentTab = "visible";

const el = id => document.getElementById(id);


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

  const date = new Date(ev.start);

  return Number.isNaN(
    date.getTime()
  )
    ? []
    : [date];
}

function futureDates(ev) {
  const now = new Date();

  return eventDates(ev)
    .filter(
      date =>
        date >= now
    )
    .sort(
      (a, b) =>
        a - b
    );
}

function hasFutureSession(ev) {
  return futureDates(ev).length > 0;
}


/* ======================================================
   DATE / AFFICHAGE
   ====================================================== */

function dayKey(date) {
  const y =
    date.getFullYear();

  const m =
    String(
      date.getMonth() + 1
    ).padStart(
      2,
      "0"
    );

  const d =
    String(
      date.getDate()
    ).padStart(
      2,
      "0"
    );

  return `${y}-${m}-${d}`;
}

function formatDay(date) {
  const today =
    new Date();

  today.setHours(
    0,
    0,
    0,
    0
  );

  const tomorrow =
    new Date(today);

  tomorrow.setDate(
    tomorrow.getDate() + 1
  );

  const current =
    new Date(date);

  current.setHours(
    0,
    0,
    0,
    0
  );

  const label =
    new Intl.DateTimeFormat(
      "fr-FR",
      {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
      }
    ).format(date);

  const capitalized =
    label.charAt(0).toUpperCase() +
    label.slice(1);

  if (
    current.getTime() ===
    today.getTime()
  ) {
    return (
      `Aujourd’hui · ${capitalized}`
    );
  }

  if (
    current.getTime() ===
    tomorrow.getTime()
  ) {
    return (
      `Demain · ${capitalized}`
    );
  }

  return capitalized;
}

function formatShortDate(date) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      day: "numeric",
      month: "short"
    }
  ).format(date);
}

function sessionsLabel(ev) {
  const dates =
    futureDates(ev);

  if (
    dates.length <= 1
  ) {
    return "";
  }

  const lastDate =
    dates[
      dates.length - 1
    ];

  return (
    `${dates.length} séances` +
    ` · jusqu'au ` +
    `${formatShortDate(lastDate)}`
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
    futureDates(ev);

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
    .forEach(
      value => {
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

        label.append(
          input,
          text
        );

        container.appendChild(
          label
        );
      }
    );
}


/* ======================================================
   CHARGEMENT ÉVÉNEMENTS
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
   SUPABASE
   ====================================================== */

async function loadPrefs() {
  prefs =
    new Map();

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
      );

  if (error) {
    console.error(
      error
    );

    throw new Error(
      "Impossible de charger les préférences Supabase."
    );
  }

  (data || []).forEach(
    row => {
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
    }
  );
}

async function savePref(
  eventId,
  patch
) {
  const previous = {
    ...getPref(eventId)
  };

  const current = {
    ...previous,
    ...patch
  };

  prefs.set(
    eventId,
    current
  );

  render();

  const {
    error
  } =
    await client
      .from(
        "event_preferences"
      )
      .upsert(
        {
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
            "event_id"
        }
      );

  if (error) {
    console.error(
      error
    );

    prefs.set(
      eventId,
      previous
    );

    render();

    el("status")
      .textContent =
        "Impossible d’enregistrer la préférence dans Supabase.";
  }
}


/* ======================================================
   THÈMES
   ====================================================== */

function themeClass(
  category
) {
  return (
    "theme-" +
    normalize(
      category ||
      "culture"
    )
      .replace(
        /[^a-z0-9]+/g,
        "-"
      )
      .replace(
        /^-|-$/g,
        ""
      )
  );
}


/* ======================================================
   REGROUPEMENT DES SPECTACLES
   ====================================================== */

function buildDisplayEvents(
  filteredEvents
) {
  const displayEvents = [];

  for (
    const ev
    of filteredEvents
  ) {
    const dates =
      futureDates(ev);

    if (
      !dates.length
    ) {
      continue;
    }

    /*
     * Une seule carte par spectacle.
     *
     * Elle est positionnée à la date
     * de la prochaine séance.
     */
    displayEvents.push({
      ev,
      nextDate:
        dates[0]
    });
  }

  displayEvents.sort(
    (a, b) => {
      const dateDiff =
        a.nextDate -
        b.nextDate;

      if (
        dateDiff !== 0
      ) {
        return dateDiff;
      }

      return (
        a.ev.title ||
        ""
      ).localeCompare(
        b.ev.title ||
        "",
        "fr"
      );
    }
  );

  return displayEvents;
}


/* ======================================================
   AFFICHAGE
   ====================================================== */

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
          getPref(
            ev.id
          );

        if (
          !hasFutureSession(
            ev
          )
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
          !haystack.includes(
            q
          )
        ) {
          return false;
        }

        return true;
      }
    );

  const displayEvents =
    buildDisplayEvents(
      filtered
    );

  el("status")
    .textContent =
      `${displayEvents.length} spectacle${
        displayEvents.length > 1
          ? "s"
          : ""
      } · synchronisé avec Supabase`;

  const container =
    el("events");

  container.innerHTML =
    "";

  if (
    !displayEvents.length
  ) {
    container.innerHTML =
      `<div class="empty-card">Aucun spectacle pour ces filtres.</div>`;

    return;
  }

  /*
   * Regroupement par date
   * de prochaine séance.
   */
  const groups =
    new Map();

  for (
    const item
    of displayEvents
  ) {
    const key =
      dayKey(
        item.nextDate
      );

    if (
      !groups.has(key)
    ) {
      groups.set(
        key,
        {
          date:
            item.nextDate,

          items: []
        }
      );
    }

    groups
      .get(key)
      .items
      .push(item);
  }

  for (
    const group
    of groups.values()
  ) {
    const section =
      document.createElement(
        "section"
      );

    section.className =
      "day-group";

    const heading =
      document.createElement(
        "div"
      );

    heading.className =
      "day-heading";

    heading.innerHTML = `
      <strong>
        ${escapeHtml(
          formatDay(
            group.date
          )
        )}
      </strong>

      <span>
        ${group.items.length}
        spectacle${
          group.items.length > 1
            ? "s"
            : ""
        }
      </span>
    `;

    const grid =
      document.createElement(
        "div"
      );

    grid.className =
      "day-grid";

    for (
      const {
        ev
      }
      of group.items
    ) {
      const p =
        getPref(
          ev.id
        );

      const card =
        document.createElement(
          "article"
        );

      card.className =
        "event-card";

      const titleHtml =
        ev.url
          ? `
            <a
              class="event-title-link"
              href="${escapeAttr(ev.url)}"
              target="_blank"
              rel="noopener"
            >
              ${escapeHtml(ev.title)}
            </a>
          `
          : `
            <span class="event-title-link">
              ${escapeHtml(ev.title)}
            </span>
          `;

      const sessionInfo =
        sessionsLabel(
          ev
        );

      card.innerHTML = `
        <div class="event-card-main">

          <span
            class="theme-badge ${themeClass(ev.category)}"
          >
            ${escapeHtml(
              ev.category ||
              "Culture"
            )}
          </span>

          <div class="event-info">

            ${titleHtml}

            <div class="event-details">

              ${
                ev.venue
                  ? `
                    <span class="event-venue">
                      ${escapeHtml(ev.venue)}
                    </span>
                  `
                  : ""
              }

              ${
                sessionInfo
                  ? `
                    <span class="event-sessions">
                      ${escapeHtml(sessionInfo)}
                    </span>
                  `
                  : ""
              }

            </div>

          </div>

        </div>

        <div class="icon-actions">

          <button
            class="icon-action ${
              p.favorite
                ? "active"
                : ""
            }"
            data-action="favorite"
            data-id="${escapeAttr(ev.id)}"
            title="${
              p.favorite
                ? "Retirer des favoris"
                : "Ajouter aux favoris"
            }"
            aria-label="${
              p.favorite
                ? "Retirer des favoris"
                : "Ajouter aux favoris"
            }"
          >
            ${
              p.favorite
                ? "★"
                : "☆"
            }
          </button>

          <button
            class="icon-action ${
              p.reserved
                ? "active"
                : ""
            }"
            data-action="reserved"
            data-id="${escapeAttr(ev.id)}"
            title="${
              p.reserved
                ? "Retirer des réservés"
                : "Marquer comme réservé"
            }"
            aria-label="${
              p.reserved
                ? "Retirer des réservés"
                : "Marquer comme réservé"
            }"
          >
            ${
              p.reserved
                ? "▣"
                : "▢"
            }
          </button>

          <button
            class="icon-action ${
              p.hidden
                ? "active"
                : ""
            }"
            data-action="hidden"
            data-id="${escapeAttr(ev.id)}"
            title="${
              p.hidden
                ? "Réafficher"
                : "Masquer"
            }"
            aria-label="${
              p.hidden
                ? "Réafficher"
                : "Masquer"
            }"
          >
            ${
              p.hidden
                ? "◉"
                : "⊘"
            }
          </button>

        </div>
      `;

      grid.appendChild(
        card
      );
    }

    section.append(
      heading,
      grid
    );

    container.appendChild(
      section
    );
  }
}


/* ======================================================
   ÉCHAPPEMENT
   ====================================================== */

function escapeHtml(
  value
) {
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

function escapeAttr(
  value
) {
  return escapeHtml(
    value
  );
}


/* ======================================================
   ACTIONS
   ====================================================== */

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


/* ======================================================
   RECHERCHE
   ====================================================== */

el("search")
  .addEventListener(
    "input",
    render
  );

setupPeriodCheckboxes();


/* ======================================================
   EFFACER FILTRES
   ====================================================== */

document
  .querySelectorAll(
    ".filter-clear"
  )
  .forEach(
    button => {
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
    }
  );


/* ======================================================
   ONGLETS
   ====================================================== */

document
  .querySelectorAll(
    ".tab"
  )
  .forEach(
    button => {
      button.addEventListener(
        "click",
        () => {
          document
            .querySelectorAll(
              ".tab"
            )
            .forEach(
              tab => {
                tab.classList
                  .remove(
                    "active"
                  );
              }
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
    }
  );


/* ======================================================
   INITIALISATION
   ====================================================== */

(async function init() {
  try {
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
