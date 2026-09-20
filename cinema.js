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
  let label =
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
   SUPPRESSION DES SÉANCES MÉGARAMA
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
     * Ne plus afficher une séance
     * déjà commencée.
     */
    if (dt <= now) {
      return false;
    }

    if (
      dt < start ||
      dt >= end
    ) {
      return false;
    }

    if (
      afterWorkOnly &&
      isWeekday(dt) &&
      dt.getHours() < 17
    ) {
      return false;
    }

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
   REGROUPEMENT PAR FILM
   ====================================================== */

function groupByFilm(events) {
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
          sessions: []
        }
      );
    }

    films
      .get(key)
      .sessions
      .push(event);
  }

  return [
    ...films.values()
  ];
}


/* ======================================================
   URL DU FILM
   ====================================================== */

function filmUrl(film) {
  const session =
    film.sessions.find(
      item => item.url
    );

  return session?.url || null;
}


/* ======================================================
   SÉPARATION DES FILMS
   ====================================================== */

function splitFilms(films) {
  const regularMeliesFilms = [];
  const occasionalMeliesFilms = [];
  const occasionalMegarama = [];
  const bigReleases = [];

  for (const film of films) {
    const meliesSessions =
      film.sessions.filter(
        isMeliesSession
      );

    if (meliesSessions.length) {
      /*
       * 1 ou 2 séances :
       * Méliès ponctuel.
       *
       * 3 séances ou plus :
       * programmation Méliès.
       */
      if (meliesSessions.length <= 2) {
        occasionalMeliesFilms.push(
          film
        );
      } else {
        regularMeliesFilms.push(
          film
        );
      }

      continue;
    }

    const megaramaSessions =
      film.sessions.filter(
        isMegaramaSession
      );

    if (
      megaramaSessions.length <= 4
    ) {
      occasionalMegarama.push(
        film
      );
    } else {
      bigReleases.push(
        film
      );
    }
  }

  return {
    regularMeliesFilms,
    occasionalMeliesFilms,
    occasionalMegarama,
    bigReleases
  };
}


/* ======================================================
   EN-TÊTE UNIQUE DES 5 JOURS
   ====================================================== */

function ensurePlanningLayout() {
  const oldTable =
    el("cinemaWeekBody")
      ?.closest(".cinema-table-wrap");

  if (!oldTable) {
    return null;
  }

  let planning =
    el("cinemaPlanning");

  if (planning) {
    return planning;
  }

  /*
   * On conserve le conteneur HTML existant,
   * mais on masque l'ancien tableau.
   */
  oldTable.style.display =
    "none";

  planning =
    document.createElement("div");

  planning.id =
    "cinemaPlanning";

  planning.className =
    "cinema-planning";

  oldTable.insertAdjacentElement(
    "afterend",
    planning
  );

  return planning;
}


/* ======================================================
   CRÉATION D'UNE SÉANCE
   ====================================================== */

function createPlanningSession(
  session,
  filmTitle,
  url
) {
  const row =
    document.createElement("div");

  row.className =
    "planning-session";

  const time =
    document.createElement("span");

  const cinemaClass =
    sessionCinemaClass(
      session
    );

  time.className =
    cinemaClass
      ? `planning-time ${cinemaClass}`
      : "planning-time";

  time.textContent =
    formatTime(
      new Date(session.start)
    );

  row.appendChild(time);

  if (session.version) {
    const version =
      document.createElement("span");

    version.className =
      "planning-version";

    version.textContent =
      session.version;

    time.appendChild(version);
  }

  if (url) {
    const title =
      document.createElement("a");

    title.className =
      "planning-film-title";

    title.href =
      url;

    title.target =
      "_blank";

    title.rel =
      "noopener";

    title.textContent =
      filmTitle;

    row.appendChild(title);

  } else {
    const title =
      document.createElement("span");

    title.className =
      "planning-film-title";

    title.textContent =
      filmTitle;

    row.appendChild(title);
  }

  return row;
}


/* ======================================================
   TRANSFORMATION FILMS -> SÉANCES
   ====================================================== */

function filmSessions(films) {
  return films.flatMap(
    film => {
      const url =
        filmUrl(film);

      return film.sessions.map(
        session => ({
          ...session,
          filmTitle:
            film.title,
          filmUrl:
            url
        })
      );
    }
  );
}


/* ======================================================
   EN-TÊTE DES DATES
   ====================================================== */

function createDatesHeader(days) {
  const header =
    document.createElement("div");

  header.className =
    "planning-dates";

  for (const day of days) {
    const cell =
      document.createElement("div");

    cell.className =
      "planning-date";

    cell.textContent =
      formatHeaderDay(day);

    header.appendChild(cell);
  }

  return header;
}


/* ======================================================
   GRILLE 5 JOURS
   ====================================================== */

