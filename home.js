const el = id => document.getElementById(id);

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

function normalize(value) {
  return (value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function countFilms(events) {
  const start = startOfToday();
  const end = addDays(start, 7);
  const films = new Set();

  for (const event of events) {
    if (!event?.start || !event?.title) continue;

    const date = new Date(event.start);
    if (Number.isNaN(date.getTime())) continue;
    if (date < start || date >= end) continue;

    films.add(normalize(event.title));
  }

  return films.size;
}

function eventSessions(event) {
  if (Array.isArray(event.sessions) && event.sessions.length) {
    return event.sessions;
  }

  return event.start ? [event.start] : [];
}

function isEventInNext7Days(event, start, end) {
  return eventSessions(event).some(value => {
    const date = new Date(value);
    return !Number.isNaN(date.getTime()) && date >= start && date < end;
  });
}

function countShows(events) {
  const start = startOfToday();
  const end = addDays(start, 7);
  const shows = new Set();

  for (const event of events) {
    if (!event?.title) continue;
    if (!isEventInNext7Days(event, start, end)) continue;

    const key =
      event.id ||
      `${normalize(event.title)}|${normalize(event.venue || event.source || "")}`;

    shows.add(key);
  }

  return shows.size;
}

async function init() {
  try {
    const [cinemaResponse, showsResponse] = await Promise.all([
      fetch("cinema_events.json", { cache: "no-store" }),
      fetch("events.json", { cache: "no-store" })
    ]);

    if (!cinemaResponse.ok) {
      throw new Error("Impossible de charger cinema_events.json");
    }

    if (!showsResponse.ok) {
      throw new Error("Impossible de charger events.json");
    }

    const cinemaEvents = await cinemaResponse.json();
    const showEvents = await showsResponse.json();

    el("homeFilmCount").textContent = countFilms(cinemaEvents);
    el("homeShowCount").textContent = countShows(showEvents);

  } catch (error) {
    console.error(error);

    if (el("homeFilmCount")) {
      el("homeFilmCount").textContent = "?";
    }

    if (el("homeShowCount")) {
      el("homeShowCount").textContent = "?";
    }
  }
}

init();
