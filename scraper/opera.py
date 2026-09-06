from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://opera.saint-etienne.fr/otse/agenda/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12
}


def _year(month: int) -> int:
    return 2026 if month >= 9 else 2027


def scrape_opera() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    raw = []
    current_month = None

    for node in soup.find_all(["h2", "h3", "h4", "tr"]):
        if node.name in {"h2", "h3", "h4"}:
            heading = clean(node.get_text(" ")).lower()
            for name, number in MONTHS.items():
                if heading == name or heading.endswith(name):
                    current_month = number
                    break
            continue

        if node.name != "tr" or current_month is None:
            continue

        cells = node.find_all(["td", "th"])
        if len(cells) < 3:
            continue

        row_text = clean(node.get_text(" "))
        match = re.search(
            r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?"
            r"(?:\s*\([^)]+\))?\s*"
            r"(\d{1,2})\s+(\d{1,2}):(\d{2})",
            row_text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        day, hour, minute = map(int, match.groups())

        try:
            dt = datetime(
                _year(current_month),
                current_month,
                day,
                hour,
                minute,
                tzinfo=PARIS,
            )
        except ValueError:
            continue

        title = clean(cells[2].get_text(" "))
        if not title:
            continue

        link = node.find("a", href=True)
        event_url = urljoin(URL, link["href"]) if link else URL

        raw.append({
            "title": title,
            "dt": dt,
            "url": event_url,
        })

    grouped = {}

    for item in raw:
        key = (item["title"].lower(), item["url"])
        grouped.setdefault(key, []).append(item)

    events = []

    for items in grouped.values():
        items.sort(key=lambda x: x["dt"])
        first = items[0]
        last = items[-1]

        sessions = [item["dt"].isoformat() for item in items]
        start = sessions[0]
        end = sessions[-1]

        events.append({
            "id": stable_id("Opéra de Saint-Étienne", first["title"], start),
            "title": first["title"],
            "start": start,
            "end": end,
            "sessions": sessions,
            "session_count": len(sessions),
            "venue": "Opéra Sainté",
            "city": "Saint-Étienne",
            "category": "Opéra",
            "description": "",
            "url": first["url"],
            "source": "Opéra de Saint-Étienne",
        })

    return sorted(events, key=lambda x: x["start"])
