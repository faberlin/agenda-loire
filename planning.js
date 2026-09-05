let events = [];
let weekStart = startOfWeek(new Date());

function startOfWeek(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
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

function categoryClass(category) {
  return "cat-" + String(category || "spectacle")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function formatDayHeader(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short"
  }).format(date);
}

function formatTime(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function formatWeekLabel(start) {
  const end = addDays(start, 6);

  const startText = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short"
  }).format(start);

  const endText = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric"
  }).format(end);

  return `${startText} — ${endText}`;
}

function expandEventSessions(ev) {
  if (Array.isArray(ev.sessions)) {
    return ev.sessions.map(session => ({
      ...ev,
      sessionDate: new Date(session)
    }));
  }

  return [{
    ...ev,
    sessionDate: new Date(ev.start)
  }];
}

function renderWeek() {
  const grid = document.getElementById("weekGrid");
  const weekLabel = document.getElementById("weekLabel");
  const today = new Date();

  weekLabel.textContent = formatWeekLabel(weekStart);
  grid.innerHTML = "";

  const expanded = events.flatMap(expandEventSessions);

  for (let i = 0; i < 7; i++) {
    const dayDate = addDays(weekStart, i);
    const day = document.createElement("section");
    day.className = "day" + (sameDay(dayDate, today) ? " today" : "");

    const header = document.createElement("div");
    header.className = "day-header";
    header.textContent = formatDayHeader(dayDate);
    day.appendChild(header);

    const dayEvents = document.createElement("div");
    dayEvents.className = "day-events";

    const matches = expanded
      .filter(ev => sameDay(ev.sessionDate, dayDate))
      .sort((a, b) => a.sessionDate - b.sessionDate);

    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "—";
      dayEvents.appendChild(empty);
    } else {
      for (const ev of matches) {
        const row = document.createElement(ev.url ? "a" : "div");
        row.className = `event ${categoryClass(ev.category)}`;

        if (ev.url) {
          row.href = ev.url;
          row.target = "_blank";
          row.rel = "noopener";
        }

        const venue = ev.venue ? ` · ${ev.venue}` : "";
        row.innerHTML = `
          <span class="event-time">${formatTime(ev.sessionDate)}</span>
          <span>${escapeHtml(ev.title)}</span>
          <span class="event-venue">${escapeHtml(venue)}</span>
        `;

        row.title = [
          formatTime(ev.sessionDate),
          ev.title,
          ev.venue || "",
          ev.category || ""
        ].filter(Boolean).join(" · ");

        dayEvents.appendChild(row);
      }
    }

    day.appendChild(dayEvents);
    grid.appendChild(day);
  }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[c]));
}

async function init() {
  const response = await fetch("events.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Impossible de charger events.json");
  }

  events = await response.json();
  renderWeek();
}

document.getElementById("prevWeek").addEventListener("click", () => {
  weekStart = addDays(weekStart, -7);
  renderWeek();
});

document.getElementById("nextWeek").addEventListener("click", () => {
  weekStart = addDays(weekStart, 7);
  renderWeek();
});

document.getElementById("todayWeek").addEventListener("click", () => {
  weekStart = startOfWeek(new Date());
  renderWeek();
});

init().catch(err => {
  console.error(err);
  document.getElementById("weekGrid").innerHTML =
    `<div class="empty">Erreur : ${escapeHtml(err.message)}</div>`;
});
