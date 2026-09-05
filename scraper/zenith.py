from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://www.zenith-saint-etienne.fr/agenda/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

MONTHS = {
    "janv.": 1,
    "févr.": 2,
    "fevr.": 2,
    "mars": 3,
    "avr.": 4,
    "mai": 5,
    "juin": 6,
    "juil.": 7,
    "août": 8,
    "aout": 8,
    "sept.": 9,
    "oct.": 10,
    "nov.": 11,
    "déc.": 12,
    "dec.": 12,
}

DATE_PATTERN = re.compile(
    r"(\d{1,2})\s+"
    r"(janv\.|févr\.|fevr\.|mars|avr\.|mai|juin|juil\.|août|aout|sept\.|oct\.|nov\.|déc\.|dec\.)"
    r"\s+(\d{4})\s*\|\s*"
    r"(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)


def _clean_title(text: str) -> str:
    text = clean(text)

    # Nettoyage des statuts répétés dans certaines cartes.
    text = re.sub(
        r"^(?:(?:Complet|Annulé|Annule)\s*[•·\-\s]*)+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # On retire "Voir plus" si jamais il se retrouve dans le titre.
    text = re.sub(r"\s*Voir plus\s*$", "", text, flags=re.IGNORECASE)

    return clean(text)


def scrape_zenith() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    # Les vraies fiches spectacle du Zénith ont des URLs /evenement/...
    # Cela évite de récupérer les menus et autres liens de la page.
    links = soup.select('a[href*="/evenement/"]')

    for link in links:
        href = link.get("href")
        if not href:
            continue

        event_url = urljoin(URL, href)

        # Texte de la carte : titre + éventuel sous-titre + date(s) + "Voir plus".
        text = clean(link.get_text(" "))
        if not text or "{title}" in text:
            continue

        matches = list(DATE_PATTERN.finditer(text))
        if not matches:
            continue

        # Le titre correspond à tout le texte précédant la première date.
        title = _clean_title(text[:matches[0].start()])
        if not title:
            continue

        # Une même fiche peut avoir plusieurs représentations
        # (par ex. DUB INC sur deux jours).
        for match in matches:
            day = int(match.group(1))
            month = MONTHS[match.group(2).lower()]
            year = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            try:
                dt = datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    tzinfo=PARIS,
                )
            except ValueError:
                continue

            start = dt.isoformat()

            # Évite les doublons si la même carte apparaît plusieurs fois.
            key = (event_url, start)
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "id": stable_id(
                    "Zénith de Saint-Étienne Métropole",
                    title,
                    start,
                ),
                "title": title,
                "start": start,
                "venue": "Zénith Sainté",
                "city": "Saint-Étienne",
                "category": "Concert",
                "description": "",
                "url": event_url,
                "source": "Zénith de Saint-Étienne Métropole",
            })

    return events
