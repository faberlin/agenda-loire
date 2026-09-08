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
    "Accept-Language": "fr-FR,fr;q=0.9",
}


ALLOCINE_CINEMAS = [
    (
        "Mégarama Jean-Jaurès",
        "https://www.allocine.fr/seance/salle_gen_csalle=P0231.html",
    ),
    (
        "Mégarama Camion Rouge",
        "https://www.allocine.fr/seance/salle_gen_csalle=P0191.html",
    ),
]


MELIES_URL = "https://www.lemelies.com/films/"


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

    end = start + timedelta(days=5)

    return start, end


def in_window(dt):
    start, end = window()
    return start <= dt < end


def parse_french_date(text):
    match = re.search(
        r"\b(\d{1,2})\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|"
        r"décembre|decembre)"
        r"\s+(20\d{2})\b",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS[match.group(2).lower()]
    year = int(match.group(3))

    return datetime(
        year,
        month,
        day,
        tzinfo=PARIS,
    )


def extract_times(text):
    result = []

    for match in re.finditer(
        r"\b(\d{1,2}):(\d{2})\b",
        text
    ):
        hour = int(match.group(1))
        minute = int(match.group(2))

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.append(
                (hour, minute)
            )

    return result


# =========================================================
# ALLOCINÉ
# =========================================================

def get_allocine_films(soup):
    """
    Récupère les vrais titres de films + URL de fiche.
    """

    films = []

    seen = set()

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if "/film/fichefilm_gen_cfilm=" not in href:
            continue

        title = clean(
            link.get_text(" ")
        )

        if not title:
            continue

        key = title.lower()

        if key in seen:
            continue

        seen.add(key)

        films.append({
            "title": title,
            "url": urljoin(
                "https://www.allocine.fr",
                href,
            ),
        })

    return films


def split_allocine_text_by_films(page_text, films):
    """
    Découpe le texte complet AlloCiné en un bloc par film.

    Cela évite les doublons provoqués par les éléments HTML imbriqués.
    """

    positions = []

    search_from = 0

    for film in films:

        title = film["title"]

        position = page_text.find(
            title,
            search_from,
        )

        if position == -1:
            continue

        positions.append(
            (
                position,
                film,
            )
        )

        search_from = (
            position
            + len(title)
        )

    sections = []

    for index, (
        position,
        film,
    ) in enumerate(positions):

        end = (
            positions[index + 1][0]
            if index + 1 < len(positions)
            else len(page_text)
        )

        block = page_text[
            position:end
        ]

        sections.append(
            (
                film,
                block,
            )
        )

    return sections


def parse_allocine_block(
    cinema_name,
    film,
    block,
):
    """
    Exemple attendu :

    8 septembre 2026 - En VF
    14:00 Réserver
    17:00 Réserver

    8 septembre 2026 - En VO
    21:30 Réserver
    """

    events = []

    session_pattern = re.compile(
        r"(\d{1,2}\s+"
        r"(?:janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|"
        r"décembre|decembre)"
        r"\s+20\d{2})"
        r"\s*-\s*En\s+"
        r"(VF|VO|VOST|VOSTF|VF ST-SME|VO ST-SME|VOSTFR)",
        re.IGNORECASE,
    )

    matches = list(
        session_pattern.finditer(
            block
        )
    )

    for index, match in enumerate(matches):

        date = parse_french_date(
            match.group(1)
        )

        if not date:
            continue

        if not in_window(date):
            continue

        version = (
            match.group(2)
            .upper()
            .replace(" ST-SME", "")
        )

        if version == "VOSTFR":
            version = "VOSTF"

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(block)
        )

        session_text = block[
            match.end():end
        ]

        # On s'arrête avant les textes de navigation éventuels.
        session_text = session_text.split(
            "Choisissez votre horaire"
        )[0]

        for hour, minute in extract_times(
            session_text
        ):

            dt = date.replace(
                hour=hour,
                minute=minute,
            )

            if not in_window(dt):
                continue

            events.append({
                "id": stable_id(
                    cinema_name,
                    film["title"],
                    dt.isoformat(),
                    version,
                ),
                "title": film["title"],
                "cinema": cinema_name,
                "start": dt.isoformat(),
                "version": version,
                "url": film["url"],
            })

    return events


