# Utilisation d'Infoconcert

`infoconcert.py` est un scraper générique pour les pages "salle" d'Infoconcert.

Exemple :

```python
from infoconcert import scrape_infoconcert_venue

events = scrape_infoconcert_venue(
    url="https://www.infoconcert.com/salle/le-fil-a-saint-etienne-21927/concerts",
    venue="Le Fil",
    city="Saint-Étienne",
    category="Musique",
)
```

Pour ajouter une autre salle présente sur Infoconcert, il suffit donc de réutiliser la même fonction avec une autre URL.

Le scraper récupère :
- titre
- date
- heure quand elle est indiquée
- salle
- ville
- lien vers l'événement
