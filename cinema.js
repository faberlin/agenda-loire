let cinemaEvents = [];

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

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatHeaderDay(date) {
  const label =
    new Intl.DateTimeFormat(
      "fr-FR",
      {
        weekday: "short",
        day: "numeric",
        month: "short"
      }
    ).format(date);

  return (
    label.charAt(0).toUpperCase() +
    label.slice(1)
  );
}

function formatTime(date) {
  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      hour: "2-digit",
      minute: "2-digit"
    }
  ).format(date);
}

function isWeekday(date) {
  const day = date.getDay();

  return day >= 1 && day <= 5;
}


/* ======================================================
   CINÉMAS
   ====================================================== */

function isMeliesSession(session) {
  return normalize(
    session.cinema
  ).includes("melies");
}

function isMegaramaSession(session) {
  return normalize(
    session.cinema
  ).includes("megarama");
}

function sessionCinemaClass(session) {
  const cinema =
    normalize(session.cinema);

  if (
    cinema.includes("melies") &&
    cinema.includes("saint-francois")
  ) {
    return "session-sf";
  }

  if (
    cinema.includes("melies") &&
    cinema.includes("jean-jaures")
  ) {
    return "session-melies-jj";
  }

  if (
    cinema.includes("megarama") &&
    (
      cinema.includes("camion") ||
      cinema.includes("chavanelle")
    )
  ) {
    return "session-mega-cr";
  }

  if (
    cinema.includes("megarama") &&
    cinema.includes("jean-jaures")
  ) {
    return "session-mega-jj";
  }

  return "";
}


/* ======================================================
   VF / VO MÉGARAMA
   ====================================================== */

function isOriginalVersion(session) {
  const version =
    normalize(session.version)
      .replace(/\s/g, "");

  return (
    version === "vo" ||
    version === "vost" ||
    version === "vostf" ||
    version === "vostfr"
  );
}

function isVF(session) {
  return (
    normalize(session.version)
      .replace(/\s/g, "") === "vf"
  );
}

function filterMegaramaVF(events) {
  const filmsWithVO =
    new Set();

  for (const session of events) {
    if (
      isMegaramaSession(session) &&
      isOriginalVersion(session)
    ) {
      filmsWithVO.add(
        normalize(session.title)
      );
    }
  }

  return events.filter(session => {
    if (!isMegaramaSession(session)) {
      return true;
    }

    const key =
      normalize(session.title);

    if (!filmsWithVO.has(key)) {
      return true;
    }

    return !isVF(session);
  });
}


/* ======================================================
   SI FILM AU MÉLIÈS :
   SUPPRIMER MÉGARAMA
   ====================================================== */

function removeMegaramaWhenMeliesExists(events) {
  const filmsAtMelies =
    new Set();

  for (const event of events) {
    if (isMeliesSession(event)) {
      filmsAtMelies.add(
        normalize(event.title)
      );
    }
  }

  return events.filter(event => {
    if (
      filmsAtMelies.has(
        normalize(event.title)
      ) &&
      isMegaramaSession(event)
    ) {
      return false;
    }

    return true;
  });
}


/* ======================================================
   FILTRES CINÉMAS
   ====================================================== */

function selectedCinemas() {
  const container =
    el("cinemaFilters");

  if (!container) {
    return new Set();
  }

  return new Set(
    [
      ...container.querySelectorAll(
        'input[type="checkbox"]:checked'
      )
    ].map(
      input => input.value
    )
  );
}

function buildCinemaFilters() {
  const container =
    el("cinemaFilters");

  if (!container) {
    return;
  }

  container.innerHTML = "";

  const names = [
    ...new Set(
      cinemaEvents
        .map(event => event.cinema)
        .filter(Boolean)
    )
  ].sort(
    (a, b) =>
      a.localeCompare(b, "fr")
  );

  for (const name of names) {
    const label =
      document.createElement("label");

    label.className =
      "cinema-filter-check";

    const input =
      document.createElement("input");

    input.type =
      "checkbox";

    input.value =
      name;

    input.addEventListener(
      "change",
      render
    );

    const span =
      document.createElement("span");

    span.textContent =
      name;

    label.appendChild(input);
    label.appendChild(span);

    container.appendChild(label);
  }
}


/* ======================================================
   SÉANCES VISIBLES
   ====================================================== */