function createFiveDayGrid(
  films,
  days,
  options = {}
) {
  const {
    showDates = false
  } = options;

  const wrapper =
    document.createElement("div");

  wrapper.className =
    "planning-grid-wrap";

  if (showDates) {
    wrapper.appendChild(
      createDatesHeader(days)
    );
  }

  const grid =
    document.createElement("div");

  grid.className =
    "planning-grid";

  const sessions =
    filmSessions(films);

  for (const day of days) {
    const column =
      document.createElement("div");

    column.className =
      "planning-day-column";

    const daySessions =
      sessions
        .filter(
          session =>
            sameDay(
              new Date(session.start),
              day
            )
        )
        .sort(
          (a, b) =>
            new Date(a.start) -
            new Date(b.start)
        );

    if (!daySessions.length) {
      const empty =
        document.createElement("div");

      empty.className =
        "planning-empty";

      empty.textContent =
        "—";

      column.appendChild(empty);

    } else {
      for (
        const session
        of daySessions
      ) {
        column.appendChild(
          createPlanningSession(
            session,
            session.filmTitle,
            session.filmUrl
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
   TITRE DE SECTION
   ====================================================== */

function createSectionTitle(text) {
  const title =
    document.createElement("h3");

  title.className =
    "planning-section-title";

  title.textContent =
    text;

  return title;
}


/* ======================================================
   AFFICHAGE DU PLANNING MÉLIÈS
   ====================================================== */

function renderCinemaPlanning(
  regularMeliesFilms,
  occasionalMeliesFilms,
  days
) {
  const planning =
    ensurePlanningLayout();

  if (!planning) {
    return;
  }

  planning.innerHTML = "";

  /*
   * Programmation Méliès
   *
   * C'est le premier bloc :
   * c'est donc lui qui affiche les dates.
   */
  planning.appendChild(
    createFiveDayGrid(
      regularMeliesFilms,
      days,
      {
        showDates: true
      }
    )
  );

  /*
   * Séances ponctuelles Méliès
   *
   * Pas de répétition des dates.
   */
  if (
    occasionalMeliesFilms.length
  ) {
    planning.appendChild(
      createSectionTitle(
        "Séances ponctuelles Méliès"
      )
    );

    planning.appendChild(
      createFiveDayGrid(
        occasionalMeliesFilms,
        days,
        {
          showDates: false
        }
      )
    );
  }
}


/* ======================================================
   MÉGARAMA PONCTUEL
   ====================================================== */

function renderOccasionalMegarama(
  films,
  days
) {
  const section =
    el("cinemaOccasionalSection");

  const grid =
    el("cinemaOccasionalGrid");

  if (
    !section ||
    !grid
  ) {
    return;
  }

  grid.innerHTML = "";

  if (!films.length) {
    section.style.display =
      "none";

    return;
  }

  section.style.display =
    "";

  /*
   * L'ancien grid Mégarama possédait une
   * première colonne + les dates.
   *
   * Désormais on met uniquement les cinq
   * colonnes de séances.
   */
  grid.className =
    "planning-grid planning-grid-megarama";

  const sessions =
    filmSessions(films);

  for (const day of days) {
    const column =
      document.createElement("div");

    column.className =
      "planning-day-column";

    const daySessions =
      sessions
        .filter(
          session =>
            sameDay(
              new Date(session.start),
              day
            )
        )
        .sort(
          (a, b) =>
            new Date(a.start) -
            new Date(b.start)
        );

    if (!daySessions.length) {
      const empty =
        document.createElement("div");

      empty.className =
        "planning-empty";

      empty.textContent =
        "—";

      column.appendChild(empty);

    } else {
      for (
        const session
        of daySessions
      ) {
        column.appendChild(
          createPlanningSession(
            session,
            session.filmTitle,
            session.filmUrl
          )
        );
      }
    }

    grid.appendChild(column);
  }
}


/* ======================================================
   GROSSES SORTIES MÉGARAMA
   ====================================================== */

function renderBigReleases(films) {
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

  if (!films.length) {
    section.style.display =
      "none";

    return;
  }

  section.style.display =
    "";

  films
    .sort(
      (a, b) =>
        a.title.localeCompare(
          b.title,
          "fr"
        )
    )
    .forEach(
      (film, index) => {
        if (index > 0) {
          const sep =
            document.createElement("span");

          sep.className =
            "big-release-separator";

          sep.textContent =
            " · ";

          container.appendChild(
            sep
          );
        }

        const url =
          filmUrl(film);

        if (url) {
          const link =
            document.createElement("a");

          link.className =
            "big-release-title";

          link.href =
            url;

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
   AFFICHAGE
   ====================================================== */

function render() {
  const start =
    startOfToday();

  const days =
    Array.from(
      { length: 5 },
      (_, i) =>
        addDays(
          start,
          i
        )
    );

  const events =
    visibleEvents();

  const films =
    groupByFilm(
      events
    );

  const {
    regularMeliesFilms,
    occasionalMeliesFilms,
    occasionalMegarama,
    bigReleases
  } =
    splitFilms(films);

  renderCinemaPlanning(
    regularMeliesFilms,
    occasionalMeliesFilms,
    days
  );

  renderOccasionalMegarama(
    occasionalMegarama,
    days
  );

  renderBigReleases(
    bigReleases
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
      !Array.isArray(cinemaEvents)
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

  } catch (err) {
    console.error(err);
  }
}

el("afterWorkOnly")
  ?.addEventListener(
    "change",
    render
  );

init();
