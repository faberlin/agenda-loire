from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


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

DATE_RE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})"
    r"(?:\s+à\s+(\d{1,2})h(\d{2}))?",
    re.IGNORECASE
)


def _extract_date(text: str) -> datetime | None:
    match = DATE_RE.search(clean(text))
    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS[match.group(2).lower()]
    year = int(match.group(3))
    hour = int(match.group(4)) if match.group(4) else 0
    minute = int(match.group(5)) if match.group(5) else 0

    try:
        return datetime(year, month, day, hour, minute, tzinfo=PARIS)
    except ValueError:
        return None


def scrape_infoconcert_venue(
    url: str,
    venue: str,
    city: str,
    category: str = "Musique",
) -> list[dict]:
    """
    Scraper générique d'une page salle Infoconcert.

    Exemple :
    https://www.infoconcert.com/salle/le-fil-a-saint-etienne-21927/concerts
    """
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    # Sur les pages salle Infoconcert, les artistes/événements
    # sont présentés comme des titres <h2>.
    for heading in soup.find_all("h2"):
        title = clean(heading.get_text(" "))
        if not title:
            continue

        # Exclut les titres de section.
        if title.lower().startswith("les concerts"):
            continue

        # Cherche le texte associé jusqu'au prochain h2.
        parts = []
        node = heading.next_sibling

        while node is not None:
            if getattr(node, "name", None) == "h2":
                break

            if hasattr(node, "get_text"):
                txt = clean(node.get_text(" "))
            else:
                txt = clean(str(node))

            if txt:
                parts.append(txt)

            node = node.next_sibling

        block_text = " ".join(parts)

        # Si la structure HTML imbrique les éléments, on essaie aussi
        # le conteneur parent de proximité.
        dt = _extract_date(block_text)
        if dt is None:
            parent = heading.parent
            for _ in range(4):
                if parent is None:
                    break
                dt = _extract_date(parent.get_text(" "))
                if dt is not None:
                    break
                parent = parent.parent

        if dt is None:
            continue

        # Cherche un lien pertinent dans le titre.
        link = heading.find("a", href=True)
        if link:
            event_url = urljoin(url, link["href"])
        else:
            event_url = url

        start = dt.isoformat()
        key = (title.lower(), start)

        if key in seen:
            continue
        seen.add(key)

        events.append({
            "id": stable_id(f"Infoconcert - {venue}", title, start),
            "title": title,
            "start": start,
            "venue": venue,
            "city": city,
            "category": category,
            "description": "",
            "url": event_url,
            "source": f"Infoconcert - {venue}",
        })

    return events
