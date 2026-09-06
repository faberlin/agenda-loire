from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://www.arcomik.com/billetterie-2/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janvier":1, "février":2, "fevrier":2, "mars":3, "avril":4,
    "mai":5, "juin":6, "juillet":7, "août":8, "aout":8,
    "septembre":9, "octobre":10, "novembre":11, "décembre":12, "decembre":12
}

def scrape_arcomik():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = clean(soup.get_text(" "))

    # L'année est donnée dans le titre "La programmation 2027"
    ym = re.search(r"programmation\s+(20\d{2})", text, re.I)
    year = int(ym.group(1)) if ym else datetime.now(PARIS).year

    events = []
    seen = set()

    for h in soup.find_all(["h2", "h3", "h4"]):
        title = clean(h.get_text(" "))
        if not title or title.lower().startswith("la programmation"):
            continue

        block = h.parent
        block_text = clean(block.get_text(" ")) if block else ""
        m = re.search(
            r"Date\s*:\s*(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+"
            r"Heure\s*:\s*(\d{1,2})h(\d{2})\s+"
            r"Lieu\s*:\s*(.+?)\s+Ville\s*:\s*(.+?)(?:\s+En savoir plus|$)",
            block_text, re.I
        )
        if not m:
            continue

        month = MONTHS.get(m.group(2).lower())
        if not month:
            continue

        dt = datetime(year, month, int(m.group(1)), int(m.group(3)), int(m.group(4)), tzinfo=PARIS)
        venue = clean(m.group(5))
        city = clean(m.group(6))
        link = h.find("a", href=True) or (block.find("a", href=True) if block else None)
        url = urljoin(URL, link["href"]) if link else URL

        key = (title.lower(), dt.isoformat(), venue.lower())
        if key in seen:
            continue
        seen.add(key)

        events.append({
            "id": stable_id("ArcomiK Festival", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": venue,
            "city": city,
            "category": "Humour",
            "description": "",
            "url": url,
            "source": "ArcomiK Festival",
        })

    return events
