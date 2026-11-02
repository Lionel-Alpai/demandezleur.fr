#!/usr/bin/env python3
"""fraicheur_hugo.py — extrait de backend/corpus/bilan.json la fraîcheur par candidat vers
hugo-src/data/fraicheur.json (lu au build par le partial fraicheur-corpus.html).
Brique dl-fiche-mention-programme-2022. Déterministe, zéro LLM. Relancer après tools/bilan_corpus.py."""
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
bilan = json.loads((RACINE / "backend/corpus/bilan.json").read_text())
sortie = {}
for c in bilan["candidats"]:
    f = c.get("fraicheur") or {}
    sortie[c["id"]] = {"p2027": round(f.get("part_2026_2027", 0.0)),
                       "p2022": round(f.get("part_2022_et_avant", 0.0)),
                       "genere_le": bilan["_meta"]["genere_le"]}
cible = RACINE / "hugo-src/data/fraicheur.json"
cible.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n")
print("FRAICHEUR_HUGO_OK", len(sortie), cible)