function visibleEvents() {
  let filtered =
    filterMegaramaVF(
      cinemaEvents
    );

  filtered =
    removeMegaramaWhenMeliesExists(
      filtered
    );

  const afterWorkOnly =
    el("afterWorkOnly")
      ?.checked || false;

  const cinemas =
    selectedCinemas();

  const start =
    startOfToday();

  const now =
    new Date();

  const end =
    addDays(start, 5);

  return filtered.filter(event => {
    const dt =
      new Date(event.start);

    if (
      Number.isNaN(dt.getTime())
    ) {
      return false;
    }

    /*
     * Ne pas afficher les séances
     * déjà commencées.
     */
    if (dt <= now) {
      return false;
    }

    /*
     * 5 jours à partir d'aujourd'hui.
     */
    if (
      dt < start ||
      dt >= end
    ) {
      return false;
    }

    /*
     * En semaine :
     * masquer avant 17h.
     */
    if (
      afterWorkOnly &&
      isWeekday(dt) &&
      dt.getHours() < 17
    ) {
      return false;
    }

    /*
     * Filtre cinéma.
     * Aucune case cochée = tous les cinémas.
     */
    if (
      cinemas.size > 0 &&
      !cinemas.has(event.cinema)
    ) {
      return false;
    }

    return true;
  });
}


/* ======================================================
   URL DU FILM
   ====================================================== */

function filmUrl(session) {
  return session.url || "";
}


/* ======================================================
   CRÉATION D'UNE SÉANCE
   ====================================================== */

function createSessionNode(session) {
  const row =
    document.createElement("div");

  row.className =
    "cinema-session";

  const time =
    document.createElement("span");

  const cinemaClass =
    sessionCinemaClass(
      session
    );

  time.className =
    cinemaClass
      ? `cinema-session-time ${cinemaClass}`
      : "cinema-session-time";

  const hour =
    document.createElement("span");

  hour.textContent =
    formatTime(
      new Date(session.start)
    );

  time.appendChild(hour);

  if (session.version) {
    const version =
      document.createElement("span");

    version.className =
      "cinema-session-version";

    version.textContent =
      session.version;

    time.appendChild(version);
  }

  row.appendChild(time);

  const url =
    filmUrl(session);

  if (url) {
    const title =
      document.createElement("a");

    title.className =
      "cinema-session-title";

    title.href =
      url;

    title.target =
      "_blank";

    title.rel =
      "noopener";

    title.textContent =
      session.title;

    row.appendChild(title);

  } else {
    const title =
      document.createElement("span");

    title.className =
      "cinema-session-title";

    title.textContent =
      session.title;

    row.appendChild(title);
  }

  return row;
}


/* ======================================================
   EN-TÊTE DES 5 JOURS
   ====================================================== */

function createDatesHeader(days) {
  const header =
    document.createElement("div");

  header.className =
    "cinema-dates-header";

  for (const day of days) {
    const cell =
      document.createElement("div");

    cell.className =
      "cinema-date-cell";

    cell.textContent =
      formatHeaderDay(day);

    header.appendChild(cell);
  }

  return header;
}


/* ======================================================
   GRILLE DE SÉANCES
   ====================================================== */

function createSessionsGrid(
  events,
  days,
  showDates = false
) {
  const wrapper =
    document.createElement("div");

  wrapper.className =
    "cinema-grid-wrap";

  if (showDates) {
    wrapper.appendChild(
      createDatesHeader(days)
    );
  }

  const grid =
    document.createElement("div");

  grid.className =
    "cinema-five-day-grid";

  for (const day of days) {
    const column =
      document.createElement("div");

    column.className =
      "cinema-day-column";

    const sessions =
      events
        .filter(
          event =>
            sameDay(
              new Date(event.start),
              day
            )
        )
        .sort(
          (a, b) => {
            const timeDiff =
              new Date(a.start) -
              new Date(b.start);

            if (timeDiff !== 0) {
              return timeDiff;
            }

            return a.title.localeCompare(
              b.title,
              "fr"
            );
          }
        );

    if (!sessions.length) {
      const empty =
        document.createElement("div");

      empty.className =
        "cinema-day-empty";

      empty.textContent =
        "—";

      column.appendChild(empty);

    } else {
      for (const session of sessions) {
        column.appendChild(
          createSessionNode(
            session
          )
        );
      }
    }

    grid.appendChild(column);
  }

  wrapper.appendChild(grid);

  return wrapper;
}


/* ======================================================
   MÉLIÈS
   ====================================================== */

function renderMelies(
  events,
  days
) {
  const container =
    el("cinemaMeliesPlanning");

  if (!container) {
    return;
  }

  container.innerHTML = "";

  const melies =
    events.filter(
      isMeliesSession
    );

  /*
   * Les dates ne sont affichées qu'ici.
   */
  container.appendChild(
    createSessionsGrid(
      melies,
      days,
      true
    )
  );
}


/* ======================================================
   MÉGARAMA
   ====================================================== */

