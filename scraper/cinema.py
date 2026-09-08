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

MEGARAMA = [
    (
        "Mégarama Jean-Jaurès",
        "https://jean-jaures.megarama.fr/",
    ),
    (
        "Mégarama Camion Rouge",
        "https://chavanelle.megarama.fr/",
    ),
]

MELIES_URL = "https://www.lemelies.com/films/"

MONTHS = {
    "janv": 1, "janvier": 1,
    "févr": 2, "fevr": 2, "février": 2, "fevrier": 2,
    "mars": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8,
    "sept": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12, "decembre": 12,
}


def _window():
    now = datetime.now(PARIS)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=8)
    return start, end


def _in_window(dt: datetime) -> bool:
    start, end = _window()
    return start <= dt < end


def _stable_id(cinema: str, title: str, start: str, version: str) -> str:
    raw = f"{cinema}|{title}|{start}|{version}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _parse_day_month(text: str) -> datetime | None:
    """
    Reconnaît :
      lun. 07
      mar. 08
      mer. 09
    en choisissant la date correspondante dans la fenêtre actuelle.
    """
    m = re.search(
        r"\b(lun|mar|mer|jeu|ven|sam|dim)\.?\s+(\d{1,2})\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    day_number = int(m.group(2))
    start, _ = _window()

    for offset in range(-1, 10):
        d = start + timedelta(days=offset)
        if d.day == day_number:
            return d

    return None


def _times(text: str) -> list[tuple[int, int]]:
    result = []
    for m in re.finditer(r"\b(\d{1,2})(?:h|:)(\d{2})\b", text):
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.append((hour, minute))
    return result


# ---------------------------------------------------------------------------
# MÉGARAMA
# ---------------------------------------------------------------------------

def scrape_megarama(cinema_name: str, home_url: str) -> list[dict]:
    """
    Le site Mégarama ne renvoie plus directement la grille HTML à requests.
    La page d'accueil contient par contre un lien TicketingCiné pour chaque film.

    On récupère donc :
      - le titre depuis le H3
      - le lien "Séances du film ..." vers TicketingCiné
      - les séances depuis cette page de réservation
    """
    response = requests.get(home_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    film_links = []

    for h3 in soup.find_all("h3"):
        title = clean(h3.get_text(" "))
        if not title:
            continue

        node = h3
        booking_url = None

        # Cherche le lien TicketingCiné situé juste après le titre.
        for _ in range(12):
            node = node.find_next()
            if not node:
                break

            if getattr(node, "name", None) == "h3":
                break

            if getattr(node, "name", None) == "a" and node.get("href"):
                href = node["href"]
                txt = clean(node.get_text(" ")).lower()

                if "ticketingcine.com" in href or "séances du film" in txt or "seances du film" in txt:
                    booking_url = href
                    break

        if booking_url:
            film_links.append((title, booking_url))

    events = []

    for title, booking_url in film_links:
        try:
            r = requests.get(booking_url, headers=HEADERS, timeout=25)
            r.raise_for_status()
        except Exception as exc:
            print(f"{cinema_name}: erreur TicketingCiné {title}: {exc}")
            continue

        page = BeautifulSoup(r.text, "html.parser")
        text = clean(page.get_text(" "))

        # On travaille dans les petits blocs qui contiennent simultanément
        # une date et une heure.
        for block in page.find_all(["div", "li", "article", "section", "p"]):
            block_text = clean(block.get_text(" "))
            if not block_text:
                continue

            date = _parse_day_month(block_text)
            if not date:
                continue

            version_match = re.search(
                r"\b(VF|VO|VOST|VOSTF|VOEST|VFST)\b",
                block_text,
                re.IGNORECASE,
            )
            version = version_match.group(1).upper() if version_match else ""

            for hour, minute in _times(block_text):
                dt = date.replace(hour=hour, minute=minute)
                if not _in_window(dt):
                    continue

                events.append({
                    "id": _stable_id(
                        cinema_name,
                        title,
                        dt.isoformat(),
                        version,
                    ),
                    "title": title,
                    "cinema": cinema_name,
                    "start": dt.isoformat(),
                    "version": version,
                    "url": booking_url,
                })

    unique = {event["id"]: event for event in events}
    return sorted(unique.values(), key=lambda e: e["start"])


# ---------------------------------------------------------------------------
# MÉLIÈS
# ---------------------------------------------------------------------------

def _melies_film_blocks(soup: BeautifulSoup):
    """
    Le Méliès expose les films et horaires directement dans /films/.
    On découpe la page à partir des titres H2/H3 et on lit jusqu'au titre suivant.
    """
    headings = soup.find_all(["h2", "h3"])

    for i, heading in enumerate(headings):
        title = clean(heading.get_text(" "))
        if not title:
            continue

        # Ignore les titres de sections génériques.
        if title.lower() in {
            "tous les films",
            "à la une",
            "a la une",
            "film du mois",
            "séances",
            "seances",
        }:
            continue

        stop = headings[i + 1] if i + 1 < len(headings) else None

        chunks = []
        node = heading.find_next()

        while node and node is not stop:
            if getattr(node, "get_text", None):
                txt = clean(node.get_text(" "))
                if txt:
                    chunks.append(txt)
            node = node.find_next()

        text = " ".join(chunks)

        if not re.search(r"\b(?:lun|mar|mer|jeu|ven|sam|dim)\.?\s+\d{1,2}\b", text, re.I):
            continue

        link = heading.find("a", href=True)
        film_url = urljoin(MELIES_URL, link["href"]) if link else MELIES_URL

        yield title, text, film_url


def scrape_melies() -> list[dict]:
    response = requests.get(MELIES_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []

    for title, text, film_url in _melies_film_blocks(soup):
        # La structure textuelle est :
        # Jean Jaurès / St-François / lun. 07 / horaires JJ / horaires SF / mar. 08 / ...
        day_matches = list(re.finditer(
            r"\b(lun|mar|mer|jeu|ven|sam|dim)\.?\s+(\d{1,2})\b",
            text,
            re.IGNORECASE,
        ))

        for idx, match in enumerate(day_matches):
            date = _parse_day_month(match.group(0))
            if not date:
                continue

            end = day_matches[idx + 1].start() if idx + 1 < len(day_matches) else len(text)
            day_text = text[match.end():end]

            # Le site affiche deux colonnes : Jean Jaurès puis St-François.
            # "Aucune séance" sert de séparateur naturel.
            parts = re.split(
                r"Aucune\s+s[ée]ance",
                day_text,
                flags=re.IGNORECASE,
            )

            jj_text = parts[0] if parts else day_text
            sf_text = parts[1] if len(parts) > 1 else ""

            for cinema_name, cinema_text in [
                ("Méliès Jean-Jaurès", jj_text),
                ("Méliès Saint-François", sf_text),
            ]:
                version_match = re.search(
                    r"\b(VF|VO|VOST|VOSTF|VOEST|VFST)\b",
                    cinema_text,
                    re.IGNORECASE,
                )
                version = version_match.group(1).upper() if version_match else ""

                for hour, minute in _times(cinema_text):
                    dt = date.replace(hour=hour, minute=minute)
                    if not _in_window(dt):
                        continue

                    events.append({
                        "id": _stable_id(
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

    unique = {event["id"]: event for event in events}
    return sorted(unique.values(), key=lambda e: e["start"])


# ---------------------------------------------------------------------------
# GLOBAL
# ---------------------------------------------------------------------------

def scrape_cinema() -> list[dict]:
    events = []

    for cinema_name, home_url in MEGARAMA:
        try:
            found = scrape_megarama(cinema_name, home_url)
            print(f"{cinema_name}: {len(found)} séance(s)")
            events.extend(found)
        except Exception as exc:
            print(f"ERREUR {cinema_name}: {exc}")

    try:
        melies = scrape_melies()

        jj = [
            event for event in melies
            if event["cinema"] == "Méliès Jean-Jaurès"
        ]
        sf = [
            event for event in melies
            if event["cinema"] == "Méliès Saint-François"
        ]

        print(f"Méliès Jean-Jaurès: {len(jj)} séance(s)")
        print(f"Méliès Saint-François: {len(sf)} séance(s)")

        events.extend(melies)

    except Exception as exc:
        print(f"ERREUR Méliès: {exc}")

    unique = {event["id"]: event for event in events}

    return sorted(
        unique.values(),
        key=lambda e: (e["start"], e["cinema"], e["title"])
    )


if __name__ == "__main__":
    events = scrape_cinema()

    output = ROOT / "cinema_events.json"
    output.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"{len(events)} séance(s) écrite(s) dans {output}")
