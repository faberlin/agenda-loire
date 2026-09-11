from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://saint-chamond.fr/locations/salle-aristide-briand/"

HEADERS = {
    "User-Agent": "AgendaLoire/1.0 (personal cultural events aggregator)"
}


DATE_RE = re.compile(
    r"(\d{2})/(\d{2})/(\d{4})"
    r"\s*-\s*"
    r"(\d{1,2})\s*h\s*(\d{2})",
    re.IGNORECASE,
)


def infer_category(title: str) -> str:
    value = title.lower()

    if "humour" in value:
        return "Humour"

    if "danse" in value:
        return "Danse"

    if any(word in value for word in (
        "concert",
        "jazz",
        "musique",
        "polyphonie",
        "percussion",
        "opérette",
        "operette",
    )):
        return "Musique"

    if any(word in value for word in (
        "théâtre",
        "theatre",
        "clown",
    )):
        return "Théâtre"

    if "jeune public" in value:
        return "Jeune public"

    return "Spectacle"


def clean_title(title: str) -> str:
    title = clean(title)

    # La ville préfixe souvent les titres par le genre.
    # On garde le texte complet, car il est informatif et stable.
    return title


def scrape_aristide_briand() -> list[dict]:
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    heading = None

    for tag in soup.find_all(["h2", "h3", "h4"]):
        if "évènement à venir" in clean(tag.get_text(" ")).lower() or \
           "événement à venir" in clean(tag.get_text(" ")).lower():
            heading = tag
            break

    if not heading:
        raise RuntimeError(
            "Salle Aristide Briand: section 'Évènement à venir' introuvable"
        )

    events = []
    seen = set()

    # Les événements sont dans la liste qui suit immédiatement le titre.
    container = heading.find_next(["ul", "ol"])

    if not container:
        raise RuntimeError(
            "Salle Aristide Briand: liste des événements introuvable"
        )

    for item in container.find_all("li", recursive=False):
        text = clean(item.get_text(" "))
        match = DATE_RE.search(text)

        if not match:
            continue

        link = item.find("a", href=True)

        if link:
            title = clean_title(link.get_text(" "))
            event_url = urljoin(URL, link["href"])
        else:
            title = clean_title(
                text[:match.start()].rstrip(" -")
            )
            event_url = URL

        if not title:
            continue

        dt = datetime(
            int(match.group(3)),
            int(match.group(2)),
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5)),
            tzinfo=PARIS,
        )

        start = dt.isoformat()

        event = {
            "id": stable_id(
                "Salle Aristide Briand",
                title,
                start,
            ),
            "title": title,
            "start": start,
            "venue": "Salle Aristide Briand",
            "city": "Saint-Chamond",
            "category": infer_category(title),
            "description": "",
            "url": event_url,
            "source": "Salle Aristide Briand",
        }

        if event["id"] in seen:
            continue

        seen.add(event["id"])
        events.append(event)

    events.sort(
        key=lambda event: event["start"]
    )

    print(
        f"Salle Aristide Briand : "
        f"{len(events)} évènement(s)"
    )

    return events


if __name__ == "__main__":
    for event in scrape_aristide_briand():
        print(event)
