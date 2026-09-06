from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://le-solar.fr/agenda/"
BASE = "https://le-solar.fr/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}


def _parse_date(text: str):
    date_match = re.search(
        r"\b(\d{1,2})\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
        r"septembre|octobre|novembre|décembre|decembre)\s+"
        r"(20\d{2})\b",
        text,
        re.IGNORECASE,
    )

    time_match = re.search(
        r"(?:À|A|à)\s*(\d{1,2})h(?:(\d{2}))?",
        text,
        re.IGNORECASE,
    )

    if not date_match:
        return None

    day = int(date_match.group(1))
    month = MONTHS[date_match.group(2).lower()]
    year = int(date_match.group(3))
    hour = int(time_match.group(1)) if time_match else 20
    minute = int(time_match.group(2) or 0) if time_match else 0

    try:
        return datetime(year, month, day, hour, minute, tzinfo=PARIS)
    except ValueError:
        return None


def scrape_solar() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    detail_urls = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE, link["href"])
        if "/evenement/" not in href:
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        detail_urls.append(href)

    events = []
    now = datetime.now(PARIS)

    for href in detail_urls:
        try:
            detail = requests.get(href, headers=HEADERS, timeout=25)
            detail.raise_for_status()
        except Exception as exc:
            print(f"Le Solar: erreur fiche {href}: {exc}")
            continue

        page = BeautifulSoup(detail.text, "html.parser")
        h1 = page.find("h1")
        title = clean(h1.get_text(" ")) if h1 else ""
        if not title:
            continue

        text = clean(page.get_text(" "))
        dt = _parse_date(text)
        if not dt or dt < now:
            continue

        events.append({
            "id": stable_id("Le Solar", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Le Solar",
            "city": "Saint-Étienne",
            "category": "Musique",
            "description": "",
            "url": href,
            "source": "Le Solar",
        })

    return sorted(events, key=lambda ev: ev["start"])
