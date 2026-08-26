#!/usr/bin/env python3
"""Portraits d'essai — 2 styles illustrés × 3 candidats, via FLUX.2 Pro EDIT (FAL) à partir de la photo originale.
Sortie : hugo-src/photos-originales/essais/<style>_<id>.png + planche-contact essais/planche.png
Usage : /home/lionel/tools/flux2/venv/bin/python tools/portraits_essai.py [--ids a,b,c] [--styles jours,plateau]"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
import fal_client
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent.parent
SRC = R / "hugo-src/photos-originales"; OUT = SRC / "essais"; OUT.mkdir(exist_ok=True)
os.environ.setdefault("FAL_KEY", subprocess.run(["pass", "show", "api/fal_ai"], capture_output=True, text=True).stdout.strip().splitlines()[0])
NOMS = {"marine-le-pen": "Marine Le Pen", "jean-luc-melenchon": "Jean-Luc Mélenchon", "edouard-philippe": "Édouard Philippe"}
STYLES = {
 "jours": {"scene": "Use the reference photo. Recreate the EXACT same person — SAME face, SAME identity, SAME facial proportions, SAME hair, SAME glasses if any, SAME expression — as an editorial illustrated portrait for a French news website. Plain uniform dark navy background (#0a1428). Head-and-shoulders, centered, looking at the viewer, neutral dignified expression. Nothing else in the frame. No text.",
           "style": "hand-drawn editorial illustration in the manner of French press portraits: confident black ink linework, limited flat color palette (warm skin, navy, one red accent on the clothing), subtle cross-hatching in shadows, paper texture. Realistic proportions, NOT a caricature, NOT exaggerated features, respectful and neutral.",
           "color_palette": ["#0a1428", "#f4f6fb", "#e53946", "#c9a27a"], "lighting": "soft frontal studio light", "mood": "serious, composed, neutral"},
 "plateau": {"scene": "Use the reference photo. Recreate the EXACT same person — SAME face, SAME identity, SAME facial proportions, SAME hair, SAME glasses if any — as a bold graphic poster portrait for a televised political debate set. Plain uniform dark navy background (#0a1428). Head-and-shoulders, centered, three-quarter view looking at the viewer. Nothing else in the frame. No text.",
             "style": "two-tone screen-print / risograph poster style: navy blue and off-white halftone dots for the face, a single flat red accent light on one side of the face, crisp high contrast, cinematic studio spotlight feel. Realistic proportions, NOT a caricature, respectful and neutral.",
             "color_palette": ["#0a1428", "#f4f6fb", "#e53946"], "lighting": "dramatic single spotlight from upper left, rim light", "mood": "televised debate, intense, dignified"},
}

def generer(cid, style, seed=42):
    src = next(p for p in SRC.glob(f"{cid}.*") if p.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png"))
    st = STYLES[style]
    prompt = {"scene": st["scene"], "subjects": [{"type": "person", "description": "the person in the reference photo, identical face", "pose": "head and shoulders portrait, facing the viewer", "position": "center"}],
              "style": st["style"], "color_palette": st["color_palette"], "lighting": st["lighting"], "mood": st["mood"],
              "composition": "centered square portrait, head and shoulders, generous margin", "camera": {"angle": "eye level", "distance": "close medium shot", "lens": "85mm"}}
    # source convertie en PNG ≤ 1024 px (le webp lourd a fait échouer le chargement côté FAL)
    tmp = OUT / f"_src_{cid}.png"
    im = Image.open(src).convert("RGB"); im.thumbnail((1024, 1024)); im.save(tmp, "PNG")
    ref = fal_client.upload_file(str(tmp))
    for essai in range(5):
        try:
            res = fal_client.subscribe("fal-ai/flux-2-pro/edit", arguments={"prompt": json.dumps(prompt), "image_urls": [ref], "image_size": {"width": 1024, "height": 1024}, "output_format": "png", "seed": seed + essai})
            url = res["images"][0]["url"]
            data = fal_client.__dict__.get("httpx", __import__("httpx")).get(url, timeout=120).content
            out = OUT / f"{style}_{cid}.png"; out.write_bytes(data); return out
        except Exception as e:
            print(f"  essai {essai+1} KO ({str(e)[:80]}) — retry"); time.sleep(2)
    return None

def planche(chemins, ids, styles):
    T = 360; im = Image.new("RGB", (T * (len(ids) + 1), T * len(styles)), "#0a1428"); d = ImageDraw.Draw(im)
    try: police = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception: police = ImageFont.load_default()
    for r, style in enumerate(styles):
        d.text((16, r * T + T // 2 - 12), style.upper(), font=police, fill="#ff5f6b")
        for c, cid in enumerate(ids):
            p = chemins.get((style, cid))
            if p and p.exists():
                th = Image.open(p).convert("RGB").resize((T - 12, T - 12)); im.paste(th, ((c + 1) * T + 6, r * T + 6))
            d.text(((c + 1) * T + 12, r * T + T - 32), NOMS.get(cid, cid), font=police, fill="#f4f6fb")
    out = OUT / "planche.png"; im.save(out); return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", default="marine-le-pen,jean-luc-melenchon,edouard-philippe"); ap.add_argument("--styles", default="jours,plateau"); a = ap.parse_args()
    ids, styles = a.ids.split(","), a.styles.split(",")
    chemins = {(st, cid): OUT / f"{st}_{cid}.png" for st in STYLES for cid in NOMS if (OUT / f"{st}_{cid}.png").exists()}
    for style in styles:
        for cid in ids:
            print(f"{style} × {cid} …", flush=True); p = generer(cid, style)
            if p: chemins[(style, cid)] = p; print("  →", p.name)
    print("planche :", planche(chemins, list(NOMS), list(STYLES)))
