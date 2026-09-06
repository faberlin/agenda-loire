from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from utils import PARIS, clean, stable_id

URL = "https://billetterie-lesolar.mapado.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_solar():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" "))
        if not text or "carte de membre" in text.lower() or "bon cadeau" in text.lower():
            continue

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
        title = re.sub(r"^(nouveau|complet)\s*!?\s*", "", title, flags=re.I)
        if not title:
            continue

        url = urljoin(URL, a["href"])
        events.append({
            "id": stable_id("Le Solar", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Le Solar",
            "city": "Saint-Étienne",
            "category": "Musique",
            "description": "",
            "url": url,
            "source": "Le Solar",
        })

    return events
