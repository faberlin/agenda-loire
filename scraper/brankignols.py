from __future__ import annotations

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = (
    "https://brankignols.wixsite.com/"
    "theatredepoche/spectacles-%C3%A0-venir"
)

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
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"
    r"(\d{1,2})(?:er)?\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})"
    r"\s*[,–—-]\s*"
    r"(\d{1,2})h(?:(\d{2}))?",
    re.IGNORECASE,
)


GENERIC = {
    "theatre",
    "théâtre",
    "concert",
    "musique",
    "spectacle",
    "humour",
    "danse",
    "trio",
}


def normalized(value: str) -> str:
    return (
        value.lower()
        .replace("’", "'")
        .strip()
    )


def infer_category(context: str) -> str:
    value = context.lower()

    if any(word in value for word in (
        "théâtre",
        "theatre",
        "comédie",
        "comedie",
    )):
        return "Théâtre"

    if any(word in value for word in (
        "humour",
        "stand-up",
    )):
        return "Humour"

    if "danse" in value:
        return "Opéra-Danse"

    if any(word in value for word in (
        "jazz",
        "concert",
        "musique",
        "chante",
        "guitare",
        "irlande",
        "swing",
    )):
        return "Concerts"

    return "Théâtre"


def choose_title(previous_lines: list[str]) -> str | None:
    candidates = []

    for line in previous_lines:
        value = clean(line)

        if not value:
            continue

        lower = normalized(value)

        if lower in GENERIC:
            continue

        if lower.startswith("cie "):
            continue

        if lower.startswith("tarif"):
            continue

        if lower.startswith("réservation"):
            continue

        if lower.startswith("reservations"):
            continue

        candidates.append(value)

    if not candidates:
        return None

    # Le site place généralement le titre avant le sous-titre :
    # "ANAÏS" / "Initiation à la danse irlandaise" / date.
    return candidates[0]


def scrape_brankignols() -> list[dict]:
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    lines = [
        clean(value)
        for value in soup.stripped_strings
        if clean(value)
    ]

    events = []
    seen = set()

    for index, line in enumerate(lines):
        match = DATE_RE.fullmatch(line)

        if not match:
            continue

        # On regarde les quelques lignes qui précèdent la date :
        # le titre et éventuellement un sous-titre/catégorie.
        previous = lines[
            max(0, index - 4):
            index
        ]

        title = choose_title(previous)

        if not title:
            print(
                f"Brankignols: titre introuvable avant '{line}'"
            )
            continue

        dt = datetime(
            int(match.group(3)),
            MONTHS[match.group(2).lower()],
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5) or 0),
            tzinfo=PARIS,
        )

        start = dt.isoformat()

        # Contexte utilisé uniquement pour déterminer la catégorie.
        context = " ".join(
            lines[
                max(0, index - 4):
                min(len(lines), index + 8)
            ]
        )

        event = {
            "id": stable_id(
                "Théâtre de Poche des Brankignols",
                title,
                start,
            ),
            "title": title,
            "start": start,
            "venue": "Théâtre de Poche des Brankignols",
            "city": "Saint-Étienne",
            "category": infer_category(context),
            "description": "",
            "url": URL,
            "source": "Théâtre de Poche des Brankignols",
        }

        if event["id"] in seen:
            continue

        seen.add(event["id"])
        events.append(event)

    events.sort(
        key=lambda event: event["start"]
    )

    print(
        f"Théâtre de Poche des Brankignols : "
        f"{len(events)} évènement(s)"
    )

    return events


if __name__ == "__main__":
    for event in scrape_brankignols():
        print(event)
