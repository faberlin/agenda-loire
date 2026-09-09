let exhibitions = [];

const el = id => document.getElementById(id);

function normalize(value) {
  return (value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function parseDate(value) {
  if (!value) return null;

  const d = new Date(value + (value.length === 10 ? "T12:00:00" : ""));
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDate(value) {
  const d = parseDate(value);
  if (!d) return null;

  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric"
  }).format(d);
}

function exhibitionPeriod(exhibition) {
  const start = formatDate(exhibition.start);
  const end = formatDate(exhibition.end);

  if (start && end) {
    return `${start} → ${end}`;
  }

  if (end) {
    return `jusqu’au ${end}`;
  }

  if (start) {
    return `à partir du ${start}`;
  }

  return "en cours";
}

function selectedTypes() {
  const types = new Set();

  if (el("filterMusees")?.checked) {
    types.add("musee");
  }

  if (el("filterGaleries")?.checked) {
    types.add("galerie");
  }

  return types;
}

function isVisible(exhibition) {
  const types = selectedTypes();

  if (!types.size) {
    return true;
  }

  return types.has(
    normalize(exhibition.type)
      .replace("musée", "musee")
  );
}

function classify(exhibition) {
  const today = startOfToday();

  if (exhibition.status === "upcoming") {
    return "upcoming";
  }

  if (exhibition.status === "current") {
    return "current";
  }

  const start = parseDate(exhibition.start);
  const end = parseDate(exhibition.end);

  if (start && start > today) {
    return "upcoming";
  }

  if (!end || end >= today) {
    return "current";
  }

  return "past";
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function createRow(exhibition) {
  const row = document.createElement("article");
  row.className = "expo-row";

  const venue = exhibition.venue || exhibition.source || "";
  const city = exhibition.city || "";

  row.innerHTML = `
    <div class="expo-content">
      <span class="expo-type">${escapeHtml(exhibition.type || "Musée")}</span>

      <span class="expo-title">${escapeHtml(exhibition.title)}</span>

      <span class="expo-separator">·</span>
      <span class="expo-meta">${escapeHtml(exhibitionPeriod(exhibition))}</span>

      ${venue ? `
        <span class="expo-separator">·</span>
        <span class="expo-meta">${escapeHtml(venue)}</span>
      ` : ""}

      ${city ? `
        <span class="expo-separator">·</span>
        <span class="expo-meta">${escapeHtml(city)}</span>
      ` : ""}
    </div>

    ${exhibition.url ? `
      <a
        class="expo-source"
        href="${escapeAttr(exhibition.url)}"
        target="_blank"
        rel="noopener"
      >Source</a>
    ` : ""}
  `;

  return row;
}

function renderList(containerId, items, emptyText) {
  const container = el(containerId);
  container.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "expo-empty";
    empty.textContent = emptyText;
    container.appendChild(empty);
    return;
  }

  for (const exhibition of items) {
    container.appendChild(createRow(exhibition));
  }
}

function render() {
  const visible = exhibitions.filter(isVisible);

  const current = visible
    .filter(item => classify(item) === "current")
    .sort((a, b) =>
      (parseDate(a.end)?.getTime() || Number.MAX_SAFE_INTEGER) -
      (parseDate(b.end)?.getTime() || Number.MAX_SAFE_INTEGER)
    );

  const upcoming = visible
    .filter(item => classify(item) === "upcoming")
    .sort((a, b) =>
      (parseDate(a.start)?.getTime() || Number.MAX_SAFE_INTEGER) -
      (parseDate(b.start)?.getTime() || Number.MAX_SAFE_INTEGER)
    );

  renderList(
    "currentExhibitions",
    current,
    "Aucune exposition en cours."
  );

  renderList(
    "upcomingExhibitions",
    upcoming,
    "Aucune exposition à venir."
  );

  el("expoStatus").textContent =
    `${current.length} en cours · ${upcoming.length} à venir`;
}

async function init() {
  try {
    const response = await fetch(
      "expositions.json",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error("Impossible de charger expositions.json");
    }

    exhibitions = await response.json();

    if (!Array.isArray(exhibitions)) {
      throw new Error("expositions.json n'a pas le bon format");
    }

    render();

  } catch (error) {
    console.error(error);
    el("expoStatus").textContent =
      "Erreur au chargement des expositions.";
  }
}

["filterMusees", "filterGaleries"].forEach(id => {
  el(id)?.addEventListener("change", render);
});

init();
