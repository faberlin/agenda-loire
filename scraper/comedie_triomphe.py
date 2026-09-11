from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import PARIS, clean, stable_id

CATALOG_URL = "https://www.comedietriomphe.fr/tout-publicold/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def infer_category(title: str) -> str:
    val = title.lower()
    if any(w in val for w in ("enfant", "fantôme", "sorcière", "jeune public", "conte", "princesse")):
        return "Jeune public"
    if any(w in val for w in ("magie", "mental", "hypnose")):
        return "Spectacle"
    if any(w in val for w in ("stand-up", "one man", "humour", "comedy")):
        return "Humour"
    return "Théâtre"

def fetch_billetweb_events(bw_url: str, show_title: str, show_url: str, today_start: datetime) -> list[dict]:
    """Extrait les séances directement depuis l'iFrame Billetweb du spectacle."""
    events = []
    try:
        res = requests.get(bw_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []

        # Recherche de la variable JS contenant la liste des événements/séances
        match = re.search(r"var\s+events\s*=\s*(\[.*?\]);", res.text, re.DOTALL)
        if not match:
            match = re.search(r"events\s*=\s*(\[.*?\]);", res.text, re.DOTALL)

        if match:
            data = json.loads(match.group(1))
            for item in data:
                start_str = item.get("start") or item.get("date")
                if not start_str:
                    continue

                try:
                    if isinstance(start_str, (int, float)):
                        dt = datetime.fromtimestamp(start_str, tz=PARIS)
                    else:
                        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(PARIS)
                except Exception:
                    continue

                # Filtre : uniquement les séances futures
                if dt < today_start:
                    continue

                start = dt.isoformat()
                events.append({
                    "id": stable_id("Comédie Triomphe", show_title, start),
                    "title": show_title,
                    "start": start,
                    "venue": "Comédie Triomphe",
                    "city": "Saint-Étienne",
                    "category": infer_category(show_title),
                    "description": clean(item.get("description", ""))[:500],
                    "url": show_url,
                    "source": "Comédie Triomphe",
                })
    except Exception as exc:
        print(f"Erreur extraction Billetweb ({bw_url}): {exc}")

    return events

def scrape_comedie_triomphe() -> list[dict]:
    events = []
    seen = set()
    now = datetime.now(tz=PARIS)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        # 1. Charger la page catalogue
        res = requests.get(CATALOG_URL, headers=HEADERS, timeout=20)
        if res.status_code != 200:
            print(f"Erreur HTTP {res.status_code} sur {CATALOG_URL}")
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # 2. Récupérer tous les liens vers les fiches de spectacle
        show_links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/spectacle/" in href or "/evenement/" in href:
                show_links.add(urljoin(CATALOG_URL, href))

        print(f"Comédie Triomphe : {len(show_links)} fiche(s) de spectacle trouvée(s)")

        # 3. Visiter chaque fiche pour récupérer les séances Billetweb
        for show_url in show_links:
            try:
                sub_res = requests.get(show_url, headers=HEADERS, timeout=10)
                if sub_res.status_code != 200:
                    continue

                sub_soup = BeautifulSoup(sub_res.text, "html.parser")
                
                # Récupération du titre exact de la pièce
                title_el = sub_soup.find(["h1", "h2"])
                if not title_el:
                    continue
                title = clean(title_el.get_text(" "))

                # Recherche du widget de billetterie Billetweb dans la page
                iframes = sub_soup.find_all("iframe", src=re.compile(r"billetweb\.fr"))
                for iframe in iframes:
                    bw_url = iframe.get("src")
                    if not bw_url:
                        continue

                    found_events = fetch_billetweb_events(bw_url, title, show_url, today_start)
                    for ev in found_events:
                        if ev["id"] not in seen:
                            seen.add(ev["id"])
                            events.append(ev)

            except Exception as exc:
                print(f"Erreur traitement spectacle {show_url}: {exc}")

    except Exception as exc:
        print(f"Erreur globale Comédie Triomphe: {exc}")

    events.sort(key=lambda e: (e["start"], e["title"].lower()))
    print(f"Comédie Triomphe : {len(events)} séance(s) à venir retenue(s)")
    return events

if __name__ == "__main__":
    for event in scrape_comedie_triomphe():
        print(event)
