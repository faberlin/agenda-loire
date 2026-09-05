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
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}


DATE_PATTERN = re.compile(
    r"(?:lun|mar|mer|jeu|ven|sam|dim)\.\s+"
    r"(\d{1,2})\s+"
    r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)"
    r"\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE
)


def scrape_le_fil() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        title = clean(link.get_text(" "))
        if len(title) < 3:
            continue

        parent = link
        match = None

        for _ in range(6):
            if parent.parent:
                parent = parent.parent

            text = clean(parent.get_text(" "))
            match = DATE_PATTERN.search(text)

            if match:
                break

        if not match:
            continue

        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        hour = int(match.group(3))
        minute = int(match.group(4))

        # Saison 2026-2027.
        year = 2026 if month >= 9 else 2027

        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=PARIS)
        except ValueError:
            continue

        url = urljoin(URL, link["href"])

        if url.rstrip("/") == URL.rstrip("/"):
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        start = dt.isoformat()

        events.append({
            "id": stable_id("Le Fil", title, start),
            "title": title,
            "start": start,
            "venue": "Le Fil",
            "city": "Saint-Étienne",
            "category": "Musique",
            "description": "",
            "url": url,
            "source": "Le Fil"
        })

    return events
