from pathlib import Path
import json

from utils import dedupe

from mediatheques import scrape_mediatheques
from le_fil import scrape_le_fil
from zenith import scrape_zenith
from opera import scrape_opera
from comedie import scrape_comedie

from solar import scrape_solar
from chambon import scrape_chambon
from comete import scrape_comete
from trois_ducs import scrape_trois_ducs
from chok import scrape_chok
from verso import scrape_verso
from arcomik import scrape_arcomik
from comedie_triomphe import scrape_comedie_triomphe


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "events.json"

SCRAPERS = [
    ("Médiathèques Sainté", scrape_mediatheques),
    ("Le Fil", scrape_le_fil),
    ("Zénith", scrape_zenith),
    ("Opéra Sainté", scrape_opera),
    ("Comédie Sainté", scrape_comedie),

    ("Le Solar", scrape_solar),
    ("Le Chambon-Feugerolles", scrape_chambon),
    ("La Comète", scrape_comete),
    ("Les Trois Ducs", scrape_trois_ducs),
    ("Chok Théâtre", scrape_chok),
    ("Théâtre Le Verso", scrape_verso),
    ("ArcomiK", scrape_arcomik),
    ("Comédie Triomphe", scrape_comedie_triomphe),
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
