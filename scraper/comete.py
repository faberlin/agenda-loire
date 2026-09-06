from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://lacomete.saint-etienne.fr/"
AGENDA = urljoin(BASE, "lagenda/")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _discover_event_rest_base() -> str | None:
    """
    La page agenda est chargée dynamiquement.
    On interroge l'API WordPress pour découvrir le type de contenu "événement".
    """
    url = urljoin(BASE, "wp-json/wp/v2/types")
    response = requests.get(url, headers=HEADERS, timeout=30)
    if not response.ok:
        return None

    try:
        types = response.json()
    except Exception:
        return None

    for _slug, info in types.items():
        label = clean(
            f'{info.get("name", "")} {info.get("slug", "")} '
            f'{info.get("rest_base", "")}'
        ).lower()

        if "even" in label or "agenda" in label:
            return info.get("rest_base") or info.get("slug")

    return None


def _event_links_from_api() -> list[str]:
    rest_base = _discover_event_rest_base()
    if not rest_base:
        return []

    links = []
    seen = set()

    for page in range(1, 10):
        url = urljoin(
            BASE,
            f"wp-json/wp/v2/{rest_base}?per_page=100&page={page}"
        )
        response = requests.get(url, headers=HEADERS, timeout=30)

        if response.status_code == 400:
            break
        response.raise_for_status()

        try:
            rows = response.json()
        except Exception:
            break

        if not rows:
            break

        for row in rows:
            link = row.get("link")
            if link and link not in seen:
                seen.add(link)
                links.append(link)

        if len(rows) < 100:
            break

    return links


def _event_links_from_sitemap() -> list[str]:
    """
    Fallback si le type WordPress n'est pas exposé.
    """
    candidates = [
        urljoin(BASE, "wp-sitemap.xml"),
        urljoin(BASE, "sitemap_index.xml"),
    ]

    links = []
    seen = set()

    for sitemap_url in candidates:
        try:
            response = requests.get(
                sitemap_url, headers=HEADERS, timeout=20
            )
            if not response.ok:
                continue
        except Exception:
            continue

        soup = BeautifulSoup(response.text, "xml")

        child_maps = [
            clean(loc.get_text())
            for loc in soup.find_all("loc")
            if "sitemap" in clean(loc.get_text()).lower()
        ]

        for child in child_maps[:30]:
            if "even" not in child.lower() and "event" not in child.lower():
                continue

            try:
                child_response = requests.get(
                    child, headers=HEADERS, timeout=20
                )
                if not child_response.ok:
                    continue
            except Exception:
                continue

            child_soup = BeautifulSoup(child_response.text, "xml")
            for loc in child_soup.find_all("loc"):
                href = clean(loc.get_text())
                if "/evenements/" in href and href not in seen:
                    seen.add(href)
                    links.append(href)

        if links:
            break

    return links


def _category(page_text: str) -> str:
    match = re.search(
        r"Discipline\s*:\s*(.+?)\s+Activité\s*:",
        page_text,
        re.IGNORECASE,
    )

    discipline = clean(match.group(1)).lower() if match else ""

    mapping = {
        "musique": "Musique",
        "humour": "Humour",
        "théatre": "Théâtre",
        "théâtre": "Théâtre",
        "danse": "Danse",
        "cirque": "Spectacle",
        "arts plastiques": "Exposition",
    }

    return mapping.get(discipline, "Spectacle")


def _parse_event(href: str):
    response = requests.get(href, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    h1 = soup.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    if not title:
        return None

    text = clean(soup.get_text(" "))

    date_match = re.search(
        r"\b(\d{2})/(\d{2})/(20\d{2})\b",
        text
    )
    time_match = re.search(
        r"\b(\d{1,2}):(\d{2})\b",
        text
    )

    if not date_match or not time_match:
        return None

    dt = datetime(
        int(date_match.group(3)),
        int(date_match.group(2)),
        int(date_match.group(1)),
        int(time_match.group(1)),
        int(time_match.group(2)),
        tzinfo=PARIS,
    )

    venue_match = re.search(
        r"Salle\s*:\s*(.+?)\s+(?:Durée|Duree)\s*:",
        text,
        re.IGNORECASE,
    )

    venue = clean(venue_match.group(1)) if venue_match else "La Comète"
    if not venue or venue.lower() == "autre":
        venue = "La Comète"

    return {
        "id": stable_id("La Comète", title, dt.isoformat()),
        "title": title,
        "start": dt.isoformat(),
        "venue": venue,
        "city": "Saint-Étienne",
        "category": _category(text),
        "description": "",
        "url": href,
        "source": "La Comète",
    }


def scrape_comete() -> list[dict]:
    links = _event_links_from_api()

    if not links:
        links = _event_links_from_sitemap()

    print(f"La Comète: {len(links)} fiche(s) découverte(s)")

    now = datetime.now(PARIS)
    events = []

    # On limite volontairement à des fiches récentes/futures après parsing.
    for href in links:
        try:
            event = _parse_event(href)
        except Exception as exc:
            print(f"La Comète: erreur fiche {href}: {exc}")
            continue

        if not event:
            continue

        if datetime.fromisoformat(event["start"]) < now:
            continue

        events.append(event)

    # doublons éventuels API/sitemap
    unique = {}
    for event in events:
        unique[event["id"]] = event

    return sorted(unique.values(), key=lambda ev: ev["start"])
