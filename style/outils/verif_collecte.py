#!/usr/bin/env python3
"""Juge d'effet de dl-style-collecte-verbatims-oraux — mécanique, rejouable.

Usage : python3 verif_collecte.py <slug> [<slug> ...]
Lit style/verbatims/<slug>.*.jsonl. Les lignes voix_mixtes ne comptent pas dans les mots.
Critères : ≥ 30 000 mots ; ≥ 3 situations dont interpellation ou interruption ; 100 % des
lignes sourcées (source + url) et datées ; ≥ 40 % des mots postérieurs au 31/12/2022.
Sortie : une ligne VERDICT par candidat, code retour 1 si un critère échoue.
"""
import json
import sys
from pathlib import Path

VERBATIMS = Path(__file__).resolve().parent.parent / "verbatims"


def juger(slug):
    lignes = []
    for f in sorted(VERBATIMS.glob(f"{slug}.*.jsonl")):
        lignes += [json.loads(l) for l in f.open(encoding="utf-8") if l.strip()]
    propres = [l for l in lignes if not l.get("voix_mixtes")]
    mots = sum(l["mots"] for l in propres)
    situations = {}
    for l in propres:
        situations[l["situation"]] = situations.get(l["situation"], 0) + l["mots"]
    sources = sum(1 for l in lignes if l.get("source") and l.get("url") and l.get("date"))
    recents = sum(l["mots"] for l in propres if l.get("date", "") > "2022-12-31")
    crit = {
        "mots>=30000": mots >= 30000,
        "situations>=3": len(situations) >= 3,
        "duel_ou_interpellation": bool({"interpellation", "interruption"} & set(situations)),
        "100%_sourcees_datees": bool(lignes) and sources == len(lignes),
        "recent>=40%": mots > 0 and recents / mots >= 0.40,
    }
    ok = all(crit.values())
    print(f"VERDICT {slug} {'OK' if ok else 'ECHEC'} — {mots} mots, {len(lignes)} lignes, "
          f"situations {situations}, sourcées {sources}/{len(lignes)}, récents {recents / max(mots, 1):.0%}")
    for k, v in crit.items():
        if not v:
            print(f"   ✗ {k}")
    return ok


if __name__ == "__main__":
    resultats = [juger(s) for s in sys.argv[1:]]
    sys.exit(0 if resultats and all(resultats) else 1)
