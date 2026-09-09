let cinemaEvents = [];


const el = id =>
  document.getElementById(id);



/* =======================================================
   OUTILS
   ======================================================= */


function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}


function startOfToday() {
  const d = new Date();

  d.setHours(
    0,
    0,
    0,
    0
  );

  return d;
}


function addDays(date, days) {
  const d =
    new Date(date);

  d.setDate(
    d.getDate() + days
  );

  return d;
}


function sameDay(a, b) {
  return (
    a.getFullYear() ===
      b.getFullYear() &&

    a.getMonth() ===
      b.getMonth() &&

    a.getDate() ===
      b.getDate()
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
  const day =
    date.getDay();

  return (
    day >= 1 &&
    day <= 5
  );
}



/* =======================================================
   CINÉMAS
   ======================================================= */


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
    normalize(
      session.cinema
    );


  /* Méliès Saint-François */

  if (
    cinema.includes("melies") &&
    (
      cinema.includes("saint-francois") ||
      cinema.includes("saint francois")
    )
  ) {
    return "session-sf";
  }


  /* Méliès Jean-Jaurès */

  if (
    cinema.includes("melies") &&
    (
      cinema.includes("jean-jaures") ||
      cinema.includes("jean jaures")
    )
  ) {
    return "session-melies-jj";
  }


  /* Mégarama Camion Rouge */

  if (
    cinema.includes("megarama") &&
    (
      cinema.includes("camion") ||
      cinema.includes("chavanelle")
    )
  ) {
    return "session-mega-cr";
  }


  /* Mégarama Jean-Jaurès */

  if (
    cinema.includes("megarama") &&
    (
      cinema.includes("jean-jaures") ||
      cinema.includes("jean jaures")
    )
  ) {
    return "session-mega-jj";
  }


  return "";
}



/* =======================================================
   VERSION VF / VO
   ======================================================= */


function isOriginalVersion(session) {

  const version =
    normalize(
      session.version
    )
      .replace(/\s/g, "");


  return (
    version === "vo" ||
    version === "vost" ||
    version === "vostf" ||
    version === "vostfr"
  );
}


function isVF(session) {

  const version =
    normalize(
      session.version
    )
      .replace(/\s/g, "");

  return version === "vf";
}



/*
Pour chaque film :

si au moins UNE séance Mégarama
existe en VO/VOST sur les 7 jours
contenus dans cinema_events.json,

on enlève toutes les séances VF
de ce film au Mégarama.

Les séances Méliès ne sont jamais
supprimées par cette règle.
*/


function filterMegaramaVF(events) {

  const filmsWithVO =
    new Set();


  for (const session of events) {

    if (
      !isMegaramaSession(session)
    ) {
      continue;
    }

    if (
      isOriginalVersion(session)
    ) {

      filmsWithVO.add(
        normalize(session.title)
      );

    }
  }


  return events.filter(
    session => {

      if (
        !isMegaramaSession(session)
      ) {
        return true;
      }


      const filmKey =
        normalize(session.title);


      if (
        !filmsWithVO.has(filmKey)
      ) {
        return true;
      }


      return !isVF(session);
    }
  );
}



/* =======================================================
   FILTRES CINÉMAS
   ======================================================= */


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
      input =>
        input.value
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
        .map(
          event =>
            event.cinema
        )
        .filter(Boolean)

    )

  ].sort(
    (a, b) =>
      a.localeCompare(
        b,
        "fr"
      )
  );


  for (const name of names) {

    const label =
      document.createElement(
        "label"
      );

    label.className =
      "cinema-filter-check";


    const input =
      document.createElement(
        "input"
      );

    input.type =
      "checkbox";

    input.value =
      name;

    input.addEventListener(
      "change",
      render
    );


    const span =
      document.createElement(
        "span"
      );

    span.textContent =
      name;


    label.appendChild(
      input
    );

    label.appendChild(
      span
    );


    container.appendChild(
      label
    );
  }
}



