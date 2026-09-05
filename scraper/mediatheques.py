from __future__ import annotations

from datetime import timezone

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from utils import clean, parse_french_event_date, stable_id


RSS_URL = "https://mediatheques.saint-etienne.fr/Portal/Recherche/Search.svc/SearchRss?key=23d8f3adc8036a025835ea59faeef58b&useSearchResultSize=true&useSearchSort=false"


def scrape_mediatheques() -> list[dict]:
    source_name = "Médiathèques de Saint-Étienne"
    feed = feedparser.parse(RSS_URL)
    events = []

    for item in feed.entries:
        title = clean(item.get("title"))
        link = item.get("link") or RSS_URL

        summary_html = item.get("summary", "")
        summary = clean(BeautifulSoup(summary_html, "html.parser").get_text(" "))

        # La vraie date est dans la description du RSS.
        dt = parse_french_event_date(summary)

        # Repli si nécessaire.
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
            "id": stable_id(source_name, title, start),
            "title": title,
            "start": start,
            "venue": "Médiathèques Sainté",
            "city": "Saint-Étienne",
            "category": "Littérature",
            "description": summary[:500],
            "url": link,
            "source": source_name
        })

    return events
