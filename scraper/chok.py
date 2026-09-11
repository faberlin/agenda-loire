from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://choktheatre.com/"
SITEMAPS = [
    "https://choktheatre.com/wp-sitemap-posts-post-1.xml",
    "https://choktheatre.com/post-sitemap.xml",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

DATE_RE = re.compile(
    r"\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
    r"(\d{1,2})(?:er)?\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})\s*[-–—|]\s*"
    r"(\d{1,2})h(\d{2})\b",
    re.IGNORECASE,
)

# Certains articles écrivent "20 septembre 2026 - 17h00"
# ou "Dimanche 20 septembre 2026 - 17h00".
SEASON_MARKERS = (
    "saison 26/27",
    "saison 2026-2027",
    "26-27 #1",
    "2026-2027",
)


def infer_category(text: str) -> str:
    value = text.lower()

    if any(word in value for word in (
        "concert", "musique", "chanson", "jazz",
    )):
        return "Musique"

    if any(word in value for word in (
        "danse", "butô", "buto",
    )):
        return "Danse"

    if any(word in value for word in (
        "jeune public", "enfant", "conte",
    )):
        return "Jeune public"

    if any(word in value for word in (
        "humour", "stand-up", "stand up",
    )):
        return "Humour"

    if any(word in value for word in (
        "théâtre", "theatre", "lecture", "performance",
    )):
        return "Théâtre"

    return "Spectacle"


def sitemap_urls() -> list[str]:
    urls = []

    for sitemap in SITEMAPS:
        try:
            r = requests.get(sitemap, headers=HEADERS, timeout=30)
            if not r.ok:
                continue

            root = ET.fromstring(r.text)

            for loc in root.iter():
                if loc.tag.endswith("loc") and loc.text:
                    url = clean(loc.text)
                    if url.startswith(BASE):
                        urls.append(url)

            if urls:
                break
        except Exception:
            continue

    # Fallback minimum : page de programmation + lancement de saison.
    if not urls:
        urls = [
            urljoin(BASE, "programmation/"),
            urljoin(BASE, "lancement-saison-2026-2027%E2%86%92acte-1/"),
        ]

    return list(dict.fromkeys(urls))


def extract_dates(text: str) -> list[datetime]:
    result = {}

    for m in DATE_RE.finditer(text):
        day = int(m.group(1))
        month = MONTHS[m.group(2).lower()]
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))

        try:
            dt = datetime(
                year, month, day, hour, minute, tzinfo=PARIS
            )
        except ValueError:
            continue

        if year not in (2026, 2027):
            continue

        result[dt.isoformat()] = dt

    return sorted(result.values())


def scrape_chok() -> list[dict]:
    events = []
    seen = set()

    urls = sitemap_urls()
    candidates = 0

    for url in urls:
        # On ignore les pages structurelles évidentes.
        if any(part in url for part in (
            "/category/",
            "/tag/",
            "/author/",
            "/wp-",
            "/feed",
        )):
            continue

        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if not r.ok:
                continue
        except requests.RequestException:
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        text = clean(soup.get_text(" "))

        if not any(marker in text.lower() for marker in SEASON_MARKERS):
            continue

        dates = extract_dates(text)
        if not dates:
            continue

        candidates += 1

        h1 = soup.find("h1")
        if h1:
            title = clean(h1.get_text(" "))
        else:
            title_tag = soup.find("title")
            title = clean(title_tag.get_text(" ")) if title_tag else ""

        title = re.sub(
            r"\s*(?:-|–|—|\|)\s*Chok théâtre.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            r"\s*Mise à jour récente\s*!?\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        if not title:
            continue

        category = infer_category(text)

        for dt in dates:
            start = dt.isoformat()
            event_id = stable_id("Chok Théâtre", title, start)

            if event_id in seen:
                continue

            seen.add(event_id)
            events.append({
                "id": event_id,
                "title": title,
                "start": start,
                "venue": "Chok Théâtre",
                "city": "Saint-Étienne",
                "category": category,
                "description": "",
                "url": url,
                "source": "Chok Théâtre",
            })

    events.sort(key=lambda e: (e["start"], e["title"].lower()))

    print(f"Chok Théâtre : {candidates} fiche(s) saison 26/27")
    print(f"Chok Théâtre : {len(events)} représentation(s)")

    return events


if __name__ == "__main__":
    for event in scrape_chok():
        print(event)
