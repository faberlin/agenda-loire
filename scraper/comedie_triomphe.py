from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://www.comedietriomphe.fr/"
URLS = [
    urljoin(BASE, "cas-categorie/tout-public/"),
    urljoin(BASE, "cas-categorie/jeune-public/"),
]
HEADERS = {"User-Agent": "Mozilla/5.0"}

SESSION_RE = re.compile(
    r"\b(\d{2})/(\d{2})/(20\d{2})\s+"
    r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\b"
)


def _extract_sections(soup: BeautifulSoup):
    """
    La page moderne contient un H2 par spectacle puis une liste de dates.
    On lit chaque H2 jusqu'au H2 suivant.
    """
    for heading in soup.find_all("h2"):
        title = clean(heading.get_text(" "))
        if not title:
            continue

        chunks = []
        node = heading.find_next()

        while node and node is not heading:
            if getattr(node, "name", None) == "h2":
                break

            if getattr(node, "get_text", None):
                text = clean(node.get_text(" "))
                if text:
                    chunks.append(text)

            node = node.find_next()

        yield heading, title, " ".join(chunks)


def scrape_comedie_triomphe() -> list[dict]:
    now = datetime.now(PARIS)
    events = []
    seen = set()

    for page_url in URLS:
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for heading, title, section_text in _extract_sections(soup):
            sessions = []

            for match in SESSION_RE.finditer(section_text):
                dt = datetime(
                    int(match.group(3)),
                    int(match.group(2)),
                    int(match.group(1)),
                    int(match.group(4)),
                    int(match.group(5)),
                    tzinfo=PARIS,
                )

                if dt >= now:
                    sessions.append(dt)

            # Certains blocs n'affichent que "23/09/2026" puis l'heure ailleurs.
            if not sessions:
                fallback = re.findall(
                    r"\b(\d{2})/(\d{2})/(20\d{2})\b",
                    section_text
                )
                time_match = re.search(
                    r"\b(\d{1,2}):(\d{2})\b",
                    section_text
                )

                if time_match:
                    for day, month, year in fallback:
                        dt = datetime(
                            int(year), int(month), int(day),
                            int(time_match.group(1)),
                            int(time_match.group(2)),
                            tzinfo=PARIS,
                        )
                        if dt >= now:
                            sessions.append(dt)

            # dédoublonnage car la billetterie répète les mêmes dates
            sessions = sorted(set(sessions))
            if not sessions:
                continue

            start = sessions[0].isoformat()
            session_strings = [dt.isoformat() for dt in sessions]

            # lien du titre si présent, sinon page catégorie
            link = heading.find("a", href=True)
            href = urljoin(page_url, link["href"]) if link else page_url

            key = (title.lower(), tuple(session_strings))
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "id": stable_id(
                    "La Comédie Triomphe",
                    title,
                    start
                ),
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
                "source": "La Comédie Triomphe",
            })

    return sorted(events, key=lambda ev: ev["start"])
