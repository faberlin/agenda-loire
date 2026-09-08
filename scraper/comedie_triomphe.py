from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


LIST_URL = "https://www.comedietriomphe.fr/tout-publicold/"
DETAIL_URL = "https://www.comedietriomphe.fr/cas-categorie/tout-public/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SESSION_RE = re.compile(
    r"\b(\d{2})/(\d{2})/(20\d{2})\s+"
    r"(\d{1,2}):(\d{2})\s*-\s*"
    r"(\d{1,2}):(\d{2})\b"
)


def _list_titles_and_urls():
    """
    La vieille page est très pratique pour récupérer les spectacles
    et leurs liens de fiche.
    """
    response = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" "))
        if not title:
            continue

        href = urljoin(LIST_URL, a["href"])

        # On ne garde que les liens qui semblent être des fiches de spectacle.
        if href.startswith(LIST_URL):
            continue
        if "comedietriomphe.fr" not in href:
            continue

        key = (title.lower(), href)
        if key in seen:
            continue
        seen.add(key)

        # On vérifie qu'une date ou plage suit bien le lien dans la page.
        nxt = a.find_next(string=re.compile(
            r"\b(?:le|du)\s+\d{2}/\d{2}/20\d{2}",
            re.IGNORECASE
        ))
        if not nxt:
            continue

        items.append((title, href))

    return items


def _sections_from_detail_page():
    """
    La page moderne /cas-categorie/tout-public/ contient tous les spectacles
    avec leurs séances exactes. On découpe la page par H2.
    """
    response = requests.get(DETAIL_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    sections = {}

    headings = soup.find_all("h2")

    for i, h2 in enumerate(headings):
        title = clean(h2.get_text(" "))
        if not title:
            continue

        start = h2
        end = headings[i + 1] if i + 1 < len(headings) else None

        chunks = []
        node = start.find_next()

        while node and node is not end:
            if getattr(node, "get_text", None):
                text = clean(node.get_text(" "))
                if text:
                    chunks.append(text)
            node = node.find_next()

        text = " ".join(chunks)

        sessions = []
        seen = set()

        for m in SESSION_RE.finditer(text):
            dt = datetime(
                int(m.group(3)),
                int(m.group(2)),
                int(m.group(1)),
                int(m.group(4)),
                int(m.group(5)),
                tzinfo=PARIS,
            )

            if dt.isoformat() not in seen:
                seen.add(dt.isoformat())
                sessions.append(dt)

        if sessions:
            sections[title.lower()] = {
                "title": title,
                "sessions": sorted(sessions),
            }

    return sections


def scrape_comedie_triomphe() -> list[dict]:
    now = datetime.now(PARIS)

    list_items = _list_titles_and_urls()
    detail_sections = _sections_from_detail_page()

    print(
        f"Comédie Triomphe: {len(list_items)} spectacle(s) listé(s), "
        f"{len(detail_sections)} bloc(s) avec séances"
    )

    events = []

    # On utilise les titres/liens de la vieille page,
    # et les séances exactes de la page moderne.
    for title, href in list_items:
        section = detail_sections.get(title.lower())

        if not section:
            # Petit fallback tolérant sur apostrophes/accents/espaces.
            norm_title = (
                title.lower()
                .replace("’", "'")
                .replace("“", '"')
                .replace("”", '"')
            )

            for key, value in detail_sections.items():
                norm_key = (
                    key
                    .replace("’", "'")
                    .replace("“", '"')
                    .replace("”", '"')
                )

                if norm_title == norm_key:
                    section = value
                    break

        if not section:
            print(f"Comédie Triomphe: séances introuvables pour {title}")
            continue

        sessions = [dt for dt in section["sessions"] if dt >= now]

        if not sessions:
            continue

        session_strings = [dt.isoformat() for dt in sessions]

        events.append({
            "id": stable_id(
                "Comédie Triomphe",
                title,
                session_strings[0]
            ),
            "title": title,
            "start": session_strings[0],
            "end": session_strings[-1],
            "sessions": session_strings,
            "session_count": len(session_strings),
            "venue": "Comédie Triomphe",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": href,
            "source": "Comédie Triomphe",
        })

    return sorted(events, key=lambda ev: ev["start"])
