# Scrapers

Un fichier Python par source.

## Actifs

- `mediatheques.py` : Médiathèques de Saint-Étienne
- `le_fil.py` : Le Fil

## Fichiers communs

- `utils.py` : fonctions partagées
- `main.py` : lance tous les scrapers et génère `events.json`

## Ajouter une salle

1. Créer par exemple `comedie.py`
2. Ajouter une fonction `scrape_comedie()`
3. Importer cette fonction dans `main.py`
4. L'ajouter dans la liste `SCRAPERS`

Exemple :

```python
from comedie import scrape_comedie

SCRAPERS = [
    ("Médiathèques de Saint-Étienne", scrape_mediatheques),
    ("Le Fil", scrape_le_fil),
    ("La Comédie", scrape_comedie),
]
```
