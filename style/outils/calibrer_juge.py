#!/usr/bin/env python3
"""Plafond de l'instrument : le juge d'attribution reconnaît-il les VRAIS pilotes sur leurs vrais
verbatims (interpellations de 30 à 120 mots, masqués comme au banc) ? Si non, le seuil de 75 %
du banc est hors de portée quel que soit la fiche."""
import asyncio, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc_attribution as b  # noqa: E402

async def main(n=20):
    random.seed(31)
    noms = {i: b.charger_candidat(i)["nom"] for i in b.PILOTES + b.LEURRES}
    fiches = {i: b.fiche_prompt.charger_fiche(i) for i in b.PILOTES}
    lignes = []
    for p in b.PILOTES:
        rows = [json.loads(l) for f in sorted((b.STYLE / "verbatims").glob(f"{p}.*.jsonl")) for l in open(f, encoding="utf-8")]
        rows = [r for r in rows if r["situation"] in ("interpellation", "commission") and 30 <= len(r["texte"].split()) <= 120]
        lignes += [{"orateur": p, "avec_fiche": None, "sujet": "réel", "tour": 0, "texte": r["texte"]} for r in random.sample(rows, n)]
    lignes = await asyncio.gather(*[b.juger(l, noms, fiches) for l in lignes])
    for p in b.PILOTES:
        s = [l for l in lignes if l["orateur"] == p]
        print(p, f"{100 * sum(l['juste'] for l in s) / len(s):.0f} %", {k: sum(l["attribue"] == k for l in s) for k in b.PILOTES + b.LEURRES})
    print(f"PLAFOND {100 * sum(l['juste'] for l in lignes) / len(lignes):.0f} %")

asyncio.run(main())
