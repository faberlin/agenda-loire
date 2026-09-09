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

  return (
    day >= 1 &&
    day <= 5
  );
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
   URL / TITRE FILM
   ====================================================== */

function filmUrl(film) {
  const session =
    film.sessions.find(
      item => item.url
    );

  return session?.url || null;
}

function createFilmTitle(film) {
  const url =
    filmUrl(film);

  if (url) {
    const link =
      document.createElement("a");

    link.className =
      "film-title film-title-link";

    link.href =
      url;

    link.target =
      "_blank";

    link.rel =
      "noopener";

    link.textContent =
      film.title;

    return link;
  }

  const title =
    document.createElement("span");

  title.className =
    "film-title";

  title.textContent =
    film.title;

  return title;
}


/* ======================================================
   SÉPARATION
   ====================================================== */

function splitFilms(films) {
  const meliesFilms = [];
  const occasionalMegarama = [];
  const bigReleases = [];

  for (const film of films) {
    const hasMelies =
      film.sessions.some(
        isMeliesSession
      );

    if (hasMelies) {
      meliesFilms.push(
        film
      );

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

  meliesFilms.sort(
    (a, b) => {
      if (
        b.sessions.length !==
        a.sessions.length
      ) {
        return (
          b.sessions.length -
          a.sessions.length
        );
      }

      return a.title.localeCompare(
        b.title,
        "fr"
      );
    }
  );

  bigReleases.sort(
    (a, b) =>
      a.title.localeCompare(
        b.title,
        "fr"
      )
  );

  return {
    meliesFilms,
    occasionalMegarama,
    bigReleases
  };
}


/* ======================================================
   EN-TÊTES DES JOURS
   ====================================================== */

function buildDayHeaders(days) {
  const row =
    el("cinemaWeekHeader");

  if (!row) {
    return;
  }

  row.innerHTML =
    '<th class="film-col">Film</th>';

  for (const day of days) {
    const th =
      document.createElement("th");

    th.className =
      "day-col";

    th.textContent =
      formatHeaderDay(day);

    row.appendChild(th);
  }
}


/* ======================================================
   HORAIRE
   ====================================================== */

function createSessionNode(session) {
  const dt =
    new Date(session.start);

  const node =
    document.createElement("span");

  const cinemaClass =
    sessionCinemaClass(session);

  node.className =
    cinemaClass
      ? `session-time ${cinemaClass}`
      : "session-time";

  const hour =
    document.createElement("span");

  hour.textContent =
    formatTime(dt);

  node.appendChild(hour);

  if (session.version) {
    const version =
      document.createElement("span");

    version.className =
      "session-version";

    version.textContent =
      session.version;

    node.appendChild(version);
  }

  return node;
}


/* ======================================================
   TABLEAU MÉLIÈS
   ====================================================== */

function renderMeliesTable(
  films,
  days
) {
  const body =
    el("cinemaWeekBody");

  if (!body) {
    return;
  }

  body.innerHTML = "";

  for (const film of films) {
    const tr =
      document.createElement("tr");

    const firstTd =
      document.createElement("td");

    firstTd.className =
      "film-col";

    firstTd.appendChild(
      createFilmTitle(
        film
      )
    );

    tr.appendChild(
      firstTd
    );

    for (const day of days) {
      const td =
        document.createElement("td");

      td.className =
        "sessions-cell";

      const sessions =
        film.sessions
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

      if (!sessions.length) {
        const empty =
          document.createElement("span");

        empty.className =
          "no-session";

        empty.textContent =
          "—";

        td.appendChild(empty);

      } else {
        const list =
          document.createElement("div");

        list.className =
          "session-list";

        for (const session of sessions) {
          list.appendChild(
            createSessionNode(
              session
            )
          );
        }

        td.appendChild(list);
      }

      tr.appendChild(td);
    }

    body.appendChild(tr);
  }

  if (!films.length) {
    const tr =
      document.createElement("tr");

    const td =
      document.createElement("td");

    td.colSpan = 6;

    td.className =
      "cinema-empty";

    td.textContent =
      "Aucune séance Méliès.";

    tr.appendChild(td);
    body.appendChild(tr);
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

  const allSessions =
    films.flatMap(
      film =>
        film.sessions.map(
          session => ({
            ...session,
            filmTitle:
              film.title,

            filmUrl:
              filmUrl(film)
          })
        )
    );

  if (!allSessions.length) {
    section.style.display =
      "none";

    return;
  }

  section.style.display =
    "";

  const labelColumn =
    document.createElement("div");

  labelColumn.className =
    "occasional-label-column";

  labelColumn.textContent =
    "Séances ponctuelles Mégarama";

  grid.appendChild(
    labelColumn
  );

  for (const day of days) {
    const column =
      document.createElement("div");

    column.className =
      "occasional-day";

    const heading =
      document.createElement("div");

    heading.className =
      "occasional-day-title";

    heading.textContent =
      formatHeaderDay(day);

    column.appendChild(
      heading
    );

    const daySessions =
      allSessions
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
        "occasional-empty";

      empty.textContent =
        "—";

      column.appendChild(
        empty
      );

    } else {
      for (
        const session
        of daySessions
      ) {
        const row =
          document.createElement("div");

        row.className =
          "occasional-session";

        const time =
          document.createElement("span");

        time.className =
          `occasional-time ${
            sessionCinemaClass(
              session
            )
          }`;

        time.textContent =
          formatTime(
            new Date(session.start)
          );

        row.appendChild(time);

        if (session.filmUrl) {
          const title =
            document.createElement("a");

          title.className =
            "occasional-film-title occasional-film-link";

          title.href =
            session.filmUrl;

          title.target =
            "_blank";

          title.rel =
            "noopener";

          title.textContent =
            session.filmTitle;

          row.appendChild(title);

        } else {
          const title =
            document.createElement("span");

          title.className =
            "occasional-film-title";

          title.textContent =
            session.filmTitle;

          row.appendChild(title);
        }

        column.appendChild(row);
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

  films.forEach(
    (film, index) => {
      if (index > 0) {
        const sep =
          document.createElement("span");

        sep.className =
          "big-release-separator";

        sep.textContent =
          " · ";

        container.appendChild(sep);
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

        container.appendChild(link);

      } else {
        const title =
          document.createElement("span");

        title.className =
          "big-release-title";

        title.textContent =
          film.title;

        container.appendChild(title);
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

  buildDayHeaders(
    days
  );

  const events =
    visibleEvents();

  const films =
    groupByFilm(
      events
    );

  const {
    meliesFilms,
    occasionalMegarama,
    bigReleases
  } =
    splitFilms(films);

  renderMeliesTable(
    meliesFilms,
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