function renderMegarama(
  events,
  days
) {
  const section =
    el("cinemaOccasionalSection");

  const container =
    el("cinemaOccasionalGrid");

  if (
    !section ||
    !container
  ) {
    return;
  }

  container.innerHTML = "";

  const megarama =
    events.filter(
      isMegaramaSession
    );

  if (!megarama.length) {
    section.style.display =
      "none";

    return;
  }

  section.style.display =
    "";

  /*
   * Pas de dates ici :
   * les colonnes correspondent à celles
   * affichées au-dessus dans Méliès.
   */
  for (const day of days) {
    const column =
      document.createElement("div");

    column.className =
      "cinema-day-column";

    const sessions =
      megarama
        .filter(
          event =>
            sameDay(
              new Date(event.start),
              day
            )
        )
        .sort(
          (a, b) => {
            const timeDiff =
              new Date(a.start) -
              new Date(b.start);

            if (timeDiff !== 0) {
              return timeDiff;
            }

            return a.title.localeCompare(
              b.title,
              "fr"
            );
          }
        );

    if (!sessions.length) {
      const empty =
        document.createElement("div");

      empty.className =
        "cinema-day-empty";

      empty.textContent =
        "—";

      column.appendChild(empty);

    } else {
      for (const session of sessions) {
        column.appendChild(
          createSessionNode(
            session
          )
        );
      }
    }

    container.appendChild(column);
  }
}


/* ======================================================
   GROSSES SORTIES MÉGARAMA
   ====================================================== */

function renderBigReleases(
  events
) {
  const section =
    el("cinemaBigReleasesSection");

  const container =
    el("cinemaBigReleases");

  if (
    !section ||
    !container
  ) {
    return;
  }

  container.innerHTML = "";

  /*
   * Films Mégarama ayant plus de
   * 4 séances visibles.
   */
  const films =
    new Map();

  for (const event of events) {
    if (!isMegaramaSession(event)) {
      continue;
    }

    const key =
      normalize(event.title);

    if (!films.has(key)) {
      films.set(
        key,
        {
          title: event.title,
          url: event.url || "",
          count: 0
        }
      );
    }

    films.get(key).count += 1;
  }

  const bigReleases =
    [...films.values()]
      .filter(
        film =>
          film.count > 4
      )
      .sort(
        (a, b) =>
          a.title.localeCompare(
            b.title,
            "fr"
          )
      );

  if (!bigReleases.length) {
    section.style.display =
      "none";

    return;
  }

  section.style.display =
    "";

  bigReleases.forEach(
    (film, index) => {
      if (index > 0) {
        const separator =
          document.createElement("span");

        separator.className =
          "big-release-separator";

        separator.textContent =
          " · ";

        container.appendChild(
          separator
        );
      }

      if (film.url) {
        const link =
          document.createElement("a");

        link.className =
          "big-release-title";

        link.href =
          film.url;

        link.target =
          "_blank";

        link.rel =
          "noopener";

        link.textContent =
          film.title;

        container.appendChild(
          link
        );

      } else {
        const title =
          document.createElement("span");

        title.className =
          "big-release-title";

        title.textContent =
          film.title;

        container.appendChild(
          title
        );
      }
    }
  );
}


/* ======================================================
   RETIRER LES GROSSES SORTIES DU TABLEAU MÉGARAMA
   ====================================================== */

function removeBigMegaramaReleases(
  events
) {
  const counts =
    new Map();

  for (const event of events) {
    if (!isMegaramaSession(event)) {
      continue;
    }

    const key =
      normalize(event.title);

    counts.set(
      key,
      (counts.get(key) || 0) + 1
    );
  }

  return events.filter(event => {
    if (!isMegaramaSession(event)) {
      return true;
    }

    return (
      (counts.get(
        normalize(event.title)
      ) || 0) <= 4
    );
  });
}


/* ======================================================
   AFFICHAGE
   ====================================================== */

function render() {
  const start =
    startOfToday();

  const days =
    Array.from(
      { length: 5 },
      (_, index) =>
        addDays(
          start,
          index
        )
    );

  const events =
    visibleEvents();

  /*
   * Méliès :
   * toutes les séances ensemble.
   */
  renderMelies(
    events,
    days
  );

  /*
   * Mégarama :
   * on conserve la distinction entre
   * séances ponctuelles et grosses sorties.
   */
  const megaramaPlanningEvents =
    removeBigMegaramaReleases(
      events
    );

  renderMegarama(
    megaramaPlanningEvents,
    days
  );

  renderBigReleases(
    events
  );
}


/* ======================================================
   CHARGEMENT
   ====================================================== */

async function init() {
  try {
    const response =
      await fetch(
        "cinema_events.json",
        {
          cache: "no-store"
        }
      );

    if (!response.ok) {
      throw new Error(
        "Impossible de charger cinema_events.json"
      );
    }

    cinemaEvents =
      await response.json();

    if (!Array.isArray(cinemaEvents)) {
      throw new Error(
        "cinema_events.json n'a pas le bon format"
      );
    }

    cinemaEvents.sort(
      (a, b) =>
        new Date(a.start) -
        new Date(b.start)
    );

    buildCinemaFilters();
    render();

  } catch (error) {
    console.error(error);
  }
}

el("afterWorkOnly")
  ?.addEventListener(
    "change",
    render
  );

init();
