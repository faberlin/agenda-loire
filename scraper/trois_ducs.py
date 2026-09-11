from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


URL = "https://www.lestroisducs.fr/programmation"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

WEEKDAYS = (
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
)

# Le site Webflow expose actuellement les cartes sous une forme du type :
# "Wednesday, November 18, 2026 21h ALEX FREDO"
CARD_RE = re.compile(
    rf"(?:{WEEKDAYS}),?\s+"
    r"(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+"
    r"(\d{1,2}),\s+(\d{4})\s+"
    r"(\d{1,2})[hH](\d{2})?\s+"
    r"(.+)$",
    re.IGNORECASE,
)

PREFIX_RE = re.compile(
    r"^(?:(?:NOUVELLE SAISON\s*!?|NOUVEAU\s*!?|COMPLET|HORS LES MURS)\s*)+",
    re.IGNORECASE,
)


def infer_category(title: str) -> str:
    value = title.lower()

    if any(word in value for word in (
        "concert",
        "musique",
        "chanson",
        "jazz",
    )):
        return "Concerts"

    if any(word in value for word in (
        "théâtre",
        "theatre",
        "comédie",
        "comedie",
    )):
        return "Théâtre"

    # Les Trois Ducs est principalement un café-théâtre d'humour.
    return "Humour"


def normalize_card_text(text: str) -> str:
    text = clean(text)

    # Sur certaines cartes, les badges sont collés à la date :
    # "NOUVELLE SAISON !Thursday, October..."
    for marker in (
        "NOUVELLE SAISON !",
        "NOUVEAU !",
        "COMPLET ",
        "HORS LES MURS ",
    ):
        text = text.replace(marker, f"{marker} ")

    return clean(text)


def parse_card(text: str) -> tuple[datetime, str] | None:
    text = normalize_card_text(text)

    # On cherche la date n'importe où dans la carte pour tolérer les badges.
    match = CARD_RE.search(text)
    if not match:
        return None

    month = MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    year = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5) or 0)

    title = clean(match.group(6))
    title = PREFIX_RE.sub("", title).strip()

    if not title:
        return None

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
        return None

    return dt, title


def scrape_trois_ducs() -> list[dict]:
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    # Chaque spectacle de la page programmation est cliquable.
    # On travaille volontairement à partir du texte de chaque lien :
    # cela évite de dépendre des classes Webflow qui peuvent changer.
    for link in soup.find_all("a", href=True):
        text = clean(link.get_text(" "))

        if not text:
            continue

        parsed = parse_card(text)
        if parsed is None:
            continue

        dt, title = parsed
        start = dt.isoformat()

        event_url = urljoin(URL, link.get("href"))

        # La carte cadeau apparaît aussi dans la programmation mais
        # n'est pas un spectacle.
        if "carte cadeau" in title.lower():
            continue

        # Gestion du spectacle "hors les murs" connu sur la page.
        lower_text = text.lower()
        if "hors les murs" in lower_text:
            venue = "La Comète"
        else:
            venue = "Les 3 Ducs"

        event_id = stable_id(
            "Les 3 Ducs",
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
            "venue": venue,
            "city": "Saint-Étienne",
            "category": infer_category(title),
            "description": "",
            "url": event_url,
            "source": "Les 3 Ducs",
        })

    events.sort(key=lambda event: event["start"])

    print(
        f"Les 3 Ducs : {len(events)} représentation(s)"
    )

    # Contrôle explicite utile dans les logs GitHub Actions.
    if any(
        event["title"].upper() == "ALEX FREDO"
        for event in events
    ):
        print("Les 3 Ducs : ALEX FREDO trouvé")
    else:
        print("ATTENTION Les 3 Ducs : ALEX FREDO absent")

    return events


if __name__ == "__main__":
    for event in scrape_trois_ducs():
        print(event)