/* =======================================================
   FILTRAGE DES SÉANCES VISIBLES
   ======================================================= */


function visibleEvents() {

  /*
  IMPORTANT :

  Le filtrage VF / VO se fait d'abord
  sur cinemaEvents complet.

  On utilise donc bien les 7 jours
  présents dans le JSON.
  */

  const filteredVersions =
    filterMegaramaVF(
      cinemaEvents
    );


  const afterWorkInput =
    el("afterWorkOnly");


  const afterWorkOnly =
    afterWorkInput
      ? afterWorkInput.checked
      : false;


  const cinemas =
    selectedCinemas();


  const start =
    startOfToday();


  /*
  La page affiche aujourd'hui
  + les 4 jours suivants.
  */

  const end =
    addDays(
      start,
      5
    );


  return filteredVersions.filter(
    event => {

      const dt =
        new Date(
          event.start
        );


      if (
        Number.isNaN(
          dt.getTime()
        )
      ) {
        return false;
      }


      if (
        dt < start ||
        dt >= end
      ) {
        return false;
      }


      /*
      Lundi à vendredi :

      si l'option est cochée,
      on masque avant 17h.
      */

      if (
        afterWorkOnly &&
        isWeekday(dt) &&
        dt.getHours() < 17
      ) {
        return false;
      }


      /*
      Si aucun cinéma n'est coché :
      on affiche tout.

      Si au moins un est coché :
      on affiche uniquement ceux cochés.
      */

      if (
        cinemas.size > 0 &&
        !cinemas.has(
          event.cinema
        )
      ) {
        return false;
      }


      return true;
    }
  );
}



/* =======================================================
   REGROUPEMENT PAR FILM
   ======================================================= */


