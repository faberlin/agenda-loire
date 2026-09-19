import hashlib
import html
import re
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import tz


BASE_URL = "https://choktheatre.com"
REST_URL = f"{BASE_URL}/wp-json/wp/v2/posts"
FEED_URL = f"{BASE_URL}/feed/"

SOURCE = "Chok Théâtre"
VENUE = "Chok Théâtre"
CITY = "Saint-Étienne"
CATEGORY = "Théâtre"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; AgendaLoire/1.0; "
        "+https://github.com/faberlin/agenda-loire)"
    )
}

PARIS = tz.gettz("Europe/Paris")

MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


# Exemples acceptés :
#
# Dimanche 20 septembre 2026 - 17h00
# Jeudi 1 octobre 2026 - 20h
# Vendredi 2 octobre 2026 – 20h
#
DATE_RE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+"
    r"(2026|2027)"
    r"\s*(?:[-–—|]\s*)?"
    r"(\d{1,2})\s*h(?:\s*(\d{2}))?",
    re.IGNORECASE,
)


# On accepte UNIQUEMENT la saison actuelle.
#
# Exemples rencontrés sur le site :
# SAISON 2026-2027 #1
# Saison 26/27 #1
# Les + Saison 26/27 #1
#
CURRENT_SEASON_RE = re.compile(
    r"(?:les\s*\+\s*)?"
    r"saison\s*"
    r"(?:2026\s*[-–—]\s*2027|26\s*/\s*27)"
    r"\s*#\s*1",
    re.IGNORECASE,
)


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_id(title, start):
    raw = f"{SOURCE}|{title}|{start}".encode("utf-8")

    return hashlib.sha1(
        raw
    ).hexdigest()[:20]


def parse_dates(text):
    dates = []

    for match in DATE_RE.finditer(text):
        day = int(
            match.group(1)
        )

        month = MONTHS[
            match.group(2).lower()
        ]

        year = int(
            match.group(3)
        )

        hour = int(
            match.group(4)
        )

        minute = int(
            match.group(5) or 0
        )

        try:
            dt = datetime(
                year,
                month,
                day,
                hour,
                minute,
                tzinfo=PARIS
            )

        except ValueError:
            continue

        dates.append(dt)

    # Déduplication
    unique = []
    seen = set()

    for dt in dates:
        key = dt.isoformat()

        if key in seen:
            continue

        seen.add(key)
        unique.append(dt)

    return unique


def fetch_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


def get_title(soup):
    h1 = soup.find("h1")

    if h1:
        title = clean_text(
            h1.get_text(
                " ",
                strip=True
            )
        )

        if title:
            title = re.sub(
                r"\s+Mise à jour récente\s*!?$",
                "",
                title,
                flags=re.IGNORECASE
            )

            return title.strip()

    if soup.title:
        title = clean_text(
            soup.title.get_text(
                " ",
                strip=True
            )
        )

        title = re.sub(
            r"\s*[-–|]\s*Chok théâtre.*$",
            "",
            title,
            flags=re.IGNORECASE
        )

        return title.strip()

    return ""


def extract_main_content(soup):
    """
    Supprime tout ce qui peut contenir les menus
    et les liens vers les anciennes saisons.

    C'est important :
    on ne doit JAMAIS utiliser le texte du menu
    pour décider de la saison d'un spectacle.
    """

    for node in soup.select(
        "nav, "
        "header, "
        "footer, "
        "aside, "
        ".navbar, "
        ".menu, "
        ".nav, "
        ".sidebar, "
        ".widget, "
        "#menu, "
        "#sidebar"
    ):
        node.decompose()

    return soup


def check_current_season(url):
    """
    Vérifie la fiche individuelle.

    Elle n'est retenue que si son contenu
    indique explicitement :

        Saison 2026-2027 #1

    ou :

        Saison 26/27 #1

    On ne se base donc plus sur la colonne
    des anciennes saisons du site.
    """

    try:
        page_html = fetch_page(
            url
        )

    except Exception as exc:
        print(
            f"Chok Théâtre : "
            f"erreur fiche {url}: "
            f"{exc}"
        )

        return None

    soup = BeautifulSoup(
        page_html,
        "html.parser"
    )

    soup = extract_main_content(
        soup
    )

    text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    )

    if not CURRENT_SEASON_RE.search(
        text
    ):
        return None

    return soup, text


