from __future__ import annotations

import re
from datetime import datetime, timedelta
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
    "mars": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}

DATE_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre|janv?|févr?|fevr?|avr|juil|sept?|oct|nov|déc|dec)"
    r"\.?\s+(\d{4})(?:\s+.*?(\d{1,2})[h:](\d{2}))?",
    re.IGNORECASE,
)


def infer_category(title: str) -> str:
    val = title.lower()
    if any(w in val for w in ("enfant", "fantôme", "sorcière", "jeune public")):
        return "Jeune public"
    if any(w in val for w in ("magie", "mental", "hypnose")):
        return "Spectacle"
    if any(w in val for w in ("stand-up", "one man", "humour", "comedy")):
        return "Humour"
    return "Théâtre"


def scrape_comedie_triomphe() -> list[dict]:
    response = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    seen = set()

    # Définition du seuil : on refuse tout ce qui est antérieur à aujourd'hui à minuit
    now = datetime.now(tz=PARIS)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    cards = soup.select("article, .spectacle, .event, .card, .elementor-post")
    if not cards:
        cards = [
            a.parent for a in soup.find_all("a", href=True)
            if "/spectacle/" in a["href"] or "/evenement/" in a["href"]
        ]

    for card in cards:
        title_el = card.find(["h1", "h2", "h3", "h4", ".title"])
        if not title_el:
            continue

        title = clean(title_el.get_text(" "))
        if not title or len(title) < 3:
            continue

        link_el = card.find("a", href=True) if card.name != "a" else card
        event_url = urljoin(BASE_URL, link_el["href"]) if link_el else BASE_URL

        card_text = clean(card.get_text(" "))
        match = DATE_RE.search(card_text)

        if not match:
            # Sans date explicite sur la carte, on ignore pour éviter d'importer une ancienne saison
            continue

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
        year = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 20
        minute = int(match.group(5)) if match.group(5) else 0

        if not month:
            continue

        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=PARIS)
        except ValueError:
            continue

        # FILTRE DE SAISON : On élimine les dates passées
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
            "url": event_url,
            "source": "Comédie Triomphe (Officiel)",
        })

    events.sort(key=lambda e: (e["start"], e["title"].lower()))
    print(f"Comédie Triomphe (Saison actuelle) : {len(events)} spectacle(s) à venir")
    return events


if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