function groupByFilm(events) {

  const films =
    new Map();


  for (const event of events) {

    const filmKey =
      normalize(
        event.title
      );


    if (
      !films.has(
        filmKey
      )
    ) {

      films.set(
        filmKey,
        {
          title:
            event.title,

          sessions:
            []
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
  ];
}



/* =======================================================
   TRI DES FILMS
   ======================================================= */


function sortMainFilms(films) {

  return films.sort(
    (a, b) => {

      const aMelies =
        a.sessions.some(
          isMeliesSession
        );

      const bMelies =
        b.sessions.some(
          isMeliesSession
        );


      /*
      Les films du Méliès passent
      avant les films uniquement Mégarama.
      */

      if (
        aMelies !== bMelies
      ) {

        return aMelies
          ? -1
          : 1;
      }


      /*
      Ensuite :
      films avec le plus de séances.
      */

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
}



/* =======================================================
   SÉPARATION TABLEAU / GROSSES SORTIES
   ======================================================= */


function splitFilms(films) {

  const mainFilms = [];

  const bigReleases = [];


  for (const film of films) {

    const hasMelies =
      film.sessions.some(
        isMeliesSession
      );


    /*
    Dès qu'un film passe au Méliès,
    il reste toujours dans le tableau.

    Cela inclut également ses éventuelles
    séances Mégarama.
    */

    if (hasMelies) {

      mainFilms.push(
        film
      );

      continue;
    }


    /*
    Ici le film est uniquement Mégarama.

    1 à 4 séances :
    programmation ponctuelle,
    donc on la garde dans le tableau.

    5 séances ou plus :
    grosse sortie Mégarama.
    */

    if (
      film.sessions.length <= 4
    ) {

      mainFilms.push(
        film
      );

    } else {

      bigReleases.push(
        film
      );
    }
  }


  sortMainFilms(
    mainFilms
  );


  bigReleases.sort(
    (a, b) =>
      a.title.localeCompare(
        b.title,
        "fr"
      )
  );


  return {
    mainFilms,
    bigReleases
  };
}



/* =======================================================
   EN-TÊTE DES JOURS
   ======================================================= */


function buildDayHeaders(days) {

  const row =
    el("cinemaWeekHeader");


  if (!row) {
    return;
  }


  row.innerHTML =
    '<th class="film-col">Film</th>';


  const today =
    startOfToday();


  for (const day of days) {

    const th =
      document.createElement(
        "th"
      );

    th.className =
      "day-col";


    if (
      sameDay(
        day,
        today
      )
    ) {

      th.classList.add(
        "today-col"
      );

    }


    th.textContent =
      formatHeaderDay(
        day
      );


    row.appendChild(
      th
    );
  }
}



/* =======================================================
   PASTILLE D'UNE SÉANCE
   ======================================================= */


function createSessionNode(session) {

  const dt =
    new Date(
      session.start
    );


  const node =
    document.createElement(
      session.url
        ? "a"
        : "span"
    );


  const cinemaClass =
    sessionCinemaClass(
      session
    );


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


  node.appendChild(
    hour
  );


  /*
  On affiche VO/VOST si disponible.

  VF devrait normalement avoir été
  éliminé pour les films Mégarama
  disposant d'une VO.
  */

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



/* =======================================================
   CELLULE D'UN JOUR
   ======================================================= */


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


    td.appendChild(
      empty
    );


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


  td.appendChild(
    list
  );


  return sessions.length;
}



/* =======================================================
   TABLEAU PRINCIPAL
   ======================================================= */


function renderMainTable(
  films,
  days
) {

  const body =
    el("cinemaWeekBody");


  if (!body) {
    return 0;
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


    /*
    Colonne titre
    */

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


    /*
    5 colonnes = 5 jours
    */

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


      tr.appendChild(
        td
      );
    }


    body.appendChild(
      tr
    );
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
      "Aucune séance à afficher.";


    tr.appendChild(
      td
    );


    body.appendChild(
      tr
    );
  }


  return totalSessions;
}



/* =======================================================
   GROSSES SORTIES MÉGARAMA
   ======================================================= */


function renderBigReleases(films) {

  const container =
    el("cinemaBigReleases");


  const section =
    el(
      "cinemaBigReleasesSection"
    );


  if (
    !container ||
    !section
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

      /*
      Séparateur entre les films.
      */

      if (index > 0) {

        const separator =
          document.createElement(
            "span"
          );


        separator.className =
          "big-release-separator";


        separator.textContent =
          " · ";


        container.appendChild(
          separator
        );
      }


      /*
      On prend de préférence une URL
      provenant d'une séance Mégarama.
      */

      const sessionWithUrl =
        film.sessions.find(
          session =>
            isMegaramaSession(
              session
            ) &&
            session.url
        ) ||

        film.sessions.find(
          session =>
            session.url
        );


      if (
        sessionWithUrl?.url
      ) {

        const link =
          document.createElement(
            "a"
          );


        link.className =
          "big-release-title";


        link.href =
          sessionWithUrl.url;


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
          document.createElement(
            "span"
          );


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



/* =======================================================
   AFFICHAGE GLOBAL
   ======================================================= */


function render() {

  const start =
    startOfToday();


  const days =
    Array.from(
      {
        length: 5
      },
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
    mainFilms,
    bigReleases
  } =
    splitFilms(
      films
    );


  const displayedSessions =
    renderMainTable(
      mainFilms,
      days
    );


  renderBigReleases(
    bigReleases
  );


  /*
  Le compteur correspond aux films
  et séances réellement présents
  dans le tableau principal.

  Les grosses sorties ne gonflent donc
  plus artificiellement le compteur.
  */

  const status =
    el("cinemaStatus");


  if (status) {

    status.textContent =
      `${mainFilms.length} film` +
      `${mainFilms.length > 1 ? "s" : ""}` +
      ` · ` +
      `${displayedSessions} séance` +
      `${displayedSessions > 1 ? "s" : ""}`;

  }
}



/* =======================================================
   CHARGEMENT
   ======================================================= */


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

  }

  catch (err) {

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



/* =======================================================
   ÉVÉNEMENTS
   ======================================================= */


el("afterWorkOnly")
  ?.addEventListener(
    "change",
    render
  );


init();
