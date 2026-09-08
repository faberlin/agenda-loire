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
    )
}


CINEFIL_CINEMAS = [
    (
        "Mégarama Jean-Jaurès",
        "https://www.cinefil.com/cinema/"
        "megarama-jean-jaures-l-alhambra-saint-etienne/programmation"
    ),
    (
        "Mégarama Camion Rouge",
        "https://www.cinefil.com/cinema/"
        "le-camion-rouge/programmation"
    ),
]


MELIES_URL = "https://www.lemelies.com/films/"


# ---------------------------------------------------------
# OUTILS
# ---------------------------------------------------------

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
        microsecond=0
    )

    # On garde un peu plus large côté JSON.
    # L'affichage JS limitera ensuite à 5 jours.
    end = start + timedelta(days=7)

    return start, end


def in_window(dt):
    start, end = window()

    return start <= dt < end


def parse_time(text):
    m = re.search(
        r"\b(\d{1,2})[:h](\d{2})\b",
        text
    )

    if not m:
        return None

    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------
# CINEFIL / MÉGARAMA
# ---------------------------------------------------------

def cinefil_dates(soup):
    """
    Récupère les jours affichés en haut de la programmation Cinéfil.

    Exemple :
    Mar. 08 sept.
    Mer. 09 sept.
    Jeu. 10 sept.
    """

    text = clean(soup.get_text(" "))

    matches = re.findall(
        r"\b(?:lun|mar|mer|jeu|ven|sam|dim)\.?\s+"
        r"(\d{1,2})\s+"
        r"(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec)"
        r"\.?",
        text,
        re.IGNORECASE
    )

    month_numbers = {
        "janv": 1,
        "févr": 2,
        "fevr": 2,
        "mars": 3,
        "avr": 4,
        "mai": 5,
        "juin": 6,
        "juil": 7,
        "août": 8,
        "aout": 8,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "déc": 12,
        "dec": 12,
    }

    today = datetime.now(PARIS)

    dates = []
    seen = set()

    for day_text, month_text in matches:
        month = month_numbers[
            month_text.lower()
        ]

        year = today.year

        # Gestion simple du passage décembre -> janvier
        if today.month == 12 and month == 1:
            year += 1

        dt = datetime(
            year,
            month,
            int(day_text),
            tzinfo=PARIS
        )

        key = dt.date().isoformat()

        if key not in seen:
            seen.add(key)
            dates.append(dt)

    return dates[:7]


