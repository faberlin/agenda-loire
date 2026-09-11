from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://laricane.com/events/liste/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def infer_category(text: str) -> str:
    value = text.lower()

    if any(word in value for word in ("humour", "stand-up", "comedy club", "comédie")):
        return "Humour"

    if any(word in value for word in ("concert", "musique", "jazz", "rock")):
        return "Musique"

    if any(word in value for word in ("impro", "théâtre", "theatre", "murder party")):
        return "Théâtre"

    if any(word in value for word in ("jeune public", "enfant", "conte")):
        return "Jeune public"

    return "Spectacle"


def parse_datetime_from_node(node) -> datetime | None:
    # The Events Calendar expose généralement la date ISO dans <time datetime="...">
    time_tag = node.find("time")

    if time_tag:
        raw = time_tag.get("datetime")

        if raw:
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt.astimezone(PARIS)
            except ValueError:
                pass

    text = clean(node.get_text(" "))

    months = {
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

    match = re.search(
        r"(\d{1,2})\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
        r"septembre|octobre|novembre|décembre|decembre)"
        r",?\s+(\d{4})\s+@\s+(\d{1,2})h(\d{2})",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return datetime(
        int(match.group(3)),
        months[match.group(2).lower()],
        int(match.group(1)),
        int(match.group(4)),
        int(match.group(5)),
        tzinfo=PARIS,
    )


def scrape_page(url: str) -> tuple[list[dict], str | None]:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # The Events Calendar v6
    rows = soup.select(
        ".tribe-events-calendar-list__event-row, "
        "article.tribe-events-calendar-list__event"
    )

    # Fallback si le thème modifie légèrement les classes.
    if not rows:
        rows = soup.select("article")

    events = []

    for row in rows:
        link = row.select_one(
            "a.tribe-events-calendar-list__event-title-link, "
            "h2 a[href*='/event/'], "
            "h3 a[href*='/event/'], "
            "a[href*='/event/']"
        )

        if not link:
            continue

        href = link.get("href")
        title = clean(link.get_text(" "))

        if not href or not title:
            continue

        event_url = urljoin(url, href)

        if "/event/" not in event_url:
            continue

        dt = parse_datetime_from_node(row)

        if not dt:
            print(f"La Ricane: date introuvable pour {title}")
            continue

        text = clean(row.get_text(" "))
        start = dt.isoformat()

        events.append({
            "id": stable_id("La Ricane", title, start),
            "title": title,
            "start": start,
            "venue": "La Ricane",
            "city": "Saint-Étienne",
            "category": infer_category(text),
            "description": "",
            "url": event_url,
            "source": "La Ricane",
        })

    next_link = soup.select_one(
        "a.tribe-events-c-nav__next, "
        "a[rel='next']"
    )

    next_url = (
        urljoin(url, next_link.get("href"))
        if next_link and next_link.get("href")
        else None
    )

    return events, next_url


def scrape_la_ricane() -> list[dict]:
    events = []
    seen_ids = set()
    url = URL

    # Sécurité : on ne dépassera jamais 10 pages.
    for _ in range(10):
        page_events, next_url = scrape_page(url)

        for event in page_events:
            if event["id"] in seen_ids:
                continue

            seen_ids.add(event["id"])
            events.append(event)

        if not next_url or next_url == url:
            break

        url = next_url

    events.sort(
        key=lambda event: event["start"]
    )

    print(f"La Ricane : {len(events)} évènement(s)")
    return events


if __name__ == "__main__":
    for event in scrape_la_ricane():
        print(event)
