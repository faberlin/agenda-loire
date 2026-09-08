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


ALLOCINE_CINEMAS = [
    (
        "Mégarama Jean-Jaurès",
        "P0231",
    ),
    (
        "Mégarama Camion Rouge",
        "P0191",
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

    # Aujourd'hui + 4 jours
    end = start + timedelta(days=5)

    return start, end


def in_window(dt):
    start, end = window()

    return start <= dt < end


def parse_french_full_date(text):
    """
    Exemple :
    8 septembre 2026
    08 septembre 2026
    """

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
        r"\b(\d{1,2})(?::|h)(\d{2})\b",
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
# ALLOCINÉ / MÉGARAMA
# =========================================================

def allocine_url(cinema_code, day):
    """
    AlloCiné permet de sélectionner le jour via ?date=YYYY-MM-DD
    """

    return (
        "https://www.allocine.fr/seance/"
        f"salle_gen_csalle={cinema_code}.html"
        f"?date={day.strftime('%Y-%m-%d')}"
    )


def allocine_film_headings(soup):
    """
    On recherche uniquement les titres qui pointent
    vers une vraie fiche film AlloCiné.
    """

    result = []

    for heading in soup.find_all(["h2", "h3"]):

        link = heading.find(
            "a",
            href=True,
        )

        if not link:
            continue

        href = link["href"]

        if (
            "/film/fichefilm_gen_cfilm="
            not in href
        ):
            continue

        title = clean(
            link.get_text(" ")
        )

        if not title:
            continue

        result.append(
            (
                heading,
                title,
                urljoin(
                    "https://www.allocine.fr/",
                    href,
                ),
            )
        )

    return result


def text_between_headings(
    heading,
    next_heading,
):
    """
    Récupère le texte du film jusqu'au film suivant.
    """

    parts = []

    node = heading.find_next()

    while node:

        if node is next_heading:
            break

        if getattr(
            node,
            "get_text",
            None,
        ):
            text = clean(
                node.get_text(" ")
            )

            if text:
                parts.append(text)

        node = node.find_next()

    return " ".join(parts)


def parse_allocine_film_block(
    cinema_name,
    title,
    film_url,
    block_text,
    expected_day,
):
    """
    Exemple AlloCiné :

    8 septembre 2026 - En VF
    14:00 Réserver
    17:00 Réserver
    20:00 Réserver

    8 septembre 2026 - En VO
    21:30 Réserver
    """

    events = []

    date_pattern = re.compile(
        r"(\d{1,2}\s+"
        r"(?:janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|"
        r"décembre|decembre)"
        r"\s+20\d{2})"
        r"\s*-\s*En\s+"
        r"(VF|VO|VOST|VOSTF|VO(?:\s+STFR)?)",
        re.IGNORECASE,
    )

    matches = list(
        date_pattern.finditer(
            block_text
        )
    )

    for index, match in enumerate(matches):

        date_text = match.group(1)

        version = (
            match.group(2)
            .upper()
            .replace(" ", "")
        )

        if version == "VOSTFR":
            version = "VOSTF"

        date = parse_french_full_date(
            date_text
        )

        if not date:
            continue

        # On ne conserve que le jour demandé.
        if date.date() != expected_day.date():
            continue

        section_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(block_text)
        )

        section = block_text[
            match.end():section_end
        ]

        for hour, minute in extract_times(
            section
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

    return events


def scrape_allocine_day(
    cinema_name,
    cinema_code,
    day,
):
    url = allocine_url(
        cinema_code,
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

    headings = allocine_film_headings(
        soup
    )

    events = []

    for index, (
        heading,
        title,
        film_url,
    ) in enumerate(headings):

        next_heading = (
            headings[index + 1][0]
            if index + 1 < len(headings)
            else None
        )

        block_text = text_between_headings(
            heading,
            next_heading,
        )

        events.extend(
            parse_allocine_film_block(
                cinema_name,
                title,
                film_url,
                block_text,
                day,
            )
        )

    return events


def scrape_allocine_cinema(
    cinema_name,
    cinema_code,
):
    start, _ = window()

    events = []

    for offset in range(5):

        day = start + timedelta(
            days=offset
        )

        try:

            found = scrape_allocine_day(
                cinema_name,
                cinema_code,
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

            if not in_window(
                date
            ):
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
                    r"\b("
                    r"VF|VO|VOST|VOSTF"
                    r")\b",
                    cinema_text,
                    re.IGNORECASE,
                )

                version = (
                    version_match
                    .group(1)
                    .upper()
                    if version_match
                    else ""
                )

                for (
                    hour,
                    minute,
                ) in extract_times(
                    cinema_text
                ):

                    dt = date.replace(
                        hour=hour,
                        minute=minute,
                    )

                    if not in_window(
                        dt
                    ):
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

    # -----------------------------
    # MÉGARAMA VIA ALLOCINÉ
    # -----------------------------

    for (
        cinema_name,
        cinema_code,
    ) in ALLOCINE_CINEMAS:

        try:

            found = scrape_allocine_cinema(
                cinema_name,
                cinema_code,
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

    # -----------------------------
    # MÉLIÈS
    # -----------------------------

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

    # -----------------------------
    # DÉDOUBLONNAGE
    # -----------------------------

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


# =========================================================
# EXÉCUTION DIRECTE
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

    print(
        f"{len(events)} séance(s) "
        f"écrite(s) dans {output}"
    )
