from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://choktheatre.com/programmation/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janvier":1, "février":2, "fevrier":2, "mars":3, "avril":4,
    "mai":5, "juin":6, "juillet":7, "août":8, "aout":8,
    "septembre":9, "octobre":10, "novembre":11, "décembre":12, "decembre":12
}

def scrape_chok():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = []
    now = datetime.now(PARIS)

    # Le site est très irrégulier : on travaille fiche par fiche.
    # Si la programmation 2026-27 n'est pas encore publiée, ce scraper renverra 0.
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(URL, a["href"])
        title = clean(a.get_text(" "))
        if not title or href in seen:
            continue
        if "programmation" in href or "saison-" in href or href.rstrip("/") == URL.rstrip("/"):
            continue
        if "choktheatre.com" not in href:
            continue
        seen.add(href)
        links.append((title, href))

    for fallback_title, href in links:
        try:
            rr = requests.get(href, headers=HEADERS, timeout=20)
            rr.raise_for_status()
        except Exception:
            continue

        ss = BeautifulSoup(rr.text, "html.parser")
        h1 = ss.find("h1") or ss.find("h2")
        title = clean(h1.get_text(" ")) if h1 else fallback_title
        page = clean(ss.get_text(" "))

        # cherche une date française avec année explicite
        m = re.search(
            r"(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(20\d{2})"
            r".{0,80}?(\d{1,2})h(?:(\d{2}))?",
            page, re.I
        )
        if not m:
            continue

        month = MONTHS[m.group(2).lower()]
        dt = datetime(int(m.group(3)), month, int(m.group(1)), int(m.group(4)), int(m.group(5) or 0), tzinfo=PARIS)
        if dt < now:
            continue

        events.append({
            "id": stable_id("Chok Théâtre", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Chok Théâtre",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": href,
            "source": "Chok Théâtre",
        })

    return events
