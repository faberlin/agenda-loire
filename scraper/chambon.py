from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://lechambon.fr/culture/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12
}

DATE_RE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"
    r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+à\s+(\d{1,2})h(?:(\d{2}))?",
    re.I
)

def _year(month):
    return 2026 if month >= 9 else 2027

def scrape_chambon():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    section = soup.find(lambda tag: tag.name in ["h2", "h3"] and "saison culturelle" in clean(tag.get_text(" ")).lower())
    if not section:
        return []

    events = []
    node = section.find_next()

    while node:
        if node.name in ["h2", "h3"] and node is not section:
            break

        text = clean(node.get_text(" ")) if getattr(node, "get_text", None) else ""
        m = DATE_RE.search(text)

        if m:
            date_node = node
            title_node = date_node.find_previous(lambda t: t.name in ["p", "h3", "h4", "div"] and clean(t.get_text(" ")))
            title = clean(title_node.get_text(" ")) if title_node else ""

            # évite de reprendre le titre de section
            if "saison culturelle" in title.lower():
                title = ""

            month = MONTHS.get(m.group(2).lower())
            if not month:
                node = node.find_next()
                continue

            dt = datetime(
                _year(month), month, int(m.group(1)),
                int(m.group(3)), int(m.group(4) or 0), tzinfo=PARIS
            )

            # Le lieu est généralement le bloc juste après la date
            venue = ""
            probe = date_node.find_next()
            for _ in range(4):
                if not probe:
                    break
                t = clean(probe.get_text(" ")) if getattr(probe, "get_text", None) else ""
                if t in {"La Forge", "Espace culturel Albert Camus", "Espace Culturel Albert Camus"}:
                    venue = t
                    break
                probe = probe.find_next()

            if not venue:
                venue = "Le Chambon-Feugerolles"

            link = None
            probe = date_node
            for _ in range(6):
                if not probe:
                    break
                link = probe.find("a", href=True) if getattr(probe, "find", None) else None
                if link and "billetterie" in clean(link.get_text(" ")).lower():
                    break
                probe = probe.find_next()

            url = urljoin(URL, link["href"]) if link else URL

            if title:
                events.append({
                    "id": stable_id("Ville du Chambon-Feugerolles", title, dt.isoformat()),
                    "title": title,
                    "start": dt.isoformat(),
                    "venue": venue,
                    "city": "Le Chambon-Feugerolles",
                    "category": "Spectacle",
                    "description": "",
                    "url": url,
                    "source": "Ville du Chambon-Feugerolles",
                })

        node = node.find_next()

    return events
