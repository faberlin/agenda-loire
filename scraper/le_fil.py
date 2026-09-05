from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://www.le-fil.com/agenda/"
HEADERS = {
    "User-Agent": "AgendaLoire/1.0 (personal cultural events aggregator)"
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

DATE_PATTERN = re.compile(
    r"(?:lun|mar|mer|jeu|ven|sam|dim)\.\s+"
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE
)


def infer_year(month: int) -> int:
    """
    Agenda consulté en septembre 2026 :
    septembre-décembre -> 2026
    janvier-août -> 2027
    """
    return 2026 if month >= 9 else 2027


def find_date_near_link(link) -> re.Match | None:
    """
    Remonte uniquement dans la carte de l'événement jusqu'à trouver
    la date. On ne prend plus tous les liens de la page.
    """
    node = link

    for _ in range(8):
        node = node.parent
        if node is None:
            break

        text = clean(node.get_text(" "))
        match = DATE_PATTERN.search(text)

        if match:
            return match

    return None


def scrape_le_fil() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=25)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen_urls = set()

    # IMPORTANT :
    # seules les fiches d'événement du Fil ont une URL /evenement/...
    # Les filtres "Grande Salle", "Studios", "Sur la terrasse", etc.
    # sont donc automatiquement exclus.
    links = soup.select('a[href*="/evenement/"]')

    for link in links:
        href = link.get("href")
        if not href:
            continue

        event_url = urljoin(URL, href)

        if event_url in seen_urls:
            continue

        title = clean(link.get_text(" "))
        if not title:
            continue

        match = find_date_near_link(link)
        if not match:
            print(f"Le Fil: date introuvable pour {title}")
            continue

        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        hour = int(match.group(3))
        minute = int(match.group(4))
        year = infer_year(month)

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

        start = dt.isoformat()
        seen_urls.add(event_url)

        events.append({
            "id": stable_id("Le Fil", title, start),
            "title": title,
            "start": start,
            "venue": "Le Fil",
            "city": "Saint-Étienne",
            "category": "Musique",
            "description": "",
            "url": event_url,
            "source": "Le Fil"
        })

    return events
