#!/usr/bin/env python3
"""Vérifie l'IDENTITÉ des sources collectées (photos-sources/<id>/NN.jpg) contre la photo précédemment validée
(photos-originales/<id>.*) avec le juge SFace ; retient la source la plus récente dont la similarité ≥ seuil ;
écrit `choix` + `score` dans provenance.json ; planche des choix. Repli : l'ancienne photo si rien ne passe."""
import json, os, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent


def date_iso(s):
    """Date normalisée AAAA-MM-JJ (les dates Commons non ISO, ex. « Taken on 2 … », sont ignorées)."""
    import re as _re
    m = _re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s or "")); return m.group(0) if m else ""
J = Path("/home/lionel/trio/orchestre/tools/fabrique/juge_visage")
os.chdir(J); sys.path.insert(0, str(J))
import juge  # charge yunet/sface (chemins relatifs → chdir)
from PIL import Image, ImageDraw, ImageFont
SEUIL = float(os.environ.get("SEUIL_IDENTITE", "0.30"))
SRC = R / "hugo-src/photos-sources"; ORIG = R / "hugo-src/photos-originales"
cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))
choix = {}
for c in cands:
    cid = c["id"]; d = SRC / cid; prov = d / "provenance.json"
    if not prov.exists(): print(f"{cid:24} aucune source"); continue
    p = json.loads(prov.read_text(encoding="utf-8"))
    ref = next((x for x in ORIG.glob(cid + ".*") if x.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png")), None)
    eref = juge.embedding(str(ref)) if ref else None
    if eref is None: print(f"{cid:24} pas de référence exploitable → on garde 01"); p["choix"] = p["sources"][0]["fichier"] if p["sources"] else None; prov.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8"); choix[cid] = (p["choix"], None, p["sources"][0] if p["sources"] else {}); continue
    retenu = None
    p["sources"].sort(key=lambda x: date_iso(x.get("date")) or date_iso(x.get("date_upload")), reverse=True)
    for s in p["sources"]:  # triées par date normalisée décroissante
        e = juge.embedding(str(d / s["fichier"])); sc = float(juge.sim(e, eref)) if e is not None else -1.0
        s["score_identite"] = round(sc, 3)
        print(f"{cid:24} {s['fichier']} {s.get('date','')[:10]:10} score {sc:6.3f} {'✓' if sc >= SEUIL else '✗'}")
        if retenu is None and sc >= SEUIL: retenu = s
    if retenu is None:
        # repli : l'ancienne photo validée, recadrée carré
        im = Image.open(ref).convert("RGB"); w, h = im.size; k = min(w, h); im.crop(((w - k) // 2, 0, (w - k) // 2 + k, k)).resize((768, 768), Image.LANCZOS).save(d / "00_ancienne.jpg", quality=92)
        retenu = {"fichier": "00_ancienne.jpg", "date": "", "licence": "ancienne photo validée (chaîne dl-photo)", "titre": ref.name, "score_identite": 1.0}
        p["sources"].insert(0, retenu); print(f"{cid:24} → REPLI sur l'ancienne photo")
    p["choix"] = retenu["fichier"]; prov.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8"); choix[cid] = (retenu["fichier"], retenu.get("score_identite"), retenu)
# planche des choix
T = 240; cols = 6; ok = [c for c in cands if c["id"] in choix]; rows = (len(ok) + cols - 1) // cols
im = Image.new("RGB", (T * cols, (T + 44) * rows), "#0a1428"); dr = ImageDraw.Draw(im); f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
for i, c in enumerate(ok):
    fich, sc, s = choix[c["id"]]; x, y = (i % cols) * T, (i // cols) * (T + 44)
    im.paste(Image.open(SRC / c["id"] / fich).resize((T - 8, T - 8)), (x + 4, y + 4))
    dr.text((x + 8, y + T), f"{c['nom'][:20]} · {(s.get('date') or '')[:4] or 'anc.'}", font=f, fill="#f4f6fb"); dr.text((x + 8, y + T + 20), f"identité {sc if sc is not None else '-'}", font=f, fill="#3fa66b" if (sc or 0) >= 0.363 else "#f2a93b")
im.save(SRC / "planche_choix.jpg", quality=88); print("planche :", SRC / "planche_choix.jpg")
