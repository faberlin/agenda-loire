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

function dateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
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
  return new Set(
    [...document.querySelectorAll(
      '#cinemaFilters input[type="checkbox"]:checked'
    )].map(input => input.value)
  );
}

function buildCinemaFilters() {
  const container = el("cinemaFilters");
  container.innerHTML = "";

  const names = [...new Set(
    cinemaEvents.map(event => event.cinema).filter(Boolean)
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

function buildWeekHeader(days) {
  const row = el("cinemaWeekHeader");
  row.innerHTML = '<th class="film-col">Film</th>';

  const today = startOfToday();

  for (const day of days) {
    const th = document.createElement("th");
    th.className = "day-col";
    if (sameDay(day, today)) th.classList.add("today-col");
    th.textContent = formatHeaderDay(day);
    row.appendChild(th);
  }
}

function visibleEvents() {
  const search = normalize(el("cinemaSearch").value);
  const afterWorkOnly = el("afterWorkOnly").checked;
  const cinemas = selectedCinemas();
  const start = startOfToday();
  const end = addDays(start, 7);

  return cinemaEvents.filter(event => {
    const dt = new Date(event.start);

    if (Number.isNaN(dt.getTime())) return false;
    if (dt < start || dt >= end) return false;

    if (
      afterWorkOnly
      && isWeekday(dt)
      && dt.getHours() < 17
    ) {
      return false;
    }

    if (
      cinemas.size > 0
      && !cinemas.has(event.cinema)
    ) {
      return false;
    }

    if (
      search
      && !normalize(event.title).includes(search)
    ) {
      return false;
    }

    return true;
  });
}

function groupByFilmAndCinema(events) {
  const groups = new Map();

  for (const event of events) {
    const key = `${event.title}|||${event.cinema}`;

    if (!groups.has(key)) {
      groups.set(key, {
        title: event.title,
        cinema: event.cinema,
        sessions: []
      });
    }

    groups.get(key).sessions.push(event);
  }

  return [...groups.values()].sort((a, b) => {
    const titleCompare = a.title.localeCompare(b.title, "fr");
    if (titleCompare !== 0) return titleCompare;
    return a.cinema.localeCompare(b.cinema, "fr");
  });
}

function render() {
  const start = startOfToday();
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

  buildWeekHeader(days);

  const body = el("cinemaWeekBody");
  body.innerHTML = "";

  const events = visibleEvents();
  const groups = groupByFilmAndCinema(events);

  let sessionCount = 0;
  const today = startOfToday();

  for (const group of groups) {
    const tr = document.createElement("tr");

    const filmTd = document.createElement("td");
    filmTd.className = "film-col";

    const title = document.createElement("span");
    title.className = "film-title";
    title.textContent = group.title;

    const cinema = document.createElement("span");
    cinema.className = "film-cinema";
    cinema.textContent = group.cinema;

    filmTd.appendChild(title);
    filmTd.appendChild(cinema);
    tr.appendChild(filmTd);

    for (const day of days) {
      const td = document.createElement("td");
      td.className = "sessions-cell";
      if (sameDay(day, today)) td.classList.add("today-col");

      const sessions = group.sessions
        .filter(session => sameDay(new Date(session.start), day))
        .sort((a, b) => new Date(a.start) - new Date(b.start));

      if (!sessions.length) {
        const empty = document.createElement("span");
        empty.className = "no-session";
        empty.textContent = "—";
        td.appendChild(empty);
      } else {
        const list = document.createElement("div");
        list.className = "session-list";

        for (const session of sessions) {
          sessionCount++;

          const dt = new Date(session.start);
          const node = document.createElement(session.url ? "a" : "span");
          node.className = "session-time";

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
      }

      tr.appendChild(td);
    }

    body.appendChild(tr);
  }

  if (!groups.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 8;
    td.className = "cinema-empty";
    td.textContent = "Aucune séance pour ces filtres.";
    tr.appendChild(td);
    body.appendChild(tr);
  }

  el("cinemaStatus").textContent =
    `${groups.length} film${groups.length > 1 ? "s" : ""} · `
    + `${sessionCount} séance${sessionCount > 1 ? "s" : ""}`;
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
    el("cinemaStatus").textContent =
      "Erreur : " + err.message;
  }
}

el("cinemaSearch").addEventListener("input", render);
el("afterWorkOnly").addEventListener("change", render);

init();
