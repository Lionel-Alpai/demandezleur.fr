#!/usr/bin/env python3
"""Vérifie la cohérence des données du site. Sortie non nulle si un écart est trouvé."""
import json, sys
from pathlib import Path
from PIL import Image
R = Path(__file__).resolve().parent.parent
hugo = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))
back = json.loads((R / "backend/candidats.json").read_text(encoding="utf-8"))
familles = json.loads((R / "hugo-src/data/familles.json").read_text(encoding="utf-8"))
erreurs = []
if hugo != back: erreurs.append("candidats.json : hugo-src/data ≠ backend (lancer tools/resumes_generer.py --fusionner ou recopier)")
for c in hugo:
    cid = c["id"]
    if c.get("famille") not in familles: erreurs.append(f"{cid} : famille inconnue {c.get('famille')!r}")
    else:
        ton = R / "backend/prompts" / (familles[c["famille"]]["ton"] + ".txt")
        if not ton.exists(): erreurs.append(f"{cid} : ton absent {ton.name}")
    if not (R / "backend/corpus" / f"{cid}.json").exists(): erreurs.append(f"{cid} : corpus absent")
    photo = R / "hugo-src/static" / c.get("photo", "").lstrip("/")
    if not photo.exists(): erreurs.append(f"{cid} : photo absente {c.get('photo')}")
    else:
        w, h = Image.open(photo).size
        if w != h or w < 512: erreurs.append(f"{cid} : photo {w}x{h} (attendu carré ≥ 512)")
    if not c.get("questions_suggerees"): erreurs.append(f"{cid} : questions_suggerees manquantes")
    if c.get("photo_type") == "affiche": print(f"note : {cid} photo de type affiche, à remplacer")
faits = R / "backend/faits.json"
if faits.exists():
    f = json.loads(faits.read_text(encoding="utf-8")).get("candidats", {})
    for c in hugo:
        if c["id"] not in f: erreurs.append(f"{c['id']} : absent de faits.json")
print("\n".join(erreurs) if erreurs else f"cohérence OK ({len(hugo)} candidats)")
sys.exit(1 if erreurs else 0)
