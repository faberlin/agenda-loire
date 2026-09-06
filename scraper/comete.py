from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://lacomete.saint-etienne.fr/lagenda/"
BASE = "https://lacomete.saint-etienne.fr/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_comete():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    detail_urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        if "/evenements/" in href and href not in seen:
            seen.add(href)
            detail_urls.append(href)

    events = []
    now = datetime.now(PARIS)

    for href in detail_urls:
        try:
            rr = requests.get(href, headers=HEADERS, timeout=20)
            rr.raise_for_status()
        except Exception:
            continue

        ss = BeautifulSoup(rr.text, "html.parser")
        h1 = ss.find("h1")
        title = clean(h1.get_text(" ")) if h1 else ""
        if not title:
            continue

        page = clean(ss.get_text(" "))

        dm = re.search(r"\b(\d{2})/(\d{2})/(20\d{2})\b", page)
        tm = re.search(r"\b(\d{1,2}):(\d{2})\b", page)
        if not dm or not tm:
            continue

        dt = datetime(
            int(dm.group(3)), int(dm.group(2)), int(dm.group(1)),
            int(tm.group(1)), int(tm.group(2)), tzinfo=PARIS
        )
        if dt < now:
            continue

        venue_m = re.search(r"Salle\s*:\s*(.+?)\s+(?:Durée|Duree|###|\d{2}/\d{2}/)", page, re.I)
        venue = clean(venue_m.group(1)) if venue_m else "La Comète"
        if venue.lower() == "autre":
            venue = "La Comète"

        disc_m = re.search(r"Discipline\s*:\s*(.+?)\s+Activité", page, re.I)
        discipline = clean(disc_m.group(1)) if disc_m else "Spectacle"
        cat = {
            "musique": "Musique", "humour": "Humour", "théatre": "Théâtre",
            "théâtre": "Théâtre", "danse": "Danse", "cirque": "Spectacle"
        }.get(discipline.lower(), "Spectacle")

        events.append({
            "id": stable_id("La Comète", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": venue,
            "city": "Saint-Étienne",
            "category": cat,
            "description": "",
            "url": href,
            "source": "La Comète",
        })

    return events
