from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://www.lestroisducs.fr/programmation"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

PAT = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(20\d{2})\s+"
    r"(\d{1,2})[hH](\d{2})\s*(.+)$"
)

def scrape_trois_ducs():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" "))
        m = PAT.search(text)
        if not m:
            continue

        month = MONTHS.get(m.group(1))
        if not month:
            continue

        dt = datetime(
            int(m.group(3)), month, int(m.group(2)),
            int(m.group(4)), int(m.group(5)), tzinfo=PARIS
        )
        title = clean(m.group(6))
        title = re.sub(r"^(NOUVEAU\s*!|NOUVELLE SAISON\s*!|HORS LES MURS)\s*", "", title, flags=re.I)

        if not title or "carte cadeau" in title.lower():
            continue

        events.append({
            "id": stable_id("Les Trois Ducs", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Les Trois Ducs",
            "city": "Saint-Étienne",
            "category": "Humour",
            "description": "",
            "url": urljoin(URL, a["href"]),
            "source": "Les Trois Ducs",
        })

    return events
