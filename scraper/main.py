from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser


ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads(
    (ROOT / "sources.json").read_text(
        encoding="utf-8"
    )
)
OUT = ROOT / "events.json"

HEADERS = {
    "User-Agent": (
        "AgendaLoire/1.0 "
        "(personal cultural events aggregator)"
    )
}

PARIS = ZoneInfo("Europe/Paris")


# ======================================================
# OUTILS
# ======================================================

def stable_id(
    source: str,
    title: str,
    start: str,
) -> str:
    raw = (
        f"{source}|{title}|{start}"
    ).encode("utf-8")

    return hashlib.sha1(
        raw
    ).hexdigest()[:20]


def clean(
    text: str | None,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()


# ======================================================
# DATES FRANÇAISES
# ======================================================

def parse_french_event_date(
    text: str,
) -> datetime | None:
    """
    Extrait la vraie date de début d'un événement
    depuis des textes du type :

    - Du 15/09/2026 10:00 au 17/10/2026 18:30
    - Le 09/10/2026 19:30
    - 09/10/2026 19:30

    Si l'heure est absente, on met 00:00.
    """

    text = clean(text)

    patterns = [
        (
            r"\bDu\s+"
            r"(\d{1,2})/"
            r"(\d{1,2})/"
            r"(\d{4})"
            r"(?:\s+(\d{1,2}):(\d{2}))?"
        ),
        (
            r"\bLe\s+"
            r"(\d{1,2})/"
            r"(\d{1,2})/"
            r"(\d{4})"
            r"(?:\s+(\d{1,2}):(\d{2}))?"
        ),
        (
            r"\b"
            r"(\d{1,2})/"
            r"(\d{1,2})/"
            r"(\d{4})"
            r"(?:\s+(\d{1,2}):(\d{2}))?"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        day, month, year = map(
            int,
            match.group(1, 2, 3),
        )

        hour = (
            int(match.group(4))
            if match.group(4)
            else 0
        )

        minute = (
            int(match.group(5))
            if match.group(5)
            else 0
        )

        try:
            return datetime(
                year,
                month,
                day,
                hour,
                minute,
                tzinfo=PARIS,
            )

        except ValueError:
            continue

    return None


# ======================================================
# RSS
# ======================================================

def parse_feed(
    source: dict,
) -> list[dict]:

    feed = feedparser.parse(
        source["url"]
    )

    events = []

    for item in feed.entries:
        title = clean(
            item.get("title")
        )

        link = (
            item.get("link")
            or source["url"]
        )

        summary_html = item.get(
            "summary",
            "",
        )

        summary = clean(
            BeautifulSoup(
                summary_html,
                "html.parser",
            ).get_text(" ")
        )

        # Priorité à la vraie date
        # contenue dans le texte.
        dt = parse_french_event_date(
            summary
        )

        if dt is None:
            dt = parse_french_event_date(
                f"{title} {summary}"
            )

        # Dernier recours :
        # date de publication RSS.
        if dt is None:
            raw_date = (
                item.get("published")
                or item.get("updated")
            )

            if not raw_date:
                continue

            try:
                dt = dateparser.parse(
                    raw_date
                )

                if not dt.tzinfo:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

            except Exception:
                continue

        start = dt.isoformat()

        events.append(
            {
                "id": stable_id(
                    source["name"],
                    title,
                    start,
                ),
                "title": title,
                "start": start,
                "venue": source["name"],
                "city": source.get(
                    "city",
                    "",
                ),
                "category": source.get(
                    "category",
                    "Culture",
                ),
                "description": summary[:500],
                "url": link,
                "source": source["name"],
            }
        )

    return events


# ======================================================
# HTML GÉNÉRIQUE
# ======================================================

FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}


def parse_french_text_date(text: str) -> datetime | None:
    """Détecte une date française écrite en toutes lettres."""
    text = clean(text).lower()
    month_names = "|".join(
        sorted((re.escape(m) for m in FRENCH_MONTHS), key=len, reverse=True)
    )

    patterns = [
        re.compile(
            rf"\bdu\s+(\d{{1,2}})(?:er)?\s+au\s+\d{{1,2}}(?:er)?\s+"
            rf"({month_names})\s+(20\d{{2}})"
            rf"(?:\s+(?:à|a)\s+(\d{{1,2}})(?:\s*[h:]\s*(\d{{2}}))?)?",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b(\d{{1,2}})(?:er)?\s+({month_names})\s+(20\d{{2}})"
            rf"(?:\s+(?:à|a)\s+(\d{{1,2}})(?:\s*[h:]\s*(\d{{2}}))?)?",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        day = int(match.group(1))
        month = FRENCH_MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        try:
            return datetime(year, month, day, hour, minute, tzinfo=PARIS)
        except ValueError:
            continue
    return None


def meta_content(soup: BeautifulSoup, *, property_name=None, name=None) -> str:
    attrs = {}
    if property_name:
        attrs["property"] = property_name
    if name:
        attrs["name"] = name
    tag = soup.find("meta", attrs=attrs)
    return clean(tag.get("content")) if tag else ""


def page_title(soup: BeautifulSoup, source: dict) -> str:
    title = meta_content(soup, property_name="og:title")
    if title:
        return title
    h1 = soup.find("h1")
    if h1 and clean(h1.get_text(" ")):
        return clean(h1.get_text(" "))
    if soup.title and clean(soup.title.get_text(" ")):
        return clean(soup.title.get_text(" "))
    return source["name"]


def page_description(soup: BeautifulSoup) -> str:
    description = meta_content(soup, property_name="og:description")
    if not description:
        description = meta_content(soup, name="description")
    return description[:500]


def parse_datetime_attribute(raw: str) -> datetime | None:
    raw = clean(raw)
    if not raw:
        return None
    try:
        dt = dateparser.parse(raw, dayfirst=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PARIS)
        return dt
    except Exception:
        return None


def find_html_event_date(soup: BeautifulSoup) -> datetime | None:
    """Cherche d'abord <time datetime>, puis une date visible dans le contenu."""
    for time_tag in soup.find_all("time"):
        raw = time_tag.get("datetime")
        if raw:
            dt = parse_datetime_attribute(raw)
            if dt:
                return dt

    content = BeautifulSoup(str(soup), "html.parser")
    for tag in content.select("script, style, noscript, nav, footer"):
        tag.decompose()

    text = clean(content.get_text(" ", strip=True))
    dt = parse_french_event_date(text)
    if dt:
        return dt
    return parse_french_text_date(text)


def jsonld_nodes(payload) -> list[dict]:
    roots = payload if isinstance(payload, list) else [payload]
    result = []
    for node in roots:
        if not isinstance(node, dict):
            continue
        graph = node.get("@graph")
        if isinstance(graph, list):
            result.extend(item for item in graph if isinstance(item, dict))
        result.append(node)
    return result


def is_jsonld_event(node: dict) -> bool:
    kind = node.get("@type")
    kinds = [str(v) for v in kind] if isinstance(kind, list) else [str(kind)]
    return any(v == "Event" or v.endswith("Event") for v in kinds)


def event_from_jsonld(source: dict, node: dict) -> dict | None:
    title = clean(node.get("name"))
    raw_start = node.get("startDate")
    if not title or not raw_start:
        return None

    try:
        dt = dateparser.parse(str(raw_start), dayfirst=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PARIS)
    except Exception:
        return None

    start = dt.isoformat()
    location = node.get("location") or {}
    if isinstance(location, list) and location:
        location = location[0]

    venue = source.get("venue") or source["name"]
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
        BeautifulSoup(str(node.get("description", "")), "html.parser").get_text(" ")
    )

    return {
        "id": stable_id(source["name"], title, start),
        "title": title,
        "start": start,
        "venue": venue,
        "city": city,
        "category": source.get("category", "Culture"),
        "description": description[:500],
        "url": url,
        "source": source["name"],
    }


def parse_generic_html(source: dict) -> list[dict]:
    """
    Collecteur générique pour les petits événements.

    Priorité :
    1. schema.org Event en JSON-LD ;
    2. <time datetime="..."> ;
    3. date numérique visible ;
    4. date française en toutes lettres.

    Sans date fiable, aucun événement n'est créé.
    """
    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=25,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        for node in jsonld_nodes(payload):
            if not is_jsonld_event(node):
                continue
            event = event_from_jsonld(source, node)
            if event:
                events.append(event)

    if events:
        return dedupe(events)

    dt = find_html_event_date(soup)
    if dt is None:
        print(
            f'{source["name"]}: aucune date fiable trouvée dans la page HTML'
        )
        return []

    title = page_title(soup, source)
    if source.get("use_source_name_as_title", False):
        title = source["name"]

    start = dt.isoformat()

    return [{
        "id": stable_id(source["name"], title, start),
        "title": title,
        "start": start,
        "venue": source.get("venue") or source["name"],
        "city": source.get("city", ""),
        "category": source.get("category", "Culture"),
        "description": page_description(soup),
        "url": source["url"],
        "source": source["name"],
    }]


# ======================================================
# DÉDOUBLONNAGE
# ======================================================

def dedupe(
    events: list[dict],
) -> list[dict]:

    seen = set()
    result = []

    for ev in sorted(
        events,
        key=lambda x: x["start"],
    ):
        key = (
            ev["title"].lower(),
            ev["start"][:10],
            ev.get(
                "city",
                "",
            ).lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(ev)

    return result


# ======================================================
# SCRAPERS DÉDIÉS
# ======================================================

DEDICATED_SCRAPERS = [
    (
        "mediatheques",
        "scrape_mediatheques",
    ),
    (
        "le_fil",
        "scrape_le_fil",
    ),
    (
        "zenith",
        "scrape_zenith",
    ),
    (
        "opera",
        "scrape_opera",
    ),
    (
        "comedie",
        "scrape_comedie",
    ),
    (
        "solar",
        "scrape_solar",
    ),
    (
        "chambon",
        "scrape_chambon",
    ),
    (
        "comete",
        "scrape_comete",
    ),
    (
        "trois_ducs",
        "scrape_trois_ducs",
    ),
    (
        "chok",
        "scrape_chok",
    ),
    (
        "verso",
        "scrape_verso",
    ),
    (
        "arcomik",
        "scrape_arcomik",
    ),
    (
        "comedie_triomphe",
        "scrape_comedie_triomphe",
    ),
    (
        "la_ricane",
        "scrape_la_ricane",
    ),
    (
        "aristide_briand",
        "scrape_aristide_briand",
    ),
    (
        "brankignols",
        "scrape_brankignols",
    ),
]


# ======================================================
# CORRESPONDANCE MODULE -> SOURCE
# ======================================================

DEDICATED_EVENT_SOURCES = {
    "mediatheques": {
        "médiathèques de saint-étienne",
        "mediatheques de saint-etienne",
    },

    "le_fil": {
        "le fil",
    },

    "zenith": {
        "zénith sainté",
        "zenith sainte",
    },

    "opera": {
        "opéra sainté",
        "opera sainte",
    },

    "comedie": {
        "comédie sainté",
        "comedie sainte",
        "la comédie de saint-étienne",
        "la comedie de saint-etienne",
    },

    "solar": {
        "le solar",
    },

    "chambon": {
        "salles chambon-feugerolles",
    },

    "comete": {
        "la comète",
        "la comete",
    },

    "trois_ducs": {
        "les 3 ducs",
    },

    "chok": {
        "chok théâtre",
        "chok theatre",
    },

    "verso": {
        "théâtre le verso",
        "theatre le verso",
    },

    "arcomik": {
        "arcomik",
    },

    "comedie_triomphe": {
        "comédie triomphe",
        "comedie triomphe",
    },

    "la_ricane": {
        "la ricane",
    },

    "aristide_briand": {
        "salle aristide briand",
    },

    "brankignols": {
        "théâtre de poche des brankignols",
        "theatre de poche des brankignols",
    },
}


DEDICATED_SOURCE_NAMES = {
    name
    for names
    in DEDICATED_EVENT_SOURCES.values()
    for name in names
}


# ======================================================
# EXÉCUTION D'UN SCRAPER DÉDIÉ
# ======================================================

def run_dedicated_scraper(
    module_name: str,
    expected_function: str,
) -> list[dict]:

    try:
        module = importlib.import_module(
            module_name
        )

    except Exception as exc:
        print(
            f"ERREUR import "
            f"{module_name}: {exc}"
        )
        return []

    scraper = getattr(
        module,
        expected_function,
        None,
    )

    # Fallback si le nom exact
    # diffère légèrement.
    if scraper is None:
        for name in dir(module):
            if name.startswith(
                "scrape_"
            ):
                candidate = getattr(
                    module,
                    name,
                )

                if callable(
                    candidate
                ):
                    scraper = candidate
                    break

    if scraper is None:
        print(
            f"ERREUR {module_name}: "
            "aucune fonction "
            f"{expected_function} / "
            "scrape_* trouvée"
        )
        return []

    try:
        found = scraper() or []

        print(
            f"{module_name}: "
            f"{len(found)} événement(s)"
        )

        return found

    except Exception as exc:
        print(
            f"ERREUR {module_name}: "
            f"{exc}"
        )

        return []


# ======================================================
# SOURCES
# ======================================================

def normalized_source_name(
    value: str,
) -> str:
    return clean(
        value
    ).lower()


# ======================================================
# CHARGEMENT EVENTS.JSON EXISTANT
# ======================================================

def load_existing_events() -> list[dict]:
    """
    Charge events.json existant.

    Utilisé uniquement lorsqu'on lance --only
    afin de conserver toutes les autres sources.
    """

    if not OUT.exists():
        return []

    try:
        data = json.loads(
            OUT.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            list,
        ):
            return []

        return data

    except Exception as exc:
        print(
            "ERREUR lecture "
            f"events.json : {exc}"
        )

        return []


# ======================================================
# REMPLACEMENT D'UNE SEULE SOURCE
# ======================================================

def replace_source_events(
    existing_events: list[dict],
    module_name: str,
    new_events: list[dict],
) -> list[dict]:
    """
    Conserve tous les événements existants sauf ceux
    appartenant au scraper ciblé.

    Les anciens événements de cette source sont ensuite
    remplacés par le résultat du nouveau scraping.
    """

    source_names = (
        DEDICATED_EVENT_SOURCES.get(
            module_name,
            set(),
        )
    )

    # Sécurité supplémentaire :
    # les nouvelles données nous donnent aussi
    # le nom exact réellement utilisé par le scraper.
    for event in new_events:
        source = normalized_source_name(
            event.get(
                "source",
                "",
            )
        )

        if source:
            source_names.add(
                source
            )

    kept_events = []

    removed = 0

    for event in existing_events:
        source = normalized_source_name(
            event.get(
                "source",
                "",
            )
        )

        if source in source_names:
            removed += 1
            continue

        kept_events.append(
            event
        )

    print(
        f"{module_name}: "
        f"{removed} ancien(s) "
        "événement(s) remplacé(s)"
    )

    kept_events.extend(
        new_events
    )

    return kept_events


# ======================================================
# MAIN
# ======================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Agenda Loire Scraper"
        )
    )

    parser.add_argument(
        "--only",
        type=str,
        help=(
            "Exécuter un seul scraper dédié "
            "(ex: la_ricane, chok, "
            "comedie_triomphe)"
        ),
    )

    args = parser.parse_args()

    # ==================================================
    # MODE CIBLÉ --only
    # ==================================================

    if args.only:
        target = (
            args.only
            .lower()
            .strip()
        )

        matched_scraper = None

        for (
            module_name,
            func_name,
        ) in DEDICATED_SCRAPERS:

            if (
                target == module_name
                or target == func_name
                or target in module_name
            ):
                matched_scraper = (
                    module_name,
                    func_name,
                )
                break

        if not matched_scraper:
            print(
                "❌ Aucun scraper trouvé "
                "pour l'argument --only : "
                f"'{args.only}'"
            )
            return

        (
            module_name,
            func_name,
        ) = matched_scraper

        print(
            "🚀 Lancement ciblé "
            f"du scraper : {module_name}"
        )

        # On charge D'ABORD le fichier existant.
        existing_events = (
            load_existing_events()
        )

        print(
            f"{len(existing_events)} "
            "événement(s) actuellement "
            "dans events.json"
        )

        # Puis on lance uniquement
        # le scraper demandé.
        found = run_dedicated_scraper(
            module_name,
            func_name,
        )

        # IMPORTANT :
        # si le scraper ciblé échoue,
        # on ne détruit pas ses anciennes données.
        if not found:
            print(
                f"⚠️ {module_name} "
                "n'a retourné aucun événement."
            )

            print(
                "events.json conservé "
                "sans modification."
            )

            return

        # Remplacement uniquement
        # de la source concernée.
        all_events = replace_source_events(
            existing_events,
            module_name,
            found,
        )

        all_events = dedupe(
            all_events
        )

        OUT.write_text(
            json.dumps(
                all_events,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"{len(all_events)} "
            "événements écrits dans "
            f"{OUT}"
        )

        print(
            "✅ Mise à jour ciblée terminée : "
            "les autres sources ont été conservées."
        )

        return

    # ==================================================
    # MODE GLOBAL
    # ==================================================

    all_events = []

    # Sources génériques
    for source in SOURCES:
        try:
            source_name = (
                normalized_source_name(
                    source.get(
                        "name",
                        "",
                    )
                )
            )

            # Un lieu ayant un scraper dédié
            # ne doit pas être collecté deux fois.
            if (
                source_name
                in DEDICATED_SOURCE_NAMES
            ):
                print(
                    f'{source["name"]}: '
                    "ignoré dans sources.json "
                    "(scraper dédié)"
                )

                continue

            if (
                source["type"]
                == "rss"
            ):
                found = parse_feed(
                    source
                )

            else:
                found = (
                    parse_generic_html(
                        source
                    )
                )

            print(
                f'{source["name"]}: '
                f"{len(found)} événement(s)"
            )

            all_events.extend(
                found
            )

        except Exception as exc:
            print(
                f'ERREUR '
                f'{source["name"]}: '
                f"{exc}"
            )

    # Scrapers dédiés
    for (
        module_name,
        function_name,
    ) in DEDICATED_SCRAPERS:

        found = (
            run_dedicated_scraper(
                module_name,
                function_name,
            )
        )

        all_events.extend(
            found
        )

    all_events = dedupe(
        all_events
    )

    # Ne pas écraser le fichier
    # si absolument tout a échoué.
    if not all_events:
        print(
            "Aucun événement collecté : "
            "events.json conservé."
        )

        return

    OUT.write_text(
        json.dumps(
            all_events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{len(all_events)} "
        "événements écrits dans "
        f"{OUT}"
    )


if __name__ == "__main__":
    main()
