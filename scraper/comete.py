from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id


BASE = "https://lacomete.saint-etienne.fr/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SITEMAPS = [
    urljoin(BASE, "wp-sitemap.xml"),
    urljoin(BASE, "sitemap_index.xml"),
]


def _xml_locs(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    result = []
    for element in root.iter():
        if element.tag.lower().endswith("loc") and element.text:
            result.append(clean(element.text))
    return result


def _event_links_from_sitemaps() -> list[str]:
    event_links = []
    seen = set()

    for sitemap_url in SITEMAPS:
        try:
            response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if not response.ok:
                continue
        except Exception:
            continue

        locs = _xml_locs(response.text)
        if not locs:
            continue

        # Le premier XML peut être soit un index de sitemaps, soit déjà un sitemap de pages.
        child_sitemaps = [u for u in locs if "sitemap" in u.lower()]

        if child_sitemaps:
            for child in child_sitemaps:
                if not any(x in child.lower() for x in ("event", "even", "agenda")):
                    continue

                try:
                    child_response = requests.get(child, headers=HEADERS, timeout=30)
                    if not child_response.ok:
                        continue
                except Exception:
                    continue

                for href in _xml_locs(child_response.text):
                    if "/evenements/" in href and href not in seen:
                        seen.add(href)
                        event_links.append(href)
        else:
            for href in locs:
                if "/evenements/" in href and href.rstrip("/") != urljoin(BASE, "evenements").rstrip("/"):
                    if href not in seen:
                        seen.add(href)
                        event_links.append(href)

        if event_links:
            break

    return event_links


def _event_links_from_archive() -> list[str]:
    url = urljoin(BASE, "evenements/")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        if "/evenements/" not in href:
            continue
        if href.rstrip("/") == url.rstrip("/"):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(href)

    return links


def _category(text: str) -> str:
    match = re.search(
        r"Discipline\s*:\s*(.+?)\s+Activité\s*:",
        text,
        re.IGNORECASE,
    )
    discipline = clean(match.group(1)).lower() if match else ""

    mapping = {
        "musique": "Musique",
        "humour": "Humour",
        "théatre": "Théâtre",
        "théâtre": "Théâtre",
        "danse": "Danse",
        "arts plastiques": "Exposition",
        "cirque": "Spectacle",
    }
    return mapping.get(discipline, "Spectacle")


def _extract_sessions(text: str) -> list[datetime]:
    # La fiche peut contenir plusieurs phrases du type :
    # "Mercredi 24 juin 2026 de 20h à 21h20."
    months = {
        "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11,
        "décembre": 12, "decembre": 12,
    }

    pattern = re.compile(
        r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"
        r"(\d{1,2})\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
        r"septembre|octobre|novembre|décembre|decembre)\s+"
        r"(20\d{2})\s+de\s+"
        r"(\d{1,2})h(?:(\d{2}))?",
        re.IGNORECASE,
    )

    sessions = []
    seen = set()

    for m in pattern.finditer(text):
        dt = datetime(
            int(m.group(3)),
            months[m.group(2).lower()],
            int(m.group(1)),
            int(m.group(4)),
            int(m.group(5) or 0),
            tzinfo=PARIS,
        )
        if dt.isoformat() not in seen:
            seen.add(dt.isoformat())
            sessions.append(dt)

    # Fallback sur le bloc principal 25/11/2026 + 20:00
    if not sessions:
        dm = re.search(r"\b(\d{2})/(\d{2})/(20\d{2})\b", text)
        tm = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if dm and tm:
            sessions.append(datetime(
                int(dm.group(3)),
                int(dm.group(2)),
                int(dm.group(1)),
                int(tm.group(1)),
                int(tm.group(2)),
                tzinfo=PARIS,
            ))

    return sorted(sessions)


def _parse_event(href: str):
    response = requests.get(href, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    h1 = soup.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    if not title:
        return None

    text = clean(soup.get_text(" "))

    sessions = _extract_sessions(text)
    if not sessions:
        return None

    venue_match = re.search(
        r"Salle\s*:\s*(.+?)(?:\s+Durée\s*:|\s+Duree\s*:|\s+###|\s+\d{2}/\d{2}/)",
        text,
        re.IGNORECASE,
    )
    venue = clean(venue_match.group(1)) if venue_match else "La Comète"
    if not venue or venue.lower() == "autre":
        venue = "La Comète"

    session_strings = [dt.isoformat() for dt in sessions]

    event = {
        "id": stable_id("La Comète", title, session_strings[0]),
        "title": title,
        "start": session_strings[0],
        "venue": venue,
        "city": "Saint-Étienne",
        "category": _category(text),
        "description": "",
        "url": href,
        "source": "La Comète",
    }

    if len(session_strings) > 1:
        event["end"] = session_strings[-1]
        event["sessions"] = session_strings
        event["session_count"] = len(session_strings)

    return event


def scrape_comete() -> list[dict]:
    links = []

    try:
        links = _event_links_from_archive()
    except Exception:
        pass

    if not links:
        links = _event_links_from_sitemaps()

    print(f"La Comète: {len(links)} fiche(s) découverte(s)")

    now = datetime.now(PARIS)
    events = {}

    for href in links:
        try:
            event = _parse_event(href)
        except Exception as exc:
            print(f"La Comète: erreur fiche {href}: {exc}")
            continue

        if not event:
            continue

        # On garde si au moins une séance est future.
        dates = event.get("sessions") or [event["start"]]
        if not any(datetime.fromisoformat(x) >= now for x in dates):
            continue

        events[event["id"]] = event

    return sorted(events.values(), key=lambda ev: ev["start"])
