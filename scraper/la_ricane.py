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
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
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
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})\s*[·\-–—]\s*"
    r"(\d{1,2})h(\d{2})",
    re.IGNORECASE,
)

# Les catégories présentes sur le site permettent de repérer
# la fin du titre.
CATEGORY_MARKERS = [
    "Humour",
    "Stand Up",
    "Comédie",
    "Comedie",
    "Concert",
    "Interactif",
    "Murder Party",
    "Impro",
    "Contes",
    "Jeune Public",
    "A partir de",
    "A Partir de",
    "Enfants >",
    "Tout public",
    "Les Jeudis",
]


def infer_category(text: str) -> str:
    value = text.lower()

    if any(
        word in value
        for word in (
            "jeune public",
            "a partir de 1",
            "a partir de 2",
            "a partir de 3",
            "a partir de 4",
            "à partir de 1",
            "à partir de 2",
            "à partir de 3",
            "à partir de 4",
            "contes",
        )
    ):
        return "Jeune public"

    if any(
        word in value
        for word in (
            "humour",
            "stand up",
            "stand-up",
            "comedy club",
        )
    ):
        return "Humour"

    if any(
        word in value
        for word in (
            "concert",
            "musique",
            "jazz",
            "rock",
        )
    ):
        return "Concerts"

    if any(
        word in value
        for word in (
            "murder party",
            "comédie",
            "comedie",
            "théâtre",
            "theatre",
            "impro",
        )
    ):
        return "Théâtre"

    return "Spectacle"


def clean_title(block: str) -> str:
    """
    Reçoit par exemple :

    DERRIERE LA PORTE
    Comedie · Spectacle Amateur · Tout public 12,00 €

    et retourne :

    DERRIERE LA PORTE
    """

    positions = []

    lower_block = block.lower()

    for marker in CATEGORY_MARKERS:
        pos = lower_block.find(
            marker.lower()
        )

        if pos >= 0:
            positions.append(pos)

    if positions:
        block = block[:min(positions)]

    # Supprime un éventuel prix restant.
    block = re.sub(
        r"\s+\d+(?:[,.]\d+)?\s*€.*$",
        "",
        block,
        flags=re.IGNORECASE,
    )

    return clean(block)


def find_event_url(
    soup: BeautifulSoup,
    title: str,
    page_url: str,
) -> str:
    """
    Essaie de retrouver le lien correspondant au titre.
    Si aucun lien propre n'est trouvé, renvoie la page
    de programmation.
    """

    wanted = clean(title).lower()

    for link in soup.find_all(
        "a",
        href=True,
    ):
        text = clean(
            link.get_text(" ")
        )

        if not text:
            continue

        normalized = text.lower()

        if (
            normalized == wanted
            or wanted in normalized
        ):
            href = link.get(
                "href",
                "",
            )

            if href:
                return urljoin(
                    page_url,
                    href,
                )

    return page_url


def scrape_page(
    url: str,
) -> tuple[list[dict], str | None]:

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # Texte de la zone principale.
    #
    # On conserve des espaces entre les éléments HTML :
    # la programmation devient alors une suite du type :
    #
    # 15 octobre 2026 · 21h00
    # VERT DE RIRE COMEDY CLUB !
    # Humour · ...
    #
    text = clean(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    matches = list(
        DATE_RE.finditer(text)
    )

    events = []

    for index, match in enumerate(
        matches
    ):
        day = int(
            match.group(1)
        )

        month_name = (
            match.group(2)
            .lower()
        )

        month = MONTHS[
            month_name
        ]

        year = int(
            match.group(3)
        )

        hour = int(
            match.group(4)
        )

        minute = int(
            match.group(5)
        )

        # Tout ce qui se trouve entre cette date
        # et la date suivante appartient à cet événement.
        start_pos = match.end()

        if index + 1 < len(matches):
            end_pos = (
                matches[
                    index + 1
                ].start()
            )
        else:
            end_pos = len(text)

        block = clean(
            text[
                start_pos:end_pos
            ]
        )

        # Stoppe avant la pagination / footer.
        for stopper in (
            "« Précédent",
            "Suivant »",
            "La Ricane La Scène",
            "Spectacles Tous Public",
        ):
            pos = block.find(
                stopper
            )

            if pos >= 0:
                block = block[:pos]

        title = clean_title(
            block
        )

        if not title:
            continue

        # Sécurité : évite qu'un bloc de navigation
        # soit interprété comme un spectacle.
        if title.lower() in {
            "programmation",
            "suivant",
            "précédent",
        }:
            continue

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

        event_url = find_event_url(
            soup,
            title,
            url,
        )

        event = {
            "id": stable_id(
                "La Ricane",
                title,
                start,
            ),
            "title": title,
            "start": start,
            "venue": "La Ricane",
            "city": "Saint-Étienne",
            "category": infer_category(
                block
            ),
            "description": "",
            "url": event_url,
            "source": "La Ricane",
        }

        events.append(event)

    # --------------------------------------------------
    # PAGE SUIVANTE
    # --------------------------------------------------

    current_match = re.search(
        r"[?&]evpage=(\d+)",
        url,
    )

    current_page = (
        int(
            current_match.group(1)
        )
        if current_match
        else 1
    )

    next_url = None

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = link.get(
            "href",
            "",
        )

        candidate = urljoin(
            url,
            href,
        )

        page_match = re.search(
            r"[?&]evpage=(\d+)",
            candidate,
        )

        if not page_match:
            continue

        page_number = int(
            page_match.group(1)
        )

        if page_number == (
            current_page + 1
        ):
            next_url = candidate
            break

    return events, next_url


def scrape_la_ricane() -> list[dict]:
    all_events = []
    seen_ids = set()

    current_url = URL

    for page_number in range(
        1,
        11,
    ):
        events, next_url = (
            scrape_page(
                current_url
            )
        )

        new_count = 0

        for event in events:
            if (
                event["id"]
                in seen_ids
            ):
                continue

            seen_ids.add(
                event["id"]
            )

            all_events.append(
                event
            )

            new_count += 1

        print(
            "La Ricane "
            f"page {page_number} : "
            f"{new_count} "
            "nouvelle(s) "
            "représentation(s)"
        )

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
        "La Ricane : "
        f"{len(all_events)} "
        "représentation(s)"
    )

    # Contrôles utiles dans GitHub Actions.
    checks = [
        "DERRIERE LA PORTE",
        "LA FIV DU SAMEDI SOIR",
        "LA PETITE FILLE QUI VOULAIT SAUVER L’AMOUR",
    ]

    for wanted in checks:
        found = [
            event
            for event in all_events
            if event["title"].upper()
            == wanted.upper()
        ]

        print(
            "La Ricane contrôle : "
            f"{wanted} -> "
            f"{len(found)} séance(s)"
        )

        for event in found:
            print(
                "  ",
                event["start"],
            )

    return all_events


if __name__ == "__main__":
    for event in scrape_la_ricane():
        print(event)
