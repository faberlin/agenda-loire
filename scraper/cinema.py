from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean


ROOT = Path(__file__).resolve().parents[1]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}

# Les deux Mégarama ont une grille hebdomadaire très structurée.
MEGARAMA = [
    (
        "Mégarama Jean-Jaurès",
        "https://jean-jaures.megarama.fr/FR/programmation-cine?tk_source=site&tk_type=progpdf",
    ),
    (
        "Mégarama Camion Rouge",
        "https://chavanelle.megarama.fr/FR/programmation-cine?tk_source=site&tk_type=progpdf",
    ),
]

# Pour les Méliès on part du site officiel.
MELIES_URL = "https://www.lemelies.com/films/"

CINEMA_ALIASES = {
    "méliès jean jaurès": "Méliès Jean-Jaurès",
    "melies jean jaures": "Méliès Jean-Jaurès",
    "le méliès jean jaurès": "Méliès Jean-Jaurès",
    "le melies jean jaures": "Méliès Jean-Jaurès",
    "jean jaurès": "Méliès Jean-Jaurès",
    "jean jaures": "Méliès Jean-Jaurès",

    "méliès st françois": "Méliès Saint-François",
    "melies st francois": "Méliès Saint-François",
    "méliès saint françois": "Méliès Saint-François",
    "melies saint francois": "Méliès Saint-François",
    "le méliès st-françois": "Méliès Saint-François",
    "saint françois": "Méliès Saint-François",
    "st françois": "Méliès Saint-François",
}

DAY_NAMES = {
    "lun": 0,
    "mar": 1,
    "mer": 2,
    "jeu": 3,
    "ven": 4,
    "sam": 5,
    "dim": 6,
}

MONTHS = {
    "janv": 1, "janvier": 1,
    "févr": 2, "fevr": 2, "février": 2, "fevrier": 2,
    "mars": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "août": 8, "aout": 8,
    "sept": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "déc": 12, "dec": 12, "décembre": 12, "decembre": 12,
}


def _window():
    """Aujourd'hui 00:00 jusqu'à J+7 inclus (8 dates calendaires)."""
    now = datetime.now(PARIS)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=8)
    return start, end


def _in_window(dt: datetime) -> bool:
    start, end = _window()
    return start <= dt < end


def _stable_session_id(cinema: str, title: str, start: str, version: str) -> str:
    import hashlib
    raw = f"{cinema}|{title}|{start}|{version}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _infer_date(day_name: str, day_number: int) -> datetime | None:
    """
    Les grilles Mégarama affichent parfois seulement 'Mer 09'.
    On cherche la date correspondante autour des 7 prochains jours.
    """
    wanted_weekday = DAY_NAMES.get(day_name.lower()[:3])
    if wanted_weekday is None:
        return None

    start, end = _window()

    for offset in range(-1, 10):
        d = start + timedelta(days=offset)
        if d.day == day_number and d.weekday() == wanted_weekday:
            return d

    return None


def _split_times(text: str) -> list[str]:
    return re.findall(r"\b(\d{1,2})h(\d{2})\b|\b(\d{1,2}):(\d{2})\b", text)


def _time_strings(text: str) -> list[tuple[int, int]]:
    result = []
    for m in re.finditer(r"\b(\d{1,2})(?:h|:)(\d{2})\b", text):
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.append((hour, minute))
    return result


