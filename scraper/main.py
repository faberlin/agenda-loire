from __future__ import annotations

import json
from pathlib import Path

from mediatheques import scrape_mediatheques
from infoconcert import scrape_infoconcert_venue
from utils import dedupe


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "events.json"


def scrape_le_fil():
    return scrape_infoconcert_venue(
        url="https://www.infoconcert.com/salle/le-fil-a-saint-etienne-21927/concerts",
        venue="Le Fil",
        city="Saint-Étienne",
        category="Musique",
    )


SCRAPERS = [
    ("Médiathèques de Saint-Étienne", scrape_mediatheques),
    ("Le Fil via Infoconcert", scrape_le_fil),
]


def main():
    all_events = []

    for name, scraper in SCRAPERS:
        try:
            found = scraper()
            print(f"{name}: {len(found)} événement(s)")
            all_events.extend(found)
        except Exception as exc:
            print(f"ERREUR {name}: {exc}")

    all_events = dedupe(all_events)

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
