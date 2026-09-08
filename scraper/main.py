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

from cinema import scrape_cinema


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "events.json"
CINEMA_OUT = ROOT / "cinema_events.json"

SCRAPERS = [
    ("Médiathèques Sainté", scrape_mediatheques),
    ("Le Fil", scrape_le_fil),
    ("Zénith Sainté", scrape_zenith),
    ("Opéra Sainté", scrape_opera),
    ("Comédie Sainté", scrape_comedie),

    ("Le Solar", scrape_solar),
    ("Salles Chambon-Feugerolles", scrape_chambon),
    ("La Comète", scrape_comete),
    ("Les 3 Ducs", scrape_trois_ducs),
    ("Chok Théâtre", scrape_chok),
    ("Théâtre Le Verso", scrape_verso),
    ("ArcomiK", scrape_arcomik),
    ("Comédie Triomphe", scrape_comedie_triomphe),
]


def collect_cultural_events():
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
        print("Aucun événement culturel collecté : events.json conservé.")
        return

    OUT.write_text(
        json.dumps(all_events, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"{len(all_events)} événements écrits dans {OUT}")


def collect_cinema_events():
    try:
        cinema_events = scrape_cinema()
    except Exception as exc:
        print(f"ERREUR CINÉMA: {exc}")
        return

    # On évite d'écraser un fichier valide si toutes les sources ciné
    # échouent temporairement.
    if not cinema_events:
        print("Aucune séance cinéma collectée : cinema_events.json conservé.")
        return

    CINEMA_OUT.write_text(
        json.dumps(cinema_events, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(
        f"{len(cinema_events)} séances cinéma écrites "
        f"dans {CINEMA_OUT}"
    )


def main():
    collect_cultural_events()
    collect_cinema_events()


if __name__ == "__main__":
    main()
