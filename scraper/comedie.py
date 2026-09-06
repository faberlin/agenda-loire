from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://www.lacomedie.fr"
LIST = "https://www.lacomedie.fr/la-saison-menu/tous-les-spectacles"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "janv": 1, "janvier": 1,
    "févr": 2, "fevr": 2, "février": 2, "fevrier": 2,
    "mars": 3,
    "avr": 4, "avril": 4,
    "mai": 5, "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8,
    "sept": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12, "decembre": 12
}

DAY = r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?"
MON = (
    r"(janv(?:ier)?|févr(?:ier)?|fevr(?:ier)?|mars|avr(?:il)?|mai|juin|"
    r"juil(?:let)?|août|aout|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|"
    r"déc(?:embre)?|dec(?:embre)?)\.?"
)


def _month(raw: str) -> int:
    return MONTHS[raw.lower().rstrip(".")]


def _detail_urls() -> list[str]:
    found = []
    seen = set()

    for page in range(1, 30):
        url = LIST if page == 1 else f"{LIST}?page={page}"
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        page_urls = []
        for link in soup.find_all("a", href=True):
            if "/programmation/" not in link["href"]:
                continue

            detail_url = urljoin(BASE, link["href"])
            if detail_url not in seen:
                seen.add(detail_url)
                page_urls.append(detail_url)
                found.append(detail_url)

        print(f"La Comédie page {page}: {len(page_urls)} nouvelle(s) fiche(s)")
        if not page_urls:
            break

    return found


def _dates(text: str, year: int) -> list[datetime]:
    pos = re.search(r"\bDates\b", text, re.IGNORECASE)
    if pos:
        text = text[pos.end():]

    stop = re.search(
        r"\b(?:Médias|Medias|Presse|Autour du spectacle|À découvrir aussi|A découvrir aussi)\b",
        text,
        re.IGNORECASE,
    )
    if stop:
        text = text[:stop.start()]

    pattern = re.compile(
        rf"{DAY}\s+(\d{{1,2}})\s+{MON}\s+(\d{{1,2}})h(?:\s*(\d{{2}}))?",
        re.IGNORECASE,
    )

    result = []
    for match in pattern.finditer(text):
        day = int(match.group(1))
        month = _month(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4) or 0)

        try:
            result.append(datetime(year, month, day, hour, minute, tzinfo=PARIS))
        except ValueError:
            continue

    return result


def scrape_comedie() -> list[dict]:
    events = []
    now = datetime.now(PARIS)

    for detail_url in _detail_urls():
        try:
            response = requests.get(detail_url, headers=HEADERS, timeout=30)
            response.raise_for_status()
        except Exception as exc:
            print(f"La Comédie: erreur fiche {detail_url}: {exc}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        h1 = soup.find("h1")
        title = clean(h1.get_text(" ")) if h1 else ""
        if not title:
            continue

        page_text = clean(soup.get_text(" "))

        years = re.findall(r"\b(20\d{2})\b", page_text)
        if not years:
            continue

        year = int(years[0])
        dates = [dt for dt in _dates(page_text, year) if dt >= now]

        if not dates:
            continue

        dates.sort()

        sessions = [dt.isoformat() for dt in dates]
        start = sessions[0]
        end = sessions[-1]

        events.append({
            "id": stable_id("La Comédie de Saint-Étienne", title, start),
            "title": title,
            "start": start,
            "end": end,
            "sessions": sessions,
            "session_count": len(sessions),
            "venue": "La Comédie",
            "city": "Saint-Étienne",
            "category": "Théâtre",
            "description": "",
            "url": detail_url,
            "source": "Comédie Sainté",
        })

    return sorted(events, key=lambda x: x["start"])
