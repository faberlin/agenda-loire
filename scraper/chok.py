from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


PROGRAMMATION_URL = "https://choktheatre.com/programmation/"
CALAMEO_URL = "https://www.calameo.com/books/0074686781c45d39c3f39"

HEADERS = {
    "User-Agent": "AgendaLoire/1.0 (personal cultural events aggregator)"
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

WEEKDAY = (
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)"
)

DATE_RE = re.compile(
    rf"(?:{WEEKDAY}\s+)?"
    r"(\d{1,2})(?:er)?\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})"
    r"(?:\s*[-–—|]\s*|\s+)"
    r"(\d{1,2})\s*h\s*(\d{2})?",
    re.IGNORECASE,
)

# Cas du type :
# "du jeudi 8 au samedi 10 octobre 2026 - 20h"
RANGE_RE = re.compile(
    rf"du\s+(?:{WEEKDAY}\s+)?(\d{{1,2}})(?:er)?\s+"
    rf"au\s+(?:{WEEKDAY}\s+)?(\d{{1,2}})(?:er)?\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})"
    r"(?:\s*[-–—|]\s*|\s+)"
    r"(\d{1,2})\s*h\s*(\d{2})?",
    re.IGNORECASE,
)


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def infer_category(text: str) -> str:
    value = text.lower()

    if "danse" in value or "butô" in value or "buto" in value:
        return "Opéra-Danse"

    if any(word in value for word in (
        "concert",
        "musique",
        "musical",
        "chanson",
        "jazz",
    )):
        return "Concerts"

    if any(word in value for word in (
        "humour",
        "stand-up",
    )):
        return "Humour"

    if any(word in value for word in (
        "théâtre",
        "theatre",
        "comédie",
        "comedie",
    )):
        return "Théâtre"

    return "Spectacle"


def parse_dates(text: str) -> list[datetime]:
    """
    Récupère une ou plusieurs représentations depuis le texte
    d'une fiche du Chok.
    """
    dates = []

    # Plage continue, ex. du 8 au 10 octobre 2026 - 20h
    for match in RANGE_RE.finditer(text):
        start_day = int(match.group(1))
        end_day = int(match.group(2))
        month = MONTHS[match.group(3).lower()]
        year = int(match.group(4))
        hour = int(match.group(5))
        minute = int(match.group(6) or 0)

        for day in range(start_day, end_day + 1):
            try:
                dates.append(
                    datetime(
                        year,
                        month,
                        day,
                        hour,
                        minute,
                        tzinfo=PARIS,
                    )
                )
            except ValueError:
                pass

    # Dates simples.
    for match in DATE_RE.finditer(text):
        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5) or 0)

        try:
            dates.append(
                datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    tzinfo=PARIS,
                )
            )
        except ValueError:
            pass

    # Déduplication.
    result = {}
    for dt in dates:
        result[dt.isoformat()] = dt

    return sorted(result.values())


def title_from_page(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")

    if h1:
        title = clean(h1.get_text(" "))

        # Le site ajoute parfois des mentions techniques au H1.
        title = re.sub(
            r"\s*[-–—]\s*(mise à jour récente.*)$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        if title:
            return title

    title_tag = soup.find("title")

    if title_tag:
        title = clean(title_tag.get_text(" "))
        title = re.sub(
            r"\s*[-–—|]\s*Chok théâtre.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        return title

    return ""


def discover_event_urls() -> list[str]:
    """
    Découvre les fiches depuis la page Programmation.

    La brochure Calaméo 26-27 est conservée comme référence,
    mais les fiches HTML du Chok sont utilisées pour récupérer
    automatiquement les dates et horaires sans OCR.
    """
    soup = get_soup(PROGRAMMATION_URL)

    urls = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if not href:
            continue

        url = urljoin(PROGRAMMATION_URL, href)

        if not url.startswith("https://choktheatre.com/"):
            continue

        # On exclut les pages structurelles.
        lower = url.lower().rstrip("/")
        if any(lower.endswith(part) for part in (
            "/programmation",
            "/le-chok-theatre",
            "/contact",
            "/billetterie",
        )):
            continue

        if url in seen:
            continue

        text = clean(link.get_text(" "))
        parent_text = clean(link.parent.get_text(" ")) if link.parent else ""

        # Le lien doit se trouver dans un bloc ressemblant à une
        # programmation : saison 26/27 ou date visible.
        context = f"{text} {parent_text}".lower()

        if not (
            "26/27" in context
            or "2026" in context
            or "2027" in context
            or re.search(
                r"\b(?:septembre|octobre|novembre|décembre|janvier|"
                r"février|mars|avril|mai|juin)\b",
                context,
                re.IGNORECASE,
            )
        ):
            continue

        seen.add(url)
        urls.append(url)

    return urls


def scrape_event(url: str) -> list[dict]:
    soup = get_soup(url)
    title = title_from_page(soup)

    if not title:
        return []

    text = clean(soup.get_text(" "))

    # On ne garde que la saison actuelle.
    if "2026" not in text and "2027" not in text:
        return []

    dates = parse_dates(text)

    if not dates:
        print(f"Chok Théâtre: aucune date trouvée pour {title} ({url})")
        return []

    category = infer_category(text)
    events = []

    for dt in dates:
        # Évite de récupérer une date de publication WordPress ou
        # une date ancienne présente dans le corps de page.
        if dt.year not in (2026, 2027):
            continue

        start = dt.isoformat()

        events.append({
            "id": stable_id("Chok Théâtre", title, start),
            "title": title,
            "start": start,
            "venue": "Chok Théâtre",
            "city": "Saint-Étienne",
            "category": category,
            "description": "",
            "url": url,
            "source": "Chok Théâtre",
        })

    return events


def scrape_chok() -> list[dict]:
    events = []
    seen_ids = set()

    urls = discover_event_urls()

    print(
        f"Chok Théâtre : {len(urls)} fiche(s) trouvée(s) "
        f"depuis la programmation"
    )

    for url in urls:
        try:
            page_events = scrape_event(url)
        except requests.RequestException as exc:
            print(f"Chok Théâtre: erreur sur {url}: {exc}")
            continue

        for event in page_events:
            if event["id"] in seen_ids:
                continue

            seen_ids.add(event["id"])
            events.append(event)

    events.sort(key=lambda event: event["start"])

    print(f"Chok Théâtre : {len(events)} représentation(s)")
    print(f"Brochure de référence : {CALAMEO_URL}")

    return events


if __name__ == "__main__":
    for event in scrape_chok():
        print(event)
