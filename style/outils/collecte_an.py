#!/usr/bin/env python3
"""Collecte des verbatims ORAUX d'un candidat à l'Assemblée (NosDéputés, législature 2017-2022).

Usage : python3 collecte_an.py <slug-nosdeputes> [<slug-nosdeputes> ...]
Sortie : style/verbatims/<slug>.an.jsonl — une ligne par prise de parole du candidat :
  {texte, locuteur, situation, date, source, url, contexte_avant, reaction, mots}
  situation : interruption (≤ 25 mots, sans parole donnée) | interpellation (hémicycle) | commission
  contexte_avant : la dernière prise de parole d'un AUTRE orateur (hors présidence), pour les duels
  reaction : didascalie qui suit immédiatement (Applaudissements, Exclamations…)
Cache HTML dans style/cache/an/ (rejouable sans réseau). Politesse : 1,2 s entre deux requêtes.
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://2017-2022.nosdeputes.fr"
RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / "cache" / "an"
SORTIE = RACINE / "verbatims"
MOIS = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                                     "août", "septembre", "octobre", "novembre", "décembre"], 1)}


def get(url, nom):
    f = CACHE / nom
    if f.exists():
        return f.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "demandezleur-style/1.0 (analyse interne)"})
    for essai in range(4):
        try:
            txt = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
            break
        except Exception as e:  # réseau capricieux : on réessaie, puis on abandonne la page
            print(f"  ! {url} : {e}", file=sys.stderr)
            time.sleep(5 * (essai + 1))
    else:
        return ""
    f.write_text(txt, encoding="utf-8")
    time.sleep(1.2)
    return txt


def propre(fragment):
    t = re.sub(r"</p>\s*<p>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[ \t ]+", " ", html.unescape(t)).strip()


def seances_du_depute(slug):
    ids, ratees = [], []
    premiere = get(f"{BASE}/{slug}/interventions?page=1", f"liste-{slug}-1.html")
    dernier = max([int(x) for x in re.findall(r"page=(\d+)", premiere)] or [1])
    for p in range(1, dernier + 1):
        txt = premiere if p == 1 else get(f"{BASE}/{slug}/interventions?page={p}", f"liste-{slug}-{p}.html")
        trouves = re.findall(r'href="/15/seance/(\d+)#inter_', txt)
        if not trouves:  # page en échec : on la note et on continue, le cache permet de la reprendre
            ratees.append(p)
        for s in trouves:
            if s not in ids:
                ids.append(s)
    if ratees:
        print(f"  ! {slug} : {len(ratees)} page(s) de liste en échec {ratees[:20]} — relancer pour compléter")
    return ids


def date_seance(titre):
    m = re.search(r"(\d{1,2})(?:er)? (\w+) (\d{4})", titre)
    if not m or m.group(2) not in MOIS:
        return ""
    return f"{m.group(3)}-{MOIS[m.group(2)]:02d}-{int(m.group(1)):02d}"


def blocs(txt):
    """Suite ordonnée de ('parole', slug|None, nom, texte, ancre) et ('didascalie', texte)."""
    out = []
    for m in re.finditer(r'<div class="(intervention|didascalie)"([^>]*)>(.*?)'
                         r'(?=<div class="(?:intervention|didascalie)"|<div id="footer"|\Z)', txt, re.S):
        genre, attrs, corps = m.groups()
        ancre = (re.search(r'id="(inter_[0-9a-f]+)"', attrs) or [None, None])[1]
        if genre == "didascalie":
            out.append(("didascalie", propre(corps)))
            continue
        perso = re.search(r'<div class="perso">(.*?)</div>', corps, re.S)
        texte = re.search(r'<div class="texte_intervention">(.*?)</div>', corps, re.S)
        if not perso or not texte:
            continue
        lien = re.search(r'href="/([a-z0-9-]+)"', perso.group(1))
        out.append(("parole", lien.group(1) if lien else None, propre(perso.group(1)), propre(texte.group(1)), ancre))
    return out


def collecte(slug):
    SORTIE.mkdir(parents=True, exist_ok=True)
    seances = seances_du_depute(slug)
    print(f"{slug} : {len(seances)} séances")
    lignes = []
    for i, sid in enumerate(seances, 1):
        txt = get(f"{BASE}/15/seance/{sid}", f"seance-{sid}.html")
        titre = (re.search(r"<title>([^<]*)", txt) or [None, ""])[1]
        situation_base = "commission" if "ommission" in titre else "interpellation"
        b = blocs(txt)
        dernier_autre = ""
        for k, x in enumerate(b):
            if x[0] != "parole":
                continue
            _, qui, nom, texte, ancre = x
            if qui != slug:
                if not re.search(r"\bprésident(e)?\b", nom) and len(texte.split()) > 3:
                    dernier_autre = f"{nom} : {texte}"
                continue
            mots = len(texte.split())
            precedent = b[k - 1] if k else None
            parole_donnee = bool(precedent and precedent[0] == "parole" and "parole est à" in precedent[3])
            situation = "interruption" if mots <= 25 and not parole_donnee else situation_base
            suivant = b[k + 1] if k + 1 < len(b) else None
            lignes.append({
                "texte": texte, "locuteur": slug, "situation": situation, "date": date_seance(titre),
                "source": f"Assemblée nationale (NosDéputés) — {titre.replace(' - NosDéputés.fr', '').strip()}",
                "url": f"{BASE}/15/seance/{sid}#{ancre}" if ancre else f"{BASE}/15/seance/{sid}",
                "contexte_avant": dernier_autre[:600],
                "reaction": suivant[1] if suivant and suivant[0] == "didascalie" else "",
                "mots": mots,
            })
        if i % 25 == 0:
            print(f"  {i}/{len(seances)} séances, {len(lignes)} prises de parole")
    f = SORTIE / f"{slug}.an.jsonl"
    with f.open("w", encoding="utf-8") as o:
        for l in lignes:
            o.write(json.dumps(l, ensure_ascii=False) + "\n")
    total = sum(l["mots"] for l in lignes)
    par = {}
    for l in lignes:
        par[l["situation"]] = par.get(l["situation"], 0) + l["mots"]
    print(f"{slug} : {len(lignes)} prises de parole, {total} mots {par} → {f}")


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    for s in sys.argv[1:]:
        collecte(s)
