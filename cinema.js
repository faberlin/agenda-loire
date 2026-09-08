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
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function formatHeaderDay(date) {
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
  if (!container) return new Set();

  return new Set(
    [...container.querySelectorAll('input[type="checkbox"]:checked')]
      .map(input => input.value)
  );
}

function cinemaGroupName(name) {
  if (
    name === "Méliès Jean-Jaurès" ||
    name === "Méliès Saint-François"
  ) {
    return "Méliès";
  }

  return name || "Cinéma";
}

function sessionCinemaClass(session) {
  if (session.cinema === "Méliès Saint-François") {
    return "session-sf";
  }

  if (session.cinema === "Méliès Jean-Jaurès") {
    return "session-jj";
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

  const names = [...new Set(
    cinemaEvents
      .map(event => event.cinema)
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, "fr"));

  for (const name of names) {
    const label = document.createElement("label");
    label.className = "cinema-filter-check";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = name;
    input.addEventListener("change", render);

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

  row.innerHTML = '<th class="film-col">Film / cinéma</th>';

  const today = startOfToday();

  for (const day of days) {
    const th = document.createElement("th");
    th.className = "day-col";

    if (sameDay(day, today)) {
      th.classList.add("today-col");
    }

    th.textContent = formatHeaderDay(day);
    row.appendChild(th);
  }
}

function visibleEvents() {
  const searchInput = el("cinemaSearch");
  const afterWorkInput = el("afterWorkOnly");

  const search = normalize(searchInput ? searchInput.value : "");
  const afterWorkOnly = afterWorkInput ? afterWorkInput.checked : false;
  const cinemas = selectedCinemas();

  const start = startOfToday();
  const end = addDays(start, 5);

  return cinemaEvents.filter(event => {
    const dt = new Date(event.start);

    if (Number.isNaN(dt.getTime())) return false;
    if (dt < start || dt >= end) return false;

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
      !normalize(event.title).includes(search)
    ) {
      return false;
    }

    return true;
  });
}

function groupByFilmThenCinema(events) {
  const films = new Map();

  for (const event of events) {
    const filmKey = normalize(event.title);

    if (!films.has(filmKey)) {
      films.set(filmKey, {
        title: event.title,
        cinemas: new Map()
      });
    }

    const film = films.get(filmKey);
    const cinemaKey = cinemaGroupName(event.cinema);

    if (!film.cinemas.has(cinemaKey)) {
      film.cinemas.set(cinemaKey, []);
    }

    film.cinemas.get(cinemaKey).push(event);
  }

return [...films.values()].sort((a, b) => {
  const countA = [...a.cinemas.values()]
    .reduce((sum, sessions) => sum + sessions.length, 0);

  const countB = [...b.cinemas.values()]
    .reduce((sum, sessions) => sum + sessions.length, 0);

  if (countB !== countA) {
    return countB - countA;
  }

  return a.title.localeCompare(b.title, "fr");
});
}

function renderSessionCell(td, sessions) {
  if (!sessions.length) {
    const empty = document.createElement("span");
    empty.className = "no-session";
    empty.textContent = "—";
    td.appendChild(empty);
    return 0;
  }

  sessions.sort((a, b) => new Date(a.start) - new Date(b.start));

  const list = document.createElement("div");
  list.className = "session-list";

  for (const session of sessions) {
    const dt = new Date(session.start);

    const node = document.createElement(
      session.url ? "a" : "span"
    );

    const cinemaClass = sessionCinemaClass(session);

    node.className = cinemaClass
      ? `session-time ${cinemaClass}`
      : "session-time";

    if (session.url) {
      node.href = session.url;
      node.target = "_blank";
      node.rel = "noopener";
    }

    const hour = document.createElement("span");
    hour.textContent = formatTime(dt);
    node.appendChild(hour);

    if (session.version) {
      const version = document.createElement("span");
      version.className = "session-version";
      version.textContent = session.version;
      node.appendChild(version);
    }

    list.appendChild(node);
  }

  td.appendChild(list);
  return sessions.length;
}

function render() {
  const start = startOfToday();

  const days = Array.from(
    { length: 5 },
    (_, i) => addDays(start, i)
  );

  buildDayHeaders(days);

  const body = el("cinemaWeekBody");

  if (!body) {
    throw new Error(
      "cinema.html et cinema.js ne correspondent pas : #cinemaWeekBody absent"
    );
  }

  body.innerHTML = "";

  const events = visibleEvents();
  const films = groupByFilmThenCinema(events);

  let totalSessions = 0;
  let filmCount = 0;

  const today = startOfToday();

  for (const film of films) {
    filmCount++;

    const cinemaEntries = [...film.cinemas.entries()]
      .sort((a, b) => a[0].localeCompare(b[0], "fr"));

    cinemaEntries.forEach(([cinemaName, sessions], index) => {
      const tr = document.createElement("tr");

      tr.className =
        index === 0
          ? "film-start-row"
          : "film-sub-row";

      const firstTd = document.createElement("td");
      firstTd.className = "film-col";

      if (index === 0) {
        const title = document.createElement("span");
        title.className = "film-title";
        title.textContent = film.title;
        firstTd.appendChild(title);
      }

      const cinema = document.createElement("span");
      cinema.className = "film-cinema";
      cinema.textContent = cinemaName;
      firstTd.appendChild(cinema);

      tr.appendChild(firstTd);

      for (const day of days) {
        const td = document.createElement("td");
        td.className = "sessions-cell";

        if (sameDay(day, today)) {
          td.classList.add("today-col");
        }

        const daySessions = sessions.filter(session =>
          sameDay(new Date(session.start), day)
        );

        totalSessions += renderSessionCell(
          td,
          daySessions
        );

        tr.appendChild(td);
      }

      body.appendChild(tr);
    });
  }

  if (!films.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");

    td.colSpan = 6;
    td.className = "cinema-empty";
    td.textContent = "Aucune séance pour ces filtres.";

    tr.appendChild(td);
    body.appendChild(tr);
  }

  const status = el("cinemaStatus");

  if (status) {
    status.textContent =
      `${filmCount} film${filmCount > 1 ? "s" : ""} · ` +
      `${totalSessions} séance${totalSessions > 1 ? "s" : ""}`;
  }
}

async function init() {
  try {
    const response = await fetch(
      "cinema_events.json",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        "Impossible de charger cinema_events.json"
      );
    }

    cinemaEvents = await response.json();

    if (!Array.isArray(cinemaEvents)) {
      throw new Error(
        "cinema_events.json n'a pas le bon format"
      );
    }

    cinemaEvents.sort(
      (a, b) => new Date(a.start) - new Date(b.start)
    );

    buildCinemaFilters();
    render();

  } catch (err) {
    console.error(err);

    const status = el("cinemaStatus");

    if (status) {
      status.textContent =
        "Erreur : " + err.message;
    }
  }
}

el("cinemaSearch")?.addEventListener(
  "input",
  render
);

el("afterWorkOnly")?.addEventListener(
  "change",
  render
);

init();
