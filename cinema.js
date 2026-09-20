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
     * Une séance déjà commencée disparaît.
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
     * masquer les séances avant 17h.
     */
    if (
      afterWorkOnly &&
      isWeekday(dt) &&
      dt.getHours() < 17
    ) {
      return false;
    }

    /*
     * Aucune case cinéma cochée = tout afficher.
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
   REGROUPER LES SÉANCES D'UN JOUR PAR FILM
   ====================================================== */

function groupDaySessionsByFilm(events) {
  const films =
    new Map();

  for (const event of events) {
    const key =
      normalize(event.title);

    if (!films.has(key)) {
      films.set(
        key,
        {
          title: event.title,
          url: event.url || "",
          sessions: []
        }
      );
    }

    const film =
      films.get(key);

    /*
     * On garde une URL si la première
     * séance n'en avait pas.
     */
    if (
      !film.url &&
      event.url
    ) {
      film.url =
        event.url;
    }

    film.sessions.push(
      event
    );
  }

  const result =
    [...films.values()];

  /*
   * Séances du film triées par heure.
   */
  for (const film of result) {
    film.sessions.sort(
      (a, b) =>
        new Date(a.start) -
        new Date(b.start)
    );
  }

  /*
   * Films triés selon leur première séance.
   */
  result.sort(
    (a, b) => {
      const firstA =
        new Date(
          a.sessions[0].start
        );

      const firstB =
        new Date(
          b.sessions[0].start
        );

      const diff =
        firstA - firstB;

      if (diff !== 0) {
        return diff;
      }

      return a.title.localeCompare(
        b.title,
        "fr"
      );
    }
  );

  return result;
}


/* ======================================================
   UNE PASTILLE HORAIRE
   ====================================================== */

function createTimeBadge(session) {
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

  return time;
}


/* ======================================================
   UNE LIGNE = UN FILM
   ====================================================== */

function createFilmRow(film) {
  const row =
    document.createElement("div");

  row.className =
    "cinema-film-row";

  /*
   * Tous les horaires du film
   * sont regroupés au début de la ligne.
   */
  const times =
    document.createElement("div");

  times.className =
    "cinema-film-times";

  for (
    const session
    of film.sessions
  ) {
    times.appendChild(
      createTimeBadge(
        session
      )
    );
  }

  row.appendChild(times);

  /*
   * Titre du film.
   */
  if (film.url) {
    const title =
      document.createElement("a");

    title.className =
      "cinema-session-title";

    title.href =
      film.url;

    title.target =
      "_blank";

    title.rel =
      "noopener";

    title.textContent =
      film.title;

    row.appendChild(title);

  } else {
    const title =
      document.createElement("span");

    title.className =
      "cinema-session-title";

    title.textContent =
      film.title;

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
   CRÉATION D'UNE COLONNE JOUR
   ====================================================== */

function createDayColumn(
  events,
  day
) {
  const column =
    document.createElement("div");

  column.className =
    "cinema-day-column";

  const dayEvents =
    events.filter(
      event =>
        sameDay(
          new Date(event.start),
          day
        )
    );

  const films =
    groupDaySessionsByFilm(
      dayEvents
    );

  if (!films.length) {
    const empty =
      document.createElement("div");

    empty.className =
      "cinema-day-empty";

    empty.textContent =
      "—";

    column.appendChild(
      empty
    );

    return column;
  }

  for (const film of films) {
    column.appendChild(
      createFilmRow(
        film
      )
    );
  }

  return column;
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
      createDatesHeader(
        days
      )
    );
  }

  const grid =
    document.createElement("div");

  grid.className =
    "cinema-five-day-grid";

  for (const day of days) {
    grid.appendChild(
      createDayColumn(
        events,
        day
      )
    );
  }

  wrapper.appendChild(
    grid
  );

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
   * Les dates sont affichées uniquement
   * sur le tableau Méliès.
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
   GROSSES SORTIES MÉGARAMA
   ====================================================== */

function getBigMegaramaFilms(
  events
) {
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
          title:
            event.title,
          url:
            event.url || "",
          count:
            0
        }
      );
    }

    const film =
      films.get(key);

    film.count += 1;

    if (
      !film.url &&
      event.url
    ) {
      film.url =
        event.url;
    }
  }

  return [
    ...films.values()
  ]
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
}


/* ======================================================
   RETIRER LES GROSSES SORTIES DU PLANNING
   ====================================================== */

function removeBigMegaramaReleases(
  events
) {
  const bigKeys =
    new Set(
      getBigMegaramaFilms(
        events
      ).map(
        film =>
          normalize(
            film.title
          )
      )
    );

  return events.filter(
    event => {
      if (
        !isMegaramaSession(event)
      ) {
        return true;
      }

      return !bigKeys.has(
        normalize(
          event.title
        )
      );
    }
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
    el(
      "cinemaOccasionalSection"
    );

  const container =
    el(
      "cinemaOccasionalGrid"
    );

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

  for (const day of days) {
    container.appendChild(
      createDayColumn(
        megarama,
        day
      )
    );
  }
}


/* ======================================================
   AFFICHER LES GROSSES SORTIES
   ====================================================== */

function renderBigReleases(
  events
) {
  const section =
    el(
      "cinemaBigReleasesSection"
    );

  const container =
    el(
      "cinemaBigReleases"
    );

  if (
    !section ||
    !container
  ) {
    return;
  }

  container.innerHTML = "";

  const bigReleases =
    getBigMegaramaFilms(
      events
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
          document.createElement(
            "span"
          );

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
          document.createElement(
            "a"
          );

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
          document.createElement(
            "span"
          );

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
   * Méliès
   */
  renderMelies(
    events,
    days
  );

  /*
   * Mégarama :
   * les grosses sorties restent en bas.
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

    if (
      !Array.isArray(
        cinemaEvents
      )
    ) {
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
    console.error(
      error
    );
  }
}

el("afterWorkOnly")
  ?.addEventListener(
    "change",
    render
  );

init();
