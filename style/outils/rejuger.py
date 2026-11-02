#!/usr/bin/env python3
"""Rejuge les répliques d'un rapport du banc avec le juge courant (DL_MODELE_JUGE), sans régénérer."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc_attribution as b  # noqa: E402

async def main(chemin):
    d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    noms = {i: b.charger_candidat(i)["nom"] for i in b.PILOTES + b.LEURRES}
    fiches = {i: b.fiche_prompt.charger_fiche(i) for i in b.PILOTES}
    lignes = await asyncio.gather(*[b.juger(dict(l), noms, fiches) for l in d["repliques"]])
    for cond in (False, True):
        for p in b.PILOTES:
            s = [l for l in lignes if l["avec_fiche"] is cond and l["orateur"] == p]
            print("AVEC" if cond else "SANS", p, f"{100 * sum(l['juste'] for l in s) / len(s):.0f} %")
        s = [l for l in lignes if l["avec_fiche"] is cond]
        print("AVEC" if cond else "SANS", "TOTAL", f"{100 * sum(l['juste'] for l in s) / len(s):.0f} %")
    sortie = Path(chemin).with_name(Path(chemin).stem + f"-rejuge-{b.llm.MODELE_JUGE}.json")
    sortie.write_text(json.dumps({"juge": b.llm.MODELE_JUGE, "repliques": lignes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", sortie)

asyncio.run(main(sys.argv[1]))
