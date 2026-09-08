let cinemaEvents = [];

const el = id => document.getElementById(id);

function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function formatDay(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long"
  }).format(date);
}

function formatTime(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function dateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
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

function groupedVisibleEvents() {
  const search = normalize(el("cinemaSearch").value);
  const afterWorkOnly = el("afterWorkOnly").checked;
  const cinemas = selectedCinemas();

  const visible = cinemaEvents.filter(event => {
    const dt = new Date(event.start);

    if (Number.isNaN(dt.getTime())) return false;

    if (
      afterWorkOnly
      && isWeekday(dt)
      && (dt.getHours() < 17)
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

  // jour -> film+cinéma -> séances
  const days = new Map();

  for (const event of visible) {
    const dt = new Date(event.start);
    const day = dateKey(dt);

    if (!days.has(day)) {
      days.set(day, {
        date: new Date(
          dt.getFullYear(),
          dt.getMonth(),
          dt.getDate()
        ),
        films: new Map()
      });
    }

    const filmKey = `${event.title}|||${event.cinema}`;

    if (!days.get(day).films.has(filmKey)) {
      days.get(day).films.set(filmKey, {
        title: event.title,
        cinema: event.cinema,
        sessions: []
      });
    }

    days.get(day).films.get(filmKey).sessions.push(event);
  }

  return days;
}

function render() {
  const container = el("cinemaDays");
  const days = groupedVisibleEvents();

  container.innerHTML = "";

  let totalSessions = 0;

  for (const [, dayData] of days) {
    const daySection = document.createElement("section");
    daySection.className = "cinema-day";

    const header = document.createElement("div");
    header.className = "cinema-day-header";

    let label = formatDay(dayData.date);
    label = label.charAt(0).toUpperCase() + label.slice(1);
    header.textContent = label;

    const list = document.createElement("div");
    list.className = "cinema-list";

    const films = [...dayData.films.values()]
      .sort((a, b) => {
        const firstA = new Date(a.sessions[0].start);
        const firstB = new Date(b.sessions[0].start);
        return firstA - firstB;
      });

    for (const film of films) {
      film.sessions.sort(
        (a, b) => new Date(a.start) - new Date(b.start)
      );

      totalSessions += film.sessions.length;

      const row = document.createElement("div");
      row.className = "cinema-film";

      const title = document.createElement("div");
      title.className = "cinema-title";
      title.textContent = film.title;

      const cinema = document.createElement("div");
      cinema.className = "cinema-name";
      cinema.textContent = film.cinema;

      const times = document.createElement("div");
      times.className = "cinema-times";

      for (const session of film.sessions) {
        const dt = new Date(session.start);

        const time = document.createElement(
          session.url ? "a" : "span"
        );
        time.className = "cinema-time";

        if (session.url) {
          time.href = session.url;
          time.target = "_blank";
          time.rel = "noopener";
        }

        const hour = document.createElement("span");
        hour.textContent = formatTime(dt);
        time.appendChild(hour);

        if (session.version) {
          const version = document.createElement("span");
          version.className = "cinema-version";
          version.textContent = session.version;
          time.appendChild(version);
        }

        times.appendChild(time);
      }

      row.appendChild(title);
      row.appendChild(cinema);
      row.appendChild(times);

      list.appendChild(row);
    }

    daySection.appendChild(header);
    daySection.appendChild(list);
    container.appendChild(daySection);
  }

  if (!days.size) {
    container.innerHTML =
      '<div class="cinema-empty">Aucune séance pour ces filtres.</div>';
  }

  el("cinemaStatus").textContent =
    `${totalSessions} séance${totalSessions > 1 ? "s" : ""} affichée${totalSessions > 1 ? "s" : ""}`;
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
