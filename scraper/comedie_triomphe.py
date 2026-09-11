from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://www.comedietriomphe.fr/cas-categorie/tout-public/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

DATE_RE = re.compile(
    r"\b(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})\b"
)


def infer_category(title: str, text: str) -> str:
    value = f"{title} {text}".lower()

    if any(word in value for word in (
        "concert",
        "musique",
        "chanson",
        "jazz",
    )):
        return "Concerts"

    if any(word in value for word in (
        "humour",
        "stand-up",
        "one man",
        "one-man",
        "impro",
    )):
        return "Humour"

    return "Théâtre"


def block_until_next_h2(h2) -> str:
    """
    Récupère STRICTEMENT le contenu appartenant à un spectacle,
    entre son <h2> et le <h2> suivant.

    C'est important pour éviter d'attribuer à un spectacle les dates
    des spectacles voisins.
    """
    parts = []
    node = h2.next_sibling

    while node:
        if getattr(node, "name", None) == "h2":
            break

        if hasattr(node, "get_text"):
            text = clean(node.get_text(" "))
        else:
            text = clean(str(node))

        if text:
            parts.append(text)

        node = node.next_sibling

    return clean(" ".join(parts))


def extract_sessions(text: str) -> list[datetime]:
    """
    Extrait toutes les dates/horaires présentes dans le bloc du spectacle.
    Les pages de billetterie répètent souvent la même séance pour plusieurs
    tarifs : on déduplique donc par date+heure.
    """
    sessions = {}

    for match in DATE_RE.finditer(text):
        day = int(match.group(1))
        month = int(match.group(2))
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

        sessions[dt.isoformat()] = dt

    return sorted(sessions.values())


def scrape_comedie_triomphe() -> list[dict]:
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    for h2 in soup.find_all("h2"):
        title = clean(h2.get_text(" "))

        if not title:
            continue

        link = h2.find("a", href=True)
        event_url = (
            urljoin(URL, link["href"])
            if link
            else URL
        )

        block_text = block_until_next_h2(h2)

        if not block_text:
            continue

        sessions = extract_sessions(block_text)

        if not sessions:
            print(
                f"Comédie Triomphe : aucune séance trouvée pour {title}"
            )
            continue

        category = infer_category(
            title,
            block_text,
        )

        for dt in sessions:
            start = dt.isoformat()

            event_id = stable_id(
                "Comédie Triomphe",
                title,
                start,
            )

            if event_id in seen:
                continue

            seen.add(event_id)

            events.append({
                "id": event_id,
                "title": title,
                "start": start,
                "venue": "Comédie Triomphe",
                "city": "Saint-Étienne",
                "category": category,
                "description": "",
                "url": event_url,
                "source": "Comédie Triomphe",
            })

    events.sort(
        key=lambda event: (
            event["start"],
            event["title"].lower(),
        )
    )

    print(
        f"Comédie Triomphe : {len(events)} représentation(s)"
    )

    # Contrôle ciblé dans les logs GitHub Actions.
    fortune = [
        event
        for event in events
        if "fortune de l" in event["title"].lower()
    ]

    if fortune:
        print(
            "Comédie Triomphe : LA FORTUNE DE L'ÉPOQUE -> "
            f"{len(fortune)} séance(s) : "
            + ", ".join(
                event["start"]
                for event in fortune
            )
        )

    return events


if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
