from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

BASE_URL = "https://www.comedietriomphe.fr/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

MONTHS = {
    "janvier": 1, "janv": 1, "jan": 1,
    "février": 2, "fevrier": 2, "févr": 2, "fevr": 2,
    "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6,
    "juillet": 7, "juil": 7, "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9, "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11, "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}

# Regex plus souple : année optionnelle (prend l'année en cours si absente)
DATE_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre|janv?|févr?|fevr?|avr|juil|sept?|oct|nov|déc|dec)"
    r"\.?\s*(?:(\d{4}))?(?:\s+.*?(\d{1,2})[h:](\d{2}))?",
    re.IGNORECASE,
)


def infer_category(title: str) -> str:
    val = title.lower()
    if any(w in val for w in ("enfant", "fantôme", "sorcière", "jeune public", "conte")):
        return "Jeune public"
    if any(w in val for w in ("magie", "mental", "hypnose")):
        return "Spectacle"
    if any(w in val for w in ("stand-up", "one man", "humour", "comedy")):
        return "Humour"
    return "Théâtre"


def extract_dates_from_page(url: str) -> list[datetime]:
    """Visite la fiche du spectacle pour extraire toutes les dates de représentation."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    text = clean(soup.get_text(" "))
    found_dates = []
    current_year = datetime.now(tz=PARIS).year

    for match in DATE_RE.finditer(text):
        day = int(match.group(1))
        month_str = (
            match.group(2)
            .lower()
            .replace(".", "")
            .replace("é", "e")
            .replace("è", "e")
            .replace("û", "u")
        )
        month = MONTHS.get(month_str)
        year = int(match.group(3)) if match.group(3) else current_year
        hour = int(match.group(4)) if match.group(4) else 20
        minute = int(match.group(5)) if match.group(5) else 0

        if not month:
            continue

        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=PARIS)
            found_dates.append(dt)
        except ValueError:
            continue

    return found_dates


def scrape_comedie_triomphe() -> list[dict]:
    response = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    seen = set()

    now = datetime.now(tz=PARIS)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Récupérer tous les liens vers les fiches de spectacle
    links = soup.find_all("a", href=True)
    show_urls = set()
    for a in links:
        href = a["href"]
        if "/spectacle/" in href or "/evenement/" in href or "/programmation/" in href:
            show_urls.add(urljoin(BASE_URL, href))

    for url in show_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            
            show_soup = BeautifulSoup(resp.text, "html.parser")
            
            # Titre de la pièce
            title_el = show_soup.find(["h1", "h2"])
            if not title_el:
                continue
            title = clean(title_el.get_text(" "))

            # Dates trouvées sur la page
            dates = extract_dates_from_page(url)

            for dt in dates:
                # Filtre : uniquement les séances futures
                if dt < today_start:
                    continue

                start = dt.isoformat()
                event_id = stable_id("Comédie Triomphe", title, start)

                if event_id in seen:
                    continue

                seen.add(event_id)
                events.append({
                    "id": event_id,
                    "title": title,
                    "start": start,
                    "venue": "Comédie Triomphe",
                    "city": "Saint-Étienne",
                    "category": infer_category(title),
                    "description": "",
                    "url": url,
                    "source": "Comédie Triomphe (Officiel)",
                })

        except Exception as exc:
            print(f"Erreur sur {url}: {exc}")

    events.sort(key=lambda e: (e["start"], e["title"].lower()))
    print(f"Comédie Triomphe (Saison actuelle) : {len(events)} spectacle(s) trouvé(s)")
    return events


if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
