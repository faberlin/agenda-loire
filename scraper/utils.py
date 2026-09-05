from __future__ import annotations

import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def stable_id(source: str, title: str, start: str) -> str:
    raw = f"{source}|{title}|{start}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_french_event_date(text: str) -> datetime | None:
    """
    Extrait des dates du type :
    - Du 15/09/2026 10:00 au 17/10/2026 18:30
    - Le 09/10/2026 19:30
    - 09/10/2026 19:30
    """
    text = clean(text)

    patterns = [
        r"\bDu\s+(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
        r"\bLe\s+(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        day, month, year = map(int, match.group(1, 2, 3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0

        try:
            return datetime(year, month, day, hour, minute, tzinfo=PARIS)
        except ValueError:
            continue

    return None


def dedupe(events: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for ev in sorted(events, key=lambda x: x["start"]):
        key = (
            ev["title"].lower(),
            ev["start"][:10],
            ev.get("city", "").lower()
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(ev)

    return result
