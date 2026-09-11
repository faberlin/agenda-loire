from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://laricane.com/programmation/"

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
    r"\b(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})\s*[·\-–—]\s*"
    r"(\d{1,2})h(\d{2})\b",
    re.IGNORECASE,
)


def infer_category(text: str) -> str:
    value = text.lower()

    if any(word in value for word in (
        "humour",
        "stand up",
        "stand-up",
        "comedy club",
    )):
        return "Humour"

    if any(word in value for word in (
        "jeune public",
        "a partir de",
        "à partir de",
        "contes",
        "enfant",
    )):
        return "Jeune public"

    if any(word in value for word in (
        "concert",
        "musique",
        "jazz",
        "rock",
    )):
        return "Musique"

    if any(word in value for word in (
        "murder party",
        "comédie",
        "comedie",
        "théâtre",
        "theatre",
        "impro",
    )):
        return "Théâtre"

    return "Spectacle"


def event_title_from_link(link) -> str:
    text = clean(link.get_text(" "))
    if text:
        return text

    return ""


def scrape_page(url: str) -> tuple[list[dict], str | None]:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    # La page "Programmation" expose les vraies heures locales en texte,
    # ex. "15 octobre 2026 · 21h00".
    # On évite volontairement les attributs datetime du plugin calendrier,
    # qui peuvent contenir seulement un offset de fuseau.
    for link in soup.find_all("a", href=True):
        title = event_title_from_link(link)
        if not title:
            continue

        # Remonte dans quelques parents pour trouver la date/heure de la carte.
        node = link
        context = ""
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            context = clean(node.get_text(" "))
            if DATE_RE.search(context):
                break

        match = DATE_RE.search(context)
        if not match:
            continue

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
        event_url = urljoin(url, link["href"])

        # Ignore la navigation, les boutons et les liens génériques.
        lower_title = title.lower()
        if lower_title in {
            "suivant »",
            "« précédent",
            "1",
            "2",
            "3",
            "obtenir billets",
            "réserver",
            "billets",
        }:
            continue

        event = {
            "id": stable_id("La Ricane", title, start),
            "title": title,
            "start": start,
            "venue": "La Ricane",
            "city": "Saint-Étienne",
            "category": infer_category(context),
            "description": "",
            "url": event_url,
            "source": "La Ricane",
        }

        events.append(event)

    # Page suivante de la pagination custom de la programmation.
    next_url = None
    for link in soup.find_all("a", href=True):
        text = clean(link.get_text(" "))
        href = link.get("href", "")
        if "suivant" in text.lower() or "evpage=" in href:
            candidate = urljoin(url, href)
            if candidate != url:
                # On prend le premier lien vers une page supérieure.
                m = re.search(r"[?&]evpage=(\d+)", candidate)
                if m:
                    current = re.search(r"[?&]evpage=(\d+)", url)
                    current_page = int(current.group(1)) if current else 1
                    if int(m.group(1)) > current_page:
                        next_url = candidate
                        break

    return events, next_url


def scrape_la_ricane() -> list[dict]:
    all_events = []
    seen_ids = set()

    current_url = URL

    for _ in range(10):
        events, next_url = scrape_page(current_url)

        for event in events:
            if event["id"] in seen_ids:
                continue

            seen_ids.add(event["id"])
            all_events.append(event)

        if not next_url:
            break

        current_url = next_url

    all_events.sort(
        key=lambda event: (
            event["start"],
            event["title"].lower(),
        )
    )

    print(
        f"La Ricane : {len(all_events)} représentation(s)"
    )

    return all_events


if __name__ == "__main__":
    for event in scrape_la_ricane():
        print(event)
