from __future__ import annotations
import re
from dateutil import parser as dateparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://billetterie-leverso.mapado.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_verso():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" "))
        m = re.search(
            r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"\s+(\d{1,2}),\s+(20\d{2})\s+at\s+(\d{1,2}):(\d{2})\s*(AM|PM)",
            text, re.I
        )
        if not m:
            continue

        try:
            dt = dateparser.parse(m.group(0), fuzzy=True).replace(tzinfo=PARIS)
        except Exception:
            continue

        title = clean(text[:m.start()])
        if not title or "adhésion" in title.lower() or "carte" in title.lower():
            continue

        events.append({
            "id": stable_id("Théâtre Le Verso", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Théâtre Le Verso",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": urljoin(URL, a["href"]),
            "source": "Théâtre Le Verso",
        })

    return events
