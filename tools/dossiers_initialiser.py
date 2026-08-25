#!/usr/bin/env python3
"""Équité : crée (sans écraser) un dossier faits par candidat et une flèche par paire de familles, vides et datés."""
import json, itertools
from datetime import date
from pathlib import Path
R = Path(__file__).resolve().parent.parent
cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))
familles = json.loads((R / "hugo-src/data/familles.json").read_text(encoding="utf-8"))
F, RP = R / "backend/dossiers/faits", R / "backend/dossiers/rapports"; F.mkdir(parents=True, exist_ok=True); RP.mkdir(parents=True, exist_ok=True)
n = 0
for c in cands:
    p = F / f"{c['id']}.json"
    if not p.exists(): p.write_text(json.dumps({"candidat_id": c["id"], "maj": date.today().isoformat(), "entrees": []}, ensure_ascii=False, indent=1), encoding="utf-8"); n += 1
for a, b in itertools.permutations(familles, 2):
    p = RP / f"{a}__{b}.json"
    if not p.exists(): p.write_text(json.dumps({"de": a, "vers": b, "registre": "neutre", "maj": date.today().isoformat(), "griefs": []}, ensure_ascii=False, indent=1), encoding="utf-8"); n += 1
print(f"{n} dossiers créés — {len(list(F.glob('*.json')))} faits, {len(list(RP.glob('*.json')))} flèches")