def scrape_allocine_cinema(
    cinema_name,
    url,
):

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

    films = get_allocine_films(
        soup
    )

    print(
        f"{cinema_name}: "
        f"{len(films)} film(s) trouvé(s)"
    )

    page_text = clean(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    sections = split_allocine_text_by_films(
        page_text,
        films,
    )

    events = []

    for film, block in sections:

        found = parse_allocine_block(
            cinema_name,
            film,
            block,
        )

        events.extend(
            found
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
# MÉLIÈS
# =========================================================

def parse_melies_day(text):

    match = re.search(
        r"\b(lun|mar|mer|jeu|ven|sam|dim)"
        r"\.?\s+(\d{1,2})\b",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    day_number = int(
        match.group(2)
    )

    start, _ = window()

    for offset in range(
        -1,
        7,
    ):

        day = start + timedelta(
            days=offset
        )

        if day.day == day_number:
            return day

    return None


def melies_film_blocks(soup):

    headings = soup.find_all(
        ["h2", "h3"]
    )

    for index, heading in enumerate(
        headings
    ):

        title = clean(
            heading.get_text(" ")
        )

        if not title:
            continue

        next_heading = (
            headings[index + 1]
            if index + 1 < len(headings)
            else None
        )

        chunks = []

        node = heading.find_next()

        while (
            node
            and node is not next_heading
        ):

            if getattr(
                node,
                "get_text",
                None,
            ):

                text = clean(
                    node.get_text(" ")
                )

                if text:
                    chunks.append(
                        text
                    )

            node = node.find_next()

        text = " ".join(
            chunks
        )

        if not re.search(
            r"\b(?:lun|mar|mer|jeu|ven|sam|dim)"
            r"\.?\s+\d{1,2}\b",
            text,
            re.IGNORECASE,
        ):
            continue

        link = heading.find(
            "a",
            href=True,
        )

        film_url = (
            urljoin(
                MELIES_URL,
                link["href"],
            )
            if link
            else MELIES_URL
        )

        yield (
            title,
            text,
            film_url,
        )


def scrape_melies():

    response = requests.get(
        MELIES_URL,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    events = []

    for (
        title,
        text,
        film_url,
    ) in melies_film_blocks(
        soup
    ):

        day_matches = list(
            re.finditer(
                r"\b(?:lun|mar|mer|jeu|ven|sam|dim)"
                r"\.?\s+\d{1,2}\b",
                text,
                re.IGNORECASE,
            )
        )

        for index, match in enumerate(
            day_matches
        ):

            date = parse_melies_day(
                match.group(0)
            )

            if not date:
                continue

            end = (
                day_matches[index + 1].start()
                if index + 1 < len(day_matches)
                else len(text)
            )

            day_text = text[
                match.end():end
            ]

            parts = re.split(
                r"Aucune\s+s[ée]ance",
                day_text,
                flags=re.IGNORECASE,
            )

            jj_text = (
                parts[0]
                if parts
                else day_text
            )

            sf_text = (
                parts[1]
                if len(parts) > 1
                else ""
            )

            for (
                cinema_name,
                cinema_text,
            ) in [

                (
                    "Méliès Jean-Jaurès",
                    jj_text,
                ),

                (
                    "Méliès Saint-François",
                    sf_text,
                ),

            ]:

                version_match = re.search(
                    r"\b(VF|VO|VOST|VOSTF)\b",
                    cinema_text,
                    re.IGNORECASE,
                )

                version = (
                    version_match.group(1).upper()
                    if version_match
                    else ""
                )

                for hour, minute in extract_times(
                    cinema_text
                ):

                    dt = date.replace(
                        hour=hour,
                        minute=minute,
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
# GLOBAL
# =========================================================

def scrape_cinema():

    events = []

    for cinema_name, url in ALLOCINE_CINEMAS:

        try:

            found = scrape_allocine_cinema(
                cinema_name,
                url,
            )

            print(
                f"{cinema_name}: "
                f"{len(found)} séance(s)"
            )

            events.extend(
                found
            )

        except Exception as exc:

            print(
                f"ERREUR {cinema_name}: "
                f"{exc}"
            )

    try:

        melies = scrape_melies()

        jj = [
            event
            for event in melies
            if event["cinema"]
            == "Méliès Jean-Jaurès"
        ]

        sf = [
            event
            for event in melies
            if event["cinema"]
            == "Méliès Saint-François"
        ]

        print(
            f"Méliès Jean-Jaurès: "
            f"{len(jj)} séance(s)"
        )

        print(
            f"Méliès Saint-François: "
            f"{len(sf)} séance(s)"
        )

        events.extend(
            melies
        )

    except Exception as exc:

        print(
            f"ERREUR Méliès: "
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
            event["cinema"],
            event["title"],
        ),
    )


if __name__ == "__main__":

    events = scrape_cinema()

    output = ROOT / "cinema_events.json"

    output.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{len(events)} séance(s) "
        f"écrite(s) dans {output}"
    )
