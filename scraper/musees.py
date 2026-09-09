from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AgendaLoire/1.0; "
        "+https://github.com/faberlin/agenda-loire)"
    )
}

TIMEOUT = 30

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "expositions.json"

MAMC_URL = "https://mamc.saint-etienne-metropole.fr/fr/expositions"
MAI_URL = "https://mai.saint-etienne.fr/je-minteresse-a/expositions"
COURIOT_URL = "https://musee-mine.saint-etienne.fr/agenda"


MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    return "".join(
        char for char in value
        if unicodedata.category(char) != "Mn"
    )


def stable_id(source: str, title: str, venue: str) -> str:
    raw = f"{source}|{title}|{venue}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def french_date(day: str, month: str, year: str) -> date | None:
    try:
        return date(
            int(year),
            MONTHS[normalize(month)],
            int(day),
        )
    except (KeyError, ValueError):
        return None


DATE_RANGE_RE = re.compile(
    r"(?:du\s+)?"
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})"
    r"\s*(?:au|—|-)\s*"
    r"(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)


def parse_date_range(text: str) -> tuple[date | None, date | None]:
    text = clean(text)
    match = DATE_RANGE_RE.search(text)

    if not match:
        return None, None

    start = french_date(
        match.group(1),
        match.group(2),
        match.group(3),
    )

    end = french_date(
        match.group(4),
        match.group(5),
        match.group(6),
    )

    return start, end


def status_from_dates(
    start: date | None,
    end: date | None,
    fallback: str = "current",
) -> str:
    today = date.today()

    if start and start > today:
        return "upcoming"

    if end and end < today:
        return "past"

    return fallback


def make_event(
    *,
    source: str,
    title: str,
    venue: str,
    url: str,
    start: date | None = None,
    end: date | None = None,
    status: str = "current",
) -> dict:
    return {
        "id": stable_id(source, title, venue),
        "type": "Musée",
        "source": source,
        "title": clean(title),
        "venue": venue,
        "city": "Saint-Étienne",
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "status": status,
        "url": url,
    }


# ============================================================
# MAMC+
# ============================================================

def scrape_mamc() -> list[dict]:
    soup = get_soup(MAMC_URL)
    links: dict[str, str] = {}

    for link in soup.select('a[href*="/fr/expositions/"]'):
        href = link.get("href")
        title = clean(link.get_text(" "))

        if not href or not title:
            continue

        url = urljoin(MAMC_URL, href)

        if url.rstrip("/") == MAMC_URL.rstrip("/"):
            continue

        links[url] = title

    events = []

    for url, list_title in links.items():
        try:
            detail = get_soup(url)
        except requests.RequestException as exc:
            print(f"MAMC+: erreur détail {url}: {exc}")
            continue

        h1 = detail.find("h1")
        title = clean(h1.get_text(" ")) if h1 else list_title

        # Le MAMC+ utilise souvent un sous-titre immédiatement après le H1.
        subtitle = None
        if h1:
            h2 = h1.find_next("h2")
            if h2:
                candidate = clean(h2.get_text(" "))
                if candidate and normalize(candidate) not in {
                    "pour approfondir",
                    "autour de l'exposition",
                    "commissariat",
                }:
                    subtitle = candidate

        if subtitle and normalize(subtitle) not in normalize(title):
            title = f"{title} — {subtitle}"

        page_text = clean(detail.get_text(" "))
        start, end = parse_date_range(page_text)

        if not start and not end:
            print(f"MAMC+: dates introuvables pour {title}")
            continue

        status = status_from_dates(start, end)

        if status == "past":
            continue

        events.append(
            make_event(
                source="MAMC+",
                title=title,
                venue="MAMC+",
                url=url,
                start=start,
                end=end,
                status=status,
            )
        )

    print(f"MAMC+ : {len(events)} exposition(s)")
    return events


# ============================================================
# MUSÉE D'ART ET D'INDUSTRIE
# ============================================================

