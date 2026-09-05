from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from utils import PARIS, clean, stable_id

URL="https://opera.saint-etienne.fr/otse/agenda/"
HEADERS={"User-Agent":"Mozilla/5.0"}
MONTHS={"janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12}
GENRES={"lyrique":"Opéra","symphonique":"Musique","musique":"Musique","récitals":"Musique","recitals":"Musique","danse":"Danse","jeune public":"Jeune public"}

def _cat(t):
    t=clean(t).lower()
    for k,v in GENRES.items():
        if k in t:return v
    return "Spectacle"

def _year(month): return 2026 if month>=9 else 2027

def scrape_opera():
    r=requests.get(URL,headers=HEADERS,timeout=30); r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    events=[]; seen=set(); month=None
    for node in soup.find_all(["h2","h3","h4","tr"]):
        if node.name in {"h2","h3","h4"}:
            h=clean(node.get_text(" ")).lower()
            for n,m in MONTHS.items():
                if h==n or h.endswith(n): month=m; break
            continue
        if node.name!="tr" or month is None: continue
        cells=node.find_all(["td","th"])
        if len(cells)<3: continue
        txt=clean(node.get_text(" "))
        m=re.search(r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?(?:\s*\([^)]+\))?\s*(\d{1,2})\s+(\d{1,2}):(\d{2})",txt,re.I)
        if not m: continue
        day,hour,minute=map(int,m.groups())
        try: dt=datetime(_year(month),month,day,hour,minute,tzinfo=PARIS)
        except ValueError: continue
        venue=clean(cells[1].get_text(" "))
        title=clean(cells[2].get_text(" "))
        if not title: continue
        link=node.find("a",href=True)
        url=urljoin(URL,link["href"]) if link else URL
        start=dt.isoformat(); key=(title.lower(),start,venue.lower())
        if key in seen: continue
        seen.add(key)
        events.append({"id":stable_id("Opéra de Saint-Étienne",title,start),"title":title,"start":start,"venue":venue or "Opéra","city":"Saint-Étienne","category":_cat(txt),"description":"","url":url,"source":"Opéra de Saint-Étienne"})
    return events
