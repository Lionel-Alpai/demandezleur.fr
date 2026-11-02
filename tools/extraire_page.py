#!/usr/bin/env python3
"""extraire.py <url> <sortie.txt> — texte principal d'une page (article/main/entry-content), + date publiée si trouvée."""
import sys,re,subprocess
from bs4 import BeautifulSoup
url,out=sys.argv[1],sys.argv[2]
html=subprocess.run(["curl","-sL","-m","30","-A","Mozilla/5.0",url],capture_output=True).stdout.decode("utf-8","replace")
s=BeautifulSoup(html,"html.parser")
date=None
for m in s.find_all("meta"):
    if m.get("property") in ("article:published_time","article:modified_time") or m.get("name") in ("date","pubdate"):
        date=date or m.get("content")
t=s.find("time")
if not date and t: date=t.get("datetime") or t.get_text(strip=True)
for x in s(["script","style","nav","header","footer","aside","form","noscript"]): x.decompose()
node=s.select_one(".entry-content") or s.find("article") or s.find("main") or s.body
paras=[]
for el in node.find_all(["h1","h2","h3","h4","p","li"]):
    tx=re.sub(r"\s+"," ",el.get_text(" ",strip=True))
    if len(tx)>2 and (not paras or paras[-1]!=tx): paras.append(tx)
titre=(s.title.get_text(strip=True) if s.title else "")
open(out,"w").write(f"URL: {url}\nTITRE: {titre}\nDATE: {date}\n\n"+"\n".join(paras))
print(out, len("\n".join(paras)),"car", "date",date)
