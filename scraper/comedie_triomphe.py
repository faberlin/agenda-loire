from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://www.comedietriomphe.fr/tout-publicold/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def parse_fr_date(s):
    return datetime.strptime(s, "%d/%m/%Y").replace(tzinfo=PARIS)

def scrape_comedie_triomphe():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    # La page liste les spectacles et leurs plages de dates.
    # On conserve un événement par spectacle et la plage début/fin.
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" "))
        if not title:
            continue

        nxt = a.find_next(string=re.compile(r"\b(?:le|du)\s+\d{2}/\d{2}/20\d{2}", re.I))
        if not nxt:
            continue

        date_text = clean(str(nxt))
        single = re.search(r"\ble\s+(\d{2}/\d{2}/20\d{2})", date_text, re.I)
        span = re.search(r"\bdu\s+(\d{2}/\d{2}/20\d{2})\s+au\s+(\d{2}/\d{2}/20\d{2})", date_text, re.I)

        if span:
            start_dt = parse_fr_date(span.group(1))
            end_dt = parse_fr_date(span.group(2))
        elif single:
            start_dt = parse_fr_date(single.group(1))
            end_dt = start_dt
        else:
            continue

        if start_dt.year < 2026:
            continue

        events.append({
            "id": stable_id("La Comédie Triomphe", title, start_dt.isoformat()),
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "venue": "La Comédie Triomphe",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": urljoin(URL, a["href"]),
            "source": "La Comédie Triomphe",
        })

    # retire les liens de menu / doublons
    uniq = {}
    for ev in events:
        key = (ev["title"].lower(), ev["start"])
        uniq[key] = ev

    return list(uniq.values())
