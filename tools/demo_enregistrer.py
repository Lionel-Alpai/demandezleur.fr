#!/usr/bin/env python3
"""Enregistre les fixtures du MODE DÉMO en interrogeant une instance backend lancée en DL_MODE=record.

  1. lance :  cd backend && DL_MODE=record ADMIN_BYPASS_TOKEN=xyz uvicorn api:app --port 8002
  2. puis  :  python tools/demo_enregistrer.py --port 8002 --jeton xyz

Pour chaque candidat : ses questions_suggerees via /api/ask (llm.py écrit demo/<hash>.json).
Écrit aussi hugo-src/data/demo_accueil.json (question, réponse, preuves) pour la démo de l'accueil,
et 2 débats types (standard + arène) sur des paires fixes.
"""
import argparse, asyncio, json, sys
from pathlib import Path
import httpx
R = Path(__file__).resolve().parent.parent
DATA = R / "hugo-src/data/candidats.json"
ACCUEIL = R / "hugo-src/static/data/demo_accueil.json"  # servi tel quel, lu par accueil.js
DEBATS = [(["marine-le-pen", "gabriel-attal"], "la sécurité du quotidien", "arene"),
          (["delphine-batho", "bruno-retailleau"], "le nucléaire", "standard"),
          (["jean-luc-melenchon", "edouard-philippe", "nathalie-arthaud"], "les retraites", "arene")]


async def ask(cl, base, jeton, cid, q):
    texte, preuves = "", []
    async with cl.stream("POST", f"{base}/api/ask", json={"candidat_id": cid, "question": q, "history": []},
                         headers={"X-Admin-Token": jeton, "X-DL-Client": "plateau"}, timeout=120) as r:
        if r.status_code != 200:
            print("  HTTP", r.status_code, cid, q[:40]); return None
        async for ligne in r.aiter_lines():
            if not ligne.startswith("data: "): continue
            d = json.loads(ligne[6:])
            if d["type"] == "preuves": preuves = d["preuves"]
            elif d["type"] == "token": texte += d["text"]
    return {"candidat_id": cid, "question": q, "reponse": texte, "preuves": preuves}


async def debat(cl, base, jeton, cands, sujet, mode):
    async with cl.stream("POST", f"{base}/api/debat/stream", headers={"X-Admin-Token": jeton, "X-DL-Client": "plateau"}, timeout=300,
                         json={"candidats": cands, "sujet": sujet, "tour": 1, "type_tour": "ouverture", "historique": [], "mode": mode}) as r:
        n = 0
        async for ligne in r.aiter_lines():
            if '"speaker_end"' in ligne: n += 1
        print(f"  débat {mode} {cands} : {n} prises de parole")


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8002); ap.add_argument("--jeton", required=True)
    ap.add_argument("--parallele", type=int, default=4); ap.add_argument("--sans-debats", action="store_true"); a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    cands = json.loads(DATA.read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(a.parallele)
    async with httpx.AsyncClient() as cl:
        async def borne(cid, q):
            async with sem:
                r = await ask(cl, base, a.jeton, cid, q)
                if r: print("  ok", cid, "|", q[:50])
                return r
        taches = [borne(c["id"], q) for c in cands for q in (c.get("questions_suggerees") or [])[:4]]
        print(f"{len(taches)} questions à enregistrer…")
        res = [r for r in await asyncio.gather(*taches) if r]
        # Démo d'accueil : 5 Q/R variées (familles différentes), réponses de 300-900 caractères, avec preuves
        vus, accueil = set(), []
        par_id = {c["id"]: c for c in cands}
        for r in sorted(res, key=lambda x: -len(x["preuves"])):
            fam = par_id[r["candidat_id"]]["famille"]
            if fam in vus or not (300 <= len(r["reponse"]) <= 1300) or not r["preuves"]: continue
            vus.add(fam); accueil.append({**r, "nom": par_id[r["candidat_id"]]["nom"], "parti": par_id[r["candidat_id"]]["parti_court"]})
            if len(accueil) == 5: break
        ACCUEIL.write_text(json.dumps(accueil, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"demo_accueil.json : {len(accueil)} séquences")
        for cands_, sujet, mode in ([] if a.sans_debats else DEBATS):
            await debat(cl, base, a.jeton, cands_, sujet, mode)

asyncio.run(main())
