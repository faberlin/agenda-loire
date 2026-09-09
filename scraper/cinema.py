from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean


ROOT = Path(__file__).resolve().parents[1]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# =========================================================
# LES 4 CINÉMAS - TÉLÉRAMA
# =========================================================

TELERAMA_CINEMAS = [
    (
        "Mégarama Jean-Jaurès",
        "https://www.telerama.fr/seances-cinema/"
        "megarama_jean_jaures_l_alhambra-P0231",
    ),
    (
        "Mégarama Camion Rouge",
        "https://www.telerama.fr/seances-cinema/"
        "megarama_chavanelle_camion_rouge-P0191",
    ),
    (
        "Méliès Jean-Jaurès",
        "https://www.telerama.fr/seances-cinema/"
        "le_melies_st_etienne_jean_jaures-P0161",
    ),
    (
        "Méliès Saint-François",
        "https://www.telerama.fr/seances-cinema/"
        "le_melies_st_etienne_st_francois-P0034",
    ),
]


# =========================================================
# OUTILS
# =========================================================

def stable_id(cinema, title, start, version=""):
    raw = f"{cinema}|{title}|{start}|{version}"

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:20]


def window():
    now = datetime.now(PARIS)

    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end = start + timedelta(days=7)

    return start, end


def in_window(dt):
    start, end = window()
    return start <= dt < end


def extract_times(text):
    """
    Reconnaît les horaires :
    14h00
    18h30
    20:15

    On ignore les heures avant 8h afin
    d'éviter de prendre les durées comme :
    1h45
    2h02
    """

    result = []

    for match in re.finditer(
        r"\b(\d{1,2})(?:h|:)(\d{2})\b",
        text,
        re.IGNORECASE,
    ):
        hour = int(match.group(1))
        minute = int(match.group(2))

        if (
            8 <= hour <= 23
            and 0 <= minute <= 59
        ):
            result.append(
                (hour, minute)
            )

    return result


# =========================================================
# URL JOUR
# =========================================================

def telerama_url(base_url, day):
    return (
        f"{base_url}"
        f"?date={day.strftime('%Y-%m-%d')}"
    )


# =========================================================
# LIENS FILMS
# =========================================================

def build_film_link_map(soup, page_url):
    """
    Essaie d'associer le titre affiché
    à la fiche film Télérama.

    On ne dépend pas d'un seul type
    d'URL car Télérama peut faire évoluer
    ses chemins.
    """

    links = {}

    for link in soup.find_all(
        "a",
        href=True,
    ):
        title = clean(
            link.get_text(" ")
        )

        if not title:
            continue

        href = clean(
            link.get("href")
        )

        if not href:
            continue

        absolute_url = urljoin(
            page_url,
            href,
        )

        # On évite les liens vers les pages cinéma,
        # navigation, login, réservation, etc.
        if "/seances-cinema/" in absolute_url:
            continue

        if any(
            value in absolute_url
            for value in [
                "/compte",
                "/connexion",
                "/recherche",
                "/reservation",
            ]
        ):
            continue

        links[
            title.lower()
        ] = absolute_url

    return links


def find_film_url(
    title,
    link_map,
):
    """
    Correspondance simple sur le titre.

    On commence par l'égalité exacte,
    puis on accepte qu'un texte de lien
    contienne le titre.
    """

    target = (
        title
        .strip()
        .lower()
    )

    if target in link_map:
        return link_map[target]

    for link_title, url in link_map.items():
        if (
            target == link_title
            or target in link_title
            or link_title in target
        ):
            return url

    return None


# =========================================================
# BLOCS FILMS TÉLÉRAMA
# =========================================================

def telerama_film_segments(soup):
    """
    Télérama présente typiquement :

    Découvrir la note
    TITRE
    réalisateur
    durée
    ...
    Séances en VO
    18h00
    ...

    On travaille sur le texte de page,
    ce qui s'est montré plus stable que
    les classes CSS.
    """

    text = soup.get_text(
        "\n",
        strip=True,
    )

    parts = re.split(
        r"Découvrir\s+la\s+note",
        text,
        flags=re.IGNORECASE,
    )

    segments = []

    for part in parts[1:]:
        lines = [
            clean(line)
            for line in part.splitlines()
            if clean(line)
        ]

        if not lines:
            continue

        if not re.search(
            r"S[ée]ances?\s+en\s+",
            part,
            re.IGNORECASE,
        ):
            continue

        title = lines[0]

        if title.lower() in {
            "favoris",
            "réserver",
            "reserver",
            "previous",
            "next",
            "précédent",
            "suivant",
        }:
            continue

        segments.append(
            (
                title,
                part,
            )
        )

    return segments