def scrape_megarama(cinema_name: str, url: str) -> list[dict]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table")
    if not table:
        print(f"{cinema_name}: aucune grille trouvée")
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # En-tête : Mer 09 / Jeu 10 / ...
    headers = []
    header_row_index = None

    for idx, row in enumerate(rows[:10]):
        cells = row.find_all(["th", "td"])
        parsed = []
        for cell in cells:
            txt = clean(cell.get_text(" "))
            m = re.search(
                r"\b(lun|mar|mer|jeu|ven|sam|dim)\.?\s*(\d{1,2})\b",
                txt,
                re.IGNORECASE,
            )
            if m:
                parsed.append(_infer_date(m.group(1), int(m.group(2))))

        if len(parsed) >= 5:
            headers = parsed
            header_row_index = idx
            break

    if not headers:
        print(f"{cinema_name}: dates de grille non reconnues")
        return []

    events = []
    current_title = ""
    current_url = url

    for row in rows[(header_row_index or 0) + 1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # Ligne titre de film : cellule couvrant toute la semaine.
        if len(cells) == 1 or int(cells[0].get("colspan", "1") or "1") >= len(headers):
            text = clean(cells[0].get_text(" "))
            if not text:
                continue

            # Ex: "MICHAEL — Drame, Biopic... | 02h07"
            current_title = re.split(r"\s+[—–-]\s+", text, maxsplit=1)[0].strip()

            link = cells[0].find("a", href=True)
            if link:
                from urllib.parse import urljoin
                current_url = urljoin(url, link["href"])
            else:
                current_url = url

            continue

        if not current_title:
            continue

        # Première cellule = VF / VO / VOST...
        version = clean(cells[0].get_text(" ")).upper()
        if not version:
            version = ""

        # Le reste correspond aux jours.
        session_cells = cells[1:]

        for day_index, cell in enumerate(session_cells):
            if day_index >= len(headers):
                break

            date = headers[day_index]
            if not date:
                continue

            cell_text = clean(cell.get_text(" "))

            for hour, minute in _time_strings(cell_text):
                dt = date.replace(hour=hour, minute=minute)

                if not _in_window(dt):
                    continue

                start = dt.isoformat()

                events.append({
                    "id": _stable_session_id(
                        cinema_name, current_title, start, version
                    ),
                    "title": current_title,
                    "cinema": cinema_name,
                    "start": start,
                    "version": version,
                    "url": current_url,
                })

    return events


def _normalize_cinema(text: str) -> str | None:
    low = (
        clean(text)
        .lower()
        .replace("-", " ")
        .replace("’", "'")
    )

    for alias, canonical in CINEMA_ALIASES.items():
        if alias in low:
            return canonical

    return None


def _parse_explicit_date(text: str) -> datetime | None:
    """
    Reconnaît notamment :
      mer. 9 sept.
      mercredi 9 septembre
      mer. 9 sept. 2026
    """
    m = re.search(
        r"\b(lun|mar|mer|jeu|ven|sam|dim)[a-zéû]*\.?\s+"
        r"(\d{1,2})\s+"
        r"(janv(?:ier)?|févr(?:ier)?|fevr(?:ier)?|mars|avr(?:il)?|mai|juin|"
        r"juil(?:let)?|août|aout|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|"
        r"déc(?:embre)?|dec(?:embre)?)\.?"
        r"(?:\s+(20\d{2}))?",
        text,
        re.IGNORECASE,
    )

    if not m:
        return None

    month = MONTHS.get(m.group(3).lower().rstrip("."))
    if not month:
        return None

    now = datetime.now(PARIS)
    year = int(m.group(4)) if m.group(4) else now.year

    # Passage décembre -> janvier.
    if not m.group(4):
        candidate = datetime(year, month, int(m.group(2)), tzinfo=PARIS)
        if candidate < now - timedelta(days=30):
            year += 1

    try:
        return datetime(year, month, int(m.group(2)), tzinfo=PARIS)
    except ValueError:
        return None


def scrape_melies() -> list[dict]:
    """
    Parser volontairement souple du site officiel du Méliès.

    Le site change régulièrement sa mise en page. On parcourt les cartes de films
    et cherche, dans chaque carte, les dates, les deux cinémas et les horaires.
    """
    response = requests.get(MELIES_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()

    # Candidats "film" : articles / cartes contenant un titre et des horaires.
    candidates = soup.find_all(["article", "li", "div"])

    for block in candidates:
        block_text = clean(block.get_text(" "))
        if not re.search(r"\b\d{1,2}(?:h|:)\d{2}\b", block_text):
            continue

        heading = block.find(["h2", "h3", "h4"])
        if not heading:
            continue

        title = clean(heading.get_text(" "))
        if not title or len(title) > 140:
            continue

        # Une carte utile doit mentionner au moins un des deux sites.
        if not _normalize_cinema(block_text):
            continue

        link = heading.find("a", href=True) or block.find("a", href=True)
        if link:
            from urllib.parse import urljoin
            film_url = urljoin(MELIES_URL, link["href"])
        else:
            film_url = MELIES_URL

        # Lecture séquentielle des petits blocs internes.
        current_date = None
        current_cinema = None

        for node in block.find_all(["div", "li", "p", "span", "time", "strong"]):
            text = clean(node.get_text(" "))
            if not text:
                continue

            d = _parse_explicit_date(text)
            if d:
                current_date = d

            c = _normalize_cinema(text)
            if c:
                current_cinema = c

            if current_date and current_cinema:
                for hour, minute in _time_strings(text):
                    dt = current_date.replace(hour=hour, minute=minute)

                    if not _in_window(dt):
                        continue

                    # Version si elle est indiquée près de l'horaire.
                    version_match = re.search(
                        r"\b(VF|VO|VOST|VOSTF|VOF|VFST)\b",
                        text,
                        re.IGNORECASE,
                    )
                    version = (
                        version_match.group(1).upper()
                        if version_match else ""
                    )

                    key = (
                        title.lower(),
                        current_cinema,
                        dt.isoformat(),
                        version,
                    )
                    if key in seen:
                        continue
                    seen.add(key)

                    events.append({
                        "id": _stable_session_id(
                            current_cinema,
                            title,
                            dt.isoformat(),
                            version,
                        ),
                        "title": title,
                        "cinema": current_cinema,
                        "start": dt.isoformat(),
                        "version": version,
                        "url": film_url,
                    })

    return events


def scrape_cinema() -> list[dict]:
    events = []

    for cinema_name, url in MEGARAMA:
        try:
            found = scrape_megarama(cinema_name, url)
            print(f"{cinema_name}: {len(found)} séance(s)")
            events.extend(found)
        except Exception as exc:
            print(f"ERREUR {cinema_name}: {exc}")

    try:
        melies = scrape_melies()

        jj = [x for x in melies if x["cinema"] == "Méliès Jean-Jaurès"]
        sf = [x for x in melies if x["cinema"] == "Méliès Saint-François"]

        print(f"Méliès Jean-Jaurès: {len(jj)} séance(s)")
        print(f"Méliès Saint-François: {len(sf)} séance(s)")

        events.extend(melies)

    except Exception as exc:
        print(f"ERREUR Méliès: {exc}")

    # Dédoublonnage + tri
    unique = {}
    for event in events:
        unique[event["id"]] = event

    return sorted(
        unique.values(),
        key=lambda x: (x["start"], x["cinema"], x["title"])
    )


if __name__ == "__main__":
    events = scrape_cinema()

    out = ROOT / "cinema_events.json"
    out.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"{len(events)} séance(s) écrite(s) dans {out}")