def scrape_cinefil_cinema(cinema_name, url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    dates = cinefil_dates(soup)

    if not dates:
        print(
            f"{cinema_name}: aucune date trouvée"
        )
        return []

    events = []

    # Les films sont généralement présentés via des H3.
    headings = soup.find_all(
        ["h2", "h3"]
    )

    for i, heading in enumerate(headings):
        title = clean(
            heading.get_text(" ")
        )

        if not title:
            continue

        lower = title.lower()

        if lower in {
            "films projetés",
            "programmation",
            "séances",
            "seances",
        }:
            continue

        next_heading = (
            headings[i + 1]
            if i + 1 < len(headings)
            else None
        )

        chunks = []

        node = heading.find_next()

        while node and node is not next_heading:
            if getattr(
                node,
                "get_text",
                None
            ):
                txt = clean(
                    node.get_text(" ")
                )

                if txt:
                    chunks.append(txt)

            node = node.find_next()

        block_text = " ".join(chunks)

        # Si aucun horaire, ce n'est probablement
        # pas une vraie fiche film.
        if not re.search(
            r"\b\d{1,2}:\d{2}\b",
            block_text
        ):
            continue

        link = heading.find(
            "a",
            href=True
        )

        if link:
            film_url = urljoin(
                url,
                link["href"]
            )
        else:
            film_url = url

        # Cinéfil affiche les séances dans l'ordre
        # des colonnes de jours.
        #
        # On essaie d'isoler les groupes entre
        # "Aucune séance".
        day_groups = re.split(
            r"Aucune\s+s[ée]ance"
            r"(?:\s+Prochaine\s+s[ée]ance[^0-9]*)?",
            block_text,
            flags=re.IGNORECASE
        )

        # Première tentative : on récupère les blocs
        # ayant des horaires.
        groups_with_times = []

        for group in day_groups:
            times = re.findall(
                r"\b(\d{1,2}):(\d{2})"
                r"(?:\s+(VF|VO|VOST|VOSTF))?",
                group,
                re.IGNORECASE
            )

            if times:
                groups_with_times.append(
                    times
                )

        # Si Cinéfil n'a pas produit une séparation
        # exploitable, fallback : extraction globale.
        if not groups_with_times:
            all_times = re.findall(
                r"\b(\d{1,2}):(\d{2})"
                r"(?:\s+(VF|VO|VOST|VOSTF))?",
                block_text,
                re.IGNORECASE
            )

            if all_times:
                groups_with_times = [
                    all_times
                ]

        # Cas courant : une liste d'horaires par jour.
        for day_index, times in enumerate(
            groups_with_times
        ):
            if day_index >= len(dates):
                break

            day = dates[day_index]

            for hour, minute, version in times:
                dt = day.replace(
                    hour=int(hour),
                    minute=int(minute)
                )

                if not in_window(dt):
                    continue

                version = (
                    version.upper()
                    if version
                    else ""
                )

                events.append({
                    "id": stable_id(
                        cinema_name,
                        title,
                        dt.isoformat(),
                        version
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
        key=lambda e: (
            e["start"],
            e["title"]
        )
    )


# ---------------------------------------------------------
# MÉLIÈS
# ---------------------------------------------------------

def parse_melies_day(text):
    m = re.search(
        r"\b(lun|mar|mer|jeu|ven|sam|dim)"
        r"\.?\s+(\d{1,2})\b",
        text,
        re.IGNORECASE
    )

    if not m:
        return None

    day_number = int(
        m.group(2)
    )

    start, _ = window()

    for offset in range(
        -1,
        10
    ):
        d = start + timedelta(
            days=offset
        )

        if d.day == day_number:
            return d

    return None


def extract_times(text):
    result = []

    for m in re.finditer(
        r"\b(\d{1,2})(?:h|:)(\d{2})\b",
        text
    ):
        hour = int(
            m.group(1)
        )

        minute = int(
            m.group(2)
        )

        if (
            0 <= hour <= 23
            and 0 <= minute <= 59
        ):
            result.append(
                (hour, minute)
            )

    return result


def melies_film_blocks(soup):
    headings = soup.find_all(
        ["h2", "h3"]
    )

    for i, heading in enumerate(
        headings
    ):
        title = clean(
            heading.get_text(" ")
        )

        if not title:
            continue

        next_heading = (
            headings[i + 1]
            if i + 1 < len(headings)
            else None
        )

        chunks = []

        node = heading.find_next()

        while node and node is not next_heading:
            if getattr(
                node,
                "get_text",
                None
            ):
                txt = clean(
                    node.get_text(" ")
                )

                if txt:
                    chunks.append(txt)

            node = node.find_next()

        text = " ".join(chunks)

        if not re.search(
            r"\b(?:lun|mar|mer|jeu|ven|sam|dim)"
            r"\.?\s+\d{1,2}\b",
            text,
            re.IGNORECASE
        ):
            continue

        link = heading.find(
            "a",
            href=True
        )

        film_url = (
            urljoin(
                MELIES_URL,
                link["href"]
            )
            if link
            else MELIES_URL
        )

        yield (
            title,
            text,
            film_url
        )


def scrape_melies():
    response = requests.get(
        MELIES_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    events = []

    for (
        title,
        text,
        film_url
    ) in melies_film_blocks(soup):

        day_matches = list(
            re.finditer(
                r"\b(?:lun|mar|mer|jeu|ven|sam|dim)"
                r"\.?\s+\d{1,2}\b",
                text,
                re.IGNORECASE
            )
        )

        for idx, match in enumerate(
            day_matches
        ):
            date = parse_melies_day(
                match.group(0)
            )

            if not date:
                continue

            end = (
                day_matches[idx + 1].start()
                if idx + 1 < len(day_matches)
                else len(text)
            )

            day_text = text[
                match.end():end
            ]

            parts = re.split(
                r"Aucune\s+s[ée]ance",
                day_text,
                flags=re.IGNORECASE
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
                cinema_text
            ) in [
                (
                    "Méliès Jean-Jaurès",
                    jj_text
                ),
                (
                    "Méliès Saint-François",
                    sf_text
                ),
            ]:

                version_match = re.search(
                    r"\b(VF|VO|VOST|VOSTF)\b",
                    cinema_text,
                    re.IGNORECASE
                )

                version = (
                    version_match.group(1).upper()
                    if version_match
                    else ""
                )

                for (
                    hour,
                    minute
                ) in extract_times(
                    cinema_text
                ):
                    dt = date.replace(
                        hour=hour,
                        minute=minute
                    )

                    if not in_window(dt):
                        continue

                    events.append({
                        "id": stable_id(
                            cinema_name,
                            title,
                            dt.isoformat(),
                            version
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
        key=lambda e: e["start"]
    )


# ---------------------------------------------------------
# GLOBAL
# ---------------------------------------------------------

def scrape_cinema():
    events = []

    for (
        cinema_name,
        url
    ) in CINEFIL_CINEMAS:

        try:
            found = scrape_cinefil_cinema(
                cinema_name,
                url
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
            f"ERREUR Méliès: {exc}"
        )

    unique = {
        event["id"]: event
        for event in events
    }

    return sorted(
        unique.values(),
        key=lambda e: (
            e["start"],
            e["cinema"],
            e["title"]
        )
    )


if __name__ == "__main__":
    events = scrape_cinema()

    output = ROOT / "cinema_events.json"

    output.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"{len(events)} séance(s) "
        f"écrite(s) dans {output}"
    )
