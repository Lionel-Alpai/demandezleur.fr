#!/usr/bin/env python3
"""Portraits illustrés « plateau » des candidats via OpenAI gpt-image-1 (édition avec préservation d'identité),
à partir de la source retenue (photos-sources/<id>/provenance.json → choix). Sortie : hugo-src/portraits/<id>[_vN].png + planche.
Usage : venv/bin/python tools/portraits_generer.py [--ids a,b] [--variantes 1] [--qualite medium]"""
import argparse, base64, io, json
from pathlib import Path
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent.parent
SRC = R / "hugo-src/photos-sources"; OUT = R / "hugo-src/portraits"; OUT.mkdir(exist_ok=True)
STYLE = ("Turn this photo into a bold graphic poster portrait for a televised political debate set, two-tone screen-print / risograph style. "
         "Face, hair and clothes rendered ONLY in navy blue (#0a1428) and off-white (#f4f6fb) halftone dots and ink; the ONLY red (#e53946) is a single flat rim light on one side of the face and shoulder — no red in the hair, no red background. "
         "Plain uniform dark navy background, crisp high contrast, studio spotlight feel. "
         "PRESERVE THE EXACT IDENTITY of the person: same face, same facial proportions, same hair, same glasses, same age, same expression — a viewer must recognize them instantly. Realistic proportions, dignified, not a caricature. "
         "Head and shoulders, centered, square framing with generous margin, no text, no logo.")

# PORTRAIT_AUTO_SOURCE_EXPLICITE (brique dl-fiche-portrait-plateau-auto, 31/08/2026) :
# src/out_dir explicites pour la chaîne dl-fiche (worktree) ; sans eux, comportement dépôt inchangé.
def generer(cl, cid, k, qualite, src=None, out_dir=None):
    if src is None:
        p = json.loads((SRC / cid / "provenance.json").read_text(encoding="utf-8")); src = SRC / cid / p["choix"]
    im = Image.open(src).convert("RGB"); im.thumbnail((1024, 1024)); buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0); buf.name = "src.png"
    r = cl.images.edit(model="gpt-image-1", image=buf, prompt=STYLE, size="1024x1024", quality=qualite)
    out = (out_dir or OUT) / (f"{cid}.png" if k == 0 else f"{cid}_v{k+1}.png"); out.write_bytes(base64.b64decode(r.data[0].b64_json)); return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", default=""); ap.add_argument("--variantes", type=int, default=1); ap.add_argument("--qualite", default="medium"); a = ap.parse_args()
    cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8")); voulus = set(a.ids.split(",")) if a.ids else None
    cl = OpenAI(); faits = []
    for c in cands:
        if voulus and c["id"] not in voulus: continue
        for k in range(a.variantes):
            try: out = generer(cl, c["id"], k, a.qualite); faits.append(c); print("ok", out.name, flush=True)
            except Exception as e: print("KO", c["id"], str(e)[:120], flush=True)
    T = 240; cols = 6; ok = [c for c in cands if (OUT / f"{c['id']}.png").exists()]; rows = (len(ok) + cols - 1) // cols
    im = Image.new("RGB", (T * cols, (T + 30) * rows), "#0a1428"); dr = ImageDraw.Draw(im); f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    for i, c in enumerate(ok):
        x, y = (i % cols) * T, (i // cols) * (T + 30); im.paste(Image.open(OUT / f"{c['id']}.png").convert("RGB").resize((T - 8, T - 8)), (x + 4, y + 4)); dr.text((x + 8, y + T), c["nom"][:24], font=f, fill="#f4f6fb")
    im.save(OUT / "planche.jpg", quality=88); print("planche :", OUT / "planche.jpg")
