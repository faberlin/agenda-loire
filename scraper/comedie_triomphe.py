from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://www.comedietriomphe.fr/"
LIST_URLS = [
    urljoin(BASE, "cas-categorie/tout-public/"),
    urljoin(BASE, "cas-categorie/jeune-public/"),
]
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _detail_urls() -> list[str]:
    urls = []
    seen = set()

    for list_url in LIST_URLS:
        response = requests.get(list_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = urljoin(BASE, a["href"])

            if "/events/" not in href:
                continue

            if href in seen:
                continue

            seen.add(href)
            urls.append(href)

    return urls


def _sessions(text: str) -> list[datetime]:
    # Sur les fiches : 11/09/2026 20:00 - 21:15
    pattern = re.compile(
        r"\b(\d{2})/(\d{2})/(20\d{2})\s+"
        r"(\d{1,2}):(\d{2})\s*[-à]\s*"
        r"\d{1,2}:\d{2}\b"
    )

    seen = set()
    result = []

    for m in pattern.finditer(text):
        dt = datetime(
            int(m.group(3)),
            int(m.group(2)),
            int(m.group(1)),
            int(m.group(4)),
            int(m.group(5)),
            tzinfo=PARIS,
        )

        key = dt.isoformat()
        if key in seen:
            continue

        seen.add(key)
        result.append(dt)

    return sorted(result)


def scrape_comedie_triomphe() -> list[dict]:
    urls = _detail_urls()
    print(f"Comédie Triomphe: {len(urls)} fiche(s) découverte(s)")

    now = datetime.now(PARIS)
    events = []

    for href in urls:
        try:
            response = requests.get(href, headers=HEADERS, timeout=25)
            response.raise_for_status()
        except Exception as exc:
            print(f"Comédie Triomphe: erreur fiche {href}: {exc}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Les fiches utilisent parfois h1, parfois h3.
        heading = soup.find("h1") or soup.find("h3")
        title = clean(heading.get_text(" ")) if heading else ""

        if not title:
            # fallback sur le slug
            title = href.rstrip("/").split("/")[-1].replace("-", " ").title()

        text = clean(soup.get_text(" "))
        sessions = [dt for dt in _sessions(text) if dt >= now]

        if not sessions:
            continue

        session_strings = [dt.isoformat() for dt in sessions]
        start = session_strings[0]

        events.append({
            "id": stable_id("La Comédie Triomphe", title, start),
            "title": title,
            "start": start,
            "end": session_strings[-1],
            "sessions": session_strings,
            "session_count": len(session_strings),
            "venue": "La Comédie Triomphe",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": href,
            "source": "Comédie Triomphe",
        })

    return sorted(events, key=lambda ev: ev["start"])
