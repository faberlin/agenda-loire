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
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}

DATE_RE = re.compile(
    r"^(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"
    r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+à\s+"
    r"(\d{1,2})h(?:(\d{2}))?$",
    re.IGNORECASE,
)

VENUES = {
    "la forge": "La Forge",
    "espace culturel albert camus": "Espace culturel Albert Camus",
    "espace culturel a. camus": "Espace culturel Albert Camus",
}

SKIP = {
    "billetterie", "image", "lecteur vidéo vimeo", "video",
    "télécharger le programme", "telecharger le programme",
    "prendre un abonnement",
}


def _season_year(month: int) -> int:
    # Saison 2026/2027
    return 2026 if month >= 9 else 2027


def scrape_chambon() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    lines = [clean(x) for x in soup.stripped_strings]
    lines = [x for x in lines if x]

    # On ne travaille que dans la zone "Saison culturelle 2026/2027".
    start = next(
        (i for i, line in enumerate(lines)
         if "saison culturelle 2026/2027" in line.lower()),
        None
    )
    if start is None:
        return []

    end = next(
        (i for i in range(start + 1, len(lines))
         if lines[i].lower() == "abonnements"),
        len(lines)
    )

    lines = lines[start + 1:end]

    events = []
    seen = set()

    for i, line in enumerate(lines):
        match = DATE_RE.match(line)
        if not match:
            continue

        day = int(match.group(1))
        month_name = match.group(2).lower()
        month = MONTHS.get(month_name)
        if not month:
            continue

        hour = int(match.group(3))
        minute = int(match.group(4) or 0)
        dt = datetime(
            _season_year(month), month, day, hour, minute, tzinfo=PARIS
        )

        # Titre = première ligne utile juste avant la date.
        title = ""
        for j in range(i - 1, max(-1, i - 8), -1):
            candidate = lines[j]
            low = candidate.lower()
            if low in SKIP:
                continue
            if DATE_RE.match(candidate):
                break
            if low in VENUES:
                continue
            if low.startswith("billetterie"):
                continue
            if low.startswith("saison culturelle"):
                continue
            title = candidate
            break

        if not title:
            continue

        # Salle = première salle reconnue juste après la date.
        venue = ""
        for j in range(i + 1, min(len(lines), i + 8)):
            candidate = lines[j]
            low = candidate.lower()

            if low in VENUES:
                venue = VENUES[low]
                break

            if DATE_RE.match(candidate):
                break

        if not venue:
            # Les seules salles de cette programmation sont La Forge et Albert Camus.
            # Si la page change, on préfère ignorer plutôt qu'inventer un lieu.
            continue

        key = (title.lower(), dt.isoformat(), venue.lower())
        if key in seen:
            continue
        seen.add(key)

        events.append({
            "id": stable_id(
                "Ville du Chambon-Feugerolles",
                title,
                dt.isoformat()
            ),
            "title": title,
            "start": dt.isoformat(),
            "venue": venue,
            "city": "Le Chambon-Feugerolles",
            "category": "Spectacle",
            "description": "",
            "url": URL,
            "source": " Salles Chambon-Feugerolles",
        })

    return sorted(events, key=lambda ev: ev["start"])
