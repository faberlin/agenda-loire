let planningEvents = [];
let currentWeekStart = getStartOfWeek(new Date());

const el = id => document.getElementById(id);

function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function getStartOfWeek(date) {
  const d = startOfDay(date);
  const day = d.getDay(); // 0 dimanche, 1 lundi...
  const diff = day === 0 ? -6 : 1 - day; // lundi = début de semaine
  d.setDate(d.getDate() + diff);
  return d;
}

function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatRange(start) {
  const end = addDays(start, 6);

  const sameMonth = start.getMonth() === end.getMonth();
  const sameYear = start.getFullYear() === end.getFullYear();

  const startDay = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric"
  }).format(start);

  const startMonth = new Intl.DateTimeFormat("fr-FR", {
    month: "short"
  }).format(start);

  const endDay = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric"
  }).format(end);

  const endMonth = new Intl.DateTimeFormat("fr-FR", {
    month: "short"
  }).format(end);

  const year = new Intl.DateTimeFormat("fr-FR", {
    year: "numeric"
  }).format(end);

  if (sameMonth && sameYear) {
    return `${startDay} ${startMonth} — ${endDay} ${endMonth} ${year}`;
  }

  if (sameYear) {
    return `${startDay} ${startMonth} — ${endDay} ${endMonth} ${year}`;
  }

  const startYear = new Intl.DateTimeFormat("fr-FR", {
    year: "numeric"
  }).format(start);

  return `${startDay} ${startMonth} ${startYear} — ${endDay} ${endMonth} ${year}`;
}

function formatDayTitle(date) {
  let s = new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short"
  }).format(date);

  s = s.replace(/\./g, "");
  return s.toUpperCase();
}

function formatTime(date) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
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

function categoryClass(category) {
  const c = normalize(category);

  if (c.includes("musique") || c.includes("concert")) return "cat-musique";
  if (c.includes("theatre") || c.includes("opéra") || c.includes("opera")) return "cat-theatre";
  if (c.includes("danse")) return "cat-danse";
  if (c.includes("litterature")) return "cat-litterature";
  if (c.includes("humour")) return "cat-humour";
  if (c.includes("exposition")) return "cat-exposition";

  return "cat-default";
}

function eventsOfSelectedWeek() {
  const weekStart = startOfDay(currentWeekStart);
  const weekEnd = addDays(weekStart, 7);

  return planningEvents
    .filter(ev => {
      if (!ev.start) return false;

      const d = new Date(ev.start);

      if (Number.isNaN(d.getTime())) return false;

      return d >= weekStart && d < weekEnd;
    })
    .sort((a, b) => new Date(a.start) - new Date(b.start));
}

function groupEventsByDay(events) {
  const days = [];

  for (let i = 0; i < 7; i++) {
    const day = addDays(currentWeekStart, i);

    const dayEvents = events.filter(ev =>
      sameDay(new Date(ev.start), day)
    );

    if (dayEvents.length > 0) {
      days.push({
        date: day,
        events: dayEvents
      });
    }
  }

  return days;
}

function renderEventRow(ev) {
  const article = document.createElement("article");
  article.className = `planning-event ${categoryClass(ev.category)}`;

  const time = formatTime(new Date(ev.start));
  const venue = ev.venue || ev.source || "";
  const title = ev.title || "Événement";

  const content = `
    <span class="planning-event-time">${escapeHtml(time)}</span>
    <span class="planning-event-title">${escapeHtml(title)}</span>
    ${venue ? `<span class="planning-event-sep">·</span><span class="planning-event-venue">${escapeHtml(venue)}</span>` : ""}
  `;

  if (ev.url) {
    const link = document.createElement("a");
    link.href = ev.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "planning-event-link";
    link.innerHTML = content;
    article.appendChild(link);
  } else {
    article.innerHTML = content;
  }

  return article;
}

function renderDayCard(dayBlock) {
  const section = document.createElement("section");
  section.className = "planning-day-card";

  const title = document.createElement("h2");
  title.className = "planning-day-title";
  title.textContent = formatDayTitle(dayBlock.date);
  section.appendChild(title);

  const list = document.createElement("div");
  list.className = "planning-day-events";

  for (const ev of dayBlock.events) {
    list.appendChild(renderEventRow(ev));
  }

  section.appendChild(list);

  return section;
}

function render() {
  const events = eventsOfSelectedWeek();
  const grouped = groupEventsByDay(events);

  const grid = el("planningGrid");
  const status = el("planningStatus");
  const range = el("planningRange");

  range.textContent = formatRange(currentWeekStart);

  if (status) {
    status.textContent = `${events.length} événement${events.length > 1 ? "s" : ""} · ${grouped.length} jour${grouped.length > 1 ? "s" : ""}`;
  }

  grid.innerHTML = "";

  if (!grouped.length) {
    const empty = document.createElement("div");
    empty.className = "planning-empty";
    empty.textContent = "Aucun événement sur cette semaine.";
    grid.appendChild(empty);
    return;
  }

  for (const dayBlock of grouped) {
    grid.appendChild(renderDayCard(dayBlock));
  }
}

async function init() {
  try {
    const res = await fetch("events.json", { cache: "no-store" });

    if (!res.ok) {
      throw new Error("Impossible de charger events.json");
    }

    const data = await res.json();

    if (!Array.isArray(data)) {
      throw new Error("events.json n'a pas le bon format");
    }

    planningEvents = data
      .filter(ev => ev && ev.start)
      .sort((a, b) => new Date(a.start) - new Date(b.start));

    render();
  } catch (err) {
    console.error(err);

    const grid = el("planningGrid");
    grid.innerHTML = "";

    const empty = document.createElement("div");
    empty.className = "planning-empty";
    empty.textContent = "Erreur : " + err.message;
    grid.appendChild(empty);
  }
}

el("prevWeekBtn")?.addEventListener("click", () => {
  currentWeekStart = addDays(currentWeekStart, -7);
  render();
});

el("nextWeekBtn")?.addEventListener("click", () => {
  currentWeekStart = addDays(currentWeekStart, 7);
  render();
});

el("todayBtn")?.addEventListener("click", () => {
  currentWeekStart = getStartOfWeek(new Date());
  render();
});

init();
