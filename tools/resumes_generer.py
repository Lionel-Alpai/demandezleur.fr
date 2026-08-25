#!/usr/bin/env python3
"""Génère un BROUILLON de `resume` (2-3 phrases) et `questions_suggerees` (4) par candidat,
à partir de son corpus, via le modèle. Écrit hugo-src/data/candidats.brouillon.json.
Avec --fusionner, recopie resume/questions_suggerees dans candidats.json (statut brouillon,
à relire par Lionel) et dans backend/candidats.json.
Usage : DL_MODE=live venv/bin/python tools/resumes_generer.py [--ids a,b] [--fusionner]
"""
import argparse, asyncio, json, sys
from pathlib import Path
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "backend"))
import llm  # noqa: E402

DATA = RACINE / "hugo-src" / "data" / "candidats.json"
BROUILLON = RACINE / "hugo-src" / "data" / "candidats.brouillon.json"
MIROIR = RACINE / "backend" / "candidats.json"
CORPUS = RACINE / "backend" / "corpus"

PROMPT = """Tu es documentaliste pour un site citoyen neutre. À partir des extraits du programme officiel de {nom} ({parti}) ci-dessous, produis un JSON strict :
{{"resume": "...", "questions_suggerees": ["...", "...", "...", "..."]}}
- resume : 2 à 3 phrases, ton neutre et factuel, au présent, sans adjectif évaluatif, qui disent ce que propose ce programme (thèmes principaux). Ne pas parler de la personne, seulement du programme. Commence par « Son programme ».
- questions_suggerees : 4 questions courtes (≤ 70 caractères), à la deuxième personne du pluriel, qu'un électeur poserait au candidat, chacune sur un thème réellement couvert par les extraits. Pas de question piège.
Réponds uniquement par le JSON.

EXTRAITS :
{extraits}"""


async def un(c):
    corpus = json.loads((CORPUS / f"{c['id']}.json").read_text(encoding="utf-8")) if (CORPUS / f"{c['id']}.json").exists() else []
    if not corpus:
        return None
    extraits = "\n\n".join(f"[{b.get('theme','')}] {b.get('text','')[:700]}" for b in corpus[:14])
    txt = await llm.completer_texte([{"role": "user", "content": PROMPT.format(nom=c["nom"], parti=c["parti"], extraits=extraits)}],
                                    cle_demo=("resume", c["id"]), max_tokens=500, temperature=0.3,
                                    extra={"response_format": {"type": "json_object"}})
    try:
        d = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        return {"resume": d.get("resume", "").strip(), "questions_suggerees": [q.strip() for q in d.get("questions_suggerees", [])][:5]}
    except Exception as e:
        print("  JSON illisible pour", c["id"], e); return None


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", default=""); ap.add_argument("--fusionner", action="store_true")
    a = ap.parse_args()
    cands = json.loads(DATA.read_text(encoding="utf-8"))
    voulus = set(a.ids.split(",")) if a.ids else None
    brouillon = json.loads(BROUILLON.read_text(encoding="utf-8")) if BROUILLON.exists() else {}
    for c in cands:
        if voulus and c["id"] not in voulus: continue
        if c["id"] in brouillon and not voulus: print("déjà :", c["id"]); continue
        print("génère :", c["id"]); r = await un(c)
        if r: brouillon[c["id"]] = r
        BROUILLON.write_text(json.dumps(brouillon, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.fusionner:
        for c in cands:
            b = brouillon.get(c["id"])
            if b:
                c["resume"], c["questions_suggerees"], c["resume_statut"] = b["resume"], b["questions_suggerees"], "brouillon"
        DATA.write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
        MIROIR.write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
        print("fusionné dans candidats.json (statut brouillon) + miroir backend")

asyncio.run(main())
