from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from utils import PARIS, clean, stable_id

BASE="https://www.lacomedie.fr"
LIST="https://www.lacomedie.fr/la-saison-menu/tous-les-spectacles"
HEADERS={"User-Agent":"Mozilla/5.0"}
MONTHS={"janv":1,"janvier":1,"févr":2,"fevr":2,"février":2,"fevrier":2,"mars":3,"avr":4,"avril":4,"mai":5,"juin":6,"juil":7,"juillet":7,"août":8,"aout":8,"sept":9,"septembre":9,"oct":10,"octobre":10,"nov":11,"novembre":11,"déc":12,"dec":12,"décembre":12,"decembre":12}
DAY=r"(?:lun|mar|mer|jeu|ven|sam|dim)\.?"
MON=r"(janv(?:ier)?|févr(?:ier)?|fevr(?:ier)?|mars|avr(?:il)?|mai|juin|juil(?:let)?|août|aout|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|déc(?:embre)?|dec(?:embre)?)\.?"

def _month(s): return MONTHS[s.lower().rstrip(".")]

def _urls():
    found=[]; seen=set()
    for page in range(1,30):
        url=LIST if page==1 else f"{LIST}?page={page}"
        r=requests.get(url,headers=HEADERS,timeout=30); r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        new=[]
        for a in soup.find_all("a",href=True):
            if "/programmation/" not in a["href"]: continue
            u=urljoin(BASE,a["href"])
            if u not in seen:
                seen.add(u); new.append(u); found.append(u)
        print(f"La Comédie page {page}: {len(new)} nouvelle(s) fiche(s)")
        if not new: break
    return found

def _venue(text):
    m=re.search(r"\bLieu\s+(.+?)\s+(?:Public|Générique|Generique|Dates|Médias|Medias)\b",text,re.I)
    if not m:return "La Comédie"
    return clean(m.group(1)).replace("Salle ","",1)

def _dates(text,year):
    p=text
    pos=re.search(r"\bDates\b",p,re.I)
    if pos:p=p[pos.end():]
    stop=re.search(r"\b(?:Médias|Medias|Presse|Autour du spectacle|À découvrir aussi|A découvrir aussi)\b",p,re.I)
    if stop:p=p[:stop.start()]
    rgx=re.compile(rf"{DAY}\s+(\d{{1,2}})\s+{MON}\s+(\d{{1,2}})h(?:\s*(\d{{2}}))?",re.I)
    out=[]
    for m in rgx.finditer(p):
        day=int(m.group(1)); month=_month(m.group(2)); hour=int(m.group(3)); minute=int(m.group(4) or 0)
        try: out.append(datetime(year,month,day,hour,minute,tzinfo=PARIS))
        except ValueError: pass
    return out

def scrape_comedie():
    events=[]; seen=set(); now=datetime.now(PARIS)
    for u in _urls():
        try:
            r=requests.get(u,headers=HEADERS,timeout=30); r.raise_for_status()
        except Exception as e:
            print("La Comédie erreur",u,e); continue
        soup=BeautifulSoup(r.text,"html.parser")
        h1=soup.find("h1"); title=clean(h1.get_text(" ")) if h1 else ""
        if not title: continue
        text=clean(soup.get_text(" "))
        years=re.findall(r"\b(20\d{2})\b",text)
        if not years: continue
        year=int(years[0]); venue=_venue(text)
        for dt in _dates(text,year):
            if dt<now: continue
            start=dt.isoformat(); key=(title.lower(),start,venue.lower())
            if key in seen: continue
            seen.add(key)
            events.append({"id":stable_id("La Comédie de Saint-Étienne",title,start),"title":title,"start":start,"venue":venue,"city":"Saint-Étienne","category":"Théâtre","description":"","url":u,"source":"La Comédie de Saint-Étienne"})
    return events
