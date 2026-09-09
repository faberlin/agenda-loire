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
# CINÉMAS
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
]


MELIES_URL = "https://www.lemelies.com/films/"


# =========================================================
# OUTILS
# =========================================================

def stable_id(cinema, title, start, version=""):
    raw = f"{cinema}|{title}|{start}|{version}"

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:20]


def window():
    """
    On garde 7 jours dans cinema_events.json.

    cinema.js limite déjà l'affichage aux 5 premiers jours.
    """

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
    result = []

    for match in re.finditer(
        r"\b(\d{1,2})(?:h|:)(\d{2})\b",
        text,
        re.IGNORECASE,
    ):
        hour = int(match.group(1))
        minute = int(match.group(2))

        # On élimine notamment les durées de films :
        # 1h45, 2h02, etc.
        if 8 <= hour <= 23 and 0 <= minute <= 59:
            result.append((hour, minute))

    return result


# =========================================================
# TÉLÉRAMA / MÉGARAMA
# =========================================================

def telerama_url(base_url, day):
    return (
        f"{base_url}"
        f"?date={day.strftime('%Y-%m-%d')}"
    )


def build_telerama_link_map(soup, page_url):
    """
    Associe autant que possible un titre de film à sa fiche
    Télérama.
    """

    result = {}

    for link in soup.find_all("a", href=True):
        title = clean(
            link.get_text(" ")
        )

        if not title:
            continue

        href = link["href"]

        # Les fiches films Télérama sont généralement
        # dans /cinema/...
        if "/cinema/" not in href:
            continue

        result[
            title.lower()
        ] = urljoin(
            page_url,
            href,
        )

    return result


def telerama_film_segments(soup):
    """
    Télérama structure les fiches de programmation avec :

    Découvrir la note
    NOM DU FILM
    réalisateur
    durée
    ...
    Séances en VF
    14h00
    16h00
    ...

    On s'appuie sur cette structure textuelle plutôt que
    sur les classes CSS du site.
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

    # Le premier morceau correspond à l'en-tête de page.
    for part in parts[1:]:

        lines = [
            clean(line)
            for line in part.splitlines()
            if clean(line)
        ]

        if not lines:
            continue

        # On ignore les blocs qui ne contiennent aucune séance.
        if not re.search(
            r"S[ée]ances?\s+en\s+",
            part,
            re.IGNORECASE,
        ):
            continue

        title = lines[0]

        # Sécurité contre les éléments de navigation.
        if title.lower() in {
            "favoris",
            "réserver",
            "reserver",
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


def parse_telerama_versions(block):
    """
    Retourne par exemple :

    [
        ("VF", "14h00 ... 16h00 ..."),
        ("VO", "20h30 ...")
    ]
    """

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

    link_map = build_telerama_link_map(
        soup,
        url,
    )

    segments = telerama_film_segments(
        soup
    )

    events = []

    for title, block in segments:

        film_url = link_map.get(
            title.lower(),
            url,
        )

        versions = parse_telerama_versions(
            block
        )

        for version, section in versions:

            for hour, minute in extract_times(
                section
            ):

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


def scrape_telerama_cinema(
    cinema_name,
    base_url,
):
    """
    On interroge Télérama jour par jour.

    C'est volontaire :
    la date du JSON est donc celle réellement demandée,
    ce qui évite le problème rencontré avec AlloCiné où
    toutes les séances se retrouvaient le même jour.
    """

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
# MÉLIÈS
# =========================================================

def parse_melies_day(text):
    """
    Reconnaît :
    lun. 07
    mar. 08
    mer. 09
    """

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
        10,
    ):

        day = start + timedelta(
            days=offset
        )

        if day.day == day_number:
            return day

    return None


def melies_film_blocks(soup):
    """
    Version du parser Méliès qui avait déjà donné
    des résultats dans GitHub Actions.
    """

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
                        second=0,
                        microsecond=0,
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

    # -----------------------------------------------------
    # MÉGARAMA VIA TÉLÉRAMA
    # -----------------------------------------------------

    for (
        cinema_name,
        base_url,
    ) in TELERAMA_CINEMAS:

        try:

            found = scrape_telerama_cinema(
                cinema_name,
                base_url,
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

    # -----------------------------------------------------
    # MÉLIÈS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # DÉDOUBLONNAGE
    # -----------------------------------------------------

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
