from __future__ import annotations

import re
from datetime import datetime
import cloudscraper
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

URL = "https://42.agendaculturel.fr/le-triomphe"

MONTHS = {
    "janv": 1, "jan": 1, "févr": 2, "fevr": 2, "fév": 2, "fev": 2,
    "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7,
    "août": 8, "aout": 8, "sept": 9, "sep": 9, "oct": 10,
    "nov": 11, "déc": 12, "dec": 12,
}

DATE_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(janv?|févr?|fevr?|mars|avr|mai|juin|juil|août|aout|sept?|oct|nov|déc|dec)"
    r"\.?\s+(\d{4})",
    re.IGNORECASE,
)

def infer_category(title: str) -> str:
    val = title.lower()
    if any(w in val for w in ("enfant", "fantôme", "sorcière", "jeune public")):
        return "Jeune public"
    if any(w in val for w in ("magie", "mental", "hypnose")):
        return "Spectacle"
    if any(w in val for w in ("stand-up", "one man", "humour", "comedy")):
        return "Humour"
    return "Théâtre"

def scrape_triomphe_agenda_culturel() -> list[dict]:
    # Création du client contournant Cloudflare
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(URL, timeout=20)
        if response.status_code != 200:
            print(f"Agenda Culturel : Erreur HTTP {response.status_code}")
            return []
    except Exception as exc:
        print(f"Agenda Culturel : Erreur d'accès {exc}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    seen = set()
    
    now = datetime.now(tz=PARIS)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Récupération des cartes de spectacles
    cards = soup.select(".list-events .event, article, .card-event")

    for card in cards:
        title_el = card.select_one("h2, h3, .title")
        if not title_el:
            continue
        
        title = clean(title_el.get_text())
        
        # Lien vers la fiche
        link_el = card.find("a", href=True)
        event_url = link_el["href"] if link_el else URL

        # Extraction de la date dans le texte de la carte
        card_text = clean(card.get_text())
        match = DATE_RE.search(card_text)
        
        if not match:
            continue

        day = int(match.group(1))
        month_str = match.group(2).lower().replace(".", "").replace("é", "e").replace("û", "u")
        month = MONTHS.get(month_str)
        year = int(match.group(3))

        if not month:
            continue

        try:
            # Heure fixée à 20h00 par défaut si non spécifiée
            dt = datetime(year, month, day, 20, 0, tzinfo=PARIS)
        except ValueError:
            continue

        if dt < today_start:
            continue

        start = dt.isoformat()
        event_id = stable_id("Comédie Triomphe", title, start)

        if event_id in seen:
            continue

        seen.add(event_id)
        events.append({
            "id": event_id,
            "title": title,
            "start": start,
            "venue": "Comédie Triomphe",
            "city": "Saint-Étienne",
            "category": infer_category(title),
            "description": "",
            "url": event_url,
            "source": "Agenda Culturel",
        })

    print(f"Agenda Culturel (Triomphe) : {len(events)} événement(s) récupéré(s)")
    return events

if __name__ == "__main__":
    for event in scrape_triomphe_agenda_culturel():
        print(event)
