from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://choktheatre.com/"
PROGRAM_URL = urljoin(BASE, "programmation/")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

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


# Exemples :
#
# Dimanche 20 septembre 2026 - 17h00
# 20 septembre 2026 – 17h
# Vendredi 23 octobre 2026 | 20h30

DATE_RE = re.compile(
    r"\b"
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?"
    r"\s*"
    r"(\d{1,2})(?:er)?"
    r"\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+"
    r"(\d{4})"
    r"\s*"
    r"[-–—|]"
    r"\s*"
    r"(\d{1,2})h(?:([0-5]\d))?"
    r"\b",
    re.IGNORECASE,
)


# ------------------------------------------------------
# REQUÊTES
# ------------------------------------------------------

def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


# ------------------------------------------------------
# DATES
# ------------------------------------------------------

def extract_dates(text: str) -> list[datetime]:
    dates = {}

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
                tzinfo=PARIS,
            )
        except ValueError:
            continue

        dates[
            dt.isoformat()
        ] = dt

    return sorted(
        dates.values()
    )


# ------------------------------------------------------
# TITRE
# ------------------------------------------------------

def extract_title(
    soup: BeautifulSoup,
) -> str:

    h1 = soup.find("h1")

    if h1:
        title = clean(
            h1.get_text(" ")
        )
    else:
        title_tag = soup.find(
            "title"
        )

        title = (
            clean(
                title_tag.get_text(
                    " "
                )
            )
            if title_tag
            else ""
        )

    # Enlève éventuellement :
    # " - Chok théâtre"
    # " | Chok théâtre"

    title = re.sub(
        r"\s*(?:-|–|—|\|)\s*"
        r"Chok\s+théâtre.*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\s*Mise à jour récente\s*!?\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    return clean(title)


# ------------------------------------------------------
# ZONE PROGRAMMATION
# ------------------------------------------------------

def find_program_area(
    soup: BeautifulSoup,
):
    """
    Cherche le contenu principal de la page.

    Le but est surtout de NE PAS parcourir le menu
    latéral qui contient toutes les anciennes saisons.
    """

    # WordPress utilise généralement <main>.
    main = soup.find("main")

    if main:
        return main

    # Autres conteneurs fréquemment utilisés
    # par les thèmes WordPress.

    for selector in (
        "#main",
        "#content",
        ".site-content",
        ".entry-content",
        ".article-container",
        "article",
    ):
        area = soup.select_one(
            selector
        )

        if area:
            # Vérifie qu'on est bien dans la zone
            # contenant PROGRAMMATION.
            text = clean(
                area.get_text(" ")
            ).lower()

            if "programmation" in text:
                return area

    # Dernier recours :
    # on part du H1 PROGRAMMATION.

    for heading in soup.find_all(
        ["h1", "h2"]
    ):
        text = clean(
            heading.get_text(" ")
        )

        if (
            text.lower()
            == "programmation"
        ):
            parent = heading.parent

            # Remonte quelques niveaux seulement.
            for _ in range(4):
                if parent is None:
                    break

                links = parent.find_all(
                    "a",
                    href=True,
                )

                if len(links) >= 3:
                    return parent

                parent = parent.parent

    return None


# ------------------------------------------------------
# LIENS DE LA PROGRAMMATION
# ------------------------------------------------------

def is_internal_event_url(
    url: str,
) -> bool:

    parsed = urlparse(url)

    if (
        parsed.netloc
        and parsed.netloc
        != "choktheatre.com"
    ):
        return False

    lower = url.lower()

    excluded = (
        "/programmation/",
        "/category/",
        "/tag/",
        "/author/",
        "/wp-",
        "/feed",
        "/infos-pratiques",
        "/partenaires",
        "/la-cie-",
        "/le-chok-theatre",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "youtube.com",
        "calameo.com",
        "helloasso.com",
    )

    return not any(
        item in lower
        for item in excluded
    )


def program_urls() -> list[str]:
    soup = get_soup(
        PROGRAM_URL
    )

    area = find_program_area(
        soup
    )

    if area is None:
        print(
            "Chok Théâtre : "
            "zone PROGRAMMATION introuvable"
        )

        return []

    urls = []

    for link in area.find_all(
        "a",
        href=True,
    ):
        href = clean(
            link.get(
                "href",
                ""
            )
        )

        if not href:
            continue

        url = urljoin(
            PROGRAM_URL,
            href,
        )

        if not is_internal_event_url(
            url
        ):
            continue

        urls.append(url)

    # Supprime les doublons
    # tout en conservant l'ordre.

    urls = list(
        dict.fromkeys(urls)
    )

    print(
        "Chok Théâtre : "
        f"{len(urls)} lien(s) "
        "dans la zone PROGRAMMATION"
    )

    return urls


# ------------------------------------------------------
# FICHE D'UN SPECTACLE
# ------------------------------------------------------

def scrape_event_page(
    url: str,
) -> list[dict]:

    try:
        soup = get_soup(
            url
        )

    except requests.RequestException as exc:
        print(
            "Chok Théâtre : "
            f"erreur {url} : {exc}"
        )

        return []

    title = extract_title(
        soup
    )

    if not title:
        return []

    # Important :
    # on évite soup.get_text() sur toute la page,
    # car cela inclurait encore le menu avec
    # toutes les anciennes saisons.

    content = None

    for selector in (
        ".entry-content",
        "article .entry-content",
        "article",
        "main",
    ):
        content = soup.select_one(
            selector
        )

        if content:
            break

    if content is None:
        return []

    text = clean(
        content.get_text(" ")
    )

    dates = extract_dates(
        text
    )

    if not dates:
        print(
            "Chok Théâtre : "
            f"{title} -> aucune date"
        )

        return []

    events = []

    for dt in dates:
        start = dt.isoformat()

        events.append(
            {
                "id": stable_id(
                    "Chok Théâtre",
                    title,
                    start,
                ),
                "title": title,
                "start": start,
                "venue": "Chok Théâtre",
                "city": "Saint-Étienne",
                "category": "Théâtre",
                "description": "",
                "url": url,
                "source": "Chok Théâtre",
            }
        )

    print(
        "Chok Théâtre : "
        f"{title} -> "
        f"{len(events)} séance(s)"
    )

    return events


# ------------------------------------------------------
# SCRAPER PRINCIPAL
# ------------------------------------------------------

def scrape_chok() -> list[dict]:
    events = []
    seen = set()

    urls = program_urls()

    for url in urls:
        page_events = (
            scrape_event_page(
                url
            )
        )

        for event in page_events:
            event_id = event[
                "id"
            ]

            if event_id in seen:
                continue

            seen.add(
                event_id
            )

            events.append(
                event
            )

    events.sort(
        key=lambda event: (
            event["start"],
            event["title"].lower(),
        )
    )

    print(
        "Chok Théâtre : "
        f"{len(events)} "
        "représentation(s) au total"
    )

    return events


if __name__ == "__main__":
    for event in scrape_chok():
        print(event)
