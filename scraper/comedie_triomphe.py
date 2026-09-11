from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from utils import PARIS, clean, stable_id


URL = "https://www.comedietriomphe.fr/cas-categorie/tout-public/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

# On ne prend QUE les vraies séances, qui sont présentées sous la forme :
# 20/03/2026 19:00 - 20:15
# Cela évite de prendre les dates de vente ("En vente", "Fin des ventes").
SESSION_RE = re.compile(
    r"\b(\d{2})/(\d{2})/(\d{4})\s+"
    r"(\d{1,2}):(\d{2})\s*-\s*"
    r"(\d{1,2}):(\d{2})\b"
)


def infer_category(title: str, text: str) -> str:
    value = f"{title} {text}".lower()

    if any(word in value for word in (
        "concert", "musique", "chanson", "jazz", "pop",
    )):
        return "Musique"

    if any(word in value for word in (
        "jeune public", "enfant", "marionnette", "conte",
    )):
        return "Jeune public"

    if any(word in value for word in (
        "stand up", "stand-up", "humour", "impro",
    )):
        return "Humour"

    return "Théâtre"


def section_text(h2: Tag) -> str:
    """
    Récupère le contenu d'un spectacle depuis son H2 jusqu'au H2 suivant.
    On parcourt les éléments suivants dans l'ordre du document : cela marche
    même lorsque les H2 ne sont pas des frères directs.
    """
    parts = []

    for node in h2.find_all_next():
        if node is h2:
            continue

        if node.name == "h2":
            break

        # On ne récupère que des blocs structurants pour limiter les répétitions.
        if node.name in {
            "li", "p", "h3", "h4", "h5", "div", "span"
        }:
            txt = clean(node.get_text(" "))
            if txt:
                parts.append(txt)

    return clean(" ".join(parts))


def extract_sessions(text: str) -> list[datetime]:
    sessions = {}

    for m in SESSION_RE.finditer(text):
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))

        try:
            dt = datetime(
                year, month, day, hour, minute, tzinfo=PARIS
            )
        except ValueError:
            continue

        sessions[dt.isoformat()] = dt

    return sorted(sessions.values())


def scrape_comedie_triomphe() -> list[dict]:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    for h2 in soup.find_all("h2"):
        title = clean(h2.get_text(" "))
        if not title:
            continue

        block = section_text(h2)
        sessions = extract_sessions(block)

        if not sessions:
            continue

        link = h2.find("a", href=True)
        event_url = (
            urljoin(URL, link["href"])
            if link
            else URL
        )

        category = infer_category(title, block)

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

    events.sort(key=lambda e: (e["start"], e["title"].lower()))

    print(f"Comédie Triomphe : {len(events)} représentation(s)")

    fortune = [
        e for e in events
        if "fortune de l" in e["title"].lower()
    ]
    if fortune:
        print(
            "Comédie Triomphe : LA FORTUNE DE L'ÉPOQUE -> "
            f"{len(fortune)} séance(s) : "
            + ", ".join(e["start"] for e in fortune)
        )

    return events


if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
