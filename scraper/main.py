from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
OUT = ROOT / "events.json"

HEADERS = {
    "User-Agent": "AgendaLoire/1.0 (personal cultural events aggregator)"
}

PARIS = ZoneInfo("Europe/Paris")


def stable_id(source: str, title: str, start: str) -> str:
    raw = f"{source}|{title}|{start}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_french_event_date(text: str) -> datetime | None:
    """
    Extrait la vraie date de début d'un événement depuis des textes du type :
      - Du 15/09/2026 10:00 au 17/10/2026 18:30
      - Du 18/09/2026 10:00 au 31/10/2026 18:30
      - Le 09/10/2026 19:30
      - 09/10/2026 19:30

    Si l'heure est absente, on met 00:00.
    """
    text = clean(text)

    patterns = [
        r"\bDu\s+(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
        r"\bLe\s+(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        day, month, year = map(int, match.group(1, 2, 3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0

        try:
            return datetime(year, month, day, hour, minute, tzinfo=PARIS)
        except ValueError:
            continue

    return None


def parse_feed(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"])
    events = []

    for item in feed.entries:
        title = clean(item.get("title"))
        link = item.get("link") or source["url"]

        summary_html = item.get("summary", "")
        summary = clean(BeautifulSoup(summary_html, "html.parser").get_text(" "))

        # Priorité absolue à la date réelle contenue dans le texte de l'événement.
        dt = parse_french_event_date(summary)

        # À défaut, on tente aussi le titre + résumé.
        if dt is None:
            dt = parse_french_event_date(f"{title} {summary}")

        # Dernier recours : date publiée par le RSS.
        # Cela évite de perdre l'événement si le flux ne contient pas de vraie date.
        if dt is None:
            raw_date = item.get("published") or item.get("updated")
            if not raw_date:
                continue

            try:
                dt = dateparser.parse(raw_date)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

        start = dt.isoformat()

        events.append({
            "id": stable_id(source["name"], title, start),
            "title": title,
            "start": start,
            "venue": source["name"],
            "city": source.get("city", ""),
            "category": source.get("category", "Culture"),
            "description": summary[:500],
            "url": link,
            "source": source["name"]
        })

    return events


def parse_generic_html(source: dict) -> list[dict]:
    """
    Recherche les événements schema.org Event en JSON-LD.
    Pour un site sans JSON-LD, il faudra créer un collecteur dédié.
    """
    response = requests.get(source["url"], headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except Exception:
            continue

        nodes = payload if isinstance(payload, list) else [payload]
        expanded = []

        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                expanded.extend(node["@graph"])
            else:
                expanded.append(node)

        for node in expanded:
            if not isinstance(node, dict):
                continue

            kind = node.get("@type")
            if isinstance(kind, list):
                is_event = "Event" in kind
            else:
                is_event = kind == "Event" or (
                    isinstance(kind, str) and kind.endswith("Event")
                )

            if not is_event:
                continue

            title = clean(node.get("name"))
            raw_start = node.get("startDate")

            if not title or not raw_start:
                continue

            try:
                dt = dateparser.parse(raw_start)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=PARIS)
                start = dt.isoformat()
            except Exception:
                continue

            location = node.get("location") or {}
            if isinstance(location, list) and location:
                location = location[0]

            venue = source["name"]
            city = source.get("city", "")

            if isinstance(location, dict):
                venue = clean(location.get("name")) or venue
                address = location.get("address") or {}

                if isinstance(address, dict):
                    city = clean(address.get("addressLocality")) or city

            url = node.get("url") or source["url"]

            if isinstance(url, dict):
                url = url.get("@id") or source["url"]

            url = urljoin(source["url"], str(url))

            description = clean(
                BeautifulSoup(
                    str(node.get("description", "")),
                    "html.parser"
                ).get_text(" ")
            )

            events.append({
                "id": stable_id(source["name"], title, start),
                "title": title,
                "start": start,
                "venue": venue,
                "city": city,
                "category": source.get("category", "Culture"),
                "description": description[:500],
                "url": url,
                "source": source["name"]
            })

    return events


def dedupe(events: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for ev in sorted(events, key=lambda x: x["start"]):
        key = (
            ev["title"].lower(),
            ev["start"][:10],
            ev.get("city", "").lower()
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(ev)

    return result


def main():
    all_events = []

    for source in SOURCES:
        try:
            if source["type"] == "rss":
                found = parse_feed(source)
            else:
                found = parse_generic_html(source)

            print(f'{source["name"]}: {len(found)} événement(s)')
            all_events.extend(found)

        except Exception as exc:
            print(f'ERREUR {source["name"]}: {exc}')

    all_events = dedupe(all_events)

    # Ne pas écraser le fichier existant si toutes les sources échouent.
    if not all_events:
        print("Aucun événement collecté : events.json conservé.")
        return

    OUT.write_text(
        json.dumps(all_events, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"{len(all_events)} événements écrits dans {OUT}")


if __name__ == "__main__":
    main()
