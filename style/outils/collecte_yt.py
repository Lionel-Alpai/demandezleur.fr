#!/usr/bin/env python3
"""Collecte des verbatims ORAUX d'un candidat sur sa chaîne YouTube OFFICIELLE (sous-titres auto fr).

Usage : python3 collecte_yt.py <slug> <url-chaîne> [--max 25]
Sortie : style/verbatims/<slug>.yt.jsonl — une ligne par tronçon (~150 mots) :
  {texte, locuteur, situation, date, source, url, mots, voix_mixtes}
  situation : meeting | allocution | conference | interview | mixte (déduite du titre)
  voix_mixtes : true pour les interviews et formats à plusieurs voix (questions du journaliste dans le texte) — à pondérer à la baisse
Seules les vidéos de plus de 20 min sont prises, meetings / allocutions / conférences d'abord.
Cache des .vtt dans style/cache/yt/.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
YTDLP = str(RACINE / "venv" / "bin" / "yt-dlp")
CACHE = RACINE / "cache" / "yt"
SORTIE = RACINE / "verbatims"
ORDRE = ["meeting", "allocution", "conference", "interview", "mixte"]


MIXTE = (r"avec |with |coulisses|\bep\.? ?\d|épisode|round ?table|backseat|allo |quartier général|débat|"
         r"debate|show|interview|événement|guest|invité|vlog|behind the scenes|faces |face à|summit|matinale")


def situation(titre):
    t = titre.lower()
    if re.search(MIXTE, t):
        return "mixte"
    if re.search(r"meeting|rally|speech|discours|fête|conclusion|congrès|grand oral", t):
        return "meeting"
    if re.search(r"press conference|conférence de presse", t):
        return "conference"
    if re.search(r"interview| on [a-z]|sur [a-z]|débat|debate|événement", t):
        return "interview"
    return "allocution"


def videos(chaine, plafond=400):
    out = subprocess.run([YTDLP, "--flat-playlist", "--playlist-end", str(plafond), "--print",
                          "%(id)s\t%(duration)s\t%(title)s", f"{chaine}/videos"],
                         capture_output=True, text=True).stdout
    res = []
    for l in out.splitlines():
        vid, dur, titre = (l.split("\t") + ["", "", ""])[:3]
        try:
            if float(dur) > 1200:
                res.append((vid, titre))
        except ValueError:
            pass
    return res


def sous_titres(vid):
    vtt = CACHE / f"{vid}.fr-orig.vtt"
    meta = CACHE / f"{vid}.meta"
    if not vtt.exists() or not meta.exists():
        r = subprocess.run([YTDLP, "--skip-download", "--write-auto-subs", "--sub-langs", "fr-orig",
                            "--sub-format", "vtt", "--no-simulate", "--print", "%(upload_date)s\t%(channel)s",
                            "-o", str(CACHE / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, text=True)
        meta.write_text(r.stdout.strip().splitlines()[0] if r.stdout.strip() else "\t", encoding="utf-8")
    if not vtt.exists():
        return None, None, None
    date, chaine = (meta.read_text(encoding="utf-8").split("\t") + [""])[:2]
    vu, lignes = set(), []
    for l in vtt.read_text(encoding="utf-8").splitlines():
        if not l.strip() or "-->" in l or l.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        l = re.sub(r"<[^>]+>", "", l).strip()
        if l and l not in vu:  # les sous-titres auto répètent chaque ligne en défilant
            vu.add(l)
            lignes.append(l)
    date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else ""
    return " ".join(lignes), date, chaine


def troncons(texte, cible=150):
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    bloc, out = [], []
    for p in phrases:
        bloc.append(p)
        if sum(len(x.split()) for x in bloc) >= cible:
            out.append(" ".join(bloc))
            bloc = []
    if bloc:
        out.append(" ".join(bloc))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("chaine")
    ap.add_argument("--max", type=int, default=25)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    SORTIE.mkdir(parents=True, exist_ok=True)
    liste = sorted(videos(a.chaine), key=lambda v: ORDRE.index(situation(v[1])))[:a.max]
    lignes = []
    for vid, titre in liste:
        texte, date, chaine = sous_titres(vid)
        if not texte:
            print(f"  - {vid} sans sous-titres fr : {titre}")
            continue
        sit = situation(titre)
        for t in troncons(texte):
            lignes.append({"texte": t, "locuteur": a.slug, "situation": sit, "date": date,
                           "source": f"YouTube — chaîne {chaine} — « {titre} » (sous-titres automatiques)",
                           "url": f"https://www.youtube.com/watch?v={vid}", "mots": len(t.split()),
                           "voix_mixtes": sit in ("interview", "mixte")})
        print(f"  + {vid} {date} [{sit}] {len(texte.split())} mots : {titre[:70]}")
    f = SORTIE / f"{a.slug}.yt.jsonl"
    with f.open("w", encoding="utf-8") as o:
        for l in lignes:
            o.write(json.dumps(l, ensure_ascii=False) + "\n")
    par = {}
    for l in lignes:
        par[l["situation"]] = par.get(l["situation"], 0) + l["mots"]
    print(f"{a.slug} : {sum(par.values())} mots {par} → {f}")


if __name__ == "__main__":
    main()
