from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE_URL = (
    "https://www.fnacspectacles.com/city/st-etienne-2042/"
    "venue/le-triomphe-st-etienne-80471/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

MONTHS = {
    "janv": 1, "jan": 1,
    "févr": 2, "fevr": 2, "fév": 2, "fev": 2,
    "mars": 3,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "août": 8, "aout": 8,
    "sept": 9, "sep": 9,
    "oct": 10,
    "nov": 11,
    "déc": 12, "dec": 12,
}

# Exemple FNAC :
# 11 sept. 2026 ven. 20:00
DATE_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(janv?|févr?|fevr?|mars|avr|mai|juin|juil|août|aout|sept?|oct|nov|déc|dec)"
    r"\.?\s+(\d{4})\s+"
    r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?\s+"
    r"(\d{1,2}):(\d{2})\b",
    re.IGNORECASE,
)


def normalize_month(value: str) -> int | None:
    value = (
        value.lower()
        .replace(".", "")
        .replace("é", "e")
        .replace("û", "u")
    )

    aliases = {
        "jan": 1, "janv": 1,
        "fev": 2, "fevr": 2,
        "mars": 3,
        "avr": 4,
        "mai": 5,
        "juin": 6,
        "juil": 7,
        "aout": 8,
        "sep": 9, "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return aliases.get(value)


def infer_category(title: str) -> str:
    value = title.lower()

    if any(word in value for word in (
        "petit fantôme", "petit fantome", "citrouillette",
        "enfant", "petite sorcière", "petite sorciere",
    )):
        return "Jeune public"

    if any(word in value for word in (
        "magie", "mental", "hypnose",
    )):
        return "Spectacle"

    if any(word in value for word in (
        "stand-up", "stand up", "one man", "one-man",
        "humour", "comedy",
    )):
        return "Humour"

    # Le Triomphe programme majoritairement comédies et café-théâtre.
    return "Théâtre"


def page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    return f"{BASE_URL}?pnum={page}"


def extract_events_from_page(page: int) -> list[dict]:
    url = page_url(page)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    # Les titres de spectacles sont des H2. Pour chaque H2, on cherche
    # la date immédiatement AVANT le titre, ce qui évite d'associer la
    # séance suivante au mauvais spectacle.
    for h2 in soup.find_all("h2"):
        title = clean(h2.get_text(" "))
        if not title:
            continue

        # Ignore les titres structurels de la page.
        if title.lower() in {
            "accès", "acces", "avis",
        }:
            continue

        date_match = None
        node = h2

        # Remonte dans l'ordre du document, avec une limite pour ne pas
        # capturer la date d'un spectacle précédent.
        for _ in range(20):
            node = node.find_previous()
            if node is None:
                break

            text = clean(node.get_text(" "))

            match = DATE_RE.search(text)
            if match:
                date_match = match
                break

            # Si on croise un autre H2 avant une date, ce H2 n'est pas
            # une carte spectacle exploitable.
            if node.name == "h2":
                break

        if not date_match:
            continue

        day = int(date_match.group(1))
        month = normalize_month(date_match.group(2))
        year = int(date_match.group(3))
        hour = int(date_match.group(4))
        minute = int(date_match.group(5))

        if not month:
            continue

        try:
            dt = datetime(
                year, month, day, hour, minute, tzinfo=PARIS
            )
        except ValueError:
            continue

        # Cherche le lien de réservation / fiche dans la carte.
        event_url = url
        container = h2.parent
        for _ in range(6):
            if container is None:
                break
            link = container.find("a", href=True)
            if link:
                href = link.get("href", "")
                if href and not href.startswith("#"):
                    event_url = urljoin(url, href)
                    break
            container = container.parent

        start = dt.isoformat()

        events.append({
            "id": stable_id("Comédie Triomphe", title, start),
            "title": title,
            "start": start,
            "venue": "Comédie Triomphe",
            "city": "Saint-Étienne",
            "category": infer_category(title),
            "description": "",
            "url": event_url,
            "source": "Comédie Triomphe",
        })

    return events


def scrape_comedie_triomphe() -> list[dict]:
    events = []
    seen = set()

    # La page FNAC annonce actuellement 4 pages. On en tente jusqu'à 10
    # et on s'arrête dès qu'une page après la première ne renvoie rien.
    for page in range(1, 11):
        try:
            found = extract_events_from_page(page)
        except requests.RequestException as exc:
            print(f"Comédie Triomphe : erreur page {page}: {exc}")
            break

        if not found:
            if page == 1:
                print("Comédie Triomphe : aucune séance trouvée sur la page FNAC")
            break

        new_count = 0
        for event in found:
            if event["id"] in seen:
                continue
            seen.add(event["id"])
            events.append(event)
            new_count += 1

        print(
            f"Comédie Triomphe FNAC page {page}: "
            f"{new_count} nouvelle(s) séance(s)"
        )

    events.sort(key=lambda e: (e["start"], e["title"].lower()))

    print(f"Comédie Triomphe : {len(events)} représentation(s)")

    # Contrôle explicite de l'anomalie qui nous a servi à corriger le scraper.
    fortune = [
        e for e in events
        if "fortune de l" in e["title"].lower()
    ]
    print(
        "Comédie Triomphe : LA FORTUNE DE L'ÉPOQUE -> "
        f"{len(fortune)} séance(s)"
    )

    return events


if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
