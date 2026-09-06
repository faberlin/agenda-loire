from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://billetterie-leverso.mapado.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janv": 1, "janvier": 1,
    "févr": 2, "fevr": 2, "février": 2, "fevrier": 2,
    "mars": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8,
    "sept": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12, "decembre": 12,
}

DATE_RE = re.compile(
    r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?\s+"
    r"(\d{1,2})\s+"
    r"(janv(?:ier)?|févr(?:ier)?|fevr(?:ier)?|mars|avr(?:il)?|mai|juin|"
    r"juil(?:let)?|août|aout|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|"
    r"déc(?:embre)?|dec(?:embre)?)\.?\s+"
    r"(20\d{2})\s+à\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)


def scrape_verso() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = urljoin(URL, link["href"])
        if "/event/" not in href:
            continue

        text = clean(link.get_text(" "))
        match = DATE_RE.search(text)
        if not match:
            # Parfois la date est dans le conteneur de la carte.
            parent = link.find_parent()
            parent_text = clean(parent.get_text(" ")) if parent else text
            match = DATE_RE.search(parent_text)
            text = parent_text

        if not match:
            continue

        month_key = match.group(2).lower().rstrip(".")
        month = MONTHS.get(month_key)
        if not month:
            continue

        dt = datetime(
            int(match.group(3)),
            month,
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5)),
            tzinfo=PARIS,
        )

        # Le titre est avant la date sur la carte Mapado.
        title = clean(text[:match.start()])
        title = re.sub(
            r"^(programmation|en ce moment)\s*",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        # Si la carte contient trop de texte, on préfère le texte du lien.
        link_text = clean(link.get_text(" "))
        if DATE_RE.search(link_text):
            candidate = clean(link_text[:DATE_RE.search(link_text).start()])
            if candidate:
                title = candidate

        if not title:
            continue

        if title.lower() in {
            "adhésion", "adhesion", "carte 5 places",
            "adhésion à l'association théâtre le verso",
        }:
            continue

        key = (title.lower(), dt.isoformat())
        if key in seen:
            continue
        seen.add(key)

        events.append({
            "id": stable_id("Théâtre Le Verso", title, dt.isoformat()),
            "title": title,
            "start": dt.isoformat(),
            "venue": "Théâtre Le Verso",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": href,
            "source": "Théâtre Le Verso",
        })

    return sorted(events, key=lambda ev: ev["start"])