def scrape_mai() -> list[dict]:
    soup = get_soup(MAI_URL)
    events = []
    seen = set()

    # Le menu du site expose explicitement les pages
    # "Exposition en cours". On ne prend pas l'agenda général.
    for link in soup.select('a[href*="/expositions-evenements/"]'):
        href = link.get("href")
        title = clean(link.get_text(" "))

        if not href or not title:
            continue

        href_norm = normalize(href)

        if (
            "/exposition-en-cours/" not in href_norm
            and "/expositions/" not in href_norm
        ):
            continue

        url = urljoin(MAI_URL, href)

        if url in seen:
            continue

        seen.add(url)

        try:
            detail = get_soup(url)
        except requests.RequestException as exc:
            print(f"MAI: erreur détail {url}: {exc}")
            continue

        h1 = detail.find("h1")
        detail_title = clean(h1.get_text(" ")) if h1 else title

        # Les pages MAI ne donnent pas toujours une plage de dates.
        # Si elle existe, on la récupère ; sinon l'état "en cours"
        # fourni par le site fait foi.
        page_text = clean(detail.get_text(" "))
        start, end = parse_date_range(page_text)
        status = status_from_dates(start, end, "current")

        if status == "past":
            continue

        events.append(
            make_event(
                source="Musée d'Art et d'Industrie",
                title=detail_title,
                venue="Musée d'Art et d'Industrie",
                url=url,
                start=start,
                end=end,
                status=status,
            )
        )

    # Déduplication par titre : certains liens apparaissent
    # plusieurs fois dans le menu et le contenu.
    unique = {}
    for event in events:
        unique[normalize(event["title"])] = event

    events = list(unique.values())

    print(
        "Musée d'Art et d'Industrie : "
        f"{len(events)} exposition(s)"
    )

    return events


# ============================================================
# COURIOT - MUSÉE DE LA MINE
# ============================================================

def scrape_couriot() -> list[dict]:
    soup = get_soup(COURIOT_URL)
    events = []
    seen = set()

    # On cherche uniquement les cartes de l'agenda qui contiennent
    # explicitement la catégorie "Exposition temporaire".
    for text_node in soup.find_all(
        string=re.compile(r"Exposition temporaire", re.I)
    ):
        node = text_node.parent

        for _ in range(6):
            if node is None:
                break

            card_text = clean(node.get_text(" "))
            links = node.find_all("a", href=True)

            if (
                "exposition temporaire" in normalize(card_text)
                and links
            ):
                link = links[-1]
                url = urljoin(COURIOT_URL, link["href"])

                if url in seen:
                    break

                seen.add(url)

                try:
                    detail = get_soup(url)
                except requests.RequestException as exc:
                    print(f"Couriot: erreur détail {url}: {exc}")
                    break

                h1 = detail.find("h1")
                h2 = detail.find("h2")

                title = clean(
                    h1.get_text(" ")
                    if h1
                    else (
                        h2.get_text(" ")
                        if h2
                        else link.get_text(" ")
                    )
                )

                page_text = clean(detail.get_text(" "))
                start, end = parse_date_range(page_text)
                status = status_from_dates(start, end)

                if title and status != "past":
                    events.append(
                        make_event(
                            source="Couriot - Musée de la Mine",
                            title=title,
                            venue="Couriot - Musée de la Mine",
                            url=url,
                            start=start,
                            end=end,
                            status=status,
                        )
                    )

                break

            node = node.parent

    print(f"Couriot - Musée de la Mine : {len(events)} exposition(s)")
    return events


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    events = []

    scrapers = [
        ("MAMC+", scrape_mamc),
        ("Musée d'Art et d'Industrie", scrape_mai),
        ("Couriot - Musée de la Mine", scrape_couriot),
    ]

    for name, scraper in scrapers:
        try:
            events.extend(scraper())
        except Exception as exc:
            # Un musée en panne ne bloque pas les autres.
            print(f"{name}: ERREUR: {exc}")

    unique = {}

    for event in events:
        key = (
            normalize(event["source"]),
            normalize(event["title"]),
        )

        unique[key] = event

    events = list(unique.values())

    events.sort(
        key=lambda event: (
            event["status"] != "current",
            event["start"] or "9999-12-31",
            normalize(event["venue"]),
            normalize(event["title"]),
        )
    )

    OUTPUT.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        f"TOTAL : {len(events)} exposition(s) "
        f"écrite(s) dans {OUTPUT.name}"
    )


if __name__ == "__main__":
    main()