def discover_with_rest():
    """
    Cherche les publications WordPress récentes.

    On ne consulte volontairement que les
    publications à partir de juillet 2026.

    Cela évite de reparcourir toute la saison
    2025-2026.
    """

    urls = []

    try:
        page = 1

        while page <= 5:

            response = requests.get(
                REST_URL,
                headers=HEADERS,
                params={
                    "per_page": 100,
                    "page": page,
                    "after": (
                        "2026-07-01T00:00:00"
                    ),
                    "_fields": (
                        "link,date,modified"
                    ),
                },
                timeout=30,
            )

            # WordPress renvoie souvent 400
            # quand on dépasse la dernière page.
            if response.status_code == 400:
                break

            response.raise_for_status()

            posts = response.json()

            if not posts:
                break

            for post in posts:
                link = post.get(
                    "link"
                )

                if link:
                    urls.append(
                        link
                    )

            total_pages = int(
                response.headers.get(
                    "X-WP-TotalPages",
                    page
                )
            )

            if page >= total_pages:
                break

            page += 1

    except Exception as exc:
        print(
            "Chok Théâtre : "
            "API WordPress indisponible : "
            f"{exc}"
        )

    return urls


def discover_with_feed():
    """
    Méthode de secours.

    Si l'API WordPress n'est pas disponible,
    on regarde également le flux RSS.
    """

    urls = []

    for page in range(
        1,
        8
    ):

        if page == 1:
            feed_url = FEED_URL
        else:
            feed_url = (
                f"{FEED_URL}"
                f"?paged={page}"
            )

        try:
            response = requests.get(
                feed_url,
                headers=HEADERS,
                timeout=30
            )

            response.raise_for_status()

        except Exception as exc:
            print(
                "Chok Théâtre : "
                f"erreur flux page {page}: "
                f"{exc}"
            )

            break

        feed = feedparser.parse(
            response.content
        )

        if not feed.entries:
            break

        before = len(
            urls
        )

        for entry in feed.entries:
            link = entry.get(
                "link"
            )

            if (
                link
                and link.startswith(
                    BASE_URL
                )
            ):
                urls.append(
                    link
                )

        if len(urls) == before:
            break

    return urls


def discover_urls():
    """
    Combine API WordPress + RSS puis supprime
    les doublons.
    """

    urls = (
        discover_with_rest()
        +
        discover_with_feed()
    )

    unique = []
    seen = set()

    for url in urls:

        url = (
            url
            .split("#", 1)[0]
            .rstrip("/")
            + "/"
        )

        if url in seen:
            continue

        seen.add(url)
        unique.append(url)

    print(
        "Chok Théâtre : "
        f"{len(unique)} fiche(s) "
        "récente(s) à vérifier"
    )

    return unique


def scrape():
    events = []
    accepted_pages = 0

    urls = discover_urls()

    for url in urls:

        result = check_current_season(
            url
        )

        # Pas explicitement saison 26/27 #1 :
        # on ignore totalement la fiche.
        if result is None:
            continue

        soup, text = result

        title = get_title(
            soup
        )

        if not title:
            continue

        dates = parse_dates(
            text
        )

        if not dates:
            print(
                "Chok Théâtre : "
                f"{title} "
                "-> aucune date "
                "2026/2027 trouvée"
            )

            continue

        accepted_pages += 1

        print(
            "Chok Théâtre : "
            f"{title} "
            f"-> {len(dates)} séance(s)"
        )

        for dt in dates:

            start = dt.isoformat()

            events.append({
                "id": make_id(
                    title,
                    start
                ),
                "title": title,
                "start": start,
                "venue": VENUE,
                "city": CITY,
                "category": CATEGORY,
                "description": "",
                "url": url,
                "source": SOURCE,
            })

    # Déduplication finale
    deduped = []
    seen = set()

    for event in sorted(
        events,
        key=lambda e: e["start"]
    ):

        key = (
            event["title"].lower(),
            event["start"]
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(
            event
        )

    print(
        "Chok Théâtre : "
        f"{accepted_pages} fiche(s) "
        "saison 26/27 #1, "
        f"{len(deduped)} "
        "représentation(s)"
    )

    return deduped


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            scrape(),
            ensure_ascii=False,
            indent=2
        )
    )