# =========================================================
# VF / VO
# =========================================================

def parse_telerama_versions(block):
    pattern = re.compile(
        r"S[ée]ances?\s+en\s+"
        r"(VF|VO|VOST|VOSTF|VOSTFR)",
        re.IGNORECASE,
    )

    matches = list(
        pattern.finditer(block)
    )

    result = []

    for index, match in enumerate(matches):
        version = (
            match.group(1)
            .upper()
        )

        if version == "VOSTFR":
            version = "VOSTF"

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(block)
        )

        section = block[
            match.end():end
        ]

        result.append(
            (
                version,
                section,
            )
        )

    return result


# =========================================================
# SCRAPING D'UN JOUR
# =========================================================

def scrape_telerama_day(
    cinema_name,
    base_url,
    day,
):
    url = telerama_url(
        base_url,
        day,
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    link_map = build_film_link_map(
        soup,
        url,
    )

    film_segments = (
        telerama_film_segments(
            soup
        )
    )

    events = []

    for title, block in film_segments:
        film_url = find_film_url(
            title,
            link_map,
        )

        versions = (
            parse_telerama_versions(
                block
            )
        )

        for version, section in versions:
            times = extract_times(
                section
            )

            for hour, minute in times:
                dt = day.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )

                if not in_window(dt):
                    continue

                events.append({
                    "id": stable_id(
                        cinema_name,
                        title,
                        dt.isoformat(),
                        version,
                    ),
                    "title": title,
                    "cinema": cinema_name,
                    "start": dt.isoformat(),
                    "version": version,
                    "url": film_url,
                    "source": "Télérama",
                })

    unique = {
        event["id"]: event
        for event in events
    }

    return sorted(
        unique.values(),
        key=lambda event: (
            event["start"],
            event["title"],
        ),
    )


# =========================================================
# SCRAPING D'UN CINÉMA SUR 7 JOURS
# =========================================================

def scrape_telerama_cinema(
    cinema_name,
    base_url,
):
    start, _ = window()

    events = []

    for offset in range(7):
        day = start + timedelta(
            days=offset
        )

        try:
            found = scrape_telerama_day(
                cinema_name,
                base_url,
                day,
            )

            print(
                f"{cinema_name} "
                f"{day.strftime('%d/%m')}: "
                f"{len(found)} séance(s)"
            )

            events.extend(
                found
            )

        except Exception as exc:
            print(
                f"ERREUR {cinema_name} "
                f"{day.strftime('%d/%m')}: "
                f"{exc}"
            )

    unique = {
        event["id"]: event
        for event in events
    }

    return sorted(
        unique.values(),
        key=lambda event: (
            event["start"],
            event["title"],
        ),
    )


# =========================================================
# GLOBAL
# =========================================================

def scrape_cinema():
    events = []

    for (
        cinema_name,
        base_url,
    ) in TELERAMA_CINEMAS:

        try:
            found = (
                scrape_telerama_cinema(
                    cinema_name,
                    base_url,
                )
            )

            print(
                f"{cinema_name}: "
                f"{len(found)} séance(s) au total"
            )

            events.extend(
                found
            )

        except Exception as exc:
            print(
                f"ERREUR {cinema_name}: "
                f"{exc}"
            )

    unique = {
        event["id"]: event
        for event in events
    }

    events = sorted(
        unique.values(),
        key=lambda event: (
            event["start"],
            event["cinema"],
            event["title"],
        ),
    )

    # Petit bilan des liens films
    with_url = sum(
        1
        for event in events
        if event.get("url")
    )

    without_url = (
        len(events)
        - with_url
    )

    print()
    print(
        f"Liens Télérama : "
        f"{with_url} séance(s) avec URL"
    )

    print(
        f"Sans URL film : "
        f"{without_url} séance(s)"
    )

    return events


# =========================================================
# EXÉCUTION
# =========================================================

if __name__ == "__main__":
    events = scrape_cinema()

    output = (
        ROOT
        / "cinema_events.json"
    )

    output.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"{len(events)} séance(s) "
        f"écrite(s) dans {output}"
    )
