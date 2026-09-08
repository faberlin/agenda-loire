let cinemaEvents = [];

const el = id => document.getElementById(id);

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
  let label = new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short"
  }).format(date);

  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatShortDate(date) {
  let label = new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short"
  }).format(date);

  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatTime(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function isWeekday(date) {
  const day = date.getDay();
  return day >= 1 && day <= 5;
}

function selectedCinemas() {
  const container = el("cinemaFilters");

  if (!container) {
    return new Set();
  }

  return new Set(
    [...container.querySelectorAll(
      'input[type="checkbox"]:checked'
    )].map(input => input.value)
  );
}

function sessionCinemaClass(session) {
  const cinema = normalize(session.cinema);

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
    cinema.includes("camion")
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

function buildCinemaFilters() {
  const container = el("cinemaFilters");

  if (!container) {
    throw new Error(
      "cinema.html et cinema.js ne correspondent pas : #cinemaFilters absent"
    );
  }

  container.innerHTML = "";

  const names = [
    ...new Set(
      cinemaEvents
        .map(event => event.cinema)
        .filter(Boolean)
    )
  ].sort((a, b) =>
    a.localeCompare(b, "fr")
  );

  for (const name of names) {
    const label = document.createElement("label");
    label.className = "cinema-filter-check";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = name;
    input.addEventListener(
      "change",
      render
    );

    const span = document.createElement("span");
    span.textContent = name;

    label.appendChild(input);
    label.appendChild(span);

    container.appendChild(label);
  }
}

function buildDayHeaders(days) {
  const row = el("cinemaWeekHeader");

  if (!row) {
    throw new Error(
      "cinema.html et cinema.js ne correspondent pas : #cinemaWeekHeader absent"
    );
  }

  row.innerHTML =
    '<th class="film-col">Film</th>';

  const today = startOfToday();

  for (const day of days) {
    const th = document.createElement("th");
    th.className = "day-col";

    if (sameDay(day, today)) {
      th.classList.add("today-col");
    }

    th.textContent =
      formatHeaderDay(day);

    row.appendChild(th);
  }
}

function visibleEvents() {
  const searchInput =
    el("cinemaSearch");

  const afterWorkInput =
    el("afterWorkOnly");

  const search = normalize(
    searchInput
      ? searchInput.value
      : ""
  );

  const afterWorkOnly =
    afterWorkInput
      ? afterWorkInput.checked
      : false;

  const cinemas =
    selectedCinemas();

  const start =
    startOfToday();

  const end =
    addDays(start, 5);

  return cinemaEvents.filter(event => {
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

    if (
      search &&
      !normalize(event.title)
        .includes(search)
    ) {
      return false;
    }

    return true;
  });
}

function groupByFilm(events) {
  const films = new Map();

  for (const event of events) {
    const filmKey =
      normalize(event.title);

    if (!films.has(filmKey)) {
      films.set(
        filmKey,
        {
          title: event.title,
          sessions: []
        }
      );
    }

    films
      .get(filmKey)
      .sessions
      .push(event);
  }

  return [
    ...films.values()
  ].sort((a, b) => {
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
  });
}

function filmSessionCount(film) {
  return film.sessions.length;
}

function createSessionNode(session) {
  const dt =
    new Date(session.start);

  const node =
    document.createElement(
      session.url
        ? "a"
        : "span"
    );

  const cinemaClass =
    sessionCinemaClass(session);

  node.className =
    cinemaClass
      ? `session-time ${cinemaClass}`
      : "session-time";

  if (session.url) {
    node.href =
      session.url;

    node.target =
      "_blank";

    node.rel =
      "noopener";
  }

  const hour =
    document.createElement(
      "span"
    );

  hour.textContent =
    formatTime(dt);

  node.appendChild(hour);

  if (session.version) {
    const version =
      document.createElement(
        "span"
      );

    version.className =
      "session-version";

    version.textContent =
      session.version;

    node.appendChild(
      version
    );
  }

  return node;
}

function renderSessionCell(
  td,
  sessions
) {
  if (!sessions.length) {
    const empty =
      document.createElement(
        "span"
      );

    empty.className =
      "no-session";

    empty.textContent =
      "—";

    td.appendChild(empty);

    return 0;
  }

  sessions.sort(
    (a, b) =>
      new Date(a.start) -
      new Date(b.start)
  );

  const list =
    document.createElement(
      "div"
    );

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

  return sessions.length;
}

function renderMainTable(
  films,
  days
) {
  const body =
    el("cinemaWeekBody");

  if (!body) {
    throw new Error(
      "cinema.html et cinema.js ne correspondent pas : #cinemaWeekBody absent"
    );
  }

  body.innerHTML = "";

  const today =
    startOfToday();

  let totalSessions = 0;

  for (const film of films) {
    const tr =
      document.createElement(
        "tr"
      );

    tr.className =
      "film-start-row";

    const firstTd =
      document.createElement(
        "td"
      );

    firstTd.className =
      "film-col";

    const title =
      document.createElement(
        "span"
      );

    title.className =
      "film-title";

    title.textContent =
      film.title;

    firstTd.appendChild(
      title
    );

    tr.appendChild(
      firstTd
    );

    for (const day of days) {
      const td =
        document.createElement(
          "td"
        );

      td.className =
        "sessions-cell";

      if (
        sameDay(
          day,
          today
        )
      ) {
        td.classList.add(
          "today-col"
        );
      }

      const daySessions =
        film.sessions.filter(
          session =>
            sameDay(
              new Date(
                session.start
              ),
              day
            )
        );

      totalSessions +=
        renderSessionCell(
          td,
          daySessions
        );

      tr.appendChild(td);
    }

    body.appendChild(tr);
  }

  if (!films.length) {
    const tr =
      document.createElement(
        "tr"
      );

    const td =
      document.createElement(
        "td"
      );

    td.colSpan = 6;

    td.className =
      "cinema-empty";

    td.textContent =
      "Aucun film avec au moins 5 séances.";

    tr.appendChild(td);

    body.appendChild(tr);
  }

  return totalSessions;
}

function renderOccasional(
  films
) {
  const container =
    el("cinemaOccasional");

  const section =
    el("cinemaOccasionalSection");

  if (
    !container ||
    !section
  ) {
    return 0;
  }

  container.innerHTML = "";

  if (!films.length) {
    section.style.display =
      "none";

    return 0;
  }

  section.style.display =
    "";

  const list =
    document.createElement(
      "div"
    );

  list.className =
    "occasional-list";

  let totalSessions = 0;

  for (const film of films) {
    const row =
      document.createElement(
        "div"
      );

    row.className =
      "occasional-row";

    const title =
      document.createElement(
        "span"
      );

    title.className =
      "occasional-title";

    title.textContent =
      film.title;

    row.appendChild(title);

    const sessionsWrap =
      document.createElement(
        "div"
      );

    sessionsWrap.className =
      "occasional-sessions";

    const sessions =
      [...film.sessions]
        .sort(
          (a, b) =>
            new Date(a.start) -
            new Date(b.start)
        );

    sessions.forEach(
      (session, index) => {
        totalSessions++;

        if (index > 0) {
          const separator =
            document.createElement(
              "span"
            );

          separator.className =
            "occasional-separator";

          separator.textContent =
            ",";

          sessionsWrap.appendChild(
            separator
          );
        }

        const dt =
          new Date(
            session.start
          );

        const date =
          document.createElement(
            "span"
          );

        date.className =
          "occasional-date";

        date.textContent =
          formatShortDate(dt);

        sessionsWrap.appendChild(
          date
        );

        sessionsWrap.appendChild(
          createSessionNode(
            session
          )
        );
      }
    );

    row.appendChild(
      sessionsWrap
    );

    list.appendChild(row);
  }

  container.appendChild(list);

  return totalSessions;
}

function render() {
  const start =
    startOfToday();

  const days =
    Array.from(
      { length: 5 },
      (_, i) =>
        addDays(start, i)
    );

  buildDayHeaders(days);

  const events =
    visibleEvents();

  const films =
    groupByFilm(events);

  const mainFilms =
    films.filter(
      film =>
        filmSessionCount(film)
        >= 5
    );

  const occasionalFilms =
    films.filter(
      film =>
        filmSessionCount(film)
        < 5
    );

  const mainSessions =
    renderMainTable(
      mainFilms,
      days
    );

  const occasionalSessions =
    renderOccasional(
      occasionalFilms
    );

  const status =
    el("cinemaStatus");

  if (status) {
    const total =
      mainSessions +
      occasionalSessions;

    status.textContent =
      `${films.length} film${films.length > 1 ? "s" : ""} · ` +
      `${total} séance${total > 1 ? "s" : ""}`;
  }
}

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

  } catch (err) {
    console.error(err);

    const status =
      el("cinemaStatus");

    if (status) {
      status.textContent =
        "Erreur : " +
        err.message;
    }
  }
}

el("cinemaSearch")
  ?.addEventListener(
    "input",
    render
  );

el("afterWorkOnly")
  ?.addEventListener(
    "change",
    render
  );

init();
